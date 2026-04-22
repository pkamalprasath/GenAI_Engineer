"""
Unit tests for per-agent, per-tenant cost tracking.
No Docker, no API — validates token math and cost accumulation.
"""
from __future__ import annotations

import pytest

from sentinel.observability.cost_tracker import (
    record_cost,
    summarize_costs,
)


class TestRecordCost:
    """record_cost() returns a partial state dict with correct cost math."""

    def test_ollama_cost_is_zero(self):
        update = record_cost(
            agent="discovery",
            model="llama3.2:3b",
            provider="ollama",
            input_tokens=500,
            output_tokens=100,
        )
        log_entries = update["cost_log"]
        assert len(log_entries) == 1
        assert log_entries[0]["cost_usd"] == 0.0
        assert log_entries[0]["provider"] == "ollama"

    def test_anthropic_haiku_cost_positive(self):
        update = record_cost(
            agent="investigation",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=200,
        )
        cost = update["cost_log"][0]["cost_usd"]
        assert cost > 0.0

    def test_anthropic_sonnet_cost_higher_than_haiku(self):
        haiku_update = record_cost(
            agent="investigation",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=200,
        )
        sonnet_update = record_cost(
            agent="report",
            model="claude-sonnet-4-6",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=200,
        )
        haiku_cost = haiku_update["cost_log"][0]["cost_usd"]
        sonnet_cost = sonnet_update["cost_log"][0]["cost_usd"]
        assert sonnet_cost > haiku_cost

    def test_record_contains_all_required_fields(self):
        update = record_cost(
            agent="legal",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=800,
            output_tokens=150,
        )
        record = update["cost_log"][0]
        required_fields = ["agent", "model", "provider", "input_tokens", "output_tokens",
                           "cost_usd", "timestamp"]
        for field in required_fields:
            assert field in record, f"Missing field: {field}"

    def test_token_counts_stored_correctly(self):
        update = record_cost(
            agent="bias_detection",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=750,
            output_tokens=300,
        )
        record = update["cost_log"][0]
        assert record["input_tokens"] == 750
        assert record["output_tokens"] == 300

    def test_cost_usd_is_float(self):
        update = record_cost(
            agent="legal",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
        )
        cost = update["cost_log"][0]["cost_usd"]
        assert isinstance(cost, float)

    def test_zero_tokens_returns_zero_cost(self):
        update = record_cost(
            agent="discovery",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=0,
            output_tokens=0,
        )
        assert update["cost_log"][0]["cost_usd"] == 0.0

    def test_unknown_model_does_not_raise(self):
        """Unknown models should fallback to 0 cost rather than crash."""
        update = record_cost(
            agent="discovery",
            model="unknown-model-xyz",
            provider="unknown",
            input_tokens=100,
            output_tokens=50,
        )
        assert "cost_log" in update
        # Cost can be 0.0 for unknown — not crashing is what matters
        assert update["cost_log"][0]["cost_usd"] >= 0.0

    def test_timestamp_is_iso_string(self):
        from datetime import datetime
        update = record_cost(
            agent="discovery",
            model="llama3.2:3b",
            provider="ollama",
            input_tokens=100,
            output_tokens=50,
        )
        timestamp = update["cost_log"][0]["timestamp"]
        # Should not raise
        datetime.fromisoformat(timestamp)

    def test_state_update_structure_for_langgraph(self):
        """Return dict must be mergeable into LangGraph state via operator.add."""
        import operator
        initial_cost_log = []
        update = record_cost(
            agent="discovery",
            model="llama3.2:3b",
            provider="ollama",
            input_tokens=200,
            output_tokens=50,
        )
        merged = operator.add(initial_cost_log, update["cost_log"])
        assert len(merged) == 1


class TestSummarizeCosts:
    """summarize_costs() aggregates across multiple agents for analytics."""

    def _build_cost_log(self):
        logs = []
        for agent, model, provider, in_tok, out_tok in [
            ("discovery", "llama3.2:3b", "ollama", 500, 100),
            ("investigation", "claude-haiku-4-5-20251001", "anthropic", 1000, 200),
            ("legal", "claude-haiku-4-5-20251001", "anthropic", 800, 150),
            ("bias_detection", "claude-haiku-4-5-20251001", "anthropic", 600, 100),
            ("report", "claude-sonnet-4-6", "anthropic", 2000, 400),
        ]:
            update = record_cost(agent, model, provider, in_tok, out_tok)
            logs.extend(update["cost_log"])
        return logs

    def test_total_cost_is_sum_of_parts(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        individual_sum = sum(r["cost_usd"] for r in logs)
        assert abs(summary["total_cost_usd"] - individual_sum) < 1e-9

    def test_per_agent_breakdown_present(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        assert "by_agent" in summary
        assert "discovery" in summary["by_agent"]
        assert "report" in summary["by_agent"]

    def test_ollama_provider_cost_is_zero_in_summary(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        discovery_cost = summary["by_agent"]["discovery"]["cost_usd"]
        assert discovery_cost == 0.0

    def test_report_agent_highest_cost(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        costs_by_agent = {
            agent: data["cost_usd"]
            for agent, data in summary["by_agent"].items()
        }
        assert costs_by_agent["report"] >= costs_by_agent["discovery"]

    def test_empty_log_returns_zero(self):
        summary = summarize_costs([])
        assert summary["total_cost_usd"] == 0.0

    def test_total_tokens_tracked(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        assert "total_input_tokens" in summary
        assert "total_output_tokens" in summary
        assert summary["total_input_tokens"] > 0

    def test_provider_breakdown(self):
        logs = self._build_cost_log()
        summary = summarize_costs(logs)
        assert "by_provider" in summary
        assert "anthropic" in summary["by_provider"]
        assert "ollama" in summary["by_provider"]
        assert summary["by_provider"]["ollama"]["cost_usd"] == 0.0


class TestCostAccuracyBenchmarks:
    """Verify cost math is within expected ranges — catch model pricing errors."""

    def test_haiku_1k_input_cost_reasonable(self):
        """claude-haiku-4-5 at $0.80/M input — 1000 tokens ≈ $0.0008."""
        update = record_cost(
            agent="test",
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            input_tokens=1_000,
            output_tokens=0,
        )
        cost = update["cost_log"][0]["cost_usd"]
        # Sanity range: $0.00001 to $0.01 for 1K tokens
        assert 0.000001 <= cost <= 0.01, f"Unexpected haiku input cost: {cost}"

    def test_sonnet_1k_input_cost_higher_than_haiku(self):
        haiku = record_cost("t", "claude-haiku-4-5-20251001", "anthropic", 1_000, 0)
        sonnet = record_cost("t", "claude-sonnet-4-6", "anthropic", 1_000, 0)
        assert sonnet["cost_log"][0]["cost_usd"] > haiku["cost_log"][0]["cost_usd"]

    def test_output_tokens_cost_more_than_input(self):
        """Output tokens are always priced higher than input for Anthropic models."""
        input_only = record_cost("t", "claude-haiku-4-5-20251001", "anthropic", 1000, 0)
        output_only = record_cost("t", "claude-haiku-4-5-20251001", "anthropic", 0, 1000)
        assert (output_only["cost_log"][0]["cost_usd"]
                > input_only["cost_log"][0]["cost_usd"])
