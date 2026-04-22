"""
LangGraph state schema for SENTINEL investigations.

All agents read from and write to this TypedDict.
Fields annotated with `operator.add` are safe for parallel agent writes —
LangGraph merges them via the reducer without race conditions.

Never add mutable defaults here — LangGraph initializes state externally.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional, TypedDict


_last = lambda a, b: b if b is not None else a  # noqa: E731
_last_bool = lambda a, b: b  # noqa: E731

# ── Literal types — values sourced from configs/agents.yaml, never hardcoded ──

InvestigationStatus = Literal[
    "queued", "discovering", "investigating",
    "analyzing", "pending_human", "reporting", "complete", "failed",
]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
TriggerMode = Literal["reactive", "proactive", "scheduled"]
ComplianceVerdict = Literal["COMPLIANT", "VIOLATION", "UNCERTAIN"]


# ── Sub-schemas ────────────────────────────────────────────────────────────────

class ProvenanceNode(TypedDict):
    """
    W3C PROV-O Entity — represents one decision, document, or tool call
    in the provenance graph. content_hash enables tamper detection.
    """
    node_id: str
    node_type: str       # "decision" | "document" | "tool_call" | "agent_action"
    content_hash: str    # SHA-256 of node content — compare to detect tampering
    tenant_id: str       # Isolation guard — cross-tenant nodes are rejected
    metadata: dict
    timestamp: str       # ISO 8601


class EvidenceItem(TypedDict):
    """
    A verified piece of evidence with a link back to its provenance node.
    trust_score reflects how much weight agents should give this item.
    """
    evidence_id: str
    description: str
    provenance_node_id: str   # Must exist in provenance store — hallucinated IDs rejected
    trust_score: float        # 0.0–1.0 from trust_scorer.py
    source_type: str          # "regulation" | "decision_record" | "statistical_finding"


class AgentHeartbeat(TypedDict):
    """
    Health signal emitted by each agent before and after LLM calls.
    Orchestrator uses this to detect stuck agents (heartbeat > timeout).
    Timeout threshold is set in configs/agents.yaml per agent.
    """
    agent_name: str
    last_seen: str     # ISO 8601 — compared against heartbeat_timeout_seconds
    status: str        # "running" | "waiting" | "complete" | "failed"
    iteration: int


class CostRecord(TypedDict):
    """Per-LLM-call token and cost record. Appended to cost_log by cost_tracker.py."""
    agent: str
    model: str
    provider: str         # "ollama" | "anthropic" | "openai"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: str


# ── Main state schema ──────────────────────────────────────────────────────────

class InvestigationState(TypedDict):
    """
    Complete state for one SENTINEL investigation.

    Fields with `Annotated[list, operator.add]` are reducer fields:
    parallel LangGraph nodes can safely append to them simultaneously
    without overwriting each other's writes.

    All other fields follow last-writer-wins semantics — only one agent
    should write to each at a time (enforced by graph topology).
    """

    # ── Identity — set at graph entry, never modified ──────────────────────
    investigation_id: str
    tenant_id: str        # Injected from auth session, never from user input
    trigger_mode: TriggerMode
    domain: str           # Maps to configs/domains/{domain}.yaml

    # ── Sanitized input — set by input_guard.py before graph starts ────────
    query: str                  # PII-redacted, OWASP-sanitized query
    query_pii_detected: bool    # True if PII was found and redacted
    date_range: dict            # {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}
    context_sources: list       # Each source has trust_score from trust_scorer.py

    # ── Discovery agent outputs ────────────────────────────────────────────
    relevant_case_ids: list[str]
    case_count: int
    discovery_confidence: float

    # ── Investigation agent outputs ────────────────────────────────────────
    provenance_nodes: Annotated[list[ProvenanceNode], operator.add]
    evidence_items: Annotated[list[EvidenceItem], operator.add]
    decision_chains: Annotated[list[dict], operator.add]
    investigation_sufficient: Annotated[bool, _last_bool]
    investigation_iterations: Annotated[int, lambda a, b: b]

    # ── Legal analysis outputs (runs in parallel with bias detection) ───────
    applicable_regulations: Annotated[list[str], operator.add]
    compliance_verdict: Annotated[Optional[ComplianceVerdict], _last]
    legal_citations: Annotated[list[str], operator.add]
    regulatory_risk: Annotated[Optional[RiskLevel], _last]

    # ── Bias detection outputs (runs in parallel with legal analysis) ───────
    bias_dimensions_checked: Annotated[list[str], operator.add]
    statistical_findings: Annotated[list[dict], operator.add]
    bias_detected: Annotated[bool, _last_bool]
    bias_confidence: Annotated[float, _last]

    # ── Report agent outputs ───────────────────────────────────────────────
    draft_report: Optional[str]
    final_report: Optional[str]
    report_citations: list[str]
    report_confidence: float

    # ── HITL escalation ────────────────────────────────────────────────────
    hitl_required: bool
    hitl_reason: Optional[str]
    human_decision: Optional[str]
    reviewer_id: Optional[str]

    # ── Cross-cutting — Annotated fields safe for parallel writes ──────────
    status: Annotated[InvestigationStatus, _last]
    messages: Annotated[list[dict], operator.add]            # Agent progress events
    heartbeats: Annotated[list[AgentHeartbeat], operator.add]
    cost_log: Annotated[list[CostRecord], operator.add]
    error_log: Annotated[list[str], operator.add]

    # ── Resource tracking ──────────────────────────────────────────────────
    total_cost_usd: Annotated[float, _last]
    token_budget_remaining: dict[str, int]   # Per agent, from configs/agents.yaml
    max_iterations: int                       # From configs/agents.yaml at graph init
    iteration_count: int


def make_initial_state(
    investigation_id: str,
    tenant_id: str,
    query: str,
    date_range: dict,
    trigger_mode: TriggerMode = "reactive",
    domain: str = "finance",
    max_iterations: int = 5,
    token_budgets: Optional[dict[str, int]] = None,
) -> InvestigationState:
    """
    Factory that builds a valid initial state dict.
    All list/optional fields initialized to safe empty values.
    Prevents KeyError in agents that read optional fields before they're set.
    """
    default_budgets = {
        "discovery": 4000,
        "investigation": 8000,
        "legal_analysis": 8000,
        "bias_detection": 6000,
        "report_generation": 12000,
    }
    return InvestigationState(
        investigation_id=investigation_id,
        tenant_id=tenant_id,
        trigger_mode=trigger_mode,
        domain=domain,
        query=query,
        query_pii_detected=False,
        date_range=date_range,
        context_sources=[],
        relevant_case_ids=[],
        case_count=0,
        discovery_confidence=0.0,
        provenance_nodes=[],
        evidence_items=[],
        decision_chains=[],
        investigation_sufficient=False,
        investigation_iterations=0,
        applicable_regulations=[],
        compliance_verdict=None,
        legal_citations=[],
        regulatory_risk=None,
        bias_dimensions_checked=[],
        statistical_findings=[],
        bias_detected=False,
        bias_confidence=0.0,
        draft_report=None,
        final_report=None,
        report_citations=[],
        report_confidence=0.0,
        hitl_required=False,
        hitl_reason=None,
        human_decision=None,
        reviewer_id=None,
        status="queued",
        messages=[],
        heartbeats=[],
        cost_log=[],
        error_log=[],
        total_cost_usd=0.0,
        token_budget_remaining=token_budgets or default_budgets,
        max_iterations=max_iterations,
        iteration_count=0,
    )
