"""
Per-agent, per-tenant token and cost accounting.

Cost table is maintained here and updated quarterly.
Every agent node calls record_cost() before returning its state update.
Aggregates are queryable via the analytics API for per-tenant billing reports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Cost per 1,000 tokens (input, output) — update quarterly from provider pricing pages
# Ollama models have zero API cost — only local compute (not tracked in USD)
_COST_TABLE: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.00025, "output": 0.00125},
    "claude-sonnet-4-6":         {"input": 0.003,   "output": 0.015},
    "gpt-4o-mini":               {"input": 0.00015, "output": 0.0006},
    "gpt-4o":                    {"input": 0.0025,  "output": 0.01},
    # Local models — zero API cost
    "llama3.2:3b":               {"input": 0.0,     "output": 0.0},
    "nomic-embed-text":          {"input": 0.0,     "output": 0.0},
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a single LLM call. Returns 0.0 for unknown models."""
    pricing = _COST_TABLE.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])
    return round(cost, 6)


def record_cost(
    agent: str,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    state_total: float = 0.0,
) -> dict:
    """
    Build the state update dict that appends a CostRecord to cost_log.
    Call this at the end of every agent node before returning state.

    Returns a partial state dict ready to be merged by LangGraph.
    """
    cost = compute_cost(model, input_tokens, output_tokens)
    record = {
        "agent": agent,
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        '{"event":"llm_call","agent":"%s","model":"%s","tokens_in":%d,"tokens_out":%d,"cost_usd":%.6f}',
        agent, model, input_tokens, output_tokens, cost,
    )
    return {
        "cost_log": [record],
        "total_cost_usd": round(state_total + cost, 6),
    }


def summarize_costs(cost_log: list[dict]) -> dict:
    """
    Aggregate cost_log into a per-agent summary with top-level totals.
    Used by dashboard analytics and API cost endpoint.
    """
    per_agent: dict[str, dict] = {}
    total_cost = 0.0
    total_tokens = 0
    provider_costs: dict[str, float] = {}

    for record in cost_log:
        agent = record["agent"]
        provider = record.get("provider", "unknown")
        cost = record.get("cost_usd", 0.0)
        tokens = record.get("input_tokens", 0) + record.get("output_tokens", 0)

        if agent not in per_agent:
            per_agent[agent] = {"total_cost_usd": 0.0, "total_tokens": 0, "calls": 0}
        per_agent[agent]["total_cost_usd"] += cost
        per_agent[agent]["total_tokens"] += tokens
        per_agent[agent]["calls"] += 1

        total_cost += cost
        total_tokens += tokens
        provider_costs[provider] = provider_costs.get(provider, 0.0) + cost

    total_input = sum(r.get("input_tokens", 0) for r in cost_log)
    total_output = sum(r.get("output_tokens", 0) for r in cost_log)

    return {
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "by_agent": {
            agent: {"cost_usd": round(d["total_cost_usd"], 6), "total_tokens": d["total_tokens"], "calls": d["calls"]}
            for agent, d in per_agent.items()
        },
        "by_provider": {
            p: {"cost_usd": round(c, 6)} for p, c in provider_costs.items()
        },
    }
