"""
Integration test — single record walks through every agent.

Traces one CASE-TEST-001 record through the full pipeline and verifies
all state key handoffs between agents. No Docker, no Ollama required.
All I/O boundaries are mocked; only business logic is exercised.

Run:
    cd projects/sentinel_v2
    pytest tests/integration/test_one_record_pipeline.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest
import pytest_asyncio

from sentinel.agents import (
    bias_detection_agent,
    discovery_agent,
    investigation_agent,
    legal_agent,
    report_agent,
)
from sentinel.graph.edges import route_after_evidence_assembly, route_after_report
from sentinel.state.investigation_state import (
    EvidenceItem,
    InvestigationState,
    make_initial_state,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def one_record_state() -> InvestigationState:
    """Minimal state for a 7-day, single-case investigation."""
    return make_initial_state(
        investigation_id="INV-TEST-001",
        tenant_id="test-tenant",
        query="Review credit decisions Jan 3–10 2024 for fair lending compliance",
        date_range={"from": "2024-01-03", "to": "2024-01-10"},
        domain="finance",
    )


@pytest.fixture
def one_record_db(mock_db_session):
    """DB session pre-loaded with a single decision record."""
    row = MagicMock()
    row.case_id = "CASE-TEST-001"
    row.outcome = "denied"
    row.decision_timestamp = datetime(2024, 1, 5, 10, 30, tzinfo=timezone.utc)
    row.reasoning_text = "Credit score below threshold for loan amount requested."
    row.metadata = json.dumps({"race": "unknown", "gender": "unknown", "age": 35})
    row._mapping = {
        "case_id": row.case_id,
        "outcome": row.outcome,
        "decision_timestamp": row.decision_timestamp,
        "reasoning_text": row.reasoning_text,
        "metadata": row.metadata,
    }

    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[row])
    mock_result.fetchone = MagicMock(return_value=row)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    return mock_db_session


@pytest.fixture
def one_record_provenance_store():
    """ProvenanceStore with a single decision node for CASE-TEST-001."""
    store = AsyncMock()

    # Build a minimal DiGraph with one decision node
    g = nx.DiGraph()
    g.add_node(
        "decision-CASE-TEST-001",
        node_type="prov:Entity",
        content=json.dumps({
            "case_id": "CASE-TEST-001",
            "outcome": "denied",
            "content_hash": "sha256-abc123",
        }),
    )
    store.build_graph = AsyncMock(return_value=g)
    store.verify_hashes_batch = AsyncMock(return_value={"decision-CASE-TEST-001": True})
    store.verify_hash = AsyncMock(return_value=True)
    store.node_exists = AsyncMock(return_value=True)
    return store


def _llm_response(text: str, model: str = "gpt-4o-mini") -> MagicMock:
    """Build a mock LLMResponse object."""
    r = MagicMock()
    r.text = text
    r.model = model
    r.provider = "openai"
    r.input_tokens = 120
    r.output_tokens = 80
    return r


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Discovery: required output keys
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_discovery_returns_required_keys(one_record_state, one_record_db, monkeypatch):
    """Discovery agent must return all keys the downstream agents depend on."""
    # Mock BERT scorer to return above-threshold score for our one case
    bert_score = MagicMock()
    bert_score.case_id = "CASE-TEST-001"
    bert_score.score = 0.85
    bert_score.reasoning = "Credit decision, relevant to query."

    # score_cases_bert is sync (not async) — use MagicMock, not AsyncMock
    monkeypatch.setattr(
        "sentinel.agents.discovery_agent.score_cases_bert",
        MagicMock(return_value=[bert_score]),
    )
    monkeypatch.setattr(
        "sentinel.agents.discovery_agent.rank_cases_bm25",
        MagicMock(return_value=[{
            "case_id": "CASE-TEST-001",
            "reasoning_text": "Credit score below threshold.",
            "outcome": "denied",
        }]),
    )

    result = await discovery_agent.run(one_record_state, one_record_db)

    # All required keys must be present
    assert "relevant_case_ids" in result, "Missing relevant_case_ids"
    assert "case_count" in result, "Missing case_count"
    assert "discovery_confidence" in result, "Missing discovery_confidence"
    assert "status" in result, "Missing status"
    assert "messages" in result, "Missing messages"

    # Types
    assert isinstance(result["relevant_case_ids"], list)
    assert isinstance(result["case_count"], int)
    assert isinstance(result["discovery_confidence"], float)
    assert isinstance(result["messages"], list)
    assert len(result["messages"]) >= 1
    assert result["messages"][0]["agent"] == "discovery_agent"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Discovery: SQL date range format
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_discovery_date_range_sql_format(one_record_state, one_record_db, monkeypatch):
    """Discovery must pass timestamp strings in 'YYYY-MM-DD HH:MM:SS' format to SQL."""
    captured_params = {}

    async def _capture_execute(query, params=None):
        if params:
            captured_params.update(params)
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        return mock_result

    one_record_db.execute = _capture_execute

    monkeypatch.setattr(
        "sentinel.agents.discovery_agent.score_cases_bert",
        AsyncMock(return_value=[]),
    )

    await discovery_agent.run(one_record_state, one_record_db)

    assert "date_from" in captured_params, "SQL must include date_from param"
    assert "date_to" in captured_params, "SQL must include date_to param"
    assert captured_params["date_from"] == "2024-01-03 00:00:00", (
        f"Expected '2024-01-03 00:00:00', got '{captured_params.get('date_from')}'"
    )
    assert captured_params["date_to"] == "2024-01-10 23:59:59", (
        f"Expected '2024-01-10 23:59:59', got '{captured_params.get('date_to')}'"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Investigation: required output keys with one case
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_investigation_with_one_case(one_record_state, one_record_db, monkeypatch):
    """Investigation agent must return evidence_items, investigation_sufficient, messages."""
    one_record_state["relevant_case_ids"] = ["CASE-TEST-001"]
    one_record_state["case_count"] = 1
    one_record_state["discovery_confidence"] = 0.85

    # Mock provenance store (injected via ProvenanceStore.__init__)
    # content must be a dict (not json.dumps string) — matches what asyncpg returns for JSONB
    g = nx.DiGraph()
    g.add_node("decision-CASE-TEST-001", node_type="prov:Entity",
               content={"case_id": "CASE-TEST-001", "content_hash": "sha256-abc123"})
    mock_store = AsyncMock()
    mock_store.build_graph = AsyncMock(return_value=g)
    mock_store.verify_hashes_batch = AsyncMock(return_value={"decision-CASE-TEST-001": True})

    monkeypatch.setattr(
        "sentinel.agents.investigation_agent.ProvenanceStore",
        MagicMock(return_value=mock_store),
    )
    monkeypatch.setattr(
        "sentinel.agents.investigation_agent.llm_chat",
        AsyncMock(return_value=_llm_response(
            '{"investigation_sufficient": true, "investigation_iterations": 1, '
            '"summary": "One denied credit decision found with valid provenance."}'
        )),
    )

    result = await investigation_agent.run(one_record_state, one_record_db)

    assert "evidence_items" in result, "Missing evidence_items"
    assert "investigation_sufficient" in result, "Missing investigation_sufficient"
    assert "messages" in result, "Missing messages"
    assert isinstance(result["evidence_items"], list)
    assert isinstance(result["investigation_sufficient"], bool)
    assert isinstance(result["messages"], list)
    assert result["messages"][0]["agent"] == "investigation_agent"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Investigation: batch hash verify called once (not N times)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_investigation_batch_hash_verify(one_record_state, one_record_db, monkeypatch):
    """verify_hashes_batch must be called exactly once regardless of node count."""
    one_record_state["relevant_case_ids"] = ["CASE-TEST-001"]

    g = nx.DiGraph()
    g.add_node("decision-CASE-TEST-001", node_type="prov:Entity",
               content={"case_id": "CASE-TEST-001", "content_hash": "sha256-abc123"})
    mock_store = AsyncMock()
    mock_store.build_graph = AsyncMock(return_value=g)
    mock_store.verify_hashes_batch = AsyncMock(return_value={"decision-CASE-TEST-001": True})

    monkeypatch.setattr(
        "sentinel.agents.investigation_agent.ProvenanceStore",
        MagicMock(return_value=mock_store),
    )
    monkeypatch.setattr(
        "sentinel.agents.investigation_agent.llm_chat",
        AsyncMock(return_value=_llm_response(
            '{"investigation_sufficient": true, "investigation_iterations": 1, "summary": "ok"}'
        )),
    )

    await investigation_agent.run(one_record_state, one_record_db)

    # Exactly one batch call — not one per node
    assert mock_store.verify_hashes_batch.call_count == 1, (
        f"Expected exactly 1 batch call, got {mock_store.verify_hashes_batch.call_count}"
    )
    # The old per-node verify_hash must NOT be called
    assert mock_store.verify_hash.call_count == 0, (
        f"verify_hash (N+1 pattern) was called {mock_store.verify_hash.call_count} times — "
        "use verify_hashes_batch instead"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — Legal: verdict and risk in allowed values
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_legal_returns_verdict_and_risk(one_record_state, monkeypatch):
    """Legal agent must return compliance_verdict and regulatory_risk in allowed sets."""
    one_record_state["relevant_case_ids"] = ["CASE-TEST-001"]
    one_record_state["case_count"] = 1
    one_record_state["discovery_confidence"] = 0.85
    one_record_state["evidence_items"] = []

    monkeypatch.setattr(
        "sentinel.agents.legal_agent.llm_chat",
        AsyncMock(return_value=_llm_response(json.dumps({
            "applicable_regulations": ["ECOA Section 202.6"],
            "compliance_verdict": "COMPLIANT",
            "legal_citations": ["Equal Credit Opportunity Act requires non-discriminatory lending."],
            "regulatory_risk": "LOW",
            "analysis_summary": "No discriminatory patterns found in the 7-day window.",
        }))),
    )
    monkeypatch.setattr(
        "sentinel.agents.legal_agent._inner_search_regulations",
        AsyncMock(return_value=[{
            "regulation_name": "ECOA",
            "section": "202.6",
            "text": "Creditors shall not discriminate on a prohibited basis.",
        }]),
    )

    result = await legal_agent.run(one_record_state)

    assert "compliance_verdict" in result, "Missing compliance_verdict"
    assert "regulatory_risk" in result, "Missing regulatory_risk"
    assert "messages" in result, "Missing messages"

    assert result["compliance_verdict"] in ("COMPLIANT", "VIOLATION", "UNCERTAIN"), (
        f"Unexpected verdict: {result['compliance_verdict']}"
    )
    assert result["regulatory_risk"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL"), (
        f"Unexpected risk level: {result['regulatory_risk']}"
    )
    assert result["messages"][0]["agent"] == "legal_agent"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6 — Bias: required output keys
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_bias_returns_required_keys(one_record_state, one_record_db, monkeypatch):
    """Bias agent must return bias_detected, bias_confidence, statistical_findings, messages."""
    one_record_state["relevant_case_ids"] = ["CASE-TEST-001"]

    # Mock domain config to have bias dimensions
    monkeypatch.setattr(
        "sentinel.agents.bias_detection_agent.get_domain_config",
        MagicMock(return_value={
            "bias_config": {"dimensions": ["race", "gender"]},
            "decision_schema": {
                "outcome_field": "outcome",
                "outcome_values": ["approved"],
            },
        }),
    )

    result = await bias_detection_agent.run(one_record_state, one_record_db)

    assert "bias_detected" in result, "Missing bias_detected"
    assert "bias_confidence" in result, "Missing bias_confidence"
    assert "statistical_findings" in result, "Missing statistical_findings"
    assert "messages" in result, "Missing messages"

    assert isinstance(result["bias_detected"], bool)
    assert isinstance(result["bias_confidence"], float)
    assert isinstance(result["statistical_findings"], list)
    assert result["messages"][0]["agent"] == "bias_detection_agent"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7 — Edge routing: verdict alone is enough to reach report (no hitl loop)
# ══════════════════════════════════════════════════════════════════════════════

def test_evidence_assembly_routes_to_report_with_verdict(one_record_state):
    """
    When legal agent produced a verdict but investigation found 0 evidence items,
    route_after_evidence_assembly must return 'report' — not 'hitl'.
    This was the root cause of the Interrupt serialization crash.
    """
    one_record_state["compliance_verdict"] = "COMPLIANT"
    one_record_state["regulatory_risk"] = "LOW"
    one_record_state["bias_detected"] = False
    one_record_state["discovery_confidence"] = 0.85
    one_record_state["evidence_items"] = []           # No provenance evidence
    one_record_state["investigation_sufficient"] = False

    route = route_after_evidence_assembly(one_record_state)
    assert route == "report", (
        f"Expected 'report' (legal verdict present), got '{route}'. "
        "This would cause a GraphInterrupt → JSON serialization crash."
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8 — Report: required output keys
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_report_returns_final_report(one_record_state, one_record_db, monkeypatch):
    """Report agent must return final_report, report_confidence, hitl_required, messages."""
    one_record_state["relevant_case_ids"] = ["CASE-TEST-001"]
    one_record_state["case_count"] = 1
    one_record_state["compliance_verdict"] = "COMPLIANT"
    one_record_state["regulatory_risk"] = "LOW"
    one_record_state["bias_detected"] = False
    one_record_state["applicable_regulations"] = ["ECOA Section 202.6"]
    one_record_state["evidence_items"] = [
        EvidenceItem(
            evidence_id="ev-001",
            description="Decision record",
            provenance_node_id="decision-CASE-TEST-001",
            trust_score=0.80,
            source_type="decision_record",
        )
    ]
    one_record_state["investigation_sufficient"] = True

    report_text = (
        "## SENTINEL Compliance Report — INV-TEST-001\n\n"
        "**Executive Summary:** The 7-day review (Jan 3–10, 2024) found 1 credit decision "
        "that complies with ECOA requirements. No discriminatory patterns detected.\n\n"
        "**Verdict:** COMPLIANT — LOW regulatory risk."
    )

    monkeypatch.setattr(
        "sentinel.agents.report_agent.llm_chat",
        AsyncMock(return_value=_llm_response(report_text)),
    )
    # Mock output guard — set all fields explicitly so log_agent_event can json.dumps them
    mock_guard = MagicMock()
    mock_guard.safe = True
    mock_guard.block_reason = None
    mock_guard.hitl_required = False
    mock_guard.hitl_reason = None
    mock_guard.content = report_text
    mock_guard.content_hash = "abc123def456789012345678901234ab"  # 32-char hex string
    monkeypatch.setattr(
        "sentinel.agents.report_agent.validate_output",
        AsyncMock(return_value=mock_guard),
    )

    result = await report_agent.run(one_record_state, one_record_db)

    assert "final_report" in result, "Missing final_report"
    assert "report_confidence" in result, "Missing report_confidence"
    assert "hitl_required" in result, "Missing hitl_required"
    assert "messages" in result, "Missing messages"

    assert isinstance(result["hitl_required"], bool)
    assert isinstance(result["report_confidence"], float)
    assert result["messages"][0]["agent"] == "report_agent"

    # When guard passes, final_report should be populated
    if not result["hitl_required"]:
        assert result["final_report"], "final_report should be non-empty when hitl not required"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9 — Full pipeline state handoff: messages accumulate, verdict preserved
# ══════════════════════════════════════════════════════════════════════════════

def test_full_pipeline_state_handoff(one_record_state):
    """
    Simulate state updates from each agent and verify:
    - messages list grows (operator.add reducer)
    - compliance_verdict uses _last (latest wins, not clobbered)
    - bias_detected uses _last_bool (explicit False doesn't get dropped)
    - evidence_items accumulate (operator.add reducer)
    """
    from operator import add as op_add
    from sentinel.state.investigation_state import _last, _last_bool

    # Simulate discovery output
    discovery_out = {
        "relevant_case_ids": ["CASE-TEST-001"],
        "case_count": 1,
        "discovery_confidence": 0.85,
        "status": "investigating",
        "messages": [{"agent": "discovery_agent", "event": "complete"}],
    }

    # Simulate legal output (parallel)
    legal_out = {
        "compliance_verdict": "COMPLIANT",
        "regulatory_risk": "LOW",
        "status": "analyzing",
        "messages": [{"agent": "legal_agent", "event": "complete", "verdict": "COMPLIANT"}],
    }

    # Simulate investigation output (parallel)
    investigation_out = {
        "evidence_items": [
            EvidenceItem(evidence_id="ev-001", description="Decision",
                         provenance_node_id="decision-CASE-TEST-001",
                         trust_score=0.80, source_type="decision_record")
        ],
        "investigation_sufficient": True,
        "status": "investigating",
        "messages": [{"agent": "investigation_agent", "event": "complete", "evidence_count": 1}],
    }

    # Simulate bias output (parallel)
    bias_out = {
        "bias_detected": False,
        "bias_confidence": 0.88,
        "statistical_findings": [],
        "status": "analyzing",
        "messages": [{"agent": "bias_detection_agent", "event": "complete"}],
    }

    # Apply operator.add to messages (as LangGraph would)
    combined_messages = op_add(
        op_add(
            op_add(discovery_out["messages"], legal_out["messages"]),
            investigation_out["messages"],
        ),
        bias_out["messages"],
    )

    # Apply _last to compliance_verdict (legal agent wins)
    final_verdict = _last(None, legal_out["compliance_verdict"])

    # Apply _last_bool to bias_detected (explicit False is preserved)
    final_bias = _last_bool(True, bias_out["bias_detected"])

    # Apply operator.add to evidence_items
    combined_evidence = op_add([], investigation_out["evidence_items"])

    # Assertions
    assert len(combined_messages) == 4, (
        f"Expected 4 agent messages (one per agent), got {len(combined_messages)}"
    )
    agents_in_messages = [m["agent"] for m in combined_messages]
    assert "discovery_agent" in agents_in_messages
    assert "legal_agent" in agents_in_messages
    assert "investigation_agent" in agents_in_messages
    assert "bias_detection_agent" in agents_in_messages

    assert final_verdict == "COMPLIANT", (
        f"compliance_verdict should be 'COMPLIANT' after _last reducer, got '{final_verdict}'"
    )
    assert final_bias is False, (
        f"bias_detected should be False after _last_bool reducer, got {final_bias}"
    )
    assert len(combined_evidence) == 1, (
        f"evidence_items should have 1 item after operator.add, got {len(combined_evidence)}"
    )
