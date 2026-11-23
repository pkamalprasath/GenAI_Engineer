"""
Seed PostgreSQL with synthetic decisions and provenance nodes.
Run after generate_synthetic_data.py and docker compose up.

python scripts/seed_database.py
"""
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path regardless of where script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from configs.settings import settings

SYNTHETIC_FILE = Path("data/synthetic/decisions.json")


async def seed():
    print("🛡️  SENTINEL — Database Seeder\n")

    if not SYNTHETIC_FILE.exists():
        print("❌ Synthetic data not found. Run generate_synthetic_data.py first.")
        return

    decisions = json.loads(SYNTHETIC_FILE.read_text())
    print(f"Loading {len(decisions)} decisions into database...\n")

    conn = await asyncpg.connect(settings.database_url_sync)

    try:
        # Insert decision records
        inserted = 0
        for d in decisions:
            try:
                await conn.execute(
                    """
                    INSERT INTO decision_records
                        (case_id, tenant_id, outcome, decision_timestamp, model_version,
                         reasoning_text, metadata)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
                    ON CONFLICT (case_id, tenant_id) DO NOTHING
                    """,
                    d["case_id"], d["tenant_id"], d["outcome"],
                    datetime.fromisoformat(d["decision_timestamp"]).replace(tzinfo=None), d.get("model_version", "unknown"),
                    d.get("reasoning_text", ""), json.dumps(d.get("metadata", {})),
                )
                inserted += 1
            except Exception as exc:
                print(f"  Skip {d['case_id']}: {exc}")

        print(f"✓ Inserted {inserted} decision records")

        # Insert provenance nodes for each decision
        prov_inserted = 0
        for d in decisions:
            meta = d.get("metadata", {}) or {}
            content = {
                "case_id":        d["case_id"],
                "outcome":        d["outcome"],
                "reasoning_text": d.get("reasoning_text", ""),
                "model_version":  d.get("model_version"),
                "timestamp":      d["decision_timestamp"],
                "age_group":      meta.get("age_group", ""),
                "income_bracket": meta.get("income_bracket", ""),
                "credit_score_tier": meta.get("credit_score_tier", ""),
                "zip_code_census_tract": meta.get("zip_code_census_tract", ""),
            }
            content_hash = hashlib.sha256(
                json.dumps(content, sort_keys=True).encode()
            ).hexdigest()

            # Skip provenance for integrity-broken cases (simulates missing chain)
            if d.get("_demo_meta", {}).get("integrity_broken"):
                continue

            try:
                await conn.execute(
                    """
                    INSERT INTO provenance_nodes
                        (node_id, node_type, tenant_id, content, content_hash, timestamp)
                    VALUES ($1,$2,$3,$4::jsonb,$5,$6)
                    ON CONFLICT (node_id, tenant_id) DO NOTHING
                    """,
                    f"decision-{d['case_id']}",
                    "prov:Entity",
                    d["tenant_id"],
                    json.dumps(content),
                    content_hash,
                    datetime.fromisoformat(d["decision_timestamp"]).replace(tzinfo=None),
                )
                prov_inserted += 1
            except Exception:
                pass

        print(f"✓ Inserted {prov_inserted} provenance nodes")
        print(f"  (10 nodes intentionally omitted — integrity break simulation)")

    finally:
        await conn.close()

    print("\n✅ Database seeding complete")
    print("   Start SENTINEL: make dev")


if __name__ == "__main__":
    asyncio.run(seed())
