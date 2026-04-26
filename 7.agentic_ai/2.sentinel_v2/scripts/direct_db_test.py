"""
Direct database test - check applicant_data storage without API
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = "postgresql+asyncpg://sentinel_user:sentinel_pass@localhost/sentinel_v2"

async def test_direct_insert():
    """Test inserting applicant_data directly to database"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    applicant_data = {
        "applicant_id": "TEST_DB_001",
        "applicant_name": "Test User",
        "race": "African American",
        "age": 35,
        "income": 45000,
        "credit_score": 620,
        "denied": True,
        "denial_reason": "credit_score_too_low",
    }

    async with async_session() as db:
        try:
            print("\n=== STEP 1: Direct INSERT with applicant_data ===")

            # Prepare JSON
            app_data_json = json.dumps(applicant_data)
            print(f"[DEBUG] JSON length: {len(app_data_json)}")
            print(f"[DEBUG] JSON preview: {app_data_json[:80]}")
            print(f"[DEBUG] app_data_json is None: {app_data_json is None}")

            # Insert with explicit CAST
            inv_id = "INV-DIRECT-TEST-001"
            await db.execute(
                text("""
                    INSERT INTO investigations (investigation_id, tenant_id, status, domain,
                                                trigger_mode, query, applicant_data)
                    VALUES (:id, :tenant, 'queued', 'financial_services', 'reactive', 'Test query',
                            CAST(:app_data AS jsonb))
                """),
                {
                    "id": inv_id,
                    "tenant": "test-tenant",
                    "app_data": app_data_json,
                }
            )
            await db.commit()
            print("[OK] INSERT successful")

            print("\n=== STEP 2: SELECT and verify ===")

            # Fetch back
            result = await db.execute(
                text("SELECT applicant_data FROM investigations WHERE investigation_id = :id"),
                {"id": inv_id}
            )
            row = result.fetchone()

            if row:
                print(f"[OK] Row found")
                print(f"[DEBUG] applicant_data type: {type(row.applicant_data)}")
                print(f"[DEBUG] applicant_data is None: {row.applicant_data is None}")
                print(f"[DEBUG] applicant_data value: {row.applicant_data}")

                if row.applicant_data is None:
                    print("[ERROR] applicant_data stored as NULL!")

                    # Check other columns to ensure insert worked
                    result2 = await db.execute(
                        text("SELECT investigation_id, status, query FROM investigations WHERE investigation_id = :id"),
                        {"id": inv_id}
                    )
                    row2 = result2.fetchone()
                    if row2:
                        print(f"[DEBUG] Other columns work fine: id={row2.investigation_id}, status={row2.status}")
                else:
                    print("[OK] applicant_data stored correctly!")
                    print(f"[DEBUG] Stored data: {row.applicant_data}")
            else:
                print("[ERROR] Row not found after INSERT!")

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_direct_insert())
