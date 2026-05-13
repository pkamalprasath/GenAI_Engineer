"""
Tests for Slack slash command handlers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.slack.listeners.commands import (
    handle_help_command,
    handle_status_command,
    handle_summarize_command,
    handle_remind_command,
)


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_acknowledges_command(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890"}
        client = AsyncMock()
        logger = MagicMock()

        await handle_help_command(ack, command, client, logger)
        ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_posts_help_message(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890"}
        client = AsyncMock()
        logger = MagicMock()

        await handle_help_command(ack, command, client, logger)
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert (
            "bot-help" in call_kwargs["text"].lower() or "commands" in call_kwargs["text"].lower()
        )


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_acknowledges_command(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890"}
        client = AsyncMock()
        logger = MagicMock()

        await handle_status_command(ack, command, client, logger)
        ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_posts_status_message(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890"}
        client = AsyncMock()
        logger = MagicMock()

        await handle_status_command(ack, command, client, logger)
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert "status" in call_kwargs["text"].lower() or "healthy" in call_kwargs["text"].lower()


class TestSummarizeCommand:
    @pytest.mark.asyncio
    async def test_acknowledges_command(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890", "text": "#general 24h"}
        client = AsyncMock()
        context = MagicMock()
        logger = MagicMock()

        await handle_summarize_command(ack, command, client, context, logger)
        ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_posts_summarize_response(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890", "text": "#general 24h"}
        client = AsyncMock()
        context = MagicMock()
        logger = MagicMock()

        await handle_summarize_command(ack, command, client, context, logger)
        client.chat_postMessage.assert_called_once()


class TestRemindCommand:
    @pytest.mark.asyncio
    async def test_acknowledges_command(self):
        ack = AsyncMock()
        command = {
            "user_id": "U123",
            "channel_id": "C1234567890",
            "text": "Send email in 5 minutes",
        }
        client = AsyncMock()
        logger = MagicMock()

        await handle_remind_command(ack, command, client, logger)
        ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_posts_remind_response(self):
        ack = AsyncMock()
        command = {"user_id": "U123", "channel_id": "C1234567890", "text": "Review PR in 1 hour"}
        client = AsyncMock()
        logger = MagicMock()

        await handle_remind_command(ack, command, client, logger)
        client.chat_postMessage.assert_called_once()
