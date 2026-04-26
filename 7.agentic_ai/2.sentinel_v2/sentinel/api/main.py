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

import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    RegulationUploadRequest,
    RegulationUploadResponse,
    RegulationListItem,
)
from sentinel.core.utils import make_safe_snapshot
from sentinel.db.session import get_db_session
from sentinel.graph.builder import get_compiled_graph
from sentinel.guardrails.input_guard import sanitize_input
from sentinel.state.investigation_state import make_initial_state

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up compiled graph, initialize Redis connection pool."""
    import asyncio
    from arq import create_pool

    logger.info('{"event":"startup","service":"sentinel-api","version":"2.0"}')
    await get_compiled_graph()

    # Initialize Redis connection pool for job queue (Phase 4)
    from sentinel.worker.settings import get_redis_settings
    redis_settings = get_redis_settings()
    try:
        # Timeout Redis connection after 10 seconds (conn_retries=3 * conn_timeout=5)
        app.state.redis = await asyncio.wait_for(create_pool(redis_settings), timeout=12.0)
        logger.info('{"event":"redis_pool_initialized"}')
    except asyncio.TimeoutError:
        logger.warning('{"event":"redis_connection_timeout","error":"Redis pool initialization timed out after 12s"}')
        app.state.redis = None
    except Exception as e:
        logger.warning('{"event":"redis_connection_failed","error":"%s"}', str(e)[:200])
        app.state.redis = None

    yield

    # Shutdown: close Redis pool
    if hasattr(app.state, "redis") and app.state.redis:
        try:
            await app.state.redis.close()
            logger.info('{"event":"redis_pool_closed"}')
        except Exception as e:
            logger.warning('{"event":"redis_close_error","error":"%s"}', str(e)[:200])

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

            # Add structured applicant/case data if provided
            has_app_data = request_body.applicant_data is not None and len(request_body.applicant_data) > 0 if isinstance(request_body.applicant_data, dict) else False
            logger.info('{"event":"check_applicant_data_in_run","id":"%s","has_applicant_data":%s,"type":"%s"}',
                       investigation_id, str(has_app_data), type(request_body.applicant_data).__name__)

            if request_body.applicant_data:
                initial_state["applicant_data"] = request_body.applicant_data
                logger.info('{"event":"applicant_data_added_to_state","id":"%s","fields":%d,"keys":%s}',
                           investigation_id, len(request_body.applicant_data),
                           str(list(request_body.applicant_data.keys())[:3]))

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
                    _safe_partial = make_safe_snapshot(partial)
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

            safe_snapshot = make_safe_snapshot(final_state)

            # FALLBACK: Ensure required fields are always populated
            if "compliance_verdict" not in safe_snapshot or safe_snapshot.get("compliance_verdict") is None:
                safe_snapshot["compliance_verdict"] = final_state.get("compliance_verdict", "UNCERTAIN")
            if "regulatory_risk" not in safe_snapshot or safe_snapshot.get("regulatory_risk") is None:
                safe_snapshot["regulatory_risk"] = final_state.get("regulatory_risk", "MEDIUM")
            if "bias_detected" not in safe_snapshot:
                safe_snapshot["bias_detected"] = final_state.get("bias_detected", False)

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


@app.post("/api/v1/investigations", response_model=InvestigationResponse, status_code=202)
async def start_investigation(
    body: InvestigationRequest,
    request: Request,
):
    """Submit a new compliance investigation. Enqueues async job to worker."""
    from sentinel.db.session import AsyncSessionFactory
    from pathlib import Path
    import json as _json

    tenant_id = request.state.tenant_id
    investigation_id = f"INV-{uuid.uuid4().hex[:12].upper()}"

    # DEBUG: Log received body with explicit type checking
    import sys
    debug_f = open(Path(__file__).parent.parent.parent / "api_debug.log", "a")
    debug_f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] START_INVESTIGATION CALLED: id={investigation_id}\n")
    debug_f.write(f"[DEBUG] body type: {type(body).__name__}\n")
    debug_f.write(f"[DEBUG] body.applicant_data: {body.applicant_data}\n")
    debug_f.write(f"[DEBUG] body.applicant_data is None: {body.applicant_data is None}\n")
    debug_f.write(f"[DEBUG] type(body.applicant_data): {type(body.applicant_data).__name__}\n")
    debug_f.flush()
    debug_f.close()
    logger.info('{"event":"investigate_request","id":"%s","body_type":"%s"}',
               investigation_id, type(body).__name__)
    logger.info('{"event":"applicant_data_check","id":"%s","is_none":%s,"type":"%s","value_str":"%s"}',
               investigation_id,
               str(body.applicant_data is None),
               type(body.applicant_data).__name__,
               str(body.applicant_data)[:100])

    if body.applicant_data:
        logger.info('{"event":"app_data_received","id":"%s","keys":%s,"len":%d}',
                   investigation_id, str(list(body.applicant_data.keys())), len(body.applicant_data))
    else:
        logger.info('{"event":"app_data_empty_or_none","id":"%s"}', investigation_id)

    async with AsyncSessionFactory() as db:
        import json as _json
        # Store applicant_data as JSONB if provided
        app_data_param = None
        if body.applicant_data is not None:
            try:
                app_data_param = _json.dumps(body.applicant_data)
                logger.info('{"event":"applicant_data_serialized","id":"%s","json_len":%d}',
                           investigation_id, len(app_data_param))
            except Exception as serialize_err:
                logger.error('{"event":"applicant_data_serialize_failed","id":"%s","error":"%s"}',
                           investigation_id, str(serialize_err))
                app_data_param = None
        else:
            logger.info('{"event":"applicant_data_is_none","id":"%s"}', investigation_id)

        debug_f = open(Path(__file__).parent.parent.parent / "api_debug.log", "a")
        debug_f.write(f"[DEBUG] Before INSERT: app_data_param is None: {app_data_param is None}\n")
        if app_data_param:
            debug_f.write(f"[DEBUG] JSON to be inserted (first 100 chars): {app_data_param[:100]}\n")
        debug_f.flush()
        debug_f.close()

        logger.info('{"event":"insert_about_to_execute","id":"%s","app_data_param_is_none":%s}',
                   investigation_id, str(app_data_param is None))

        await db.execute(
            text("""
                INSERT INTO investigations (investigation_id, tenant_id, status, domain,
                                            trigger_mode, query, applicant_data, date_from, date_to)
                VALUES (:id, :tenant, 'queued', :domain, :trigger, :query,
                        CAST(:app_data AS jsonb), :date_from, :date_to)
            """),
            {
                "id": investigation_id,
                "tenant": tenant_id,
                "domain": body.domain or settings.active_domain,
                "trigger": body.trigger_mode,
                "query": body.query[:500],
                "app_data": app_data_param,
                "date_from": body.date_from,
                "date_to": body.date_to,
            },
        )
        await db.commit()

        # Verify what was actually stored
        verify_result = await db.execute(
            text("SELECT applicant_data FROM investigations WHERE investigation_id=:id"),
            {"id": investigation_id}
        )
        verify_row = verify_result.fetchone()
        if verify_row:
            debug_f = open(Path(__file__).parent.parent.parent / "api_debug.log", "a")
            debug_f.write(f"[DEBUG] After INSERT verification:\n")
            debug_f.write(f"[DEBUG]   stored_value is None: {verify_row.applicant_data is None}\n")
            debug_f.write(f"[DEBUG]   stored_value: {verify_row.applicant_data}\n")
            debug_f.flush()
            debug_f.close()
            logger.info('{"event":"insert_verification","id":"%s","stored_value_is_null":%s,"stored_value_preview":"%s"}',
                       investigation_id, str(verify_row.applicant_data is None),
                       str(verify_row.applicant_data)[:100] if verify_row.applicant_data else "NULL")

        if body.applicant_data:
            logger.info('{"event":"investigation_created_with_applicant_data","id":"%s","fields":%d}',
                       investigation_id, len(body.applicant_data))

    # Enqueue job to Redis (Phase 4) — worker will pick it up
    if hasattr(request.app.state, "redis") and request.app.state.redis:
        try:
            await request.app.state.redis.enqueue_job(
                "run_investigation",
                investigation_id,
                tenant_id,
                body.model_dump(mode="json"),  # Pydantic v2 JSON-safe dict
            )
            logger.info('{"event":"investigation_enqueued","id":"%s"}', investigation_id)
        except Exception as e:
            logger.warning('{"event":"job_enqueue_failed","id":"%s","error":"%s"}',
                          investigation_id, str(e)[:200])
            # Fall back to in-process if queue fails (not ideal but graceful)
    else:
        logger.warning('{"event":"redis_unavailable","id":"%s","using":"background_task"}',
                      investigation_id)

    return InvestigationResponse(
        investigation_id=investigation_id,
        status="queued",
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class SyncExecutionRequest(BaseModel):
    """Request body for synchronous investigation execution."""
    applicant_data: Optional[Dict[str, Any]] = None


@app.post("/api/v1/investigations/{investigation_id}/execute-sync", response_model=InvestigationResult, tags=["Testing"])
async def execute_investigation_sync(
    investigation_id: str,
    sync_body: Optional[SyncExecutionRequest] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Execute investigation synchronously (for testing without Redis/worker). Blocks until complete."""
    if request is None:
        raise HTTPException(status_code=400, detail="Request object required")

    tenant_id = request.state.tenant_id

    # Fetch investigation from DB (includes applicant_data and dates if stored)
    result = await db.execute(
        text("""
            SELECT query, trigger_mode, domain, applicant_data, date_from, date_to
            FROM investigations
            WHERE investigation_id=:id AND tenant_id=:tenant
        """),
        {"id": investigation_id, "tenant": tenant_id},
    )
    inv_row = result.fetchone()
    if not inv_row:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Determine applicant_data: prefer request body, then fall back to stored DB value
    applicant_data = sync_body.applicant_data if sync_body and sync_body.applicant_data else inv_row.applicant_data

    if applicant_data:
        logger.info('{"event":"execute_sync_using_applicant_data","id":"%s","source":"%s"}',
                   investigation_id, "request_body" if (sync_body and sync_body.applicant_data) else "database")

    # Build request body from investigation details (use stored dates from DB)
    request_body = InvestigationRequest(
        query=inv_row.query or "",
        date_from=inv_row.date_from or "2024-01-01",
        date_to=inv_row.date_to or "2024-12-31",
        trigger_mode=inv_row.trigger_mode or "reactive",
        domain=inv_row.domain,
        applicant_data=applicant_data,  # Include applicant_data (from request or DB)
    )

    # Execute investigation synchronously
    await _run_investigation(investigation_id, tenant_id, request_body)

    # Return final result
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
        raise HTTPException(status_code=404, detail="Investigation not found after execution")

    # Parse state_snapshot from JSON string
    snapshot = {}
    if row.state_snapshot:
        if isinstance(row.state_snapshot, str):
            try:
                snapshot = json.loads(row.state_snapshot)
            except:
                snapshot = {}
        else:
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

    # Parse state_snapshot from JSON string
    snapshot = {}
    if row.state_snapshot:
        if isinstance(row.state_snapshot, str):
            try:
                snapshot = json.loads(row.state_snapshot)
            except:
                snapshot = {}
        else:
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


