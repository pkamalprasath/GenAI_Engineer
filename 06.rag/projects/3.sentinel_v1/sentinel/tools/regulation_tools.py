"""
Regulation retrieval tools — queries local pgvector regulation_documents table.
Falls back gracefully if DB is unavailable.
"""
from __future__ import annotations

import logging
import os

from configs.settings import settings

logger = logging.getLogger(__name__)


async def search_regulations(query: str, domain: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve relevant regulation sections via pgvector similarity search
    against the regulation_documents table populated by ingest_regulations.py.
    """
    try:
        import openai
        import asyncpg

        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        client = openai.AsyncOpenAI(api_key=api_key)

        # Embed the query
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
                str(embedding),
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

    except Exception as exc:
        logger.warning(
            '{"event":"regulation_search_failed","error":"%s"}', str(exc)[:100]
        )
        return []
