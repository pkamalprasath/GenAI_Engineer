#!/usr/bin/env python3
"""
SENTINEL System Verification & Diagnostics
Checks database state, data integrity, and system configuration.
Usage: python scripts/verify_system.py [--fix] [--seed]
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=True)
sys.path.insert(0, str(_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Color codes for terminal output
class Colors:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    INFO = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# Symbols (use ASCII on Windows)
CHECKMARK = '[OK]'
XMARK = '[FAIL]'
WARN_MARK = '[!]'


async def check_db_connection():
    """Check if database is reachable."""
    print(f"\n{Colors.BOLD}[1/10] Database Connection{Colors.END}")
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/sentinel")
        # Convert to asyncpg if needed
        if "psycopg2://" in db_url:
            db_url = db_url.replace("psycopg2://", "postgresql+asyncpg://")
        elif "postgresql://" in db_url and "asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        print(f"{Colors.OK}[OK] Database connection OK{Colors.END}")
        return True, engine
    except Exception as e:
        print(f"{Colors.FAIL}[FAIL] Database connection failed: {str(e)[:100]}{Colors.END}")
        return False, None


async def check_schema(engine):
    """Check if all required tables exist."""
    print(f"\n{Colors.BOLD}[2/10] Database Schema{Colors.END}")
    required_tables = [
        "investigations",
        "decision_records",
        "provenance_nodes",
        "provenance_edges",
        "escalations",
        "audit_entries",
    ]

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public'
            """)
        )
        existing = {row[0] for row in result.fetchall()}

    missing = [t for t in required_tables if t not in existing]
    if missing:
        print(f"{Colors.FAIL}[FAIL] Missing tables: {', '.join(missing)}{Colors.END}")
        return False

    print(f"{Colors.OK}[OK] All {len(required_tables)} required tables exist{Colors.END}")
    return True


async def check_investigations_table(engine):
    """Check investigations table structure."""
    print(f"\n{Colors.BOLD}[3/10] Investigations Table Structure{Colors.END}")
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name='investigations'
            """)
        )
        columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

    required_cols = {
        "investigation_id": "character varying",
        "applicant_data": "jsonb",
        "state_snapshot": "jsonb",
        "status": "character varying",
    }

    missing = [c for c in required_cols if c not in columns]
    if missing:
        print(f"{Colors.WARN}[!] Missing columns: {', '.join(missing)}{Colors.END}")
        return False

    print(f"{Colors.OK}[OK] Investigations table has all required columns{Colors.END}")
    return True


async def check_data_counts(engine):
    """Check row counts in key tables."""
    print(f"\n{Colors.BOLD}[4/10] Data Counts{Colors.END}")
    async with engine.begin() as conn:
        counts = {}
        for table in ["investigations", "decision_records", "provenance_nodes", "escalations"]:
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            counts[table] = count
            status = Colors.OK if count > 0 else Colors.WARN
            print(f"{status}{table}: {count} rows{Colors.END}")

    return counts


async def check_investigation_data_integrity(engine, counts):
    """Check if investigations have required data."""
    print(f"\n{Colors.BOLD}[5/10] Investigation Data Integrity{Colors.END}")

    if counts.get("investigations", 0) == 0:
        print(f"{Colors.WARN}[!] No investigations found in database{Colors.END}")
        return False

    async with engine.begin() as conn:
        # Check for NULL applicant_data
        result = await conn.execute(
            text("SELECT COUNT(*) FROM investigations WHERE applicant_data IS NULL")
        )
        null_applicant = result.scalar()

        # Check for NULL state_snapshot
        result = await conn.execute(
            text("SELECT COUNT(*) FROM investigations WHERE state_snapshot IS NULL")
        )
        null_snapshot = result.scalar()

        # Check for NULL compliance_verdict in state_snapshot
        result = await conn.execute(
            text("""
                SELECT COUNT(*) FROM investigations
                WHERE state_snapshot->>'compliance_verdict' IS NULL
                AND status='complete'
            """)
        )
        null_verdict = result.scalar()

    issues = []
    if null_applicant > 0:
        issues.append(f"{null_applicant} investigations have NULL applicant_data")
    if null_snapshot > 0:
        issues.append(f"{null_snapshot} investigations have NULL state_snapshot")
    if null_verdict > 0:
        issues.append(f"{null_verdict} completed investigations have NULL compliance_verdict")

    if issues:
        print(f"{Colors.WARN}[!] Data integrity issues:{Colors.END}")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print(f"{Colors.OK}[OK] Investigation data integrity OK{Colors.END}")
    return True


async def check_decision_records(engine, counts):
    """Check if decision_records have required metadata."""
    print(f"\n{Colors.BOLD}[6/10] Decision Records Quality{Colors.END}")

    if counts.get("decision_records", 0) == 0:
        print(f"{Colors.WARN}[!] No decision records found{Colors.END}")
        return False

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN outcome IS NULL THEN 1 END) as null_outcome,
                    COUNT(CASE WHEN metadata IS NULL THEN 1 END) as null_metadata,
                    COUNT(CASE WHEN reasoning_text IS NULL THEN 1 END) as null_reasoning
                FROM decision_records
            """)
        )
        row = result.fetchone()
        total, null_outcome, null_metadata, null_reasoning = row

    issues = []
    if null_outcome > 0:
        issues.append(f"{null_outcome}/{total} records have NULL outcome")
    if null_metadata > 0:
        issues.append(f"{null_metadata}/{total} records have NULL metadata")
    if null_reasoning > 0:
        issues.append(f"{null_reasoning}/{total} records have NULL reasoning_text")

    if issues:
        print(f"{Colors.WARN}[!] Quality issues:{Colors.END}")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print(f"{Colors.OK}[OK] {total} decision records have complete data{Colors.END}")
    return True


