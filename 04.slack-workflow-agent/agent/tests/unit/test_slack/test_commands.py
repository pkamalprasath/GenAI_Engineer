"""
Tests for Slack slash command handlers.

Handlers follow the Slack Bolt signature: ack() first, then reply via say().
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.slack.listeners.commands import (
    handle_help_command,
    handle_remind_command,
    handle_status_command,
    handle_summarize_command,
)


def _said(say: AsyncMock) -> list[str]:
    return [c.kwargs["text"] for c in say.await_args_list]


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_acks_and_lists_commands(self):
        ack, say = AsyncMock(), AsyncMock()
        await handle_help_command(ack, {"user_id": "U123"}, say, MagicMock())
        ack.assert_awaited_once()
        text = _said(say)[0]
        assert "/bot-summarize" in text and "/bot-remind" in text


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_acks_and_posts_status(self):
        ack, say = AsyncMock(), AsyncMock()
        await handle_status_command(ack, {"user_id": "U123"}, say, MagicMock())
        ack.assert_awaited_once()
        say.assert_awaited_once()
        assert "status" in _said(say)[0].lower()


class TestSummarizeCommand:
    @pytest.mark.asyncio
    async def test_no_args_shows_usage(self):
        ack, say, client = AsyncMock(), AsyncMock(), AsyncMock()
        await handle_summarize_command(ack, {"user_id": "U1", "text": ""}, say, client, MagicMock())
        ack.assert_awaited_once()
        assert "Usage" in _said(say)[0]
        client.conversations_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarizes_channel_and_caps_hours(self):
        ack, say, client = AsyncMock(), AsyncMock(), AsyncMock()
        client.conversations_history.return_value = {"messages": [{"text": "a"}, {"text": "b"}]}
        client.conversations_info.return_value = {"channel": {"name": "general"}}
        service = MagicMock()
        service.summarize_messages = AsyncMock(return_value="Two things happened.")

        with patch("src.services.summarization.SummarizationService", return_value=service):
            await handle_summarize_command(
                ack, {"user_id": "U1", "text": "<#C0123456789|general> 500h"}, say, client, MagicMock()
            )

        assert client.conversations_history.await_args.kwargs["channel"] == "C0123456789"
        said = _said(say)
        assert "last 168h" in said[0]  # 500h is capped at one week
        assert "*Summary of #general*" in said[-1] and "Two things happened." in said[-1]

    @pytest.mark.asyncio
    async def test_api_failure_reports_error(self):
        ack, say, client = AsyncMock(), AsyncMock(), AsyncMock()
        client.conversations_history.side_effect = RuntimeError("not_in_channel")
        await handle_summarize_command(
            ack, {"user_id": "U1", "text": "C0123456789 24h"}, say, client, MagicMock()
        )
        assert "couldn't summarize" in _said(say)[-1]


class TestRemindCommand:
    @pytest.mark.asyncio
    async def test_schedules_reminder_with_parsed_delay(self):
        ack, say = AsyncMock(), AsyncMock()
        service = MagicMock()
        service.schedule_reminder = AsyncMock(return_value={"reminder_id": "rem-42"})
        command = {"user_id": "U123", "channel_id": "C1", "text": "Review PR in 2 hours"}

        before = int(time.time())
        with patch("src.services.reminder.ReminderService", return_value=service):
            await handle_remind_command(ack, command, say, AsyncMock(), MagicMock())

        ack.assert_awaited_once()
        kwargs = service.schedule_reminder.await_args.kwargs
        assert kwargs["text"] == "Review PR" and kwargs["user_id"] == "U123"
        assert before + 7200 <= kwargs["remind_at"] <= int(time.time()) + 7200
        assert "rem-42" in _said(say)[0] and "2 hours" in _said(say)[0]

    @pytest.mark.asyncio
    async def test_unparseable_reminder_explains_format(self):
        ack, say = AsyncMock(), AsyncMock()
        command = {"user_id": "U1", "channel_id": "C1", "text": "sometime tomorrow"}
        await handle_remind_command(ack, command, say, AsyncMock(), MagicMock())
        assert "couldn't parse" in _said(say)[0]
