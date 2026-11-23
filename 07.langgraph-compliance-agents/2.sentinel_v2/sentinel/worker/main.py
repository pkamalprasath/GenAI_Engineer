"""
SENTINEL background worker (Phase 4).

Long-running investigations run here, not in the API process.
Jobs are enqueued by the API via Redis task queue (arq + Redis).
Worker pulls jobs, executes them, and stores results back in PostgreSQL.

Usage:
    arq sentinel.worker.main.WorkerSettings
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import settings
from sentinel.core.utils import make_safe_snapshot
from sentinel.db.session import AsyncSessionFactory
from sentinel.graph.builder import get_compiled_graph
from sentinel.guardrails.input_guard import sanitize_input
from sentinel.observability.logger import log_error
from sentinel.state.investigation_state import make_initial_state

logger = logging.getLogger(__name__)


async def run_investigation(
    investigation_id: str,
    tenant_id: str,
    request_body_json: str,
) -> dict:
    """
    arq job function — runs background investigation.

    Called by API via:
      await redis.enqueue_job(
          "run_investigation",
          investigation_id,
          tenant_id,
          request_body.model_dump(mode="json")  # Pydantic v2
      )

    Returns: dict with final investigation status
    """
    async with AsyncSessionFactory() as db:
        try:
            # Deserialize request body
            request_body = json.loads(request_body_json)

            # Sanitize input
            guard = sanitize_input(request_body["query"], tenant_id=tenant_id)
            if guard.blocked:
                logger.warning(
                    '{"event":"investigation_blocked","id":"%s","reason":"%s"}',
                    investigation_id, guard.block_reason
                )
                await db.execute(
                    text("UPDATE investigations SET status='failed' WHERE investigation_id=:id"),
                    {"id": investigation_id},
                )
                await db.commit()
                return {"status": "blocked", "investigation_id": investigation_id}

            # Initialize state
            initial_state = make_initial_state(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                query=guard.sanitized_query,
                date_range=request_body.get("date_range", {
                    "from": "2024-01-01",
                    "to": datetime.now().isoformat()[:10],
                }),
                trigger_mode=request_body.get("trigger_mode", "reactive"),
                domain=request_body.get("domain", "finance"),
                max_iterations=request_body.get("max_iterations", 5),
            )

            # Run investigation graph
            graph = await get_compiled_graph()
            config = {"configurable": {"thread_id": investigation_id}}

            try:
                final_state = await graph.ainvoke(initial_state, config=config)
            except Exception as graph_exc:
                # Graph raised exception (not interrupt) — failed state
                logger.error(
                    '{"event":"graph_error","id":"%s","error":"%s"}',
                    investigation_id, str(graph_exc)[:200]
                )
                await db.execute(
                    text("UPDATE investigations SET status='failed' WHERE investigation_id=:id"),
                    {"id": investigation_id},
                )
                await db.commit()
                return {"status": "failed", "investigation_id": investigation_id}

            # Save final state
            safe_snapshot = make_safe_snapshot(final_state)
            final_status = final_state.get("status", "complete")
            if final_status not in ("complete", "failed", "pending_human") or \
               final_state.get("hitl_required"):
                final_status = "pending_human"
                safe_snapshot["hitl_required"] = True

            await db.execute(
                text("""
                    UPDATE investigations
                    SET status=:status, state_snapshot=CAST(:snapshot AS jsonb),
                        total_cost_usd=:cost, completed_at=NOW()
                    WHERE investigation_id=:id
                """),
                {
                    "id": investigation_id,
                    "status": final_status,
                    "snapshot": json.dumps(safe_snapshot),
                    "cost": final_state.get("total_cost_usd", 0.0),
                },
            )
            await db.commit()

            logger.info(
                '{"event":"investigation_complete","id":"%s","status":"%s","cost":%.2f}',
                investigation_id,
                final_status,
                final_state.get("total_cost_usd", 0.0),
            )

            return {"status": final_status, "investigation_id": investigation_id}

        except Exception as exc:
            log_error(
                logger,
                investigation_id,
                tenant_id,
                "worker",
                type(exc).__name__,
                str(exc)[:500],
            )
            try:
                await db.execute(
                    text("UPDATE investigations SET status='failed' WHERE investigation_id=:id"),
                    {"id": investigation_id},
                )
                await db.commit()
            except Exception:
                pass
            return {"status": "failed", "investigation_id": investigation_id}


# ── arq Worker Configuration ───────────────────────────────────────────────

from sentinel.worker.settings import get_redis_settings


class WorkerSettings:
    """arq worker configuration — run with: arq sentinel.worker.main.WorkerSettings"""

    redis_settings = get_redis_settings()
    functions = [run_investigation]

    # Job execution policies
    max_jobs = 10                  # Max concurrent jobs (tune to available CPU/memory)
    job_timeout = 300             # 5-minute timeout per investigation
    allow_abort_jobs = False       # Don't allow aborting investigations mid-flight
    max_tries = 1                  # No auto-retry; store failed state in DB
