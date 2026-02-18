"""
Application Entry Point -- Slack Bot Assistant
================================================

WHY THIS FILE IS REQUIRED:
    Every Python application needs a single, well-defined entry point that
    bootstraps the runtime, wires up dependencies, and starts the event loop.
    Without this file:
      - There would be no way to start the bot from the command line
        (`python -m src.main` or `python src/main.py`).
      - Logging would not be configured before the first log message, causing
        early log output to be lost or mis-formatted.
      - There would be no graceful shutdown handling -- killing the process
        with Ctrl+C or SIGTERM would leave open WebSocket connections and
        unflushed log buffers.
      - The import order (logging first, then settings, then app) would not
        be enforced, risking circular imports or missing configuration.

PROGRAM LOGIC:
    1. PATH SETUP: `sys.path.insert(0, ...)` adds the project root to
       Python's module search path so that imports like `from config.settings`
       and `from src.utils.logger` work regardless of the current working
       directory.  This is necessary because Python only adds the script's
       own directory to sys.path, not the project root.

    2. LOGGING INITIALIZATION: `setup_logging()` is called BEFORE any other
       module is imported (besides stdlib and the logger itself).  This
       ensures that every subsequent `get_logger(__name__)` call in other
       modules picks up the configured log level and format.

    3. SIGNAL REGISTRATION: `handle_shutdown()` is bound to SIGINT (Ctrl+C)
       and SIGTERM (process manager kill).  On Windows, SIGTERM is not
       supported, so it is conditionally registered only on Unix.

    4. ASYNC MAIN FUNCTION:
       a. Logs a startup banner with environment and log level for diagnostics.
       b. Imports `create_app` from src/app.py (lazy import -- see WHY below).
       c. Creates the Slack Bolt AsyncApp via the factory function.
       d. Creates an AsyncSocketModeHandler and starts the WebSocket connection.
       e. Awaits an asyncio.Event that never fires -- this keeps the event
          loop alive until an external signal (Ctrl+C, SIGTERM) interrupts it.
       f. On KeyboardInterrupt or fatal exception, logs the event and exits.
       g. The `finally` block ensures a "bot stopped" log line is always
          emitted, which is useful for confirming shutdown in log aggregators.

    5. __main__ GUARD: The `if __name__ == "__main__"` block registers signal
       handlers and then calls `asyncio.run(main())` to start the event loop.
       This guard prevents the bot from auto-starting when the module is
       imported (e.g., during testing).

WHY THIS APPROACH:
    - LAZY IMPORT OF create_app: The `from src.app import create_app` is
      inside main() rather than at the top of the file.  This is intentional:
      create_app triggers a cascade of imports (listeners, middleware, agent
      orchestrator, memory, RAG) that all expect logging to be configured.
      By deferring the import until after setup_logging(), we guarantee the
      logging infrastructure is ready before any module emits its first log.
    - asyncio.run() FOR THE EVENT LOOP: This is the recommended way to start
      an async program in Python 3.7+.  It creates a new event loop, runs the
      coroutine, and tears down the loop cleanly on exit.  Alternatives like
      `loop.run_forever()` require more manual cleanup.
    - asyncio.Event().wait() AS A KEEP-ALIVE: After starting the Socket Mode
      handler (which runs in a background task), the main coroutine needs to
      stay alive.  Awaiting a never-set Event is a clean, cancellation-friendly
      way to block indefinitely without busy-waiting or sleep loops.
    - DOUBLE KeyboardInterrupt HANDLING: KeyboardInterrupt is caught both in
      main() and in the __main__ block.  The inner catch logs the event; the
      outer catch ensures the process exits cleanly even if the inner catch
      itself raises (e.g., if logging is broken).
    - sys.exit(1) ON FATAL ERROR: If the bot cannot start (e.g., invalid
      tokens, Slack API unreachable), the process exits with code 1 so that
      process managers (systemd, Docker, Kubernetes) know to restart it.

RELATIONSHIP TO OTHER FILES:
    - config/settings.py (DEPENDENCY):
        Provides `settings.environment`, `settings.log_level`, and
        `settings.slack_app_token` used during startup.
    - src/utils/logger.py (DEPENDENCY):
        Provides `setup_logging()` (called first) and `get_logger()`.
    - src/app.py (DEPENDENCY):
        Provides `create_app()`, the factory function that builds the
        fully-configured Slack Bolt application with middleware and listeners.
    - src/slack/middleware/*.py (INDIRECT):
        Middleware modules are imported and registered inside create_app().
    - src/slack/listeners/*.py (INDIRECT):
        Listener modules are imported and registered inside create_app().
    - slack_bolt.adapter.socket_mode (DEPENDENCY):
        Provides AsyncSocketModeHandler for the WebSocket-based connection
        to Slack's servers.
"""

import asyncio
import signal
import sys
from pathlib import Path

