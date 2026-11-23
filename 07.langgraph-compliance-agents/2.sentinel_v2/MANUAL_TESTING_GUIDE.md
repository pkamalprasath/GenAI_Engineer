# SENTINEL v2 — Manual Testing Guide

## Overview

Manual testing allows you to interact with SENTINEL v2 directly through the API and Dashboard to verify functionalities, data flow, and user experience.

## Prerequisites

### 1. Services Running

Start these in separate terminals:

**Terminal 1: PostgreSQL/Supabase**
```bash
# Verify your DATABASE_URL is set in .env
# Test connection:
psql $DATABASE_URL -c "SELECT 1"
```

**Terminal 2: API Server**
```bash
cd sentinel_v2
python -m uvicorn sentinel.api.main:app --port 8003 --reload
# Should see: "Application startup complete"
```

**Terminal 3: Streamlit Dashboard**
```bash
cd sentinel_v2
streamlit run sentinel/dashboard/app.py --server.port 8501
# Should see: "You can now view your Streamlit app..."
```

### 2. Access Points

- **API:** `http://localhost:8003`
- **Dashboard:** `http://localhost:8501`
- **API Docs:** `http://localhost:8003/docs`
- **Health Check:** `http://localhost:8003/health`

---

## Manual Testing Methods

### Method 1: Using Streamlit Dashboard (User-Friendly)

Best for visual verification and user experience testing.

**Advantages:**
- ✅ Visual interface (easier to use)
- ✅ See real-time results
- ✅ Screenshot-friendly
- ✅ Form validation visible

**Steps:**
1. Open `http://localhost:8501`
2. Navigate to "Investigate" page
3. Fill in investigation form
4. Click "Start Investigation"
5. Wait for results
6. Review compliance verdict, risk level, report

### Method 2: Using REST API (Programmatic)

Best for automation and testing edge cases.

**Advantages:**
- ✅ Full control over request/response
- ✅ Easy to test edge cases
- ✅ Can use cURL, Postman, or Python
- ✅ Verify JSON responses

**Tools:**
- **cURL** — Command line (included on all systems)
- **Postman** — GUI application (free)
- **Python requests** — Programmatic testing
- **Thunder Client** — VS Code extension

### Method 3: Using Test Scripts (Batch Testing)

Best for testing multiple scenarios rapidly.

---

## Sample Test Data

### Scenario 1: Approved Applicant (No Compliance Issues)

**Profile:**
```json
{
  "applicant_id": "MANUAL_001",
  "applicant_name": "James Richardson",
  "age": 50,
  "race": "White",
  "gender": "Male",
  "income": 150000,
  "credit_score": 780,
  "employment_years": 15,
  "loan_amount": 450000,
  "loan_purpose": "Home Purchase",
  "denied": false
}
```

**Expected Results:**
- ✅ Case Count: 1
- ✅ Compliance Verdict: **COMPLIANT**
- ✅ Regulatory Risk: **LOW**
- ✅ Bias Detected: **False**
- ✅ Report: Generated (400+ characters)

**Test Focus:**
- Verify approved applicant flow
- Confirm compliant verdict
- Validate low-risk assessment

---

### Scenario 2: Denied Applicant (Potential Disparate Impact)

**Profile:**
```json
{
  "applicant_id": "MANUAL_002",
  "applicant_name": "Maria Santos",
  "age": 32,
  "race": "Hispanic",
  "gender": "Female",
  "income": 55000,
  "credit_score": 620,
  "employment_years": 3,
  "loan_amount": 250000,
  "loan_purpose": "Home Purchase",
  "denied": true,
  "denial_reason": "credit_score_too_low"
}
```

**Expected Results:**
- ✅ Case Count: 1
- ✅ Compliance Verdict: **UNCERTAIN** (requires manual review)
- ✅ Regulatory Risk: **MEDIUM** (potential disparate impact)
- ✅ Bias Detected: **False** (single applicant, need pattern)
- ✅ Report: Generated with denial analysis

**Test Focus:**
- Verify denied applicant handling
- Check disparate impact detection
- Confirm medium risk assessment

---

### Scenario 3: Multiple Denials by Race Pattern

**Profile Set A (Approved):**
```json
{
  "applicant_id": "MANUAL_003A",
  "applicant_name": "David Miller",
  "race": "White",
  "credit_score": 700,
  "income": 100000,
  "denied": false
}
```

