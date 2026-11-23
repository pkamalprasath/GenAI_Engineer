"""
Conversation Indexer

WHY THIS FILE IS REQUIRED:
    The RAG pipeline needs a way to transform raw Slack messages into searchable
    vector-store documents.  This module is the "write path" of the RAG system:
    it receives a batch of Slack messages, extracts the relevant text and
    metadata, and persists them into the ChromaDB vector store (via
    ``VectorStore``).  Without this indexer, the retriever would have nothing to
    search against.

PROGRAM LOGIC:
    1. ``index_messages`` takes a channel ID and a list of raw Slack message
       dicts (as returned by the Slack API).
    2. Each message is validated -- empty texts and missing timestamps are
       skipped because they would produce meaningless embeddings and unstable
       document IDs.
    3. Valid messages are batched into three parallel lists (documents,
       metadatas, ids) that match the ChromaDB ``add`` signature.
    4. The batch is sent to ``VectorStore.add_documents`` inside
       ``asyncio.to_thread`` so that the synchronous ChromaDB call does not
       block the async event loop.
    5. ``reindex_channel`` provides a convenient "delete old + insert new"
       workflow for keeping the index fresh.

WHY THIS APPROACH:
    * Batching -- All messages for a channel are added in a single
      ``add_documents`` call rather than one-at-a-time.  This is dramatically
      more efficient because ChromaDB can batch-embed and batch-insert
      internally, reducing both embedding API calls and disk I/O.
    * Deterministic IDs -- Document IDs are ``{channel_id}:{timestamp}``.
      Slack message timestamps are unique per channel, so this naturally
      prevents duplicate indexing.  It also means re-indexing the same message
      is idempotent.
    * Message limit -- ``settings.rag_message_limit`` caps the number of
      messages indexed per call, protecting against runaway memory/time usage
      on very active channels.

RELATIONSHIP TO OTHER FILES:
    - ``src/rag/store.py``       -- The VectorStore that this indexer writes to.
    - ``src/rag/retriever.py``   -- The "read path" counterpart; queries what
                                    this indexer writes.
    - ``src/mcp_servers/slack_server.py`` -- Provides the raw Slack messages
                                    that are ultimately fed to this indexer.
    - ``config/settings.py``     -- Supplies ``rag_message_limit``.
    - ``src/utils/exceptions.py`` -- Defines ``IndexingError``.

Indexes Slack conversations into vector store for RAG.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime

from src.rag.store import VectorStore
from src.utils.logger import get_logger
from src.utils.exceptions import IndexingError
from config.settings import settings

# One logger per module; the name encodes the full import path for easy
# filtering (e.g., ``src.rag.indexer``).
logger = get_logger(__name__)


class ConversationIndexer:
    """Indexes Slack conversations for RAG.

    This class is stateless beyond holding a reference to its ``VectorStore``
    instance.  It can safely be instantiated once and reused across many
    indexing calls without worrying about stale internal state.

    Design decision -- why a class instead of bare functions?
        Wrapping the logic in a class lets us construct the (potentially
        expensive) ``VectorStore`` once and share it across calls.  It also
        provides a clean seam for dependency injection in tests -- a test can
        subclass or monkeypatch ``self.vector_store``.
    """

    def __init__(self):
        """Create the indexer and its underlying vector store.

        The VectorStore is instantiated eagerly (in __init__) rather than
        lazily because we want startup failures to surface immediately,
        not silently on the first indexing attempt.
        """
        self.vector_store = VectorStore()
        logger.info("Conversation indexer initialized")

    async def index_messages(self, channel_id: str, messages: List[Dict[str, Any]]) -> int:
        """Index messages from a channel.

        Transforms raw Slack message dicts into vector-store documents and
        persists them.  Messages that lack text or a timestamp are silently
        skipped because:
          - Empty text would produce a meaningless (near-zero) embedding that
            pollutes search results.
          - Missing timestamp means we cannot construct a stable document ID,
            which would risk duplicates on re-indexing.

        Why ``asyncio.to_thread``?
            ``VectorStore.add_documents`` is synchronous (ChromaDB is a sync
            library).  Calling it directly inside this ``async`` method would
            block the event loop and freeze all concurrent coroutines.
            ``asyncio.to_thread`` offloads the call to a thread-pool worker,
            keeping the event loop responsive.

        Args:
            channel_id: Slack channel identifier (e.g., "C01ABCDEF").
            messages:   List of raw Slack message dicts, each expected to have
                        at least ``text``, ``ts``, and optionally ``user``.

        Returns:
            The number of messages successfully indexed.

        Raises:
            IndexingError: If the vector-store write fails.
        """
        try:
            # ----------------------------------------------------------------
            # Step 1: Prepare parallel lists for ChromaDB's batch API.
            # ChromaDB.add() expects three aligned lists: documents, metadatas,
            # and ids.  Building them in a single pass is efficient and clear.
            # ----------------------------------------------------------------
            documents = []
            metadatas = []
            ids = []

            # Slice to ``rag_message_limit`` BEFORE the loop to cap both
            # processing time and the number of embeddings computed.  Older
            # messages (at higher indices) are dropped because Slack returns
            # messages in reverse-chronological order, so the most recent ones
            # come first and are more likely to be relevant.
            for msg in messages[: settings.rag_message_limit]:
                text = msg.get("text", "")
                ts = msg.get("ts", "")
                user = msg.get("user", "")

                # Skip messages that would produce useless embeddings or
                # unstable IDs (see method docstring for rationale).
                if not text or not ts:
                    continue

                documents.append(text)
                metadatas.append(
                    {
                        # Metadata is stored alongside each vector in ChromaDB
                        # and can be used for filtered queries (e.g., retrieve
                        # only from a specific channel).
                        "channel_id": channel_id,
                        "user_id": user,
                        "timestamp": ts,
                        # ``indexed_at`` is informational -- useful for auditing
                        # when a particular message was last indexed.
                        "indexed_at": datetime.now().isoformat(),
                    }
                )
                # Deterministic ID: ``channel_id:timestamp`` guarantees
                # uniqueness within a channel (Slack timestamps are unique per
                # channel) and makes re-indexing idempotent.
                ids.append(f"{channel_id}:{ts}")

            # ----------------------------------------------------------------
            # Step 2: Persist to the vector store (off the event loop).
            # Only call add_documents if there is at least one valid document;
            # an empty add would be a pointless no-op (and some DB drivers
            # might even error on an empty batch).
            # ----------------------------------------------------------------
            if documents:
                await asyncio.to_thread(
                    self.vector_store.add_documents,
                    documents=documents, metadatas=metadatas, ids=ids,
                )

                logger.info(f"Indexed {len(documents)} messages from {channel_id}")
                return len(documents)

            return 0

        except Exception as e:
            # Wrap all failures into a domain-specific exception so callers
            # can handle indexing problems uniformly.
            raise IndexingError(f"Failed to index messages: {e}")

    async def reindex_channel(self, channel_id: str, messages: List[Dict[str, Any]]) -> int:
        """Reindex a channel (delete old, add new).

        This two-step "purge + insert" approach is preferred over incremental
        updates for several reasons:
          1. Simplicity -- no need to diff old vs. new documents.
          2. Correctness -- edited or deleted Slack messages are automatically
             removed because the old index is wiped entirely.
          3. Consistency -- the channel's index always reflects a single,
             complete snapshot of its messages.

        The downside is that there is a brief window (between delete and add)
        where the channel has zero indexed documents.  For a Slack assistant
        this is acceptable because re-indexing is infrequent and the window
        is very short (milliseconds).

        Args:
            channel_id: Slack channel identifier to reindex.
            messages:   Fresh list of messages to replace the old index with.

        Returns:
            The number of messages indexed in the new batch.

        Raises:
            IndexingError: If either the delete or the insert fails.
        """
        try:
            # Step 1: Remove all previously indexed documents for this channel.
            # Uses asyncio.to_thread for the same reason as index_messages.
            await asyncio.to_thread(self.vector_store.delete_by_channel, channel_id)

            # Step 2: Insert the fresh batch.
            return await self.index_messages(channel_id, messages)

        except Exception as e:
            raise IndexingError(f"Failed to reindex channel: {e}")
