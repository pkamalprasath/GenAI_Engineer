"""
Unit tests for InvestigationState schema.
Validates TypedDict fields, Annotated reducers, and make_initial_state factory.
No Docker, no API calls.
"""
from __future__ import annotations

import operator
from datetime import datetime, timezone

import pytest

from sentinel.state.investigation_state import (
    AgentHeartbeat,
    CostRecord,
    EvidenceItem,
    InvestigationState,
    ProvenanceNode,
    make_initial_state,
)


class TestMakeInitialState:
    """make_initial_state() factory — required fields populated, optional fields defaulted."""

    def test_required_fields_present(self, sample_state):
        assert sample_state["investigation_id"] == "TEST-INV-001"
        assert sample_state["tenant_id"] == "test-tenant"
        assert sample_state["query"] == "Review Q1 2024 credit decisions for fair lending compliance"
        assert sample_state["domain"] == "finance"

    def test_date_range_structure(self, sample_state):
        dr = sample_state["date_range"]
        assert "from" in dr and "to" in dr
        assert dr["from"] == "2024-01-01"
        assert dr["to"] == "2024-03-31"

    def test_list_fields_initialized_empty(self, sample_state):
        list_fields = [
            "messages", "heartbeats", "cost_log", "error_log",
            "relevant_case_ids", "provenance_nodes", "evidence_items",
            "decision_chains", "applicable_regulations", "legal_citations",
            "bias_dimensions_checked", "statistical_findings", "report_citations",
            "context_sources",
        ]
        for field in list_fields:
            assert sample_state[field] == [], f"{field} should be empty list"

    def test_numeric_defaults(self, sample_state):
        assert sample_state["case_count"] == 0
        assert sample_state["discovery_confidence"] == 0.0
        assert sample_state["total_cost_usd"] == 0.0
        assert sample_state["iteration_count"] == 0
        assert sample_state["report_confidence"] == 0.0
        assert sample_state["bias_confidence"] == 0.0

    def test_bool_defaults(self, sample_state):
        assert sample_state["investigation_sufficient"] is False
        assert sample_state["hitl_required"] is False
        assert sample_state["bias_detected"] is False
        assert sample_state["query_pii_detected"] is False

    def test_optional_fields_are_none(self, sample_state):
        assert sample_state["compliance_verdict"] is None
        assert sample_state["regulatory_risk"] is None
        assert sample_state["draft_report"] is None
        assert sample_state["final_report"] is None
        assert sample_state["hitl_reason"] is None
        assert sample_state["human_decision"] is None
        assert sample_state["reviewer_id"] is None

    def test_status_is_queued(self, sample_state):
        assert sample_state["status"] == "queued"

    def test_trigger_mode_default(self, sample_state):
        assert sample_state["trigger_mode"] == "reactive"

    def test_token_budget_is_dict(self, sample_state):
        budget = sample_state["token_budget_remaining"]
        assert isinstance(budget, dict)
        assert len(budget) > 0

    def test_max_iterations_positive(self, sample_state):
        assert sample_state["max_iterations"] > 0


class TestAnnotatedReducers:
    """Annotated[list, operator.add] fields should merge, not overwrite — safe parallel writes."""

    def test_messages_reducer(self, sample_state):
        initial = sample_state["messages"]
        msg1 = {"agent": "discovery", "text": "found 10 cases"}
        msg2 = {"agent": "legal", "text": "regulation loaded"}
        merged = operator.add(initial, [msg1])
        merged = operator.add(merged, [msg2])
        assert len(merged) == 2
        assert merged[0]["agent"] == "discovery"
        assert merged[1]["agent"] == "legal"

    def test_heartbeats_reducer_accumulates(self, sample_state):
        hb1: AgentHeartbeat = {
            "agent_name": "discovery",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "iteration": 1,
        }
        hb2: AgentHeartbeat = {
            "agent_name": "legal",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "status": "complete",
            "iteration": 1,
        }
        merged = operator.add(sample_state["heartbeats"], [hb1, hb2])
        assert len(merged) == 2

    def test_cost_log_reducer(self, sample_state):
        record: CostRecord = {
            "agent": "discovery",
            "model": "llama3.2:3b",
            "provider": "ollama",
            "input_tokens": 200,
            "output_tokens": 50,
            "cost_usd": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        merged = operator.add(sample_state["cost_log"], [record])
        assert len(merged) == 1
        assert merged[0]["cost_usd"] == 0.0

    def test_error_log_reducer(self, sample_state):
        merged = operator.add(sample_state["error_log"], ["some error"])
        merged = operator.add(merged, ["another error"])
        assert len(merged) == 2


class TestProvenanceNodeSchema:
    """ProvenanceNode TypedDict structure validation."""

    def test_valid_provenance_node(self):
        node: ProvenanceNode = {
            "node_id": "decision-CASE-0001",
            "node_type": "prov:Entity",
            "content_hash": "abc123def456",
            "tenant_id": "bank-acme",
            "metadata": {"case_id": "CASE-0001", "outcome": "denied"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        assert node["node_id"] == "decision-CASE-0001"
        assert node["node_type"] == "prov:Entity"
        assert node["tenant_id"] == "bank-acme"

    def test_provenance_node_in_state(self, sample_state_complete):
        nodes = sample_state_complete["provenance_nodes"]
        # sample_state_complete may or may not have nodes — just check it's a list
        assert isinstance(nodes, list)


class TestEvidenceItemSchema:
    """EvidenceItem TypedDict structure validation."""

    def test_valid_evidence_item(self):
        item: EvidenceItem = {
            "evidence_id": "ev-001",
            "description": "Decision record shows denial despite excellent credit",
            "provenance_node_id": "decision-CASE-0001",
            "trust_score": 0.80,
            "source_type": "decision_record",
        }
        assert item["trust_score"] == 0.80
        assert item["source_type"] == "decision_record"

    def test_evidence_items_in_complete_state(self, sample_state_complete):
        items = sample_state_complete["evidence_items"]
        assert len(items) == 2
        assert all("evidence_id" in i for i in items)
        assert all("trust_score" in i for i in items)
        assert all(0.0 <= i["trust_score"] <= 1.0 for i in items)


class TestStateProgressFixtures:
    """Validate the three state progression fixtures used by downstream agent tests."""

    def test_sample_state_is_baseline(self, sample_state):
        assert sample_state["status"] == "queued"
        assert sample_state["case_count"] == 0

    def test_sample_state_with_cases_has_discovery_output(self, sample_state_with_cases):
        assert len(sample_state_with_cases["relevant_case_ids"]) == 3
        assert sample_state_with_cases["case_count"] == 3
        assert sample_state_with_cases["discovery_confidence"] > 0.0
        assert sample_state_with_cases["status"] == "investigating"

    def test_sample_state_complete_has_verdict(self, sample_state_complete):
        assert sample_state_complete["compliance_verdict"] == "UNCERTAIN"
        assert sample_state_complete["regulatory_risk"] == "MEDIUM"
        assert sample_state_complete["investigation_sufficient"] is True
        assert sample_state_complete["bias_detected"] is False
        assert len(sample_state_complete["applicable_regulations"]) > 0
