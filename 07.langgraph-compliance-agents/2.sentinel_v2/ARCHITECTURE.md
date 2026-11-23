# SENTINEL Architecture Guide

## System Overview

SENTINEL is a production-grade compliance automation platform built on three core principles:

1. **Autonomous agents** — Specialized LLMs for each compliance dimension
2. **Immutable provenance** — W3C PROV-O + SHA-256 tamper detection
3. **Scalable infrastructure** — Microservices, background queues, vector indexes

---

## The 7-Agent Pipeline

### 1. Discovery Agent (Case Selection)
**Problem:** Finding relevant cases in a database of 10,000+ decisions is expensive with LLMs.

**Solution:** Three-stage hybrid filter
```
BM25 keyword filter        (milliseconds, $0)       → eliminates 95%
DistilBERT semantic rerank (2-4s, CPU-only)        → cosine similarity
llama3.2:3b classification (local, $0)             → resolves borderline

Result: 3 relevant cases for $0.001 (vs. $150 with pure GPT-4o)
```

**Output:** `relevant_case_ids: List[str]`

---

### 2. Investigation Agent (Provenance Validation)
**Problem:** How do we trust the decisions we're reviewing? They could be tampered.

**Solution:** Traverse W3C PROV-O graph, verify SHA-256 hash per node
```
Decision Node
├─ case_id: "CASE-0047"
├─ outcome: "DENIED"
├─ content_hash: "40bcd..." (SHA-256 of entire content)
│   └─ If tampered, hash mismatch → flag immediately
└─ children: [Evidence nodes, Rule nodes, ...]
```

**Key insight:** Hash stored IN content, then ProvNode computes outer hash. Nested hashing provides two layers of tamper detection.

**Output:** 
- `evidence_items: List[EvidenceItem]` — Case decision + applicant profile
- `provenance_nodes: List[ProvNode]` — Full decision chain for audit

---

### 3. Legal Agent (Regulation Matching)
**Problem:** Compliance officers need to know "which regulation does this decision violate?"

**Solution:** pgvector RAG + dynamic tool calling
```
Step 1: Embed user query: "Are these denials discriminatory?"
Step 2: pgvector similarity search → top-10 regulation sections
Step 3: LLM uses search_regulations tool to fetch full text
Step 4: LLM analyzes: "Denial based on age (input variable), 
        ECOA §1691(a) prohibits this. VIOLATION."
```

**Tool-based approach:** Regulations fetched on-demand, not pre-cached. Adapts to any regulatory framework.

**Output:**
- `compliance_verdict: "COMPLIANT" | "VIOLATION" | "UNCERTAIN"`
- `applicable_regulations: List[str]` — ECOA §1691(a), HMDA §2803, etc.
- `legal_citations: List[str]` — Quoted regulation text

---

### 4. Bias Detection Agent (Anomaly Analysis)
**Problem:** Statistical discrimination is hard to spot. Need unsupervised detection.

**Solution:** Isolation Forest anomaly detection
```
1. Extract features from all cases:
   - Age, income, credit score, geography, outcome
   
2. Isolation Forest learns normal patterns
   
3. Flags outliers:
   - "All denials in census tract 12 are age 60+"
   - "Income $25k–$50k has 40% denial rate vs. 5% overall"
   
4. Reports anomaly score (0–1)
```

**Why Isolation Forest?** Unsupervised (no training data), robust, interpretable.

**Output:**
- `bias_detected: bool`
- `bias_confidence: float (0.0–1.0)`
- `statistical_findings: List[str]` — Human-readable anomalies

---

### 5. Evidence Assembly (Fan-In)
**Problem:** Multiple agents ran in parallel. How do we combine results?

**Solution:** Trust scoring + fact combination
```
Legal verdict: COMPLIANT (confidence 0.95)
Bias verdict:  ANOMALY (confidence 0.72)

Fan-in logic:
- If legal says VIOLATION → always escalate (no exceptions)
- If bias_confidence > 0.85 → escalate for human review
- Otherwise → proceed to report

trust_score = (legal_conf + bias_conf) / 2
```

