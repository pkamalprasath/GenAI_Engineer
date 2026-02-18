"""
Custom Exception Hierarchy for the Slack Bot Assistant
========================================================

WHY THIS FILE IS REQUIRED:
    Python's built-in exceptions (ValueError, RuntimeError, etc.) are generic
    and carry no domain-specific meaning.  When the agent's ReAct loop catches
    a plain ValueError, it cannot distinguish between a bad user input, a
    misconfigured token, and a corrupt memory file -- all three would require
    different recovery strategies.  This module defines a tree of custom
    exceptions rooted at SlackBotError so that:
      - Each subsystem (Slack API, Agent, Memory, RAG, MCP, Services) has its
        own exception branch.
      - Callers can catch at any granularity: a broad "except SlackBotError"
        for last-resort handling, or a precise "except RateLimitError" to
        implement exponential backoff.
      - Every exception carries a structured `details` dict for machine-readable
        context that logging/monitoring systems can index.
    Without this file, error handling across the 30+ modules would devolve into
    string-matching on generic exception messages, which is brittle and
    unmanageable.

PROGRAM LOGIC:
    1. SlackBotError is the root of the hierarchy.  It extends Exception and
       adds a `message` string plus an optional `details` dict.  Its __str__
       merges both into a human-readable representation.
    2. Six top-level branches extend SlackBotError:
         ConfigurationError  -- startup/config issues
         SlackAPIError       -- Slack platform errors (with error_code)
         AgentError          -- ReAct loop / tool execution errors
         BotMemoryError      -- persistent memory read/write errors
         RAGError            -- retrieval-augmented generation errors
         MCPError            -- Model Context Protocol server errors
         ValidationError     -- input validation failures
         ServiceError        -- business logic service failures
    3. Leaf exceptions add domain-specific fields.  For example,
       RateLimitError carries `retry_after` (seconds) and ToolExecutionError
       carries `tool_name`.
    4. handle_exception() is a utility that logs the full traceback internally
       while returning only a user-safe message to the Slack user, preventing
       information leakage.

WHY THIS APPROACH:
    - Single-inheritance tree: every custom exception IS-A SlackBotError,
      so a top-level "except SlackBotError" in the Slack event loop guarantees
      no custom exception ever leaks an ugly traceback to the end user.
    - `details` dict over ad-hoc attributes: a uniform structure means logging
      middleware can always call `exc.details` without type-checking each
      subclass, which simplifies the error_handler middleware.
    - Separate ValidationError vs. SecurityValidationError: security-related
      validation failures are logged at a higher severity and may trigger
      alerts, whereas ordinary input validation is merely informational.
    - handle_exception() centralizes the "log internally, reply externally"
      pattern so that every Slack listener does not re-implement it.

SECURITY CONSIDERATIONS:
    - handle_exception() deliberately withholds internal details from the user.
      Exposing stack traces or SQL errors to end users is a well-known
      information-disclosure vulnerability (OWASP A01:2021).
    - SecurityValidationError exists specifically so that security failures
      (invalid signatures, injection attempts) can be routed to a dedicated
      alert channel rather than silently swallowed.

RELATIONSHIP TO OTHER FILES:
    USED BY (imports specific exception classes):
        - src/utils/validators.py      (InvalidInputError, SecurityValidationError)
        - src/utils/security.py        (SecurityValidationError)
        - src/slack/middleware/error_handler.py (SlackBotError, handle_exception)
        - src/slack/services/message_service.py
        - src/agent/orchestrator.py    (AgentError, ToolExecutionError, ContextTooLargeError)
        - src/memory/*.py              (BotMemoryError and children)
        - src/rag/*.py                 (RAGError and children)
        - src/mcp_servers/*.py         (MCPError and children)
        - src/services/*.py            (ServiceError and children)
        - src/app.py
    USES:
        - Python stdlib only (typing)
        - No external dependencies -- this is intentional so that importing
          exceptions never triggers side effects or circular imports.
"""

