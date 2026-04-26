"""
LangGraph StateGraph builder — assembles the SENTINEL investigation workflow.

Graph topology:
  START → discovery → [investigation + legal + bias] (parallel) → evidence_assembly
        → report_generation → END
        → hitl_review (interrupt) → END

Parallel fan-out: investigation, legal_analysis, bias_detection run simultaneously.
All three write to Annotated[list, operator.add] fields — safe for concurrent writes.
Sequential: discovery runs first (uses Ollama — semaphore enforces 1 at a time).

The graph is compiled once and reused — compilation is expensive, execution is cheap.
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from configs.settings import agents_cfg
from sentinel.agents import (
    audit_agent,
    bias_detection_agent,
    discovery_agent,
    investigation_agent,
    legal_agent,
    report_agent,
)
from sentinel.graph.edges import (
    route_after_discovery,
    route_after_evidence_assembly,
    route_after_hitl,
    route_after_report,
)
from sentinel.observability import heartbeat
from sentinel.observability.logger import log_agent_event, get_logger
from sentinel.state.investigation_state import InvestigationState

logger = get_logger(__name__)


# ── Node wrapper functions ─────────────────────────────────────────────────────
# These adapt agent.run() signatures to the LangGraph node signature.
# Each node receives full state, returns partial state update dict.

async def discovery_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for discovery_agent — creates its own DB session."""
    from sentinel.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        return await discovery_agent.run(state, session)


async def investigation_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for investigation_agent."""
    from sentinel.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        return await investigation_agent.run(state, session)


async def legal_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for legal_agent (no DB session needed)."""
    return await legal_agent.run(state)


async def bias_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for bias_detection_agent."""
    from sentinel.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        return await bias_detection_agent.run(state, session)


async def evidence_assembly_node(state: InvestigationState) -> dict:
    """
    Fan-in node — waits for investigation + legal + bias to all complete.
    Merges their outputs (already in state via operator.add reducers).
    Updates status and iteration count.
    """
    log_agent_event(
        logger,
        state["investigation_id"],
        state["tenant_id"],
        "evidence_assembly",
        "fan_in_complete",
        details={
            "evidence_items": len(state.get("evidence_items", [])),
            "compliance_verdict": state.get("compliance_verdict"),
            "bias_detected": state.get("bias_detected"),
        },
    )
    return {
        "status": "analyzing",
        "iteration_count": state["iteration_count"] + 1,
        "messages": [{"agent": "evidence_assembly", "event": "fan_in_complete"}],
    }


async def report_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for report_agent."""
    from sentinel.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        return await report_agent.run(state, session)


async def hitl_node(state: InvestigationState) -> dict:
    """
    HITL node — pauses the graph using LangGraph interrupt().
    State is persisted to PostgreSQL by the checkpointer before pausing.
    The resume endpoint calls graph.ainvoke() with the checkpoint config
    and provides human_decision to continue execution.

    The interrupt payload is shown to the human reviewer via the dashboard.
    """
    log_agent_event(
        logger,
        state["investigation_id"],
        state["tenant_id"],
        "hitl_node",
        "human_review_requested",
        details={"reason": state.get("hitl_reason", "Low confidence")},
    )

    # interrupt() pauses graph here. Execution resumes after human calls the resume API.
    human_input = interrupt({
        "investigation_id": state["investigation_id"],
        "hitl_reason": state.get("hitl_reason", ""),
        "draft_report": state.get("draft_report", ""),
        "compliance_verdict": state.get("compliance_verdict"),
        "regulatory_risk": state.get("regulatory_risk"),
        "bias_detected": state.get("bias_detected"),
        "action_options": ["approve_draft", "modify_response", "close_investigation"],
    })

    # Execution resumes here with human_input from the resume API
    return {
        "human_decision": human_input.get("response", ""),
        "reviewer_id": human_input.get("reviewer_id", ""),
        "final_report": human_input.get("response", state.get("draft_report", "")),
        "hitl_required": False,
        "status": "complete",
        "messages": [{
            "agent": "hitl_node",
            "event": "human_resolved",
            "reviewer_id": human_input.get("reviewer_id", ""),
        }],
    }


async def audit_node(state: InvestigationState) -> dict:
    """LangGraph node wrapper for audit_agent — always runs after report."""
    from sentinel.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        return await audit_agent.run(state, session)


async def complete_node(state: InvestigationState) -> dict:
    """Terminal node — marks investigation complete and logs cost summary."""
    from sentinel.observability.cost_tracker import summarize_costs
    cost_summary = summarize_costs(state.get("cost_log", []))
    log_agent_event(
        logger,
        state["investigation_id"],
        state["tenant_id"],
        "sentinel",
        "investigation_complete",
        details={
            "total_cost_usd": state.get("total_cost_usd", 0.0),
            "cost_by_agent": cost_summary,
        },
    )
    return {"status": "complete"}


