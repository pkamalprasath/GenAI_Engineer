# SENTINEL System Verification & Troubleshooting Guide

## Quick Diagnostics

Run the comprehensive verification script to check all system components:

```bash
cd projects/sentinel_v2

# Full system diagnostic
python scripts/verify_system.py

# Diagnostic + seed sample data
python scripts/verify_system.py --seed

# Diagnostic + auto-fix issues (future)
python scripts/verify_system.py --fix
```

The script checks:
- ✓ Database connectivity
- ✓ Schema completeness (all tables exist)
- ✓ Table structure (required columns)
- ✓ Data row counts
- ✓ Data integrity (NULLs, missing fields)
- ✓ Decision records quality
- ✓ Provenance graph consistency
- ✓ Escalations/HITL queue
- ✓ Audit trail
- ✓ Environment configuration

---

## Common Issues & Solutions

### Issue 1: "Case UNKNOWN" in Provenance Page

**Symptoms:**
- Provenance page shows "Case UNKNOWN" with empty `{}`
- Evidence Items: "No evidence items found"
- Decision Chain Summary: all N/A values

**Root Causes:**
1. **Decision records are empty** — no cases in DB with applicant metadata
2. **Discovery found 0 cases** — query didn't match any records
3. **Case metadata is NULL** — `metadata` column in decision_records is empty

**Solutions:**
```bash
# Check decision records count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM decision_records;"

# Check if they have metadata
psql $DATABASE_URL -c "
SELECT case_id, outcome, metadata
FROM decision_records
WHERE tenant_id='bank-acme'
LIMIT 3;
"

# If empty, seed sample data
python scripts/verify_system.py --seed

# Verify data exists
psql $DATABASE_URL -c "
SELECT COUNT(*), COUNT(CASE WHEN metadata IS NOT NULL THEN 1 END)
FROM decision_records;
"
```

---

### Issue 2: N/A Values in Results Page

**Symptoms:**
- Compliance Verdict: N/A
- Regulatory Risk: N/A
- Bias Detected: N/A

**Root Causes:**
1. **state_snapshot is NULL** — investigation didn't complete
2. **Legal/Bias agents didn't run** — due to graph routing
3. **LLM response was empty** — agent couldn't parse response

**Solutions:**
```bash
# Check investigation status
psql $DATABASE_URL -c "
SELECT investigation_id, status, state_snapshot, created_at
FROM investigations
ORDER BY created_at DESC
LIMIT 5;
"

# Check if state_snapshot exists
psql $DATABASE_URL -c "
SELECT investigation_id, status, state_snapshot IS NOT NULL as has_snapshot
FROM investigations
WHERE status='complete'
ORDER BY created_at DESC
LIMIT 5;
"

# Check API logs for agent failures
# Look for: "event":"agent_failed" in logs

# Re-run investigation via dashboard
# POST /api/v1/investigations/{id}/execute-sync
```

---

### Issue 3: Empty Provenance Graph

**Symptoms:**
- "No provenance nodes found for this investigation"
- Provenance page shows no chain
- Graph is blank

**Root Causes:**
1. **Investigation_agent returned early** — case_ids was empty
2. **Provenance nodes not written to DB** — INSERT failed silently
3. **Graph query failed** — SQL error in provenance endpoint

**Solutions:**
```bash
# Check provenance nodes exist
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM provenance_nodes
WHERE tenant_id='bank-acme';
"

# Check for a specific investigation
psql $DATABASE_URL -c "
SELECT node_id, node_type, content
FROM provenance_nodes
WHERE content->>'investigation_id' = 'INV-XXXXXX'
LIMIT 10;
"

# Check API logs for provenance endpoint errors
curl -H "X-Tenant-ID: bank-acme" \
  http://localhost:8003/api/v1/provenance/INV-XXXXXX/trace

# If 500: check investigation exists in DB first
psql $DATABASE_URL -c "
SELECT investigation_id, status
FROM investigations
WHERE investigation_id='INV-XXXXXX';
"
```

---

### Issue 4: Investigation Stuck in "Queued"

**Symptoms:**
- Investigation status stays "queued" forever
- Progress bar doesn't move
- Results page shows "Executing queued investigation..."

