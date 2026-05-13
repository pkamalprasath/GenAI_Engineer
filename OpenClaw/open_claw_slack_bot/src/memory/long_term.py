"""
Long-Term Memory (File-Backed Persistent Storage)
===================================================

WHY THIS FILE IS REQUIRED:
    Short-term memory lives only in RAM and vanishes when the process stops.
    For the bot to "remember" facts, preferences, and past interactions across
    restarts (and even across days/weeks), those memories must be persisted to
    durable storage.

    This module writes to and reads from plain Markdown files on the local
    file system.  It maintains two complementary stores:
        - **MEMORY.md**: A curated, ever-growing knowledge base of distilled
          insights (think "the bot's long-term notebook").
        - **memory/YYYY-MM-DD.md**: Raw daily logs of every interaction,
          one file per calendar day (think "the bot's diary").

PROGRAM LOGIC:
    1. On construction, the base directory and a `memory/` sub-directory are
       created if they do not already exist (`mkdir(parents=True, exist_ok=True)`).
    2. `write_to_memory` / `read_memory` operate on `MEMORY.md` -- the
       curated file.  Writing defaults to *append* mode so existing content
       is never overwritten by accident.
    3. `write_daily_log` / `read_daily_log` operate on per-day files inside
       the `memory/` sub-directory.  The file name is the ISO date, making it
       trivially sortable and human-browseable.
    4. `get_all_daily_logs` returns a list of date strings for every day that
       has a log file, enabling the retriever to iterate across all history.

WHY THIS APPROACH (plain Markdown files on disk):
    - **Zero infrastructure**: No database server, no external service.  The
      bot works out of the box with just a file system.
    - **Human-readable**: Operators can open the files in any editor, grep
      them, or render them on GitHub.  Great for debugging and auditing.
    - **Append-only safety**: Using file-append mode (`"a"`) is crash-safe on
      most operating systems -- even if the process dies mid-write, previously
      written data is intact.
    - **Easy migration path**: When scale demands it, swap this class for a
      database-backed implementation (same interface, different backend).

    Alternative considered: SQLite.  Rejected for v1 because Markdown files
    are easier to inspect during development.  The `database_url` setting in
    `config/settings.py` is reserved for a future SQLite/PostgreSQL backend.

RELATIONSHIP TO OTHER FILES:
    - `config/settings.py` provides `settings.memory_store_path`, the root
      directory for all file storage.
    - `src/memory/manager.py` owns the single `LongTermMemory` instance and
      calls `write_daily_log` after every interaction.
    - `src/memory/retriever.py` calls `read_memory`, `read_daily_log`, and
      `get_all_daily_logs` to search across persisted data.
    - `src/utils/exceptions.py` defines `MemoryWriteError` and
      `MemoryReadError`, custom exceptions that this module raises on I/O
      failures.

SECURITY CONSIDERATIONS:
    - Files are written with UTF-8 encoding; no encryption at rest.  If PII
      or secrets are stored, enable disk encryption at the OS level or add an
      application-layer encryption wrapper.
    - The `base_path` is configurable.  Ensure it points to a directory with
      restrictive file permissions (e.g. 0700) so other users on the same
      machine cannot read conversation logs.
    - `write_to_memory` and `write_daily_log` propagate any I/O exception as
      a custom `MemoryWriteError`.  Callers should catch this and decide
      whether to retry, alert, or degrade gracefully.
    - There is no file-locking mechanism.  Running multiple bot processes
      writing to the same directory could cause interleaved writes.  For
      multi-process deployments, switch to a database backend or add
      `fcntl.flock` / equivalent locking.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import MemoryWriteError, MemoryReadError

logger = get_logger(__name__)


class LongTermMemory:
    """
    File-backed long-term memory storage.

    Provides two persistence layers:
        1. MEMORY.md  -- curated knowledge (distilled summaries, user prefs).
        2. memory/YYYY-MM-DD.md -- raw daily conversation logs.

    All paths are derived from a single `base_path`, making the storage
    location fully configurable via environment variables.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialise the file-backed storage directories.

        WHY accept an optional `base_path`:
            - Production uses `settings.memory_store_path` (from `.env`).
            - Unit tests pass a temporary directory so tests don't pollute
              the real file system.
            The `or` fallback pattern makes both cases trivial.

        WHY `mkdir(parents=True, exist_ok=True)`:
            - `parents=True` creates intermediate directories if they are
              missing (e.g. `./memory_store/memory` when `memory_store/`
              doesn't exist yet).
            - `exist_ok=True` avoids a `FileExistsError` on subsequent runs.

        Args:
            base_path: Override for the root storage directory.  Falls back to
                       `settings.memory_store_path` if not provided.
        """
        self.base_path = Path(base_path or settings.memory_store_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create a dedicated sub-directory for daily log files, keeping them
        # separate from the curated MEMORY.md at the root.
        self.memory_dir = self.base_path / "memory"
        self.memory_dir.mkdir(exist_ok=True)

        logger.info(f"Long-term memory initialized at {self.base_path}")

    # --------------------------------------------------------------------- #
    #  Curated memory (MEMORY.md)                                            #
    # --------------------------------------------------------------------- #

    def write_to_memory(self, content: str, append: bool = True) -> None:
        """
        Write to MEMORY.md (curated long-term memory).

        WHY Markdown with timestamps:
            Each entry is written under an `## YYYY-MM-DD HH:MM:SS` header.
            This makes the file:
                - Chronologically ordered and easy to scan visually.
                - Parseable by the retriever (headers act as chunk boundaries).
                - Renderable by any Markdown viewer.

        WHY default to append (`append=True`):
            Overwriting would destroy all previous curated knowledge.  Append
            is the safe default; the `append=False` escape hatch exists for
            the weekly distillation job that rewrites the file with a
            compressed summary.

        Args:
            content: The text to persist (e.g. a distilled summary or user
                     preference).
            append:  If True (default), add to the end of the file.
                     If False, overwrite the entire file.

        Raises:
            MemoryWriteError: If the write fails for any I/O reason.
        """
        memory_file = self.base_path / "MEMORY.md"

        try:
            mode = "a" if append else "w"
            with open(memory_file, mode, encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n## {timestamp}\n{content}\n")
            logger.debug(f"Written to MEMORY.md: {content[:50]}...")
        except Exception as e:
            # WHY re-raise as custom exception: Callers should not need to
            # catch bare `OSError` / `PermissionError` -- a domain-specific
            # exception makes error handling cleaner and unit-testable.
            raise MemoryWriteError(f"Failed to write to MEMORY.md: {e}")

    def read_memory(self) -> str:
        """
        Read the entire contents of MEMORY.md.

        WHY return empty string instead of raising when file is missing:
            On first run, MEMORY.md does not exist yet.  Returning "" lets
            the retriever treat "no curated memories" as a normal case
            rather than an error, simplifying upstream logic.

        Returns:
            The full text of MEMORY.md, or "" if the file does not exist.

        Raises:
            MemoryReadError: If the file exists but cannot be read (e.g.
                             permission denied).
        """
        memory_file = self.base_path / "MEMORY.md"

        if not memory_file.exists():
            return ""

        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise MemoryReadError(f"Failed to read MEMORY.md: {e}")

    # --------------------------------------------------------------------- #
    #  Daily logs (memory/YYYY-MM-DD.md)                                     #
    # --------------------------------------------------------------------- #

    def write_daily_log(self, content: str) -> None:
        """
        Write to today's daily log file (memory/YYYY-MM-DD.md).

        WHY one file per day:
            - Natural partitioning: each file stays a manageable size.
            - Easy cleanup: delete files older than N days with a simple
              glob + age check.
            - The retriever can skip irrelevant dates entirely, reducing I/O.

        WHY append mode:
            A single day may have dozens or hundreds of interactions.  Each
            call appends a timestamped entry so the full chronological record
            is preserved.

        Args:
            content: The interaction text to log (typically a user+bot pair).

        Raises:
            MemoryWriteError: If the write fails.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                # Use HH:MM:SS (no date) because the date is already in the
                # file name -- avoids redundant information.
                timestamp = datetime.now().strftime("%H:%M:%S")
                f.write(f"\n### {timestamp}\n{content}\n")
            logger.debug(f"Written to daily log: {today}")
        except Exception as e:
            raise MemoryWriteError(f"Failed to write daily log: {e}")

    def read_daily_log(self, date: Optional[str] = None) -> str:
        """
        Read the daily log for a specific date.

        WHY default to today's date:
            The most common use case is reading the current day's log
            (e.g. to see what has been discussed so far today).  Defaulting
            to `None` -> today removes boilerplate from callers.

        Args:
            date: ISO date string "YYYY-MM-DD".  Defaults to today.

        Returns:
            The full text of the log file, or "" if no log exists for that
            date.

        Raises:
            MemoryReadError: If the file exists but cannot be read.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        log_file = self.memory_dir / f"{date}.md"

        if not log_file.exists():
            return ""

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise MemoryReadError(f"Failed to read daily log: {e}")

    def get_all_daily_logs(self) -> List[str]:
        """
        Get a list of all dates that have a daily log file.

        WHY return date strings (not Path objects):
            The retriever and UI layers work with date strings.  Converting
            here keeps the boundary clean -- file-system details stay inside
            this class.

        Returns:
            A list of "YYYY-MM-DD" strings, one per existing log file.
            The list is unordered; sort it if chronological order is needed.
        """
        return [f.stem for f in self.memory_dir.glob("*.md")]
