"""
SENTINEL FastAPI application.

Endpoints:
  POST /api/v1/investigations          — start investigation (background task)
  GET  /api/v1/investigations/{id}     — get result
  POST /api/v1/escalations/{id}/resolve — HITL resume
  GET  /api/v1/provenance/{id}/trace   — decision chain query
  GET  /api/v1/analytics               — pattern insights
  GET  /health                         — system health check
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.logging_config import configure_logging
from configs.settings import settings
from sentinel.api.middleware import AuthMiddleware, RateLimitMiddleware, RequestIDMiddleware
from sentinel.api.models import (
    AnalyticsResponse,
    EscalationResolveRequest,
    EscalationResponse,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationResult,
)
from sentinel.db.session import get_db_session
from sentinel.graph.builder import get_compiled_graph
from sentinel.guardrails.input_guard import sanitize_input
from sentinel.state.investigation_state import make_initial_state

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up compiled graph on startup — first compile is expensive."""
    logger.info('{"event":"startup","service":"sentinel-api"}')
    await get_compiled_graph()
    yield
    logger.info('{"event":"shutdown","service":"sentinel-api"}')
    from sentinel.observability.langfuse_tracer import flush
    flush()


app = FastAPI(
    title="SENTINEL — AI Compliance Investigation Platform",
    version="1.0.0",
    description="Autonomous AI governance and provenance investigation",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Middleware order matters — outermost runs first on request, last on response
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8502"],   # Streamlit dashboard
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "X-Tenant-ID", "Content-Type"],
)


async def _run_investigation(
    investigation_id: str,
    tenant_id: str,
    request_body: InvestigationRequest,
) -> None:
    """Background task — owns its own DB session (request session is closed by then)."""
    import json as _json
    from sentinel.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        try:
            guard = sanitize_input(request_body.query, tenant_id=tenant_id)
            if guard.blocked:
                logger.warning(
                    '{"event":"investigation_blocked","id":"%s","reason":"%s"}',
                    investigation_id, guard.block_reason,
                )
                await db.execute(
                    text("UPDATE investigations SET status='failed' WHERE investigation_id=:id"),
                    {"id": investigation_id},
                )
                await db.commit()
                return

            initial_state = make_initial_state(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                query=guard.clean_text,
                date_range={"from": request_body.date_from, "to": request_body.date_to},
                trigger_mode=request_body.trigger_mode,
                domain=request_body.domain or settings.active_domain,
            )
            initial_state["query_pii_detected"] = guard.pii_detected
            initial_state["context_sources"] = guard.context_sources

            # Mark discovering immediately so dashboard stops showing "queued"
            await db.execute(
                text("UPDATE investigations SET status='discovering' WHERE investigation_id=:id"),
                {"id": investigation_id},
            )
            await db.commit()

            graph = await get_compiled_graph()
            config = {"configurable": {"thread_id": investigation_id}}

            try:
                final_state = await graph.ainvoke(initial_state, config=config)
            except Exception as graph_exc:
                exc_type = type(graph_exc).__name__
                # LangGraph raises GraphInterrupt / Interrupt when hitl_node pauses
                if "Interrupt" in exc_type or "interrupt" in str(graph_exc).lower():
                    logger.info(
                        '{"event":"hitl_interrupt","id":"%s"}', investigation_id
                    )
                    # Retrieve checkpoint state for partial snapshot
                    try:
                        checkpoint = await graph.aget_state(config)
                        partial = checkpoint.values if checkpoint else {}
                    except Exception:
                        partial = {}
                    _safe_partial = _make_safe_snapshot(partial)
                    _safe_partial["hitl_required"] = True
                    await db.execute(
                        text("""
                            UPDATE investigations
                            SET status='pending_human', state_snapshot=CAST(:snapshot AS jsonb),
                                completed_at=NOW()
                            WHERE investigation_id=:id
                        """),
                        {"id": investigation_id, "snapshot": _json.dumps(_safe_partial)},
                    )
                    await db.commit()
                    return
                raise  # Re-raise non-interrupt exceptions to outer handler

            safe_snapshot = _make_safe_snapshot(final_state)
            # Detect HITL: graph returned partial state without raising interrupt exception
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
                    "snapshot": _json.dumps(safe_snapshot),
                    "cost": final_state.get("total_cost_usd", 0.0),
                },
            )
            await db.commit()

        except Exception as exc:
            logger.error('{"event":"investigation_error","id":"%s","error":"%s"}',
                         investigation_id, str(exc)[:500])
            try:
                await db.execute(
                    text("UPDATE investigations SET status='failed' WHERE investigation_id=:id"),
                    {"id": investigation_id},
                )
                await db.commit()
            except Exception:
                pass


def _make_safe_snapshot(state: dict) -> dict:
    """Serialize state to a JSON-safe dict, dropping non-serializable objects."""
    import json as _json

    def _is_safe(v) -> bool:
        try:
            _json.dumps(v)
            return True
        except (TypeError, ValueError):
            return False

    excluded = {"provenance_nodes", "decision_chains"}
    return {
        k: v for k, v in state.items()
        if k not in excluded and _is_safe(v)
    }


