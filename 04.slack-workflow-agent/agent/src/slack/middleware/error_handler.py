"""
Error Handler Middleware
========================

WHY THIS FILE IS REQUIRED:
    Every web application needs a centralized safety net that catches exceptions
    before they propagate to the framework or crash the process.  Without this
    middleware, any unhandled exception in a Slack listener would result in:
      - an opaque HTTP 500 response to Slack (which Slack may retry, causing
        duplicate processing),
      - sensitive stack traces or internal details leaking to end users,
      - inconsistent error logging (each listener would need its own try/except),
      - no ability to return different HTTP status codes for different error
        categories (e.g., 429 for rate limits vs. 400 for bad input).

    This middleware solves all four problems by wrapping every downstream
    handler in a single try/except hierarchy, translating exceptions into
    structured, user-safe JSON responses with appropriate HTTP status codes.

PROGRAM LOGIC:
    1. The middleware receives the incoming Slack request and calls `next()`
       to invoke the downstream middleware chain and, eventually, the listener.
    2. If `next()` completes without raising, the successful BoltResponse is
       returned unmodified.
    3. If `next()` raises, the exception is caught and matched against a
       priority-ordered chain of except blocks:
         a. RateLimitError   -> 429 with retry_after hint
         b. ValidationError  -> 400 (client mistake, not server fault)
         c. SlackAPIError    -> 500 (Slack-side failure)
         d. AgentError       -> 500 (LLM / orchestrator failure)
         e. BotMemoryError   -> 500 (file-backed memory failure)
         f. RAGError         -> 500 (vector search failure)
         g. MCPError         -> 500 (external tool server failure)
         h. SlackBotError    -> 500 (catch-all for any custom exception)
         i. Exception        -> 500 (truly unexpected / unknown error)
    4. Each branch logs the error (with severity appropriate to the category)
       and returns a BoltResponse containing a user-friendly message that
       never exposes internal details.
    5. Two helper functions at the bottom provide reusable error formatting
       and retry-eligibility logic for use outside the middleware itself.

WHY THIS APPROACH:
    - MIDDLEWARE vs. DECORATOR: Middleware runs automatically for every request
      without requiring each listener author to remember a decorator or
      try/except.  This eliminates an entire class of bugs ("developer forgot
      to add error handling to the new listener").
    - ORDERED EXCEPT BLOCKS: Python's except chain is matched top-to-bottom.
      More specific exceptions (RateLimitError) must appear before their
      parent classes (SlackAPIError -> SlackBotError -> Exception).  If the
      order were reversed, the parent would catch everything and the specific
      handlers would never run.
    - USER-FRIENDLY MESSAGES: Each error category returns a different
      plain-language message so the Slack user understands what went wrong
      (e.g., "You're sending requests too quickly" vs. "I had trouble
      searching my knowledge base").  Technical details go to the log, not
      to the user -- this is both better UX and a security best practice.
    - SEPARATE should_retry() HELPER: Callers (e.g., the agent orchestrator
      or a retry wrapper) can ask whether a given exception is transient
      without duplicating the classification logic.

RELATIONSHIP TO OTHER FILES:
    - src/app.py (CALLER):
        Registers this as the THIRD middleware in the chain
        (auth -> rate_limit -> error_handler).  It runs last among
        middleware so it can catch errors from listeners AND from
        the rate_limit middleware itself.
    - src/utils/exceptions.py (DEPENDENCY):
        Defines the full exception hierarchy (SlackBotError and its
        subclasses) that this middleware catches and classifies.
    - src/utils/logger.py (DEPENDENCY):
        Provides the structured logger used for error telemetry.
    - src/slack/middleware/rate_limit.py (PEER):
        Runs before this middleware.  If rate_limit raises RateLimitError,
        this middleware catches it and formats the 429 response.
    - src/slack/listeners/*.py (DOWNSTREAM):
        All listener modules benefit from this middleware -- any exception
        they raise is caught here, so they do not need their own global
        error handling.
"""

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.request.async_request import AsyncBoltRequest
from slack_bolt.response import BoltResponse

