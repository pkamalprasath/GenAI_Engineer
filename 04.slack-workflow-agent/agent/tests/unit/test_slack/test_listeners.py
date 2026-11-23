"""
Tests for Slack event listeners.

Routing design: the message listener answers DMs only; @mentions in channels are
handled by the app_mention listener, so the bot never replies twice.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.slack.listeners.mentions import handle_app_mention
from src.slack.listeners.messages import handle_message_event

BOT = "U0BOT12345"  # real Slack IDs are uppercase letters and digits


def _event(text: str, channel: str = "C1234567890", **extra) -> dict:
    return {"text": text, "user": "U1234567890", "channel": channel,
            "ts": "1234567890.123456", **extra}


def _orchestrator(reply: str = "Agent reply"):
    orch = MagicMock()
    orch.process_message = AsyncMock(return_value=reply)
    return orch


class TestMessageListener:
    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        say = AsyncMock()
        await handle_message_event(_event("Bot message", bot_id="B123"), say, AsyncMock(), MagicMock())
        say.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_is_answered_by_agent_in_thread(self):
        say, orch = AsyncMock(), _orchestrator("Hi there")
        with patch("src.slack.listeners.messages.get_orchestrator", return_value=orch):
            await handle_message_event(_event("Hello bot", channel="D1234567890"), say, AsyncMock(), MagicMock())

        orch.process_message.assert_awaited_once()
        assert orch.process_message.await_args.kwargs["user_message"] == "Hello bot"
        say.assert_awaited_once_with(text="Hi there", thread_ts="1234567890.123456")

    @pytest.mark.asyncio
    async def test_ignores_plain_channel_message(self):
        say = AsyncMock()
        await handle_message_event(_event("Random message"), say, AsyncMock(), MagicMock())
        say.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_mention_left_to_mention_listener(self):
        say = AsyncMock()
        await handle_message_event(_event(f"Hey <@{BOT}> what is up?"), say, AsyncMock(), MagicMock())
        say.assert_not_called()  # handle_app_mention answers it instead


class TestMentionListener:
    @pytest.mark.asyncio
    async def test_empty_mention_shows_help(self):
        say, orch = AsyncMock(), _orchestrator()
        with patch("src.slack.listeners.mentions.get_orchestrator", return_value=orch):
            await handle_app_mention(_event(f"<@{BOT}>"), say, AsyncMock(), MagicMock())

        orch.process_message.assert_not_called()
        say.assert_awaited_once()
        assert "/bot-help" in say.await_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_mention_text_goes_to_agent_without_bot_id(self):
        say, orch = AsyncMock(), _orchestrator("Here is the summary")
        with patch("src.slack.listeners.mentions.get_orchestrator", return_value=orch):
            await handle_app_mention(_event(f"<@{BOT}> summarize the channel"), say, AsyncMock(), MagicMock())

        assert orch.process_message.await_args.kwargs["user_message"] == "summarize the channel"
        say.assert_awaited_once_with(text="Here is the summary", thread_ts="1234567890.123456")

    @pytest.mark.asyncio
    async def test_agent_failure_sends_apology(self):
        say, orch = AsyncMock(), _orchestrator()
        orch.process_message.side_effect = RuntimeError("API down")
        with patch("src.slack.listeners.mentions.get_orchestrator", return_value=orch):
            await handle_app_mention(_event(f"<@{BOT}> hello"), say, AsyncMock(), MagicMock())

        assert "encountered an error" in say.await_args.kwargs["text"]