**Output:** `investigation_sufficient: bool` — Do we have enough confidence to auto-resolve?

---

### 6. Report Agent (Synthesis & Export)
**Problem:** Generating a compliance report that satisfies both engineers and regulators.

**Solution:** GPT-4o synthesis with guardrails
```
Input from all agents → Narrative synthesis:
"This investigation analyzed 50 credit decisions from Jan–Mar 2024
under ECOA and HMDA. No demographic discrimination detected. Two
anomalies flagged (see Appendix). Verdict: COMPLIANT."

Guardrails:
- output_guard filters PII (SSN, phone, email)
- Fact checker verifies citations match regulations
- Low-confidence claims re-submitted to legal agent
```

**Output:**
- `final_report: str` — Markdown compliance report
- `report_confidence: float` — Model's confidence in verdict
- `report_citations: List[str]` — Regulation sections cited

---

### 7. Audit Agent (Compliance Trail) ✨ v2 ADDITION
**Problem:** Regulators require 7-year audit trail (SR 11-7, GDPR Article 30).

**Solution:** Structured event logging to audit_log table
```
Event Sequence:
├─ investigation_started
│  └─ query, domain, date_range, tenant_id
├─ discovery_complete
│  └─ case_count, confidence, case_ids (first 10)
├─ investigation_complete
│  └─ evidence_count, broken_chains
├─ legal_analysis_complete
│  └─ verdict, regulatory_risk, applicable_regulations
├─ bias_analysis_complete
│  └─ bias_detected, confidence, dimensions_checked
├─ report_finalized
│  └─ compliance_verdict, risk_level, report_length
└─ hitl_escalated (if applicable)
   └─ reason, report_confidence
```

**Storage:** PostgreSQL JSONB with automatic timestamps.
**Export:** W3C PROV-O format for regulator submission.

**Output:**
- `audit_entries_written: int` — Number of events logged
- Audit log table contains full history for compliance review

---

## State Machine: LangGraph Flow

```
                    START
                      ↓
              ┌─────────────────┐
              │ discovery_agent │
              └────────┬────────┘
                       ↓
            investigation_agent
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   legal_agent    bias_agent   (parallel fan-out)
        ↓              ↓
        └──────────────┼──────────────┘
                       ↓
          ┌────────────────────────┐
          │ evidence_assembly      │
          │ (fan-in results)       │
          └────────────┬───────────┘
                       ↓
              ┌─────────────────┐
              │  report_agent   │
              └────────┬────────┘
                       ↓
          ┌──────────────────────────┐
          │ route_after_report       │
          │ Confidence ≥ 0.85 ?      │
          └────────┬──────────┬──────┘
             YES   │          │ NO
                   ↓          ↓
              complete    hitl_node (PAUSED)
                   ↓          ↓
                   └──────────┘
                       ↓
              ┌─────────────────┐
              │  audit_agent    │
              │  (always runs)  │
              └────────┬────────┘
                       ↓
                      END
```

**Key insight:** HITL pause/resume works because LangGraph persists full state to PostgreSQL checkpoint. Resume from exact node where paused.

---

## Database Schema (Core Tables)

### investigations
```sql
- investigation_id: str (PK)
- tenant_id: str (tenant isolation)
- query: str (user's plain-English request)
- status: str (pending, running, complete, failed, pending_human)
- compliance_verdict: str (COMPLIANT, VIOLATION, UNCERTAIN)
- regulatory_risk: str (LOW, MEDIUM, HIGH, CRITICAL)
- state_snapshot: JSONB (full LangGraph state at checkpoint)
- created_at, updated_at: timestamp
```

### provenance_nodes
```sql
- node_id: str (PK) — e.g., "decision-CASE-0047"
- node_type: str — prov:Entity, prov:Activity, prov:Agent
- tenant_id: str (FK to investigations)
- content: JSONB — Domain-specific payload
  {
    "case_id": "CASE-0047",
    "outcome": "DENIED",
    "case_ids": [...],  # NEW in v2 — source documentation
    "content_hash": "40bcd..." # NEW in v2 — tamper detection
  }
- content_hash: str (SHA-256 of content)
- timestamp: timestamp
```

