"""
Authentication Middleware

=============================================================================
WHY THIS FILE IS REQUIRED:
=============================================================================
Every incoming Slack request must be authenticated before the bot processes it.
While Slack Bolt automatically verifies request signatures (HMAC-SHA256) and
timestamp freshness, this middleware adds APPLICATION-LEVEL security checks
that go beyond what Slack Bolt provides out of the box:
  - Sanitized request logging for audit trails
  - Bot loop prevention (ignoring messages the bot itself sent)
  - Extensibility points for workspace and user authorization

Without this middleware, the bot would be vulnerable to processing its own
messages (infinite loops) and would lack an audit trail of incoming requests.

=============================================================================
PROGRAM LOGIC:
=============================================================================
1. RECEIVE REQUEST: The middleware receives every Slack request before any
   event listener sees it.

2. LOG (SANITIZED): The request body is sanitized (tokens/secrets masked)
   and logged for debugging and audit purposes.

3. BOT LOOP CHECK: If the event contains a bot_id, the request is
   short-circuited with a 200 OK. This prevents the bot from responding
   to its own messages, which would cause an infinite loop.

4. TEAM CHECK (EXTENSIBLE): Placeholder for workspace-level authorization.
   In a multi-tenant deployment, this is where you would verify the
   workspace is allowed to use the bot.

5. USER CHECK (EXTENSIBLE): Placeholder for user-level authorization.
   Could restrict certain commands to admin users.

6. CONTINUE: If all checks pass, `next()` is called to pass the request
   to the next middleware (rate_limit -> error_handler -> listener).

=============================================================================
WHY THIS APPROACH:
=============================================================================
- MIDDLEWARE PATTERN: Cross-cutting concerns like authentication belong in
  middleware, not in individual listeners. This ensures EVERY request is
  checked, even if a developer forgets to add auth logic to a new listener.
- DEFENSE IN DEPTH: Slack Bolt already verifies request signatures, but we
  add our own bot-loop prevention as an extra safety net. The listeners also
  check for bot_id, creating two layers of protection.
- SANITIZED LOGGING: Production logs are often accessed by multiple team
  members and may be sent to third-party services (DataDog, Splunk). Masking
  tokens in logs prevents accidental credential exposure.

=============================================================================
RELATIONSHIP TO OTHER FILES:
=============================================================================
- src/app.py                     -- Registers this middleware first in the chain.
- src/slack/middleware/rate_limit.py   -- Next middleware after auth.
- src/slack/middleware/error_handler.py -- Final middleware before listeners.
- src/utils/security.py          -- Provides `sanitize_for_logging()`.
- src/utils/logger.py            -- Provides the structured logger.

=============================================================================
SECURITY CONSIDERATIONS:
=============================================================================
- Slack Bolt's built-in verification (HMAC-SHA256 signature + timestamp) is
  the PRIMARY defense against forged requests. This middleware is ADDITIONAL.
- The bot loop check is critical: without it, a bot that posts a message
  would receive that message as an event, respond to it, receive THAT
  response, and loop forever -- consuming API quota and flooding channels.
- `sanitize_for_logging` recursively masks any dict keys containing words
  like "token", "secret", "password" to prevent accidental log exposure.
"""

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.request.async_request import AsyncBoltRequest
from slack_bolt.response import BoltResponse

from src.utils.logger import get_logger
from src.utils.security import sanitize_for_logging

# Module-level logger for auth middleware events
logger = get_logger(__name__)


