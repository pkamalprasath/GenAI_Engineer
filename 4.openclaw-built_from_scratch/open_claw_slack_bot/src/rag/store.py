"""
Vector Store Management

WHY THIS FILE IS REQUIRED:
    This module provides the persistence layer for the RAG (Retrieval-Augmented
    Generation) pipeline. Without a vector store, the system would have no way
    to persist conversation embeddings between restarts or perform fast semantic
    similarity searches. ChromaDB is used as the embedded vector database,
    meaning it runs in-process with no external database server required -- this
    simplifies deployment while still providing high-performance approximate
    nearest-neighbor (ANN) search.

PROGRAM LOGIC:
    1. On initialization, a PersistentClient is created so that all indexed
       vectors survive process restarts (stored on disk at a configured path).
    2. A single ChromaDB "collection" named ``slack_conversations`` is created
       (or re-opened if it already exists). This collection uses cosine distance
       as the similarity metric, which is the standard choice for text embeddings
       because it measures the angle between vectors and is insensitive to their
       magnitude.
    3. Three public methods expose the core CRUD operations that the rest of the
       RAG pipeline needs:
       - ``add_documents``  -- upsert documents (used by the Indexer)
       - ``query``          -- semantic search   (used by the Retriever)
       - ``delete_by_channel`` -- bulk delete     (used during re-indexing)

WHY THIS APPROACH:
    * ChromaDB was chosen over FAISS or Pinecone because it is open-source,
      embeddable (no infrastructure to manage), and natively supports metadata
      filtering -- which we need for per-channel queries.
    * All ChromaDB calls are synchronous. The callers in the async RAG layer
      (indexer.py, retriever.py) wrap these calls with ``asyncio.to_thread``
      to avoid blocking the event loop. Keeping this module synchronous avoids
      mixing sync/async concerns in the storage layer itself.
    * Errors are caught and re-raised as ``VectorStoreError`` to give upstream
      code a single, predictable exception type to handle.

RELATIONSHIP TO OTHER FILES:
    - ``src/rag/indexer.py``    -- Creates an instance of VectorStore to persist
                                   newly indexed Slack messages.
    - ``src/rag/retriever.py``  -- Creates an instance of VectorStore to run
                                   similarity queries at inference time.
    - ``config/settings.py``    -- Supplies ``chroma_persist_directory`` (where
                                   the database files live on disk).
    - ``src/utils/exceptions.py`` -- Defines ``VectorStoreError``.
    - ``src/utils/logger.py``   -- Provides structured logging.

Manages ChromaDB vector store for RAG knowledge base.
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import VectorStoreError

# Module-level logger follows the project convention of one logger per module.
# Using __name__ ensures the log records carry the fully-qualified module path
# (e.g., "src.rag.store"), which makes filtering and debugging straightforward.
logger = get_logger(__name__)


class VectorStore:
    """ChromaDB vector store manager.

    This class encapsulates every interaction with the ChromaDB database so that
    the rest of the codebase never imports ``chromadb`` directly.  This keeps the
    storage technology as a swappable implementation detail -- if the project ever
    migrates to Pinecone, Weaviate, or another engine, only this file needs to
    change.
    """

    def __init__(self):
        """Initialize ChromaDB client and open (or create) the collection.

        Why PersistentClient?
            ChromaDB offers both in-memory and persistent clients.  We use the
            persistent variant because the Slack conversation embeddings should
            survive bot restarts. The storage path comes from centralized
            settings so it can differ between dev, test, and production.

        Why disable anonymized_telemetry?
            ChromaDB sends anonymous usage data by default.  Disabling it is a
            security/privacy best practice -- enterprise deployments often
            prohibit outbound telemetry from internal services.

        Why "cosine" as the HNSW space?
            HNSW (Hierarchical Navigable Small World) is the ANN index algorithm
            ChromaDB uses internally.  The ``hnsw:space`` metadata tells it which
            distance function to use.  Cosine distance is the most common choice
            for text embeddings because it focuses on directional similarity
            rather than absolute magnitude, making it robust against embeddings
            of different norms.

        Raises:
            VectorStoreError: If ChromaDB fails to initialize (e.g., bad path,
                corrupt data directory, permission error).
        """
        try:
            # PersistentClient writes the index to ``settings.chroma_persist_directory``
            # so that data survives process restarts without re-indexing.
            self.client = chromadb.PersistentClient(
                path=settings.chroma_persist_directory,
                # Disable telemetry to prevent unintended outbound network traffic.
                settings=Settings(anonymized_telemetry=False),
            )

            # get_or_create_collection is idempotent: on first run it creates the
            # collection; on subsequent runs it simply opens the existing one.
            # This avoids the need for a separate "migration" or "init" step.
            self.collection = self.client.get_or_create_collection(
                name="slack_conversations",
                # HNSW with cosine space -- cosine similarity is standard for
                # semantic search with text embeddings (e.g., OpenAI ada-002).
                metadata={"hnsw:space": "cosine"}  # HNSW indexing
            )

            # Log the current document count so operators can verify that
            # previously indexed data was loaded successfully after a restart.
            logger.info(f"Vector store initialized: {self.collection.count()} documents")

        except Exception as e:
            # Wrap all init failures into VectorStoreError so callers have one
            # exception type to catch rather than chasing ChromaDB internals.
            raise VectorStoreError(f"Failed to initialize vector store: {e}")

    def add_documents(
        self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]
    ) -> None:
        """Add documents to vector store.

        ChromaDB will automatically compute embeddings for each document using its
        default embedding function (Sentence Transformers / all-MiniLM-L6-v2) if
        no custom embedding function was supplied at collection creation time.

        Why accept parallel lists instead of a list of dicts?
            This matches ChromaDB's native ``collection.add()`` signature, avoiding
            an unnecessary transformation step. Keeping the interface aligned with
            the underlying database reduces complexity and allocation overhead.

        Design note -- Idempotency:
            ChromaDB ``add`` will raise if a duplicate ID is inserted.  The caller
            (ConversationIndexer) constructs IDs deterministically from
            ``channel_id:timestamp``, and uses ``reindex_channel`` (delete + add)
            to avoid duplicates.

        Args:
            documents: Raw text contents to embed and store.
            metadatas: One metadata dict per document (channel_id, user_id, etc.).
            ids:       Unique identifiers for each document (used for dedup).

        Raises:
            VectorStoreError: If the underlying ChromaDB ``add`` call fails.
        """
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            logger.debug(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            raise VectorStoreError(f"Failed to add documents: {e}")

    def query(
        self, query_text: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query vector store for similar documents.

        Performs an approximate nearest-neighbor search using the HNSW index.
        The query text is embedded on-the-fly using the same embedding model
        that was used during indexing, ensuring the vector spaces match.

        Why accept ``where`` as a raw dict?
            ChromaDB's metadata filtering uses a dict-based DSL
            (e.g., ``{"channel_id": "C123"}``).  Passing it through unchanged
            keeps this layer thin and avoids inventing a redundant abstraction.

        Security consideration:
            The ``where`` filter is constructed internally (by the Retriever) --
            it is never built from raw user input.  If it were, the caller
            should validate the filter keys to prevent metadata injection.

        Args:
            query_text: Natural-language query to embed and search against.
            n_results:  Maximum number of results to return (default 5).
            where:      Optional ChromaDB metadata filter dict.

        Returns:
            Raw ChromaDB result dict containing ``documents``, ``metadatas``,
            ``distances``, and ``ids`` -- each as a list-of-lists (one inner
            list per query, but we always send a single query).

        Raises:
            RetrievalError via VectorStoreError if the query fails.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text], n_results=n_results, where=where
            )
            logger.debug(f"Query returned {len(results['documents'][0])} results")
            return results
        except Exception as e:
            raise VectorStoreError(f"Query failed: {e}")

    def delete_by_channel(self, channel_id: str) -> None:
        """Delete all documents for a channel.

        Used by ``ConversationIndexer.reindex_channel`` to purge stale data
        before inserting a fresh set of messages.  This "delete-then-add"
        pattern is simpler and more reliable than trying to diff old vs. new
        documents, especially since Slack message edits can silently change
        content without changing the message timestamp.

        Security consideration:
            ``channel_id`` is expected to be a Slack channel ID (e.g.,
            "C01ABCDEF").  In a multi-tenant deployment, ensure that the caller
            validates ownership before deleting an entire channel's worth of
            indexed data.

        Args:
            channel_id: The Slack channel whose documents should be purged.

        Raises:
            VectorStoreError: If the delete operation fails.
        """
        try:
            self.collection.delete(where={"channel_id": channel_id})
            logger.info(f"Deleted documents for channel {channel_id}")
        except Exception as e:
            raise VectorStoreError(f"Failed to delete documents: {e}")
