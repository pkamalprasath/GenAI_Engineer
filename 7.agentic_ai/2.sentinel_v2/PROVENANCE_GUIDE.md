# PROVENANCE GRAPH - Detailed Information Guide

## Issue: "Only few nodes visible, missing other factors"

### Current Limitation
- Graph shows ~5-10 key decision nodes
- Other related information exists but not in visual graph
- Missing applicant details, regulations, verdict reasoning

### Solution: Access Hidden Information

Even though the graph shows few nodes, ALL information is available. Here's how to access it:

---

## WHERE TO FIND COMPLETE INFORMATION

### 1️⃣ APPLICANT INFORMATION
**Location:** Results Page (same investigation)

```
Results Page shows:
  ├─ Name: Marcus Johnson
  ├─ Age: 45
  ├─ Race: African American
  ├─ Gender: Male
  ├─ Income: $45,000
  ├─ Credit Score: 600
  ├─ Denied: YES
  └─ Denial Reason: Low credit score
```

### 2️⃣ DISCOVERY PHASE RESULTS
**Location:** Results Page → Compliance Analysis Results section

```
Shows:
  ├─ Case Count: X related cases found
  ├─ Discovery Confidence: Y%
  └─ Related Case IDs: [CASE-001, CASE-002, ...]
```

### 3️⃣ INVESTIGATION RESULTS
**Location:** Results Page → Full Report section

```
Shows:
  ├─ Evidence Items Found: N
  ├─ Decision Chains Analyzed: M
  ├─ Evidence Details:
  │  ├─ ID: EV-CASE-0010-001
  │  ├─ Description: "Applicant denied due to..."
  │  ├─ Source: decision_record
  │  └─ Trust Score: 0.9
  └─ Case Details: [Full decision chain breakdown]
```

### 4️⃣ LEGAL ANALYSIS
**Location:** Results Page → Compliance Analysis Results

```
Shows:
  ├─ Compliance Verdict: UNCERTAIN
  ├─ Regulatory Risk: MEDIUM
  ├─ Applicable Regulations:
  │  ├─ Fair Housing Act
  │  ├─ FCRA (Fair Credit Reporting Act)
  │  ├─ ECOA (Equal Credit Opportunity Act)
  │  └─ Disparate Impact Analysis Required
  └─ Legal Citations: [Specific regulation sections]
```

### 5️⃣ BIAS DETECTION RESULTS
**Location:** Results Page → Compliance Analysis Results OR full report

```
Shows:
  ├─ Bias Detected: YES/NO
  ├─ Bias Confidence: X%
  ├─ Dimensions Checked:
  │  ├─ race_credit_interaction
  │  ├─ gender (if applicable)
  │  ├─ age (if applicable)
  │  └─ family_status (if applicable)
  └─ Statistical Findings:
     ├─ Finding: "Applicant identified as African American with credit score 600..."
     ├─ Confidence: 0.75
     └─ Dimension: race_credit_interaction
```

### 6️⃣ FINAL VERDICT & REASONING
**Location:** Results Page → Compliance Analysis Results + Full Report

```
Shows:
  ├─ Final Verdict: UNCERTAIN / COMPLIANT / VIOLATION
  ├─ Why (Regulations cited):
  │  ├─ "Fair Housing Act - Disparate impact suspected"
  │  ├─ "ECOA - Applied equally but needs verification"
  │  └─ "FCRA - Credit score within fair range"
  └─ Recommendation:
     ├─ ESCALATE (if VIOLATION)
     ├─ REVIEW (if UNCERTAIN)
     └─ APPROVE (if COMPLIANT)
```

---

## HOW TO ACCESS ALL INFORMATION

### Step-by-Step Guide:

**Step 1: Go to Results Page**
```
Sidebar → Results
```

**Step 2: Find the Investigation**
```
Scroll through list OR
Search by Investigation ID OR
Click "View Results" button after batch completes
```

**Step 3: Click Investigation to Expand**
```
Click on: "INV-ABC123 | Marcus Johnson | UNCERTAIN"
```

**Step 4: Review Applicant Information**
```
See section: "Applicant Information"
Shows: Name, Age, Race, Income, Credit Score, Denied status
```

**Step 5: Review Compliance Analysis**
```
See section: "Compliance Analysis Results"
Shows: Verdict, Risk, Regulations, Bias flag
```

**Step 6: Review Full Compliance Report**
```
See section: "Compliance Report"
Shows: Full text report with:
  - Executive Summary
  - Findings
  - Regulatory Analysis
  - Risk Assessment
  - Recommendations
```

