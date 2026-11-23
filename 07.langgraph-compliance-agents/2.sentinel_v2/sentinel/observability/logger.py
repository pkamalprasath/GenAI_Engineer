"""
Structured JSON logger for all SENTINEL modules (Phase 4).

Uses structlog internally for JSON serialization + stdlib integration.
Exports three functions with unchanged signatures for backward compatibility.

Every log entry includes correlation_id and tenant_id for filtering.
PII is NEVER logged — only counts, case IDs, node IDs, and event types.
All output goes to stdout — container-friendly, works with any log aggregator.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import structlog


def get_logger(module_name: str) -> logging.Logger:
    """Return a standard logger for the given module name."""
    return logging.getLogger(module_name)


def log_agent_event(
    logger: logging.Logger,
    correlation_id: str,
    tenant_id: str,
    agent: str,
    event: str,
    level: str = "INFO",
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Emit a structured agent event log entry via structlog.
    details dict must not contain PII — caller's responsibility.
    """
    slog = structlog.get_logger(logger.name)
    log_fn = getattr(slog, level.lower(), slog.info)
    log_fn(
        event=event,
        agent=agent,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        **(details or {}),
    )


def log_error(
    logger: logging.Logger,
    correlation_id: str,
    tenant_id: str,
    agent: str,
    error_type: str,
    error_message: str,
    recoverable: bool = True,
) -> None:
    """
    Emit a structured error entry via structlog.
    error_message must not contain PII — truncate or sanitize before passing.
    recoverable=False signals a fatal error that stops the investigation.
    """
    slog = structlog.get_logger(logger.name)
    slog.error(
        event="error",
        agent=agent,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        error_type=error_type,
        error_message=str(error_message)[:500],
        recoverable=recoverable,
    )