### provenance_edges
```sql
- edge_id: str (PK)
- source_id: str (FK to node_id)
- target_id: str (FK to node_id)
- relation: str — prov:wasGeneratedBy, prov:used, prov:wasAttributedTo
- tenant_id: str (FK)
```

### audit_log (NEW in v2)
```sql
- id: UUID (PK)
- investigation_id: str (FK)
- tenant_id: str (FK)
- event: str — "investigation_started", "discovery_complete", etc.
- actor: str — "discovery_agent", "system", "human"
- details: JSONB — Event-specific metadata
- created_at: timestamp
```

---

## Vector Search: HNSW Optimization

### Problem
Default pgvector cosine similarity scans all rows:
```
SELECT * FROM regulation_documents
ORDER BY embedding <=> query_embedding
LIMIT 10
```
With 500+ regulations, this is slow (full table scan).

### Solution: HNSW Index
```sql
CREATE INDEX idx_regulation_docs_hnsw
ON regulation_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Result:** 10x speedup, <10ms per search vs. ~100ms.

**Why HNSW?**
- Navigable Small World graph structure
- M=16: max connections per node (balance speed/quality)
- ef_construction=64: more neighbors → better quality → slower build
- Tuned for compliance (quality > raw speed)

---

## Cost Optimization: Why 3-Stage Discovery?

### Naive Approach (❌ $150/run)
```
All 10,000 decisions → GPT-4o
10,000 × 500 tokens = 5M tokens
5M tokens × $0.003/1K tokens = $15 per run
150 runs/month = $2,250/month
```

### SENTINEL Approach (✓ $0.001/run)
```
Step 1: BM25 keyword filter
├─ "credit" "denied" "income" → 1,000 matches (eliminates 90%)
├─ Cost: $0 (local, milliseconds)

Step 2: DistilBERT semantic ranking
├─ Embed all 1,000 survivors + query vector
├─ Cosine similarity sort
├─ Keep top 50 (eliminates 98% overall)
├─ Cost: $0 (local, 2-4 seconds, 250MB model)

Step 3: llama3.2:3b final judgment
├─ Review 50 borderline cases
├─ "Is this case about credit discrimination?" → yes/no
├─ Keep 3-5 final cases
├─ Cost: $0 (local)

Total: $0.001/run (150x cheaper)
```

**Math:** 3 final cases analyzed deeply > 10,000 skimmed quickly.

---

## Provenance Standard: W3C PROV-O

Why W3C PROV-O instead of custom JSON?

✓ **Regulator-friendly** — Bank of America, FDA use it for audit trails
✓ **Machine-readable** — Tools exist to import into compliance systems
✓ **Extensible** — Add custom fields without breaking standard
✓ **Exportable** — Generate PROV-N (text), RDF (semantic web), PROV-JSON

Example export:
```json
{
  "@context": "https://www.w3.org/ns/prov-json",
  "@id": "sentinel://bank-acme/INV-F7F2AA0D8E80",
  "prov:wasGeneratedBy": "activity-investigation-INV-F7F2AA0D8E80",
  "prov:wasAttributedTo": "agent-investigation-INV-F7F2AA0D8E80",
  "prov:generatedAtTime": "2026-04-26T05:00:00Z"
}
```

Regulators can validate: Does this decision trace back to a compliant process?

---

## Scaling Considerations

### Horizontal Scaling (Multiple Workers)
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Worker 1    │  │ Worker 2    │  │ Worker 3    │
│ (processing)│  │ (processing)│  │ (processing)│
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        ↓
                  ┌──────────────┐
                  │ Redis Queue  │
                  │ (job queue)  │
                  └──────┬───────┘
                         ↓
                  PostgreSQL DB
```

