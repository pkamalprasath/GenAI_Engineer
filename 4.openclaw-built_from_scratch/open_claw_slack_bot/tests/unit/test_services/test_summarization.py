"""Tests for SummarizationService -- edge cases and formatting."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def service():
    """Create SummarizationService with mocked Anthropic client."""
    with patch("src.services.summarization.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        with patch("src.services.summarization.AsyncAnthropic"):
            from src.services.summarization import SummarizationService
            svc = SummarizationService()
            svc.client = AsyncMock()
    return svc


# ── _format_messages edge cases ─────────────────────────────────────

class TestFormatMessages:
    def test_basic_formatting(self, service):
        msgs = [{"user": "U1", "text": "hello"}]
        result = service._format_messages(msgs)
        assert "**User U1**: hello" in result

    def test_empty_text_skipped(self, service):
        msgs = [{"user": "U1", "text": ""}, {"user": "U2", "text": "valid"}]
        result = service._format_messages(msgs)
        assert "U1" not in result
        assert "U2" in result

    def test_missing_user_defaults_to_unknown(self, service):
        msgs = [{"text": "orphan"}]
        result = service._format_messages(msgs)
        assert "**User Unknown**: orphan" in result

    def test_missing_text_treated_as_empty(self, service):
        msgs = [{"user": "U1"}]
        result = service._format_messages(msgs)
        assert result == ""

    def test_caps_at_50_messages(self, service):
        msgs = [{"user": f"U{i}", "text": f"msg{i}"} for i in range(80)]
        result = service._format_messages(msgs)
        assert "msg49" in result
        assert "msg50" not in result

    def test_empty_list(self, service):
        assert service._format_messages([]) == ""

    def test_messages_joined_with_double_newline(self, service):
        msgs = [{"user": "U1", "text": "a"}, {"user": "U2", "text": "b"}]
        result = service._format_messages(msgs)
        assert "\n\n" in result


# ── summarize_messages edge cases ───────────────────────────────────

class TestSummarizeMessages:
    @pytest.mark.asyncio
    async def test_successful_summarization(self, service):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Summary: The team discussed deployment."
        mock_response.content = [mock_block]
        service.client.messages.create = AsyncMock(return_value=mock_response)

        result = await service.summarize_messages(
            [{"user": "U1", "text": "Let's deploy"}], "engineering"
        )
        assert "deployment" in result

    @pytest.mark.asyncio
    async def test_api_failure_returns_fallback(self, service):
        service.client.messages.create = AsyncMock(
            side_effect=RuntimeError("API timeout")
        )
        result = await service.summarize_messages(
            [{"user": "U1", "text": "hello"}], "general"
        )
        assert result == "Failed to generate summary."

    @pytest.mark.asyncio
    async def test_empty_messages_still_calls_api(self, service):
        """Even with empty messages, the service tries (handles gracefully)."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "No messages to summarize."
        mock_response.content = [mock_block]
        service.client.messages.create = AsyncMock(return_value=mock_response)

        result = await service.summarize_messages([], "general")
        assert "No messages" in result

    @pytest.mark.asyncio
    async def test_channel_name_in_prompt(self, service):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Summary"
        mock_response.content = [mock_block]
        service.client.messages.create = AsyncMock(return_value=mock_response)

        await service.summarize_messages(
            [{"user": "U1", "text": "test"}], "my-channel"
        )
        # Verify the prompt contained the channel name
        call_args = service.client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "#my-channel" in prompt

    @pytest.mark.asyncio
    async def test_various_exception_types_handled(self, service):
        """All exception types return fallback string."""
        for exc in [ConnectionError("net"), TimeoutError("slow"), ValueError("bad")]:
            service.client.messages.create = AsyncMock(side_effect=exc)
            result = await service.summarize_messages(
                [{"user": "U1", "text": "x"}], "ch"
            )
            assert result == "Failed to generate summary."
