"""
Performance tests — p50/p95 latency targets per agent node.
LLMs mocked — measures Python overhead + graph routing, not API latency.
Targets defined in configs/agents.yaml.

Run with: make test-performance
Note: CI skips these by default (pytest.mark.performance).
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.state.investigation_state import make_initial_state

pytestmark = [pytest.mark.asyncio, pytest.mark.performance]

# Latency targets (seconds) — from configs/agents.yaml
# These measure node execution overhead, not LLM call time
LATENCY_TARGETS = {
    "input_guard": {"p50": 0.10, "p95": 0.50},     # PII + OWASP scan
    "graph_routing": {"p50": 0.005, "p95": 0.020},  # Conditional edge decisions
    "cost_tracker": {"p50": 0.001, "p95": 0.005},   # Cost math + state update
    "provenance_schema": {"p50": 0.001, "p95": 0.005},  # SHA-256 hash computation
}

SAMPLE_SIZE = 20  # Enough for stable p95 without being slow


async def measure_latency(fn: Callable, n: int = SAMPLE_SIZE) -> dict:
    """Run fn n times, return p50 and p95 latency in seconds."""
    times = []
    for _ in range(n):
        start = time.perf_counter()
        if asyncio.iscoroutinefunction(fn):
            await fn()
        else:
            fn()
        times.append(time.perf_counter() - start)
    times.sort()
    p50 = statistics.median(times)
    p95 = times[int(len(times) * 0.95)]
    return {"p50": p50, "p95": p95, "times": times}


class TestInputGuardLatency:
    """Input guard must complete within latency budget even for complex inputs."""

    async def test_sanitize_input_p50(self):
        from sentinel.guardrails.input_guard import sanitize_input

        def run():
            sanitize_input(
                "Review Q1 2024 credit decisions for fair lending compliance",
                tenant_id="bank-acme",
            )

        metrics = await measure_latency(run)
        assert metrics["p50"] <= LATENCY_TARGETS["input_guard"]["p50"], (
            f"input_guard p50={metrics['p50']:.3f}s exceeds target "
            f"{LATENCY_TARGETS['input_guard']['p50']}s"
        )

    async def test_sanitize_input_p95(self):
        from sentinel.guardrails.input_guard import sanitize_input

        def run():
            sanitize_input(
                "Review Q1 2024 credit decisions for fair lending compliance " * 5,
                tenant_id="bank-acme",
            )

        metrics = await measure_latency(run)
        assert metrics["p95"] <= LATENCY_TARGETS["input_guard"]["p95"], (
            f"input_guard p95={metrics['p95']:.3f}s exceeds target "
            f"{LATENCY_TARGETS['input_guard']['p95']}s"
        )


class TestGraphRoutingLatency:
    """Conditional edge decisions are pure Python — must be sub-millisecond."""

    async def test_route_after_discovery_latency(self):
        from sentinel.graph.edges import route_after_discovery
        state = make_initial_state("PERF-001", "t1", "q", {}, "finance")
        state["case_count"] = 5
        state["discovery_confidence"] = 0.90

        def run():
            route_after_discovery(state)

        metrics = await measure_latency(run, n=100)
        assert metrics["p50"] <= LATENCY_TARGETS["graph_routing"]["p50"], (
            f"route_after_discovery p50={metrics['p50']*1000:.2f}ms"
        )

    async def test_route_after_evidence_latency(self):
        from sentinel.graph.edges import route_after_evidence_assembly
        state = make_initial_state("PERF-002", "t1", "q", {}, "finance")
        state["investigation_sufficient"] = True
        state["regulatory_risk"] = "LOW"
        state["bias_detected"] = False

        def run():
            route_after_evidence_assembly(state)

        metrics = await measure_latency(run, n=100)
        assert metrics["p50"] <= LATENCY_TARGETS["graph_routing"]["p50"]


class TestCostTrackerLatency:
    """Cost recording must not add meaningful overhead per agent call."""

    async def test_record_cost_latency(self):
        from sentinel.observability.cost_tracker import record_cost

        def run():
            record_cost(
                agent="investigation",
                model="claude-haiku-4-5-20251001",
                provider="anthropic",
                input_tokens=1000,
                output_tokens=200,
            )

        metrics = await measure_latency(run, n=100)
        assert metrics["p50"] <= LATENCY_TARGETS["cost_tracker"]["p50"], (
            f"record_cost p50={metrics['p50']*1000:.3f}ms"
        )

    async def test_summarize_costs_latency_100_entries(self):
        from sentinel.observability.cost_tracker import record_cost, summarize_costs

        cost_log = []
        for i in range(100):
            update = record_cost("agent", "claude-haiku-4-5-20251001", "anthropic", 500, 100)
            cost_log.extend(update["cost_log"])

        def run():
            summarize_costs(cost_log)

        metrics = await measure_latency(run, n=20)
        # 100-entry summarization should complete under 50ms p95
        assert metrics["p95"] <= 0.050, (
            f"summarize_costs(100) p95={metrics['p95']*1000:.1f}ms > 50ms"
        )


class TestProvenanceSchemaLatency:
    """SHA-256 hash computation in ProvNode.__post_init__ must be fast."""

    async def test_prov_node_creation_latency(self):
        from sentinel.provenance.schema import NodeType, ProvNode

        content = {"case_id": "CASE-0001", "outcome": "denied", "model_version": "v2.3"}

        def run():
            ProvNode("decision-CASE-0001", NodeType.ENTITY, "bank-acme", content)

        metrics = await measure_latency(run, n=100)
        assert metrics["p50"] <= LATENCY_TARGETS["provenance_schema"]["p50"], (
            f"ProvNode creation p50={metrics['p50']*1000:.3f}ms"
        )

    async def test_graph_to_adjacency_latency_50_nodes(self):
        """Serializing a 50-node graph must complete under 100ms."""
        import networkx as nx
        from sentinel.provenance.query import graph_to_adjacency

        g = nx.DiGraph()
        for i in range(50):
            g.add_node(f"node-{i}", node_type="prov:Entity", tenant_id="bank-acme")
        for i in range(49):
            g.add_edge(f"node-{i}", f"node-{i+1}", relation="prov:used")

        def run():
            graph_to_adjacency(g)

        metrics = await measure_latency(run, n=20)
        assert metrics["p95"] <= 0.100, (
            f"graph_to_adjacency(50 nodes) p95={metrics['p95']*1000:.1f}ms > 100ms"
        )


class TestLatencyReport:
    """Generate a latency summary report for all tested components."""

    async def test_print_latency_summary(self, capsys):
        """Print p50/p95 for all components — useful for performance regression tracking."""
        from sentinel.guardrails.input_guard import sanitize_input
        from sentinel.graph.edges import route_after_discovery
        from sentinel.observability.cost_tracker import record_cost

        state = make_initial_state("PERF-REPORT", "t1", "q", {}, "finance")
        state["case_count"] = 5
        state["discovery_confidence"] = 0.90

        results = {}

        input_metrics = await measure_latency(
            lambda: sanitize_input("Review Q1 compliance", tenant_id="t1"), n=20
        )
        results["input_guard"] = input_metrics

        route_metrics = await measure_latency(
            lambda: route_after_discovery(state), n=100
        )
        results["graph_routing"] = route_metrics

        cost_metrics = await measure_latency(
            lambda: record_cost("a", "claude-haiku-4-5-20251001", "anthropic", 500, 100),
            n=100
        )
        results["cost_tracker"] = cost_metrics

        print("\n=== SENTINEL Latency Report ===")
        for component, m in results.items():
            print(
                f"  {component:25s} p50={m['p50']*1000:6.2f}ms  "
                f"p95={m['p95']*1000:6.2f}ms"
            )
        print("================================\n")

        # Just verifying the report runs without error
        assert len(results) == 3
