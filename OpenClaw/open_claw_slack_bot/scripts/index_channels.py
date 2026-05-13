"""
Bulk Channel Indexing Script
==============================

WHY THIS FILE IS REQUIRED:
    The RAG (Retrieval-Augmented Generation) pipeline can only retrieve
    information that has been previously indexed.  When the bot is first
    deployed -- or when the vector store is wiped and recreated -- the
    ``slack_conversations`` collection is empty, meaning the bot has zero
    knowledge of past conversations.  This script fills that gap by performing
    a one-time (or periodic) bulk import of messages from ALL accessible Slack
    channels into the ChromaDB vector store.

    Without this script:
      - The bot's RAG-based answers would be empty or irrelevant because there
        are no indexed documents to search against.
      - Operators would have to wait for the bot's cron-based incremental
        indexer (which runs every 2 hours by default) to gradually populate the
        store, during which time the bot would give poor answers.
      - There would be no convenient way to do a full re-index after a schema
        change, embedding model upgrade, or data corruption recovery.

PROGRAM LOGIC:
    1. Add the project root to ``sys.path`` so that ``src.*`` and ``config.*``
       imports resolve when the script is run directly.
    2. Initialize the project's logging system for structured output.
    3. Create an ``AsyncWebClient`` authenticated with the bot token from
       ``config/settings.py``.
    4. Create a ``ConversationIndexer`` that wraps the ``VectorStore`` and
       handles message-to-document transformation.
    5. Call ``conversations_list`` on the Slack API to discover all public and
       private channels the bot has access to.
    6. For each channel:
       a. Fetch up to ``settings.rag_message_limit`` recent messages using
          ``conversations_history``.
       b. Pass the raw messages to ``indexer.index_messages()``, which extracts
          text and metadata, computes embeddings, and persists them to ChromaDB.
       c. Log the per-channel count of indexed messages.
    7. Log the grand total of indexed messages across all channels.
    8. If any step fails, log the error and exit with status code 1.

WHY THIS APPROACH:
    - **Async with ``asyncio.run``**: The Slack Web API client is async
      (``AsyncWebClient``), and the ``ConversationIndexer`` uses
      ``asyncio.to_thread`` internally to offload synchronous ChromaDB calls.
      Running everything inside ``asyncio.run(main())`` keeps the script
      compatible with these async APIs without introducing threading complexity.
    - **All channel types** (``public_channel,private_channel``): The bot may
      be invited to private channels whose history is also valuable for RAG.
      Including both types ensures comprehensive coverage.  Note: the bot can
      only see channels it has been explicitly added to -- it cannot access
      channels it is not a member of.
    - **Per-channel iteration** (not bulk): Processing channels one at a time
      is deliberate.  It keeps peak memory usage bounded (only one channel's
      messages in memory at once), provides per-channel progress logging, and
      means a failure in one channel does not prevent the others from being
      indexed.  The tradeoff is slightly longer total runtime compared to
      concurrent indexing, but reliability is more important for a setup script.
    - **``settings.rag_message_limit``**: The number of messages fetched per
      channel is capped by this setting (default: 200).  This prevents the
      script from fetching millions of messages in very active channels, which
      would be slow, memory-intensive, and expensive in embedding API calls.
      The most recent messages are fetched first (Slack returns reverse-
      chronological order), so the cap favors recent, more-relevant content.
    - **Fail-fast with ``sys.exit(1)``**: If the Slack API is unreachable or
      the indexer crashes, the script exits immediately with a non-zero code.
      This is important for CI/CD pipelines that run this script as a setup step.

RELATIONSHIP TO OTHER FILES:
    - ``scripts/setup_vector_store.py`` (prerequisite)
        Should be run before this script to ensure the ChromaDB collection
        exists.  ``ConversationIndexer`` will also create the collection via
        ``VectorStore.__init__`` if it does not exist, but running
        ``setup_vector_store.py`` first provides explicit verification.
    - ``src/rag/indexer.py`` (dependency)
        Provides the ``ConversationIndexer`` class that transforms Slack
        messages into vector-store documents and persists them.
    - ``src/rag/store.py`` (indirect dependency)
        ``ConversationIndexer`` internally creates a ``VectorStore`` instance
        to write documents to ChromaDB.
    - ``config/settings.py`` (dependency)
        Supplies ``slack_bot_token`` (for the Slack API client) and
        ``rag_message_limit`` (caps messages fetched per channel).
    - ``src/utils/logger.py`` (dependency)
        Provides ``setup_logging()`` and ``get_logger()`` for structured output.
    - ``src/rag/retriever.py`` (downstream)
        Once this script populates the vector store, the retriever can perform
        semantic search against the indexed documents.
    - ``src/agent/context_builder.py`` (downstream)
        Uses the retriever to pull relevant context from the vector store when
        building prompts for the LLM agent.
"""

import sys
import asyncio
from pathlib import Path

# WHY sys.path manipulation: Same rationale as setup_vector_store.py -- enables
# ``from src.*`` and ``from config.*`` imports when the script is invoked
# directly from the command line (e.g., ``python scripts/index_channels.py``).
sys.path.insert(0, str(Path(__file__).parent.parent))