from typing import Optional, Any

# ==============================================================================
# Base Exception
# ==============================================================================
# WHY a single base class: it lets the outermost error handler in
# src/slack/middleware/error_handler.py catch *all* application-specific errors
# with one clause ("except SlackBotError") while still allowing inner handlers
# to catch narrower types.  This mirrors the design of libraries like
# requests.exceptions.RequestException and django.core.exceptions.
# ==============================================================================


class SlackBotError(Exception):
    """
    Root of the custom exception hierarchy for this Slack bot.

    HOW it works:
        Stores a human-readable `message` and an optional `details` dict.
        __str__ combines both so that log output is immediately useful.

    WHY it is implemented this way:
        - Inheriting from Exception (not BaseException) ensures that bare
          "except Exception" blocks in third-party code can still catch it.
        - The `details` dict provides structured, machine-indexable context
          (e.g., {"channel_id": "C123", "retry_after": 30}) that is far more
          useful for automated monitoring than a free-text message alone.
        - Defaulting `details` to an empty dict (not None) avoids repeated
          None-checks in consuming code.
    """

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        # WHY default to empty dict: callers can always do exc.details.get(key)
        # without first checking "if exc.details is not None".
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        # WHY include details in __str__: when this exception is printed in
        # logs, the structured context appears immediately alongside the
        # message, eliminating the need to inspect the object interactively.
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ==============================================================================
# Configuration Exceptions
# ==============================================================================
# WHY a dedicated branch for configuration: configuration errors occur at
# startup and are fundamentally different from runtime errors.  They indicate
# that the application cannot function correctly and should not attempt to
# serve requests.  Separating them lets main.py catch ConfigurationError and
# exit cleanly with a diagnostic message rather than producing confusing
# runtime failures later.
# ==============================================================================


class ConfigurationError(SlackBotError):
    """
    Raised when application configuration is invalid or missing.

    HOW it works:
        Inherits directly from SlackBotError without adding extra fields,
        because the base message + details dict is sufficient for
        configuration diagnostics.

    WHY it is implemented this way:
        - Keeps startup validation separate from runtime validation.
        - A catch of "except ConfigurationError" in main.py can print a
          helpful setup guide and exit with a non-zero code, rather than
          letting the app limp along in a broken state.

    Examples of triggers:
        - Missing required environment variables (SLACK_BOT_TOKEN)
        - Invalid YAML in configuration files
        - Incorrect API endpoint URLs
    """

    pass


class TokenError(ConfigurationError):
    """
    Raised for authentication token issues.

    HOW it works:
        A specialization of ConfigurationError for token-specific problems.

    WHY it is implemented this way:
        - Token errors are the single most common configuration mistake.
          Having a dedicated class lets the error handler suggest token-specific
          remediation (e.g., "regenerate your bot token at api.slack.com").
        - Subclassing ConfigurationError means it is still caught by any
          "except ConfigurationError" block.

    Examples of triggers:
        - Expired OAuth tokens
        - Tokens with wrong prefix (xoxp- instead of xoxb-)
        - Missing SLACK_APP_TOKEN for Socket Mode
        - Token rotation failures during automated refresh
    """

    pass


# ==============================================================================
# Slack API Exceptions
# ==============================================================================
# WHY a separate API error branch: Slack API failures are transient and
# retryable (rate limits, network blips), whereas configuration errors are
# persistent until a human fixes them.  Separating the two lets retry logic
# target only SlackAPIError descendants without accidentally retrying a
# missing-env-var error.
# ==============================================================================


