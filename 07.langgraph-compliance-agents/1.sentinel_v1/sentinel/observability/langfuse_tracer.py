"""
LangFuse tracer — extended from engineering-rag pattern (no-op/live toggle).

LangFuse tracks production metrics: p50/p95 latency per agent node,
cost per investigation, token usage per tenant. Business-facing metrics,
not agent debugging (that's LangSmith's role).

The no-op pattern means: if LANGFUSE_PUBLIC_KEY is not set, all trace
calls are silent no-ops — zero overhead, zero errors, zero config required.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

# Lazy LangFuse client — only initialized if keys are present
_langfuse: Optional[Any] = None
_initialized = False


def _get_client() -> Optional[Any]:
    """Return LangFuse client, or None if not configured (no-op mode)."""
    global _langfuse, _initialized
    if _initialized:
        return _langfuse
    _initialized = True

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info('{"event":"langfuse_disabled","reason":"keys_not_set"}')
        return None

    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info('{"event":"langfuse_enabled","host":"%s"}', settings.langfuse_host)
    except ImportError:
        logger.warning('{"event":"langfuse_import_failed","action":"no_op_mode"}')

    return _langfuse


@contextmanager
def trace_agent_node(
    agent_name: str,
    investigation_id: str,
    tenant_id: str,
    input_data: Optional[dict] = None,
) -> Generator[Any, None, None]:
    """
    Context manager that wraps an agent node execution with a LangFuse span.
    Records start time, end time, and any exception — auto-closes on exit.

    Usage:
        with trace_agent_node("discovery", inv_id, tenant_id) as span:
            # agent work here
            pass
    """
    client = _get_client()
    start_time = time.perf_counter()
    span = None

    # LangFuse v4+ uses start_observation (OpenTelemetry-based span API)
    obs_ctx = None
    if client:
        try:
            obs_ctx = client.start_as_current_observation(
                name=agent_name,
                as_type="span",
                metadata={"investigation_id": investigation_id, "tenant_id": tenant_id},
                input=input_data or {},
            )
            obs_ctx.__enter__()
        except Exception:
            obs_ctx = None

    try:
        yield obs_ctx
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if obs_ctx:
            try:
                obs_ctx.__exit__(None, None, None)
            except Exception:
                pass
        logger.info(
            '{"event":"agent_complete","agent":"%s","duration_ms":%.1f}',
            agent_name, elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if obs_ctx:
            try:
                obs_ctx.__exit__(type(exc), exc, exc.__traceback__)
            except Exception:
                pass
        raise


def flush() -> None:
    """Flush pending LangFuse events — call at process shutdown."""
    client = _get_client()
    if client:
        try:
            client.flush()
        except Exception:
            pass
