# SENTINEL Diagnostics & System Verification

## Quick Start

When something isn't working, run these commands in order:

### 1. Quick Health Check (30 seconds)
```bash
bash scripts/quick_health_check.sh
```
Shows:
- ✓ API is running
- ✓ Database is connected
- ✓ Decision records exist
- ✓ Ollama is running

### 2. Full System Diagnostic (2 minutes)
```bash
python scripts/verify_system.py
```
Checks:
- Database schema completeness
- Data integrity (NULLs, missing fields)
- Configuration
- Audit trail

### 3. Check Specific Investigation
```bash
# Show what went wrong with INV-XXXXXX
bash scripts/quick_health_check.sh INV-XXXXXX
```

### 4. Seed Sample Data (if empty)
```bash
python scripts/verify_system.py --seed
```
Creates 3 sample decision records with complete data.

---

## Problem Diagnosis Matrix

| Symptom | Run This | What to Fix |
|---------|----------|-----------|
| "Case UNKNOWN" in Provenance | `python scripts/verify_system.py` | Seed data: `--seed` flag |
| N/A verdict on Results | `bash scripts/quick_health_check.sh INV-XXX` | Check State snapshot exists |
| Investigation stuck "queued" | `curl -X POST .../execute-sync` | Manually trigger execution |
| "No provenance nodes found" | Check decision_records count | Create test data |
| Empty decision_records table | `python scripts/verify_system.py --seed` | Load sample data |
| 500 errors in API | Check API logs | Restart API, check DB |

---

## Running Diagnostics

### Python Verification Script

```bash
cd projects/sentinel_v2

# Full diagnostic report
python scripts/verify_system.py

# With color-coded output
python scripts/verify_system.py 2>&1 | less -R

# Seed sample data
python scripts/verify_system.py --seed

# Validate after seeding
python scripts/verify_system.py
```

**Output Example:**
```
[1/10] Database Connection
✓ Database connection OK

[2/10] Database Schema
✓ All 6 required tables exist

[3/10] Investigations Table Structure
✓ Investigations table has all required columns

[4/10] Data Counts
investigations: 42 rows
decision_records: 156 rows
provenance_nodes: 128 rows
escalations: 3 rows

[5/10] Investigation Data Integrity
✓ Investigation data integrity OK

[6/10] Decision Records Quality
✓ 156 decision records have complete data

[7/10] Provenance Graph Consistency
✓ Provenance graph is consistent

[8/10] Escalations Queue
✓ Escalations: 3 total, 1 pending, 2 resolved

[9/10] Audit Trail
✓ Audit entries: 847

[10/10] Configuration
✓ All required environment variables set
```

### Bash Health Check

```bash
bash scripts/quick_health_check.sh
```

**Output Example:**
```
============================================
SENTINEL Health Check
============================================

[1] API Server
✓ API running at http://localhost:8003

[2] Database
✓ Database connected
  Investigations: 42

[3] Decision Records
  Count: 156
✓ Decision records exist

[5] System Health
✓ Ollama running
✓ API process running
✓ PostgreSQL running

============================================
System appears healthy
============================================
```

### Check Specific Investigation

```bash
bash scripts/quick_health_check.sh INV-A945C573B6E2

# Output:
# [4] Investigation: INV-A945C573B6E2
#   Status: complete
#   ✓ State snapshot exists
#   Verdict: UNCERTAIN
#   Provenance nodes: 3
#   Relevant cases: 2
```

---

## Manual SQL Diagnostics

### Check Investigation State

```sql
-- See all investigations with their status
SELECT investigation_id, status, created_at, completed_at,
       (state_snapshot IS NOT NULL) as has_snapshot
FROM investigations
ORDER BY created_at DESC
LIMIT 10;

-- Check a specific investigation
SELECT investigation_id, status, applicant_data, 
       state_snapshot->'compliance_verdict' as verdict,
       state_snapshot->'regulatory_risk' as risk
FROM investigations
WHERE investigation_id='INV-XXXXXX';
```

### Check Discovery Results

```sql
-- See what cases were discovered for an investigation
SELECT investigation_id,
       state_snapshot->'relevant_case_ids' as found_cases,
       state_snapshot->'case_count' as case_count,
       state_snapshot->'discovery_confidence' as confidence
FROM investigations
WHERE investigation_id='INV-XXXXXX';
```

### Check Decision Records

```sql
-- Count by tenant
SELECT tenant_id, COUNT(*) as count
FROM decision_records
GROUP BY tenant_id;

-- See sample records
SELECT case_id, outcome, metadata, reasoning_text
FROM decision_records
WHERE tenant_id='bank-acme'
LIMIT 5;

-- Check data quality
SELECT COUNT(*) as total,
       COUNT(CASE WHEN metadata IS NULL THEN 1 END) as null_metadata,
       COUNT(CASE WHEN outcome IS NULL THEN 1 END) as null_outcome
FROM decision_records;
```

### Check Provenance Graph

```sql
-- Count nodes and edges
SELECT 
  (SELECT COUNT(*) FROM provenance_nodes) as node_count,
  (SELECT COUNT(*) FROM provenance_edges) as edge_count;

-- See nodes for an investigation
SELECT node_id, node_type, content->'case_id' as case_id
FROM provenance_nodes
WHERE content->>'investigation_id' = 'INV-XXXXXX'
LIMIT 20;

-- Check for orphaned edges
SELECT COUNT(*) as orphaned
FROM provenance_edges pe
WHERE NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.source_id)
   OR NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.target_id);
```

---

## Environment Verification

