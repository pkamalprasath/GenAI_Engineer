"""
Rate Limiting Middleware

=============================================================================
WHY THIS FILE IS REQUIRED:
=============================================================================
Without rate limiting, a single user or a script could flood the bot with
thousands of requests per minute, exhausting AI API credits, overwhelming
backend services, and degrading the experience for all other users. This
middleware enforces per-user and per-channel request quotas, rejecting excess
requests with HTTP 429 (Too Many Requests) and a Retry-After hint.

=============================================================================
PROGRAM LOGIC:
=============================================================================
1. EXTRACT IDENTITY: The middleware extracts user_id and channel_id from
   the incoming request to identify WHO is making the request and WHERE.

2. PER-USER CHECK: If a user_id is present, the middleware checks the user's
   request count against the configured limit (default: 10 req/min). If
   exceeded, a 429 response is returned immediately.

3. PER-CHANNEL CHECK: If a channel_id is present, the middleware checks the
   channel's aggregate request count (default: 30 req/min). This prevents
   a single busy channel from monopolizing bot resources.

4. PASS-THROUGH: If both checks pass, `next()` is called to forward the
   request to the error_handler middleware and then to the event listener.

=============================================================================
WHY THIS APPROACH:
=============================================================================
- SLIDING WINDOW (FIXED): The RateLimiter uses a fixed-window algorithm
  where each key gets a count and a reset timestamp. When the window expires,
  the count resets to zero. This is simpler than a true sliding window but
  sufficient for most use cases.
- IN-MEMORY STORAGE: The rate limiter stores state in a Python dict, which
  is fast but only works for single-process deployments. For production with
  multiple bot instances behind a load balancer, this should be replaced
  with a Redis-backed rate limiter.
- TWO-TIER LIMITING: Per-user limits prevent individual abuse, while
  per-channel limits prevent collective abuse (e.g., a channel where many
  users simultaneously trigger the bot).
- 429 STATUS CODE: HTTP 429 is the standard status for rate limiting. The
  response includes a `retry_after` field so clients know when to retry.

=============================================================================
RELATIONSHIP TO OTHER FILES:
=============================================================================
- src/app.py                     -- Registers this as the second middleware.
- src/slack/middleware/auth.py    -- Runs before this (auth first, then rate limit).
- src/slack/middleware/error_handler.py -- Runs after this.
- src/utils/security.py          -- Provides the RateLimiter class.
- config/settings.py             -- Provides rate_limit_per_user and
                                    rate_limit_per_channel configuration.

=============================================================================
SECURITY CONSIDERATIONS:
=============================================================================
- Rate limiting is a critical defense against denial-of-service (DoS) attacks.
- The per-user limit prevents a single compromised or malicious account from
  exhausting the bot's AI API budget.
- The per-channel limit prevents "thundering herd" scenarios where many users
  in the same channel simultaneously trigger the bot.
- In production, use Redis or a distributed rate limiter to prevent bypass
  via multiple bot instances.
"""

import json

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.request.async_request import AsyncBoltRequest
from slack_bolt.response import BoltResponse

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.security import RateLimiter

# Module-level logger for rate limit events
logger = get_logger(__name__)

# ============================================================================
# Global Rate Limiter Instance
# ============================================================================
# WHY a module-level singleton: All requests within the same process must share
# a single rate limiter instance so that request counts accumulate correctly.
# If each request created its own RateLimiter, every request would see count=1
# and never be rate-limited.
#
# LIMITATION: This in-memory approach only works for single-process deployments.
# For multi-process or multi-instance deployments (e.g., behind a load balancer),
# replace this with a Redis-backed RateLimiter that shares state across processes.
# ============================================================================

_rate_limiter = RateLimiter()