**Profile Set B (Denied):**
```json
{
  "applicant_id": "MANUAL_003B",
  "applicant_name": "Alicia Johnson",
  "race": "African American",
  "credit_score": 710,  // HIGHER than approved applicant!
  "income": 105000,     // HIGHER than approved applicant!
  "denied": true,
  "denial_reason": "insufficient_documentation"
}
```

**Expected Results:**
- ❌ Violation Pattern Detected (same credit/income but different race)
- ✅ Compliance Verdict: **UNCERTAIN/VIOLATION**
- ✅ Regulatory Risk: **HIGH**
- ✅ Report: Detailed disparate treatment analysis

**Test Focus:**
- Verify disparate impact detection
- Check pattern recognition across applications
- Validate high-risk assessment

---

### Scenario 4: ADA Disability Accommodation

**Profile (With Accommodation):**
```json
{
  "applicant_id": "MANUAL_004",
  "applicant_name": "Robert Chen",
  "age": 45,
  "disability_status": "Yes - Mobility Impairment",
  "accommodation_requested": "Accessible Unit Required",
  "accommodation_provided": true,
  "income": 95000,
  "credit_score": 720,
  "denied": false
}
```

**Expected Results:**
- ✅ Compliance Verdict: **COMPLIANT**
- ✅ Regulatory Risk: **LOW**
- ✅ Accommodation Status: **Approved**
- ✅ Report: FHA compliance analysis

**Test Focus:**
- Verify disability accommodation handling
- Check FHA compliance
- Confirm accessibility requirements

---

### Scenario 5: Gender-Based Pricing Discrimination

**Profile:**
```json
{
  "applicant_id": "MANUAL_005",
  "applicant_name": "Angela Mitchell",
  "gender": "Female",
  "age": 35,
  "income": 105000,
  "credit_score": 760,
  "loan_approved": true,
  "loan_approved_rate": 6.5,
  "comparable_male_rate": 5.8,
  "rate_difference": 0.7
}
```

**Expected Results:**
- ⚠️ Compliance Verdict: **UNCERTAIN**
- ✅ Regulatory Risk: **MEDIUM** (gender-based pricing)
- ✅ Report: ECOA violation analysis

**Test Focus:**
- Verify gender discrimination detection
- Check pricing disparity analysis
- Validate ECOA enforcement

---

### Scenario 6: Joint Application (Couple)

**Profile:**
```json
{
  "applicant_id": "MANUAL_006",
  "applicant_names": "David & Patricia Martinez",
  "applicant_type": "Joint",
  "primary_applicant_income": 105000,
  "co_applicant_income": 80000,
  "joint_income": 185000,
  "primary_credit_score": 750,
  "co_applicant_credit_score": 700,
  "loan_amount": 500000,
  "loan_purpose": "Home Purchase",
  "denied": false
}
```

**Expected Results:**
- ✅ Compliance Verdict: **COMPLIANT**
- ✅ Regulatory Risk: **LOW**
- ✅ Joint Application: **Properly Analyzed**
- ✅ Report: Joint application compliance analysis

**Test Focus:**
- Verify joint application handling
- Check combined income evaluation
- Confirm ECOA compliance for couples

---

### Scenario 7: Senior Applicant (Age Discrimination Test)

**Profile:**
```json
{
  "applicant_id": "MANUAL_007",
  "applicant_name": "Margaret Thompson",
  "age": 75,
  "race": "White",
  "income": 85000,
  "credit_score": 740,
  "employment_type": "Retired",
  "retirement_income": "Stable Pension",
  "denied": true,
  "denial_reason": "age_too_advanced"
}
```

**Expected Results:**
- ❌ Age Discrimination Detected (ADEA violation)
- ✅ Compliance Verdict: **VIOLATION**
- ✅ Regulatory Risk: **HIGH**
- ✅ Report: ADEA violation analysis

**Test Focus:**
- Verify age discrimination detection
- Check ADEA enforcement
- Validate high-risk assessment

---

### Scenario 8: Edge Case - Incomplete Data

**Profile:**
```json
{
  "applicant_id": "MANUAL_008",
  "applicant_name": "Unknown Applicant",
  "age": null,
  "race": "Unknown",
  "income": 0,
  "credit_score": 0,
  "denied": true,
  "denial_reason": null
}
```