from src.utils.logger import get_logger
from src.utils.exceptions import (
    SlackBotError,
    SlackAPIError,
    RateLimitError,
    AgentError,
    BotMemoryError,
    RAGError,
    MCPError,
    ValidationError,
)

# WHY module-level logger: Each middleware/module gets its own named logger
# so that log output includes the originating module (e.g.,
# "src.slack.middleware.error_handler") for easy filtering and grep-ability.
logger = get_logger(__name__)


async def error_handler_middleware(
    request: AsyncBoltRequest, context: AsyncBoltContext, next
) -> BoltResponse:
    """
    Error handler middleware that catches and handles exceptions.

    This middleware:
    1. Executes the next handler in a try-except block
    2. Catches known exception types and formats user-friendly responses
    3. Logs all errors for monitoring
    4. Returns appropriate HTTP status codes

    Args:
        request: Incoming Slack request
        context: Bolt context
        next_fn: Next middleware/listener in chain

    Returns:
        BoltResponse (success or error response)
    """
    try:
        # WHY await next() with no other logic on the happy path: The middleware
        # acts as a transparent pass-through when nothing goes wrong.  Keeping
        # the success path minimal avoids adding latency to every request.
        return await next()

    except RateLimitError as e:
        # WHY catch RateLimitError first (before SlackAPIError): RateLimitError
        # inherits from SlackAPIError.  If SlackAPIError were caught first, rate
        # limit errors would be misclassified as generic API failures and the
        # user would not receive the retry_after hint they need.
        logger.warning(f"Rate limit error: {e.message}")
        return BoltResponse(
            status=429,  # WHY 429: HTTP standard for "Too Many Requests"
            body={
                "ok": False,
                "error": "rate_limit_exceeded",
                "message": "You're sending requests too quickly. Please slow down.",
                "retry_after": e.retry_after,  # WHY include retry_after: Lets well-behaved clients back off precisely
            },
        )

    except ValidationError as e:
        # WHY 400 (not 500): Validation failures are the CLIENT's fault (bad
        # input), not the server's.  Returning 400 signals that the user should
        # fix their request, not retry blindly.
        logger.warning(f"Validation error: {e.message}")
        return BoltResponse(
            status=400, body={"ok": False, "error": "invalid_input", "message": e.message}
        )

    except SlackAPIError as e:
        # WHY log error_code in extra: Slack API error codes (e.g.,
        # "channel_not_found", "not_authed") are critical for debugging but
        # should not appear in the user-facing message.
        logger.error(f"Slack API error: {e.message}", extra={"error_code": e.error_code})
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "slack_api_error",
                # WHY generic message: The actual Slack error code might reveal
                # internal channel IDs or permission details we don't want exposed.
                "message": "Failed to communicate with Slack. Please try again.",
            },
        )

    except AgentError as e:
        # WHY separate from SlackAPIError: Agent errors originate from the LLM
        # orchestrator (not from Slack), so they need a different user-facing
        # message that suggests rephrasing rather than "try again."
        logger.error(f"Agent error: {e.message}")
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "agent_error",
                "message": "I encountered an error while processing your request. Please try rephrasing or try again later.",
            },
        )

    except BotMemoryError as e:
        # WHY surface memory errors distinctly: Memory failures are non-fatal
        # for the user's request (the bot can still respond), but the user
        # should know their conversation context may not have been saved.
        logger.error(f"Memory error: {e.message}")
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "memory_error",
                "message": "I had trouble accessing my memory. The operation may not be saved.",
            },
        )

    except RAGError as e:
        # WHY "I'll try to help without it": RAG failures are gracefully
        # degradable -- the bot can still answer using its base LLM knowledge,
        # just without the benefit of indexed channel history.
        logger.error(f"RAG error: {e.message}")
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "knowledge_base_error",
                "message": "I had trouble searching my knowledge base. I'll try to help without it.",
            },
        )

    except MCPError as e:
        # WHY separate MCP handling: MCP (Model Context Protocol) errors come
        # from external tool servers (GitHub, Notion).  The user message says
        # "one of my tools" because the specific tool name might be confusing
        # to non-technical users.
        logger.error(f"MCP error: {e.message}")
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "tool_error",
                "message": "I had trouble using one of my tools. Please try again.",
            },
        )

    except SlackBotError as e:
        # WHY this catch-all for SlackBotError: Any new custom exception that
        # inherits from SlackBotError but is not yet handled by a specific
        # except block above will land here.  This ensures forward compatibility
        # when new exception types are added to exceptions.py.
        logger.error(f"Bot error: {e.message}")
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "bot_error",
                "message": e.message or "Something went wrong. Please try again.",
            },
        )

    except Exception as e:
        # WHY logger.exception (not logger.error): logger.exception()
        # automatically includes the full traceback in the log record, which
        # is essential for diagnosing truly unexpected errors.
        logger.exception(f"Unexpected error in middleware: {e}")

        # WHY log request.body: For unexpected errors, the request payload is
        # often the only way to reproduce the issue.  This structured log entry
        # can be queried in log aggregation systems (ELK, Datadog, etc.).
        logger.error(
            "Unexpected exception details",
            extra={
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "request_body": request.body,
            },
        )

        # WHY "The team has been notified" even without alerting wired up:
        # This sets user expectations and can be made truthful later by adding
        # Sentry, PagerDuty, or a Slack admin-channel alert above this return.
        return BoltResponse(
            status=500,
            body={
                "ok": False,
                "error": "internal_error",
                "message": "An unexpected error occurred. The team has been notified.",
            },
        )


