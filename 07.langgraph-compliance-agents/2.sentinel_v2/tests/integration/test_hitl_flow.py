"""
Integration tests for HITL escalation + resume flow.

Runs the real compiled LangGraph with an in-memory checkpointer. Agents and the
DB session are stubbed, so no Postgres, Ollama or LLM API is needed.

Validates: high-risk results route to hitl_review, the graph pauses via
interrupt(), state survives in the checkpointer, and resuming with the human
decision completes the investigation with reviewer_id preserved.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from sentinel.state.investigation_state import make_initial_state
from tests.integration.graph_stubs import stub_agents

pytestmark = pytest.mark.asyncio


def _state(inv_id: str = "HITL-TEST-001"):
    return make_initial_state(
        investigation_id=inv_id,
        tenant_id="bank-acme",
        query="Review Q1 2024 credit decisions",
        date_range={"from": "2024-01-01", "to": "2024-03-31"},
        domain="finance",
    )


class TestHITLRouting:
    """Routing decisions that send an investigation to human review."""

    def test_critical_risk_routes_to_hitl(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = _state()
        state["compliance_verdict"] = "VIOLATION"
        state["regulatory_risk"] = "CRITICAL"
        assert route_after_evidence_assembly(state) == "hitl"

    def test_bias_detected_routes_to_hitl(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = _state()
        state["compliance_verdict"] = "COMPLIANT"
        state["regulatory_risk"] = "MEDIUM"
        state["bias_detected"] = True
        assert route_after_evidence_assembly(state) == "hitl"

    def test_no_verdict_and_no_evidence_routes_to_hitl(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        assert route_after_evidence_assembly(_state()) == "hitl"

    def test_after_human_review_always_completes(self):
        """The human made the call, so routing after review always ends the run."""
        from sentinel.graph.edges import route_after_hitl
        for decision in ("approve_draft", "close_investigation", ""):
            state = _state()
            state["human_decision"] = decision
            assert route_after_hitl(state) == "complete"


class TestHITLNode:
    async def test_hitl_node_applies_human_decision(self):
        """hitl_node returns the reviewer's decision and marks the run complete."""
        from sentinel.graph import builder
        human = {"response": "approve_draft", "reviewer_id": "compliance-officer-007"}
        with patch.object(builder, "interrupt", return_value=human) as mock_interrupt:
            result = await builder.hitl_node(_state())

        payload = mock_interrupt.call_args.args[0]
        assert payload["investigation_id"] == "HITL-TEST-001"
        assert "approve_draft" in payload["action_options"]
        assert result["status"] == "complete"
        assert result["hitl_required"] is False
        assert result["reviewer_id"] == "compliance-officer-007"
        assert result["human_decision"] == "approve_draft"


class TestHITLPauseAndResume:
    """End-to-end through the compiled graph: pause at interrupt, then resume."""

    async def test_graph_pauses_then_resumes_with_reviewer(self):
        from sentinel.graph.builder import build_graph

        with stub_agents(regulatory_risk="CRITICAL", bias_detected=True) as calls:
            graph = build_graph().compile(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "HITL-E2E-001"}}

            paused = await graph.ainvoke(_state("HITL-E2E-001"), config)
            assert "__interrupt__" in paused, "graph should pause for human review"
            snapshot = await graph.aget_state(config)
            assert snapshot.next == ("hitl_review",)
            assert snapshot.values["tenant_id"] == "bank-acme"
            assert "report" not in calls  # high risk skips auto-report

            final = await graph.ainvoke(
                Command(resume={"response": "approve_draft", "reviewer_id": "reviewer-001"}),
                config,
            )

        assert final["status"] == "complete"
        assert final["reviewer_id"] == "reviewer-001"
        assert final["human_decision"] == "approve_draft"
        assert final["tenant_id"] == "bank-acme"