class SlackAPIError(SlackBotError):
    """
    Raised when a Slack Web API or Events API call fails.

    HOW it works:
        Extends SlackBotError with an optional `error_code` field that maps
        to Slack's documented error strings (e.g., "channel_not_found",
        "not_authed").

    WHY it is implemented this way:
        - The error_code enables programmatic branching on specific Slack
          errors without fragile string matching on the message text.
        - Wrapping Slack SDK exceptions with this class decouples the rest
          of the codebase from the Slack SDK's internal exception hierarchy,
          making it easier to swap SDKs or mock in tests.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        # WHY store error_code separately: it is a machine-readable identifier
        # that monitoring dashboards can aggregate on, unlike the free-text
        # message which may vary.
        self.error_code = error_code
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        # WHY append error_code to __str__: makes log grep for specific Slack
        # errors trivial (e.g., grep "rate_limit_exceeded").
        if self.error_code:
            return f"{base} | Error Code: {self.error_code}"
        return base


class RateLimitError(SlackAPIError):
    """
    Raised when the Slack API returns HTTP 429 (Too Many Requests).

    HOW it works:
        Carries a `retry_after` field (seconds) extracted from Slack's
        Retry-After header.  The caller can sleep for that duration before
        retrying.

    WHY it is implemented this way:
        - Slack explicitly tells us when to retry via the Retry-After header.
          Encoding that value in the exception lets retry middleware implement
          precise backoff without guessing.
        - The error_code is hardcoded to "rate_limit_exceeded" so that
          monitoring can always identify rate-limit events consistently.
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        # WHY store retry_after: it comes directly from Slack's response header
        # and is the optimal wait time.  Exponential backoff without this hint
        # would either wait too long (wasting time) or too short (getting
        # rate-limited again).
        self.retry_after = retry_after
        super().__init__(message, error_code="rate_limit_exceeded", details=details)


class ChannelNotFoundError(SlackAPIError):
    """
    Raised when the target channel does not exist or is inaccessible.

    WHY a dedicated class: distinguishes "channel deleted" (permanent) from
    "rate limit" (transient), enabling different recovery strategies.
    """

    pass


class MessageNotFoundError(SlackAPIError):
    """
    Raised when a referenced message timestamp cannot be resolved.

    WHY a dedicated class: message-not-found errors typically indicate stale
    thread references in memory, not API outages.  The memory subsystem can
    catch this specifically and prune the stale reference.
    """

    pass


class PermissionDeniedError(SlackAPIError):
    """
    Raised when the bot token lacks the required OAuth scopes.

    WHY a dedicated class: permission errors require human intervention
    (adding scopes in the Slack app dashboard), so the error message can
    include the specific scope that is missing and a link to the dashboard.
    """

    pass


# ==============================================================================
# Agent Exceptions
# ==============================================================================
# WHY a dedicated agent branch: the ReAct orchestration loop in
# src/agent/orchestrator.py needs to distinguish between tool failures
# (retryable), context overflow (requires summarization), and missing tools
# (a programming error).  These three scenarios demand different recovery
# paths that generic exceptions cannot express.
# ==============================================================================


class AgentError(SlackBotError):
    """
    Base exception for errors occurring within the agent's ReAct loop.

    HOW it works:
        Inherits from SlackBotError without additional fields.  Serves as
        the catch-all for the orchestrator's main try/except.

    WHY it is implemented this way:
        - The orchestrator catches AgentError to decide whether to retry
          the current step, summarize context, or abort the conversation.
    """

    pass


class ToolExecutionError(AgentError):
    """
    Raised when a tool invocation fails during the agent's action step.

    HOW it works:
        Carries the `tool_name` so the orchestrator can log which tool
        failed and optionally remove it from the available tool set for
        the remainder of the conversation.

    WHY it is implemented this way:
        - Knowing the tool name lets the orchestrator craft a specific
          error observation for the LLM (e.g., "The search_messages tool
          returned an error") rather than a generic "something went wrong."
        - The agent can decide to try an alternative tool or skip the step.
    """

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        # WHY store tool_name: enables the orchestrator to include it in the
        # LLM's observation, so the model can reason about which tool failed
        # and choose an alternative strategy.
        self.tool_name = tool_name
        super().__init__(message, details)


