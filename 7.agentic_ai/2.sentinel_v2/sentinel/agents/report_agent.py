"""
Report Agent — generates regulatory-compliant compliance investigation reports.

Uses the unified LLM client (synthesis tier) — provider determined by
configs/models.yaml synthesis.provider (openai | anthropic).
Validates output through output_guard before returning (citation verification + PII scan).
Triggers HITL if confidence below threshold from configs/agents.yaml.
After writing report, calls pattern_extractor to store compliance patterns for future investigations.

Soul file: souls/report_agent.md
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import agents_cfg, models_cfg, settings
from sentinel.llm.client import chat as llm_chat, get_tier_for_agent
from sentinel.guardrails.output_guard import validate_output_async as validate_output
from sentinel.guardrails.trust_scorer import aggregate_trust
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.provenance.store import ProvenanceStore
from sentinel.state.investigation_state import InvestigationState

logger = logging.getLogger(__name__)

_SOUL = open("souls/report_agent.md").read()
_agent_cfg = agents_cfg.get("agents", {}).get("report_generation", {})
_model_cfg = models_cfg.get("models", {}).get("synthesis", {})


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """Report agent node — produces the final compliance report."""
    from sentinel.core.debug import (
        log_agent_input, log_agent_output, log_agent_exception,
        generate_mock_report_output
    )

    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("report_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("report_agent", inv_id, tenant_id):
        try:
            log_agent_input(
                "report_agent", inv_id,
                ["compliance_verdict", "regulatory_risk", "bias_detected", "applicant_data"],
                state
            )

            # Aggregate trust score from all evidence items
            report_confidence = aggregate_trust(state.get("evidence_items", []))

            # Build evidence index — only decision nodes, not agent/activity nodes
            evidence_items = state.get("evidence_items", [])
            citations = [
                e["provenance_node_id"] for e in evidence_items
                if e.get("provenance_node_id", "").startswith("decision-")
            ][:30]

            # Build per-case detail for the report LLM
            case_details = []
            for e in evidence_items[:20]:
                desc = e.get("description", "")
                if desc and desc != f"Provenance node {e.get('source_type','')} for case":
                    case_details.append({
                        "case": e.get("provenance_node_id", ""),
                        "detail": desc[:300],
                    })

            findings_summary = {
                "domain":               state["domain"],
                "investigation_id":     inv_id,
                "date_range":           state.get("date_range", {}),
                "cases_reviewed":       state.get("case_count", 0),
                "compliance_verdict":   state.get("compliance_verdict", "UNCERTAIN"),
                "regulatory_risk":      state.get("regulatory_risk", "LOW"),
                "bias_detected":        state.get("bias_detected", False),
                "bias_confidence":      state.get("bias_confidence", 0),
                "bias_dimensions":      state.get("bias_dimensions_checked", []),
                "applicable_regulations": state.get("applicable_regulations", []),
                "legal_citations":      state.get("legal_citations", []),
                "statistical_findings": state.get("statistical_findings", [])[:5],
                "evidence_count":       len(evidence_items),
                "broken_chains":        sum(1 for e in evidence_items if e.get("source_type") == "broken_chain"),
            }

            report_prompt = f"""Generate a regulatory compliance investigation report.

Investigation Summary:
{json.dumps(findings_summary, indent=2)}

Case-Level Evidence (denial reasons, applicant profiles, anomaly details):
{json.dumps(case_details, indent=2)}

Evidence Index (provenance node IDs — cite these in your report):
{json.dumps(citations[:20], indent=2)}

Requirements:
- Use formal regulatory language suitable for CFPB, FDA, or state regulator submission
- For each denied or anomalous case: state the case ID, the denial reason or anomaly, and the applicant profile
- For each applicable regulation: quote the specific section and explain how the finding relates to it
- If applicable_regulations is empty: explicitly state regulations were not retrieved for this domain
- Cite provenance node IDs in square brackets [node-id] for every factual claim
- Never include PII — use case IDs, anonymized profiles, and patterns only
- Structure: Executive Summary → Scope → Key Findings → Regulatory Analysis → Risk → Conclusion → Evidence Index
- Report confidence: {report_confidence:.2f}"""

            tier = get_tier_for_agent("report_agent")
            response = await llm_chat(report_prompt, tier=tier, system=_SOUL)
            draft_report = response.text

            # Validate output: citation verification + PII scan + confidence check
            store = ProvenanceStore(session)
            guard_result = await validate_output(
                content=draft_report,
                confidence=report_confidence,
                citations=citations,
                provenance_store=store,
            )

            if not guard_result.safe:
                log_error(
                    logger, inv_id, tenant_id, "report_agent",
                    "OutputGuardBlocked", guard_result.block_reason, recoverable=True,
                )
                hb_fail = heartbeat.emit("report_agent", "failed", state["iteration_count"])
                return {
                    **hb_fail,
                    "hitl_required": True,
                    "hitl_reason": guard_result.block_reason,
                    "draft_report": draft_report,
                    "status": "pending_human",
                    "error_log": [f"report_agent output blocked: {guard_result.block_reason}"],
                }

            log_agent_event(
                logger, inv_id, tenant_id, "report_agent", "report_complete",
                details={
                    "confidence": report_confidence,
                    "hitl_required": guard_result.hitl_required,
                    "hash": guard_result.content_hash[:16],
                },
            )

            hb_end = heartbeat.emit("report_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "report_agent", response.model, response.provider,
                response.input_tokens, response.output_tokens,
                state_total=state["total_cost_usd"],
            )

            final_status = "pending_human" if guard_result.hitl_required else "reporting"

            # Extract and store compliance patterns for future investigations (non-blocking)
            if not guard_result.hitl_required:
                try:
                    from sentinel.memory.pattern_extractor import extract_and_store
                    await extract_and_store(
                        session=session,
                        report=guard_result.content or draft_report,
                        domain=state["domain"],
                        investigation_id=inv_id,
                    )
                except Exception:
                    pass  # Pattern extraction is non-critical

            output = {
                **hb_end,
                **cost_update,
                "draft_report": draft_report,
                "final_report": draft_report if guard_result.hitl_required else guard_result.content,
                "report_citations": citations,
                "report_confidence": report_confidence,
                "hitl_required": guard_result.hitl_required,
                "hitl_reason": guard_result.hitl_reason,
                "status": final_status,
                "messages": [{
                    "agent": "report_agent",
                    "event": "complete",
                    "confidence": report_confidence,
                    "hitl_required": guard_result.hitl_required,
                }],
            }
            log_agent_output("report_agent", inv_id, output)
            return output

        except Exception as exc:
            log_agent_exception("report_agent", inv_id, exc)
            log_error(logger, inv_id, tenant_id, "report_agent", type(exc).__name__, str(exc))
            hb_fail = heartbeat.emit("report_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "error_log": [f"report_agent: {type(exc).__name__}: {str(exc)[:200]}"],
                "hitl_required": True,
                "hitl_reason": f"Report generation failed: {type(exc).__name__}",
                "status": "pending_human",
            }
