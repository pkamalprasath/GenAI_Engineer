"""
Audit Log Agent — writes structured compliance audit entries at the end of every investigation.

Runs after report_agent, before END. Always executes — not conditional on HITL.
Populates the audit_log table for 7-year regulatory retention (SR 11-7, GDPR Article 30).

Soul file: none — this agent writes facts, not prose.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.observability.logger import log_agent_event, log_error
from sentinel.state.investigation_state import InvestigationState

logger = logging.getLogger(__name__)


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """
    Audit agent node — writes one audit entry per investigation event.
    Never raises; failure is logged and silently absorbed so it never blocks the pipeline.
    """
    inv_id    = state["investigation_id"]
    tenant_id = state["tenant_id"]

    try:
        entries = _build_audit_entries(state)
        await _write_entries(session, inv_id, tenant_id, entries)

        log_agent_event(
            logger, inv_id, tenant_id, "audit_agent", "audit_written",
            details={"entries": len(entries)},
        )

        return {
            "audit_entries_written": len(entries),
            "messages": [{
                "agent": "audit_agent",
                "event": "complete",
                "entries_written": len(entries),
            }],
        }

    except Exception as exc:
        log_error(logger, inv_id, tenant_id, "audit_agent", type(exc).__name__, str(exc))
        return {
            "audit_entries_written": 0,
            "messages": [{"agent": "audit_agent", "event": "error", "error": str(exc)[:200]}],
            "error_log": [f"audit_agent: {type(exc).__name__}: {str(exc)[:200]}"],
        }


def _build_audit_entries(state: InvestigationState) -> list[dict]:
    """Build ordered list of audit entries from investigation state."""
    inv_id    = state["investigation_id"]
    tenant_id = state["tenant_id"]
    now       = datetime.now(timezone.utc).isoformat()

    entries = []

    # 1. Investigation started
    entries.append({
        "event":  "investigation_started",
        "actor":  "system",
        "details": {
            "query":      state.get("query", "")[:500],
            "domain":     state.get("domain", ""),
            "date_range": state.get("date_range", {}),
            "trigger":    state.get("trigger_mode", "reactive"),
            "tenant_id":  tenant_id,
        },
    })

    # 2. Discovery complete
    if state.get("case_count", 0) > 0:
        entries.append({
            "event": "discovery_complete",
            "actor": "discovery_agent",
            "details": {
                "case_count":           state.get("case_count", 0),
                "discovery_confidence": state.get("discovery_confidence", 0),
                "relevant_case_ids":    state.get("relevant_case_ids", [])[:10],
            },
        })

    # 3. Investigation analysis complete
    evidence_items = state.get("evidence_items", [])
    if evidence_items:
        entries.append({
            "event": "investigation_complete",
            "actor": "investigation_agent",
            "details": {
                "evidence_count": len(evidence_items),
                "investigation_sufficient": state.get("investigation_sufficient", False),
                "investigation_iterations": state.get("investigation_iterations", 0),
            },
        })

    # 4. Legal analysis complete
    if state.get("compliance_verdict"):
        entries.append({
            "event": "legal_analysis_complete",
            "actor": "legal_agent",
            "details": {
                "compliance_verdict":     state.get("compliance_verdict", "UNCERTAIN"),
                "regulatory_risk":        state.get("regulatory_risk", "LOW"),
                "applicable_regulations": state.get("applicable_regulations", []),
                "legal_citations":        state.get("legal_citations", [])[:5],
            },
        })

    # 5. Bias analysis complete
    entries.append({
        "event": "bias_analysis_complete",
        "actor": "bias_detection_agent",
        "details": {
            "bias_detected":           state.get("bias_detected", False),
            "bias_confidence":         state.get("bias_confidence", 0),
            "bias_dimensions_checked": state.get("bias_dimensions_checked", []),
            "statistical_findings":    state.get("statistical_findings", [])[:3],
        },
    })

    # 6. HITL escalation (if applicable)
    if state.get("hitl_required"):
        entries.append({
            "event": "hitl_escalated",
            "actor": "system",
            "details": {
                "reason":           state.get("hitl_reason", ""),
                "report_confidence": state.get("report_confidence", 0),
            },
        })

    # 7. Report finalized
    report_text = state.get("final_report") or state.get("draft_report") or ""
    entries.append({
        "event": "report_finalized",
        "actor": "report_agent",
        "details": {
            "compliance_verdict":  state.get("compliance_verdict", "UNCERTAIN"),
            "regulatory_risk":     state.get("regulatory_risk", "LOW"),
            "report_confidence":   state.get("report_confidence", 0),
            "report_length_chars": len(report_text),
            "citations_count":     len(state.get("report_citations", [])),
            "total_cost_usd":      state.get("total_cost_usd", 0),
        },
    })

    return entries


async def _write_entries(
    session: AsyncSession,
    inv_id: str,
    tenant_id: str,
    entries: list[dict],
) -> None:
    """Insert audit entries into audit_log table."""
    for entry in entries:
        await session.execute(
            text("""
                INSERT INTO audit_log
                    (investigation_id, tenant_id, event, actor, action, details, created_at)
                VALUES (:inv_id, :tenant_id, :event, :actor, :action, CAST(:details AS jsonb), NOW())
            """),
            {
                "inv_id":    inv_id,
                "tenant_id": tenant_id,
                "event":     entry["event"],
                "actor":     entry["actor"],
                "action":    entry.get("action", entry["event"]),
                "details":   json.dumps(entry.get("details", {})),
            },
        )
    await session.commit()
