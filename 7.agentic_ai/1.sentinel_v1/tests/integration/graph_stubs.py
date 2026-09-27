"""
Stubs for running the real SENTINEL LangGraph without Postgres, Ollama or LLM APIs.

stub_agents() patches each agent's run() and the DB session factory, and records
which agents ran, so tests can check the graph wiring (fan-out, fan-in, routing,
HITL pause) end to end.
"""
from __future__ import annotations

import importlib
from contextlib import ExitStack, asynccontextmanager, contextmanager
from unittest.mock import patch


@asynccontextmanager
async def _fake_session():
    yield object()


@contextmanager
def stub_agents(
    case_count: int = 2,
    discovery_confidence: float = 0.9,
    compliance_verdict: str = "COMPLIANT",
    regulatory_risk: str = "LOW",
    bias_detected: bool = False,
):
    calls: list[str] = []

    async def discovery(state, session):
        calls.append("discovery")
        ids = [f"CASE-{i:04d}" for i in range(1, case_count + 1)]
        return {"relevant_case_ids": ids, "case_count": case_count,
                "discovery_confidence": discovery_confidence}

    async def investigation(state, session):
        calls.append("investigation")
        return {"evidence_items": [{"case_id": "CASE-0001", "summary": "stub"}],
                "investigation_sufficient": True}

    async def legal(state):
        calls.append("legal")
        return {"compliance_verdict": compliance_verdict,
                "regulatory_risk": regulatory_risk,
                "applicable_regulations": ["ECOA"]}

    async def bias(state, session):
        calls.append("bias")
        return {"bias_detected": bias_detected, "bias_confidence": 0.9 if bias_detected else 0.1}

    async def report(state, session):
        calls.append("report")
        return {"final_report": "Stub report", "draft_report": "Stub report",
                "hitl_required": False}

    async def audit(state, session):
        calls.append("audit")
        return {}

    with ExitStack() as stack:
        stack.enter_context(patch("sentinel.db.session.AsyncSessionFactory", _fake_session))
        for module, fn in [
            ("discovery_agent", discovery),
            ("investigation_agent", investigation),
            ("legal_agent", legal),
            ("bias_detection_agent", bias),
            ("report_agent", report),
            ("audit_agent", audit),
        ]:
            try:
                importlib.import_module(f"sentinel.agents.{module}")
            except ModuleNotFoundError:
                continue  # older graph versions (v1) have no audit agent
            stack.enter_context(patch(f"sentinel.agents.{module}.run", fn))
        yield calls
