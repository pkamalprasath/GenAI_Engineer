"""Tests for ReminderService -- edge cases for scheduling, cancellation, cleanup."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.utils.exceptions import ReminderError


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_reminders(tmp_path):
    """Patch REMINDERS_FILE to a temp dir and return the path."""
    reminders_file = tmp_path / "reminders.json"
    with patch("src.services.reminder.REMINDERS_FILE", reminders_file):
        yield reminders_file


@pytest.fixture
def service(tmp_reminders):
    """Create ReminderService with temp storage."""
    from src.services.reminder import ReminderService
    return ReminderService()


# ── schedule_reminder edge cases ─────────────────────────────────────

class TestScheduleReminder:
    @pytest.mark.asyncio
    async def test_schedule_valid_reminder(self, service):
        future = int(time.time()) + 3600
        result = await service.schedule_reminder("U1", "C1", "Test", future)
        assert result["success"] is True
        assert len(result["reminder_id"]) == 8
        assert result["text"] == "Test"

    @pytest.mark.asyncio
    async def test_past_time_rejected(self, service):
        past = int(time.time()) - 100
        with pytest.raises(ReminderError, match="must be in the future"):
            await service.schedule_reminder("U1", "C1", "Too late", past)

    @pytest.mark.asyncio
    async def test_now_rejected(self, service):
        now = int(time.time())
        with pytest.raises(ReminderError, match="must be in the future"):
            await service.schedule_reminder("U1", "C1", "Now", now)

    @pytest.mark.asyncio
    async def test_too_far_future_rejected(self, service):
        far_future = int(time.time()) + (366 * 24 * 3600)
        with pytest.raises(ReminderError, match="more than 1 year"):
            await service.schedule_reminder("U1", "C1", "Way later", far_future)

    @pytest.mark.asyncio
    async def test_empty_text_rejected(self, service):
        future = int(time.time()) + 3600
        with pytest.raises(ReminderError, match="cannot be empty"):
            await service.schedule_reminder("U1", "C1", "", future)

    @pytest.mark.asyncio
    async def test_whitespace_only_text_rejected(self, service):
        future = int(time.time()) + 3600
        with pytest.raises(ReminderError, match="cannot be empty"):
            await service.schedule_reminder("U1", "C1", "   \n  ", future)

    @pytest.mark.asyncio
    async def test_text_is_stripped(self, service):
        future = int(time.time()) + 3600
        result = await service.schedule_reminder("U1", "C1", "  hello  ", future)
        assert result["text"] == "hello"

    @pytest.mark.asyncio
    async def test_multiple_reminders_persisted(self, service, tmp_reminders):
        future = int(time.time()) + 3600
        await service.schedule_reminder("U1", "C1", "First", future)
        await service.schedule_reminder("U2", "C2", "Second", future + 100)
        data = json.loads(tmp_reminders.read_text(encoding="utf-8"))
        assert len(data) == 2


# ── list_reminders edge cases ───────────────────────────────────────

class TestListReminders:
    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        result = await service.list_reminders()
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_by_user(self, service):
        future = int(time.time()) + 3600
        await service.schedule_reminder("U1", "C1", "For U1", future)
        await service.schedule_reminder("U2", "C1", "For U2", future)
        result = await service.list_reminders(user_id="U1")
        assert len(result) == 1
        assert result[0]["user_id"] == "U1"

    @pytest.mark.asyncio
    async def test_filter_by_status(self, service):
        future = int(time.time()) + 3600
        r = await service.schedule_reminder("U1", "C1", "Cancel me", future)
        await service.cancel_reminder(r["reminder_id"], "U1")
        pending = await service.list_reminders(status="pending")
        cancelled = await service.list_reminders(status="cancelled")
        assert len(pending) == 0
        assert len(cancelled) == 1

    @pytest.mark.asyncio
    async def test_all_status_returns_everything(self, service):
        future = int(time.time()) + 3600
        await service.schedule_reminder("U1", "C1", "Keep", future)
        r = await service.schedule_reminder("U1", "C1", "Cancel", future)
        await service.cancel_reminder(r["reminder_id"], "U1")
        result = await service.list_reminders(status="all")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_sorted_by_remind_at(self, service):
        base = int(time.time()) + 3600
        await service.schedule_reminder("U1", "C1", "Later", base + 200)
        await service.schedule_reminder("U1", "C1", "Sooner", base + 100)
        result = await service.list_reminders(user_id="U1")
        assert result[0]["text"] == "Sooner"
        assert result[1]["text"] == "Later"


# ── cancel_reminder edge cases ──────────────────────────────────────

class TestCancelReminder:
    @pytest.mark.asyncio
    async def test_cancel_own_reminder(self, service):
        future = int(time.time()) + 3600
        r = await service.schedule_reminder("U1", "C1", "Cancel me", future)
        result = await service.cancel_reminder(r["reminder_id"], "U1")
        assert result["success"] is True
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_other_users_reminder_rejected(self, service):
        future = int(time.time()) + 3600
        r = await service.schedule_reminder("U1", "C1", "Mine", future)
        with pytest.raises(ReminderError, match="your own reminders"):
            await service.cancel_reminder(r["reminder_id"], "U2")

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_reminder(self, service):
        with pytest.raises(ReminderError, match="not found"):
            await service.cancel_reminder("deadbeef", "U1")

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled(self, service):
        future = int(time.time()) + 3600
        r = await service.schedule_reminder("U1", "C1", "X", future)
        await service.cancel_reminder(r["reminder_id"], "U1")
        with pytest.raises(ReminderError, match="Cannot cancel"):
            await service.cancel_reminder(r["reminder_id"], "U1")

    @pytest.mark.asyncio
    async def test_cancel_delivered_rejected(self, service):
        future = int(time.time()) + 3600
        r = await service.schedule_reminder("U1", "C1", "X", future)
        await service.mark_delivered(r["reminder_id"])
        with pytest.raises(ReminderError, match="Cannot cancel"):
            await service.cancel_reminder(r["reminder_id"], "U1")


# ── get_due_reminders ───────────────────────────────────────────────

class TestGetDueReminders:
    @pytest.mark.asyncio
    async def test_no_due_reminders(self, service):
        future = int(time.time()) + 3600
        await service.schedule_reminder("U1", "C1", "Not yet", future)
        due = await service.get_due_reminders()
        assert due == []

    @pytest.mark.asyncio
    async def test_past_reminder_is_due(self, service, tmp_reminders):
        # Manually insert a reminder in the past
        past_reminder = {
            "id": "abcd1234",
            "user_id": "U1",
            "channel_id": "C1",
            "text": "Overdue",
            "remind_at": int(time.time()) - 60,
            "created_at": int(time.time()) - 120,
            "status": "pending",
        }
        tmp_reminders.write_text(json.dumps([past_reminder]), encoding="utf-8")
        service._reload()
        due = await service.get_due_reminders()
        assert len(due) == 1
        assert due[0]["id"] == "abcd1234"

    @pytest.mark.asyncio
    async def test_delivered_reminders_not_due(self, service, tmp_reminders):
        past_reminder = {
            "id": "abcd1234",
            "user_id": "U1",
            "channel_id": "C1",
            "text": "Already done",
            "remind_at": int(time.time()) - 60,
            "created_at": int(time.time()) - 120,
            "status": "delivered",
        }
        tmp_reminders.write_text(json.dumps([past_reminder]), encoding="utf-8")
        service._reload()
        due = await service.get_due_reminders()
        assert due == []


# ── cleanup_old_reminders ───────────────────────────────────────────

class TestCleanupOldReminders:
    @pytest.mark.asyncio
    async def test_cleanup_zero_days_rejected(self, service):
        with pytest.raises(ReminderError, match="greater than 0"):
            await service.cleanup_old_reminders(days=0)

    @pytest.mark.asyncio
    async def test_cleanup_negative_days_rejected(self, service):
        with pytest.raises(ReminderError, match="greater than 0"):
            await service.cleanup_old_reminders(days=-5)

    @pytest.mark.asyncio
    async def test_pending_never_cleaned(self, service, tmp_reminders):
        old_pending = {
            "id": "old00001",
            "user_id": "U1",
            "channel_id": "C1",
            "text": "Old but pending",
            "remind_at": int(time.time()) + 3600,
            "created_at": int(time.time()) - (60 * 86400),  # 60 days ago
            "status": "pending",
        }
        tmp_reminders.write_text(json.dumps([old_pending]), encoding="utf-8")
        service._reload()
        removed = await service.cleanup_old_reminders(days=30)
        assert removed == 0

    @pytest.mark.asyncio
    async def test_old_delivered_cleaned(self, service, tmp_reminders):
        old_delivered = {
            "id": "old00002",
            "user_id": "U1",
            "channel_id": "C1",
            "text": "Old and done",
            "remind_at": int(time.time()) - (40 * 86400),
            "created_at": int(time.time()) - (40 * 86400),
            "status": "delivered",
        }
        tmp_reminders.write_text(json.dumps([old_delivered]), encoding="utf-8")
        service._reload()
        removed = await service.cleanup_old_reminders(days=30)
        assert removed == 1

    @pytest.mark.asyncio
    async def test_recent_delivered_kept(self, service, tmp_reminders):
        recent_delivered = {
            "id": "rec00001",
            "user_id": "U1",
            "channel_id": "C1",
            "text": "Recent delivered",
            "remind_at": int(time.time()) - 3600,
            "created_at": int(time.time()) - 3600,
            "status": "delivered",
        }
        tmp_reminders.write_text(json.dumps([recent_delivered]), encoding="utf-8")
        service._reload()
        removed = await service.cleanup_old_reminders(days=30)
        assert removed == 0


# ── Persistence edge cases ──────────────────────────────────────────

class TestPersistence:
    @pytest.mark.asyncio
    async def test_corrupt_json_recovers(self, tmp_reminders):
        tmp_reminders.write_text("NOT VALID JSON!!!", encoding="utf-8")
        from src.services.reminder import ReminderService
        svc = ReminderService()
        result = await svc.list_reminders()
        assert result == []

    @pytest.mark.asyncio
    async def test_file_missing_creates_empty(self, tmp_reminders):
        assert not tmp_reminders.exists() or True  # may or may not exist
        from src.services.reminder import ReminderService
        svc = ReminderService()
        result = await svc.list_reminders()
        assert result == []

    @pytest.mark.asyncio
    async def test_non_list_json_recovers(self, tmp_reminders):
        tmp_reminders.write_text('{"not": "a list"}', encoding="utf-8")
        from src.services.reminder import ReminderService
        svc = ReminderService()
        result = await svc.list_reminders()
        assert result == []
