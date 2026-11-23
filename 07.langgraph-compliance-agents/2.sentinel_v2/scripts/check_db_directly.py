"""
Check what's actually stored in the database
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from configs.settings import settings

async def check_db():
    """Check what's in the database"""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        try:
            print("\n=== Checking last 3 investigations ===")

            result = await db.execute(
                text("""
                    SELECT investigation_id, tenant_id, status, applicant_data
                    FROM investigations
                    WHERE tenant_id = 'test-tenant'
                    ORDER BY created_at DESC
                    LIMIT 3
                """)
            )

            rows = result.fetchall()
            if rows:
                for i, row in enumerate(rows, 1):
                    print(f"\n[{i}] Investigation: {row.investigation_id}")
                    print(f"    Tenant: {row.tenant_id}")
                    print(f"    Status: {row.status}")
                    print(f"    applicant_data is NULL: {row.applicant_data is None}")
                    print(f"    applicant_data type: {type(row.applicant_data)}")
                    if row.applicant_data:
                        print(f"    applicant_data value: {row.applicant_data}")
                    else:
                        print(f"    applicant_data value: NULL")
            else:
                print("[INFO] No test-tenant investigations found")

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

asyncio.run(check_db())
