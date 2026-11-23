"""
Shared utilities for SENTINEL agents, API, and worker.

Includes state serialization, snapshot safety checks, etc.
Used by both api/main.py and sentinel/worker/main.py.
"""
from __future__ import annotations

import json


def make_safe_snapshot(state: dict) -> dict:
    """
    Serialize state to a JSON-safe dict, dropping non-serializable objects.

    Excluded fields (non-serializable):
    - provenance_nodes (networkx graphs, sqlalchemy objects)
    - decision_chains (complex nested structures)

    Safe for storing in PostgreSQL JSONB columns.
    """
    def _is_safe(v) -> bool:
        try:
            json.dumps(v)
            return True
        except (TypeError, ValueError):
            return False

    excluded = {"provenance_nodes", "decision_chains"}
    return {
        k: v for k, v in state.items()
        if k not in excluded and _is_safe(v)
    }
