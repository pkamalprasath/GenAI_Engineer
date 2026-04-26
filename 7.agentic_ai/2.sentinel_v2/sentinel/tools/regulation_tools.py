"""
Regulation retrieval tools — queries local pgvector regulation_documents table.
Phase 2C: Now decorated with @tool for LangGraph ToolNode compatibility.
Falls back gracefully if DB is unavailable.
"""
from __future__ import annotations

import asyncio
import asyncpg
import json
import logging
import os

from langchain_core.tools import tool

from configs.settings import models_cfg, settings

logger = logging.getLogger(__name__)

# ── Tool Execution Gate (Phase 2C) ─────────────────────────────────────────────
# Semaphore to enforce per-tenant tool call quota (prevents API overload)
_api_semaphore_limit = models_cfg.get("concurrency", {}).get("api_semaphore", 5)
_api_semaphore: asyncio.Semaphore | None = None


def _get_api_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore — must be created inside a running event loop."""
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(_api_semaphore_limit)
    return _api_semaphore


async def gated_tool_call(coro) -> dict:
    """
    Wrap any async tool coroutine with:
      1. Semaphore quota enforcement (api_semaphore from models.yaml)
      2. Exception safety — returns {\"success\": False, \"error\": \"...\"} on any exception,
         never raises (ToolNode must receive a result dict, not an exception)

    Returns: dict (either the original result or error dict)
    """
    sem = _get_api_semaphore()
    async with sem:
        try:
            return await coro
        except Exception as exc:
            logger.warning(
                '{"event":"tool_call_failed","tool":"search_regulations","error":"%s"}',
                str(exc)[:200],
            )
            return {"success": False, "error": str(exc)[:200]}


async def _inner_search_regulations(query: str, domain: str, top_k: int) -> list[dict]:
    """
    Inner implementation of regulation search (extracted for gated_tool_call wrapping).
    Returns the raw search results.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    client = openai.AsyncOpenAI(api_key=api_key)

    resp = await client.embeddings.create(
        model="text-embedding-3-small",
        input=f"{domain} compliance regulations: {query}",
    )
    embedding = resp.data[0].embedding

    db_url = settings.database_url_sync
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            """
            SELECT regulation_name, full_name, section, content,
                   1 - (embedding <=> $1::vector) AS relevance
            FROM regulation_documents
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            json.dumps(embedding),
            top_k,
        )
        return [
            {
                "regulation_name": r["regulation_name"],
                "section": r["section"],
                "text": r["content"][:1000],
                "relevance_score": float(r["relevance"]),
            }
            for r in rows
        ]
    finally:
        await conn.close()


@tool
async def search_regulations(query: str, domain: str, top_k: int = 5) -> list[dict]:
    """
    Search regulatory documents by semantic similarity using pgvector.

    Use this tool when you need to retrieve specific regulation text to support
    a legal compliance analysis. The tool automatically embeds your query and
    searches the regulation_documents table for cosine similarity.

    Args:
        query: Natural language description of the regulation topic to search
               (e.g., \"credit denial procedures\" or \"adverse action notice requirements\")
        domain: Compliance domain (\"finance\", \"pharma\", or \"generic\")
        top_k: Maximum number of regulation sections to return (default 5)

    Returns:
        List of dicts with keys: regulation_name, section, text, relevance_score.
        Returns empty list if search fails or no regulations found.
    """
    return await gated_tool_call(_inner_search_regulations(query, domain, top_k))
