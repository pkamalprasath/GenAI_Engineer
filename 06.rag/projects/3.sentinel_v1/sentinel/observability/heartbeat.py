"""
Agent heartbeat pattern — from open_claw_slack_bot production experience.

Each agent emits heartbeats before and after LLM calls.
The orchestrator checks: if heartbeat timestamp is older than
heartbeat_timeout_seconds (from configs/agents.yaml) → agent is stuck.

Stuck agents are retried once. Second failure → investigation marked failed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from configs.settings import agents_cfg

logger = logging.getLogger(__name__)

# Per-agent heartbeat timeouts from config — not hardcoded
_TIMEOUTS: dict[str, int] = {
    name: cfg.get("timeout_seconds", 60)
    for name, cfg in agents_cfg.get("agents", {}).items()
}


def emit(agent_name: str, status: str, iteration: int) -> dict:
    """
    Build state update dict with a heartbeat entry.
    Call at the START of each agent node (status="running") and at END (status="complete").
    The Annotated[list, operator.add] reducer safely appends without overwriting.
    """
    return {
        "heartbeats": [{
            "agent_name": agent_name,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "iteration": iteration,
        }]
    }


def check_stuck(heartbeats: list[dict], agent_name: str) -> bool:
    """
    Return True if the agent's last heartbeat is older than its configured timeout.
    Called by orchestrator before routing to detect and recover from hung agents.
    """
    timeout = _TIMEOUTS.get(agent_name, 60)
    now = datetime.now(timezone.utc)

    # Find the most recent heartbeat from this agent
    agent_beats = [hb for hb in heartbeats if hb["agent_name"] == agent_name]
    if not agent_beats:
        return False  # Never ran — not stuck, just pending

    latest = max(agent_beats, key=lambda hb: hb["last_seen"])
    last_seen = datetime.fromisoformat(latest["last_seen"])
    elapsed = (now - last_seen).total_seconds()

    if elapsed > timeout and latest["status"] == "running":
        logger.warning(
            '{"event":"agent_stuck","agent":"%s","elapsed_seconds":%.1f,"timeout":%d}',
            agent_name, elapsed, timeout,
        )
        return True
    return False