**Expected Results:**
- ⚠️ Incomplete Data Alert
- ✅ Compliance Verdict: **UNCERTAIN**
- ✅ Regulatory Risk: **LOW** (insufficient data to determine)
- ✅ Report: Data quality issues noted

**Test Focus:**
- Verify error handling
- Check missing data handling
- Confirm system resilience

---

## Testing Functionalities - Step by Step

### Functionality 1: Create Investigation via API

**Using cURL:**

```bash
curl -X POST http://localhost:8003/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(echo $SENTINEL_API_KEY)" \
  -H "X-Tenant-ID: manual-testing" \
  -d '{
    "query": "Compliance investigation for James Richardson",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "MANUAL_001",
      "applicant_name": "James Richardson",
      "age": 50,
      "race": "White",
      "income": 150000,
      "credit_score": 780,
      "denied": false
    }
  }'
```

**Expected Response:**
```json
{
  "investigation_id": "INV-XXXXXXXXXXXXXXXX",
  "status": "queued",
  "tenant_id": "manual-testing",
  "created_at": "2026-04-25T..."
}
```

**What to Verify:**
- ✅ HTTP Status: 202 (Accepted)
- ✅ Investigation ID generated
- ✅ Status is "queued"
- ✅ Timestamp recorded

---

### Functionality 2: Execute Investigation Synchronously

**Using cURL:**

```bash
curl -X POST http://localhost:8003/api/v1/investigations/INV-XXXXXXXXXXXXXXXX/execute-sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(echo $SENTINEL_API_KEY)" \
  -H "X-Tenant-ID: manual-testing" \
  -d '{}'
```

**Expected Response:**
```json
{
  "investigation_id": "INV-XXXXXXXXXXXXXXXX",
  "status": "complete",
  "compliance_verdict": "COMPLIANT",
  "regulatory_risk": "LOW",
  "bias_detected": false,
  "report_confidence": 0.95,
  "final_report": "Compliance investigation report...",
  "case_count": 1,
  "discovery_confidence": 0.95,
  "evidence_count": 0
}
```

**What to Verify:**
- ✅ HTTP Status: 200 (OK)
- ✅ Status: "complete"
- ✅ Compliance verdict populated
- ✅ Risk level assigned
- ✅ Final report generated (300+ characters)
- ✅ Confidence scores present

**Timing:**
- Should complete in **30-60 seconds**
- If timeout, check API logs

---

### Functionality 3: Retrieve Investigation Results

**Using cURL:**

```bash
curl -X GET http://localhost:8003/api/v1/investigations/INV-XXXXXXXXXXXXXXXX \
  -H "X-API-Key: $(echo $SENTINEL_API_KEY)" \
  -H "X-Tenant-ID: manual-testing"
```

**Expected Response:**
Same as execute-sync response, with stored results.

**What to Verify:**
- ✅ Results match execute-sync output
- ✅ All fields present and consistent
- ✅ Report is readable and coherent

---

### Functionality 4: Test Streamlit Dashboard

**Step-by-Step:**

1. **Open Dashboard**
   - Navigate to `http://localhost:8501`
   - Should see SENTINEL logo and "AI Compliance Platform"

2. **Sidebar Navigation**
   - Click "Investigate" in left sidebar
   - Should navigate to investigation page
   - Check: Navigation works smoothly

3. **Investigation Form**
   - Fill in form fields:
     - Query: "Compliance investigation for James Richardson"
     - Date From: "2026-01-01"
     - Date To: "2026-12-31"
   - Check: Form accepts input

4. **Applicant Data Entry**
   - Look for "Applicant Data" section
   - Enter test data:
     ```
     Applicant ID: MANUAL_001
     Name: James Richardson
     Race: White
     Age: 50
     Income: 150000
     Credit Score: 780
     Denial Status: Not Denied
     ```
   - Check: Fields validate input

5. **Submit Investigation**
   - Click "Start Investigation" button
   - Check: Button is clickable
   - Check: Form doesn't submit if required fields missing

6. **View Results**
   - Wait for results (30-60 seconds)
   - Verify displayed:
     - Investigation ID
     - Compliance Verdict
     - Regulatory Risk Level
     - Bias Detection Result
     - Final Report

