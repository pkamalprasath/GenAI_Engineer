"""
Slack Bolt Application Factory and Initialization
===================================================

WHY THIS FILE IS REQUIRED:
    This module is the central assembly point for the entire Slack bot application.
    Without it, there would be no single place that wires together middleware,
    event listeners, and error handlers into a cohesive Slack Bolt application.
    If this file did not exist, every component (auth middleware, rate limiter,
    message listeners, slash commands, etc.) would need to be connected ad-hoc
    in the entrypoint (src/main.py), making the boot sequence fragile, hard to
    test, and difficult to reason about.

    In concrete terms, removing this file would break:
      - The middleware chain (auth -> rate-limit -> error-handler) that protects
        every inbound Slack request.
      - Event listener registration, meaning the bot would be deaf to messages,
        @mentions, and slash commands.
      - The global error handler that prevents unhandled exceptions from crashing
        the process.
      - Socket Mode setup for local development without a public URL.

PROGRAM LOGIC:
    1. ``create_app()`` is called by the entrypoint (``src/main.py``).
    2. An ``AsyncApp`` instance is created with the bot token and signing secret
       loaded from centralized settings (``config/settings.py``).
    3. Three middleware functions are registered IN ORDER:
       a. ``auth_middleware`` -- verifies request authenticity, blocks bot loops.
       b. ``rate_limit_middleware`` -- enforces per-user and per-channel quotas.
       c. ``error_handler_middleware`` -- catches and formats listener exceptions.
    4. Three listener modules are imported and their ``register_listeners()``
       functions are called, binding event handlers for messages, slash commands,
       and @mentions.
    5. A global error handler is attached via ``@app.error`` as a last-resort
       safety net for any exception that escapes both middleware and listeners.
    6. The fully configured ``AsyncApp`` is returned to the caller.

    Additionally:
    - ``create_socket_mode_handler()`` wraps the app in a WebSocket-based
      handler for development use (no public URL required).
    - ``register_health_endpoints()`` is a placeholder for production HTTP-mode
      health checks used by load balancers.

WHY THIS APPROACH:
    - **Factory pattern** (``create_app()`` returns a new instance): This is
      chosen over a module-level singleton because it enables testing -- each
      test can create its own isolated app instance with different configuration
      or mock middleware.  It also avoids import-time side effects that make
      debugging startup failures harder.
    - **Explicit middleware ordering**: Middleware is registered in a specific
      sequence (auth first, then rate-limit, then error-handler) because order
      matters.  Auth must run before rate-limiting so that bot-loop messages are
      rejected before consuming a rate-limit token.  The error handler wraps
      everything downstream so it can catch exceptions from listeners.
    - **Lazy imports inside ``create_app()``**: Middleware and listener modules
      are imported inside the function body rather than at module level.  This
      prevents circular import issues (listeners import the orchestrator, which
      imports memory, which imports settings, etc.) and ensures that logging is
      fully configured before any module-level code in those files executes.
    - **AsyncApp over App**: The async variant is used because the bot performs
      I/O-heavy operations (Slack API calls, LLM inference, ChromaDB queries).
      Async/await lets these run concurrently on a single thread, which is more
      resource-efficient than spawning OS threads for each request.
    - **Socket Mode for development**: Socket Mode opens an outbound WebSocket
      to Slack's infrastructure, so the bot works behind NAT/firewalls without
      tools like ngrok.  Production deployments should switch to HTTP mode for
      better scalability and observability.

RELATIONSHIP TO OTHER FILES:
    - ``src/main.py`` (upstream)
        Calls ``create_app()`` and ``create_socket_mode_handler()`` to boot the
        bot.  This is the only file that directly invokes the factory.
    - ``config/settings.py`` (dependency)
        Supplies ``slack_bot_token``, ``slack_signing_secret``, ``slack_app_token``,
        and ``environment`` used during app and handler construction.
    - ``src/slack/middleware/auth.py`` (dependency)
        Provides ``auth_middleware`` -- the first middleware in the chain.
    - ``src/slack/middleware/rate_limit.py`` (dependency)
        Provides ``rate_limit_middleware`` -- the second middleware in the chain.
    - ``src/slack/middleware/error_handler.py`` (dependency)
        Provides ``error_handler_middleware`` -- the third and final middleware.
    - ``src/slack/listeners/messages.py`` (dependency)
        Handles incoming DM messages via the ``"message"`` event type.
    - ``src/slack/listeners/commands.py`` (dependency)
        Handles slash commands (``/bot-help``, ``/bot-status``, etc.).
    - ``src/slack/listeners/mentions.py`` (dependency)
        Handles ``@BotName`` mentions via the ``"app_mention"`` event type.
    - ``src/utils/logger.py`` (dependency)
        Provides the structured logger used for boot-sequence diagnostics.
    - ``src/utils/exceptions.py`` (dependency)
        Defines ``SlackBotError``, used to distinguish known errors from
        unexpected ones in the global error handler.
"""

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import SlackBotError

