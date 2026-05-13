"""
Tests for Slack message service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from slack_sdk.errors import SlackApiError

from src.slack.services.message_service import MessageService
from src.utils.exceptions import ChannelNotFoundError


class TestMessageService:
    def setup_method(self):
        self.mock_client = AsyncMock()
        self.service = MessageService(self.mock_client)

    @pytest.mark.asyncio
    async def test_post_message(self):
        self.mock_client.chat_postMessage.return_value = {
            "ts": "1234567890.123456",
            "channel": "C1234567890",
        }
        result = await self.service.post_message("C1234567890", "Hello!")
        assert result["ts"] == "1234567890.123456"
        self.mock_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_message_in_thread(self):
        self.mock_client.chat_postMessage.return_value = {
            "ts": "1234567890.123457",
            "channel": "C1234567890",
        }
        await self.service.post_message("C1234567890", "Reply!", thread_ts="1234567890.123456")
        call_kwargs = self.mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_post_message_channel_not_found(self):
        error_response = MagicMock()
        error_response.__getitem__ = MagicMock(return_value="channel_not_found")
        self.mock_client.chat_postMessage.side_effect = SlackApiError(
            message="", response=error_response
        )
        with pytest.raises(ChannelNotFoundError):
            await self.service.post_message("C1234567890", "test")

    @pytest.mark.asyncio
    async def test_post_ephemeral_message(self):
        self.mock_client.chat_postEphemeral.return_value = {"ok": True}
        result = await self.service.post_ephemeral_message(
            "C1234567890", "U1234567890", "Secret message"
        )
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_get_messages(self):
        self.mock_client.conversations_history.return_value = {
            "messages": [
                {"text": "msg1", "user": "U123", "ts": "1234567890.123456"},
                {"text": "msg2", "user": "U456", "ts": "1234567890.123457"},
            ]
        }
        messages = await self.service.get_messages("C1234567890")
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_messages_in_timeframe(self):
        self.mock_client.conversations_history.return_value = {"messages": []}
        result = await self.service.get_messages_in_timeframe("C1234567890", hours=24)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_update_message(self):
        self.mock_client.chat_update.return_value = {
            "ts": "1234567890.123456",
            "channel": "C1234567890",
        }
        result = await self.service.update_message(
            "C1234567890", "1234567890.123456", "Updated text"
        )
        assert result["ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_delete_message(self):
        self.mock_client.chat_delete.return_value = {"ok": True}
        result = await self.service.delete_message("C1234567890", "1234567890.123456")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_schedule_message(self):
        self.mock_client.chat_scheduleMessage.return_value = {"scheduled_message_id": "Q123"}
        result = await self.service.schedule_message(
            "C1234567890", "Scheduled!", post_at=9999999999
        )
        assert "scheduled_message_id" in result

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        self.mock_client.reactions_add.return_value = {"ok": True}
        # Should not raise
        await self.service.add_reaction("C1234567890", "1234567890.123456", "thumbsup")

    @pytest.mark.asyncio
    async def test_add_reaction_failure_silent(self):
        error_response = MagicMock()
        error_response.__getitem__ = MagicMock(return_value="already_reacted")
        self.mock_client.reactions_add.side_effect = SlackApiError(
            message="", response=error_response
        )
        # Should not raise (failure is silently logged)
        await self.service.add_reaction("C1234567890", "1234567890.123456", "thumbsup")

    @pytest.mark.asyncio
    async def test_remove_reaction(self):
        self.mock_client.reactions_remove.return_value = {"ok": True}
        await self.service.remove_reaction("C1234567890", "1234567890.123456", "thumbsup")