7. **Report Review**
   - Read the final report text
   - Verify: Report is relevant and detailed
   - Check: Report references applicant data

---

### Functionality 5: Data Flow Verification

**Test: applicant_data Storage**

```bash
# 1. Create investigation
curl -X POST http://localhost:8003/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(echo $SENTINEL_API_KEY)" \
  -H "X-Tenant-ID: flow-test" \
  -d '{
    "query": "Data flow test",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
      "applicant_id": "FLOW_TEST_001",
      "test_field": "test_value",
      "numeric_value": 12345
    }
  }' | jq -r '.investigation_id'
```

**2. Query Database Directly**
```bash
psql $DATABASE_URL -c "
  SELECT applicant_data 
  FROM investigations 
  WHERE investigation_id = 'INV-XXXXXXXXXXXXXXXX';
"
```

**Expected Output:**
```
{"applicant_id": "FLOW_TEST_001", "test_field": "test_value", "numeric_value": 12345}
```

**What to Verify:**
- ✅ applicant_data stored in database
- ✅ All fields preserved
- ✅ Values unchanged (type conversions OK)
- ✅ No data loss

---

### Functionality 6: Verdict Accuracy Testing

**Test Case: Compliant vs. Violation**

**Scenario A (Should be COMPLIANT):**
```json
{
  "applicant_id": "VERDICT_001",
  "applicant_name": "Approved Applicant",
  "race": "White",
  "income": 150000,
  "credit_score": 780,
  "denied": false,
  "gender": "Male"
}
```

**Scenario B (Should be UNCERTAIN/VIOLATION):**
```json
{
  "applicant_id": "VERDICT_002",
  "applicant_name": "Denied Applicant",
  "race": "African American",
  "income": 55000,
  "credit_score": 680,  // Good credit but still denied
  "denied": true,
  "denial_reason": "insufficient_income",
  "gender": "Female"
}
```

**Expected Verdicts:**
- Scenario A: **COMPLIANT** (approved, no red flags)
- Scenario B: **UNCERTAIN** (potential disparate impact)

**What to Verify:**
- ✅ Verdicts match expectations
- ✅ Logic is consistent
- ✅ Disparate treatment detected

---

### Functionality 7: Report Generation Quality

**Verify Report Content:**

1. **Length:**
   - Minimum: 300 characters
   - Ideal: 400-600 characters
   - Check: `length(final_report) > 300`

2. **Relevance:**
   - Contains applicant demographics
   - References denial/approval reason
   - Mentions regulatory framework
   - Addresses compliance concerns

3. **Coherence:**
   - Report reads naturally
   - No garbled text
   - Proper grammar and spelling
   - Logical flow

**Sample Report Check:**
```
Expected Content:
- ✅ "Applicant: [Name]"
- ✅ "Age: [Age]"
- ✅ "Race/Ethnicity: [Race]"
- ✅ "Credit Score: [Score]"
- ✅ "Income: [Income]"
- ✅ "Status: [Approved/Denied]"
- ✅ "Regulatory Analysis: [Framework]"
- ✅ "Compliance Assessment: [Verdict]"
- ✅ "Risk Level: [Level]"
```

---

### Functionality 8: Error Handling

**Test Missing Required Fields:**

```bash
# Submit with missing query
curl -X POST http://localhost:8003/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(echo $SENTINEL_API_KEY)" \
  -H "X-Tenant-ID: error-test" \
  -d '{
    "date_from": "2026-01-01",
    "date_to": "2026-12-31"
  }'
```

**Expected Response:**
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

**What to Verify:**
- ✅ HTTP Status: 422 (Unprocessable Entity)
- ✅ Error message is clear
- ✅ Missing field identified
- ✅ No data stored on error

---

### Functionality 9: Bias Detection

**Test: Multiple Applicants Same Criteria**

Create 3 investigations:

**Applicant 1 (Approved):**
```json
{"applicant_id": "BIAS_001", "race": "White", "credit": 700, "denied": false}
```

**Applicant 2 (Denied):**
```json
{"applicant_id": "BIAS_002", "race": "African American", "credit": 700, "denied": true}
```

**Applicant 3 (Denied):**
```json
{"applicant_id": "BIAS_003", "race": "African American", "credit": 720, "denied": true}
```