async def no_cases_node(state: InvestigationState) -> dict:
    """Terminal node for investigations that found no relevant cases."""
    return {
        "status": "complete",
        "final_report": "No relevant cases found matching the investigation criteria.",
        "compliance_verdict": "COMPLIANT",
        "messages": [{"agent": "sentinel", "event": "no_cases_found"}],
    }


async def investigate_fanout_node(state: InvestigationState) -> dict:
    """
    Fan-out node — branches discovery's "investigate" path to parallel tasks.
    Ensures investigation, legal_analysis, bias_detection only run when
    discovery finds cases, not when routing to hitl_review or no_cases.
    Returns empty dict — just triggers downstream nodes.
    """
    return {}


# ── Graph compilation ──────────────────────────────────────────────────────────

def build_graph(session_factory=None) -> Any:
    """
    Compile the SENTINEL StateGraph.
    session_factory is a callable that returns an AsyncSession.
    Call once at startup — compiled graph is thread-safe and reusable.
    """
    graph = StateGraph(InvestigationState)

    # ── Add nodes ──────────────────────────────────────────────────────────────
    graph.add_node("discovery", discovery_node)
    graph.add_node("investigate_fanout", investigate_fanout_node)
    graph.add_node("investigation", investigation_node)
    graph.add_node("legal_analysis", legal_node)
    graph.add_node("bias_detection", bias_node)
    graph.add_node("evidence_assembly", evidence_assembly_node)
    graph.add_node("report_generation", report_node)
    graph.add_node("audit", audit_node)
    graph.add_node("hitl_review", hitl_node)
    graph.add_node("complete", complete_node)
    graph.add_node("no_cases", no_cases_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.add_edge(START, "discovery")

    # ── Conditional: after discovery ───────────────────────────────────────────
    # Routes to fan-out only if cases found, otherwise goes to hitl/no_cases
    graph.add_conditional_edges(
        "discovery",
        route_after_discovery,
        {
            "investigate": "investigate_fanout",  # Fan-out to parallel tasks
            "hitl": "hitl_review",                # Discovery uncertain
            "no_cases": "no_cases",               # Nothing found
        },
    )

    # ── Parallel fan-out: investigate_fanout → [investigation, legal, bias] ──────
    # Only branches when discovery routes to "investigate" path.
    # All three start concurrently and write to evidence_assembly's reducers.
    graph.add_edge("investigate_fanout", "investigation")
    graph.add_edge("investigate_fanout", "legal_analysis")
    graph.add_edge("investigate_fanout", "bias_detection")

    # ── Fan-in: all three agents feed evidence_assembly ─────────────────────────
    # legal_analysis, investigation, bias_detection run in parallel and all route to evidence_assembly
    graph.add_edge("legal_analysis", "evidence_assembly")
    graph.add_edge("investigation", "evidence_assembly")
    graph.add_edge("bias_detection", "evidence_assembly")

    # ── Conditional: after evidence assembly ───────────────────────────────────
    graph.add_conditional_edges(
        "evidence_assembly",
        route_after_evidence_assembly,
        {
            "report": "report_generation",
            "hitl": "hitl_review",
        },
    )

    # ── report → audit (always) → conditional split ────────────────────────────
    graph.add_edge("report_generation", "audit")

    graph.add_conditional_edges(
        "audit",
        route_after_report,          # same routing logic — checks hitl_required
        {
            "hitl": "hitl_review",
            "complete": "complete",
        },
    )

    # ── Terminal edges ─────────────────────────────────────────────────────────
    graph.add_conditional_edges("hitl_review", route_after_hitl, {"complete": "complete"})
    graph.add_edge("complete", END)
    graph.add_edge("no_cases", END)

    logger.info('{"event":"graph_compiled","nodes":11}')
    return graph


# Compiled graph singleton — initialized lazily with checkpointer
_compiled_graph = None


async def get_compiled_graph():
    """
    Return the compiled graph with PostgreSQL checkpointer attached.
    Compiled once, reused for all investigations.
    """
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    from sentinel.graph.checkpointer import get_checkpointer
    checkpointer = await get_checkpointer()
    raw_graph = build_graph()
    _compiled_graph = raw_graph.compile(checkpointer=checkpointer)
    logger.info('{"event":"compiled_graph_ready","checkpointer":"postgresql"}')
    return _compiled_graph
