"""
Centralized Logging Setup with YAML Configuration
====================================================

WHY THIS FILE IS REQUIRED:
    Without a centralized logging module, every file in the project would need to
    independently configure its own logging -- leading to inconsistent log formats,
    duplicated configuration code, and no single place to control log verbosity.
    This file provides a single entry point (setup_logging) that reads a YAML
    configuration file once at startup and configures Python's built-in logging
    framework for the entire process. If this file were removed, every module
    would fall back to Python's default logging (WARNING-level only, no file
    output, no structured format), making production debugging nearly impossible.

PROGRAM LOGIC:
    1. setup_logging() is called once at application startup (from src/main.py
       or src/app.py) to bootstrap the logging infrastructure.
    2. It resolves the path to config/logging.yaml relative to the project root.
    3. It ensures the "logs/" directory exists so file-based handlers do not fail.
    4. It attempts to load and parse the YAML configuration via yaml.safe_load().
    5. On success, it passes the parsed dict to logging.config.dictConfig() which
       configures handlers, formatters, filters, and per-logger levels.
    6. On failure (missing file, parse error), it falls back to basicConfig() so
       that the application can still emit logs rather than crashing silently.
    7. get_logger(name) is a thin convenience wrapper around logging.getLogger()
       that other modules call to obtain a logger scoped to their __name__.
    8. log_function_call() is a decorator factory that instruments any function
       (sync or async) with entry/exit/exception logging.
    9. Module-level logger instances (app_logger, agent_logger, etc.) are
       pre-created so commonly used loggers can be imported directly.

WHY THIS APPROACH:
    - YAML over code-based config: YAML is human-readable and can be changed
      by operations staff without touching Python code. It also cleanly
      separates configuration concerns from logic.
    - dictConfig over fileConfig: dictConfig supports incremental configuration
      and richer handler definitions (e.g., RotatingFileHandler with kwargs).
    - Fallback to basicConfig: Guarantees the application always has *some*
      logging even when the YAML file is absent (e.g., in CI or fresh clones).
    - Pre-created module loggers: Avoids the boilerplate of calling get_logger()
      in every file for the most commonly used logger namespaces.
    - Decorator for function-call tracing: Cross-cutting concern implemented
      once rather than duplicated in every function body.

RELATIONSHIP TO OTHER FILES:
    USED BY (imports get_logger / module loggers):
        - Nearly every module in the project (29 files import from here),
          including src/agent/orchestrator.py, src/memory/manager.py,
          src/rag/store.py, src/slack/middleware/*.py, src/services/*.py,
          src/mcp_servers/*.py, and src/utils/security.py.
    USES:
        - config/logging.yaml  -- external YAML configuration file
        - PyYAML (yaml)        -- third-party library for YAML parsing
        - Python stdlib: logging, logging.config, asyncio, functools, pathlib
    CALLED AT STARTUP BY:
        - src/main.py or src/app.py (setup_logging is invoked before any
          other application logic)
"""

import asyncio
import functools
import logging
import logging.config
from pathlib import Path
from typing import Optional
import yaml


