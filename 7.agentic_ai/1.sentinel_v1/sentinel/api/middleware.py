"""
FastAPI middleware — authentication, rate limiting, request ID injection.
All parameters from configs/security.yaml — nothing hardcoded.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from configs.settings import security_cfg, settings

_rate_cfg = security_cfg.get("rate_limiting", {})
_DEFAULT_RPM = settings.rate_limit_per_minute
_BURST = _rate_cfg.get("burst_allowance", 5)

_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate SENTINEL_API_KEY on every request. Health endpoint is exempt."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not settings.sentinel_api_key or api_key != settings.sentinel_api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        tenant_id = request.headers.get("X-Tenant-ID", "demo-tenant")
        request.state.tenant_id = tenant_id
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-tenant sliding window rate limiting.
    Accepts requests_per_minute and window_seconds for testability.
    Methods _is_allowed, _reset_tenant, _is_exempt_path, _get_retry_after
    are public for unit testing.
    """

    def __init__(self, app, requests_per_minute: int = _DEFAULT_RPM, window_seconds: int = 60):
        super().__init__(app)
        self._rpm = requests_per_minute
        self._window = window_seconds
        # Per-tenant sliding window: tenant_id → list of request timestamps
        self._counts: dict[str, list[float]] = defaultdict(list)

    def _is_exempt_path(self, path: str) -> bool:
        return path in _EXEMPT_PATHS

    def _is_allowed(self, tenant_id: str) -> bool:
        """Check and record a request. Returns True if within limit."""
        key = tenant_id or "_anonymous_"
        now = time.time()
        window_start = now - self._window

        # Slide the window — remove expired timestamps
        self._counts[key] = [t for t in self._counts[key] if t > window_start]

        if len(self._counts[key]) >= self._rpm:
            return False

        self._counts[key].append(now)
        return True

    def _reset_tenant(self, tenant_id: str) -> None:
        """Clear rate limit state for a tenant — used in tests to simulate window expiry."""
        key = tenant_id or "_anonymous_"
        self._counts[key] = []

    def _get_retry_after(self, tenant_id: str) -> int:
        """Return seconds until oldest request in window expires."""
        key = tenant_id or "_anonymous_"
        if not self._counts[key]:
            return 0
        oldest = min(self._counts[key])
        retry = int(oldest + self._window - time.time())
        return max(1, min(retry, self._window))

    async def dispatch(self, request: Request, call_next):
        if self._is_exempt_path(request.url.path):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", "anonymous")

        if not self._is_allowed(tenant_id):
            retry_after = self._get_retry_after(tenant_id)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject unique request ID for log correlation."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