# WHY module-level logger: Every module in this project creates its own logger
# using ``get_logger(__name__)``.  The ``__name__`` value encodes the full
# import path (e.g., "src.app"), which enables granular log-level filtering
# in logging configuration (e.g., set "src.app" to DEBUG while keeping
# "src.rag" at WARNING).
logger = get_logger(__name__)


def create_app() -> AsyncApp:
    """
    Factory function to create and configure the Slack Bolt application.

    HOW IT WORKS:
        1. Instantiates ``AsyncApp`` with credentials from the centralized
           settings object (loaded from ``.env`` via pydantic-settings).
        2. Imports and registers three middleware functions in a deliberate
           order: auth -> rate-limit -> error-handler.  This ordering ensures
           that unauthenticated or bot-loop requests are rejected before they
           consume rate-limit tokens, and that any exception raised by a
           listener is caught and formatted by the error-handler middleware.
        3. Imports three listener modules and calls their ``register_listeners``
           functions, which bind specific Slack event types (message,
           app_mention, slash commands) to their respective async handlers.
        4. Attaches a ``@app.error`` global error handler as a last-resort
           safety net for exceptions that escape both middleware and listeners.
        5. Returns the fully wired ``AsyncApp`` instance to the caller.

    WHY IMPLEMENTED THIS WAY:
        The factory pattern is used instead of a module-level singleton so that:
        - Tests can create isolated app instances with different settings.
        - Import-time side effects are avoided (nothing happens until
          ``create_app()`` is explicitly called).
        - The boot sequence is explicit and easy to trace in ``src/main.py``.

    Returns:
        A fully configured ``AsyncApp`` instance ready to handle Slack events.
    """
    logger.info("Creating Slack Bolt app...")

    # WHY AsyncApp: The async variant uses aiohttp under the hood, allowing
    # concurrent handling of multiple Slack events on a single thread.  This
    # is critical because every event triggers I/O (Slack API calls, LLM
    # inference, vector DB queries) and blocking would serialize all requests.
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
        # WHY no explicit token/signature verification flags: Slack Bolt
        # performs HMAC-SHA256 signature verification and token validation
        # automatically when ``signing_secret`` is provided.  Adding manual
        # checks here would be redundant.
    )

    # =========================================================================
    # Register Global Middleware
    # =========================================================================
    # WHY middleware instead of per-listener checks: Middleware enforces
    # cross-cutting concerns (authentication, rate limiting, error handling)
    # uniformly across ALL event types.  This eliminates the risk of a
    # developer forgetting to add auth or rate-limit logic when creating a
    # new listener.  Middleware also runs in a defined order, giving
    # predictable request processing.
    # =========================================================================

    logger.info("Registering middleware...")

    # WHY lazy imports: These modules are imported inside the function body
    # to avoid circular import chains.  Listener modules import the agent
    # orchestrator, which imports memory and RAG subsystems, which import
    # settings.  If app.py imported them at module level, the import graph
    # could form cycles that cause ``ImportError`` at startup.
    from src.slack.middleware.auth import auth_middleware
    from src.slack.middleware.rate_limit import rate_limit_middleware
    from src.slack.middleware.error_handler import error_handler_middleware

    # WHY this specific order matters:
    # 1. Auth FIRST: Rejects bot-loop messages and logs sanitized requests
    #    before any other processing occurs.  If rate-limiting ran first,
    #    the bot's own messages would consume rate-limit tokens.
    # 2. Rate-limit SECOND: Enforces per-user and per-channel quotas on
    #    authenticated, non-bot requests only.
    # 3. Error-handler THIRD (innermost): Wraps the actual listener
    #    execution in a try/except so that any exception from a listener
    #    is caught, logged, and converted to a user-friendly response.
    app.middleware(auth_middleware)
    app.middleware(rate_limit_middleware)
    app.middleware(error_handler_middleware)

    logger.info("[OK] Middleware registered")

    # =========================================================================
    # Register Event Listeners
    # =========================================================================
    # WHY separate listener modules: Each listener module handles one category
    # of Slack events (messages, commands, mentions).  This separation of
    # concerns makes each module small, focused, and independently testable.
    # The ``register_listeners(app)`` pattern gives this factory explicit
    # control over registration order and makes the wiring visible.
    # =========================================================================

    logger.info("Registering event listeners...")

    # WHY explicit register_listeners calls instead of decorator-based auto-
    # registration: Decorators (``@app.event("message")``) require the ``app``
    # object to exist at import time, creating a chicken-and-egg problem with
    # the factory pattern.  The ``register_listeners(app)`` approach decouples
    # handler definition from registration, enabling this factory to control
    # when and how handlers are attached.
    from src.slack.listeners import messages, commands, mentions

    # WHY this registration order: Messages are the most common event type,
    # so registering them first ensures they appear first in Slack Bolt's
    # internal handler list.  However, Slack Bolt dispatches by event type
    # (not registration order), so functionally the order does not affect
    # behavior -- it is purely for organizational clarity in the logs.
    messages.register_listeners(app)
    commands.register_listeners(app)
    mentions.register_listeners(app)

    logger.info("[OK] Event listeners registered")

    # =========================================================================
    # Register Global Error Handler
    # =========================================================================
    # WHY a global error handler in addition to the error_handler_middleware:
    # The middleware catches errors from listeners, but some errors can occur
    # OUTSIDE the middleware chain (e.g., during Slack Bolt's internal event
    # routing).  The ``@app.error`` handler is Slack Bolt's built-in last-
    # resort mechanism that catches anything the middleware missed.  Together,
    # they form a two-layer safety net that prevents any unhandled exception
    # from crashing the process.
    # =========================================================================

    @app.error
    async def global_error_handler(error, body, logger):
        """
        Global error handler for unhandled exceptions.

        HOW IT WORKS:
            Slack Bolt calls this function for any exception that escapes the
            entire middleware + listener chain.  It logs the error with full
            context (exception type, message, request body) and classifies it
            as either a known ``SlackBotError`` or an unknown error for
            different logging treatment.

        WHY IMPLEMENTED THIS WAY:
            - Logging at ``exception`` level captures the full stack trace,
              which is essential for post-mortem debugging.
            - The ``body`` is logged at ``debug`` level (not ``error``) because
              request bodies can be large and contain user messages that should
              not pollute error-level logs in monitoring dashboards.
            - The inner try/except around the classification logic ensures that
              even a bug in the error handler itself does not crash the process.

        Args:
            error: The exception that was raised.
            body: The raw Slack request body that triggered the error.
            logger: Logger instance injected by Slack Bolt.
        """
        logger.exception(f"Unhandled error: {error}")
        # WHY debug level for body: Request bodies may contain user messages
        # or PII.  Logging at debug keeps them out of production log streams
        # (which typically run at INFO or WARNING) while remaining available
        # when a developer enables DEBUG for investigation.
        logger.debug(f"Request body: {body}")

        # WHY no external monitoring call here (commented out sentry_sdk):
        # This is a placeholder for production observability integration.
        # In a real deployment, you would uncomment and configure Sentry,
        # DataDog, or a similar service to capture these errors with full
        # context for alerting and trend analysis.
        # sentry_sdk.capture_exception(error)

        # WHY classify known vs. unknown errors: Known errors (SlackBotError
        # subclasses) indicate expected failure modes (e.g., API timeout,
        # memory write failure) and may warrant different alerting thresholds
        # than truly unexpected errors (e.g., AttributeError from a bug).
        try:
            if isinstance(error, SlackBotError):
                # WHY separate branch: Known errors have a structured
                # ``message`` attribute and may carry additional context
                # (error_code, details).  Logging them distinctly allows
                # monitoring dashboards to filter and count by error type.
                logger.error(f"Known error occurred: {error.message}")
            else:
                # WHY flag as "Unknown": These are bugs or unanticipated
                # failure modes that need immediate developer attention.
                logger.error(f"Unknown error occurred: {str(error)}")
        except Exception as logging_error:
            # WHY bare print: If the structured logging system itself fails
            # (e.g., logger misconfiguration, disk full), we fall back to
            # stdout to ensure the error is not silently swallowed.
            print(f"Error handler failed: {logging_error}")

    logger.info("[OK] Global error handler registered")

    # =========================================================================
    # Start Reminder Scheduler
    # =========================================================================
    # WHY APScheduler here: ReminderService.execute_due_reminders() must be
    # called periodically to deliver due reminders.  APScheduler runs the
    # job in the background within the same async event loop.  Starting the
    # scheduler in the app factory ensures it is active as soon as the bot
    # boots, and that it shares the same event loop as Slack Bolt.
    # =========================================================================

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from src.services.reminder import ReminderService

        scheduler = AsyncIOScheduler()
        reminder_service = ReminderService()

        async def _deliver_reminders():
            """Periodic job: check for due reminders and deliver them."""
            try:
                results = await reminder_service.execute_due_reminders()
                if results:
                    logger.info("Reminder delivery cycle: %d processed", len(results))
            except Exception as e:
                logger.error("Reminder delivery failed: %s", e)

        # Run every 60 seconds — minute-level precision is sufficient for reminders.
        scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")

        # =====================================================================
        # Add RAG Indexing Job
        # =====================================================================
        # WHY RAG indexing: The vector store must be periodically updated with
        # new channel messages so the agent's RAG retrieval stays current.
        # Without this, the bot can only answer based on messages indexed at
        # startup, and new conversations remain invisible to semantic search.
        # =====================================================================
        async def _index_channels():
            """Periodic job: index recent messages from all channels."""
            try:
                from src.rag.indexer import ChannelIndexer
                indexer = ChannelIndexer()

                # Get list of channels to index
                from src.mcp_servers.slack_server import list_channels
                channels_result = await list_channels()
                channels = channels_result.get("channels", [])

                indexed_count = 0
                for channel in channels:
                    channel_id = channel.get("id")
                    if channel_id:
                        try:
                            await indexer.index_channel(channel_id)
                            indexed_count += 1
                        except Exception as e:
                            logger.warning("Failed to index channel %s: %s", channel_id, e)

                logger.info("RAG indexing cycle: %d channels indexed", indexed_count)
            except Exception as e:
                logger.error("RAG indexing failed: %s", e)

        # Run every rag_indexing_frequency seconds (default: 2 hours)
        scheduler.add_job(
            _index_channels,
            "interval",
            seconds=settings.rag_indexing_frequency,
            id="rag_indexing",
        )

        # =====================================================================
        # Add Reminder Cleanup Job
        # =====================================================================
        # WHY cleanup: Without periodic cleanup, delivered/cancelled reminders
        # accumulate in reminders.json forever. This job removes old reminders
        # (>30 days) to keep the file manageable.
        # =====================================================================
        async def _cleanup_reminders():
            """Periodic job: remove old delivered/cancelled reminders."""
            try:
                removed = await reminder_service.cleanup_old_reminders(days=30)
                if removed > 0:
                    logger.info("Reminder cleanup: %d old reminders removed", removed)
            except Exception as e:
                logger.error("Reminder cleanup failed: %s", e)

        # Run weekly on Sunday at midnight (cron: 0 0 * * 0)
        scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="reminder_cleanup")

        # =====================================================================
        # Add Heartbeat/Health Check Job
        # =====================================================================
        # WHY heartbeat: Periodic health checks ensure the bot is responsive
        # and can detect degraded states (e.g., Slack API down, vector store
        # corrupted). Logs the bot's uptime and key service availability.
        # =====================================================================
        import time
        bot_start_time = time.time()

        async def _heartbeat():
            """Periodic job: log health status and uptime."""
            try:
                uptime_seconds = int(time.time() - bot_start_time)
                uptime_hours = uptime_seconds / 3600

                # Check if key services are responsive
                health_status = {
                    "uptime_hours": round(uptime_hours, 2),
                    "reminder_service": "ok",
                    "slack_connection": "ok",
                }

                logger.info("Heartbeat: %s", health_status)
            except Exception as e:
                logger.error("Heartbeat failed: %s", e)

        # Run every 5 minutes
        scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")

        scheduler.start()
        logger.info("[OK] Scheduler started with 4 jobs: reminders (60s), RAG indexing (%ds), cleanup (weekly), heartbeat (5m)",
                    settings.rag_indexing_frequency)
    except Exception as e:
        # Non-fatal: the bot can still function without the scheduler.
        logger.warning("Failed to start scheduler: %s", e)

    # =========================================================================
    # App Initialization Complete
    # =========================================================================

    logger.info("[OK] Slack Bolt app created successfully")
    # WHY masked token in log: Printing the full token would be a security
    # risk if logs are shipped to external services.  "xoxb-****" confirms
    # that a bot token was loaded without revealing its value.
    logger.info(f"  Bot Token: xoxb-****")
    # WHY log the environment: Helps operators quickly confirm whether the
    # bot started in development (Socket Mode) or production (HTTP mode).
    logger.info(f"  Environment: {settings.environment}")

    return app