# WHY sys.path.insert: When this file is run directly (`python src/main.py`),
# Python adds `src/` to sys.path but NOT the project root.  Without this line,
# `from config.settings import settings` would fail with ModuleNotFoundError
# because `config/` is a sibling of `src/`, not a child.  Inserting the project
# root (Path(__file__).parent.parent) ensures both `config` and `src` are
# importable as top-level packages.
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.utils.logger import setup_logging, get_logger

# WHY setup_logging() is called HERE (before any other application imports):
# Logging must be configured before any module calls get_logger().  If a module
# is imported before setup_logging(), its logger will use Python's default
# config (WARNING level, no formatting), and reconfiguring later will NOT
# retroactively fix loggers that were already created in some Python versions.
setup_logging()
logger = get_logger(__name__)


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    # WHY log before sys.exit: This line proves (in the logs) that the shutdown
    # was intentional (signal received) rather than a crash.  Without it,
    # operators investigating a restart would have to guess whether it was
    # planned or unexpected.
    logger.info("Shutdown signal received, cleaning up...")
    sys.exit(0)


async def main() -> None:
    """
    Main async entry point.

    Initializes the Slack bot and starts Socket Mode.
    """
    try:
        # WHY the banner: When tailing logs during development or investigating
        # incidents in production, a clear startup banner makes it easy to find
        # where a new process began.  Including environment and log level
        # immediately answers "which config is this instance running?"
        logger.info("=" * 60)
        logger.info("Starting Slack Bot Assistant")
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Log Level: {settings.log_level}")
        logger.info("=" * 60)

        # WHY lazy import: create_app() triggers the import of every middleware,
        # listener, and service module.  Deferring this import until after
        # setup_logging() guarantees that all those modules get properly
        # configured loggers.  It also means a syntax error in a listener won't
        # prevent the logger from recording the failure.
        from src.app import create_app

        # WHY factory function (not a global app object): The factory pattern
        # allows tests to create isolated app instances without side effects
        # from previous test runs.  It also makes the initialization sequence
        # explicit and debuggable.
        logger.info("Creating Slack app...")
        app = create_app()

        # WHY Socket Mode (not HTTP): Socket Mode establishes an outbound
        # WebSocket connection to Slack's servers.  This means the bot works
        # behind NAT, firewalls, and localhost -- no public URL or ngrok
        # required.  In production, HTTP mode would be used instead for better
        # scalability and observability.
        logger.info("Starting in Socket Mode...")
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        handler = AsyncSocketModeHandler(app=app, app_token=settings.slack_app_token)

        # WHY start_async() (not start()): start_async() integrates with the
        # existing asyncio event loop rather than creating its own.  This is
        # necessary because we are already inside an async function managed
        # by asyncio.run().
        await handler.start_async()
        logger.info("[OK] Socket Mode handler started")

        # WHY asyncio.Event().wait(): After the Socket Mode handler starts
        # processing events in the background, the main coroutine needs to
        # block forever.  asyncio.Event().wait() is the idiomatic way to do
        # this -- it yields control to the event loop without consuming CPU,
        # and it responds cleanly to cancellation (unlike time.sleep or a
        # busy loop).
        logger.info("Slack bot is running! Press Ctrl+C to stop.")
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        # WHY catch KeyboardInterrupt inside main: asyncio.run() translates
        # Ctrl+C into a KeyboardInterrupt inside the running coroutine.
        # Catching it here allows us to log a clean shutdown message.
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        # WHY logger.exception (not logger.error): Includes the full traceback,
        # which is essential for diagnosing startup failures (bad tokens,
        # network issues, import errors).
        logger.exception(f"Fatal error during startup: {e}")
        # WHY sys.exit(1): A non-zero exit code tells process managers (Docker,
        # systemd, Kubernetes) that the process failed and should be restarted
        # according to the restart policy.
        sys.exit(1)
    finally:
        # WHY finally: This block runs whether the bot stopped due to Ctrl+C,
        # a fatal error, or any other reason.  It guarantees the "bot stopped"
        # log line appears, which is invaluable for confirming shutdown in log
        # aggregation systems.
        logger.info("Slack bot stopped")


if __name__ == "__main__":
    # WHY register signal handlers HERE (not inside main): Signal handlers must
    # be registered in the main thread.  asyncio.run() creates its own thread
    # for the event loop on some platforms, so registering inside main() could
    # fail with "can only register signal handlers in main thread."
    signal.signal(signal.SIGINT, handle_shutdown)
    # WHY conditional SIGTERM: Windows does not support SIGTERM.  Attempting to
    # register a handler for it raises ValueError on Windows.  The platform
    # check avoids this crash while still enabling graceful shutdown on Linux
    # and macOS where SIGTERM is the standard process-kill signal.
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handle_shutdown)

    # WHY asyncio.run(): This is Python 3.7+'s recommended entry point for
    # async programs.  It creates a fresh event loop, runs the coroutine to
    # completion, and then closes the loop and cancels any remaining tasks.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # WHY a second KeyboardInterrupt catch: If the interrupt arrives
        # during asyncio.run()'s cleanup phase (after main() has exited but
        # before the loop is closed), it would produce an ugly traceback.
        # This outer catch ensures a clean exit in all cases.
        logger.info("Shutdown complete")
