"""
Legal Analysis Agent — applies regulatory rules to established investigation facts.

Runs in PARALLEL with bias_detection_agent after discovery (LangGraph fan-out).
Uses the unified LLM client — provider determined by configs/models.yaml
reasoning.provider (openai | anthropic). Zero code changes to switch providers.
Retrieves regulations via regulation MCP tool (hybrid search over regulatory PDFs).

Soul file: souls/legal_agent.md
"""
from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from configs.settings import agents_cfg, get_domain_config, models_cfg, settings
from sentinel.llm.client import chat as llm_chat
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.state.investigation_state import InvestigationState

logger = logging.getLogger(__name__)

_SOUL = open("souls/legal_agent.md").read()
_agent_cfg = agents_cfg.get("agents", {}).get("legal_analysis", {})
_model_cfg = models_cfg.get("models", {}).get("reasoning", {})
_MAX_REGS = _agent_cfg.get("max_regulations_loaded", 5)


async def _retrieve_regulations(domain: str, query: str) -> list[dict]:
    """
    Retrieve relevant regulation sections via the regulation MCP tool.
    Falls back to loading domain config regulation list if MCP unavailable.
    Returns list of {regulation_name, section, text} dicts.
    """
    try:
        # Import MCP tool wrapper — avoids circular import at module level
        from sentinel.tools.regulation_tools import search_regulations
        results = await search_regulations(query=query, domain=domain, top_k=_MAX_REGS)
        return results
    except Exception as exc:
        logger.warning('{"event":"regulation_mcp_fallback","error":"%s"}', str(exc)[:100])
        # Graceful fallback: return regulation names from domain config (no text)
        domain_cfg = get_domain_config()
        return [
            {"regulation_name": r["name"], "section": "full", "text": ""}
            for r in domain_cfg.get("regulations", [])
        ]


async def run(state: InvestigationState) -> dict:
    """
    Legal analysis agent node.
    Applies retrieved regulations to facts established by investigation_agent.
    """
    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("legal_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("legal_agent", inv_id, tenant_id):
        try:
            # Build a focused regulation query from actual case outcomes
            evidence_items = state.get("evidence_items", [])
            denied_items   = [e for e in evidence_items if "DENIED" in str(e.get("description","")).upper()]
            has_bias       = state.get("bias_detected", False)
            domain         = state["domain"]

            reg_query = (
                f"fair lending credit denial discrimination {domain} "
                f"{'bias disparate impact' if has_bias else 'adverse action notice'} "
                f"ECOA FCRA HMDA applicant rights"
            )
            regulations = await _retrieve_regulations(domain, query=reg_query)

            # Summarize evidence with denial reasons for meaningful legal analysis
            evidence_summary = json.dumps([
                {
                    "evidence_id":   e["evidence_id"],
                    "description":   e.get("description", "")[:200],
                    "source_type":   e["source_type"],
                    "trust_score":   e["trust_score"],
                }
                for e in evidence_items[:20]
            ], indent=2)

            reg_text = "\n\n".join(
                f"### {r['regulation_name']} — {r['section']}\n{r['text'][:500]}"
                for r in regulations
            )

            denied_summary = "\n".join(
                f"- {e.get('description','')[:250]}"
                for e in denied_items[:10]
            ) or "No denials found."

            prompt = f"""## Investigation Facts
Domain: {state['domain']}
Cases reviewed: {state.get('case_count', 0)}
Total evidence items: {len(evidence_items)}
Denied cases: {len(denied_items)}
Bias detected: {state.get('bias_detected', False)}
Bias confidence: {state.get('bias_confidence', 0)}
Statistical findings: {state.get('statistical_findings', [])}

## Denial Cases with Reasons
{denied_summary}

## Full Evidence Summary
{evidence_summary}

## Applicable Regulations Retrieved
{reg_text if reg_text else "No specific regulations retrieved — apply ECOA, FCRA, and HMDA general principles."}

## Task
You are a compliance attorney reviewing AI credit decisions against regulations.
IMPORTANT RULES:
1. Always populate applicable_regulations with the regulations retrieved above — even for compliant cases (list which regulations were CHECKED)
2. Always populate legal_citations with direct quotes from the regulation text above
3. If there are denials, analyze each denial reason against the regulations
4. If all cases are approved, state "COMPLIANT" but still cite which regulations confirmed compliance
5. Never return empty arrays — at minimum list what was checked and found compliant

Respond ONLY with valid JSON — no markdown, no explanation outside the JSON:
{{
  "applicable_regulations": ["ECOA — 15 U.S.C. § 1691(a)", "HMDA — 12 U.S.C. § 2803", ...],
  "compliance_verdict": "COMPLIANT" | "VIOLATION" | "UNCERTAIN",
  "legal_citations": ["Exact quote from regulation text retrieved above — max 120 chars", ...],
  "regulatory_risk": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "analysis_summary": "Paragraph: which regulations were checked, what each case showed, whether denial reasons are consistent with fair lending, final verdict with justification"
}}"""

            response = await llm_chat(prompt, tier="reasoning", system=_SOUL)

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            result = json.loads(raw)

            log_agent_event(
                logger, inv_id, tenant_id, "legal_agent", "legal_analysis_complete",
                details={
                    "verdict": result.get("compliance_verdict"),
                    "risk": result.get("regulatory_risk"),
                },
            )

            hb_end = heartbeat.emit("legal_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "legal_agent", response.model, response.provider,
                response.input_tokens, response.output_tokens,
                state_total=state["total_cost_usd"],
            )

            return {
                **hb_end,
                **cost_update,
                "status": "analyzing",
                "applicable_regulations": result.get("applicable_regulations", []),
                "compliance_verdict": result.get("compliance_verdict", "UNCERTAIN"),
                "legal_citations": result.get("legal_citations", []),
                "regulatory_risk": result.get("regulatory_risk", "LOW"),
                "messages": [{
                    "agent": "legal_agent",
                    "event": "complete",
                    "verdict": result.get("compliance_verdict"),
                    "risk": result.get("regulatory_risk"),
                }],
            }

        except Exception as exc:
            log_error(logger, inv_id, tenant_id, "legal_agent", type(exc).__name__, str(exc))
            hb_fail = heartbeat.emit("legal_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "status": "analyzing",
                "compliance_verdict": "UNCERTAIN",
                "regulatory_risk": "LOW",
                "messages": [{"agent": "legal_agent", "event": "error", "error": str(exc)[:200]}],
                "error_log": [f"legal_agent: {type(exc).__name__}: {str(exc)[:200]}"],
            }
