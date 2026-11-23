"""
Pattern Store — pgvector-backed storage and retrieval of cross-investigation compliance patterns.

After each investigation, pattern_extractor.py extracts 3-5 compliance patterns from the
final report and stores them here. The legal agent retrieves relevant past patterns before
its analysis, injecting institutional memory into each new investigation.

Table: investigation_patterns
  pattern_id      UUID PK
  domain          TEXT (finance | pharma | generic)
  regulation      TEXT (e.g. "ECOA")
  pattern_text    TEXT (e.g. "Geographic clustering of denials in CT-015 correlates with ECOA § 1691(a) violations")
  embedding       vector(1536)
  occurrence_count INT (incremented when same pattern seen again)
  created_at      TIMESTAMPTZ
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS investigation_patterns (
    pattern_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain           TEXT NOT NULL,
    regulation       TEXT,
    pattern_text     TEXT NOT NULL,
    embedding        vector(1536),
    occurrence_count INT  NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS patterns_embedding_idx
ON investigation_patterns USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 5);
"""


async def ensure_table(session: AsyncSession) -> None:
    """Create investigation_patterns table if it doesn't exist."""
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await session.execute(text(_CREATE_TABLE))
        await session.commit()
    except Exception as exc:
        logger.warning('{"event":"pattern_table_ensure_failed","error":"%s"}', str(exc)[:100])


async def store_patterns(
    session: AsyncSession,
    patterns: list[dict],
    domain: str,
) -> int:
    """
    Store extracted patterns in investigation_patterns.

    Each pattern dict has: pattern_text, regulation (optional), embedding (list[float])

    Returns number of patterns stored.
    """
    await ensure_table(session)
    stored = 0

    for p in patterns:
        text_val  = p.get("pattern_text", "").strip()
        regulation = p.get("regulation", "")
        embedding  = p.get("embedding")

        if not text_val:
            continue

        embedding_str = (
            "[" + ",".join(str(x) for x in embedding) + "]"
            if embedding else None
        )

        try:
            await session.execute(
                text("""
                    INSERT INTO investigation_patterns
                        (domain, regulation, pattern_text, embedding)
                    VALUES (:domain, :regulation, :pattern_text,
                            CASE WHEN :embedding IS NOT NULL
                                 THEN CAST(:embedding AS vector)
                                 ELSE NULL END)
                """),
                {
                    "domain":      domain,
                    "regulation":  regulation,
                    "pattern_text": text_val,
                    "embedding":   embedding_str,
                },
            )
            stored += 1
        except Exception as exc:
            logger.warning('{"event":"pattern_store_failed","error":"%s"}', str(exc)[:100])

    if stored:
        await session.commit()

    return stored


async def get_relevant_patterns(
    session: AsyncSession,
    query: str,
    domain: str,
    top_k: int = 3,
) -> list[str]:
    """
    Retrieve top-k most relevant past patterns for a given query and domain.
    Uses pgvector cosine similarity on embeddings if available,
    falls back to most recent patterns if embedding is unavailable.

    Returns list of pattern_text strings ready for injection into legal agent prompt.
    """
    try:
        # Check if table exists
        exists = await session.execute(
            text("SELECT to_regclass('investigation_patterns')")
        )
        if not exists.scalar():
            return []

        # Try embedding-based similarity search
        embedding = await _embed(query)
        if embedding:
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            result = await session.execute(
                text("""
                    SELECT pattern_text, regulation,
                           1 - (embedding <=> CAST(:emb AS vector)) AS score
                    FROM investigation_patterns
                    WHERE domain = :domain
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:emb AS vector)
                    LIMIT :k
                """),
                {"emb": embedding_str, "domain": domain, "k": top_k},
            )
            rows = result.fetchall()
            if rows:
                return [
                    f"[{r.regulation or 'Compliance'}] {r.pattern_text}"
                    for r in rows
                ]

        # Fallback: most recent patterns for domain
        result = await session.execute(
            text("""
                SELECT pattern_text, regulation
                FROM investigation_patterns
                WHERE domain = :domain
                ORDER BY created_at DESC
                LIMIT :k
            """),
            {"domain": domain, "k": top_k},
        )
        rows = result.fetchall()
        return [
            f"[{r.regulation or 'Compliance'}] {r.pattern_text}"
            for r in rows
        ]

    except Exception as exc:
        logger.warning('{"event":"pattern_retrieval_failed","error":"%s"}', str(exc)[:100])
        return []


async def _embed(text_val: str) -> Optional[list[float]]:
    """Generate embedding — returns None if unavailable."""
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text_val[:4000],
        )
        return resp.data[0].embedding
    except Exception:
        return None
