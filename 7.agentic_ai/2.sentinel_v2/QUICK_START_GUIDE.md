# SENTINEL - Quick Start Guide (After Fixes)

## 🚀 How to Use SENTINEL Now

### Step 1: INVESTIGATE (Single Case)

**Purpose:** Test compliance analysis on one loan application

```
1. Click "Investigate" in sidebar
2. Fill form:
   ✓ Applicant Name: "Marcus Johnson"
   ✓ Age: 45
   ✓ Race: "African American"
   ✓ Income: $45,000
   ✓ Credit Score: 600
   ✓ Denied: YES
   ✓ Domain: Finance
   ✓ Date Range: 2024-01-01 to 2024-12-31
3. Click "Submit Investigation"
4. WAIT 20-30 seconds (progress bar moves)
   - Status: queued
   - Status: discovering (finding related cases)
   - Status: investigating (analyzing evidence)
   - Status: analyzing (checking regulations & bias)
   - Status: reporting (generating report)
5. Status: complete or pending_human
6. See verdict: UNCERTAIN or VIOLATION (denied + minority + low credit)
7. Click "View Results" to see full report
```

**What You Expect:**
- ✓ Slow progress (real agents, not mocks)
- ✓ Varied verdicts based on applicant data
- ✓ Detailed compliance report with regulations
- ✓ Risk assessment and bias analysis

---

### Step 2: BATCH PROCESSING (Multiple Cases)

**Purpose:** Test 50+ cases with filters to find compliance patterns

```
1. Click "Batch Processing" in sidebar
2. Configure filters:
   ✓ Domain: Finance (or Healthcare, Pharma)
   ✓ Outcome Filter: Denied Only (or All, Approved Only)
   ✓ From Date: 2024-01-01
   ✓ To Date: 2024-12-31
   ✓ Max Records: 50
3. Click "Start Batch Processing"
4. WAIT for processing (~1-2 minutes for 50 records)
5. See results:
   - Verdict Distribution:
     COMPLIANT: X  |  UNCERTAIN: Y  |  VIOLATION: Z
   - Risk Distribution:
     LOW: X  |  MEDIUM: Y  |  HIGH: Z
   - Bias Detected: X cases
6. Click "Go to Results page"
```

**What You Expect:**
- ✓ Only records matching filters are processed
- ✓ Verdict breakdown (not all COMPLIANT)
- ✓ Risk distribution varies
- ✓ Bias flags for minority applicants with denials

---

### Step 3: RESULTS (View Completed Investigations)

**Purpose:** Review investigation outcomes with verdicts and reports

```
1. Click "Results" in sidebar
2. See list of recent investigations with:
   - Applicant name
   - Verdict (COMPLIANT / UNCERTAIN / VIOLATION)
   - Risk (LOW / MEDIUM / HIGH)
   - Bias flag (YES / NO)
3. Click an investigation to expand:
   ✓ Applicant details (age, race, income, credit)
   ✓ Compliance verdict
   ✓ Regulatory risk
   ✓ Applicable regulations
   ✓ Full compliance report
   ✓ Link to Provenance graph
```

**What You Expect:**
- ✓ Verdicts match applicant characteristics
- ✓ Denied minorities show UNCERTAIN/VIOLATION
- ✓ Reports include regulatory citations
- ✓ Bias detected for protected classes

---

### Step 4: ESCALATIONS (Human Review Queue)

**Purpose:** Review cases requiring human decision

```
1. Click "Escalations" in sidebar
2. See investigations with status "pending_human":
   - UNCERTAIN verdict cases
   - HIGH risk cases
   - Bias detected cases
3. Click a case to expand:
   ✓ AI draft report
   ✓ Escalation reason
   ✓ Applicant summary
   ✓ Regulations applied
4. Make decision:
   ✓ Approve Draft (accept verdict)
   ✓ Modify Response (override with custom assessment)
   ✓ Close Without Report (dismiss)
5. Add comment & Reviewer ID
6. Click "Submit Decision"
7. Status → complete
8. Case removed from escalations
```

**What You Expect:**
- ✓ Uncertain cases appear here
- ✓ Human can override or approve
- ✓ Audit trail of reviewer decision
- ✓ Comment explains reasoning

---

### Step 5: REGULATIONS (Reference Only)

**Purpose:** View applicable compliance framework

```
1. Click "Regulations" in sidebar
2. See sections:
   - Fair Housing Act
   - ECOA (Equal Credit Opportunity Act)
   - FCRA (Fair Credit Reporting Act)
   - ADA Accessibility
   - Disparate Impact rules
3. Reference while reviewing cases
4. No interaction needed (informational only)
```

**What You Expect:**
- ✓ Complete regulatory framework
- ✓ Specific sections cited in reports
- ✓ Guidance for compliance officers

---

### Step 6: PROVENANCE (Audit Trail)

**Purpose:** Trace WHERE each decision came from