class ContextTooLargeError(AgentError):
    """
    Raised when the conversation context exceeds the LLM's token limit.

    HOW it works:
        Carries current_tokens and max_tokens so the context builder can
        calculate exactly how much to trim or summarize.

    WHY it is implemented this way:
        - Rather than silently truncating (which loses information), raising
          an exception lets the orchestrator invoke the summarization service
          to intelligently compress the context before retrying.
        - Providing both token counts lets the summarizer calculate the
          target compression ratio.
    """

    def __init__(
        self, message: str, current_tokens: Optional[int] = None, max_tokens: Optional[int] = None
    ):
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens
        # WHY embed token counts in details: they are automatically included
        # in log output via SlackBotError.__str__, making it easy to spot
        # context-overflow trends in production logs.
        details = {"current_tokens": current_tokens, "max_tokens": max_tokens}
        super().__init__(message, details)


class ToolNotFoundError(AgentError):
    """
    Raised when the LLM requests a tool that is not in the registry.

    WHY a dedicated class: this is typically a programming error (the tool
    was not registered) or a hallucination by the LLM.  The orchestrator
    can catch it and feed back an observation like "tool X does not exist,
    available tools are [...]" so the LLM self-corrects.
    """

    pass


# ==============================================================================
# Memory Exceptions
# ==============================================================================
# WHY a dedicated memory branch: the memory subsystem (short-term + long-term)
# manages persistent state.  Failures here can cause data loss, so they need
# dedicated handling: retry writes, fall back to in-memory cache on read
# failure, alert on file corruption.  Mixing these with generic IOError
# would make such targeted recovery impossible.
# ==============================================================================


class BotMemoryError(SlackBotError):
    """
    Base exception for the persistent memory subsystem.

    WHY a separate branch: memory errors affect data durability and may
    require fallback strategies (e.g., serve from cache while disk is
    unavailable).
    """

    pass


class MemoryFileNotFoundError(BotMemoryError):
    """
    Raised when a referenced memory file does not exist on disk.

    WHY a dedicated class: a missing file on first access is normal (create
    it), but a missing file after a previous successful write indicates
    data loss.  The caller can distinguish the two by checking whether
    the file was expected to exist.
    """

    pass


class MemoryWriteError(BotMemoryError):
    """
    Raised when persisting memory data to disk fails.

    WHY a dedicated class: write failures risk data loss.  The memory
    manager can catch this, keep the data in its in-memory buffer, and
    schedule a retry, rather than discarding the data entirely.
    """

    pass


class MemoryReadError(BotMemoryError):
    """
    Raised when loading memory data from disk fails.

    WHY a dedicated class: read failures can be caused by file corruption,
    permission issues, or concurrent access.  Each cause requires a
    different recovery strategy that generic IOError cannot express.
    """

    pass


# ==============================================================================
# RAG Exceptions
# ==============================================================================
# WHY a dedicated RAG branch: Retrieval-Augmented Generation involves
# multiple failure modes -- embedding API outages, vector store corruption,
# indexing lag -- each of which degrades the bot's answer quality differently.
# Separate exceptions let the orchestrator decide whether to proceed without
# RAG context or to surface the error.
# ==============================================================================


class RAGError(SlackBotError):
    """
    Base exception for the RAG (Retrieval-Augmented Generation) pipeline.

    WHY a separate branch: RAG failures are often non-fatal -- the bot can
    still answer using the LLM's parametric knowledge, just with lower
    quality.  A dedicated branch lets the orchestrator implement graceful
    degradation.
    """

    pass


class IndexingError(RAGError):
    """
    Raised when indexing new messages into the vector store fails.

    WHY a dedicated class: indexing is asynchronous and can fall behind.
    The system can catch this, queue the failed messages for re-indexing,
    and continue serving queries against the existing index.
    """

    pass


