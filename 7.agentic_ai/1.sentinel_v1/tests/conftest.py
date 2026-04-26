"""
Shared test fixtures for all SENTINEL test suites.

Design principles:
  - Unit tests: no Docker, no API calls, no network — fast and isolated
  - Integration tests: real PostgreSQL via Docker, mock LLM responses
  - Security tests: no external deps — all inputs crafted locally
  - All fixtures clean up after themselves
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sentinel.state.investigation_state import InvestigationState, make_initial_state


# ── Event loop ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Sample state fixture ───────────────────────────────────────────────────────
@pytest.fixture
def sample_state() -> InvestigationState:
    """A complete, valid InvestigationState for testing agent nodes."""
    return make_initial_state(
        investigation_id="TEST-INV-001",
        tenant_id="test-tenant",
        query="Review Q1 2024 credit decisions for fair lending compliance",
        date_range={"from": "2024-01-01", "to": "2024-03-31"},
        domain="finance",
    )


@pytest.fixture
def sample_state_with_cases(sample_state) -> InvestigationState:
    """State populated with discovery results — for downstream agent tests."""
    sample_state["relevant_case_ids"] = ["CASE-0001", "CASE-0002", "CASE-0003"]
    sample_state["case_count"] = 3
    sample_state["discovery_confidence"] = 0.88
    sample_state["status"] = "investigating"
    return sample_state


@pytest.fixture
def sample_state_complete(sample_state_with_cases) -> InvestigationState:
    """Fully populated state with all agent outputs — for report agent tests."""
    s = sample_state_with_cases
    s["evidence_items"] = [
        {"evidence_id": "ev-001", "description": "Decision record",
         "provenance_node_id": "decision-CASE-0001", "trust_score": 0.80,
         "source_type": "decision_record"},
        {"evidence_id": "ev-002", "description": "Legal citation",
         "provenance_node_id": "reg-ECOA-001", "trust_score": 0.95,
         "source_type": "regulation"},
    ]
    s["investigation_sufficient"] = True
    s["compliance_verdict"] = "UNCERTAIN"
    s["regulatory_risk"] = "MEDIUM"
    s["bias_detected"] = False
    s["applicable_regulations"] = ["ECOA Section 202.6"]
    return s


# ── Mock LLM fixture ───────────────────────────────────────────────────────────
@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client — returns deterministic JSON responses."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"investigation_sufficient": true, "investigation_iterations": 1, "summary": "test summary"}')]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_ollama_chain():
    """Mock Ollama LLM chain — returns deterministic classification output."""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value={
        "relevant_case_ids": ["CASE-0001", "CASE-0002"],
        "case_count": 2,
        "discovery_confidence": 0.87,
    })
    return mock


# ── Mock DB session fixture ────────────────────────────────────────────────────
@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy async session — no Docker required for unit tests."""
    session = AsyncMock()

    # Default: execute returns empty result
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=None)
    mock_result.fetchall = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ── Mock provenance store ──────────────────────────────────────────────────────
@pytest.fixture
def mock_provenance_store():
    """Mock ProvenanceStore — returns test nodes without hitting DB."""
    store = AsyncMock()
    store.node_exists = AsyncMock(return_value=True)
    store.get_node = AsyncMock(return_value={
        "node_id": "decision-CASE-0001",
        "node_type": "prov:Entity",
        "content": {"case_id": "CASE-0001", "outcome": "denied"},
        "content_hash": "abc123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    store.build_graph = AsyncMock(return_value=__import__("networkx").DiGraph())
    store.verify_hash = AsyncMock(return_value=True)
    return store
