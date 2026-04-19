"""
tracing.py — Langfuse Cloud observability for the Engineering RAG pipeline.
Compatible with Langfuse v4+ API.

Traces the full pipeline per user query:
  rag_query (root span)
  ├── retrieval span   (HyDE + dense search + RRF)
  ├── crag span        (chunk scoring + filtering)
  ├── generation span  (LLM call + token counts)
  └── self_rag span    (grounding critique)

Usage:
    tracer = start_trace("rag_query", input=query)
    with tracer.span("retrieval", input=query) as s:
        chunks = retriever.query(query)
        s.update(output={"chunks": len(chunks)})
    tracer.end(output=answer)

Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY in .env to enable.
If keys are absent, all calls are no-ops (no error).
"""

import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ── No-op classes (used when Langfuse is not configured) ─────────────────────

class _NoopSpan:
    def update(self, **kwargs): pass
    def end(self, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


class _NoopTrace:
    def update(self, **kwargs): pass
    def end(self, **kwargs): pass
    def span(self, name: str, **kwargs): return _NoopSpan()
    def generation(self, name: str, **kwargs): return _NoopSpan()


# ── Live span wrapper (Langfuse v4) ──────────────────────────────────────────

class _LiveSpan:
    """Wraps a Langfuse v4 start_as_current_observation context manager."""

    def __init__(self, client, name: str, as_type: str = "span", **kwargs):
        self._client = client
        self._name = name
        self._as_type = as_type   # "span", "retriever", "generation", etc.
        self._kwargs = kwargs
        self._ctx = None

    def update(self, **kwargs):
        try:
            if self._as_type == "generation":
                self._client.update_current_generation(**kwargs)
            else:
                self._client.update_current_span(**kwargs)
        except Exception as e:
            logger.debug("Langfuse span.update failed (%s): %s", self._name, e)

    def end(self, **kwargs):
        if kwargs:
            self.update(**kwargs)

    def __enter__(self):
        try:
            allowed = {k: v for k, v in self._kwargs.items()
                       if k in ("input", "metadata", "model")}
            self._ctx = self._client.start_as_current_observation(
                name=self._name,
                as_type=self._as_type,
                **allowed,
            )
            self._ctx.__enter__()
        except Exception as e:
            logger.debug("Langfuse span enter failed (%s): %s", self._name, e)
            self._ctx = None
        return self

    def __exit__(self, *args):
        if self._ctx is not None:
            try:
                self._ctx.__exit__(*args)
            except Exception as e:
                logger.debug("Langfuse span exit failed (%s): %s", self._name, e)


# ── RAGTracer ────────────────────────────────────────────────────────────────

class RAGTracer:
    """
    One RAGTracer per user query. Wraps the Langfuse v4 client.
    All child spans are created inside the root trace context.
    """

    def __init__(self, client, trace_ctx=None):
        self._client = client
        self._trace_ctx = trace_ctx   # root observation context manager

    def update(self, **kwargs):
        try:
            allowed_io = {k: v for k, v in kwargs.items() if k in ("input", "output")}
            if allowed_io:
                self._client.set_current_trace_io(**allowed_io)
        except Exception as e:
            logger.debug("Langfuse trace.update failed: %s", e)

    def end(self, **kwargs):
        self.update(**kwargs)

    @contextmanager
    def span(self, name: str, **kwargs):
        span = _LiveSpan(self._client, name, as_type="span", **kwargs)
        with span:
            yield span

    @contextmanager
    def retriever(self, name: str, **kwargs):
        span = _LiveSpan(self._client, name, as_type="retriever", **kwargs)
        with span:
            yield span

    @contextmanager
    def generation(self, name: str, model: str = "", **kwargs):
        gen = _LiveSpan(self._client, name, as_type="generation",
                        model=model, **kwargs)
        with gen:
            yield gen


# ── Module-level client (singleton) ──────────────────────────────────────────

_lf_client = None
_lf_enabled = False


def _get_client():
    global _lf_client, _lf_enabled
    if _lf_client is not None:
        return _lf_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key  = os.getenv("LANGFUSE_SECRET_KEY", "")
    host        = os.getenv("LANGFUSE_BASE_URL",
                            os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))

    if not public_key or not secret_key or public_key.startswith("pk-lf-your"):
        logger.info("Langfuse not configured — tracing disabled")
        _lf_enabled = False
        return None

    try:
        from langfuse import Langfuse
        _lf_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        _lf_enabled = True
        logger.info("Langfuse tracing enabled (host=%s)", host)
    except Exception as e:
        logger.warning("Langfuse init failed, tracing disabled: %s", e)
        _lf_client = None
        _lf_enabled = False

    return _lf_client


def start_trace(name: str = "rag_query", **kwargs) -> RAGTracer:
    """
    Start a root trace for one user query.
    Returns a RAGTracer (live) or no-op tracer if Langfuse is not configured.
    """
    client = _get_client()
    if client is None:
        return RAGTracer(_NoopTrace())

    try:
        allowed = {k: v for k, v in kwargs.items() if k in ("input", "metadata")}
        ctx = client.start_as_current_observation(
            name=name,
            as_type="span",
            **allowed,
        )
        ctx.__enter__()
        return RAGTracer(client, trace_ctx=ctx)
    except Exception as e:
        logger.debug("Langfuse trace start failed: %s", e)
        return RAGTracer(_NoopTrace())


def end_trace(tracer: RAGTracer, **kwargs):
    """End the root trace and flush pending events."""
    tracer.end(**kwargs)
    if tracer._trace_ctx is not None:
        try:
            tracer._trace_ctx.__exit__(None, None, None)
        except Exception as e:
            logger.debug("Langfuse trace end failed: %s", e)
    flush()


def flush():
    """Flush pending Langfuse events (call on app shutdown or after each trace)."""
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass
