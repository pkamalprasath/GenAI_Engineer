"""
logging_config.py — Centralised logging setup for the Engineering RAG system.

Call setup_logging() once at application entry point (app.py, api.py, ingest_docs.py).
Every module then does:  logger = logging.getLogger(__name__)

Grafana Cloud Loki (optional):
  Set GRAFANA_LOKI_URL, GRAFANA_USER, GRAFANA_API_KEY in .env to enable.
  Logs are shipped in real-time to Grafana Cloud for search and dashboards.
  Sign up free at grafana.com → Grafana Cloud → free plan (50 GB/month).

  How to get your credentials:
    grafana.com → your stack → Loki → "Send Logs" → copy url, user, api key
"""

import logging
import logging.handlers
import os
from pathlib import Path

LOG_DIR   = Path(__file__).parent.parent / "logs"
LOG_FILE  = LOG_DIR / "rag.log"
APP_FILE  = LOG_DIR / "app.log"

FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Loki label tags attached to every log line — used for filtering in Grafana
_LOKI_TAGS = {"app": "engineering-rag", "env": os.getenv("APP_ENV", "dev")}


def _make_loki_handler(numeric_level: int) -> logging.Handler | None:
    """
    Build a Grafana Cloud Loki handler if credentials are present in env.
    Returns None (silently) when not configured — no error, no crash.

    Required env vars:
        GRAFANA_LOKI_URL  — e.g. https://logs-prod-012.grafana.net/loki/api/v1/push
        GRAFANA_USER      — numeric user id from Grafana Cloud (e.g. "123456")
        GRAFANA_API_KEY   — Grafana Cloud API key with MetricsPublisher role
    """
    url     = os.getenv("GRAFANA_LOKI_URL", "")
    user    = os.getenv("GRAFANA_USER",     "")
    api_key = os.getenv("GRAFANA_API_KEY",  "")

    if not url or not user or not api_key or url.startswith("https://logs-prod-YOUR"):
        return None  # not configured — skip silently

    try:
        import logging_loki
        handler = logging_loki.LokiHandler(
            url=url,
            tags=_LOKI_TAGS,
            auth=(user, api_key),
            version="1",
        )
        handler.setLevel(numeric_level)
        return handler
    except Exception as e:
        # Don't crash the app if Loki is misconfigured
        logging.getLogger(__name__).warning(
            "Grafana Loki handler failed to initialise: %s — continuing without it", e
        )
        return None


def setup_logging(level: str | None = None, app_mode: bool = False) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(FMT, datefmt=DATE_FMT)

    # Rotating file handler — 5 MB × 5 files (separate file for app vs api)
    log_path = APP_FILE if app_mode else LOG_FILE
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid adding duplicate handlers on Streamlit reruns
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(console_handler)
        loki = _make_loki_handler(numeric_level)
        if loki:
            root.addHandler(loki)
            root.info("Grafana Cloud Loki logging enabled (url=%s)", os.getenv("GRAFANA_LOKI_URL", "")[:40])
    else:
        has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)
        if not has_file:
            root.addHandler(file_handler)

        # Add Loki on first run if not already present
        try:
            import logging_loki
            has_loki = any(isinstance(h, logging_loki.LokiHandler) for h in root.handlers)
        except ImportError:
            has_loki = True  # can't check, skip
        if not has_loki:
            loki = _make_loki_handler(numeric_level)
            if loki:
                root.addHandler(loki)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "anthropic", "openai", "urllib3", "sentence_transformers", "loki"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