@app.post("/api/v1/investigations", response_model=InvestigationResponse, status_code=202)
async def start_investigation(
    body: InvestigationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Submit a new compliance investigation. Runs asynchronously."""
    import json as _json
    from sentinel.db.session import AsyncSessionFactory

    tenant_id = request.state.tenant_id
    investigation_id = f"INV-{uuid.uuid4().hex[:12].upper()}"

    async with AsyncSessionFactory() as db:
        await db.execute(
            text("""
                INSERT INTO investigations (investigation_id, tenant_id, status, domain,
                                            trigger_mode, query)
                VALUES (:id, :tenant, 'queued', :domain, :trigger, :query)
            """),
            {
                "id": investigation_id,
                "tenant": tenant_id,
                "domain": body.domain or settings.active_domain,
                "trigger": body.trigger_mode,
                "query": body.query[:500],
            },
        )
        await db.commit()

    background_tasks.add_task(_run_investigation, investigation_id, tenant_id, body)

    return InvestigationResponse(
        investigation_id=investigation_id,
        status="queued",
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationResult)
async def get_investigation(
    investigation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Get investigation result by ID. Tenant-scoped."""
    tenant_id = request.state.tenant_id
    result = await db.execute(
        text("""
            SELECT investigation_id, status, state_snapshot, total_cost_usd
            FROM investigations
            WHERE investigation_id=:id AND tenant_id=:tenant
        """),
        {"id": investigation_id, "tenant": tenant_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Investigation not found")

    snapshot = row.state_snapshot or {}
    return InvestigationResult(
        investigation_id=row.investigation_id,
        status=row.status,
        compliance_verdict=snapshot.get("compliance_verdict"),
        regulatory_risk=snapshot.get("regulatory_risk"),
        bias_detected=snapshot.get("bias_detected", False),
        report_confidence=snapshot.get("report_confidence", 0.0),
        total_cost_usd=float(row.total_cost_usd or 0),
        final_report=snapshot.get("final_report") or snapshot.get("draft_report"),
        hitl_required=snapshot.get("hitl_required", False),
        case_count=snapshot.get("case_count", 0),
        discovery_confidence=float(snapshot.get("discovery_confidence", 0.0)),
        evidence_count=len(snapshot.get("evidence_items", [])),
        investigation_sufficient=snapshot.get("investigation_sufficient"),
        bias_confidence=float(snapshot.get("bias_confidence", 0.0)),
        agent_events=snapshot.get("messages", []),
        error_log=snapshot.get("error_log", []),
        heartbeats=snapshot.get("heartbeats", []),
    )


@app.post("/api/v1/escalations/{investigation_id}/resolve")
async def resolve_escalation(
    investigation_id: str,
    body: EscalationResolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Human HITL resolution — resumes the paused LangGraph graph with human input.
    The graph was interrupted in hitl_node and is waiting for this call.
    """
    tenant_id = request.state.tenant_id
    graph = await get_compiled_graph()
    config = {"configurable": {"thread_id": investigation_id}}

    # Resume graph with human decision — LangGraph loads checkpoint and continues
    human_input = {
        "response": body.response,
        "reviewer_id": body.reviewer_id,
        "action": body.action,
    }

    import asyncio as _asyncio
    try:
        final_state = await _asyncio.wait_for(
            graph.ainvoke({"human_decision": body.response}, config=config),
            timeout=8.0,  # Don't block dashboard for longer than this
        )
        graph_succeeded = True
    except Exception as exc:
        # Checkpoint missing, state schema mismatch, or timeout — fall through to DB update
        logger.warning(
            '{"event":"hitl_graph_resume_failed","id":"%s","error":"%s"}',
            investigation_id, str(exc)[:200],
        )
        graph_succeeded = False

    # Always persist the human decision and mark complete in DB
    import json as _json
    patch = _json.dumps({
        "human_decision": body.response,
        "reviewer_id":    body.reviewer_id,
        "hitl_action":    body.action,
    })
    try:
        await db.execute(
            text("""
                UPDATE investigations
                SET status       = 'complete',
                    completed_at = NOW(),
                    state_snapshot = COALESCE(state_snapshot, '{}') || CAST(:patch AS jsonb)
                WHERE investigation_id = :id AND tenant_id = :tenant
            """),
            {"patch": patch, "id": investigation_id, "tenant": tenant_id},
        )
        await db.commit()
    except Exception as db_exc:
        logger.error('{"event":"hitl_db_update_failed","id":"%s","error":"%s"}',
                     investigation_id, str(db_exc)[:200])
        raise HTTPException(status_code=500, detail="Failed to persist decision")

    return {"status": "resolved", "investigation_id": investigation_id, "graph_resumed": graph_succeeded}


@app.get("/api/v1/escalations")
async def list_escalations(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Return investigations with status=pending_human for HITL review queue."""
    tenant_id = request.state.tenant_id
    result = await db.execute(
        text("""
            SELECT investigation_id, status, state_snapshot, created_at
            FROM investigations
            WHERE tenant_id=:tenant AND status='pending_human'
            ORDER BY created_at DESC LIMIT 50
        """),
        {"tenant": tenant_id},
    )
    rows = result.fetchall()
    escalations = []
    for row in rows:
        snap = row.state_snapshot or {}
        escalations.append({
            "escalation_id": f"ESC-{row.investigation_id}",
            "investigation_id": row.investigation_id,
            "reason": snap.get("hitl_reason", "Requires human review"),
            "draft_report": snap.get("final_report") or snap.get("draft_report") or "Report pending human approval",
            "status": "pending",
            "created_at": str(row.created_at),
        })
    return escalations


@app.get("/api/v1/provenance/{investigation_id}/trace")
async def get_provenance_trace(
    investigation_id: str,
    case_id: str = "",
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Return the provenance decision chain for a specific case within an investigation."""
    from sentinel.provenance.store import ProvenanceStore
    from sentinel.provenance.query import trace_decision_chain

    tenant_id = getattr(request.state, "tenant_id", "demo")
    result = await db.execute(
        text("SELECT investigation_id FROM investigations WHERE investigation_id=:id AND tenant_id=:tenant"),
        {"id": investigation_id, "tenant": tenant_id},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Investigation not found")

    try:
        store = ProvenanceStore(db)

        # Build graph — include activity/agent nodes for this investigation plus case nodes
        graph = await store.build_graph(tenant_id)

        chain: list[dict] = []

        # Strategy 1: if we have an activity node for this investigation, walk from it
        activity_nid = f"activity-investigation-{investigation_id}"
        agent_nid    = f"agent-investigation-{investigation_id}"

        if activity_nid in graph.nodes:
            # Add agent → activity → decisions into the chain
            if agent_nid in graph.nodes:
                ag = graph.nodes[agent_nid]
                chain.append({
                    "node_id":   agent_nid,
                    "node_type": ag.get("node_type", "prov:Agent"),
                    "depth":     0,
                    "content":   ag.get("content", {}),
                })
            act = graph.nodes[activity_nid]
            chain.append({
                "node_id":   activity_nid,
                "node_type": act.get("node_type", "prov:Activity"),
                "depth":     1,
                "content":   act.get("content", {}),
            })
            # Add decision nodes reachable from activity
            for successor in graph.successors(activity_nid):
                # Filter to specific case_id if provided
                if case_id and f"decision-{case_id}" != successor and not successor.startswith(f"decision-{case_id}"):
                    node_case = graph.nodes[successor].get("content", {}).get("case_id", "")
                    if node_case != case_id:
                        continue
                ndata = graph.nodes[successor]
                chain.append({
                    "node_id":   successor,
                    "node_type": ndata.get("node_type", "prov:Entity"),
                    "depth":     2,
                    "content":   ndata.get("content", {}),
                })
        elif case_id:
            # Fallback: direct decision node lookup
            start_node = f"decision-{case_id}"
            chain = trace_decision_chain(graph, start_node_id=start_node) if start_node in graph.nodes else []

        return {
            "investigation_id": investigation_id,
            "case_id":          case_id,
            "chain":            chain,
            "node_count":       len(graph.nodes),
        }
    except Exception as exc:
        logger.error('{"event":"provenance_error","id":"%s","error":"%s"}', investigation_id, str(exc)[:200])
        raise HTTPException(status_code=500, detail=f"Provenance error: {type(exc).__name__}")


@app.get("/api/v1/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = 7,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Pattern insights and cost metrics for the tenant."""
    tenant_id = getattr(request.state, "tenant_id", "demo")
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                AVG(total_cost_usd) as avg_cost,
                SUM(CASE WHEN state_snapshot->>'compliance_verdict'='COMPLIANT' THEN 1 ELSE 0 END)::float
                    / NULLIF(COUNT(*), 0) as compliance_rate,
                SUM(CASE WHEN state_snapshot->>'bias_detected'='true' THEN 1 ELSE 0 END)::float
                    / NULLIF(COUNT(*), 0) as bias_rate,
                SUM(CASE WHEN state_snapshot->>'hitl_required'='true' THEN 1 ELSE 0 END)::float
                    / NULLIF(COUNT(*), 0) as hitl_rate
            FROM investigations
            WHERE tenant_id=:tenant
              AND created_at >= NOW() - INTERVAL '{days} days'
        """.format(days=int(days))),
        {"tenant": tenant_id},
    )
    row = result.fetchone()
    return AnalyticsResponse(
        period=f"last_{days}_days",
        total_investigations=row.total or 0,
        compliance_rate=float(row.compliance_rate or 0),
        bias_detection_rate=float(row.bias_rate or 0),
        avg_cost_usd=float(row.avg_cost or 0),
        hitl_rate=float(row.hitl_rate or 0),
        top_risk_categories=[],
    )


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """System health — checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "degraded"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "components": {"database": db_status, "llm_api": "up"},
    }