def setup_logging(config_path: Optional[str] = None, default_level: int = logging.INFO) -> None:
    """
    Bootstrap the logging subsystem from a YAML configuration file.

    HOW it works:
        Resolves the config file path (defaulting to config/logging.yaml at
        the project root), ensures the logs/ directory exists for file handlers,
        then delegates to logging.config.dictConfig() which wires up all
        handlers, formatters, and per-logger levels in a single call.

    WHY it is implemented this way:
        - Called once at startup so the cost of file I/O and YAML parsing is
          paid only once rather than on every getLogger() call.
        - The three-tier try/except (FileNotFoundError -> generic Exception)
          ensures the application degrades gracefully: missing config gets a
          basic console logger; a malformed YAML still results in *some*
          logging rather than an unhandled crash.
        - Printing status to stdout (not via logging) is intentional because
          the logging system is not yet configured when these lines execute.

    Args:
        config_path: Path to logging configuration YAML file.  When None,
                     defaults to config/logging.yaml relative to project root.
        default_level: Fallback logging level used only when the YAML file
                       cannot be loaded.
    """
    if config_path is None:
        # WHY three .parent calls: __file__ is src/utils/logger.py, so
        # .parent -> src/utils, .parent -> src, .parent -> project root.
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"

    # WHY create logs/ eagerly: file-based handlers declared in the YAML
    # (e.g., RotatingFileHandler) will fail at startup if the directory
    # does not exist.  exist_ok=True makes this idempotent.
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    try:
        # WHY safe_load: yaml.safe_load prevents arbitrary Python object
        # instantiation from the YAML file, avoiding a code-execution
        # vulnerability that yaml.load (without Loader) would introduce.
        with open(config_path, "r") as f:
            config = yaml.safe_load(f.read())
            # WHY dictConfig: it is the modern, recommended way to configure
            # logging in Python and supports the full range of handler types.
            logging.config.dictConfig(config)
            print(f"[OK] Logging configured from {config_path}")
    except FileNotFoundError:
        # WHY fallback to basicConfig: a missing config file is common in
        # CI pipelines, Docker builds, or first-time clones.  Rather than
        # crashing, we provide a minimal console-only configuration so
        # developers still see output.
        logging.basicConfig(
            level=default_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        print(f"[WARN] Logging config not found at {config_path}, using basic configuration")
    except Exception as e:
        # WHY catch broad Exception: a corrupt YAML, permission error, or
        # dictConfig schema violation should not bring down the whole app.
        # We log the error itself to stderr via basicConfig and move on.
        logging.basicConfig(level=default_level)
        print(f"[ERROR] Error loading logging configuration: {e}")


def get_logger(name: str) -> logging.Logger:
    """
    Obtain a module-scoped logger instance by name.

    HOW it works:
        A thin wrapper around logging.getLogger(name).  The returned logger
        inherits the configuration established by setup_logging() -- handlers,
        formatters, and level thresholds are all determined by the YAML config
        (or the basicConfig fallback).

    WHY it is implemented this way:
        - Provides a single import path (from src.utils.logger import get_logger)
          so all modules obtain loggers the same way.
        - Using __name__ as the logger name creates a dot-separated hierarchy
          (e.g., "src.agent.orchestrator") that mirrors the package structure.
          This hierarchy lets the YAML config set different levels per subtree
          (e.g., DEBUG for "src.agent" but WARNING for "src.slack").
        - If we ever need to add global logger customizations (extra filters,
          structured JSON formatting), we can do it here in one place.

    Args:
        name: Logger name, conventionally the calling module's __name__.

    Returns:
        A logging.Logger instance configured according to the active
        logging configuration.

    Usage::

        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Server started on port %d", port)
    """
    return logging.getLogger(name)


def log_function_call(logger: logging.Logger, level: int = logging.DEBUG):
    """
    Decorator factory that instruments a function with entry/exit/exception logging.

    HOW it works:
        Returns a decorator that wraps the target function.  Before the call
        it logs the function name and stringified arguments; after a successful
        return it logs the result; on exception it logs the full traceback via
        logger.exception() and then re-raises so normal error handling is
        unaffected.  It detects async coroutines at decoration time and wraps
        them with an async-compatible wrapper to support both sync and async
        code paths.

    WHY it is implemented this way:
        - Decorator pattern keeps logging concerns out of business logic,
          adhering to the Single Responsibility Principle.
        - Detecting asyncio.iscoroutinefunction at decoration time (not call
          time) avoids the overhead of runtime introspection on every
          invocation.
        - functools.wraps preserves the original function's __name__,
          __doc__, and signature so that introspection tools (help(), IDE
          tooltips, Sphinx) still work correctly.
        - The level parameter defaults to DEBUG because function-call tracing
          is verbose and typically only enabled during development.
        - Re-raising the exception after logging ensures that callers'
          error-handling logic is not silently swallowed.

    Args:
        logger: Logger instance to emit log records through.
        level:  Logging level for the entry/exit messages (default: DEBUG).

    Usage::

        logger = get_logger(__name__)

        @log_function_call(logger)
        def compute(x, y):
            return x + y

        @log_function_call(logger, level=logging.INFO)
        async def fetch_data(url):
            ...
    """

    def decorator(func):
        # WHY check iscoroutinefunction here: we need two distinct wrappers
        # because 'await' is a syntax error inside a non-async function.
        # Checking once at decoration time is cheaper than checking on every call.
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # WHY repr each arg individually: keeps the log line readable
                # even when some arguments are large objects.
                args_repr = [repr(a) for a in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                signature = ", ".join(args_repr + kwargs_repr)
                logger.log(level, f"Calling {func.__name__}({signature})")
                try:
                    result = await func(*args, **kwargs)
                    logger.log(level, f"{func.__name__} returned {result!r}")
                    return result
                except Exception as e:
                    # WHY logger.exception: it automatically attaches the
                    # full traceback to the log record, unlike logger.error.
                    logger.exception(f"{func.__name__} raised {e.__class__.__name__}: {e}")
                    # WHY re-raise: the decorator must be transparent --
                    # callers expect to handle the exception themselves.
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                args_repr = [repr(a) for a in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                signature = ", ".join(args_repr + kwargs_repr)
                logger.log(level, f"Calling {func.__name__}({signature})")
                try:
                    result = func(*args, **kwargs)
                    logger.log(level, f"{func.__name__} returned {result!r}")
                    return result
                except Exception as e:
                    logger.exception(f"{func.__name__} raised {e.__class__.__name__}: {e}")
                    raise
            return wrapper

    return decorator


# ==============================================================================
# Module-level convenience loggers
# ==============================================================================
# WHY pre-create these: the five subsystems below are imported so frequently
# that providing ready-made logger instances eliminates repetitive boilerplate.
# Each logger name matches a top-level package under src/, which lets the YAML
# config control verbosity per subsystem independently (e.g., set "src.rag" to
# DEBUG while keeping "src.slack" at INFO).
# ==============================================================================

# Application-wide root logger for cross-cutting messages
app_logger = logging.getLogger("src")

# WHY one logger per subsystem: isolating log output by component makes it
# easy to filter logs during debugging (e.g., grep for "src.agent") and to
# route different subsystems to different handlers in the YAML config.
agent_logger = logging.getLogger("src.agent")
memory_logger = logging.getLogger("src.memory")
rag_logger = logging.getLogger("src.rag")
slack_logger = logging.getLogger("src.slack")
mcp_logger = logging.getLogger("src.mcp_servers")
