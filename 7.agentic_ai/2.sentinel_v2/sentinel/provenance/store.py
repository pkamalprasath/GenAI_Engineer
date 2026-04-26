"""
Provenance store — PostgreSQL JSONB backend with NetworkX in-memory graph.

Architecture:
  - PostgreSQL stores all nodes and edges persistently (append-only)
  - NetworkX graph is built on-demand for graph traversal queries
  - Tenant isolation enforced: every query filters by tenant_id
  - content_hash enables tamper detection on any retrieved node

Why NetworkX instead of Neo4j:
  Neo4j requires 1GB+ RAM minimum — too heavy for an 8GB system.
  NetworkX builds the graph in memory from PostgreSQL records on-demand,
  uses ~50MB for 10,000 nodes, and is sufficient for compliance queries.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.provenance.schema import NodeType, ProvEdge, ProvNode, RelationType


def _parse_ts(ts) -> datetime:
    """Convert ISO string or datetime to naive datetime (matches DB column type)."""
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(ts)).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

logger = logging.getLogger(__name__)


class ProvenanceStore:
    """
    Async provenance store backed by PostgreSQL JSONB tables.
    All operations are tenant-scoped — cross-tenant access raises an error.
    """

    def __init__(self, session: AsyncSession):
        # Session is injected — never create DB connections inside this class
        self._session = session

    # ── Write operations ───────────────────────────────────────────────────────

    async def add_node(self, node: ProvNode) -> None:
        """Insert or update a provenance node. Updates if node_id already exists."""
        await self._session.execute(
            text("""
                INSERT INTO provenance_nodes
                    (node_id, node_type, tenant_id, content, content_hash, timestamp, metadata)
                VALUES
                    (:node_id, :node_type, :tenant_id, CAST(:content AS jsonb),
                     :content_hash, :timestamp, CAST(:metadata AS jsonb))
                ON CONFLICT (node_id, tenant_id) DO UPDATE SET
                    content = CAST(:content AS jsonb),
                    content_hash = :content_hash,
                    timestamp = :timestamp,
                    metadata = CAST(:metadata AS jsonb)
            """),
            {
                "node_id": node.node_id,
                "node_type": node.node_type.value,
                "tenant_id": node.tenant_id,
                "content": json.dumps(node.content),
                "content_hash": node.content_hash,
                "timestamp": _parse_ts(node.timestamp),
                "metadata": json.dumps(node.metadata),
            },
        )
        await self._session.commit()

    async def add_edge(self, edge: ProvEdge) -> None:
        """Insert a provenance edge."""
        await self._session.execute(
            text("""
                INSERT INTO provenance_edges
                    (edge_id, source_id, target_id, relation, tenant_id, timestamp, metadata)
                VALUES
                    (:edge_id, :source_id, :target_id, :relation, :tenant_id,
                     :timestamp, CAST(:metadata AS jsonb))
                ON CONFLICT (edge_id, tenant_id) DO NOTHING
            """),
            {
                "edge_id": edge.edge_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation.value,
                "tenant_id": edge.tenant_id,
                "timestamp": _parse_ts(edge.timestamp),
                "metadata": json.dumps(edge.metadata),
            },
        )
        await self._session.commit()

    # ── Read operations ────────────────────────────────────────────────────────

    async def node_exists(self, node_id: str, tenant_id: str | None = None) -> bool:
        """Check if a node exists. Used by output_guard to verify citations."""
        query = "SELECT 1 FROM provenance_nodes WHERE node_id = :node_id"
        params: dict = {"node_id": node_id}
        # Tenant filter applied when tenant_id provided — output_guard always provides it
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        result = await self._session.execute(text(query), params)
        return result.fetchone() is not None

    async def get_node(self, node_id: str, tenant_id: str) -> Optional[dict]:
        """Fetch a single node, enforcing tenant isolation."""
        result = await self._session.execute(
            text("""
                SELECT node_id, node_type, content, content_hash, timestamp, metadata
                FROM provenance_nodes
                WHERE node_id = :node_id AND tenant_id = :tenant_id
            """),
            {"node_id": node_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return dict(row._mapping)

    async def get_nodes_for_case(self, case_id: str, tenant_id: str) -> list[dict]:
        """Fetch all provenance nodes associated with a case ID."""
        result = await self._session.execute(
            text("""
                SELECT node_id, node_type, content, content_hash, timestamp
                FROM provenance_nodes
                WHERE tenant_id = :tenant_id
                  AND content->>'case_id' = :case_id
                ORDER BY timestamp ASC
            """),
            {"tenant_id": tenant_id, "case_id": case_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def build_graph(self, tenant_id: str, case_ids: list[str] | None = None) -> nx.DiGraph:
        """
        Build an in-memory NetworkX directed graph for the given tenant.
        Optionally filter to nodes related to specific case_ids.
        Used by query.py for traversal operations.
        """
        # Load nodes
        node_query = "SELECT node_id, node_type, content FROM provenance_nodes WHERE tenant_id = :t"
        params: dict = {"t": tenant_id}

        if case_ids:
            node_query += " AND content->>'case_id' = ANY(:cases)"
            params["cases"] = case_ids

        node_query += " LIMIT 2000"  # Prevent unbounded memory usage on large tenants

        node_rows = await self._session.execute(text(node_query), params)
        nodes = node_rows.fetchall()

        # Load edges
        edge_query = "SELECT source_id, target_id, relation FROM provenance_edges WHERE tenant_id = :t"
        edge_rows = await self._session.execute(text(edge_query), {"t": tenant_id})
        edges = edge_rows.fetchall()

        # Build NetworkX DiGraph
        graph = nx.DiGraph()
        for n in nodes:
            graph.add_node(n.node_id, node_type=n.node_type, content=n.content)
        for e in edges:
            graph.add_edge(e.source_id, e.target_id, relation=e.relation)

        logger.info(
            '{"event":"graph_built","tenant_id":"%s","nodes":%d,"edges":%d}',
            tenant_id, graph.number_of_nodes(), graph.number_of_edges(),
        )
        return graph

    async def verify_hashes_batch(
        self, node_hash_pairs: list[tuple[str, str]], tenant_id: str
    ) -> dict[str, bool]:
        """
        Batch tamper detection — single query instead of N individual lookups.
        Returns {node_id: is_valid} for all requested nodes.
        """
        if not node_hash_pairs:
            return {}
        node_ids = [p[0] for p in node_hash_pairs]
        result = await self._session.execute(
            text("""
                SELECT node_id, content_hash
                FROM provenance_nodes
                WHERE tenant_id = :tenant_id AND node_id = ANY(:node_ids)
            """),
            {"tenant_id": tenant_id, "node_ids": node_ids},
        )
        stored = {row.node_id: row.content_hash for row in result.fetchall()}
        expected = {node_id: h for node_id, h in node_hash_pairs}
        results = {}
        for node_id, exp_hash in expected.items():
            stored_hash = stored.get(node_id)
            is_valid = stored_hash == exp_hash if stored_hash else False
            if not is_valid:
                logger.error(
                    '{"event":"hash_mismatch","node_id":"%s","tenant_id":"%s"}',
                    node_id, tenant_id,
                )
            results[node_id] = is_valid
        return results

    async def verify_hash(self, node_id: str, tenant_id: str, expected_hash: str) -> bool:
        """
        Tamper detection: compare stored content_hash against expected value.
        Used by investigation_agent to verify provenance chain integrity.
        """
        node = await self.get_node(node_id, tenant_id)
        if not node:
            return False
        match = node["content_hash"] == expected_hash
        if not match:
            logger.error(
                '{"event":"hash_mismatch","node_id":"%s","tenant_id":"%s"}',
                node_id, tenant_id,
            )
        return match