```bash
# Check required env vars
env | grep -E "DATABASE_URL|SENTINEL_API_URL|DEMO_TENANT_ID|OPENAI_API_KEY|OLLAMA"

# Check .env file exists
cat projects/sentinel_v2/.env | head -20

# Test database connection
psql $DATABASE_URL -c "SELECT version();"

# Test API connectivity
curl http://localhost:8003/health | jq .

# Test Ollama
curl http://localhost:11434/api/tags | jq '.models[0]'
```

---

## Fixing Common Issues

### Issue: Empty decision_records Table

```bash
# Verify it's empty
psql $DATABASE_URL -c "SELECT COUNT(*) FROM decision_records;"
# Output: 0

# Seed sample data
python scripts/verify_system.py --seed

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) FROM decision_records;"
# Output: 3
```

### Issue: N/A Values Everywhere

```bash
# Check what's missing
psql $DATABASE_URL -c "
SELECT investigation_id, status,
       state_snapshot->'compliance_verdict' as verdict,
       state_snapshot->'regulatory_risk' as risk,
       state_snapshot IS NOT NULL as has_snapshot
FROM investigations
WHERE status='complete'
ORDER BY created_at DESC
LIMIT 5;
"

# If state_snapshot is NULL: investigation didn't complete
# - Check API logs for errors
# - Run verification: python scripts/verify_system.py

# If verdict is NULL: legal_agent didn't produce output
# - Check if legal_agent ran (grep for "legal_analysis_complete" in logs)
# - Check case_count > 0 (discovery found cases)
```

### Issue: Investigation Stuck "Queued"

```bash
# Manually execute it
curl -X POST \
  -H "X-API-Key: YOUR_KEY" \
  -H "X-Tenant-ID: bank-acme" \
  http://localhost:8003/api/v1/investigations/INV-XXXXXX/execute-sync

# Wait for completion
sleep 5

# Check status
psql $DATABASE_URL -c "
SELECT status, completed_at FROM investigations
WHERE investigation_id='INV-XXXXXX';
"
```

---

## Logging & Debugging

### Check API Logs
```bash
# Recent API logs
tail -100 logs/sentinel.log

# Errors only
grep ERROR logs/sentinel.log | tail -20

# Agent execution
grep "agent_name\|event.*complete" logs/sentinel.log | tail -30

# Specific investigation
grep "INV-XXXXXX" logs/sentinel.log
```

### Enable Debug Logging
```bash
# In .env:
LOG_LEVEL=DEBUG

# Restart API:
pkill -f "uvicorn sentinel"
uvicorn sentinel.api.main:app --port 8003 --reload
```

### Check Graph Execution
```bash
# Look for graph state transitions
grep "graph_state\|node_complete\|edge_route" logs/sentinel.log

# Look for tool calls (ToolNode)
grep "tool_calls\|legal_tools" logs/sentinel.log
```

---

## Testing the Fix

After running `python scripts/verify_system.py --seed`, test end-to-end:

```bash
# 1. Start API
uvicorn sentinel.api.main:app --port 8003 &

# 2. Create investigation via dashboard
# - Go to http://localhost:8501
# - Investigate page → Enter query → Create

# 3. Check results
bash scripts/quick_health_check.sh INV-XXXXXX

# 4. Verify in database
psql $DATABASE_URL -c "
SELECT investigation_id, status,
       state_snapshot->'compliance_verdict' as verdict
FROM investigations
ORDER BY created_at DESC
LIMIT 1;
"

# Expected: verdict is "COMPLIANT", "VIOLATION", or "UNCERTAIN" (NOT N/A)
```

---

## When All Else Fails

### Complete System Reset
```bash
# WARNING: This deletes all investigations and decision records

# 1. Backup current data (optional)
pg_dump $DATABASE_URL > backup.sql

# 2. Drop and recreate tables
psql $DATABASE_URL -f sentinel/db/migrations/001_initial_schema.sql

# 3. Seed sample data
python scripts/verify_system.py --seed

# 4. Verify
python scripts/verify_system.py
```

### Check Individual Agent

```bash
# Test discovery agent directly
python -c "
import asyncio
from sentinel.agents.discovery_agent import run as discovery_run
from sentinel.state.investigation_state import make_initial_state
from sentinel.db.session import AsyncSessionFactory

async def test():
    state = make_initial_state('TEST-INV', 'bank-acme', 'loan applicant denied', {})
    async with AsyncSessionFactory() as session:
        result = await discovery_run(state, session)
        print(f'Cases found: {result.get(\"case_count\")}')
        print(f'Confidence: {result.get(\"discovery_confidence\")}')

asyncio.run(test())
"
```

---

## Support Information

When asking for help, include:

1. **Verification report:**
   ```bash
   python scripts/verify_system.py > report.txt 2>&1
   # Attach report.txt
   ```

2. **Investigation details:**
   ```bash
   bash scripts/quick_health_check.sh INV-XXXXXX > inv_status.txt
   # Attach inv_status.txt
   ```

3. **API logs (last 50 lines):**
   ```bash
   tail -50 logs/sentinel.log > api_logs.txt
   # Attach api_logs.txt
   ```

4. **Database state:**
   ```bash
   psql $DATABASE_URL -c "
   SELECT COUNT(*) as investigations,
          COUNT(CASE WHEN state_snapshot IS NULL THEN 1 END) as null_snapshots,
          COUNT(CASE WHEN status='complete' THEN 1 END) as completed
   FROM investigations;
   " > db_state.txt
   # Attach db_state.txt
   ```

5. **Describe the issue:**
   - What you did
   - What you expected
   - What actually happened
   - Screenshot if UI issue