```
1. In Results page, click a case
2. Scroll to bottom → "View Provenance"
3. See decision chain:
   - Investigation started
   - Cases discovered
   - Evidence analyzed
   - Regulations applied
   - Verdict determined
   - Report generated
4. Each node shows:
   - What decision was made
   - Why (evidence)
   - When (timestamp)
   - Source (regulation)
```

**What You Expect:**
- ✓ Full audit trail
- ✓ Regulations cited for verdict
- ✓ Evidence links
- ✓ Tamper detection (hash verification)

---

### Step 7: ANALYTICS (Dashboard)

**Purpose:** View compliance metrics

```
1. Click "Analytics" in sidebar
2. See metrics:
   - Total investigations processed
   - Verdict distribution
   - Risk distribution
   - Bias detection rate
   - HITL escalation rate
   - Most cited regulations
3. Track trends over time
```

**What You Expect:**
- ✓ Compliance dashboard
- ✓ Automated metrics
- ✓ Management reporting

---

## Common Workflows

### Workflow A: "Find Discriminatory Denials"
```
1. Batch Processing
2. Filter: Denied Only, Finance domain
3. View Results
4. Sort by Risk (HIGH first)
5. Check cases with minority applicants
6. If bias flagged → go to Escalations
7. Human reviews for discrimination
```

### Workflow B: "Verify Fair Lending Compliance"
```
1. Investigate: Enter minority applicant, low credit, denied
2. Check: Is verdict UNCERTAIN/VIOLATION?
3. Check: Are regulations cited?
4. Check: Does report mention disparate impact?
5. If all yes → compliant workflow
6. If no → investigate why
```

### Workflow C: "Audit Historical Decisions"
```
1. Batch Processing
2. Filter: Specific date range, domain
3. View Results
4. Click → Provenance
5. Verify decision was documented
6. Verify regulations were checked
7. Verify no discriminatory patterns
```

---

## Expected Behavior Changes

### Before (With Mocks):
❌ Progress bar doesn't move (instant completion)
❌ All verdicts COMPLIANT (unrealistic)
❌ No escalations populated
❌ No detailed results
❌ No verdict breakdown

### After (Real Flow):
✅ Progress bar moves over 20-30 seconds
✅ Varied verdicts (COMPLIANT/UNCERTAIN/VIOLATION)
✅ Escalations show uncertain/risky cases
✅ Detailed results with reports
✅ Verdict breakdown in batch results
✅ Full compliance documentation

---

## Troubleshooting

### Q: Progress bar stuck / investigation hangs?
**A:** Check API is running:
```
curl http://localhost:8003/health
```
Should return `{"status": "alive"}`

### Q: All verdicts still COMPLIANT?
**A:** Check mocks are disabled in `sentinel/core/debug.py`
All functions should return empty dict `{}`

### Q: No escalations appearing?
**A:** Need investigations with UNCERTAIN verdict or HIGH risk
- Try denied minority applicant (see Step 1)
- Status should be `pending_human`
- Should appear in Escalations page

### Q: Reports not showing?
**A:** Check Results page loads investigation
- Click any case in Results
- Scroll down for full report
- Report shows verdict, risk, regulations, findings

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     SENTINEL Data Flow                           │
└─────────────────────────────────────────────────────────────────┘

USER INPUT
  ↓
[INVESTIGATE] or [BATCH PROCESSING]
  ↓
  → Submit applicant data (name, age, race, income, credit, denied)
  ↓
API / GRAPH EXECUTION (20-30 seconds)
  ├─ Discovery Agent: Find related cases
  ├─ Investigation Agent: Extract evidence
  ├─ Legal Agent: Apply regulations
  ├─ Bias Detection Agent: Check discrimination
  ├─ Evidence Assembly: Merge results
  └─ Report Agent: Generate compliance report
  ↓
DATABASE SAVE
  ├─ state_snapshot (verdict, risk, regulations, findings)
  ├─ final_report (full compliance assessment)
  └─ status (complete or pending_human)
  ↓
UI DISPLAY
  ├─ [RESULTS] → Shows verdict & report
  ├─ [ESCALATIONS] → Shows if pending_human
  ├─ [PROVENANCE] → Shows decision chain
  └─ [ANALYTICS] → Shows aggregated metrics
  ↓
HUMAN REVIEW (if needed)
  → [ESCALATIONS] → Approve/Modify/Close
  ↓
COMPLETE ✓

```

---

## Success Criteria

After fixes, you should see:

✅ Investigation takes 20-30 seconds (not instant)
✅ Progress bar moves visibly
✅ Verdict varies by applicant (UNCERTAIN for denied minorities)
✅ Batch shows verdict breakdown (not all COMPLIANT)
✅ Escalations populated (uncertain/risky cases)
✅ Reports detailed (regulations cited, findings explained)
✅ Provenance traceable (decision chain documented)

**If ALL of above work → System is FIXED and READY** ✓

