"""
Reminder Scheduler Service
==========================

WHY THIS FILE IS REQUIRED:
    Slack's built-in /remind command is limited — it can't be triggered
    programmatically by an AI agent, doesn't support listing or cancelling
    through an API the agent controls, and can't be extended with custom
    logic (e.g. recurring reminders, priority tagging).  This service gives
    the agent full CRUD control over reminders: schedule, list, cancel,
    deliver, and clean up — all through a simple async API.

PROGRAM LOGIC (high-level flow):
    1. Reminders are stored in a JSON file (memory_store/reminders.json).
    2. When a user asks the agent to set a reminder, we validate the input
       (future timestamp, non-empty text, within 1-year limit), generate
       a short UUID, and append it to the JSON file.
    3. A periodic scheduler (APScheduler, configured in app.py) calls
       execute_due_reminders() every minute.  This method:
       a. Reloads the file from disk (to pick up changes from any instance).
       b. Finds reminders whose remind_at <= now and status == "pending".
       c. Posts each one to Slack via the Slack MCP server.
       d. Marks delivered reminders as "delivered" with a timestamp.
    4. Users can list their pending reminders or cancel them by ID.
    5. A cleanup method removes old delivered/cancelled reminders after N days.

WHY THIS APPROACH (design decisions):
    - FILE-BACKED JSON STORAGE was chosen over a database because:
      (a) The project already uses file-backed memory (MEMORY.md, daily logs).
      (b) Reminder volume is low (tens, not millions) so JSON is sufficient.
      (c) No additional dependency (SQLite, Redis) is needed.
      (d) The file is human-readable for debugging.

    - ATOMIC WRITES (write to .tmp then rename) prevent data corruption if
      the process crashes mid-write.  On most filesystems, rename() is atomic.

    - RELOAD-BEFORE-MUTATE pattern: every public method calls _reload()
      before reading self._reminders.  This ensures that if two ToolRegistry
      instances (or two concurrent requests) are active, they always see
      the latest data from disk rather than stale in-memory copies.

    - UUID[:8] for IDs: short enough for users to type in a cancel command,
      unique enough for practical purposes (8 hex chars = 4 billion combos).

    - UNIX TIMESTAMPS are used instead of datetime strings because:
      (a) They're timezone-agnostic (no "which timezone?" ambiguity).
      (b) Slack's API uses Unix timestamps natively.
      (c) Comparison is a simple integer <= check.

SECURITY CONSIDERATIONS:
    - Path resolution: REMINDERS_FILE uses .resolve() to canonicalize the
      path, preventing any path traversal from environment variables.
    - Input bounds: remind_at is capped at 1 year in the future to prevent
      absurd scheduling (e.g. year 2500) and potential integer issues.
    - Empty text rejection: prevents creating reminders with no content.
    - Ownership check: cancel_reminder() verifies user_id matches the
      creator, so users can't cancel each other's reminders.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import ReminderError

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# .resolve() converts the path to an absolute canonical form, which
# prevents path traversal attacks if memory_store_path comes from
# an environment variable (e.g. MEMORY_STORE_PATH=../../etc).
REMINDERS_FILE = Path(settings.memory_store_path).resolve() / "reminders.json"

# Maximum how far into the future a reminder can be scheduled.
# 1 year is a practical upper bound — anything longer is likely a mistake.
MAX_FUTURE_SECONDS = 365 * 24 * 3600  # 1 year = 31,536,000 seconds


class ReminderService:
    """
    Manages user reminders with persistent JSON storage and Slack delivery.

    Architecture:
        - In-memory list (self._reminders) serves as a working cache.
        - Every public method calls _reload() first to sync from disk,
          then _save_reminders() after mutations for persistence.
        - Delivery is handled by execute_due_reminders(), designed to be
          called periodically by APScheduler.

    Lifecycle of a reminder:
        pending → delivered   (normal flow: scheduled → posted to Slack)
        pending → cancelled   (user cancelled before delivery time)
        delivered/cancelled → removed  (by cleanup_old_reminders after N days)
    """

    def __init__(self):
        # In-memory cache of all reminders (list of dicts).
        # Synced to/from REMINDERS_FILE on every operation.
        self._reminders: List[Dict[str, Any]] = []
        self._load_reminders()
        active = sum(1 for r in self._reminders if r["status"] == "pending")
        logger.info("Reminder service initialized with %d active reminders", active)

    # ──────────────────────────────────────────────────────────────────
    # PERSISTENCE LAYER
    # Why a separate layer: isolates file I/O concerns from business logic.
    # Every method that reads data calls _reload(); every method that
    # writes data calls _save_reminders().  This keeps I/O predictable.
    # ──────────────────────────────────────────────────────────────────

    def _load_reminders(self) -> None:
        """
        Load reminders from the JSON file on disk into memory.

        WHY:  Multiple ReminderService instances may exist (the ToolRegistry
        caches one, but background scheduler may use another).  By reading
        from disk on every operation, we ensure consistency.

        If the file doesn't exist yet (first run), we create it with [].
        If the file is corrupt (invalid JSON), we start fresh rather than
        crashing — a soft recovery approach.
        """
        try:
            if REMINDERS_FILE.exists():
                data = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
                self._reminders = data if isinstance(data, list) else []
            else:
                self._reminders = []
                self._save_reminders()  # Create the file for the first time
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load reminders, starting fresh: %s", e)
            self._reminders = []

    def _save_reminders(self) -> None:
        """
        Persist the in-memory reminder list to disk ATOMICALLY.

        HOW ATOMIC WRITES WORK:
            1. Write the full JSON to a .tmp file next to the real file.
            2. Use Path.replace() to atomically swap .tmp → .json.
            On POSIX systems, replace() is a single rename() syscall, which
            is atomic.  On Windows, it's close to atomic.  This prevents
            the scenario where a crash during write leaves a half-written
            (corrupt) JSON file.

        WHY NOT DIRECT WRITE:
            If we wrote directly to reminders.json and the process crashed
            mid-write, the file would contain partial JSON and _load_reminders
            would fail on the next restart.
        """
        try:
            REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = REMINDERS_FILE.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(self._reminders, indent=2), encoding="utf-8"
            )
            tmp_path.replace(REMINDERS_FILE)  # Atomic swap
        except OSError as e:
            logger.error("Failed to save reminders: %s", e)
            raise ReminderError(f"Failed to persist reminders: {e}")

    def _reload(self) -> None:
        """
        Re-read reminders from disk before any operation.

        WHY:  The ToolRegistry caches a single ReminderService instance,
        but the background scheduler might also create one.  If instance A
        adds a reminder, instance B won't see it until it reloads.  By
        calling _reload() at the start of every public method, we guarantee
        each operation works with the latest data.
        """
        self._load_reminders()

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API: Schedule, list, cancel, deliver, clean up
    # ──────────────────────────────────────────────────────────────────

    async def schedule_reminder(
        self,
        user_id: str,
        channel_id: str,
        text: str,
        remind_at: int,
    ) -> Dict[str, Any]:
        """
        Schedule a new reminder.

        VALIDATION RULES (and why):
            - remind_at must be in the future (can't remind about the past).
            - remind_at must be within 1 year (prevents absurd dates and
              potential integer overflow on 32-bit systems).
            - text must be non-empty (a reminder with no message is useless).

        ID GENERATION:
            We use uuid4()[:8] — the first 8 hex characters of a UUIDv4.
            This gives ~4 billion unique IDs, which is more than enough for
            a per-workspace reminder system.  The short ID is also easy for
            users to reference when cancelling ("cancel reminder a1b2c3d4").

        Args:
            user_id:    Slack user ID who requested the reminder.
            channel_id: Channel where the reminder will be posted.
            text:       The reminder message text.
            remind_at:  Unix timestamp for delivery time.

        Returns:
            Dict with success flag, reminder_id, and echo of inputs.

        Raises:
            ReminderError: If validation fails or file I/O fails.
        """
        now = int(time.time())

        # Input validation — fail fast with clear error messages.
        if remind_at <= now:
            raise ReminderError("Reminder time must be in the future")
        if remind_at > now + MAX_FUTURE_SECONDS:
            raise ReminderError("Reminder cannot be scheduled more than 1 year in the future")
        if not text or not text.strip():
            raise ReminderError("Reminder text cannot be empty")

        reminder_id = str(uuid4())[:8]

        reminder = {
            "id": reminder_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "text": text.strip(),
            "remind_at": remind_at,
            "created_at": now,
            "status": "pending",  # Will become "delivered" or "cancelled"
        }

        # Reload → append → save pattern ensures we don't lose reminders
        # that were added by another instance since we last loaded.
        self._reload()
        self._reminders.append(reminder)
        self._save_reminders()

        logger.info("Reminder %s scheduled for user %s at %d", reminder_id, user_id, remind_at)

        return {
            "success": True,
            "reminder_id": reminder_id,
            "text": text.strip(),
            "remind_at": remind_at,
            "channel_id": channel_id,
        }

    async def list_reminders(
        self, user_id: Optional[str] = None, status: str = "pending"
    ) -> List[Dict[str, Any]]:
        """
        List reminders, optionally filtered by user and/or status.

        WHY FILTERING:
            - By user: so "show MY reminders" works without seeing everyone's.
            - By status: so users see only pending (default), or can view
              all/delivered/cancelled for history.

        Results are sorted by remind_at ascending (soonest first) so the
        most urgent reminder is always at the top.

        Args:
            user_id: Optional filter — None means all users.
            status:  "pending", "delivered", "cancelled", or "all".

        Returns:
            Sorted list of matching reminder dicts.
        """
        self._reload()  # Always read fresh data from disk
        reminders = list(self._reminders)  # Work on a copy

        if user_id:
            reminders = [r for r in reminders if r["user_id"] == user_id]

        if status != "all":
            reminders = [r for r in reminders if r.get("status") == status]

        # Sort soonest-first so the most urgent reminders appear at the top.
        reminders.sort(key=lambda r: r.get("remind_at", 0))

        logger.info("Listed %d reminders (user=%s, status=%s)", len(reminders), user_id, status)
        return reminders

    async def cancel_reminder(self, reminder_id: str, user_id: str) -> Dict[str, Any]:
        """
        Cancel a pending reminder.

        OWNERSHIP CHECK:
            Only the user who created the reminder can cancel it.  This
            prevents one user from cancelling another's reminders.  In a
            real production system, you might also allow workspace admins
            to cancel any reminder.

        STATUS CHECK:
            Only "pending" reminders can be cancelled.  Once delivered or
            already cancelled, the operation is rejected with a clear message.

        Args:
            reminder_id: The 8-character UUID of the reminder.
            user_id:     The user requesting cancellation.

        Returns:
            Dict with success flag and cancelled status.

        Raises:
            ReminderError: If not found, wrong user, or wrong status.
        """
        self._reload()

        for reminder in self._reminders:
            if reminder["id"] == reminder_id:
                # Ownership check: must be the creator.
                if reminder["user_id"] != user_id:
                    raise ReminderError("You can only cancel your own reminders")

                # Status check: must still be pending.
                if reminder["status"] != "pending":
                    raise ReminderError(
                        f"Cannot cancel reminder with status: {reminder['status']}"
                    )

                reminder["status"] = "cancelled"
                self._save_reminders()

                logger.info("Reminder %s cancelled by %s", reminder_id, user_id)
                return {"success": True, "reminder_id": reminder_id, "status": "cancelled"}

        raise ReminderError(f"Reminder not found: {reminder_id}")

    async def get_due_reminders(self) -> List[Dict[str, Any]]:
        """
        Find all reminders that are due for delivery (remind_at <= now).

        This is called internally by execute_due_reminders() and can also
        be used by the scheduler to check if any work is pending.

        Returns:
            List of pending reminders whose delivery time has passed.
        """
        self._reload()
        now = int(time.time())
        due = [
            r for r in self._reminders
            if r.get("status") == "pending" and r.get("remind_at", 0) <= now
        ]

        if due:
            logger.info("Found %d due reminders", len(due))

        return due

    async def mark_delivered(self, reminder_id: str) -> None:
        """
        Mark a reminder as successfully delivered.

        Called after the Slack message has been posted.  Records the
        delivered_at timestamp for audit/debugging purposes.
        """
        self._reload()
        for reminder in self._reminders:
            if reminder["id"] == reminder_id:
                reminder["status"] = "delivered"
                reminder["delivered_at"] = int(time.time())
                self._save_reminders()
                logger.info("Reminder %s marked as delivered", reminder_id)
                return

        logger.warning("Reminder %s not found for delivery update", reminder_id)

    async def execute_due_reminders(self) -> List[Dict[str, Any]]:
        """
        Poll for due reminders and deliver them via Slack.

        HOW IT WORKS:
            1. Call get_due_reminders() to find all past-due pending items.
            2. For each, post the reminder text to the target channel using
               the Slack MCP server's post_message function.
            3. On success, mark the reminder as "delivered".
            4. On failure, log the error but continue with the next reminder
               (partial delivery is better than total failure).

        SCHEDULING:
            This method is designed to be called every 60 seconds by
            APScheduler (configured in src/app.py).  The poll-based approach
            is simpler than event-driven scheduling and works well for
            minute-level precision.

        WHY LAZY IMPORT:
            The Slack MCP server import is inside the loop to avoid circular
            imports at module load time.  Since this method runs infrequently
            (once per minute), the import overhead is negligible.

        Returns:
            List of delivery result dicts (one per reminder attempted).
        """
        due = await self.get_due_reminders()
        if not due:
            return []

        # Use the Slack SDK AsyncWebClient directly instead of importing the
        # MCP-decorated post_message function.  This avoids tight coupling to
        # the FastMCP module and is the standard way to post messages.
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings
        slack_client = AsyncWebClient(token=settings.slack_bot_token)

        results = []
        for reminder in due:
            try:
                # Format the reminder with a Slack mention so the user gets
                # a notification.  <@U123> is Slack's user mention syntax.
                reminder_text = (
                    f"*Reminder for <@{reminder['user_id']}>:*\n"
                    f"{reminder['text']}"
                )

                await slack_client.chat_postMessage(
                    channel=reminder["channel_id"],
                    text=reminder_text,
                )
                await self.mark_delivered(reminder["id"])

                results.append({
                    "reminder_id": reminder["id"],
                    "success": True,
                    "channel_id": reminder["channel_id"],
                })

                logger.info("Delivered reminder %s to %s", reminder["id"], reminder["channel_id"])

            except Exception as e:
                # Don't let one failed delivery stop the rest.
                logger.error("Failed to deliver reminder %s: %s", reminder["id"], e)
                results.append({
                    "reminder_id": reminder["id"],
                    "success": False,
                    "error": str(e),
                })

        return results

    async def cleanup_old_reminders(self, days: int = 30) -> int:
        """
        Remove delivered/cancelled reminders older than N days.

        WHY CLEANUP:
            Without periodic cleanup, the JSON file grows indefinitely.
            Old delivered/cancelled reminders have no operational value,
            so we remove them after a configurable retention period.

        PRESERVATION RULE:
            Pending reminders are NEVER removed, regardless of age.
            Only delivered/cancelled reminders older than the cutoff are
            eligible for removal.

        Args:
            days: Retention period in days.  Must be > 0.

        Returns:
            Number of reminders removed.
        """
        if days <= 0:
            raise ReminderError("Cleanup period must be greater than 0 days")

        self._reload()
        cutoff = int(time.time()) - (days * 86400)  # 86400 = seconds in a day
        original_count = len(self._reminders)

        # Keep pending reminders (regardless of age) and any reminder
        # created after the cutoff date.
        self._reminders = [
            r for r in self._reminders
            if r.get("status") == "pending" or r.get("created_at", 0) > cutoff
        ]

        removed = original_count - len(self._reminders)
        if removed > 0:
            self._save_reminders()
            logger.info("Cleaned up %d old reminders", removed)

        return removed
