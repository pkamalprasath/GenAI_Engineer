"""
Proactive Investigation Scheduler — triggers nightly compliance sweeps for all active tenants.

Wired into FastAPI lifespan startup. Uses APScheduler with AsyncIOScheduler.
Reads config from configs/scheduler.yaml.

The scheduler fires at 2 AM daily (configurable) and submits one investigation
per active tenant covering the past 24 hours of decisions. Uses trigger_mode="scheduled"
so the pipeline knows this is an automated, not human-initiated, investigation.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

SENTINEL_API_URL  = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
INTERNAL_API_KEY  = os.getenv("SENTINEL_API_KEY", "sentinel-dev-key-change-in-production")

_SCHEDULER_CFG_PATH = Path("configs/scheduler.yaml")


def _load_config() -> dict:
    if _SCHEDULER_CFG_PATH.exists():
        return yaml.safe_load(_SCHEDULER_CFG_PATH.read_text()).get("proactive_investigations", {})
    return {"enabled": False}


async def _get_active_tenants(configured: list[str]) -> list[dict]:
    """
    Return list of {tenant_id, domain} dicts.
    If configured tenants list is non-empty, use that.
    Otherwise query the DB for distinct tenants with recent investigations.
    """
    if configured:
        return [{"tenant_id": t, "domain": "finance"} for t in configured]

    # Query DB for active tenants
    try:
        from sentinel.db.session import AsyncSessionFactory
        from sqlalchemy import text
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("""
                    SELECT DISTINCT tenant_id,
                        COALESCE(
                            (state_snapshot->>'domain'),
                            'finance'
                        ) AS domain
                    FROM investigations
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    ORDER BY tenant_id
                    LIMIT 50
                """)
            )
            return [{"tenant_id": r.tenant_id, "domain": r.domain} for r in result.fetchall()]
    except Exception as exc:
        logger.error('{"event":"scheduler_tenant_lookup_failed","error":"%s"}', str(exc)[:100])
        return []


async def _run_nightly_sweep() -> None:
    """Triggered by APScheduler — submits one investigation per active tenant."""
    cfg = _load_config()
    if not cfg.get("enabled", False):
        logger.info('{"event":"scheduler_sweep_skipped","reason":"disabled_in_config"}')
        return

    now       = datetime.now(timezone.utc)
    yesterday = (now - timedelta(hours=cfg.get("lookback_hours", 24))).strftime("%Y-%m-%d")
    today     = now.strftime("%Y-%m-%d")

    tenants = await _get_active_tenants(cfg.get("tenants", []))
    if not tenants:
        logger.info('{"event":"scheduler_sweep_no_tenants"}')
        return

    logger.info('{"event":"nightly_sweep_started","tenant_count":%d,"date_from":"%s","date_to":"%s"}',
                len(tenants), yesterday, today)

    async with httpx.AsyncClient(timeout=30) as client:
        for tenant in tenants:
            try:
                resp = await client.post(
                    f"{SENTINEL_API_URL}/api/v1/investigations",
                    headers={
                        "X-API-Key":    INTERNAL_API_KEY,
                        "X-Tenant-ID":  tenant["tenant_id"],
                        "Content-Type": "application/json",
                    },
                    json={
                        "query":        f"Review all {tenant['domain']} decisions from {yesterday} for regulatory compliance violations, bias patterns, and adverse action notice requirements",
                        "date_from":    yesterday,
                        "date_to":      today,
                        "domain":       tenant["domain"],
                        "trigger_mode": "scheduled",
                    },
                )
                if resp.status_code == 202:
                    inv_id = resp.json().get("investigation_id", "?")
                    logger.info(
                        '{"event":"scheduled_investigation_triggered","tenant":"%s","investigation_id":"%s"}',
                        tenant["tenant_id"], inv_id,
                    )
                else:
                    logger.warning(
                        '{"event":"scheduled_investigation_failed","tenant":"%s","status":%d}',
                        tenant["tenant_id"], resp.status_code,
                    )
            except Exception as exc:
                logger.error(
                    '{"event":"scheduled_investigation_error","tenant":"%s","error":"%s"}',
                    tenant["tenant_id"], str(exc)[:100],
                )


def start_scheduler() -> AsyncIOScheduler:
    """
    Start the APScheduler with the nightly sweep job.
    Called from FastAPI lifespan startup.
    Returns the scheduler instance for potential shutdown handling.
    """
    global _scheduler

    cfg = _load_config()
    if not cfg.get("enabled", False):
        logger.info('{"event":"scheduler_disabled","reason":"enabled=false in scheduler.yaml"}')
        return None

    schedule = cfg.get("schedule", "0 2 * * *")
    # Parse cron string "0 2 * * *" → minute=0, hour=2
    parts = schedule.split()
    minute, hour = int(parts[0]), int(parts[1])

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_nightly_sweep,
        "cron",
        hour=hour,
        minute=minute,
        id="nightly_sweep",
        misfire_grace_time=3600,  # Allow up to 1h late if server was down
    )
    _scheduler.start()

    logger.info(
        '{"event":"scheduler_started","job":"nightly_sweep","schedule":"%s","hour":%d,"minute":%d}',
        schedule, hour, minute,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Called from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info('{"event":"scheduler_stopped"}')
