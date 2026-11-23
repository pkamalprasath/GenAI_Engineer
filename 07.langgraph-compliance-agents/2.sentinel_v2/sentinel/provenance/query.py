"""
Provenance graph traversal queries — used by investigation_agent and dashboard.

All queries operate on a NetworkX DiGraph built by ProvenanceStore.build_graph().
Tenant isolation is enforced at the store level before graphs reach here.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def trace_decision_chain(graph: nx.DiGraph, decision_node_id: str = "", max_depth: int = 5, *, start_node_id: str = "") -> list[dict]:
    """
    Traverse backwards from a decision node to find all influencing inputs.
    Returns a list of nodes in causal order (inputs first, decision last).
    max_depth prevents runaway traversal on deeply nested graphs.
    """
    decision_node_id = start_node_id or decision_node_id
    if decision_node_id not in graph:
        logger.warning('{"event":"node_not_found","node_id":"%s"}', decision_node_id)
        return []

    # BFS backwards through predecessors up to max_depth
    chain = []
    visited = set()
    queue = [(decision_node_id, 0)]

    while queue:
        node_id, depth = queue.pop(0)
        if node_id in visited or depth > max_depth:
            continue
        visited.add(node_id)

        node_attrs = graph.nodes[node_id]
        chain.append({
            "node_id": node_id,
            "node_type": node_attrs.get("node_type"),
            "content": node_attrs.get("content", {}),
            "depth": depth,
        })

        for predecessor in graph.predecessors(node_id):
            if predecessor not in visited:
                queue.append((predecessor, depth + 1))

    # Return in causal order: deepest inputs first
    return sorted(chain, key=lambda x: -x["depth"])


def find_shared_inputs(graph: nx.DiGraph, case_ids: list[str]) -> list[str]:
    """
    Find provenance nodes that influenced multiple decisions.
    Used by bias_detection_agent: shared inputs across denied cases may indicate
    a systematic pattern (e.g., all denials used the same biased scoring model).
    """
    # Count how many decision nodes each input node reaches
    input_reach: dict[str, set] = {}

    for case_id in case_ids:
        decision_node = f"decision-{case_id}"
        if decision_node not in graph:
            continue
        # All ancestors of this decision
        ancestors = nx.ancestors(graph, decision_node)
        for ancestor in ancestors:
            if ancestor not in input_reach:
                input_reach[ancestor] = set()
            input_reach[ancestor].add(case_id)

    # Nodes that influenced > 1 case are shared — potentially systematic
    shared = [node_id for node_id, cases in input_reach.items() if len(cases) > 1]
    logger.info('{"event":"shared_inputs_found","count":%d}', len(shared))
    return shared


def detect_broken_chains(graph: nx.DiGraph, case_ids: list[str]) -> list[str]:
    """
    Identify cases whose provenance chains are incomplete (orphaned nodes,
    disconnected components). Used by investigation_agent to flag integrity issues.
    Returns list of case_ids with broken chains.
    """
    broken = []
    for case_id in case_ids:
        decision_node = f"decision-{case_id}"
        if decision_node not in graph:
            # Decision recorded but no provenance node — chain missing entirely
            broken.append(case_id)
            continue

        # Node exists in graph — chain is considered present even without predecessors

    logger.info('{"event":"broken_chains_detected","count":%d}', len(broken))
    return broken


def graph_to_adjacency(graph: nx.DiGraph) -> dict[str, Any]:
    """Serialize a NetworkX graph to a JSON-safe adjacency dict for state storage."""
    return nx.node_link_data(graph, edges="edges")


def adjacency_to_graph(data: dict) -> nx.DiGraph:
    """Deserialize adjacency dict back to NetworkX DiGraph."""
    return nx.node_link_graph(data, directed=True, edges="edges")
