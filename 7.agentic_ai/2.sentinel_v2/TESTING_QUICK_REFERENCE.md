# SENTINEL — Testing Quick Reference Card

## How to Validate All 5 Fixes

### Setup
```bash
cd d:\AI\KrishNaik_Academy\Coding\Vizuara\rag\projects\sentinel_v2

# Start API
python -m uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8003 --reload

# In another terminal: Start Dashboard
streamlit run sentinel/dashboard/app.py
```

Access: http://localhost:8501

---

## TEST 1: Real Flow (Progress Bar)
⏱️ **Duration:** 30-40 seconds

**Steps:**
1. Click **Investigate** in sidebar
2. Fill form:
   - Name: Marcus Johnson
   - Age: 45
   - Race: African American
   - Income: $45,000
   - Credit Score: 600
   - Denied: YES
3. Click **Submit Investigation**
4. WATCH progress bar move over 20-30 seconds
5. See status change: queued → discovering → investigating → analyzing → complete

**Verification:**
- ✓ Progress bar moves visibly (not instant)
- ✓ Takes ~20-30 seconds (real agents)
- ✓ Status shows phase progression
- ✓ Final status: **complete** or **pending_human**
- ✓ Verdict: **UNCERTAIN** or **VIOLATION** (NOT COMPLIANT)

---

## TEST 2: Batch with Filters
⏱️ **Duration:** 2-3 minutes for 20 records

**Steps:**
1. Click **Batch Processing** in sidebar
2. Configure:
   - Domain: **Finance**
   - Outcome Filter: **Denied Only**
   - From Date: **2024-01-01**
   - To Date: **2024-12-31**
   - Max Records: **20**
3. Click **Start Batch Processing**
4. WAIT for processing
5. See results display

**Verification:**
- ✓ Only denied applications processed (not all)
- ✓ Only Finance domain (not other domains)
- ✓ Date range respected
- ✓ Shows three metric tables:
  - Investigations Created/Completed/Failed
  - Verdict Distribution (COMPLIANT | UNCERTAIN | VIOLATION with %)
  - Risk Distribution (LOW | MEDIUM | HIGH with %)
  - Bias Flagged count > 0
- ✓ Button: "Go to Results page"

**Expected Results:**
- Verdict Distribution: NOT all same verdict
- Risk Distribution: Mixed LOW/MEDIUM/HIGH
- Bias Flagged: Some cases flagged (minority applicants with denials)

---

## TEST 3: Results Page Detail
⏱️ **Duration:** 1-2 minutes

**Steps:**
1. From batch results, click **"Go to Results page"**
2. See list of investigations
3. Click one investigation to expand
4. Scroll down to see all sections

**Verification - Should see:**
- ✓ Applicant Information (name, age, race, income, credit, denied status)
- ✓ Compliance Verdict (COMPLIANT, UNCERTAIN, or VIOLATION)
- ✓ Regulatory Risk (LOW, MEDIUM, HIGH)
- ✓ Applicable Regulations (Fair Housing Act, ECOA, FCRA)
- ✓ Full Compliance Report (detailed text with reasoning)
- ✓ Link: **"View Provenance Graph"**

---

## TEST 4: Provenance Complete Information
⏱️ **Duration:** 1 minute

**Steps:**
1. From Results page, click **"View Provenance Graph"**
2. Scroll down through all sections

**Verification - Should see these sections in order:**
- ✓ Graph Visualization (interactive, 5-10 nodes)
- ✓ Decision Chain Summary
  - Agent/Phase name
  - Timestamp
  - Status
  - Verdict & Risk
- ✓ Evidence Items
  - Evidence ID
  - Description
  - Source
  - Trust Score (progress bar)
- ✓ Source Documentation
  - Related Cases (case IDs)
  - Applicable Regulations (list)
  - Source Documents (links)
- ✓ Tamper Detection & Hash Verification
  - SHA-256 hashes
  - "Audit trail preserved"
- ✓ Investigation Report (full text)
- ✓ Detailed Node Information (expandable)

**Expected Details:**
- Decision Chain shows phases: discovery, investigation, legal analysis, complete
- Evidence Items include: Race, Credit Score, Denied status
- Regulations include: Fair Housing Act, ECOA, FCRA
- Hash section shows at least 3 hashes
- Report explains WHY verdict was reached

---

## TEST 5: Escalations Queue
⏱️ **Duration:** 1 minute

**Steps:**
1. Click **Escalations** in sidebar
2. Look for investigations with status **pending_human**
3. Click one to expand