async def auth_middleware(
    request: AsyncBoltRequest, context: AsyncBoltContext, next
) -> BoltResponse:
    """
    Authentication middleware for Slack requests.

    Slack Bolt automatically verifies:
    - Request signatures (HMAC-SHA256) using the signing secret
    - Timestamp freshness (within 5 minutes) to prevent replay attacks

    This middleware adds:
    - Request logging with sanitized data (tokens masked)
    - Bot loop prevention (short-circuits bot-originated messages)
    - Extensibility hooks for team and user authorization

    Args:
        request: Incoming Slack request containing the raw body, headers,
                 and parsed event data.
        context: Bolt context populated by Slack Bolt with authentication
                 info (team_id, user_id, bot_token, etc.).
        next: Callable that invokes the next middleware or listener in the
              chain. NOT calling next() short-circuits the request.

    Returns:
        BoltResponse from the next handler, or a 200 OK if short-circuited.

    Design Decision:
        The `next` parameter name (without _fn suffix) matches Slack Bolt's
        middleware signature convention. Calling `await next()` passes control
        to the next registered middleware or, if this is the last middleware,
        to the matched event listener.
    """
    # =========================================================================
    # Sanitized Request Logging
    # =========================================================================
    # WHY: Logging every request creates an audit trail for debugging and
    # security incident investigation. However, raw request bodies may contain
    # tokens or secrets, so we sanitize before logging.

    body = request.body

    # sanitize_for_logging recursively masks sensitive fields (token, secret, etc.)
    sanitized_body = sanitize_for_logging(body)
    logger.debug(
        "Incoming Slack request",
        extra={
            "event_type": body.get("type"),
            "team_id": body.get("team_id"),
            "user_id": body.get("event", {}).get("user"),
            "sanitized_body": sanitized_body,
        },
    )

    # =========================================================================
    # Bot Loop Prevention
    # =========================================================================
    # WHY: When the bot posts a message, Slack sends a "message" event back to
    # the bot. If the bot processes this event and responds, it creates an
    # infinite loop: bot posts -> event fires -> bot posts -> event fires ...
    #
    # SECURITY IMPACT: An infinite loop would:
    #   1. Exhaust the Slack API rate limit (causing temporary bans)
    #   2. Flood channels with bot messages
    #   3. Consume AI API credits rapidly
    #   4. Potentially crash the bot process
    #
    # DETECTION: Bot-originated messages have a "bot_id" field in the event.
    # We check for this and short-circuit the entire middleware chain.

    event = body.get("event", {})
    if event.get("bot_id"):
        logger.debug(f"Ignoring message from bot: {event.get('bot_id')}")
        # Return 200 OK without calling next() -- this stops the request
        # from reaching any listener. Returning 200 tells Slack "we received
        # it" so Slack does not retry the delivery.
        return BoltResponse(status=200, body="OK")

    # =========================================================================
    # Team/Workspace Authorization (Extensibility Point)
    # =========================================================================
    # WHY: If this app is distributed to multiple Slack workspaces (multi-tenant),
    # you would add authorization logic here to verify the workspace is allowed
    # to use the bot. For a single-workspace deployment, this is a no-op.
    #
    # Example implementation for multi-tenant:
    #   authorized_teams = await load_authorized_teams_from_db()
    #   if team_id not in authorized_teams:
    #       return BoltResponse(status=403, body="Workspace not authorized")

    team_id = body.get("team_id")
    if team_id:
        logger.debug(f"Request from team: {team_id}")
        # Could add workspace authorization check here
        # Example: if team_id not in authorized_teams: return error

    # =========================================================================
    # User Authorization (Extensibility Point)
    # =========================================================================
    # WHY: Some commands (like admin operations) should be restricted to specific
    # users or roles. This is the place to check user permissions before the
    # request reaches any listener.
    #
    # Example implementation:
    #   if command == "/bot-admin" and not await is_admin(user_id):
    #       return BoltResponse(status=403, body="Admin access required")

    user_id = event.get("user")
    if user_id:
        logger.debug(f"Request from user: {user_id}")
        # Could add user authorization check here
        # Example: if command requires admin, check user.is_admin

    # =========================================================================
    # Continue to Next Middleware/Listener
    # =========================================================================
    # WHY: Calling next() passes the request to the next middleware in the
    # chain (rate_limit_middleware). If all middleware pass, the request
    # eventually reaches the matched event listener.

    return await next()