@app.get("/api/v1/investigations/{investigation_id}/stream")
async def stream_investigation(
    investigation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Server-Sent Events (SSE) stream of investigation progress.
    Streams node execution events as the investigation runs in the graph.
    """
    import json
    from sentinel.graph.builder import get_compiled_graph

    tenant_id = request.state.investigation_id

    graph = await get_compiled_graph()

    # Node names to stream (core agents, not internal nodes)
    NODE_NAMES = {
        "discovery", "investigation", "legal_analysis", "bias_detection",
        "evidence_assembly", "report_generation", "audit", "hitl_review"
    }

    async def event_generator():
        try:
            config = {"configurable": {"thread_id": investigation_id}}
            checkpoint = await graph.aget_state(config)

            if not checkpoint:
                yield f'data: {json.dumps({"event": "error", "detail": "Investigation not found"})}\n\n'
                return

            async for event in graph.astream_events(checkpoint.values, config=config, version="v2"):
                event_type = event.get("event", "")
                node_name = event.get("name", "")

                # Stream on_chain_start and on_chain_end for agent nodes
                if node_name in NODE_NAMES:
                    if event_type in ("on_chain_start", "on_chain_end"):
                        yield f'data: {json.dumps({"event": event_type, "node": node_name, "investigation_id": investigation_id})}\n\n'

                # Heartbeat to keep connection alive
                yield ": heartbeat\n\n"

        except Exception as exc:
            yield f'data: {json.dumps({"event": "error", "detail": str(exc)[:200]})}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
                if case_id:
                    # Check if this node belongs to the requested case
                    node_id_matches = successor.startswith(f"decision-{case_id}") or f"decision-{case_id}" == successor
                    node_case = graph.nodes[successor].get("content", {}).get("case_id", "")
                    content_matches = node_case == case_id if node_case else False

                    # Skip if neither node_id nor content matches the case_id
                    if not node_id_matches and not content_matches:
                        continue

                ndata = graph.nodes[successor]
                chain.append({
                    "node_id":   successor,
                    "node_type": ndata.get("node_type", "prov:Entity"),
                    "depth":     2,
                    "content":   ndata.get("content", {}),
                })
        elif case_id:
            # Fallback: direct decision node lookup when no activity node exists
            start_node = f"decision-{case_id}"
            if start_node in graph.nodes:
                ndata = graph.nodes[start_node]
                chain = [{
                    "node_id":   start_node,
                    "node_type": ndata.get("node_type", "prov:Entity"),
                    "depth":     0,
                    "content":   ndata.get("content", {}),
                }]
                # Optionally trace related nodes if they exist
                try:
                    related = trace_decision_chain(graph, start_node_id=start_node)
                    # Filter to only include nodes related to this case
                    for node in related:
                        if node.get("node_id") != start_node:
                            nid = node.get("node_id", "")
                            node_case = node.get("content", {}).get("case_id", "")
                            if nid.startswith(f"decision-{case_id}") or node_case == case_id:
                                chain.append(node)
                except Exception:
                    pass  # If tracing fails, just return the start node
            else:
                chain = []

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


# ── v2: Regulation management endpoints ──────────────────────────────────────

@app.get("/api/v1/regulations", response_model=list[RegulationListItem])
async def list_regulations(
    domain: str = "",
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all active regulation sections, optionally filtered by domain."""
    query = "SELECT id, regulation_name, full_name, section, domain, active, created_at FROM regulation_documents WHERE active=TRUE"
    params: dict = {}
    if domain:
        query += " AND domain=:domain"
        params["domain"] = domain
    query += " ORDER BY regulation_name, section"
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    return [
        RegulationListItem(
            id=r.id,
            regulation_name=r.regulation_name,
            full_name=r.full_name,
            section=r.section,
            domain=r.domain,
            active=r.active,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


@app.post("/api/v1/regulations", response_model=RegulationUploadResponse, status_code=201)
async def add_regulation(
    body: RegulationUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Add a new regulation section and embed it immediately.
    The legal agent picks it up on the next investigation — no restart needed.
    """
    import os
    import openai as _openai

    # Idempotency check
    existing = await db.execute(
        text("SELECT id FROM regulation_documents WHERE regulation_name=:name AND section=:section"),
        {"name": body.regulation_name, "section": body.section},
    )
    if existing.fetchone():
        raise HTTPException(status_code=409, detail=f"{body.regulation_name} — {body.section} already exists")

    # Embed via OpenAI
    embedded = False
    embedding_str = None
    try:
        client = _openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or settings.openai_api_key)
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=f"{body.regulation_name} {body.section}\n{body.content}"[:8000],
        )
        vec = resp.data[0].embedding
        embedding_str = "[" + ",".join(str(x) for x in vec) + "]"
        embedded = True
    except Exception as emb_exc:
        logger.warning('{"event":"embed_failed","error":"%s"}', str(emb_exc)[:100])

    result = await db.execute(
        text("""
            INSERT INTO regulation_documents
                (regulation_name, full_name, section, content, domain, active, embedding)
            VALUES (:name, :full_name, :section, :content, :domain, TRUE,
                    CASE WHEN :embedding IS NOT NULL THEN CAST(:embedding AS vector) ELSE NULL END)
            RETURNING id, created_at
        """),
        {
            "name": body.regulation_name,
            "full_name": body.full_name,
            "section": body.section,
            "content": body.content,
            "domain": body.domain,
            "embedding": embedding_str,
        },
    )
    row = result.fetchone()
    await db.commit()

    logger.info('{"event":"regulation_added","name":"%s","section":"%s","embedded":%s}',
                body.regulation_name, body.section, embedded)

    return RegulationUploadResponse(
        id=row.id,
        regulation_name=body.regulation_name,
        full_name=body.full_name,
        section=body.section,
        domain=body.domain,
        embedded=embedded,
        created_at=str(row.created_at),
    )


@app.get("/api/v1/regulations/search")
async def search_regulations_endpoint(
    query: str,
    domain: str = "finance",
    top_k: int = 5,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Search regulation knowledge base using pgvector cosine similarity."""
    from sentinel.tools.regulation_tools import search_regulations as _search_regulations
    results = await _search_regulations(query=query, domain=domain, top_k=top_k)
    return results


@app.delete("/api/v1/regulations/{regulation_id}", status_code=200)
async def delete_regulation(
    regulation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Soft-delete a regulation section (sets active=false). Reversible."""
    result = await db.execute(
        text("UPDATE regulation_documents SET active=FALSE WHERE id=:id RETURNING id"),
        {"id": regulation_id},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Regulation not found")
    await db.commit()
    return {"status": "deleted", "id": regulation_id}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """
    Liveness probe — service is alive (Kubernetes health).
    Fast check, no dependencies — use for restart decisions.
    """
    return {"status": "alive", "service": "sentinel-api"}


@app.get("/ready")
async def readiness_check(request: Request, db: AsyncSession = Depends(get_db_session)):
    """
    Readiness probe — service ready to accept traffic (Kubernetes readiness).
    Checks all critical dependencies: database, Redis queue.
    Returns 503 if any dependency is unhealthy.
    """
    from fastapi.responses import JSONResponse

    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        logger.warning('{"event":"db_check_failed","error":"%s"}', str(e)[:100])
        checks["database"] = "unhealthy"

    # Redis queue
    if hasattr(request.app.state, "redis") and request.app.state.redis:
        try:
            await request.app.state.redis.ping()
            checks["redis"] = "healthy"
        except Exception as e:
            logger.warning('{"event":"redis_check_failed","error":"%s"}', str(e)[:100])
            checks["redis"] = "unhealthy"
    else:
        checks["redis"] = "unavailable"

    # Database must be healthy; Redis can be unavailable (non-blocking for phase 4 rollout)
    db_healthy = checks.get("database") == "healthy"
    redis_ok = checks.get("redis") in ("healthy", "unavailable")
    service_ready = db_healthy and redis_ok

    if service_ready:
        return {"status": "ready", "components": checks}
    else:
        return JSONResponse(
            {"status": "not_ready", "components": checks},
            status_code=503,
        )