class RetrievalError(RAGError):
    """
    Raised when querying the vector store for relevant context fails.

    WHY a dedicated class: retrieval failures mean the LLM will not have
    conversation history context.  The orchestrator can catch this and
    warn the user that the answer may be less informed.
    """

    pass


class EmbeddingError(RAGError):
    """
    Raised when generating text embeddings via the embedding API fails.

    WHY a dedicated class: embedding errors can be caused by API rate
    limits (retryable) or invalid input (not retryable).  The details
    dict can carry the HTTP status code to help callers decide.
    """

    pass


class VectorStoreError(RAGError):
    """
    Raised when low-level vector store operations (insert, delete, query) fail.

    WHY a dedicated class: vector store errors may indicate index corruption
    and could require a full re-index, which is an expensive operation that
    should be triggered deliberately rather than on every failure.
    """

    pass


# ==============================================================================
# MCP Exceptions
# ==============================================================================
# WHY a dedicated MCP branch: MCP (Model Context Protocol) servers are
# external processes that the bot communicates with over stdio/SSE.
# Connection failures, tool-not-found errors, and server crashes each need
# distinct handling -- reconnect, fallback to built-in tools, or alert ops.
# ==============================================================================


class MCPError(SlackBotError):
    """
    Base exception for MCP (Model Context Protocol) operations.

    WHY a separate branch: MCP servers are external processes with their
    own lifecycle.  Errors here may require process restart, reconnection,
    or failover to built-in tool implementations.
    """

    pass


class MCPServerError(MCPError):
    """
    Raised when an MCP server returns an error or crashes.

    HOW it works:
        Carries the `server_name` so the registry can identify which
        server to restart or remove from the available pool.

    WHY it is implemented this way:
        - The MCP registry manages multiple servers (Notion, GitHub, Slack).
          Knowing which server failed lets it restart only the broken one
          rather than cycling all servers.
    """

    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        # WHY store server_name: the registry uses it to look up the server's
        # process handle and decide whether to restart or deregister it.
        self.server_name = server_name
        super().__init__(message, details)


class MCPConnectionError(MCPError):
    """
    Raised when the connection to an MCP server cannot be established.

    WHY a dedicated class: connection errors are typically transient (the
    server process has not started yet) and warrant automatic retry with
    backoff, unlike MCPServerError which may indicate a bug in the server.
    """

    pass


class MCPToolNotFoundError(MCPError):
    """
    Raised when a requested tool is not exposed by any connected MCP server.

    WHY a dedicated class: this can happen when a server is restarted with
    a different tool manifest.  The registry can catch it and refresh its
    tool inventory from the server.
    """

    pass


# ==============================================================================
# Validation Exceptions
# ==============================================================================
# WHY a dedicated validation branch: validation errors are the most common
# error type in a user-facing application.  Splitting them from security
# validation lets the error handler return helpful feedback for innocent
# mistakes while escalating potential attacks to the security log.
# ==============================================================================


class ValidationError(SlackBotError):
    """
    Base exception for all input validation failures.

    WHY a separate branch: validation errors carry user-facing messages
    that should be returned to the Slack user as helpful feedback,
    unlike internal errors whose messages must be suppressed.
    """

    pass


class InvalidInputError(ValidationError):
    """
    Raised when user-provided input fails format or range checks.

    WHY a dedicated class: these errors produce user-visible feedback
    (e.g., "Channel ID must start with C") and should never be logged at
    ERROR level because they are expected during normal operation.
    """

    pass


class SecurityValidationError(ValidationError):
    """
    Raised when a security-sensitive validation check fails.

    WHY a dedicated class: unlike InvalidInputError (which is informational),
    a SecurityValidationError may indicate an active attack.  It is logged
    at WARNING/ERROR level and may trigger an alert to the security team.

    Examples of triggers:
        - Invalid request signature (HMAC mismatch)
        - Timestamp too old (potential replay attack)
        - Injection pattern detected in user input
    """

    pass