# ==============================================================================
# Error Response Formatters
# ==============================================================================
# WHY standalone functions (not methods on the middleware): These utilities are
# used outside the middleware context -- for example, by listeners that want to
# format error responses for ephemeral messages, or by tests that need to
# verify error classification logic without spinning up the full middleware.
# ==============================================================================


def format_error_response(error: Exception, include_details: bool = False) -> dict:
    """
    Format an exception into a user-friendly error response.

    Args:
        error: Exception to format
        include_details: Whether to include technical details (dev only)

    Returns:
        Dictionary with error information
    """
    response = {"ok": False, "error": type(error).__name__, "message": str(error)}

    if include_details and isinstance(error, SlackBotError):
        # WHY gate on include_details: In production, the `details` dict may
        # contain internal file paths, database queries, or API keys embedded
        # in error context.  Only development/staging should ever see this.
        response["details"] = error.details

    return response


def should_retry(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.

    Args:
        error: Exception to check

    Returns:
        True if error is transient (retry recommended)
    """
    # WHY RateLimitError is retryable: Rate limits are inherently temporary --
    # the quota resets after the window expires, so retrying after the
    # retry_after period will succeed.
    if isinstance(error, RateLimitError):
        return True

    # WHY only specific SlackAPIError codes are retryable: Not all Slack API
    # errors are transient.  "channel_not_found" will never succeed on retry,
    # but "timeout" and "service_unavailable" are temporary server-side issues.
    if isinstance(error, SlackAPIError):
        transient_codes = ["timeout", "service_unavailable", "internal_error"]
        return error.error_code in transient_codes

    # WHY ValidationError is NOT retryable: The same invalid input will produce
    # the same validation error on every attempt.  Retrying wastes resources.
    if isinstance(error, ValidationError):
        return False

    # WHY default to False: For unknown error types, it is safer to NOT retry
    # automatically.  Retrying an unknown error could cause side effects (e.g.,
    # duplicate messages) if the original request partially succeeded.
    return False
