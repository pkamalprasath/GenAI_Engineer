"""
Structured JSON logger for all SENTINEL modules.

Every log entry includes correlation_id and tenant_id for filtering.
PII is NEVER logged — only counts, case IDs, node IDs, and event types.
All output goes to stdout — container-friendly, works with any log aggregator.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional


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
    Emit a structured agent event log entry.
    details dict must not contain PII — caller's responsibility.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "agent": agent,
        "event": event,
        "level": level,
        "details": details or {},
    }
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(json.dumps(entry))


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
    Emit a structured error entry.
    error_message must not contain PII — truncate or sanitize before passing.
    recoverable=False signals a fatal error that stops the investigation.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "agent": agent,
        "event": "error",
        "level": "ERROR",
        "error_type": error_type,
        # Truncate to prevent log explosion from large exception traces
        "error_message": str(error_message)[:500],
        "recoverable": recoverable,
    }
    logger.error(json.dumps(entry))