**Verification:**
- ✓ See at least one investigation
- ✓ Contains cases with: UNCERTAIN verdict OR HIGH risk OR bias detected
- ✓ Shows: Applicant summary, regulations, draft report
- ✓ Form: "Your Decision" with Approve/Modify/Close buttons
- ✓ Can enter comment & reviewer ID
- ✓ After submit: Status → complete, case removed

---

## TEST 6: Verdict Variation
⏱️ **Duration:** 2-3 minutes per test

**Create 3 investigations and check verdicts:**

### Test 6A: Approved, Good Credit
```
Name: John Smith
Age: 45
Race: White
Income: $150,000
Credit: 750
Denied: NO (Approved)
```
**Expected Verdict:** ✓ COMPLIANT

### Test 6B: Denied, Low Credit, Minority
```
Name: Maria Rodriguez
Age: 35
Race: Hispanic
Income: $50,000
Credit: 600
Denied: YES
```
**Expected Verdict:** ✓ UNCERTAIN or VIOLATION

### Test 6C: Approved, Low Credit, Minority
```
Name: Ahmed Hassan
Age: 40
Race: Asian
Income: $60,000
Credit: 580
Denied: NO (Approved)
```
**Expected Verdict:** ✓ COMPLIANT (approved status overrides)

**Verification:**
- ✓ All three verdicts are DIFFERENT
- ✓ Verdicts match expectations above
- ✓ NOT all same (proves real logic, not mock)

---

## Quick Check: Yes/No Questions

### Issue #1: Mock Data Cleared
- [ ] Progress bar moves 20-30 seconds? (TEST 1)
- [ ] NOT instant completion?

### Issue #2: Batch Filtering Works
- [ ] Batch respects domain filter? (TEST 2)
- [ ] Batch respects outcome filter?
- [ ] Batch respects date range?
- [ ] Batch shows verdict breakdown (not all same)?

### Issue #3: Provenance Complete
- [ ] See Decision Chain Summary? (TEST 4)
- [ ] See Evidence Items with trust scores?
- [ ] See Source Documentation?
- [ ] See Hash Verification?

### Issue #4: Batch Results Display
- [ ] See Verdict Distribution after batch? (TEST 2)
- [ ] See Risk Distribution?
- [ ] See Bias Detection count?

### Issue #5: Integration
- [ ] Investigate shows verdict matches expectations? (TEST 6)
- [ ] Batch shows varied verdicts?
- [ ] Provenance shows complete information?
- [ ] Escalations has pending cases?

---

## If Tests Fail

### Progress bar doesn't move (stuck)
```
Check: Is API running?
curl http://localhost:8003/health
Should return: {"status": "alive"}

If not running:
python -m uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8003
```

### All verdicts still COMPLIANT (mock not disabled)
```
Check: sentinel/core/debug.py line 154-162
Should see: return {} (empty dict)

If mocks enabled, you'll see: return {"verdict": "COMPLIANT", ...}
If that's the case, mocks are still running.
```

### Batch shows no results
```
Check: Is database populated?
Are there decision_records?

If batch shows "No decision records found":
Need to seed database with data first
```

### Provenance shows no data
```
Check: Did investigation complete?
Status should be: "complete" or "pending_human"
(Not "queued", "discovering", "investigating", "analyzing")

If still in progress:
Wait for completion
Then view Provenance
```

---

## Reference: What Each Section Shows

| Section | Shows | Example |
|---|---|---|
| **Decision Chain Summary** | Who decided when and what | "Investigation Agent @ 14:30 → UNCERTAIN\|MEDIUM" |
| **Evidence Items** | Facts considered | "Race: African American (0.72 confidence)" |
| **Source Documentation** | Regulations applied | "Fair Housing Act, ECOA, FCRA" |
| **Tamper Detection** | Hash verification | "f4a7e2b9c..." |
| **Investigation Report** | Full text reasoning | "Disparate impact analysis required..." |

---

## Success Checklist

After running all 6 tests, you should have:

- [ ] All 6 tests completed
- [ ] All verifications passed
- [ ] Documented any issues
- [ ] Verdicts vary (not all same)
- [ ] Provenance shows complete information
- [ ] Batch results show breakdown
- [ ] Escalations queue populated

**If ALL checked → System is READY ✓**

---

## Documentation to Review

1. **QUICK_START_GUIDE.md** — Full workflows
2. **PROVENANCE_ENHANCEMENTS.md** — Detailed provenance explanation
3. **FINAL_STATUS_ALL_5_ISSUES.md** — Complete status summary
4. **ALL_FIXES_SUMMARY.txt** — Implementation details