from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings
from src.rag.indexer import ConversationIndexer
from src.utils.logger import setup_logging, get_logger

# WHY setup_logging() first: Ensures that all subsequent log calls (including
# those from imported modules like ``VectorStore`` and ``ConversationIndexer``)
# use the project's configured log format, level, and handlers.
setup_logging()
logger = get_logger(__name__)


async def main():
    """
    Index messages from all accessible Slack channels into the vector store.

    HOW IT WORKS:
        1. Authenticates with the Slack API using the bot token.
        2. Fetches the list of all channels (public + private) the bot can see.
        3. Iterates through each channel, fetching its recent message history.
        4. Passes each channel's messages to ``ConversationIndexer.index_messages()``,
           which extracts text/metadata, computes embeddings via ChromaDB's
           default embedding function, and persists the documents.
        5. Accumulates and logs the total number of indexed messages.

    WHY IMPLEMENTED THIS WAY:
        - **Sequential channel processing**: Channels are indexed one at a time
          (not concurrently) to keep memory usage predictable and to provide
          clear per-channel progress logs.  Concurrent indexing would be faster
          but harder to debug when something goes wrong.
        - **``channel.get("name", "unknown")``**: Some private channels or
          shared channels may not have a ``name`` field in the API response.
          Defaulting to "unknown" prevents a ``KeyError`` from halting the
          entire indexing run.
        - **Single try/except around the entire flow**: If the Slack API is
          unreachable or the indexer fails on any channel, the script exits
          immediately.  A more sophisticated version could catch per-channel
          errors and continue with the remaining channels, but for a setup
          script, fail-fast is simpler and sufficient.
    """
    logger.info("Starting bulk channel indexing...")

    try:
        # WHY AsyncWebClient: The Slack SDK provides both synchronous
        # (``WebClient``) and asynchronous (``AsyncWebClient``) clients.  We
        # use the async variant because ``ConversationIndexer.index_messages``
        # is an async method that uses ``asyncio.to_thread`` internally.
        # Mixing sync and async clients would either block the event loop or
        # require additional thread management.
        slack_client = AsyncWebClient(token=settings.slack_bot_token)

        # WHY instantiate indexer here (not at module level): The
        # ``ConversationIndexer`` constructor creates a ``VectorStore``, which
        # opens the ChromaDB database.  Doing this inside ``main()`` ensures
        # the database connection is created within the async context and after
        # logging has been initialized.
        indexer = ConversationIndexer()

        # WHY both public_channel and private_channel: The bot may have been
        # invited to private channels containing valuable team discussions.
        # Omitting private channels would leave gaps in the RAG knowledge base.
        # Note: The API only returns channels the bot is a member of, so there
        # is no risk of accessing unauthorized data.
        response = await slack_client.conversations_list(
            types="public_channel,private_channel"
        )
        channels = response["channels"]

        logger.info(f"Found {len(channels)} channels")

        # WHY accumulate total_indexed: Provides a single summary metric at the
        # end of the run, which is useful for monitoring and for comparing
        # successive indexing runs (e.g., "last time we indexed 1200, now 1350,
        # so 150 new messages appeared").
        total_indexed = 0
        for channel in channels:
            channel_id = channel["id"]
            # WHY .get with default: Defensive coding against channels that may
            # lack a ``name`` field (e.g., some shared channels from external
            # organizations).  Using "unknown" keeps the log readable without
            # crashing the loop.
            channel_name = channel.get("name", "unknown")

            logger.info(f"Indexing #{channel_name}...")

            # WHY settings.rag_message_limit: Caps the number of messages
            # fetched per channel to control API usage, embedding cost, and
            # memory consumption.  Slack returns messages in reverse-
            # chronological order, so the limit naturally favors the most
            # recent (and typically most relevant) messages.
            messages_response = await slack_client.conversations_history(
                channel=channel_id,
                limit=settings.rag_message_limit
            )
            messages = messages_response["messages"]

            # WHY await indexer.index_messages: This async method handles:
            #   1. Filtering out messages with empty text or missing timestamps.
            #   2. Building parallel lists (documents, metadatas, ids) for
            #      ChromaDB's batch API.
            #   3. Offloading the synchronous ChromaDB write to a thread via
            #      ``asyncio.to_thread`` to keep the event loop responsive.
            count = await indexer.index_messages(channel_id, messages)
            total_indexed += count

            logger.info(f"  ✓ Indexed {count} messages")

        logger.info(f"✓ Bulk indexing complete: {total_indexed} total messages")

    except Exception as e:
        # WHY sys.exit(1): Ensures that CI pipelines, Makefiles, or shell
        # scripts that call this script can detect the failure via the non-zero
        # exit code and halt subsequent steps (e.g., do not start the bot if
        # indexing failed).
        logger.error(f"Indexing failed: {e}")
        sys.exit(1)


# WHY asyncio.run: This is the standard way to execute an async ``main()``
# function from a synchronous entry point.  It creates a new event loop, runs
# ``main()`` to completion, and then closes the loop.  This is preferred over
# manually managing the event loop because ``asyncio.run`` handles cleanup
# (cancelling pending tasks, closing the loop) automatically.
if __name__ == "__main__":
    asyncio.run(main())
