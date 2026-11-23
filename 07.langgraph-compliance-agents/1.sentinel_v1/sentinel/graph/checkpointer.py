"""
LangGraph PostgreSQL checkpointer setup for HITL (human-in-the-loop).

The checkpointer persists graph state to PostgreSQL after every node.
When an agent calls interrupt(), the graph pauses and state is saved.
The HITL resume endpoint loads the checkpoint and continues the graph.

This is what makes HITL actually work — without checkpointing, a paused
graph loses all state when the process restarts.
"""
from __future__ import annotations

import logging
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

# Cached checkpointer — expensive to create, reused across requests
_checkpointer: Optional[object] = None


async def get_checkpointer():
    """
    Return async PostgreSQL checkpointer.
    LangGraph creates its own 'checkpoints' table on first use.
    Thread ID in LangGraph = investigation_id (our conversation_id).
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Uses raw psycopg connection string (not SQLAlchemy URL)
        conn_string = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
        _checkpointer = await AsyncPostgresSaver.from_conn_string(conn_string)
        # Create LangGraph checkpoint tables if not already present
        await _checkpointer.setup()
        logger.info('{"event":"checkpointer_initialized","backend":"postgresql"}')

    except Exception as exc:
        logger.warning(
            '{"event":"checkpointer_fallback","error":"%s","fallback":"memory"}',
            str(exc)[:100],
        )
        # Fall back to in-memory checkpointer — HITL won't survive restarts
        # but the graph still works for development/testing
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()

    return _checkpointer
