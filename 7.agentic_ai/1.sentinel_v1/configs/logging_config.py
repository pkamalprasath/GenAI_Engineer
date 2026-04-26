"""Structured JSON logging configuration for all sentinel modules."""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """
    Sets up structured JSON-compatible logging.
    All handlers write to stdout — container-friendly, queryable by log aggregators.
    """
    fmt = (
        '{"time":"%(asctime)s","level":"%(levelname)s",'
        '"module":"%(name)s","message":"%(message)s"}'
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "anthropic", "openai", "langfuse"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