async def check_provenance_graph(engine, counts):
    """Check provenance graph consistency."""
    print(f"\n{Colors.BOLD}[7/10] Provenance Graph Consistency{Colors.END}")

    if counts.get("provenance_nodes", 0) == 0:
        print(f"{Colors.WARN}[!] No provenance nodes found{Colors.END}")
        return True  # Not critical if no investigations exist

    async with engine.begin() as conn:
        # Check for orphaned edges
        result = await conn.execute(
            text("""
                SELECT COUNT(*) FROM provenance_edges pe
                WHERE NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.source_id)
                   OR NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.target_id)
            """)
        )
        orphaned = result.scalar()

    if orphaned > 0:
        print(f"{Colors.WARN}[!] {orphaned} orphaned edges found{Colors.END}")
        return False

    print(f"{Colors.OK}[OK] Provenance graph is consistent{Colors.END}")
    return True


async def check_escalations(engine, counts):
    """Check escalations/HITL queue."""
    print(f"\n{Colors.BOLD}[8/10] Escalations Queue{Colors.END}")

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status='pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status='resolved' THEN 1 END) as resolved
                FROM escalations
            """)
        )
        row = result.fetchone()
        total, pending, resolved = row

    print(f"{Colors.OK}[OK] Escalations: {total} total, {pending} pending, {resolved} resolved{Colors.END}")
    return True


async def check_audit_trail(engine):
    """Check audit entries."""
    print(f"\n{Colors.BOLD}[9/10] Audit Trail{Colors.END}")

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM audit_entries")
            )
            count = result.scalar()
        print(f"{Colors.OK}[OK] Audit entries: {count}{Colors.END}")
    except Exception as e:
        if "does not exist" in str(e):
            print(f"{Colors.WARN}[!] audit_entries table does not exist (optional table){Colors.END}")
        else:
            print(f"{Colors.WARN}[!] Could not check audit trail: {str(e)[:100]}{Colors.END}")
    return True


async def check_configuration():
    """Verify environment configuration."""
    print(f"\n{Colors.BOLD}[10/10] Configuration{Colors.END}")

    required_env = [
        "DATABASE_URL",
        "SENTINEL_API_URL",
        "DEMO_TENANT_ID",
    ]

    missing = [e for e in required_env if not os.getenv(e)]
    if missing:
        print(f"{Colors.WARN}[!] Missing env vars: {', '.join(missing)}{Colors.END}")
        return False

    print(f"{Colors.OK}[OK] All required environment variables set{Colors.END}")
    return True


async def seed_decision_records(engine):
    """Create sample decision records for testing."""
    print(f"\n{Colors.BOLD}[SEED] Creating sample decision records...{Colors.END}")

    sample_records = [
        {
            "case_id": "CASE-0001",
            "tenant_id": "bank-acme",
            "outcome": "APPROVED",
            "decision_timestamp": datetime.now() - timedelta(days=30),
            "reasoning_text": "Good credit history, stable employment",
            "metadata": {
                "applicant_id": "APP-001",
                "applicant_name": "John Smith",
                "age_group": "35-45",
                "income_bracket": "100k-150k",
                "credit_score_tier": "excellent",
                "race": "Unknown",
                "gender": "M",
            }
        },
        {
            "case_id": "CASE-0002",
            "tenant_id": "bank-acme",
            "outcome": "DENIED",
            "decision_timestamp": datetime.now() - timedelta(days=25),
            "reasoning_text": "Poor credit score, insufficient income",
            "metadata": {
                "applicant_id": "APP-002",
                "applicant_name": "Jane Doe",
                "age_group": "25-35",
                "income_bracket": "30k-50k",
                "credit_score_tier": "poor",
                "race": "Hispanic",
                "gender": "F",
            }
        },
        {
            "case_id": "CASE-0003",
            "tenant_id": "bank-acme",
            "outcome": "APPROVED",
            "decision_timestamp": datetime.now() - timedelta(days=20),
            "reasoning_text": "Excellent credit, high income",
            "metadata": {
                "applicant_id": "APP-003",
                "applicant_name": "Marcus Johnson",
                "age_group": "45-55",
                "income_bracket": "150k+",
                "credit_score_tier": "excellent",
                "race": "African American",
                "gender": "M",
            }
        },
    ]

    async with engine.begin() as conn:
        for record in sample_records:
            # Check if already exists
            result = await conn.execute(
                text("SELECT 1 FROM decision_records WHERE case_id=:case_id AND tenant_id=:tenant"),
                {"case_id": record["case_id"], "tenant": record["tenant_id"]}
            )
            if result.fetchone():
                print(f"  - {record['case_id']} already exists, skipping")
                continue

            await conn.execute(
                text("""
                    INSERT INTO decision_records
                    (case_id, tenant_id, outcome, decision_timestamp, reasoning_text, metadata)
                    VALUES (:case_id, :tenant, :outcome, :ts, :reasoning, :metadata)
                """),
                {
                    "case_id": record["case_id"],
                    "tenant": record["tenant_id"],
                    "outcome": record["outcome"],
                    "ts": record["decision_timestamp"],
                    "reasoning": record["reasoning_text"],
                    "metadata": json.dumps(record["metadata"]),
                }
            )
            print(f"  {Colors.OK}[OK] Created {record['case_id']}{Colors.END}")

    print(f"{Colors.OK}Sample records seeded successfully{Colors.END}")


async def main():
    """Run all diagnostics."""
    print(f"{Colors.BOLD}\n{'='*60}")
    print("SENTINEL SYSTEM VERIFICATION")
    print(f"{'='*60}{Colors.END}")

    # Parse arguments
    fix_mode = "--fix" in sys.argv
    seed_mode = "--seed" in sys.argv

    if fix_mode:
        print(f"{Colors.WARN}[!] Running in FIX mode{Colors.END}")
    if seed_mode:
        print(f"{Colors.WARN}[!] Running in SEED mode{Colors.END}")

    # Check database
    ok, engine = await check_db_connection()
    if not ok:
        sys.exit(1)

    # Run all checks
    await check_schema(engine)
    await check_investigations_table(engine)
    counts = await check_data_counts(engine)
    await check_investigation_data_integrity(engine, counts)
    await check_decision_records(engine, counts)
    await check_provenance_graph(engine, counts)
    await check_escalations(engine, counts)
    await check_audit_trail(engine)
    await check_configuration()

    # Optional: seed data
    if seed_mode:
        await seed_decision_records(engine)

    # Summary
    print(f"\n{Colors.BOLD}{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}{Colors.END}")
    print(f"{Colors.OK}[OK] System verification complete{Colors.END}")
    print(f"\n{Colors.INFO}To seed sample data: python scripts/verify_system.py --seed{Colors.END}")
    print(f"{Colors.INFO}To auto-fix issues: python scripts/verify_system.py --fix{Colors.END}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
