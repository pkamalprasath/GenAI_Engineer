"""
Semantic Retriever

WHY THIS FILE IS REQUIRED:
    This module is the "read path" of the RAG pipeline.  When the LLM needs
    extra context to answer a user's question, the Retriever searches the
    vector store for past Slack conversations that are semantically similar
    to the current query.  Those conversations are then injected into the
    LLM prompt as grounding context, dramatically improving answer accuracy
    and relevance.  Without this retriever, the LLM would rely solely on
    its parametric knowledge and have no access to the team's conversation
    history.

PROGRAM LOGIC:
    1. The caller passes a natural-language query and optionally a channel_id.
    2. ``retrieve()`` delegates to ``VectorStore.query()`` (via
       ``asyncio.to_thread`` to keep the event loop free).
    3. The raw ChromaDB results include cosine distances; these are converted
       to similarity scores (``1 - distance``) so that higher = more relevant.
    4. Results below the configurable ``relevance_threshold`` (default 0.7)
       are discarded to avoid polluting the LLM prompt with noise.
    5. ``format_context_for_prompt()`` transforms the surviving results into
       a Markdown string suitable for direct insertion into a system or user
       prompt.

WHY THIS APPROACH:
    * Cosine similarity is the natural complement to the cosine distance
      metric configured on the ChromaDB collection (see ``store.py``).
      Converting distance to similarity (``1 - distance``) makes the
      threshold intuitive: 0.7 means "at least 70% similar."
    * The relevance threshold acts as a quality gate.  In practice, returning
      low-similarity results hurts more than it helps because the LLM may
      treat irrelevant context as authoritative.  0.7 is a sensible default;
      it can be tuned per deployment.
    * Formatting results as Markdown with similarity scores lets the LLM
      reason about how confident each piece of context is, and gives
      developers a readable debug trace.

RELATIONSHIP TO OTHER FILES:
    - ``src/rag/store.py``    -- Provides the VectorStore that this retriever
                                 queries against.
    - ``src/rag/indexer.py``  -- The "write path" that populates the data this
                                 retriever searches.
    - ``src/agents/``         -- The agent layer calls ``retrieve()`` before
                                 constructing the LLM prompt, and uses
                                 ``format_context_for_prompt()`` to inject the
                                 results.
    - ``src/utils/exceptions.py`` -- Defines ``RetrievalError``.

Retrieves relevant context from vector store for RAG.
"""

import asyncio
from typing import List, Dict, Any, Optional

from src.rag.store import VectorStore
from src.utils.logger import get_logger
from src.utils.exceptions import RetrievalError

# Module-level logger -- records carry the path "src.rag.retriever".
logger = get_logger(__name__)


