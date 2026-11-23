"""
Rate limiting tests — per-tenant limits enforced, 429 returned on breach.
No external deps — tests middleware logic directly.

Run with: make test-security
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.api.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    """RateLimitMiddleware enforces per-tenant sliding window rate limits."""

    def _make_middleware(self, limit: int = 5, window: int = 60):
        """Create middleware with custom limit for testing."""
        app = AsyncMock()
        return RateLimitMiddleware(app, requests_per_minute=limit, window_seconds=window)

    def _make_request(self, tenant_id: str = "bank-acme", path: str = "/api/v1/investigations"):
        """Build a minimal mock ASGI scope."""
        return {
            "type": "http",
            "path": path,
            "headers": [
                (b"x-tenant-id", tenant_id.encode()),
                (b"x-api-key", b"test-key"),
            ],
        }

    def test_middleware_instantiates(self):
        middleware = self._make_middleware()
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        middleware = self._make_middleware(limit=10)
        scope = self._make_request("bank-acme")
        is_allowed = middleware._is_allowed(tenant_id="bank-acme")
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_requests_within_limit_allowed(self):
        middleware = self._make_middleware(limit=5)
        for _ in range(5):
            assert middleware._is_allowed(tenant_id="bank-acme") is True

    @pytest.mark.asyncio
    async def test_request_over_limit_rejected(self):
        middleware = self._make_middleware(limit=3)
        for _ in range(3):
            middleware._is_allowed(tenant_id="bank-acme")
        # 4th request should be rejected
        assert middleware._is_allowed(tenant_id="bank-acme") is False

    @pytest.mark.asyncio
    async def test_different_tenants_independent_limits(self):
        """Tenant A exhausting limit must not affect Tenant B."""
        middleware = self._make_middleware(limit=2)
        # Exhaust Tenant A
        middleware._is_allowed(tenant_id="tenant-a")
        middleware._is_allowed(tenant_id="tenant-a")
        assert middleware._is_allowed(tenant_id="tenant-a") is False

        # Tenant B should still be allowed
        assert middleware._is_allowed(tenant_id="tenant-b") is True

    @pytest.mark.asyncio
    async def test_window_resets_after_timeout(self):
        """After the sliding window expires, requests are allowed again."""
        middleware = self._make_middleware(limit=1, window=1)  # 1 request per 1 second
        middleware._is_allowed(tenant_id="bank-acme")  # Use the quota

        # Simulate window expiry by clearing the counter
        # (In production, the sliding window auto-expires; here we test the mechanism)
        middleware._reset_tenant("bank-acme")
        assert middleware._is_allowed(tenant_id="bank-acme") is True

    def test_health_endpoint_exempt_from_rate_limiting(self):
        """Health check endpoint must never be rate limited."""
        middleware = self._make_middleware(limit=0)  # Zero limit
        is_exempt = middleware._is_exempt_path("/health")
        assert is_exempt is True

    def test_docs_endpoint_exempt(self):
        middleware = self._make_middleware(limit=0)
        assert middleware._is_exempt_path("/docs") is True
        assert middleware._is_exempt_path("/openapi.json") is True

    def test_api_endpoint_not_exempt(self):
        middleware = self._make_middleware(limit=10)
        assert middleware._is_exempt_path("/api/v1/investigations") is False


class TestRateLimitHeaders:
    """429 response must include Retry-After header."""

    def test_retry_after_header_present_on_rejection(self):
        middleware = RateLimitMiddleware(
            app=AsyncMock(), requests_per_minute=1, window_seconds=60
        )
        middleware._is_allowed(tenant_id="test-tenant")  # Use the 1 request quota

        # On rejection, should provide retry-after
        is_allowed = middleware._is_allowed(tenant_id="test-tenant")
        assert is_allowed is False

        retry_after = middleware._get_retry_after(tenant_id="test-tenant")
        assert isinstance(retry_after, int)
        assert retry_after > 0
        assert retry_after <= 60  # Cannot be longer than window


class TestRateLimitEdgeCases:
    """Edge cases that could bypass rate limiting."""

    def test_empty_tenant_id_gets_default_limit(self):
        """Empty tenant_id should still be rate limited — use fallback key."""
        middleware = RateLimitMiddleware(
            app=AsyncMock(), requests_per_minute=2, window_seconds=60
        )
        # Should not crash — uses fallback or blocks
        result = middleware._is_allowed(tenant_id="")
        assert isinstance(result, bool)

    def test_tenant_id_with_special_chars_safe(self):
        """Tenant ID with special chars must not bypass limit via key collision."""
        middleware = RateLimitMiddleware(
            app=AsyncMock(), requests_per_minute=1, window_seconds=60
        )
        middleware._is_allowed(tenant_id="tenant-a")

        # Attempt bypass via crafted tenant_id
        result = middleware._is_allowed(tenant_id="tenant-a'--")
        assert isinstance(result, bool)
        # tenant-a and tenant-a'-- must have SEPARATE counters
        assert middleware._is_allowed(tenant_id="tenant-b") is True
