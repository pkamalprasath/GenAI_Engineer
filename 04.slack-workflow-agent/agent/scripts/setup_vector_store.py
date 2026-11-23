"""
Vector Store Setup Script
==========================

WHY THIS FILE IS REQUIRED:
    The RAG (Retrieval-Augmented Generation) pipeline depends on a ChromaDB
    vector store to persist and search conversation embeddings.  ChromaDB uses
    on-disk storage (via ``PersistentClient``) that must be initialized before
    the first indexing or query operation can succeed.  Without running this
    script first:
      - The ``memory_store/chroma_db/`` directory may not exist, causing
        ChromaDB to fail with a ``FileNotFoundError`` on first use.
      - There is no upfront verification that ChromaDB is correctly installed
        and that its HNSW index configuration is valid.
      - Operators have no quick way to confirm that the vector store is healthy
        after a fresh deployment or after wiping the data directory.

    This script serves as a one-time (or on-demand) initialization step that
    validates the entire ChromaDB setup and reports the current state of the
    ``slack_conversations`` collection.

PROGRAM LOGIC:
    1. Add the project root to ``sys.path`` so that ``src.*`` and ``config.*``
       imports resolve correctly when the script is run directly from the
       ``scripts/`` directory (e.g., ``python scripts/setup_vector_store.py``).
    2. Initialize the project's logging system so that all log output follows
       the same structured format as the rest of the application.
    3. Instantiate a ``VectorStore`` object.  Internally, this:
       a. Creates a ``chromadb.PersistentClient`` pointing at the configured
          ``chroma_persist_directory`` (from ``config/settings.py``).
       b. Calls ``get_or_create_collection("slack_conversations")`` with HNSW
          cosine similarity, which is idempotent -- it creates the collection
          on first run and simply opens it on subsequent runs.
    4. Log the collection name, current document count, and index type to
       confirm the store is operational.
    5. If any step fails, log the error and exit with a non-zero status code
       so that CI pipelines or setup scripts can detect the failure.

WHY THIS APPROACH:
    - **Standalone script** (not integrated into the bot's startup): The vector
      store initialization is separated from ``src/main.py`` because it is a
      one-time setup step, not something that should run on every bot restart.
      Keeping it separate also means it can be run by an operator or CI pipeline
      without starting the full Slack bot.
    - **``sys.path`` manipulation**: Python does not automatically resolve
      sibling-package imports (``src.*``, ``config.*``) when a script is run
      directly.  Inserting the project root into ``sys.path`` is the standard
      workaround for scripts that live in a ``scripts/`` directory outside the
      main source tree.  An alternative would be to use ``-m`` invocation
      (``python -m scripts.setup_vector_store``), but that requires the caller
      to know the correct module path.
    - **Fail-fast with ``sys.exit(1)``**: If the vector store cannot be
      initialized, there is no point in continuing silently.  Exiting with
      status 1 signals failure to the calling process (shell, CI runner, etc.).
    - **Logging over print**: Using the project's logging infrastructure
      (``setup_logging()`` + ``get_logger()``) ensures that output format,
      log levels, and destinations are consistent with the rest of the
      application, making it easy to capture in log aggregation systems.

RELATIONSHIP TO OTHER FILES:
    - ``src/rag/store.py`` (dependency)
        Provides the ``VectorStore`` class that this script instantiates.
        All ChromaDB interaction is encapsulated there.
    - ``config/settings.py`` (indirect dependency)
        ``VectorStore.__init__`` reads ``settings.chroma_persist_directory`` to
        determine where to create/open the on-disk database.
    - ``src/utils/logger.py`` (dependency)
        Provides ``setup_logging()`` (configures the root logger) and
        ``get_logger()`` (creates a module-scoped logger).
    - ``scripts/index_channels.py`` (downstream)
        After this script initializes the store, ``index_channels.py`` populates
        it with Slack message embeddings.  Running this script first is a
        prerequisite for indexing.
    - ``src/rag/retriever.py`` (downstream)
        Queries the collection that this script creates.  If the collection does
        not exist, retrieval will fail.
"""

import sys
from pathlib import Path

# WHY sys.path manipulation: When this script is executed directly
# (``python scripts/setup_vector_store.py``), Python sets ``__file__`` to the
# script's own path and does not add the project root to ``sys.path``.  Without
# this line, ``from src.rag.store import VectorStore`` would raise
# ``ModuleNotFoundError`` because Python cannot find the ``src`` package.
# ``Path(__file__).parent.parent`` resolves to the project root regardless of
# the current working directory, making the script invocation location-agnostic.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.store import VectorStore
from src.utils.logger import setup_logging, get_logger

# WHY setup_logging() before get_logger(): ``setup_logging()`` configures the
# root logger (format, level, handlers).  If ``get_logger()`` were called first,
# the logger would use Python's default configuration (WARNING level, no
# formatting), and all INFO/DEBUG messages from this script would be silently
# dropped.
setup_logging()
logger = get_logger(__name__)


def main():
    """
    Initialize the ChromaDB vector store and verify its health.

    HOW IT WORKS:
        Creates a ``VectorStore`` instance, which internally initializes a
        ``chromadb.PersistentClient`` and opens (or creates) the
        ``slack_conversations`` collection.  On success, it logs the collection
        metadata (name, document count, index algorithm) so the operator can
        confirm the store is ready.  On failure, it logs the exception and
        exits with status code 1.

    WHY IMPLEMENTED THIS WAY:
        - The function is intentionally minimal: its only job is to prove that
          the vector store can be created and queried.  Any bug in
          ``VectorStore.__init__`` will surface here with a clear error message,
          making this script an effective smoke test.
        - ``store.collection.count()`` is called to verify not just that the
          collection exists, but that it is readable.  A corrupted data
          directory would fail at this point, giving early warning.
        - Wrapping everything in try/except ensures that the error is logged
          through the project's logging system (not just printed to stderr as
          an unhandled traceback), which is important when this script is run
          in a CI pipeline that captures structured logs.
    """
    logger.info("Initializing ChromaDB vector store...")

    try:
        # WHY no arguments to VectorStore(): The constructor reads all
        # configuration (persist directory, collection name, HNSW settings)
        # from ``config/settings.py``, following the project convention that
        # all tunable values live in one place.
        store = VectorStore()

        # WHY log these specific fields: They are the minimum information an
        # operator needs to verify a successful setup:
        #   - Collection name: confirms the correct collection was opened.
        #   - Document count: shows whether this is a fresh (0) or existing
        #     (>0) store, helping distinguish first-time setup from re-runs.
        #   - Index type: confirms that HNSW with cosine similarity is active,
        #     which is essential for correct semantic search results.
        logger.info(f"✓ Vector store initialized successfully")
        logger.info(f"  Collection: slack_conversations")
        logger.info(f"  Document count: {store.collection.count()}")
        logger.info(f"  Indexing: HNSW with cosine similarity")

    except Exception as e:
        # WHY sys.exit(1): A non-zero exit code signals failure to the calling
        # process (shell script, Makefile, CI runner).  Without it, the script
        # would exit with code 0 (success) even after a failure, potentially
        # allowing downstream steps (like indexing) to run against a broken
        # vector store.
        logger.error(f"Failed to initialize vector store: {e}")
        sys.exit(1)


# WHY __name__ guard: Allows this module to be imported without executing
# ``main()`` (useful for testing or reuse).  When run directly, Python sets
# ``__name__`` to ``"__main__"`` and the entry point fires.
if __name__ == "__main__":
    main()
