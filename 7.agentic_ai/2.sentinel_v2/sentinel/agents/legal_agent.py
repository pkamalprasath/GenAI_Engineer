"""
Legal Analysis Agent — applies regulatory rules to established investigation facts.

Analyzes investigation findings against applicable compliance regulations
and produces verdict (COMPLIANT, UNCERTAIN, VIOLATION) + regulatory risk assessment.

Runs in PARALLEL with bias_detection_agent after discovery (LangGraph fan-out).
Soul file: souls/legal_agent.md
"""
from __future__ import annotations

import asyncio
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from configs.settings import agents_cfg, settings
from sentinel.llm.client import chat as llm_chat, get_tier_for_agent
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.core.debug import log_agent_input, log_agent_output, log_agent_exception
from sentinel.state.investigation_state import InvestigationState
from sentinel.tools.regulation_tools import _inner_search_regulations

logger = logging.getLogger(__name__)

_SOUL = open("souls/legal_agent.md").read()
_agent_cfg = agents_cfg.get("agents", {}).get("legal_analysis", {})


def _build_investigation_context(state: InvestigationState) -> str:
    """Build the investigation context string for the legal agent prompt."""
    evidence_items = state.get("evidence_items", [])
    denied_items = [e for e in evidence_items if "DENIED" in str(e.get("description", "")).upper()]

    denied_summary = "\n".join(
        f"- {e.get('description','')[:250]}"
        for e in denied_items[:10]
    ) or "No denials found."

    evidence_summary = json.dumps([
        {
            "evidence_id": e["evidence_id"],
            "description": e.get("description", "")[:200],
            "source_type": e["source_type"],
            "trust_score": e["trust_score"],
        }
        for e in evidence_items[:20]
    ], indent=2)

    return f"""Domain: {state['domain']}
Cases reviewed: {state.get('case_count', 0)}
Bias detected: {state.get('bias_detected', False)}
Denied cases: {len(denied_items)}

Denial Cases:
{denied_summary}

Evidence:
{evidence_summary}"""


async def run(state: InvestigationState) -> dict:
    """
    Legal analysis agent node — simplified direct implementation.

    Fetches relevant regulations directly and analyzes them with the LLM.
    Avoids the complex ToolNode pattern to work reliably with OpenAI.
    """
    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("legal_agent", "running", state["iteration_count"])
    tier = get_tier_for_agent("legal_agent")

    with langfuse_tracer.trace_agent_node("legal_agent", inv_id, tenant_id):
        try:
            log_agent_input(
                "legal_agent", inv_id,
                ["domain", "case_count", "applicant_data", "evidence_items"],
                state
            )

            context = _build_investigation_context(state)
            domain = state.get("domain", "lending")

            # Fetch relevant regulations directly
            regulations_text = ""
            try:
                regulations = await _inner_search_regulations(
                    query=context[:500],
                    domain=domain,
                    top_k=5
                )
                if regulations:
                    regulations_text = "\n\n".join([
                        f"**{r.get('regulation_name', 'Unknown')} § {r.get('section', '')}**\n{r.get('text', '')}"
                        for r in regulations[:3]
                    ])
            except Exception as e:
                logger.warning(f"[LEGAL] Could not fetch regulations: {e}")
                regulations_text = "(Regulations unavailable)"

            # Build prompt with fetched regulations
            prompt = f"""{_SOUL}

You are a compliance attorney analyzing this investigation.

RELEVANT REGULATIONS:
{regulations_text}

INVESTIGATION CONTEXT:
{context}

Respond ONLY with valid JSON:
{{
  "applicable_regulations": ["ECOA - 15 U.S.C. § 1691(a)", "Fair Housing Act", "FCRA"],
  "compliance_verdict": "COMPLIANT" or "VIOLATION" or "UNCERTAIN",
  "legal_citations": ["Brief relevant quote"],
  "regulatory_risk": "LOW" or "MEDIUM" or "HIGH" or "CRITICAL",
  "analysis_summary": "Your assessment..."
}}"""

            # Call LLM directly for analysis
            response = await llm_chat(prompt, tier=tier, system=_SOUL)

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            result = json.loads(raw)

            hb_end = heartbeat.emit("legal_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "legal_agent", response.model, response.provider,
                response.usage.input_tokens if hasattr(response, 'usage') else 0,
                response.usage.output_tokens if hasattr(response, 'usage') else 0,
                state_total=state["total_cost_usd"],
            )

            log_agent_event(
                logger, inv_id, tenant_id, "legal_agent", "legal_analysis_complete",
                details={"verdict": result.get("compliance_verdict"), "risk": result.get("regulatory_risk")},
            )

            output = {
                **hb_end, **cost_update,
                "status": "analyzing",
                "applicable_regulations": result.get("applicable_regulations", []),
                "compliance_verdict": result.get("compliance_verdict", "UNCERTAIN"),
                "legal_citations": result.get("legal_citations", []),
                "regulatory_risk": result.get("regulatory_risk", "MEDIUM"),
                "messages": [{
                    "agent": "legal_agent",
                    "event": "complete",
                    "verdict": result.get("compliance_verdict"),
                    "risk": result.get("regulatory_risk"),
                }],
            }
            log_agent_output("legal_agent", inv_id, output)
            return output

        except Exception as exc:
            log_agent_exception("legal_agent", inv_id, exc)
            log_error(logger, inv_id, tenant_id, "legal_agent", type(exc).__name__, str(exc))
            hb_fail = heartbeat.emit("legal_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "status": "analyzing",
                "compliance_verdict": "UNCERTAIN",
                "regulatory_risk": "MEDIUM",
                "legal_citations": [],
                "applicable_regulations": [],
                "messages": [{"agent": "legal_agent", "event": "error", "error": str(exc)[:200]}],
                "error_log": [f"legal_agent: {type(exc).__name__}: {str(exc)[:200]}"],
            }