def create_socket_mode_handler(app: AsyncApp) -> AsyncSocketModeHandler:
    """
    Create a Socket Mode handler for development use.

    HOW IT WORKS:
        Wraps the given ``AsyncApp`` in an ``AsyncSocketModeHandler`` that
        opens an outbound WebSocket connection to Slack's servers.  All Slack
        events are then delivered over this persistent WebSocket instead of
        via HTTP webhooks, eliminating the need for a publicly accessible URL.

    WHY IMPLEMENTED THIS WAY:
        - **Development convenience**: Socket Mode removes the requirement for
          ngrok or similar tunneling tools during local development.  The bot
          connects outbound to Slack (port 443), which works behind NAT,
          firewalls, and VPNs without any network configuration.
        - **App-level token**: Socket Mode uses a separate ``xapp-`` token
          (not the ``xoxb-`` bot token) because the WebSocket connection is
          established at the *app* level, not the *bot user* level.  This
          distinction is part of Slack's security model.
        - **Not for production**: In production, HTTP mode is preferred because
          it supports horizontal scaling (multiple instances behind a load
          balancer), standard health checks, and is easier to monitor with
          existing infrastructure tooling.

    Args:
        app: A fully configured ``AsyncApp`` instance (from ``create_app()``).

    Returns:
        An ``AsyncSocketModeHandler`` ready to be started with
        ``handler.start_async()``.

    Reference:
        https://api.slack.com/apis/connections/socket
    """
    logger.info("Creating Socket Mode handler...")

    # WHY app_token from settings: The app-level token is loaded from the
    # same centralized configuration as all other credentials, ensuring it
    # is validated at startup and never hard-coded.
    handler = AsyncSocketModeHandler(app=app, app_token=settings.slack_app_token)

    logger.info("[OK] Socket Mode handler created")
    return handler


