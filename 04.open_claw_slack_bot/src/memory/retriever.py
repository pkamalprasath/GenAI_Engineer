"""
Memory Retriever -- Keyword-Based Search Across All Memory Layers
==================================================================

WHY THIS FILE IS REQUIRED:
    Storing data is only half the problem.  The other half is *finding the
    right data* when the LLM needs context to answer a question.  This module
    provides a unified search interface that queries both short-term (RAM) and
    long-term (disk) memory stores and returns a ranked list of matching
    entries.

    Without a retriever, the bot would have to dump ALL stored data into the
    prompt on every request -- wasteful, expensive, and often exceeding the
    context window.  The retriever selectively pulls in only the relevant
    fragments.

PROGRAM LOGIC:
    1. `search(query, user_id, channel_id)` is the single entry-point.
    2. **Short-term search** (if user_id and channel_id are provided):
       Iterates over the in-memory messages for that user-channel pair and
       checks if the query appears as a case-insensitive substring.
    3. **Long-term search (MEMORY.md)**:
       Reads the curated memory file and checks for a substring match.
       If found, includes up to the first 2000 characters as a result.
    4. **Daily-log search**:
       Iterates over every daily log file on disk and checks each for a
       substring match.  Matching logs are truncated to 1000 characters.
    5. All matching results are collected into a flat list and returned.

WHY THIS APPROACH (keyword / substring search):
    This is the simplest retrieval strategy: `query.lower() in text.lower()`.
    It has zero external dependencies and is trivially correct.

    Limitations:
        - No semantic understanding: searching for "budget" will NOT find a
          message that says "how much money do we have?"
        - Linear scan: O(N) over all daily logs.  Fine for hundreds of files;
          slow for millions.

    The architecture is designed for easy upgrades:
        - **Phase 2**: Add TF-IDF or BM25 scoring for better ranking.
        - **Phase 3**: Add vector embeddings (via OpenAI / Sentence-Transformers)
          and ChromaDB for true semantic search.
        The `settings.chroma_persist_directory` and `settings.openai_api_key`
        fields in `config/settings.py` are already reserved for Phase 3.

RELATIONSHIP TO OTHER FILES:
    - `src/memory/short_term.py` -- the retriever reads from its contexts.
    - `src/memory/long_term.py`  -- the retriever reads MEMORY.md and daily
      logs through this class's public methods.
    - `src/memory/manager.py`    -- owns the retriever and exposes
      `recall_memory()` as a high-level wrapper.
    - `src/memory/schemas.py`    -- `ConversationContext` defines the shape
      of the message dicts that the short-term search iterates over.

SECURITY CONSIDERATIONS:
    - **Content truncation**: Long-term results are capped at 2000 chars and
      daily-log results at 1000 chars.  This limits the amount of potentially
      sensitive data injected into the LLM prompt and reduces prompt-injection
      attack surface.
    - **No access control**: Any search query can access any user's data.  In
      a multi-tenant deployment, add user/channel-scoped filtering to the
      long-term search methods.
    - **Timing side-channel**: Substring search is not constant-time.  An
      attacker who can measure response latency could theoretically infer
      whether certain content exists in memory.  For most Slack-bot use cases
      this is not a practical threat.
"""

from typing import List, Dict, Any, Optional

