# SENTINEL UI - Implementation Plan
## Fix Issues 2-5: Batch Processing, Provenance, Results Display

### Current State
1. ✓ Mocks disabled - real flow enabled
2. ❌ Batch: No filtering, no detailed results
3. ❌ Provenance: Only few nodes visible  
4. ❌ Batch results: No verdict/reports shown
5. ❌ Overall: Need comprehensive fixes

---

## ISSUE #2: BATCH PROCESSING - Add Filtering & Controls

### Current (Wrong):
```python
# Line 113-118: Get ALL records, no filtering
records = await conn.fetch(f"""
    SELECT id, case_id, outcome, decision_timestamp, metadata
    FROM decision_records
    WHERE metadata IS NOT NULL
    LIMIT $1
""", limit)
```

### Expected (Right):
```python
# Should support:
- Date range (FROM ... TO)
- Domain (finance/pharma/bank)
- Outcome (all/denied/approved)
- Tenant (hardcoded or user-selected)
```

### Fix Implementation:
```
Add to Batch UI:
1. Date Range Picker (from_date, to_date)
2. Domain Dropdown (Finance, Pharma, Healthcare, Banking)
3. Outcome Filter (All, Denied Only, Approved Only)
4. Tenant Selection (hardcoded for now)
5. Build WHERE clause based on selections
```

---

## ISSUE #3: PROVENANCE - Graph Only Shows Few Nodes

### Current (Wrong):
- Only 5-10 nodes visible
- Missing: applicant info, regulations, evidence details
- Graph doesn't expand/zoom
- No drill-down on nodes

### Expected (Right):
```
Provenance Graph Should Show:
├── Investigation Start
│   ├── Applicant Info (name, age, race, credit, income)
│   └── Query Details
├── Discovery Phase
│   └── Related Cases Found
├── Investigation Phase
│   ├── Evidence Items (N items)
│   ├── Decision Chains
│   └── Trust Scores
├── Legal Phase
│   ├── Applicable Regulations
│   ├── Compliance Verdict
│   └── Regulatory Risk
├── Bias Detection Phase
│   ├── Dimensions Checked
│   ├── Findings
│   └── Bias Confidence
└── Report Phase
    └── Final Report
```

### Fix Implementation:
```
Expand provenance visualization:
1. Add node labels for: applicant, discovery, evidence, regulations, verdict
2. Add drill-down: Click node → See details
3. Add legend: Color-code nodes by phase
4. Add timeline: Show execution order
5. Add expandable sections for each phase
```

---

## ISSUE #4: BATCH RESULTS - No Verdict/Report Info

### Current (Wrong):
```
Batch Processing Summary:
- Created: 50
- Executed: 45
- Failed: 5
(No verdict breakdown, no reports shown)
```

### Expected (Right):
```
Batch Processing Results:
- Created: 50
- Executed: 45
- Failed: 5

Verdict Distribution:
- COMPLIANT: 28 (62%)
- UNCERTAIN: 12 (27%)
- VIOLATION: 5 (11%)

Risk Distribution:
- LOW: 30 (67%)
- MEDIUM: 10 (22%)
- HIGH: 5 (11%)

Bias Detection: 8 cases flagged (18%)

Pending Human Review: 12 cases

Individual Results:
[Table showing each case with verdict, risk, status, report link]
```

### Fix Implementation:
```
After batch completes:
1. Query completed investigations
2. Extract: verdict, risk, bias_detected, final_report
3. Build statistics: counts, percentages, distribution
4. Show table with: case_id, verdict, risk, status, [View Report] button
5. Add export: CSV/JSON of results
```

---

## ISSUE #5: Overall Fixes Required

### Files to Modify:
1. `sentinel/dashboard/pages/6_batch.py` - Add filtering, results display
2. `sentinel/dashboard/pages/2_provenance.py` - Expand graph visualization
3. `sentinel/dashboard/pages/0_results.py` - Link from batch results
4. `sentinel/core/debug.py` - Keep mocks disabled

### Key Changes:
```
Batch Page:
- Add date_range, domain, outcome filters to UI
- Update SQL query to use WHERE clause
- After processing, display statistics table
- Add "View Report" links to results page

Provenance Page:
- Fetch full graph data from investigation state
- Expand node visualization with details
- Add drill-down capability
- Add phase-based coloring

Results Page:
- Already works for individual cases
- Will auto-populate from batch processing results
```

---

## Execution Order:
1. ✓ Step 1: Disable mocks (DONE)
2. → Step 2: Fix Batch filtering & controls
3. → Step 3: Fix Batch results display
4. → Step 4: Fix Provenance visualization
5. → Step 5: Integration test

---

## Testing After Fix:
```
1. Go to Batch Processing
2. Set date range, select domain, filter by denied only
3. Click "Start Batch Processing"
4. Watch: Statistics populate (verdict distribution, risk breakdown)
5. Click investigation → Go to Results page
6. Click "View Provenance" → See full graph with all nodes
7. Click case → See detailed report & applicant info
```

