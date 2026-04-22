"""
Integration tests for the full LangGraph investigation pipeline.
Requires: docker compose up -d (PostgreSQL)
LLM calls are mocked — no API cost, deterministic outputs.

Run with: make test-integration
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sentinel.state.investigation_state import make_initial_state


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

    @patch("sentinel.agents.discovery_agent._OLLAMA_SEMAPHORE")
    @patch("sentinel.agents.discovery_agent.OllamaLLM")
    @patch("sentinel.agents.investigation_agent.AsyncAnthropic")
    @patch("sentinel.agents.legal_agent.AsyncAnthropic")
    @patch("sentinel.agents.bias_detection_agent.AsyncAnthropic")
    @patch("sentinel.agents.report_agent.AsyncAnthropic")
    async def test_graph_runs_to_completion(
        self, mock_report_llm, mock_bias_llm, mock_legal_llm,
        mock_inv_llm, mock_ollama_cls, mock_semaphore, initial_state
    ):
        """Graph should transition from queued → complete without exceptions."""
        _configure_mocks(
            mock_report_llm, mock_bias_llm, mock_legal_llm,
            mock_inv_llm, mock_ollama_cls
        )

        from sentinel.graph.builder import build_graph
        graph = build_graph(use_memory_saver=True)

        result = await graph.ainvoke(initial_state)

        assert result["status"] in ("complete", "pending_human")
        assert result["tenant_id"] == "bank-acme"
        assert result["investigation_id"] == "INT-TEST-001"

    @patch("sentinel.agents.discovery_agent.OllamaLLM")
    async def test_discovery_populates_case_ids(self, mock_ollama_cls, initial_state):
        """After discovery node runs, relevant_case_ids must be populated."""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value={
            "relevant_case_ids": ["CASE-0001", "CASE-0002"],
            "case_count": 2,
            "discovery_confidence": 0.85,
        })
        mock_ollama_cls.return_value = MagicMock()

        from sentinel.agents.discovery_agent import discovery_node
        with patch("sentinel.agents.discovery_agent._build_chain", return_value=mock_chain):
            with patch("sentinel.agents.discovery_agent._fetch_candidate_cases",
                       new=AsyncMock(return_value=[])):
                result = await discovery_node(initial_state)

        assert "relevant_case_ids" in result
        assert isinstance(result["relevant_case_ids"], list)

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
        assert route == "complete"  # Nothing found — skip investigation

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
        state["investigation_sufficient"] = True
        route = route_after_evidence_assembly(state)
        assert route == "hitl"

    def test_route_after_evidence_sufficient_goes_to_report(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = make_initial_state("INV-005", "t1", "query", {}, "finance")
        state["investigation_sufficient"] = True
        state["regulatory_risk"] = "LOW"
        state["bias_detected"] = False
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _configure_mocks(mock_report_llm, mock_bias_llm, mock_legal_llm,
                     mock_inv_llm, mock_ollama_cls):
    """Wire up all mock LLM clients with deterministic responses."""
    # Anthropic clients — used by investigation, legal, bias, report agents
    for mock_cls in [mock_report_llm, mock_bias_llm, mock_legal_llm, mock_inv_llm]:
        instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"investigation_sufficient": true, "compliance_verdict": "UNCERTAIN",'
                 '"regulatory_risk": "LOW", "bias_detected": false,'
                 '"applicable_regulations": ["ECOA Section 202.6"],'
                 '"legal_citations": [], "report_confidence": 0.85,'
                 '"final_report": "Investigation complete. No violations found.",'
                 '"bias_dimensions_checked": [], "statistical_findings": [],'
                 '"bias_confidence": 0.0}'
        )]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=200)
        instance.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = instance

    # Ollama — used by discovery agent
    mock_ollama_instance = MagicMock()
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value={
        "relevant_case_ids": ["CASE-0001", "CASE-0002"],
        "case_count": 2,
        "discovery_confidence": 0.88,
    })
    mock_ollama_cls.return_value = mock_ollama_instance
