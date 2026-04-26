import os, asyncio, asyncpg
from dotenv import load_dotenv
load_dotenv()

async def cleanup():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    # Delete failed/queued
    deleted = await conn.execute("DELETE FROM investigations WHERE status IN ('failed', 'queued')")
    print(f"[OK] Deleted failed/queued investigations")

    count = await conn.fetchval('SELECT COUNT(*) FROM investigations')
    print(f"[OK] Clean investigations remaining: {count}")

    await conn.close()

asyncio.run(cleanup())
