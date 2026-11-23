"""
Tests for security utilities.
"""

import time
import pytest
from datetime import datetime, timedelta

from src.utils.security import (
    verify_slack_signature,
    mask_token,
    validate_token_format,
    check_token_expiry,
    RateLimiter,
    generate_secure_id,
    generate_api_key,
    sanitize_for_logging,
    get_security_headers,
    validate_secret_strength,
)
from src.utils.exceptions import SecurityValidationError


class TestVerifySlackSignature:
    def test_valid_signature(self):
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        body = "test_body"

        import hmac
        import hashlib

        sig_basestring = f"v0:{timestamp}:{body}"
        expected_sig = (
            "v0="
            + hmac.new(
                key=signing_secret.encode(), msg=sig_basestring.encode(), digestmod=hashlib.sha256
            ).hexdigest()
        )

        result = verify_slack_signature(signing_secret, timestamp, body, expected_sig)
        assert result is True

    def test_invalid_signature(self):
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        result = verify_slack_signature(signing_secret, timestamp, "body", "v0=invalid")
        assert result is False

    def test_old_timestamp(self):
        signing_secret = "test_secret"
        old_ts = str(int(time.time()) - 400)
        with pytest.raises(SecurityValidationError):
            verify_slack_signature(signing_secret, old_ts, "body", "v0=sig")

    def test_invalid_timestamp(self):
        with pytest.raises(SecurityValidationError):
            verify_slack_signature("secret", "not-a-number", "body", "v0=sig")


class TestMaskToken:
    def test_normal_token(self):
        assert mask_token("xoxb-1234567890-abcdefghij") == "xoxb" + "*" * 22

    def test_short_token(self):
        assert mask_token("abc") == "***"

    def test_custom_visible_chars(self):
        assert mask_token("xoxb-12345", visible_chars=6) == "xoxb-1" + "*" * 4


class TestValidateTokenFormat:
    def test_valid_bot_token(self):
        assert validate_token_format("xoxb-1234567890", "bot") is True

    def test_valid_app_token(self):
        assert validate_token_format("xapp-1234567890", "app") is True

    def test_invalid_bot_token(self):
        assert validate_token_format("invalid-token", "bot") is False

    def test_invalid_type(self):
        assert validate_token_format("xoxb-1234567890", "unknown") is False

    def test_short_token(self):
        assert validate_token_format("xoxb-", "bot") is False


class TestCheckTokenExpiry:
    def test_fresh_token(self):
        created = datetime.now()
        should_rotate, days = check_token_expiry(created, rotation_days=7)
        assert should_rotate is False
        assert days > 0

    def test_expired_token(self):
        created = datetime.now() - timedelta(days=10)
        should_rotate, days = check_token_expiry(created, rotation_days=7)
        assert should_rotate is True
        assert days < 0


class TestRateLimiter:
    def test_allows_first_request(self):
        limiter = RateLimiter()
        allowed, retry_after = limiter.is_allowed("user1", max_requests=5)
        assert allowed is True
        assert retry_after is None

    def test_allows_within_limit(self):
        limiter = RateLimiter()
        for _ in range(5):
            allowed, _ = limiter.is_allowed("user1", max_requests=5)
        assert allowed is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter()
        for _ in range(5):
            limiter.is_allowed("user1", max_requests=5)
        allowed, retry_after = limiter.is_allowed("user1", max_requests=5)
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0

    def test_independent_keys(self):
        limiter = RateLimiter()
        for _ in range(5):
            limiter.is_allowed("user1", max_requests=5)
        allowed, _ = limiter.is_allowed("user2", max_requests=5)
        assert allowed is True

    def test_reset(self):
        limiter = RateLimiter()
        for _ in range(5):
            limiter.is_allowed("user1", max_requests=5)
        limiter.reset("user1")
        allowed, _ = limiter.is_allowed("user1", max_requests=5)
        assert allowed is True

    def test_clear(self):
        limiter = RateLimiter()
        limiter.is_allowed("user1", max_requests=5)
        limiter.is_allowed("user2", max_requests=5)
        limiter.clear()
        assert limiter._storage == {}


class TestGenerateSecureId:
    def test_generates_id(self):
        id1 = generate_secure_id()
        assert isinstance(id1, str)
        assert len(id1) > 0

    def test_uniqueness(self):
        id1 = generate_secure_id()
        id2 = generate_secure_id()
        assert id1 != id2


class TestGenerateApiKey:
    def test_has_prefix(self):
        key = generate_api_key()
        assert key.startswith("sbk_")

    def test_sufficient_length(self):
        key = generate_api_key()
        assert len(key) > 20


class TestSanitizeForLogging:
    def test_masks_token(self):
        data = {"token": "xoxb-secret-token", "name": "test"}
        result = sanitize_for_logging(data)
        assert result["name"] == "test"
        assert "xoxb-secret-token" not in result["token"]

    def test_masks_password(self):
        data = {"password": "my_secret_pass"}
        result = sanitize_for_logging(data)
        assert "my_secret_pass" not in result["password"]

    def test_masks_api_key(self):
        data = {"api_key": "sk-something"}
        result = sanitize_for_logging(data)
        assert "sk-something" not in result["api_key"]

    def test_preserves_non_sensitive(self):
        data = {"name": "test", "count": 42}
        result = sanitize_for_logging(data)
        assert result == data

    def test_nested_dict(self):
        data = {"config": {"secret": "hidden", "name": "test"}}
        result = sanitize_for_logging(data)
        assert result["config"]["name"] == "test"
        assert "hidden" not in str(result["config"]["secret"])


class TestGetSecurityHeaders:
    def test_returns_headers(self):
        headers = get_security_headers()
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        assert headers["X-Frame-Options"] == "DENY"


class TestValidateSecretStrength:
    def test_valid_secret(self):
        secret = "AbCdEfGhIjKlMnOpQrStUvWxYz12345678"
        is_valid, msg = validate_secret_strength(secret)
        assert is_valid is True

    def test_too_short(self):
        is_valid, msg = validate_secret_strength("short")
        assert is_valid is False
        assert "at least" in msg

    def test_no_uppercase(self):
        secret = "abcdefghijklmnopqrstuvwxyz12345678"
        is_valid, msg = validate_secret_strength(secret)
        assert is_valid is False

    def test_no_digits(self):
        secret = "abcdefghijklmnopqrstuvwxyzABCDEFGH"
        is_valid, msg = validate_secret_strength(secret)
        assert is_valid is False
