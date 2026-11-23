# SENTINEL v2 — cURL Testing Cheatsheet

## Quick Reference for API Testing via Command Line

### Setup

```bash
# Set environment variables
export API_URL="http://localhost:8003"
export API_KEY="$(echo $SENTINEL_API_KEY)"  # From .env
export TENANT_ID="manual-testing"
```

---

## 1. Health Check

**Verify API is running:**

```bash
curl -s $API_URL/health | jq
```

**Expected:**
```json
{"status": "alive", "service": "sentinel-api"}
```

---

## 2. Create Investigation (Basic)

**No applicant data:**

```bash
curl -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Simple compliance investigation",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31"
  }' | jq
```

---

## 3. Create Investigation (With Applicant Data)

**Approved applicant:**

```bash
curl -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Compliance investigation for James Richardson",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "MANUAL_001",
      "applicant_name": "James Richardson",
      "age": 50,
      "race": "White",
      "gender": "Male",
      "income": 150000,
      "credit_score": 780,
      "denied": false
    }
  }' | jq
```

**Denied applicant:**

```bash
curl -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Compliance investigation for Maria Santos",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "MANUAL_002",
      "applicant_name": "Maria Santos",
      "age": 32,
      "race": "Hispanic",
      "gender": "Female",
      "income": 55000,
      "credit_score": 620,
      "denied": true,
      "denial_reason": "credit_score_too_low"
    }
  }' | jq
```

**Save investigation ID:**

```bash
INV_ID=$(curl -s -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{"query": "test", "date_from": "2026-01-01", "date_to": "2026-12-31"}' | jq -r '.investigation_id')

echo "Investigation ID: $INV_ID"
```

---

## 4. Execute Investigation Synchronously

**Run compliance analysis:**

```bash
curl -X POST $API_URL/api/v1/investigations/$INV_ID/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}' | jq
```

**With timeout (30 minutes):**

```bash
curl -X POST $API_URL/api/v1/investigations/$INV_ID/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}' \
  --max-time 1800 | jq
```

---

## 5. Retrieve Investigation Results

**Get full results:**

```bash
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq
```

**Get just the verdict:**

```bash
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq '.compliance_verdict'
```

**Get just the risk level:**

```bash
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq '.regulatory_risk'
```

**Get the report:**

```bash
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq -r '.final_report'
```

---

## 6. Complete End-to-End Test Script

**Save as `test_investigation.sh`:**

```bash
#!/bin/bash

# Configuration
API_URL="http://localhost:8003"
API_KEY="$(echo $SENTINEL_API_KEY)"
TENANT_ID="manual-testing"

echo "====== SENTINEL v2 Manual Test ======"

# Step 1: Create investigation
echo -e "\n[1] Creating investigation..."
RESPONSE=$(curl -s -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Compliance investigation test",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "TEST_001",
      "applicant_name": "Test User",
      "age": 45,
      "race": "White",
      "income": 100000,
      "credit_score": 720,
      "denied": false
    }
  }')

INV_ID=$(echo $RESPONSE | jq -r '.investigation_id')
echo "Investigation ID: $INV_ID"
echo "Status: $(echo $RESPONSE | jq -r '.status')"

# Step 2: Execute investigation
echo -e "\n[2] Executing investigation..."
EXEC_RESPONSE=$(curl -s -X POST $API_URL/api/v1/investigations/$INV_ID/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}')

echo "Execution Status: $(echo $EXEC_RESPONSE | jq -r '.status')"

# Step 3: Display results
echo -e "\n[3] Results:"
echo "  Verdict: $(echo $EXEC_RESPONSE | jq -r '.compliance_verdict')"
echo "  Risk: $(echo $EXEC_RESPONSE | jq -r '.regulatory_risk')"
echo "  Bias Detected: $(echo $EXEC_RESPONSE | jq -r '.bias_detected')"
echo "  Report Length: $(echo $EXEC_RESPONSE | jq -r '.final_report | length') chars"
echo -e "\n  Report Preview:"
echo "  $(echo $EXEC_RESPONSE | jq -r '.final_report' | head -c 300)..."

echo -e "\n[✓] Test Complete"
```

**Run it:**

```bash
chmod +x test_investigation.sh
./test_investigation.sh
```

---

## 7. Test Disparate Impact (Multiple Applications)

**Create 2 applications to test bias detection:**

```bash
# Application 1: Approved
INV1=$(curl -s -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Test application 1",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "BIAS_APP1",
      "applicant_name": "John Smith",
      "race": "White",
      "credit_score": 700,
      "income": 80000,
      "denied": false
    }
  }' | jq -r '.investigation_id')

echo "Application 1 ID: $INV1"

# Application 2: Denied (same credit, different race)
INV2=$(curl -s -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "query": "Test application 2",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "BIAS_APP2",
      "applicant_name": "Maria Garcia",
      "race": "Hispanic",
      "credit_score": 700,
      "income": 80000,
      "denied": true,
      "denial_reason": "other_factors"
    }
  }' | jq -r '.investigation_id')

echo "Application 2 ID: $INV2"

# Execute both
echo -e "\nExecuting application 1..."
curl -s -X POST $API_URL/api/v1/investigations/$INV1/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}' | jq '.compliance_verdict'

echo "Executing application 2..."
curl -s -X POST $API_URL/api/v1/investigations/$INV2/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}' | jq '.compliance_verdict'
```

