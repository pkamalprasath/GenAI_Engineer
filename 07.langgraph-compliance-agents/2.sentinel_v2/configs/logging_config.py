"""
Structured JSON logging with structlog (Phase 4).

All logs are emitted as JSON to stdout, compatible with:
  - Docker log drivers (json-file, splunk, etc.)
  - Log aggregators (ELK, Datadog, CloudWatch)
  - Machine parsing for monitoring/alerting

Stdlib loggers still work — they're wrapped by structlog's stdlib integration.
"""
import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """
    Configure structlog for JSON logging + stdlib integration.
    Container-friendly: all output to stdout, parseable by aggregators.
    """
    # Stdlib configuration (for third-party libraries that use logging module)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "anthropic", "openai", "langfuse"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # structlog configuration: all events → JSON to stdout
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),  # Emit JSON
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