**Root Causes:**
1. **execute-sync endpoint not called** — investigation created but not executed
2. **execute-sync timed out** — graph execution took > 60s
3. **Background job queue broken** — Redis/worker not running

**Solutions:**
```bash
# Check if investigation is in queued state
psql $DATABASE_URL -c "
SELECT investigation_id, status, created_at, completed_at
FROM investigations
WHERE status='queued'
ORDER BY created_at DESC;
"

# Manually trigger execution via API
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Tenant-ID: bank-acme" \
  http://localhost:8003/api/v1/investigations/INV-XXXXXX/execute-sync

# Check if API is running
curl http://localhost:8003/health

# Check for graph errors in logs
# Look for: "event":"graph_error" or stack traces

# If execute-sync hangs, check discovery_agent
# - Is Ollama running? (should be at localhost:11434)
# - Are there stuck processes? ps aux | grep ollama
```

---

### Issue 5: Missing Applicant Data

**Symptoms:**
- Investigation form doesn't populate applicant fields
- Applicant: "Unknown" in results
- applicant_data is NULL in DB

**Root Causes:**
1. **applicant_data column missing from schema** — older migration didn't add it
2. **Dashboard didn't send applicant_data** — form not configured
3. **API didn't save applicant_data** — missing in POST handler

**Solutions:**
```bash
# Check if column exists
psql $DATABASE_URL -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name='investigations'
AND column_name='applicant_data';
"

# If missing, add it (should be done by 001_initial_schema.sql)
psql $DATABASE_URL -c "
ALTER TABLE investigations
ADD COLUMN applicant_data JSONB DEFAULT NULL;
"

# Check investigations with applicant_data
psql $DATABASE_URL -c "
SELECT investigation_id, applicant_data
FROM investigations
WHERE applicant_data IS NOT NULL
LIMIT 3;
"

# Verify dashboard sends applicant_data
# Check browser Network tab → POST /api/v1/investigations
# Should include applicant_data in request body
```

---

## Advanced Diagnostics

### Database Health Check

```bash
# Check table sizes
psql $DATABASE_URL -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname='public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check for slow queries
psql $DATABASE_URL -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
" 2>/dev/null || echo "pg_stat_statements not installed"

# Check indexes
psql $DATABASE_URL -c "
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname='public'
ORDER BY tablename, indexname;
"

# Check for deadlocks
psql $DATABASE_URL -c "
SELECT * FROM pg_locks
WHERE NOT granted;
"
```

### API Health Check

```bash
# Full health check
curl -v http://localhost:8003/health
curl -v -H "X-Tenant-ID: bank-acme" http://localhost:8003/ready

# Check API can reach database
curl -H "X-API-Key: test" \
  -H "X-Tenant-ID: bank-acme" \
  http://localhost:8003/api/v1/investigations

# Check provenance endpoint
curl -H "X-Tenant-ID: bank-acme" \
  http://localhost:8003/api/v1/provenance/INV-TEST/trace 2>&1 | jq .
```

### LLM & Model Health

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check if discovery model is loaded
curl http://localhost:11434/api/tags | jq '.models[] | select(.name | contains("llama"))'

# Check spaCy models
python -c "import spacy; print(spacy.load('en_core_web_sm'))"
```

---

## Step-by-Step Investigation Walkthrough

When an investigation shows "Case UNKNOWN" with N/A values:

### Step 1: Check Investigation Exists
```bash
INV_ID="INV-XXXXXX"  # from dashboard
psql $DATABASE_URL -c "
SELECT investigation_id, status, applicant_data, state_snapshot
FROM investigations
WHERE investigation_id='$INV_ID';
"
```
**Expected:** Row with status='complete' or 'analyzing', applicant_data and state_snapshot not NULL

### Step 2: Check Discovery Results
```bash
psql $DATABASE_URL -c "
SELECT investigation_id, status, state_snapshot->'relevant_case_ids' as case_ids
FROM investigations
WHERE investigation_id='$INV_ID';
" | jq '.[] | .state_snapshot.relevant_case_ids'
```
**Expected:** Array of case IDs like `["CASE-0001", "CASE-0002"]`  
**If empty:** Discovery found 0 cases — check decision_records exist

### Step 3: Check Decision Records for Those Cases
```bash
# If case_ids = ["CASE-0001"], check:
psql $DATABASE_URL -c "
SELECT case_id, outcome, metadata, decision_timestamp
FROM decision_records
WHERE case_id IN ('CASE-0001', 'CASE-0002', 'CASE-0003')
AND tenant_id='bank-acme';
"
```
**Expected:** Rows with non-NULL metadata  
**If missing:** Use `python scripts/verify_system.py --seed` to create sample data

### Step 4: Check Provenance Nodes
```bash
psql $DATABASE_URL -c "
SELECT node_id, node_type, content
FROM provenance_nodes
WHERE content->>'investigation_id' = '$INV_ID'
LIMIT 10;
"
```
**Expected:** activity-investigation-*, agent-investigation-*, decision-* nodes  
**If empty:** investigation_agent didn't run or didn't write nodes

### Step 5: Check Legal Agent Results
```bash
psql $DATABASE_URL -c "
SELECT investigation_id, state_snapshot->'compliance_verdict' as verdict,
       state_snapshot->'regulatory_risk' as risk
