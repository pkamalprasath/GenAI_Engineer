"""Tests for NotionIntegrationService -- edge cases and guard clauses."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.exceptions import NotionIntegrationError


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def service_no_notion():
    """Service without Notion configured."""
    with patch("src.services.notion_integration.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.notion_token = None
        with patch("src.services.notion_integration.AsyncAnthropic"):
            from src.services.notion_integration import NotionIntegrationService
            svc = NotionIntegrationService()
    return svc


@pytest.fixture
def service_with_notion():
    """Service with mocked Notion client."""
    import sys
    with patch("src.services.notion_integration.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.notion_token = "secret_test"
        with patch("src.services.notion_integration.AsyncAnthropic"):
            mock_notion_mod = MagicMock()
            with patch.dict(sys.modules, {"src.mcp_servers.notion_client": mock_notion_mod}):
                from src.services.notion_integration import NotionIntegrationService
                svc = NotionIntegrationService()
                svc._notion_client = AsyncMock()
                svc._ai_client = AsyncMock()
    return svc


# ── is_available property ───────────────────────────────────────────

class TestIsAvailable:
    def test_not_available_without_token(self, service_no_notion):
        assert service_no_notion.is_available is False

    def test_available_with_token(self, service_with_notion):
        assert service_with_notion.is_available is True


# ── _require_notion guard ───────────────────────────────────────────

class TestRequireNotion:
    def test_raises_when_not_configured(self, service_no_notion):
        with pytest.raises(NotionIntegrationError, match="not configured"):
            service_no_notion._require_notion()

    def test_passes_when_configured(self, service_with_notion):
        service_with_notion._require_notion()  # should not raise


# ── create_page_from_messages edge cases ────────────────────────────

class TestCreatePageFromMessages:
    @pytest.mark.asyncio
    async def test_no_notion_raises(self, service_no_notion):
        with pytest.raises(NotionIntegrationError, match="not configured"):
            await service_no_notion.create_page_from_messages(
                [{"text": "hi"}], "parent123", "Title"
            )

    @pytest.mark.asyncio
    async def test_empty_messages_raises(self, service_with_notion):
        with pytest.raises(NotionIntegrationError, match="No messages"):
            await service_with_notion.create_page_from_messages(
                [], "parent123", "Title"
            )

    @pytest.mark.asyncio
    async def test_successful_page_creation(self, service_with_notion):
        # Mock AI formatting
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Formatted content"
        mock_response.content = [mock_block]
        service_with_notion._ai_client.messages.create = AsyncMock(return_value=mock_response)

        # Mock Notion create
        service_with_notion._notion_client.create_page = AsyncMock(
            return_value={"success": True, "url": "https://notion.so/page"}
        )

        result = await service_with_notion.create_page_from_messages(
            [{"text": "hello", "user": "U1"}], "parent123", "Test Page"
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_notion_api_failure_wraps_error(self, service_with_notion):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "content"
        mock_response.content = [mock_block]
        service_with_notion._ai_client.messages.create = AsyncMock(return_value=mock_response)
        service_with_notion._notion_client.create_page = AsyncMock(
            side_effect=RuntimeError("Notion API error")
        )

        with pytest.raises(NotionIntegrationError, match="Failed to create Notion page"):
            await service_with_notion.create_page_from_messages(
                [{"text": "test", "user": "U1"}], "parent123", "Title"
            )


# ── search_notion edge cases ───────────────────────────────────────

class TestSearchNotion:
    @pytest.mark.asyncio
    async def test_no_notion_raises(self, service_no_notion):
        with pytest.raises(NotionIntegrationError, match="not configured"):
            await service_no_notion.search_notion("query")

    @pytest.mark.asyncio
    async def test_successful_search(self, service_with_notion):
        service_with_notion._notion_client.search = AsyncMock(
            return_value=[{"id": "page1", "title": "Result"}]
        )
        results = await service_with_notion.search_notion("test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_results(self, service_with_notion):
        service_with_notion._notion_client.search = AsyncMock(return_value=[])
        results = await service_with_notion.search_notion("nothing")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_failure_wraps_error(self, service_with_notion):
        service_with_notion._notion_client.search = AsyncMock(
            side_effect=RuntimeError("Network error")
        )
        with pytest.raises(NotionIntegrationError, match="search failed"):
            await service_with_notion.search_notion("query")


# ── _format_messages_for_notion edge cases ──────────────────────────

class TestFormatMessagesForNotion:
    @pytest.mark.asyncio
    async def test_ai_failure_falls_back_to_raw(self, service_with_notion):
        service_with_notion._ai_client.messages.create = AsyncMock(
            side_effect=RuntimeError("Claude down")
        )
        msgs = [{"text": "hello", "user": "U1"}, {"text": "world", "user": "U2"}]
        result = await service_with_notion._format_messages_for_notion(msgs, "general")
        assert "**User U1**: hello" in result
        assert "**User U2**: world" in result

    @pytest.mark.asyncio
    async def test_empty_text_skipped(self, service_with_notion):
        service_with_notion._ai_client.messages.create = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        msgs = [{"text": "", "user": "U1"}, {"text": "valid", "user": "U2"}]
        result = await service_with_notion._format_messages_for_notion(msgs, "ch")
        assert "U1" not in result
        assert "U2" in result

    @pytest.mark.asyncio
    async def test_caps_at_50_messages(self, service_with_notion):
        service_with_notion._ai_client.messages.create = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        msgs = [{"text": f"msg{i}", "user": f"U{i}"} for i in range(80)]
        result = await service_with_notion._format_messages_for_notion(msgs, "ch")
        assert "msg49" in result
        assert "msg50" not in result
