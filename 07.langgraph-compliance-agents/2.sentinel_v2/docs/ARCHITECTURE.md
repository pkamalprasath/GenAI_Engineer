# SENTINEL Architecture Guide

## System Overview

SENTINEL is a portfolio project: a LangGraph workflow that reviews synthetic lending decisions against US fair-lending rules. It runs locally on synthetic data. Three ideas shape it:

1. **Separate agents** for discovery, provenance, legal analysis, bias, reporting and audit
2. **Tamper-evident provenance** — W3C PROV-O style nodes with SHA-256 content hashes
3. **Service split** — API, background worker, scheduler and dashboard (see `docker-compose.yml`)

The README has the graph diagram generated from `sentinel/graph/builder.py`; this file goes deeper on each part.

---

## Agents and workflow nodes

Six agents (discovery, investigation, legal, bias detection, report, audit) plus five plain workflow nodes (fan-out, evidence assembly, HITL review, complete, no cases) make up the 11 LangGraph nodes. Investigation, legal and bias run in parallel.

### 1. Discovery Agent (Case Selection)
**Problem:** Sending every decision record to an LLM to judge relevance is slow, costly and not reproducible.

**Solution:** Three-stage hybrid filter
```
BM25 keyword filter        (local, deterministic)   → drops clearly irrelevant records
DistilBERT semantic rerank (local, CPU-only)        → cosine similarity re-ranking
llama3.2:3b classification (local via Ollama)       → resolves only borderline cases
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

### 5. Evidence Assembly (fan-in node, not an agent)
**Problem:** Multiple agents ran in parallel. How do we combine results?

**Solution:** The three parallel agents write to list fields with `operator.add` reducers, so their outputs merge safely. Routing after fan-in (`route_after_evidence_assembly` in `sentinel/graph/edges.py`):
```
No verdict and no evidence             → hitl_review
regulatory_risk in HIGH / CRITICAL     → hitl_review
bias_detected                          → hitl_review
discovery_confidence below 0.65        → hitl_review
otherwise                              → report_generation
```
After the report, the output guard sets `hitl_required` when report confidence is below 0.85 (`configs/agents.yaml`).

---

### 6. Report Agent (Synthesis & Export)
**Problem:** Generating a compliance report that satisfies both engineers and regulators.

**Solution:** LLM synthesis (model set in `configs/models.yaml`; gpt-4o-mini by default) with guardrails
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

### 6b. Audit Agent (audit trail, added in v2)
**Problem:** A reviewer needs a record of what each step did and why.

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

See the Mermaid diagram in the README, which is drawn from the nodes and edges in `sentinel/graph/builder.py`. In short: discovery → fan-out → (investigation, legal, bias in parallel) → evidence assembly → report → audit → complete, with branches to `hitl_review` and `no_cases`.

**Key point:** HITL pause and resume work because LangGraph saves the graph state to a PostgreSQL checkpoint, so a paused investigation resumes at the node where it stopped.

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
A full scan grows with the number of rows. The current data set is small (16 finance regulation sections), so this matters only if the corpus grows.

### Solution: HNSW Index
```sql
CREATE INDEX idx_regulation_docs_hnsw
ON regulation_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Result:** Not benchmarked in this repo. HNSW is approximate nearest-neighbour search; at this data size an exact scan is already fast.

**Why HNSW?**
- Navigable Small World graph structure
- M=16: max connections per node (balance speed/quality)
- ef_construction=64: more neighbors → better quality → slower build
- Tuned for compliance (quality > raw speed)

---

## Cost: why a 3-stage discovery?

Sending every decision to a hosted LLM costs tokens in proportion to the number of records, and LLM relevance judgements are not reproducible. The BM25 and DistilBERT stages run locally and are deterministic; only the borderline cases reach the local llama3.2:3b model. Per-investigation cost is recorded by `sentinel/observability/cost_tracker.py`, but no cost figure has been measured and published for this repo.

---

## Provenance Standard: W3C PROV-O

Why W3C PROV-O instead of custom JSON?

✓ **Standard** — a W3C recommendation for describing provenance
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

A reviewer can follow a decision back through the activities and agents that produced it.

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
  - HNSW index on regulation_documents (`sentinel/db/migrations/003_hnsw_indexes.sql`)
  - Lazy load DistilBERT (only needed if BM25 filtering enabled)
  
Connection Pooling:
  - AsyncPG pool_size = 10 (prevent connection exhaustion)
  - Redis connection: single persistent socket
```

---

## Security Model

### Tenant-scoped data model
```python
# Queries include a tenant_id filter
SELECT * FROM investigations
WHERE investigation_id = :id
  AND tenant_id = :tenant_id
```
Limitation: this is a tenant-scoped data model, not enforced isolation. The tenant comes from the client-supplied `X-Tenant-ID` header (default `demo-tenant`) and there is one shared API key (`sentinel/api/middleware.py`). Binding the tenant to an authenticated key is future work.

### Input Guards (Guardrails)
```python
input_guard.py:
├─ Pattern-based blocking (SQL injection, prompt injection, XSS, path traversal;
│  patterns in configs/security.yaml)
├─ PII detection and redaction (Presidio)
├─ Trust scoring of context sources
├─ Input length limit (max_input_length in configs/security.yaml)
└─ Per-tenant rate limiting (API middleware; RATE_LIMIT_PER_MINUTE)
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

## Deployment

### Local (Docker Compose)
```bash
docker compose up -d
# Starts 5 services: redis, api, worker, scheduler, dashboard
# PostgreSQL (with pgvector) is external: set DATABASE_URL in .env
# Ollama runs on the host (OLLAMA_BASE_URL)
```

The API exposes `/health` and `/ready`, which an orchestrator could use as liveness and readiness probes. No Kubernetes manifests exist in this repo.

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

- **Overview and quick start:** See the project `README.md`
- **Setup questions:** See `SETUP.md` (this folder)
- **API questions:** See `sentinel/api/main.py` docstrings
- **Agent logic:** See agent files (each has detailed comments)