FROM investigations
WHERE investigation_id='$INV_ID';
"
```
**Expected:** verdict and risk are not NULL  
**If NULL:** legal_agent didn't complete — check logs for errors

### Step 6: Check State Snapshot Completeness
```bash
psql $DATABASE_URL -c "
SELECT investigation_id, jsonb_object_keys(state_snapshot) as keys
FROM investigations
WHERE investigation_id='$INV_ID';
"
```
**Expected:** Keys include: compliance_verdict, regulatory_risk, bias_detected, applicable_regulations, evidence_items

---

## Data Integrity Checks

### Check for Orphaned Records
```bash
# Investigations with no corresponding provenance nodes
psql $DATABASE_URL -c "
SELECT i.investigation_id
FROM investigations i
LEFT JOIN provenance_nodes pn ON pn.content->>'investigation_id' = i.investigation_id
WHERE pn.node_id IS NULL
AND i.status='complete';
"

# Provenance edges pointing to non-existent nodes
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM provenance_edges pe
WHERE NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.source_id)
   OR NOT EXISTS (SELECT 1 FROM provenance_nodes pn WHERE pn.node_id = pe.target_id);
"
```

### Check for NULL Values
```bash
# Investigations with incomplete state_snapshot
psql $DATABASE_URL -c "
SELECT COUNT(*), status
FROM investigations
WHERE state_snapshot IS NULL
GROUP BY status;
"

# Decision records missing metadata
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM decision_records
WHERE metadata IS NULL OR metadata = '{}'::jsonb;
"
```

---

## When to Ask for Help

Include this information when reporting issues:

1. **Run the verification script:**
   ```bash
   python scripts/verify_system.py > verify_report.txt 2>&1
   # Attach verify_report.txt
   ```

2. **Collect relevant logs:**
   ```bash
   # API logs from last hour
   tail -100 logs/sentinel.log

   # Database state
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM investigations; SELECT COUNT(*) FROM decision_records;"
   ```

3. **Specific investigation details:**
   ```bash
   INV_ID="INV-XXXXXX"
   psql $DATABASE_URL -c "
   SELECT investigation_id, status, created_at, completed_at,
          applicant_data, state_snapshot
   FROM investigations
   WHERE investigation_id='$INV_ID';
   " | jq .
   ```

4. **Browser console errors:**
   - Open DevTools (F12)
   - Go to Console tab
   - Take screenshot of any red error messages

5. **What you were trying to do:**
   - Step-by-step: "I entered query..., clicked Investigate, waited X seconds..."
   - Expected result: "Should show verdict and risk"
   - Actual result: "Shows N/A for all fields"

---

## Summary

| Issue | Quick Fix | Root Cause |
|-------|-----------|-----------|
| Case UNKNOWN | `python scripts/verify_system.py --seed` | Empty decision_records |
| N/A values | Check state_snapshot exists | LLM agent didn't run |
| No provenance | Check provenance_nodes exist | Investigation_agent failed |
| Stuck queued | POST execute-sync endpoint | Investigation not executed |
| Missing applicant | Check column exists | Schema not migrated |

Always start with: `python scripts/verify_system.py`
