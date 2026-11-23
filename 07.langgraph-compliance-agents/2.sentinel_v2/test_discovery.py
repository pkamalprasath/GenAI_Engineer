#!/usr/bin/env python3
"""Test discovery query."""
import asyncpg
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime as _dt

load_dotenv()

async def test_query():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        tenant_id = 'bank-acme'
        date_range = {'from': '2024-01-03', 'to': '2024-01-03'}

        date_from = _dt.fromisoformat(date_range.get('from', '2000-01-01'))
        date_to = _dt.fromisoformat(date_range.get('to', '2099-12-31')).replace(hour=23, minute=59, second=59)

        print(f'Date from: {date_from}')
        print(f'Date to: {date_to}')

        result = await conn.fetch('''
            SELECT case_id, outcome, decision_timestamp
            FROM decision_records
            WHERE tenant_id = $1 AND decision_timestamp >= $2 AND decision_timestamp <= $3
            ORDER BY decision_timestamp DESC LIMIT 500
        ''', tenant_id, date_from, date_to)

        print(f'Query returned: {len(result)} records')
        for r in result[:5]:
            print(f'  - {r["case_id"]}: {r["outcome"]}')

    finally:
        await conn.close()

asyncio.run(test_query())
