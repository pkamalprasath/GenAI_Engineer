"""
Tests for custom exception classes.
"""

from unittest.mock import MagicMock

from src.utils.exceptions import (
    SlackBotError,
    ConfigurationError,
    TokenError,
    SlackAPIError,
    RateLimitError,
    ChannelNotFoundError,
    ToolExecutionError,
    ContextTooLargeError,
    RAGError,
    VectorStoreError,
    MCPServerError,
    InvalidInputError,
    ServiceError,
    SummarizationError,
    handle_exception,
)


class TestSlackBotError:
    def test_basic_error(self):
        err = SlackBotError("test error")
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.details == {}

    def test_error_with_details(self):
        err = SlackBotError("test error", details={"key": "value"})
        assert "key" in str(err)
        assert err.details == {"key": "value"}


class TestSlackAPIError:
    def test_with_error_code(self):
        err = SlackAPIError("API failed", error_code="channel_not_found")
        assert err.error_code == "channel_not_found"
        assert "channel_not_found" in str(err)

    def test_without_error_code(self):
        err = SlackAPIError("API failed")
        assert err.error_code is None


class TestRateLimitError:
    def test_with_retry_after(self):
        err = RateLimitError("Rate limited", retry_after=30)
        assert err.retry_after == 30
        assert err.error_code == "rate_limit_exceeded"


class TestToolExecutionError:
    def test_with_tool_name(self):
        err = ToolExecutionError("Tool failed", tool_name="get_messages")
        assert err.tool_name == "get_messages"


class TestContextTooLargeError:
    def test_with_token_counts(self):
        err = ContextTooLargeError("Too large", current_tokens=5000, max_tokens=4096)
        assert err.current_tokens == 5000
        assert err.max_tokens == 4096


class TestMCPServerError:
    def test_with_server_name(self):
        err = MCPServerError("MCP failed", server_name="slack")
        assert err.server_name == "slack"


class TestExceptionHierarchy:
    def test_configuration_error_is_slack_bot_error(self):
        assert issubclass(ConfigurationError, SlackBotError)

    def test_token_error_is_configuration_error(self):
        assert issubclass(TokenError, ConfigurationError)

    def test_channel_not_found_is_slack_api_error(self):
        assert issubclass(ChannelNotFoundError, SlackAPIError)

    def test_invalid_input_is_slack_bot_error(self):
        assert issubclass(InvalidInputError, SlackBotError)

    def test_vector_store_error_is_rag_error(self):
        assert issubclass(VectorStoreError, RAGError)

    def test_summarization_error_is_service_error(self):
        assert issubclass(SummarizationError, ServiceError)


class TestHandleException:
    def test_handles_slack_bot_error(self):
        mock_logger = MagicMock()
        err = SlackBotError("User-friendly message")
        result = handle_exception(err, mock_logger)
        assert result == "User-friendly message"
        mock_logger.exception.assert_called_once()

    def test_handles_generic_exception(self):
        mock_logger = MagicMock()
        err = ValueError("Internal error")
        result = handle_exception(err, mock_logger, "Something went wrong")
        assert result == "Something went wrong"

    def test_default_user_message(self):
        mock_logger = MagicMock()
        err = RuntimeError("crash")
        result = handle_exception(err, mock_logger)
        assert result == "An error occurred"