Each worker pulls jobs from Redis queue, processes independently.

### Vertical Scaling (Single Server Optimization)
```
Case Batching:
  - OpenAI tier: batch_size = 100 cases (fast API)
  - Ollama tier: batch_size = 25 cases (slower local LLM)
  
Vector Indexes:
  - HNSW on regulation_documents (10x search speedup)
  - Lazy load DistilBERT (only needed if BM25 filtering enabled)
  
Connection Pooling:
  - AsyncPG pool_size = 10 (prevent connection exhaustion)
  - Redis connection: single persistent socket
```

---

## Security Model

### Tenant Isolation
```python
# Every query includes tenant_id filter
SELECT * FROM investigations 
WHERE investigation_id = :id 
  AND tenant_id = :tenant_id  # ← Mandatory

# Frontend enforces:
# - API key belongs to tenant
# - Dashboard hides other tenants' data
```

### Input Guards (Guardrails)
```python
input_guard.py:
├─ SQL injection detection (parameterized queries + scanning)
├─ Prompt injection detection (LLM-based)
├─ PII detection (Presidio) — blocks SSN, credit cards in queries
├─ Rate limiting — 20 requests/min per tenant
└─ Request size limits — max 10MB payload
```

### Output Guards (Compliance)
```python
output_guard.py:
├─ PII redaction (SSN, phone, email from final report)
├─ Fact checking — does each claim cite a regulation?
├─ Confidence gating — low-confidence verdicts → HITL escalation
└─ Citation verification — linked regulation sections exist
```

---

## Observability & Debugging

### Heartbeat Events
```python
heartbeat.emit("discovery_agent", "running", iteration_count)
heartbeat.emit("discovery_agent", "complete", iteration_count)
heartbeat.emit("discovery_agent", "failed", iteration_count)
```
Used by dashboard to show agent progress in real-time.

### Cost Tracking
```python
cost_tracker.record_cost(
    agent_name="legal_agent",
    model="gpt-4o-mini",
    provider="openai",
    input_tokens=815,
    output_tokens=37,
    state_total=0.00144  # cumulative cost
)
```
Breaks down cost per agent, per provider, per investigation.

### LangFuse Integration
```
Every LLM call traces to LangFuse:
├─ Latency per call
├─ Token count per call
├─ Cost per call
├─ Full prompt/response logging (for debugging)
└─ Aggregated metrics per tenant
```

---

## Deployment Strategies

### Development (Docker Compose)
```bash
docker-compose up -d
# Starts: PostgreSQL, Redis, Ollama, API, Worker, Scheduler, Dashboard
```

### Staging (Kubernetes-ready)
```yaml
# health probe
GET /health → {"status": "alive"}

# readiness probe
GET /ready → {"status": "ready", "checks": {...}}

# Liveness: container restart on failure
# Readiness: pod exclusion from traffic if DB down
```

### Production (Multi-zone)
```
Zone 1: API + Dashboard (stateless, multiple replicas)
Zone 2: Worker pool (arq jobs, horizontal scaling)
Zone 3: PostgreSQL (managed, high-availability)
Zone 4: Redis (managed, Redis Cluster for HA)
```

---

## Future Roadmap

1. **Phase 3A: Real-time Streaming**
   - Server-sent events (SSE) for live investigation progress
   - WebSocket for interactive escalation workflow

2. **Phase 3B: Advanced Indexing**
   - Add Algolia for full-text search on regulation text
   - Implement embedding versioning (re-index on model updates)

3. **Phase 4: Distributed Tracing**
   - OpenTelemetry for cross-service tracing
   - Distributed context propagation

4. **Phase 5: Custom Regulations**
   - Upload custom regulation PDFs
   - Automatic section extraction + embedding

---

## Questions?

- **Architecture questions:** See `ARCHITECTURE.md` (this file)
- **Setup questions:** See `SETUP.md`
- **API questions:** See `sentinel/api/main.py` docstrings
- **Agent logic:** See agent files (each has detailed comments)