async def rate_limit_middleware(
    request: AsyncBoltRequest, context: AsyncBoltContext, next
) -> BoltResponse:
    """
    Rate limiting middleware for Slack requests.

    Implements two levels of rate limiting:
    1. Per-user rate limit (default: 10 requests/minute)
    2. Per-channel rate limit (default: 30 requests/minute)

    Args:
        request: Incoming Slack request.
        context: Bolt context (not directly used here but required by the
                 middleware signature).
        next: Callable that invokes the next middleware or listener. NOT
              calling next() short-circuits the request (used when rate
              limit is exceeded).

    Returns:
        BoltResponse -- either 200 OK (from downstream) or 429 Too Many Requests.

    Design Decision:
        Rate limits are configured via settings (config/settings.py) so they
        can be tuned per environment (e.g., higher limits in development,
        stricter in production) without changing code.
    """
    body = request.body
    event = body.get("event", {})

    # Extract identity for rate limiting.
    # WHY fallback to body["user_id"]: Slash commands put user_id at the top
    # level of the body, not inside an event dict. The `or` handles both cases.
    user_id = event.get("user") or body.get("user_id")
    channel_id = event.get("channel")

    # =========================================================================
    # Per-User Rate Limiting
    # =========================================================================
    # WHY per-user: Prevents a single user from monopolizing the bot. Without
    # this, one person running a script could send 1000 messages/minute and
    # exhaust the AI API budget for the entire team.
    if user_id:
        # Create a namespaced key to avoid collisions between user and channel limits
        user_key = f"user:{user_id}"
        allowed, retry_after = _rate_limiter.is_allowed(
            key=user_key, max_requests=settings.rate_limit_per_user, window_seconds=60
        )

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for user: {user_id}",
                extra={"user_id": user_id, "retry_after": retry_after},
            )

            # Return HTTP 429 with a JSON body explaining the rate limit.
            # The retry_after field tells the client when to try again.
            return BoltResponse(
                status=429,
                body=json.dumps({
                    "ok": False,
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Please retry after {retry_after} seconds.",
                    "retry_after": retry_after,
                }),
            )

    # =========================================================================
    # Per-Channel Rate Limiting
    # =========================================================================
    # WHY per-channel: In a busy channel, many different users might trigger
    # the bot simultaneously. Even if no single user exceeds their personal
    # limit, the aggregate load on the channel could overwhelm backend services.
    if channel_id:
        channel_key = f"channel:{channel_id}"
        allowed, retry_after = _rate_limiter.is_allowed(
            key=channel_key, max_requests=settings.rate_limit_per_channel, window_seconds=60
        )

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for channel: {channel_id}",
                extra={"channel_id": channel_id, "retry_after": retry_after},
            )

            return BoltResponse(
                status=429,
                body=json.dumps({
                    "ok": False,
                    "error": "rate_limit_exceeded",
                    "message": f"Channel rate limit exceeded. Please retry after {retry_after} seconds.",
                    "retry_after": retry_after,
                }),
            )

    # =========================================================================
    # Rate Limit Not Exceeded - Continue to Next Middleware
    # =========================================================================
    # WHY log at debug: Successful rate limit checks happen for EVERY request
    # and would be noisy at INFO level. DEBUG allows enabling them when
    # investigating rate limit issues without polluting normal logs.

    logger.debug("Rate limit check passed", extra={"user_id": user_id, "channel_id": channel_id})

    return await next()


# ============================================================================
# Rate Limiter Management Functions
# ============================================================================
# WHY: These utility functions allow administrators and tests to manually
# reset rate limits. In production, you might expose these through an admin
# slash command (e.g., /bot-admin reset-rate-limit @user).
# ============================================================================


def reset_user_rate_limit(user_id: str) -> None:
    """
    Reset rate limit for a specific user.

    WHY: Useful when a legitimate user has been rate-limited due to a spike
    in activity and an admin wants to unblock them immediately.

    Args:
        user_id: Slack user ID (e.g., "U12345")
    """
    key = f"user:{user_id}"
    _rate_limiter.reset(key)
    logger.info(f"Rate limit reset for user: {user_id}")


def reset_channel_rate_limit(channel_id: str) -> None:
    """
    Reset rate limit for a specific channel.

    WHY: Useful after a "thundering herd" event where a channel was temporarily
    rate-limited and normal operation needs to resume.

    Args:
        channel_id: Slack channel ID (e.g., "C12345")
    """
    key = f"channel:{channel_id}"
    _rate_limiter.reset(key)
    logger.info(f"Rate limit reset for channel: {channel_id}")


def clear_all_rate_limits() -> None:
    """
    Clear all rate limit data.

    WHY: Useful for testing (reset state between test runs) or emergency
    override when rate limiting is causing problems and needs to be
    temporarily disabled.

    Security Note:
        This logs at WARNING level because clearing all rate limits
        temporarily removes a security control. Monitor closely after calling.
    """
    _rate_limiter.clear()
    logger.warning("All rate limits cleared")


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    WHY: Exposed for testing (allows injecting a mock) and for admin tools
    that need to inspect current rate limit state.

    Returns:
        The module-level RateLimiter singleton instance.

    Design Decision:
        Returning the actual instance (not a copy) allows callers to inspect
        and modify state directly. In production, consider returning a
        read-only wrapper to prevent accidental modifications.
    """
    return _rate_limiter