**Expected Results:**
- ✅ Bias pattern detected (African American with equal/higher credit denied)
- ✅ Risk flagged as MEDIUM or HIGH
- ✅ Report mentions potential discrimination

---

### Functionality 10: API Health Check

**Verify API is running:**

```bash
curl http://localhost:8003/health
```

**Expected Response:**
```json
{
  "status": "alive",
  "service": "sentinel-api"
}
```

**What to Verify:**
- ✅ HTTP Status: 200
- ✅ Service status: "alive"
- ✅ Response time < 100ms

---

## Manual Testing Checklist

### Pre-Testing
- [ ] PostgreSQL/Supabase accessible
- [ ] API running on port 8003
- [ ] Dashboard running on port 8501
- [ ] Environment variables set (.env file)
- [ ] API Key configured

### Basic Functionality
- [ ] Create investigation via API
- [ ] Create investigation via Dashboard
- [ ] Execute investigation synchronously
- [ ] Retrieve investigation results
- [ ] View results in Dashboard

### Data Validation
- [ ] applicant_data stored in database
- [ ] All fields preserved correctly
- [ ] Type conversions working
- [ ] No data loss in transmission

### Verdict Accuracy
- [ ] Compliant applicant → COMPLIANT verdict
- [ ] Suspicious applicant → UNCERTAIN verdict
- [ ] Clear violation → VIOLATION verdict
- [ ] Risk levels assigned correctly

### Report Quality
- [ ] Report generated (300+ characters)
- [ ] Report mentions applicant details
- [ ] Report addresses compliance concerns
- [ ] Report is readable and coherent

### UI/Dashboard
- [ ] Pages load correctly
- [ ] Forms accept input
- [ ] Navigation works
- [ ] Results display properly
- [ ] Reports readable in dashboard

### Error Handling
- [ ] Missing required fields caught
- [ ] Invalid data rejected
- [ ] Error messages clear
- [ ] No data stored on error

### Performance
- [ ] Investigation creation < 2 seconds
- [ ] Execution completes in < 60 seconds
- [ ] API responds < 200ms
- [ ] Dashboard loads smoothly

### Bias Detection
- [ ] Disparate patterns detected
- [ ] Risk flagged appropriately
- [ ] Reports mention discrimination concerns
- [ ] Multiple applicant analysis works

---

## Testing Tools & Resources

### Tool 1: cURL (Command Line)

**Advantages:**
- Available on all systems
- No installation needed
- Full control

**Example:**
```bash
curl -X POST http://localhost:8003/api/v1/investigations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Tenant-ID: test" \
  -d '{"query": "test", "date_from": "2026-01-01", "date_to": "2026-12-31"}'
```

### Tool 2: Postman (GUI)

**Advantages:**
- Visual interface
- Save requests
- History tracking
- Collections

**Setup:**
1. Download from `https://www.postman.com/downloads/`
2. Create new request
3. Set URL: `http://localhost:8003/api/v1/investigations`
4. Set Method: `POST`
5. Add Headers and Body
6. Click Send

### Tool 3: Python Script

**Advantages:**
- Reusable
- Easy to modify
- Can save results

**Example:**
```python
import httpx
import json

API_URL = "http://localhost:8003"
API_KEY = "your-api-key"

# Create investigation
response = httpx.post(
    f"{API_URL}/api/v1/investigations",
    json={
        "query": "Manual test investigation",
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "applicant_data": {
            "applicant_id": "TEST_001",
            "applicant_name": "Test User",
            "race": "White",
            "income": 100000,
            "credit_score": 720,
            "denied": False
        }
    },
    headers={
        "X-API-Key": API_KEY,
        "X-Tenant-ID": "manual-test"
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Get investigation ID
inv_id = response.json()["investigation_id"]

# Execute synchronously
exec_response = httpx.post(
    f"{API_URL}/api/v1/investigations/{inv_id}/execute-sync",
    json={},
    headers={
        "X-API-Key": API_KEY,
        "X-Tenant-ID": "manual-test"
    },
    timeout=300.0
)

print(f"Execution Status: {exec_response.status_code}")
result = exec_response.json()
print(f"Verdict: {result.get('compliance_verdict')}")
print(f"Risk: {result.get('regulatory_risk')}")
print(f"Report: {result.get('final_report')[:200]}...")
```

---

## Common Issues & Solutions