---

## 8. Save Results to File

**Save investigation results:**

```bash
# Save as JSON
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq > result_$INV_ID.json

# Save report as text
curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq -r '.final_report' > report_$INV_ID.txt

# Create summary
cat > summary_$INV_ID.txt << EOF
Investigation: $INV_ID
Verdict: $(curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq -r '.compliance_verdict')
Risk: $(curl -s -X GET $API_URL/api/v1/investigations/$INV_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" | jq -r '.regulatory_risk')
Timestamp: $(date)
EOF
```

---

## 9. Error Testing

**Test missing required field:**

```bash
curl -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{
    "date_from": "2026-01-01",
    "date_to": "2026-12-31"
  }' | jq
```

**Expected error:**
```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Test invalid API key:**

```bash
curl -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: wrong-key" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{"query": "test", "date_from": "2026-01-01", "date_to": "2026-12-31"}' | jq
```

**Expected:**
```json
{"detail": "Unauthorized"}
```

---

## 10. Performance Testing

**Measure response time:**

```bash
# Create and execute, measure time
time curl -X POST $API_URL/api/v1/investigations/$INV_ID/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{}' > /dev/null
```

**Expected:**
- Creation: < 2 seconds
- Execution: < 60 seconds
- Retrieval: < 200ms

---

## 11. Batch Testing (Loop)

**Test multiple applicants:**

```bash
#!/bin/bash

API_URL="http://localhost:8003"
API_KEY="$(echo $SENTINEL_API_KEY)"
TENANT_ID="batch-test"

APPLICANTS=(
  "James Richardson:White:150000:780:false"
  "Maria Santos:Hispanic:55000:620:true"
  "Alicia Johnson:African American:48000:680:true"
  "Robert Chen:Asian:95000:720:false"
  "Patricia Brown:Black:72000:650:true"
)

for APP in "${APPLICANTS[@]}"; do
  IFS=':' read -r NAME RACE INCOME CREDIT DENIED <<< "$APP"
  
  echo "Testing $NAME ($RACE)..."
  
  INV=$(curl -s -X POST $API_URL/api/v1/investigations \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -d "{
      \"query\": \"Test for $NAME\",
      \"date_from\": \"2026-01-01\",
      \"date_to\": \"2026-12-31\",
      \"applicant_data\": {
        \"applicant_id\": \"BATCH_$(date +%s)\",
        \"applicant_name\": \"$NAME\",
        \"race\": \"$RACE\",
        \"income\": $INCOME,
        \"credit_score\": $CREDIT,
        \"denied\": $DENIED
      }
    }" | jq -r '.investigation_id')
  
  echo "  ID: $INV"
  
  VERDICT=$(curl -s -X POST $API_URL/api/v1/investigations/$INV/execute-sync \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -d '{}' | jq -r '.compliance_verdict')
  
  echo "  Verdict: $VERDICT"
  echo ""
done
```

---

## Tips & Tricks

### Pretty Print JSON

```bash
# All results formatted
curl ... | jq '.'

# Specific field
curl ... | jq '.compliance_verdict'

# Multiple fields
curl ... | jq '{verdict: .compliance_verdict, risk: .regulatory_risk}'
```

### Handle Special Characters

```bash
# Escape quotes in JSON
curl ... -d '{
  "applicant_name": "O'\''Brien",
  ...
}'

# Or use JSON properly
jq -n '{applicant_name: "O'\''Brien"}'
```

### Test with Different Tenants

```bash
# Each tenant isolates tests
curl ... -H "X-Tenant-ID: tenant-1" ...
curl ... -H "X-Tenant-ID: tenant-2" ...
```

### Verbose Debugging

```bash
# Show request details
curl -v -X POST $API_URL/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{...}'

# Show timing information
curl -w "Time: %{time_total}s\n" ...
```

---

## Common Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | Results retrieved successfully |
| 202 | Accepted | Investigation queued for processing |
| 400 | Bad Request | Fix JSON syntax or missing fields |
| 401 | Unauthorized | Check API key in header |
| 404 | Not Found | Investigation ID doesn't exist |
| 422 | Unprocessable | Validation error in fields |
| 500 | Server Error | Check API logs, retry later |

---

## Quick Troubleshooting

**"Connection refused"**
```bash
# Start API server
python -m uvicorn sentinel.api.main:app --port 8003
```

**"Unauthorized"**
```bash
# Verify API key
echo $SENTINEL_API_KEY

# Add to request
-H "X-API-Key: YOUR_ACTUAL_KEY"
```

**"Database connection error"**
```bash
# Verify database
psql $DATABASE_URL -c "SELECT 1"
```

**"Timeout"**
```bash
# Increase timeout
--max-time 3600  # 1 hour
```

---

**Happy Testing! 🚀**