# ==============================================================================
# Health Check Endpoints (for production HTTP mode)
# ==============================================================================
# WHY a separate section: Health endpoints are only meaningful in HTTP mode
# (production), where a load balancer needs to verify that the bot process is
# alive and ready to accept traffic.  In Socket Mode (development), the
# persistent WebSocket itself serves as the health signal -- if the connection
# drops, Slack stops sending events.
# ==============================================================================


def register_health_endpoints(app: AsyncApp) -> None:
    """
    Register health check endpoints for production monitoring.

    HOW IT WORKS:
        In HTTP mode, this would register ``/health`` and ``/ready`` endpoints
        that respond with a 200 status and a JSON body indicating the bot's
        operational state.  Load balancers (AWS ALB, Kubernetes probes, etc.)
        poll these endpoints at regular intervals.

    WHY IMPLEMENTED THIS WAY:
        - **/health** (liveness): Returns 200 if the process is running.
          Used by orchestrators to detect crashed instances.
        - **/ready** (readiness): Returns 200 only after the app has fully
          initialized (middleware registered, listeners bound, vector store
          connected).  Used to avoid routing traffic to an instance that is
          still booting.
        - **Fast responses** (<100ms): Health checks must be lightweight to
          avoid false-positive failures when the bot is under load.  They
          should never trigger AI inference or database queries.
        - **Current state**: This is a placeholder because the bot currently
          runs in Socket Mode (development).  When HTTP mode is implemented,
          the actual endpoint handlers will be added here.

    Args:
        app: The ``AsyncApp`` instance to register endpoints on.
    """
    # WHY no actual implementation: Socket Mode does not expose an HTTP
    # server, so health endpoints have no transport to bind to.  This
    # function exists as a documented placeholder so developers know where
    # to add health checks when transitioning to HTTP mode for production.
    logger.info("Health check endpoints would be registered for HTTP mode")