### Issue 1: API Connection Refused

**Error:**
```
Connection refused on localhost:8003
```

**Solution:**
```bash
# Check if API is running
curl http://localhost:8003/health

# If not, start it
python -m uvicorn sentinel.api.main:app --port 8003

# Check logs for errors
```

### Issue 2: Invalid API Key

**Error:**
```json
{"detail": "Unauthorized"}
```

**Solution:**
```bash
# Verify API key in .env
echo $SENTINEL_API_KEY

# Update header in request
-H "X-API-Key: YOUR_ACTUAL_API_KEY"
```

### Issue 3: Database Not Accessible

**Error:**
```
Database connection error
```

**Solution:**
```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# If failed, check Supabase credentials
```

### Issue 4: Investigation Timeout

**Error:**
```
Request timeout after 300 seconds
```

**Solution:**
- Check system resources
- Review API logs
- Try simpler investigation first
- Increase timeout in request

### Issue 5: Missing applicant_data in Results

**Error:**
```
applicant_data is null in database
```

**Solution:**
```bash
# Verify data was sent in request JSON
# Ensure headers include Content-Type: application/json
# Check data format matches expected schema
```

---

## Sample Data Sets (CSV Format)

### Fair Lending Test Data

```csv
applicant_id,applicant_name,race,gender,age,income,credit_score,denied,denial_reason
FL_001,John Smith,White,Male,50,150000,780,0,
FL_002,Maria Santos,Hispanic,Female,32,55000,620,1,credit_score_too_low
FL_003,Alicia Johnson,African American,Female,28,48000,680,1,insufficient_income
FL_004,Robert Chen,Asian,Male,45,95000,720,0,
FL_005,Patricia Brown,Black,Female,35,72000,650,1,debt_to_income_ratio
```

### ADA Accessibility Test Data

```csv
applicant_id,applicant_name,disability_status,accommodation_requested,accommodation_provided,income,credit_score,denied
ADA_001,Robert Chen,Mobility Impairment,Accessible Unit Required,1,95000,720,0
ADA_002,Susan Lee,Visual Impairment,Digital Forms,0,72000,650,1
ADA_003,James Wilson,Hearing Impairment,Visual Alerts,1,88000,700,0
ADA_004,Maria Garcia,Mobility Impairment,Wheelchair Access,1,95000,720,0
```

### ECOA Joint Application Data

```csv
applicant_id,primary_name,co_applicant_name,primary_income,co_applicant_income,primary_credit,co_applicant_credit,gender_primary,gender_co,denied
ECOA_001,David Martinez,Patricia Martinez,105000,80000,750,700,Male,Female,0
ECOA_002,Angela Mitchell,Robert Mitchell,105000,80000,760,730,Female,Male,0
ECOA_003,Jennifer Lee,James Lee,95000,85000,740,720,Female,Male,1
```

---

## Expected vs Actual Results Template

### Test Case Template

```
TEST CASE: [Test Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT DATA:
  Applicant ID: [ID]
  Name: [Name]
  Race: [Race]
  Income: [Amount]
  Credit Score: [Score]
  Denial Status: [Status]

EXPECTED OUTPUT:
  ✓ HTTP Status: 200
  ✓ Investigation ID: Generated
  ✓ Compliance Verdict: [Expected]
  ✓ Risk Level: [Expected]
  ✓ Report Generated: Yes

ACTUAL OUTPUT:
  • HTTP Status: [Actual]
  • Investigation ID: [Actual]
  • Compliance Verdict: [Actual]
  • Risk Level: [Actual]
  • Report Generated: [Yes/No]
  • Report Length: [Chars]

VERIFICATION:
  ✓/✗ Verdict matches expected
  ✓/✗ Risk level matches expected
  ✓/✗ Report is coherent
  ✓/✗ Data integrity verified

NOTES:
  [Any observations or issues]
```

---

## Next Steps After Manual Testing

1. **Document Results** — Save screenshots and responses
2. **Identify Issues** — Note any unexpected behaviors
3. **File Reports** — Report bugs if found
4. **Update Verdicts** — If agent verdicts don't match expectations
5. **Scale Testing** — Move to automated tests if confident

---

**Happy Manual Testing! 🧪**

For questions or issues, consult the Troubleshooting Guide above or review the API documentation at `http://localhost:8003/docs`.