# ==============================================================================
# Service Exceptions
# ==============================================================================
# WHY a dedicated service branch: business logic services (summarization,
# issue detection, reminders, Notion sync) each have unique failure modes
# and recovery strategies.  Dedicated exceptions let the orchestrator
# provide contextual error messages to the user (e.g., "Summarization is
# temporarily unavailable" vs. "Notion sync failed").
# ==============================================================================


class ServiceError(SlackBotError):
    """
    Base exception for business logic service failures.

    WHY a separate branch: service errors are typically non-fatal to the
    overall conversation -- if summarization fails, the bot can still
    answer other questions.  A dedicated branch lets the orchestrator
    continue the conversation while reporting the specific service failure.
    """

    pass


class SummarizationError(ServiceError):
    """
    Raised when the message summarization service fails.

    WHY a dedicated class: summarization involves an LLM call that may
    fail due to token limits or API outages.  The caller can fall back to
    a simpler extraction strategy (e.g., return the raw messages).
    """

    pass


class IssueDetectionError(ServiceError):
    """
    Raised when the automated issue detection service fails.

    WHY a dedicated class: issue detection runs in the background.  A
    failure should not block the user's current request; instead, it
    should be logged and retried on the next scheduling cycle.
    """

    pass


class ReminderError(ServiceError):
    """
    Raised when reminder scheduling or delivery fails.

    WHY a dedicated class: reminder failures may need to be surfaced to the
    user who set the reminder, so they know it will not fire as expected.
    """

    pass


class NotionIntegrationError(ServiceError):
    """
    Raised when synchronization with the Notion API fails.

    WHY a dedicated class: Notion integration is optional.  If it fails,
    the bot should continue operating normally and log the failure for
    later reconciliation rather than blocking the user.
    """

    pass


# ==============================================================================
# Utility Functions
# ==============================================================================
# WHY a centralized handler: every Slack listener and middleware needs to
# convert exceptions into user-friendly responses.  Duplicating the
# "log internally, reply externally" pattern in each handler is error-prone
# (someone will forget to sanitize the message).  Centralizing it here
# guarantees that internal details never leak to the user.
# ==============================================================================


def handle_exception(
    exception: Exception, logger: Any, user_friendly_message: str = "An error occurred"
) -> str:
    """
    Log the full exception internally and return a sanitized user-facing message.

    HOW it works:
        1. Calls logger.exception() which emits the message, exception type,
           and full traceback to the configured log handlers.
        2. If the exception is a SlackBotError, returns its `.message` (which
           is designed to be user-safe by convention).
        3. For all other (unexpected) exceptions, returns the generic
           user_friendly_message to avoid leaking internal implementation
           details.

    WHY it is implemented this way:
        - logger.exception() captures the traceback automatically, so
          developers get full diagnostic detail in the logs.
        - Returning exc.message for SlackBotError subclasses works because
          the convention in this project is that .message is always safe for
          end users (no stack traces, no file paths, no SQL).
        - The generic fallback ensures that unexpected exceptions (e.g., a
          bug producing a KeyError) never expose internal state to the Slack
          channel, which would be both confusing and a security risk.

    Args:
        exception: The exception instance to handle.
        logger: A logging.Logger (or compatible) instance for internal logging.
        user_friendly_message: The message returned for non-SlackBotError
                               exceptions.  Defaults to a safe generic string.

    Returns:
        A string safe to display in a Slack message.
    """
    # WHY logger.exception (not logger.error): .exception() automatically
    # includes the traceback, which is essential for post-mortem debugging.
    logger.exception(f"Exception occurred: {exception}")

    # WHY isinstance check: SlackBotError.message is curated to be user-safe
    # by convention.  Generic exceptions may contain file paths, SQL queries,
    # or other sensitive internals that must not reach the Slack channel.
    if isinstance(exception, SlackBotError):
        return exception.message
    else:
        return user_friendly_message
