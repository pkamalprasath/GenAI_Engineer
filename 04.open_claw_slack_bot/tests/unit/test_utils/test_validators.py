"""
Tests for validation utilities.
"""

import pytest
import time
from src.utils.validators import (
    validate_channel_id,
    validate_user_id,
    validate_message_ts,
    validate_text_length,
    sanitize_text,
    detect_injection_attempt,
    validate_positive_integer,
    validate_hours_param,
    validate_limit_param,
    validate_timestamp,
    validate_url,
    validate_batch,
)
from src.utils.exceptions import InvalidInputError, SecurityValidationError


class TestValidateChannelId:
    def test_valid_public_channel(self):
        assert validate_channel_id("C1234567890") == "C1234567890"

    def test_valid_private_channel(self):
        assert validate_channel_id("G1234567890") == "G1234567890"

    def test_invalid_empty(self):
        with pytest.raises(InvalidInputError):
            validate_channel_id("")

    def test_invalid_format(self):
        with pytest.raises(InvalidInputError):
            validate_channel_id("invalid")

    def test_invalid_prefix(self):
        with pytest.raises(InvalidInputError):
            validate_channel_id("U1234567890")

    def test_too_short(self):
        with pytest.raises(InvalidInputError):
            validate_channel_id("C123")


class TestValidateUserId:
    def test_valid_user_id(self):
        assert validate_user_id("U1234567890") == "U1234567890"

    def test_invalid_empty(self):
        with pytest.raises(InvalidInputError):
            validate_user_id("")

    def test_invalid_prefix(self):
        with pytest.raises(InvalidInputError):
            validate_user_id("C1234567890")


class TestValidateMessageTs:
    def test_valid_timestamp(self):
        assert validate_message_ts("1234567890.123456") == "1234567890.123456"

    def test_invalid_empty(self):
        with pytest.raises(InvalidInputError):
            validate_message_ts("")

    def test_invalid_format(self):
        with pytest.raises(InvalidInputError):
            validate_message_ts("12345")


class TestValidateTextLength:
    def test_valid_short_text(self):
        assert validate_text_length("Hello", max_length=10) == "Hello"

    def test_text_at_max_length(self):
        text = "x" * 4000
        assert validate_text_length(text) == text

    def test_text_exceeds_max(self):
        with pytest.raises(InvalidInputError):
            validate_text_length("x" * 5000, max_length=4000)

    def test_empty_text(self):
        with pytest.raises(InvalidInputError):
            validate_text_length("")


class TestSanitizeText:
    def test_removes_script_tags(self):
        dirty = "<script>alert('xss')</script>"
        clean = sanitize_text(dirty)
        assert "<script>" not in clean
        assert "alert" in clean

    def test_removes_control_characters(self):
        dirty = "hello\x00world\x08test"
        clean = sanitize_text(dirty)
        assert "\x00" not in clean
        assert "\x08" not in clean

    def test_normalizes_whitespace(self):
        dirty = "hello    world"
        clean = sanitize_text(dirty)
        assert clean == "hello world"

    def test_empty_string(self):
        assert sanitize_text("") == ""

    def test_preserves_normal_text(self):
        text = "Hello, world!"
        assert sanitize_text(text) == "Hello, world!"


class TestDetectInjectionAttempt:
    def test_detects_script_tag(self):
        assert detect_injection_attempt("<script>alert(1)</script>") is True

    def test_detects_sql_injection(self):
        assert detect_injection_attempt("SELECT * FROM users") is True
        assert detect_injection_attempt("DROP TABLE users") is True

    def test_detects_command_injection(self):
        assert detect_injection_attempt("ls && rm -rf /") is True

    def test_detects_path_traversal(self):
        assert detect_injection_attempt("../../etc/passwd") is True

    def test_normal_text_passes(self):
        assert detect_injection_attempt("Hello, how are you?") is False

    def test_detects_javascript_protocol(self):
        assert detect_injection_attempt("javascript:alert(1)") is True


class TestValidatePositiveInteger:
    def test_valid_value(self):
        assert validate_positive_integer(5) == 5

    def test_value_at_minimum(self):
        assert validate_positive_integer(1) == 1

    def test_value_below_minimum(self):
        with pytest.raises(InvalidInputError):
            validate_positive_integer(0)

    def test_value_above_maximum(self):
        with pytest.raises(InvalidInputError):
            validate_positive_integer(100, max_value=50)

    def test_not_integer(self):
        with pytest.raises(InvalidInputError):
            validate_positive_integer("5")


class TestValidateHoursParam:
    def test_valid_hours(self):
        assert validate_hours_param(24) == 24

    def test_max_hours(self):
        assert validate_hours_param(168) == 168

    def test_exceeds_max_hours(self):
        with pytest.raises(InvalidInputError):
            validate_hours_param(169)

    def test_zero_hours(self):
        with pytest.raises(InvalidInputError):
            validate_hours_param(0)


class TestValidateLimitParam:
    def test_valid_limit(self):
        assert validate_limit_param(100) == 100

    def test_exceeds_max_limit(self):
        with pytest.raises(InvalidInputError):
            validate_limit_param(1001)


class TestValidateTimestamp:
    def test_valid_recent_timestamp(self):
        ts = time.time()
        result = validate_timestamp(ts)
        assert isinstance(result, float)

    def test_old_timestamp(self):
        with pytest.raises(SecurityValidationError):
            validate_timestamp(1000000000.0)

    def test_future_timestamp(self):
        future_ts = time.time() + 120
        with pytest.raises(SecurityValidationError):
            validate_timestamp(future_ts)


class TestValidateUrl:
    def test_valid_https_url(self):
        url = "https://example.com/path"
        assert validate_url(url) == url

    def test_valid_http_url(self):
        url = "http://example.com"
        assert validate_url(url) == url

    def test_empty_url(self):
        with pytest.raises(InvalidInputError):
            validate_url("")

    def test_invalid_url(self):
        with pytest.raises(InvalidInputError):
            validate_url("not-a-url")

    def test_domain_whitelist(self):
        url = "https://allowed.com/path"
        assert validate_url(url, allowed_domains=["allowed.com"]) == url

    def test_domain_not_in_whitelist(self):
        with pytest.raises(SecurityValidationError):
            validate_url("https://blocked.com", allowed_domains=["allowed.com"])


class TestValidateBatch:
    def test_valid_batch(self):
        items = ["C1234567890", "G1234567890"]
        result = validate_batch(items, validate_channel_id)
        assert len(result) == 2

    def test_empty_batch(self):
        with pytest.raises(InvalidInputError):
            validate_batch([], validate_channel_id)

    def test_batch_exceeds_max(self):
        items = ["C1234567890"] * 101
        with pytest.raises(InvalidInputError):
            validate_batch(items, validate_channel_id)

    def test_batch_with_invalid_item(self):
        items = ["C1234567890", "invalid"]
        with pytest.raises(InvalidInputError):
            validate_batch(items, validate_channel_id)