class SemanticRetriever:
    """Retrieves relevant context for RAG.

    Responsibilities:
      1. Execute semantic similarity searches against the vector store.
      2. Convert raw distances into human-interpretable similarity scores.
      3. Apply a relevance threshold to filter out low-quality matches.
      4. Format results into a prompt-friendly string.

    Design decision -- why separate Retriever and VectorStore?
        VectorStore is a thin, technology-specific wrapper around ChromaDB.
        SemanticRetriever adds domain logic (threshold filtering, prompt
        formatting) that is independent of the storage backend.  This
        separation means the retriever's logic would remain unchanged if
        VectorStore were swapped to Pinecone or FAISS.
    """

    def __init__(self):
        """Initialize retriever with a vector store and default threshold.

        ``relevance_threshold`` (0.7) was chosen empirically as a good
        balance between recall (returning enough context) and precision
        (not drowning the LLM in noise).  Lower values return more results
        but risk including tangential content; higher values are stricter.
        """
        self.vector_store = VectorStore()
        # Minimum cosine similarity (0.0 - 1.0) a result must have to be
        # included in the response.  Anything below this is considered
        # irrelevant and discarded.
        self.relevance_threshold = 0.7
        logger.info("Semantic retriever initialized")

    async def retrieve(
        self, query: str, channel_id: Optional[str] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context for query.

        Performs a semantic search against the vector store, converts raw
        ChromaDB distances into similarity scores, and filters by the
        relevance threshold.

        Why ``channel_id`` is optional:
            When provided, the search is scoped to a single Slack channel,
            which is useful for channel-specific Q&A.  When omitted, the
            search spans all indexed channels, which is useful for
            cross-channel knowledge retrieval.

        Why ``asyncio.to_thread``?
            Same rationale as in ``indexer.py`` -- ChromaDB is synchronous,
            and we must not block the async event loop.

        Args:
            query:      Natural-language question or search phrase.
            channel_id: Optional Slack channel ID to restrict the search to.
            top_k:      Maximum number of candidate results to fetch from
                        the vector store (before threshold filtering).

        Returns:
            A list of context dicts, each containing:
              - ``text``:       The original indexed message text.
              - ``similarity``: Cosine similarity score (0.0 - 1.0).
              - ``metadata``:   The stored metadata (channel, user, timestamp).
            The list is ordered by descending similarity (ChromaDB's default).

        Raises:
            RetrievalError: If the vector-store query fails.
        """
        try:
            # ------------------------------------------------------------------
            # Step 1: Build the optional metadata filter.
            # ChromaDB supports a ``where`` clause that restricts which
            # documents are considered during the ANN search.  We use this to
            # scope results to a single channel when requested.
            # ------------------------------------------------------------------
            where_filter = None
            if channel_id:
                where_filter = {"channel_id": channel_id}

            # ------------------------------------------------------------------
            # Step 2: Execute the vector similarity search off the event loop.
            # ``VectorStore.query`` is synchronous, so we wrap it with
            # ``asyncio.to_thread`` to keep the calling coroutine non-blocking.
            # ------------------------------------------------------------------
            results = await asyncio.to_thread(
                self.vector_store.query, query_text=query, n_results=top_k, where=where_filter
            )

            # ------------------------------------------------------------------
            # Step 3: Post-process results -- convert distances to similarities
            # and apply the relevance threshold.
            # ------------------------------------------------------------------
            contexts = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    # ChromaDB returns results as list-of-lists (one inner list
                    # per query text).  We always send a single query, so we
                    # index into position [0].
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0

                    # ChromaDB returns cosine *distance* (0 = identical,
                    # 2 = opposite).  Convert to cosine *similarity* (1 =
                    # identical, -1 = opposite) by subtracting from 1.
                    # This makes the threshold comparison intuitive:
                    #   similarity >= 0.7  means "at least 70% similar."
                    similarity = 1 - distance

                    # Discard results that fall below the quality gate.
                    # This prevents low-relevance noise from being injected
                    # into the LLM prompt, which could mislead the model.
                    if similarity >= self.relevance_threshold:
                        contexts.append(
                            {"text": doc, "similarity": similarity, "metadata": metadata}
                        )

            logger.debug(f"Retrieved {len(contexts)} relevant contexts")
            return contexts

        except Exception as e:
            raise RetrievalError(f"Failed to retrieve context: {e}")

    def format_context_for_prompt(self, contexts: List[Dict[str, Any]]) -> str:
        """Format retrieved contexts for LLM prompt.

        Produces a Markdown-formatted string that can be directly appended to
        a system or user prompt.  Each context block includes its similarity
        score so the LLM (and developers debugging prompts) can gauge how
        relevant each snippet is.

        Why Markdown?
            LLMs handle Markdown well -- headings and structure help the model
            parse multi-block context.  It is also human-readable in logs.

        Why include similarity scores?
            Exposing the score to the LLM enables it to weight higher-
            similarity context more heavily in its reasoning.  It also serves
            as a useful debugging signal when reviewing prompt construction.

        Args:
            contexts: List of context dicts as returned by ``retrieve()``.

        Returns:
            A Markdown-formatted string, or an empty string if no contexts
            were provided (which signals to the caller that no RAG context
            is available for this query).
        """
        if not contexts:
            return ""

        formatted = "# Relevant Context from Past Conversations\n\n"

        for i, ctx in enumerate(contexts, 1):
            formatted += f"## Context {i} (Similarity: {ctx['similarity']:.2f})\n"
            formatted += f"{ctx['text']}\n\n"

        return formatted