from src.memory.short_term import ShortTermMemory
from src.memory.long_term import LongTermMemory
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryRetriever:
    """
    Searches across all memory stores for information relevant to a query.

    Currently implements case-insensitive substring matching.  Designed to be
    upgraded to vector-similarity search in a future iteration.
    """

    def __init__(
        self,
        short_term: Optional[ShortTermMemory] = None,
        long_term: Optional[LongTermMemory] = None,
    ):
        """
        Initialise the retriever with references to both memory stores.

        WHY optional parameters with fallback instantiation:
            - When created by `MemoryManager`, concrete instances are injected
              so that the manager, short-term store, and retriever all share
              the same data.
            - When used standalone (e.g. in a quick script or test), the
              retriever can create its own stores with default settings.
            This pattern is sometimes called "poor man's dependency injection".

        Args:
            short_term: An existing ShortTermMemory instance, or None to
                        create a fresh one.
            long_term:  An existing LongTermMemory instance, or None to
                        create a fresh one.
        """
        self.short_term = short_term or ShortTermMemory()
        self.long_term = long_term or LongTermMemory()
        logger.info("Memory retriever initialized")

    def search(
        self, query: str, user_id: Optional[str] = None, channel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across memory stores for relevant information.

        WHY a unified search method:
            The caller (MemoryManager) should not need to know *which* layer
            holds the answer.  By searching all layers here and merging the
            results, the manager can simply ask "what do you know about X?"
            and get a flat list regardless of where the data lives.

        Args:
            query:      The search string (case-insensitive substring match).
            user_id:    Optional Slack user ID.  When provided together with
                        channel_id, short-term memory is also searched.
            channel_id: Optional Slack channel ID.  Required alongside
                        user_id for short-term search.

        Returns:
            A list of result dicts.  Each dict contains at minimum:
                - "source":  one of "short_term", "long_term", "daily_log"
                - "content": the matching text (possibly truncated)
            Additional keys vary by source (e.g. "role", "timestamp", "date").
        """
        results: List[Dict[str, Any]] = []

        # -----------------------------------------------------------------
        # Layer 1: Short-term memory (in-process RAM)
        # -----------------------------------------------------------------
        # WHY guard with `if user_id and channel_id`:
        #   Short-term memory is keyed by user+channel.  Without both IDs we
        #   cannot look up a specific context.  Skipping this layer when IDs
        #   are missing is intentional -- it means "search only long-term".
        if user_id and channel_id:
            context = self.short_term.get_context(user_id, channel_id)
            for msg in context.messages:
                # Case-insensitive substring match -- simple but effective
                # for keyword-style queries.
                if query.lower() in msg.get("content", "").lower():
                    results.append(
                        {
                            "source": "short_term",
                            "content": msg["content"],
                            "role": msg.get("role", "unknown"),
                            "timestamp": msg.get("timestamp"),
                        }
                    )

        # -----------------------------------------------------------------
        # Layer 2: Curated long-term memory (MEMORY.md)
        # -----------------------------------------------------------------
        # WHY search the whole file as one block:
        #   MEMORY.md is a curated, relatively small file (distilled
        #   summaries).  Checking for a substring in the full text is fast
        #   enough.  If found, we return the first 2000 characters to keep
        #   the result size bounded.
        # WHY 2000 characters:
        #   Roughly ~500 tokens -- enough context to be useful without
        #   dominating the LLM's input budget.
        memory_content = self.long_term.read_memory()
        if memory_content and query.lower() in memory_content.lower():
            results.append(
                {
                    "source": "long_term",
                    "content": memory_content[:2000],
                    "type": "memory_file",
                }
            )

        # -----------------------------------------------------------------
        # Layer 3: Daily interaction logs (memory/YYYY-MM-DD.md)
        # -----------------------------------------------------------------
        # WHY iterate ALL dates:
        #   The query might reference something from any past day.  A future
        #   optimisation could accept a date-range filter to narrow the scan.
        # WHY 1000 characters per log:
        #   Daily logs can be large (hundreds of interactions).  Truncating
        #   prevents any single day from flooding the result set.
        daily_dates = self.long_term.get_all_daily_logs()
        for date in daily_dates:
            log_content = self.long_term.read_daily_log(date)
            if log_content and query.lower() in log_content.lower():
                results.append(
                    {
                        "source": "daily_log",
                        "content": log_content[:1000],
                        "date": date,
                    }
                )

        logger.debug(f"Memory search for '{query}' returned {len(results)} results")
        return results
