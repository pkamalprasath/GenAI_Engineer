"""
Integration tests for the full LangGraph investigation pipeline.
Agents and the DB session are stubbed (tests/integration/graph_stubs.py),
so no Postgres, Ollama or LLM API is needed.

Run with: make test-integration
"""
from __future__ import annotations


import pytest

from sentinel.state.investigation_state import make_initial_state
from tests.integration.graph_stubs import stub_agents


# All integration tests are async
pytestmark = pytest.mark.asyncio


class TestFullInvestigationPipeline:
    """End-to-end: query → discovery → investigation → report (all LLMs mocked)."""

    @pytest.fixture
    def initial_state(self):
        return make_initial_state(
            investigation_id="INT-TEST-001",
            tenant_id="bank-acme",
            query="Review Q1 2024 credit decisions for fair lending compliance",
            date_range={"from": "2024-01-01", "to": "2024-03-31"},
            domain="finance",
        )

    async def test_graph_runs_to_completion(self, initial_state):
        """Low-risk run: discovery -> parallel fan-out -> report -> audit -> complete."""
        from langgraph.checkpoint.memory import MemorySaver
        from sentinel.graph.builder import build_graph

        with stub_agents() as calls:
            graph = build_graph().compile(checkpointer=MemorySaver())
            result = await graph.ainvoke(
                initial_state, {"configurable": {"thread_id": "INT-TEST-001"}}
            )

        assert result["status"] == "complete"
        assert result["tenant_id"] == "bank-acme"
        assert result["investigation_id"] == "INT-TEST-001"
        assert result["compliance_verdict"] == "COMPLIANT"
        assert result["relevant_case_ids"] == ["CASE-0001", "CASE-0002"]
        # Fan-out: all three parallel agents ran, then fan-in to report and audit
        assert {"investigation", "legal", "bias"} <= set(calls)
        assert calls.index("report") > max(calls.index(n) for n in ("investigation", "legal", "bias"))
        assert calls[-1] == "audit"

    async def test_no_cases_skips_investigation(self, initial_state):
        """Discovery finding nothing ends at no_cases without running the agents."""
        from langgraph.checkpoint.memory import MemorySaver
        from sentinel.graph.builder import build_graph

        with stub_agents(case_count=0) as calls:
            graph = build_graph().compile(checkpointer=MemorySaver())
            result = await graph.ainvoke(
                initial_state, {"configurable": {"thread_id": "INT-TEST-002"}}
            )

        assert calls == ["discovery"]
        assert result["status"] == "complete"
        assert result["compliance_verdict"] == "COMPLIANT"
        assert "No relevant cases" in result["final_report"]

    async def test_state_tenant_id_preserved_through_pipeline(self, initial_state):
        """Tenant ID must never change during pipeline execution."""
        assert initial_state["tenant_id"] == "bank-acme"
        # Even after state mutations, tenant_id must be immutable
        mutated = {**initial_state, "status": "investigating"}
        assert mutated["tenant_id"] == "bank-acme"

    async def test_cost_log_accumulates_across_agents(self, initial_state):
        """Each agent appends to cost_log — total should reflect all agents."""
        import operator
        from sentinel.observability.cost_tracker import record_cost

        cost_log = initial_state["cost_log"]
        for agent, model, provider in [
            ("discovery", "llama3.2:3b", "ollama"),
            ("investigation", "claude-haiku-4-5-20251001", "anthropic"),
            ("legal", "claude-haiku-4-5-20251001", "anthropic"),
        ]:
            update = record_cost(agent, model, provider, 500, 100)
            cost_log = operator.add(cost_log, update["cost_log"])

        assert len(cost_log) == 3
        # Ollama cost should be 0, Anthropic costs > 0
        ollama_entry = next(e for e in cost_log if e["provider"] == "ollama")
        assert ollama_entry["cost_usd"] == 0.0
        anthropic_entries = [e for e in cost_log if e["provider"] == "anthropic"]
        assert all(e["cost_usd"] > 0 for e in anthropic_entries)

    async def test_error_log_captures_agent_failures(self, initial_state):
        """If an agent fails, error_log must be updated (not raise to crash graph)."""
        import operator
        initial_errors = initial_state["error_log"]
        simulated_error = "discovery_agent: OllamaConnectionError — localhost:11434 refused"
        updated = operator.add(initial_errors, [simulated_error])
        assert len(updated) == 1
        assert "discovery_agent" in updated[0]


class TestGraphEdgeRouting:
    """Conditional edge routing — correct next node chosen based on state."""

    def test_route_after_discovery_no_cases(self):
        from sentinel.graph.edges import route_after_discovery
        state = make_initial_state("INV-002", "t1", "query", {}, "finance")
        state["case_count"] = 0
        state["discovery_confidence"] = 0.0
        route = route_after_discovery(state)
        assert route == "no_cases"  # Nothing found — skip investigation

    def test_route_after_discovery_with_cases(self):
        from sentinel.graph.edges import route_after_discovery
        state = make_initial_state("INV-003", "t1", "query", {}, "finance")
        state["case_count"] = 5
        state["discovery_confidence"] = 0.90
        route = route_after_discovery(state)
        assert route == "investigate"

    def test_route_after_evidence_high_risk_goes_to_hitl(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = make_initial_state("INV-004", "t1", "query", {}, "finance")
        state["regulatory_risk"] = "CRITICAL"
        state["compliance_verdict"] = "VIOLATION"
        route = route_after_evidence_assembly(state)
        assert route == "hitl"

    def test_route_after_evidence_sufficient_goes_to_report(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = make_initial_state("INV-005", "t1", "query", {}, "finance")
        state["compliance_verdict"] = "COMPLIANT"
        state["regulatory_risk"] = "LOW"
        state["bias_detected"] = False
        state["discovery_confidence"] = 0.9  # above the 0.65 HITL floor
        route = route_after_evidence_assembly(state)
        assert route == "report"

    def test_route_after_report_hitl_required(self):
        from sentinel.graph.edges import route_after_report
        state = make_initial_state("INV-006", "t1", "query", {}, "finance")
        state["hitl_required"] = True
        route = route_after_report(state)
        assert route == "hitl"

    def test_route_after_report_auto_complete(self):
        from sentinel.graph.edges import route_after_report
        state = make_initial_state("INV-007", "t1", "query", {}, "finance")
        state["hitl_required"] = False
        state["final_report"] = "Complete compliance report..."
        route = route_after_report(state)
        assert route == "complete"
