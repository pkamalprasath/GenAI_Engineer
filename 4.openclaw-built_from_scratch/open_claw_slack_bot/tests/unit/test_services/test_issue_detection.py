"""Tests for IssueDetectionService -- focused on edge cases and parsing."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.issue_detection import (
    IssueDetectionService,
    _sanitize_log_value,
    VALID_SEVERITIES,
)
from src.utils.exceptions import IssueDetectionError


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def service():
    """Create service with mocked Anthropic client and no GitHub."""
    with patch("src.services.issue_detection.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.github_token = None
        with patch("src.services.issue_detection.AsyncAnthropic"):
            svc = IssueDetectionService()
    return svc


@pytest.fixture
def service_with_github():
    """Create service with mocked GitHub client."""
    with patch("src.services.issue_detection.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.github_token = "ghp_test"
        with patch("src.services.issue_detection.AsyncAnthropic"):
            # Patch the import target so GitHubMCPClient doesn't need aiohttp
            mock_gh = MagicMock()
            with patch.dict("sys.modules", {"src.mcp_servers.github_client": mock_gh}):
                svc = IssueDetectionService()
                svc._github_client = AsyncMock()
    return svc


# ── _sanitize_log_value ──────────────────────────────────────────────

class TestSanitizeLogValue:
    def test_strips_newlines(self):
        assert _sanitize_log_value("line1\nline2") == "line1\\nline2"

    def test_strips_carriage_returns(self):
        assert _sanitize_log_value("line1\rline2") == "line1\\rline2"

    def test_strips_both(self):
        assert _sanitize_log_value("a\r\nb") == "a\\r\\nb"

    def test_clean_string_unchanged(self):
        assert _sanitize_log_value("no special chars") == "no special chars"

    def test_empty_string(self):
        assert _sanitize_log_value("") == ""

    def test_only_newlines(self):
        assert _sanitize_log_value("\n\n\n") == "\\n\\n\\n"


# ── _parse_issues edge cases ────────────────────────────────────────

class TestParseIssues:
    def test_valid_json_array(self, service):
        raw = json.dumps([{"title": "Bug A", "severity": "high"}])
        result = service._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Bug A"
        assert result[0]["severity"] == "high"
        assert result[0]["description"] == ""  # setdefault
        assert result[0]["suggested_labels"] == []

    def test_json_wrapped_in_code_fence(self, service):
        raw = '```json\n[{"title": "Bug"}]\n```'
        result = service._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Bug"

    def test_single_object_wrapped_in_list(self, service):
        raw = json.dumps({"title": "Single"})
        result = service._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Single"

    def test_invalid_severity_normalized_to_medium(self, service):
        raw = json.dumps([{"title": "X", "severity": "URGENT"}])
        result = service._parse_issues(raw)
        assert result[0]["severity"] == "medium"

    def test_missing_severity_defaults_to_medium(self, service):
        raw = json.dumps([{"title": "No severity"}])
        result = service._parse_issues(raw)
        assert result[0]["severity"] == "medium"

    def test_entry_without_title_skipped(self, service):
        raw = json.dumps([{"description": "no title"}, {"title": "Has title"}])
        result = service._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Has title"

    def test_non_dict_entries_skipped(self, service):
        raw = json.dumps([42, "string", {"title": "Valid"}])
        result = service._parse_issues(raw)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self, service):
        result = service._parse_issues("not json at all")
        assert result == []

    def test_empty_array(self, service):
        result = service._parse_issues("[]")
        assert result == []

    def test_all_valid_severities_preserved(self, service):
        for sev in VALID_SEVERITIES:
            raw = json.dumps([{"title": f"Issue-{sev}", "severity": sev}])
            result = service._parse_issues(raw)
            assert result[0]["severity"] == sev


# ── _format_messages edge cases ──────────────────────────────────────

class TestFormatMessages:
    def test_basic_formatting(self, service):
        msgs = [{"user": "U1", "text": "hello", "ts": "123.456"}]
        result = service._format_messages(msgs)
        assert "[User U1 at 123.456]: hello" in result

    def test_empty_text_skipped(self, service):
        msgs = [
            {"user": "U1", "text": "", "ts": "1"},
            {"user": "U2", "text": "valid", "ts": "2"},
        ]
        result = service._format_messages(msgs)
        assert "U1" not in result
        assert "U2" in result

    def test_missing_fields_use_defaults(self, service):
        msgs = [{"text": "hello"}]
        result = service._format_messages(msgs)
        assert "[User Unknown at ]: hello" in result

    def test_caps_at_100_messages(self, service):
        msgs = [{"user": f"U{i}", "text": f"msg{i}", "ts": str(i)} for i in range(150)]
        result = service._format_messages(msgs)
        assert "msg99" in result
        assert "msg100" not in result

    def test_empty_list(self, service):
        assert service._format_messages([]) == ""


# ── detect_issues edge cases ────────────────────────────────────────

class TestDetectIssues:
    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self, service):
        result = await service.detect_issues([])
        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_raises_detection_error(self, service):
        service.client = AsyncMock()
        service.client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        msgs = [{"text": "bug", "user": "U1", "ts": "1"}]
        with pytest.raises(IssueDetectionError, match="Failed to detect issues"):
            await service.detect_issues(msgs)

    @pytest.mark.asyncio
    async def test_successful_detection(self, service):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps([{"title": "Found bug", "severity": "high"}])
        mock_response.content = [mock_block]
        service.client = AsyncMock()
        service.client.messages.create = AsyncMock(return_value=mock_response)

        msgs = [{"text": "app crashes", "user": "U1", "ts": "1"}]
        result = await service.detect_issues(msgs)
        assert len(result) == 1
        assert result[0]["title"] == "Found bug"


# ── detect_and_create_issues edge cases ─────────────────────────────

class TestDetectAndCreateIssues:
    @pytest.mark.asyncio
    async def test_no_github_raises_error(self, service):
        with pytest.raises(IssueDetectionError, match="GitHub integration not configured"):
            await service.detect_and_create_issues([], repo="owner/repo")

    @pytest.mark.asyncio
    async def test_invalid_threshold_raises_error(self, service_with_github):
        with pytest.raises(IssueDetectionError, match="Invalid threshold"):
            await service_with_github.detect_and_create_issues(
                [{"text": "x", "user": "U1", "ts": "1"}],
                repo="owner/repo",
                auto_create_threshold="urgent",
            )

    @pytest.mark.asyncio
    async def test_no_issues_detected_returns_empty(self, service_with_github):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "[]"
        mock_response.content = [mock_block]
        service_with_github.client = AsyncMock()
        service_with_github.client.messages.create = AsyncMock(return_value=mock_response)

        result = await service_with_github.detect_and_create_issues(
            [{"text": "all good", "user": "U1", "ts": "1"}],
            repo="owner/repo",
        )
        assert result["detected_issues"] == []
        assert result["created_issues"] == []

    @pytest.mark.asyncio
    async def test_severity_filtering_by_threshold(self, service_with_github):
        issues = [
            {"title": "Critical", "severity": "critical"},
            {"title": "Low", "severity": "low"},
        ]
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps(issues)
        mock_response.content = [mock_block]
        service_with_github.client = AsyncMock()
        service_with_github.client.messages.create = AsyncMock(return_value=mock_response)
        service_with_github._github_client.create_issue = AsyncMock(
            return_value={"success": True, "url": "https://github.com/test/1"}
        )

        result = await service_with_github.detect_and_create_issues(
            [{"text": "bug", "user": "U1", "ts": "1"}],
            repo="owner/repo",
            auto_create_threshold="high",
        )
        assert result["total_detected"] == 2
        # Only critical should be created (threshold=high means critical + high)
        assert len(result["created_issues"]) == 1
        assert result["created_issues"][0]["title"] == "Critical"

    @pytest.mark.asyncio
    async def test_github_create_failure_continues(self, service_with_github):
        issues = [{"title": "Bug1", "severity": "critical"}, {"title": "Bug2", "severity": "critical"}]
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps(issues)
        mock_response.content = [mock_block]
        service_with_github.client = AsyncMock()
        service_with_github.client.messages.create = AsyncMock(return_value=mock_response)
        # First call fails, second succeeds
        service_with_github._github_client.create_issue = AsyncMock(
            side_effect=[RuntimeError("GitHub down"), {"success": True}]
        )

        result = await service_with_github.detect_and_create_issues(
            [{"text": "bugs", "user": "U1", "ts": "1"}],
            repo="owner/repo",
            auto_create_threshold="critical",
        )
        assert len(result["created_issues"]) == 2
        assert result["created_issues"][0]["github_result"]["success"] is False
        assert result["created_issues"][1]["github_result"]["success"] is True