**Step 7: Review Provenance (Optional)**
```
At bottom: "View Provenance Graph"
Shows: Decision chain visualization
```

---

## WHAT INFORMATION IS PRESERVED

Even though the graph visualization is limited, the SYSTEM preserves ALL information:

```
✓ Applicant demographics (race, age, gender, family status)
✓ Loan decision factors (income, credit, denied reason)
✓ Related cases discovered (case IDs, decision chains)
✓ Evidence items analyzed (source, description, trust score)
✓ Regulations applied (specific sections cited)
✓ Verdict logic (why COMPLIANT/UNCERTAIN/VIOLATION)
✓ Bias analysis (dimensions checked, findings)
✓ Risk assessment (LOW/MEDIUM/HIGH reasoning)
✓ Timestamps (when each phase completed)
✓ Hash verification (tamper detection)
```

All of this is stored in the database and accessible:
- Via Results page (UI)
- Via Provenance graph (visual)
- Via API endpoints (programmatic)

---

## WHAT THE PROVENANCE GRAPH CURRENTLY SHOWS

**Node Types Visible:**
```
Decision Node
  ├─ Investigation Start
  ├─ Discovery Complete
  ├─ Investigation Complete
  ├─ Legal Analysis Complete
  ├─ Bias Analysis Complete
  └─ Report Complete

Evidence Node
  ├─ Evidence Item 1
  ├─ Evidence Item 2
  └─ Evidence Item N

Connection Node
  ├─ Case → Evidence link
  ├─ Evidence → Verdict link
  └─ Verdict → Report link
```

---

## FUTURE ENHANCEMENT: EXPANDED GRAPH

To see MORE nodes in provenance graph, we would need to:

```
1. Use advanced visualization library
   (e.g., Cytoscape.js, D3.js, Vis.js)

2. Add drill-down capability
   - Click phase → Expand to show sub-nodes
   - Click node → Show details panel

3. Add color-coding
   - Red = violation found
   - Yellow = uncertain
   - Green = compliant

4. Add timeline
   - Horizontal axis = time
   - Vertical axis = decision depth
   - Show execution order

5. Add layer toggles
   - Show/hide applicant info
   - Show/hide evidence items
   - Show/hide regulations
   - Show/hide bias factors
```

This is in backlog but not blocking current functionality.

---

## RECOMMENDATION FOR COMPLIANCE AUDITING

To get COMPLETE provenance audit trail:

```
1. Go to Results page
2. Open investigation
3. DON'T just look at graph
4. READ full report (contains all information)
5. Use Provenance graph for visual confirmation
6. Check regulations cited match what you expect
7. Verify verdict matches applicant data
8. If uncertain, go to Escalations for human review
```

This gives you:
- ✓ Complete applicant information
- ✓ Complete investigation findings
- ✓ Complete regulatory analysis
- ✓ Complete bias detection
- ✓ Complete audit trail
- ✓ Complete verdict reasoning

---

## EXAMPLE: Finding Provenance for "Marcus Johnson"

**Scenario:** You want to verify why Marcus Johnson (denied, African American, credit 600) got verdict UNCERTAIN

**Steps:**

1. Go to Results page
2. Find "INV-ABC123 | Marcus Johnson | UNCERTAIN"
3. Click to expand
4. See applicant info:
   ```
   Race: African American
   Denied: YES
   Credit Score: 600
   ```
5. See verdict: UNCERTAIN
6. See risk: MEDIUM
7. Scroll to regulations:
   ```
   Applicable Regulations:
   - Fair Housing Act
   - FCRA
   - ECOA
   - Disparate Impact Analysis Required
   ```
8. Scroll to report:
   ```
   "Applicant identified as African American with credit score 600 
    (below 650 threshold) was denied. Disparate impact analysis 
    required per Fair Lending standards. Verdict: UNCERTAIN pending 
    human review."
   ```
9. Click "View Provenance Graph" to see decision chain visually

**Result:** Complete audit trail showing:
- ✓ What factors were considered
- ✓ What regulations applied
- ✓ What verdict was reached
- ✓ Why (reasoning documented)

---

## SUMMARY

**Issue:** Provenance graph shows "only few nodes"

**Reality:** All information IS preserved and accessible

**Current Access:** Via Results page (full details) + Provenance graph (visual summary)

**How to Access All Info:**
1. Results page → Click investigation
2. See all applicant details
3. See all regulations applied
4. See full compliance report
5. See provenance graph for visual confirmation

**Future Enhancement:** More visual nodes in graph (not blocking now)

✓ **COMPLETE AUDIT TRAIL IS AVAILABLE** - Just access it from Results page!

