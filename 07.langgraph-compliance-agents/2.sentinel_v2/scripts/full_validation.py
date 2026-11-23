"""
COMPREHENSIVE VALIDATION OF SENTINEL v2 SYSTEM
Checks every component: API, Database, Graph Execution, Results
"""
import os
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()

import httpx
import asyncpg

async def validate_all():
    print("=" * 80)
    print("SENTINEL v2 SYSTEM VALIDATION")
    print("=" * 80)

    api_url = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
    api_key = os.getenv("SENTINEL_API_KEY", "")
    tenant_id = os.getenv("DEMO_TENANT_ID", "bank-acme")
    HEADERS = {"X-API-Key": api_key, "X-Tenant-ID": tenant_id}

    # 1. API HEALTH
    print("\n[1] API SERVER")
    try:
        r = httpx.get(f"{api_url}/health", timeout=5)
        print(f"  ✓ API is running: {r.json()}")
    except Exception as e:
        print(f"  ✗ API error: {e}")
        return

    # 2. DATABASE
    print("\n[2] DATABASE")
    try:
        db_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(db_url)

        count = await conn.fetchval("SELECT COUNT(*) FROM investigations")
        print(f"  ✓ Database connected: {count} investigations exist")

        # Get one investigation
        inv = await conn.fetchrow("""
            SELECT investigation_id, status, applicant_data, state_snapshot, created_at
            FROM investigations ORDER BY created_at DESC LIMIT 1
        """)

        if inv:
            print(f"\n  Latest Investigation:")
            print(f"    ID: {inv['investigation_id']}")
            print(f"    Status: {inv['status']}")
            print(f"    Has applicant_data: {bool(inv['applicant_data'])}")
            print(f"    Has state_snapshot: {bool(inv['state_snapshot'])}")

            if inv['state_snapshot']:
                state = json.loads(inv['state_snapshot']) if isinstance(inv['state_snapshot'], str) else inv['state_snapshot']
                print(f"    State keys: {list(state.keys())}")
                print(f"    Verdict: {state.get('compliance_verdict', 'N/A')}")
        else:
            print("  ✗ No investigations found")

        await conn.close()

    except Exception as e:
        print(f"  ✗ Database error: {e}")

    # 3. CREATE & EXECUTE INVESTIGATION
    print("\n[3] INVESTIGATION CREATION & EXECUTION")
    try:
        # Create
        payload = {
            "query": "Validation test investigation",
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "applicant_data": {
                "applicant_id": "VALIDATION_001",
                "applicant_name": "Test Applicant",
                "age": 35,
                "income": 80000,
                "credit_score": 720,
                "denied": False
            }
        }

        r = httpx.post(f"{api_url}/api/v1/investigations", json=payload, headers=HEADERS, timeout=30)
        if r.status_code != 202:
            print(f"  ✗ Failed to create investigation: {r.status_code} {r.text[:200]}")
        else:
            inv_data = r.json()
            inv_id = inv_data["investigation_id"]
            print(f"  ✓ Investigation created: {inv_id}")

            # Execute
            print(f"  Executing investigation...")
            r = httpx.post(
                f"{api_url}/api/v1/investigations/{inv_id}/execute-sync",
                json={},
                headers=HEADERS,
                timeout=90
            )

            if r.status_code != 200:
                print(f"  ✗ Execution failed: {r.status_code}")
                print(f"    Response: {r.text[:300]}")
            else:
                result = r.json()
                print(f"  ✓ Execution completed")
                print(f"    Verdict: {result.get('compliance_verdict', 'N/A')}")
                print(f"    Risk: {result.get('regulatory_risk', 'N/A')}")
                print(f"    Report length: {len(result.get('final_report', '')) if result.get('final_report') else 0}")

    except Exception as e:
        print(f"  ✗ Error: {e}")

    # 4. RETRIEVE RESULTS
    print("\n[4] RESULTS RETRIEVAL")
    try:
        conn = await asyncpg.connect(db_url)
        inv = await conn.fetchrow("""
            SELECT investigation_id, status, state_snapshot
            FROM investigations WHERE status = 'complete'
            ORDER BY completed_at DESC LIMIT 1
        """)

        if inv:
            print(f"  ✓ Found completed investigation: {inv['investigation_id']}")
            state = json.loads(inv['state_snapshot']) if isinstance(inv['state_snapshot'], str) else inv['state_snapshot']
            print(f"    Verdict: {state.get('compliance_verdict')}")
            print(f"    Risk: {state.get('regulatory_risk')}")
            print(f"    Bias Detected: {state.get('bias_detected')}")
        else:
            print(f"  ⚠ No completed investigations found")

        await conn.close()

    except Exception as e:
        print(f"  ✗ Error: {e}")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

asyncio.run(validate_all())
