"""
Ingest regulation sections from YAML files into pgvector.

Usage:
    python scripts/ingest_regulations.py                    # all domains
    python scripts/ingest_regulations.py --domain finance   # single domain

Idempotent: checks (regulation_name, section) uniqueness before inserting.
Drop a new .yaml in data/regulations/{domain}/ and re-run — no code change needed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import asyncpg
import openai

from configs.settings import settings

REGULATIONS_DIR = Path("data/regulations")
EMBED_MODEL = "text-embedding-3-small"


async def embed(text: str) -> list[float]:
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or settings.openai_api_key)
    resp = await client.embeddings.create(model=EMBED_MODEL, input=text[:8000])
    return resp.data[0].embedding


async def ensure_table(conn) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS regulation_documents (
            id               SERIAL PRIMARY KEY,
            regulation_name  TEXT NOT NULL,
            full_name        TEXT NOT NULL,
            section          TEXT NOT NULL,
            content          TEXT NOT NULL,
            domain           TEXT NOT NULL DEFAULT 'finance',
            active           BOOLEAN NOT NULL DEFAULT TRUE,
            embedding        vector(1536),
            created_at       TIMESTAMPTZ DEFAULT now()
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS reg_docs_embedding_idx
        ON regulation_documents USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10);
    """)


async def ingest(domain_filter: str | None = None) -> None:
    print("[OK] SENTINEL v2 - Regulation Ingestion\n")

    if not REGULATIONS_DIR.exists():
        print("[FAIL] data/regulations/ not found. Run from the project root directory.")
        return

    yaml_files = sorted(REGULATIONS_DIR.glob("**/*.yaml"))
    if domain_filter:
        yaml_files = [f for f in yaml_files if f.parent.name == domain_filter]

    if not yaml_files:
        print(f"No YAML files found{f' for domain={domain_filter}' if domain_filter else ''}.")
        return

    conn = await asyncpg.connect(settings.database_url_sync)
    total_new = total_skip = 0

    try:
        await ensure_table(conn)

        for yaml_path in yaml_files:
            domain = yaml_path.parent.name
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            reg_name = data["regulation_name"]
            full_name = data.get("full_name", reg_name)

            print(f"[FILE] {yaml_path.relative_to(REGULATIONS_DIR)} -> {reg_name} ({domain})")

            for sec in data.get("sections", []):
                section = sec["section"]
                text = sec["text"].strip()

                exists = await conn.fetchval(
                    "SELECT id FROM regulation_documents WHERE regulation_name=$1 AND section=$2",
                    reg_name, section,
                )
                if exists:
                    print(f"  [SKIP] {reg_name} — {section}")
                    total_skip += 1
                    continue

                embedding = await embed(f"{reg_name} {section}\n{text}")
                await conn.execute(
                    """
                    INSERT INTO regulation_documents
                        (regulation_name, full_name, section, content, domain, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6::vector)
                    """,
                    reg_name, full_name, section, text, domain,
                    "[" + ",".join(str(x) for x in embedding) + "]",
                )
                print(f"  [NEW] {reg_name} — {section}")
                total_new += 1

    finally:
        await conn.close()

    print(f"\n[OK] Done - {total_new} inserted, {total_skip} already present")
    if total_new:
        print("   Legal agent picks up new regulations automatically on the next investigation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Filter by domain (finance|pharma|generic)")
    args = parser.parse_args()
    asyncio.run(ingest(args.domain))
