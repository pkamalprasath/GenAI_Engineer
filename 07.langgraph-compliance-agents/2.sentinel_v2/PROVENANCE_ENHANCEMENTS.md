# SENTINEL — Provenance Graph Enhancements

## What Was Enhanced

The Provenance page now displays **complete decision chain information** that was previously only available in text reports.

---

## New Information Panels

### 1️⃣ Decision Chain Summary
**What it shows:** WHO made decisions, WHEN, and WHAT status

```
Agent/Phase    Timestamp           Status              Decision
──────────────────────────────────────────────────────────────
Investigation  2026-04-25 14:30    discovering         UNCERTAIN | MEDIUM
Agent          

Investigation  2026-04-25 14:35    investigating       UNCERTAIN | MEDIUM
Complete

Discovery      2026-04-25 14:32    case_found          Data ready
Complete
```

**Why it matters:**
- Shows execution timeline
- Reveals which phase identified issues
- Documents decision path (queued → discovering → investigating → analyzing → complete)
- Displays verdict at each decision point

---

### 2️⃣ Evidence Items
**What it shows:** FACTS CONSIDERED in the decision

```
Evidence ID: EV-CASE-0042-001
Description: "Applicant denied due to low credit score (600 < 650 threshold)"
Source: decision_record
Trust Score: [████████░░] 0.85

Evidence ID: EV-CASE-0042-002
Description: "Race: African American"
Source: applicant_metadata
Trust Score: [██████░░░░] 0.72
```

**Why it matters:**
- Shows ALL facts considered, not just the final verdict
- Trust scores indicate confidence in each piece of evidence
- Source tracking prevents bias from unmeasured factors
- Enables audit compliance (what was measured vs guessed)

---

### 3️⃣ Source Documentation
**What it shows:** WHERE information came from

```
Related Cases:
  • CASE-0039
  • CASE-0041
  • CASE-0043

Applicable Regulations:
  • Fair Housing Act
  • ECOA (Equal Credit Opportunity Act)
  • FCRA (Fair Credit Reporting Act)
  • Disparate Impact Analysis Required

Source Documents:
  • Related Cases Index → [link]
  • Regulatory Framework → [link]
```

**Why it matters:**
- Proves decision was based on applicable law
- Links to related cases (for consistency checks)
- Enables legal review
- Documents regulatory compliance framework

---

### 4️⃣ Tamper Detection & Hash Verification
**What it shows:** AUDIT TRAIL — Has anything changed after decision?

```
Hash Verification Status:

Investigation Agent          Decision Activity               Case Record
────────────────────────────────────────────────────────────────────
f4a7e2b9c...                 8d3f1a9b7...                  a2e4c9f3b...
```

Each hash is SHA-256 of node content. If ANY detail changes:
- Hash changes → Tamper detected
- Audit trail proves integrity
- Compliance officers can verify nothing was altered

**Why it matters:**
- Legal evidence: proves decisions weren't fabricated later
- Audit compliance: SEC/DOJ can verify authenticity
- Dispute resolution: applicant can verify their data
- Fraud prevention: detects unauthorized changes

---

## How the New Sections Work

### Flow:
1. **Graph Visualization** (top) — Visual decision flow
2. **Decision Chain Summary** — Timeline of who decided what
3. **Evidence Items** — What facts were considered
4. **Source Documentation** — What regulations/cases applied
5. **Tamper Detection** — Proof nothing changed after decision
6. **Investigation Report** — Full text summary
7. **Detailed Node Information** — Raw data for each node (expanders)

---

## Data Sources

All information comes from the **state_snapshot** in the database, which SENTINEL preserves during investigation:

```
Database (PostgreSQL)
├── investigations.state_snapshot
│   ├── "compliance_verdict": "UNCERTAIN"
│   ├── "regulatory_risk": "MEDIUM"
│   ├── "evidence_items": [...]
│   ├── "applicable_regulations": [...]
│   ├── "content_hash": "abc123..."
│   └── ...
└── provenance_nodes
    ├── agent nodes
    ├── activity nodes
    ├── decision nodes
    └── evidence nodes
```

The Provenance page extracts and displays this data in readable formats.

---

## Complete Audit Trail Example

**Scenario:** Auditor wants to verify Marcus Johnson's case

### Step-by-Step:

1. **Access Results page** → Find investigation
2. **Click "View Provenance Graph"** → Opens Provenance page
3. **See Decision Chain Summary** → "Who decided when"
   - Investigation Agent @ 2026-04-25 14:30 (queued)
   - Discovery Phase @ 2026-04-25 14:32 (discovering)
   - Investigation Phase @ 2026-04-25 14:35 (investigating)
   - Legal Analysis @ 2026-04-25 14:38 (analyzing)
   - Final Verdict @ 2026-04-25 14:40 (complete) → UNCERTAIN | MEDIUM
4. **See Evidence Items** → "What was considered"
   - Race: African American (confidence 0.72)
   - Credit Score: 600 (confidence 0.85)
   - Denied: YES (confidence 0.95)
   - Disparate impact suspected (confidence 0.68)
5. **See Source Documentation** → "What rules applied"
   - Fair Housing Act (requires disparate impact review)
   - ECOA (equal credit opportunity)
   - FCRA (fair credit reporting)
6. **See Hash Verification** → "Did anything change"
   - Investigation Agent hash: f4a7e2b9c...
   - Legal Analysis hash: 8d3f1a9b7...
   - Decision hash: a2e4c9f3b...
   - (All hashes verify — nothing changed after decision)
7. **See Report** → Full text explanation
   "Applicant identified as African American with credit score 600 (below 650 threshold) was denied. Disparate impact analysis required per Fair Lending standards. Verdict: UNCERTAIN pending human review."

### Result:
✅ Complete audit trail showing:
- Who made decisions (agents, humans)
- When decisions were made (timeline)
- What facts were considered (evidence)
- What rules applied (regulations)
- Why verdict was reached (reasoning in report)
- Proof nothing changed (hash verification)

---

## Compliance Benefits

| Requirement | How Provenance Satisfies It |
|---|---|
| **Fair Housing Act** | Evidence items show demographic factors considered; regulations cited |
| **ECOA** | Decision Chain shows equal treatment process for all applicants |
| **FCRA** | Evidence sources tracked; credit score factors documented |
| **SEC Audit** | Hash verification proves authenticity; timeline proves real-time analysis |
| **DOJ Review** | Complete chain shows no bias patterns; disparate impact analysis documented |
| **Applicant Appeal** | Provenance shows exact reason for denial with supporting evidence |

---

## Visual Improvements

- **Decision Chain:** Color-coded by phase status
- **Evidence Items:** Trust score progress bars (visual confidence)
- **Regulations:** Clear list format (easy for legal review)
- **Hash Verification:** Displayed in monospace (copy/paste for verification)

---

## Summary

Before: Provenance showed ~5-10 nodes with limited context
After: Provenance shows COMPLETE decision chain with:

✅ Decision Chain Summary (who, when, why)
✅ Evidence Items (facts considered, sources, confidence)
✅ Source Documentation (regulations, related cases)
✅ Tamper Detection (hash verification for audit compliance)
✅ Full Investigation Report (detailed reasoning)
✅ Detailed Node Information (raw data for experts)

**All information is now visible in the Provenance graph page — no need to access Results page separately!**
