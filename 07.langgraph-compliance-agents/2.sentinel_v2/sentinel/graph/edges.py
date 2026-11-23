"""
Conditional edge functions for the SENTINEL LangGraph.

Each function receives state and returns a string key that LangGraph
uses to route to the next node. All routing logic lives here — agents
do not make routing decisions themselves.

Thresholds come from configs/agents.yaml hitl_triggers — not hardcoded.
"""
from __future__ import annotations

from configs.settings import agents_cfg
from sentinel.state.investigation_state import InvestigationState

_hitl_triggers = agents_cfg.get("hitl_triggers", [])
_confidence_floor = next(
    (t["confidence_below"] for t in _hitl_triggers if "confidence_below" in t), 0.65
)
_hitl_risk_levels = next(
    (t["risk_level_in"] for t in _hitl_triggers if "risk_level_in" in t), ["HIGH", "CRITICAL"]
)


def route_legal_tools(state: InvestigationState) -> str:
    """
    Route after legal_agent runs: check if LLM requested tool calls.

    Loop guard: if legal_messages has >= 8 entries, force exit to evidence_assembly
    to prevent infinite tool-call loops.

    Returns:
      "legal_tools"         — LLM has tool_calls and loop guard not triggered
      "evidence_assembly"   — no tool_calls, or loop guard triggered (len >= 8)
    """
    legal_messages = state.get("legal_messages", [])

    # Loop guard: prevent infinite tool call cycles
    if len(legal_messages) >= 8:
        return "evidence_assembly"

    # Check if the last message (from LLM) has tool_calls
    if legal_messages:
        last = legal_messages[-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "legal_tools"

    return "evidence_assembly"


def route_after_discovery(state: InvestigationState) -> str:
    """
    After discovery: route to investigation if cases found, else fail.
    High-risk domains with no cases → escalate immediately rather than proceed.
    """
    if state.get("case_count", 0) == 0:
        return "no_cases"
    if state.get("discovery_confidence", 1.0) < _confidence_floor:
        return "hitl"   # Discovery itself uncertain — human needed
    return "investigate"


def route_after_evidence_assembly(state: InvestigationState) -> str:
    """
    After parallel agents (investigation + legal + bias) complete:
    route to HITL if any trigger is met, otherwise generate report.

    Routing priority:
      1. If legal agent produced a verdict → always attempt report (legal runs independently).
      2. If investigation found evidence → proceed to report.
      3. If nothing at all → HITL.
      HITL escalation on risk/bias happens AFTER report draft is created.
    """
    has_verdict  = state.get("compliance_verdict") is not None
    has_evidence = len(state.get("evidence_items", [])) > 0

    # If legal analysis produced a verdict, we have enough to generate a report
    # (investigation provenance is supplementary, not a blocker)
    if has_verdict or has_evidence:
        # HITL trigger: regulatory risk too high for auto-resolve
        if state.get("regulatory_risk") in _hitl_risk_levels:
            return "hitl"
        # HITL trigger: bias detected
        if state.get("bias_detected", False):
            return "hitl"
        # HITL trigger: low discovery confidence
        if state.get("discovery_confidence", 1.0) < _confidence_floor:
            return "hitl"
        return "report"

    # Truly nothing found — escalate to human
    return "hitl"


def route_after_report(state: InvestigationState) -> str:
    """
    After report generation: route to HITL if output guard flagged it,
    otherwise mark complete.
    """
    if state.get("hitl_required", False):
        return "hitl"
    return "complete"


def route_after_hitl(state: InvestigationState) -> str:
    """After human review: always route to complete (human made the call)."""
    return "complete"
