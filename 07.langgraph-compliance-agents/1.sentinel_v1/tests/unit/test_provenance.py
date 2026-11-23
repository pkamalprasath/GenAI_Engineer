"""
Unit tests for W3C PROV-O provenance schema, store, and graph traversal.
No Docker — uses mock DB session from conftest.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest
import pytest_asyncio

from sentinel.provenance.schema import (
    NodeType,
    ProvNode,
    RelationType,
    make_agent_node,
    make_decision_node,
    make_tool_call_node,
)
from sentinel.provenance.query import (
    adjacency_to_graph,
    detect_broken_chains,
    graph_to_adjacency,
    trace_decision_chain,
)


# ── Schema Tests ───────────────────────────────────────────────────────────────

class TestProvNodeSchema:
    """ProvNode dataclass — content hash computed automatically."""

    def test_content_hash_computed_on_init(self):
        content = {"case_id": "CASE-0001", "outcome": "denied"}
        node = ProvNode(
            node_id="decision-CASE-0001",
            node_type=NodeType.ENTITY,
            tenant_id="bank-acme",
            content=content,
        )
        expected_hash = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
        assert node.content_hash == expected_hash

    def test_same_content_same_hash(self):
        content = {"case_id": "CASE-0001", "outcome": "denied"}
        node1 = ProvNode("n1", NodeType.ENTITY, "t1", content)
        node2 = ProvNode("n2", NodeType.ENTITY, "t1", content)
        assert node1.content_hash == node2.content_hash

    def test_different_content_different_hash(self):
        node1 = ProvNode("n1", NodeType.ENTITY, "t1", {"outcome": "denied"})
        node2 = ProvNode("n2", NodeType.ENTITY, "t1", {"outcome": "approved"})
        assert node1.content_hash != node2.content_hash

    def test_node_has_timestamp(self):
        node = ProvNode("n1", NodeType.ENTITY, "t1", {})
        assert node.timestamp is not None
        # Should be parseable ISO datetime
        datetime.fromisoformat(node.timestamp)

    def test_to_prov_json_w3c_format(self):
        node = ProvNode("n1", NodeType.ENTITY, "t1", {"k": "v"})
        prov = node.to_prov_json()
        assert "prov:type" in prov
        assert "prov:id" in prov
        assert "content_hash" in prov

    def test_node_type_enum_values(self):
        assert NodeType.ENTITY.value == "prov:Entity"
        assert NodeType.ACTIVITY.value == "prov:Activity"
        assert NodeType.AGENT.value == "prov:Agent"

    def test_relation_type_enum(self):
        assert RelationType.WAS_GENERATED_BY.value == "prov:wasGeneratedBy"
        assert RelationType.USED.value == "prov:used"
        assert RelationType.WAS_DERIVED_FROM.value == "prov:wasDerivedFrom"


class TestFactoryFunctions:
    """Factory functions produce correctly structured ProvNodes."""

    def test_make_decision_node(self):
        node = make_decision_node(
            case_id="CASE-0001",
            tenant_id="bank-acme",
            outcome="denied",
            model_version="credit-scorer-v2.3",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert node.node_type == NodeType.ENTITY
        assert "CASE-0001" in node.node_id
        assert node.content["outcome"] == "denied"
        assert node.tenant_id == "bank-acme"
        assert node.content_hash != ""

    def test_make_agent_node(self):
        node = make_agent_node(
            agent_name="legal_agent",
            tenant_id="bank-acme",
            investigation_id="INV-001",
        )
        assert node.node_type == NodeType.AGENT
        assert "legal_agent" in node.node_id or "legal" in node.content.get("agent_name", "")

    def test_make_tool_call_node(self):
        node = make_tool_call_node(
            tool_name="search_regulations",
            tenant_id="bank-acme",
            inputs={"query": "ECOA Section 202"},
            outputs={"regulation": "Equal Credit Opportunity Act"},
        )
        assert node.node_type == NodeType.ACTIVITY
        assert node.content["tool_name"] == "search_regulations"


# ── Graph Traversal Tests ──────────────────────────────────────────────────────

class TestTraceDecisionChain:
    """trace_decision_chain() BFS backwards from decision node."""

    def _build_test_graph(self) -> nx.DiGraph:
        """Build a simple provenance graph: regulation → tool_call → agent → decision."""
        g = nx.DiGraph()
        g.add_node("reg-ECOA-001", node_type="prov:Entity", tenant_id="bank-acme")
        g.add_node("tool-search-001", node_type="prov:Activity", tenant_id="bank-acme")
        g.add_node("agent-legal-001", node_type="prov:Agent", tenant_id="bank-acme")
        g.add_node("decision-CASE-0001", node_type="prov:Entity", tenant_id="bank-acme")
        g.add_edge("reg-ECOA-001", "tool-search-001", relation="prov:used")
        g.add_edge("tool-search-001", "agent-legal-001", relation="prov:wasGeneratedBy")
        g.add_edge("agent-legal-001", "decision-CASE-0001", relation="prov:wasGeneratedBy")
        return g

    def test_traces_full_chain(self):
        g = self._build_test_graph()
        chain = trace_decision_chain(g, start_node_id="decision-CASE-0001", max_depth=10)
        node_ids = [n["node_id"] for n in chain]
        assert "decision-CASE-0001" in node_ids
        assert len(chain) > 1  # Should traverse backwards

    def test_max_depth_respected(self):
        g = self._build_test_graph()
        chain = trace_decision_chain(g, start_node_id="decision-CASE-0001", max_depth=1)
        # Depth 1 = only immediate predecessor
        assert len(chain) <= 2

    def test_nonexistent_node_returns_empty(self):
        g = self._build_test_graph()
        chain = trace_decision_chain(g, start_node_id="nonexistent-node", max_depth=10)
        assert chain == [] or chain == {}

    def test_isolated_node_returns_single(self):
        g = nx.DiGraph()
        g.add_node("decision-CASE-0001", node_type="prov:Entity")
        chain = trace_decision_chain(g, start_node_id="decision-CASE-0001", max_depth=10)
        node_ids = [n["node_id"] for n in chain]
        assert "decision-CASE-0001" in node_ids


class TestDetectBrokenChains:
    """detect_broken_chains() finds cases with missing provenance nodes."""

    def test_finds_cases_without_nodes(self):
        # Graph contains nodes for CASE-0001 and CASE-0002 but not CASE-0003
        g = nx.DiGraph()
        g.add_node("decision-CASE-0001", node_type="prov:Entity")
        g.add_node("decision-CASE-0002", node_type="prov:Entity")

        all_case_ids = ["CASE-0001", "CASE-0002", "CASE-0003"]
        broken = detect_broken_chains(g, all_case_ids)
        assert "CASE-0003" in broken

    def test_no_broken_chains_when_all_present(self):
        g = nx.DiGraph()
        g.add_node("decision-CASE-0001", node_type="prov:Entity")
        g.add_node("decision-CASE-0002", node_type="prov:Entity")

        broken = detect_broken_chains(g, ["CASE-0001", "CASE-0002"])
        assert len(broken) == 0

    def test_empty_graph_all_broken(self):
        g = nx.DiGraph()
        broken = detect_broken_chains(g, ["CASE-0001", "CASE-0002"])
        assert set(broken) == {"CASE-0001", "CASE-0002"}


class TestGraphSerialization:
    """graph_to_adjacency / adjacency_to_graph — NetworkX serialization for state storage."""

    def test_round_trip_preserves_nodes(self):
        g = nx.DiGraph()
        g.add_node("n1", node_type="prov:Entity", tenant_id="t1")
        g.add_node("n2", node_type="prov:Activity", tenant_id="t1")
        g.add_edge("n1", "n2", relation="prov:used")

        adj = graph_to_adjacency(g)
        restored = adjacency_to_graph(adj)

        assert set(restored.nodes()) == {"n1", "n2"}
        assert restored.has_edge("n1", "n2")

    def test_round_trip_preserves_attributes(self):
        g = nx.DiGraph()
        g.add_node("n1", node_type="prov:Entity", tenant_id="bank-acme")
        adj = graph_to_adjacency(g)
        restored = adjacency_to_graph(adj)
        assert restored.nodes["n1"]["tenant_id"] == "bank-acme"

    def test_empty_graph_serializes(self):
        g = nx.DiGraph()
        adj = graph_to_adjacency(g)
        restored = adjacency_to_graph(adj)
        assert len(restored.nodes()) == 0

    def test_adjacency_is_json_serializable(self):
        g = nx.DiGraph()
        g.add_node("n1", node_type="prov:Entity")
        adj = graph_to_adjacency(g)
        # Must be serializable for LangGraph state storage
        serialized = json.dumps(adj)
        assert serialized != ""


# ── ProvenanceStore Tests ──────────────────────────────────────────────────────

class TestProvenanceStoreMocked:
    """ProvenanceStore with mock DB — verifies tenant isolation at SQL level."""

    @pytest.mark.asyncio
    async def test_get_node_returns_tenant_scoped_result(self, mock_provenance_store):
        result = await mock_provenance_store.get_node("decision-CASE-0001", "bank-acme")
        assert result is not None
        assert result["node_id"] == "decision-CASE-0001"

    @pytest.mark.asyncio
    async def test_node_exists_returns_bool(self, mock_provenance_store):
        exists = await mock_provenance_store.node_exists("decision-CASE-0001", "bank-acme")
        assert isinstance(exists, bool)
        assert exists is True

    @pytest.mark.asyncio
    async def test_build_graph_returns_networkx(self, mock_provenance_store):
        graph = await mock_provenance_store.build_graph(
            case_ids=["CASE-0001"],
            tenant_id="bank-acme",
        )
        assert isinstance(graph, nx.DiGraph)

    @pytest.mark.asyncio
    async def test_verify_hash_returns_bool(self, mock_provenance_store):
        result = await mock_provenance_store.verify_hash(
            node_id="decision-CASE-0001",
            expected_hash="abc123",
            tenant_id="bank-acme",
        )
        assert isinstance(result, bool)
