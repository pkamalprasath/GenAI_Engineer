"""
Tests for Slack event listeners.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.slack.listeners.messages import handle_message_event
from src.slack.listeners.mentions import handle_app_mention


class TestMessageListener:
    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        event = {
            "text": "Bot message",
            "user": "U123",
            "channel": "C1234567890",
            "ts": "1234567890.123456",
            "bot_id": "B123",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_message_event(event, say, client, logger)
        say.assert_not_called()

    @pytest.mark.asyncio
    async def test_responds_to_dm(self):
        event = {
            "text": "Hello bot",
            "user": "U1234567890",
            "channel": "D1234567890",  # DM channel starts with D
            "ts": "1234567890.123456",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_message_event(event, say, client, logger)
        say.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignores_non_mention_channel_message(self):
        event = {
            "text": "Random channel message without mention",
            "user": "U1234567890",
            "channel": "C1234567890",
            "ts": "1234567890.123456",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_message_event(event, say, client, logger)
        say.assert_not_called()

    @pytest.mark.asyncio
    async def test_responds_to_mention(self):
        event = {
            "text": "Hey <@U_BOT_ID> what is up?",
            "user": "U1234567890",
            "channel": "C1234567890",
            "ts": "1234567890.123456",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_message_event(event, say, client, logger)
        say.assert_called_once()


class TestMentionListener:
    @pytest.mark.asyncio
    async def test_handles_empty_mention(self):
        event = {
            "text": "<@U_BOT_ID>",
            "user": "U1234567890",
            "channel": "C1234567890",
            "ts": "1234567890.123456",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_app_mention(event, say, client, logger)
        say.assert_called_once()
        # Check it mentions help
        call_kwargs = say.call_args[1]
        assert "help" in call_kwargs["text"].lower() or "bot-help" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_handles_mention_with_text(self):
        event = {
            "text": "<@U_BOT_ID> summarize the channel",
            "user": "U1234567890",
            "channel": "C1234567890",
            "ts": "1234567890.123456",
        }
        say = AsyncMock()
        client = AsyncMock()
        logger = MagicMock()

        await handle_app_mention(event, say, client, logger)
        say.assert_called_once()
        call_kwargs = say.call_args[1]
        assert "summarize the channel" in call_kwargs["text"]
