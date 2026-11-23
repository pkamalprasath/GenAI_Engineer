# SENTINEL
### Autonomous AI Compliance Investigation Platform

> Multi-agent LangGraph system that audits AI-assisted decisions for regulatory violations — detecting bias, tracing decision provenance, and generating regulatory-grade reports with human-in-the-loop oversight.

**Domains:** Financial lending (ECOA · FCRA · HMDA · CRA) · Pharma/Clinical trials (FDA 21 CFR 312 · ICH E6 · EU AI Act)

---

## Business Impact

| Metric | Manual Process | With SENTINEL |
|--------|---------------|---------------|
| Quarterly compliance review | 40 hours (analyst + legal team) | 45 seconds autonomous + 5 min human review |
| Cost per investigation | $8,000–$15,000 (labor + legal fees) | ~$0.002 in API tokens |
| Bias detection coverage | Spot-checks (~5% of decisions) | 100% of all decisions, every run |
| Audit trail | Mutable manual logs | SHA-256 tamper-evident provenance chain |
| Regulator-ready report | 2 weeks (compile, format, legal review) | Generated automatically, citation-verified |
| Human escalation load | Every decision reviewed manually | ~15–20% escalated (low-confidence only) |
| Decision traceability | Black-box AI, no explanation | Full W3C PROV-O graph from query → verdict |

**Who benefits:**
- **Compliance teams** — investigate 100% of AI decisions rather than sampling 5%
- **Legal departments** — reports cite ECOA §1691(a), HMDA §2803, EU AI Act Article 9 automatically
- **Regulators (CFPB, FDA, state)** — tamper-evident audit trail satisfies SR 11-7 and GDPR Article 22
- **Engineering** — swap LLM providers (OpenAI ↔ Anthropic) with one config line, zero code changes

---

## What It Does

A compliance manager submits a plain-English query. Six specialized agents run autonomously:

```
"Review credit decisions Jan–Mar 2024 for ECOA and HMDA compliance"
                                │
              ┌─────────────────▼──────────────────┐
              │         SENTINEL Pipeline            │
              │                                      │
              │  1. Discovery Agent                  │
              │     BM25 → DistilBERT → llama3.2:3b  │
              │     Selects relevant cases from DB    │
              │                                      │
              │  2. Investigation Agent               │
              │     Loads W3C PROV-O provenance graph │
              │     Verifies SHA-256 hash per node    │
              │     Flags tampered / broken chains    │
              │                                      │
              │  3. Legal Agent ──────────┐           │
              │     pgvector RAG over     │ parallel  │
              │     ECOA + HMDA + EU AI   │ fan-out   │
              │     Maps findings to law  │           │
              │                           │           │
              │  4. Bias Detection ───────┘           │
              │     Isolation Forest anomaly detect   │
              │     Tests age · income · geography    │
              │     Flags disparity > 15% threshold   │
              │                                      │
              │  5. Evidence Assembly                 │
              │     Fan-in from parallel agents       │
              │     Trust scoring + citation index    │
              │                                      │
              │  6. Report Agent                      │
              │     GPT-4o / Claude synthesizes       │
              │     regulatory report, PII-verified   │
              └──────────────────────────────────────┘
                                │
              ┌─────────────────▼──────────────────┐
              │   Confidence ≥ 0.85 → Auto-resolve  │
              │   Confidence < 0.85 → HITL Queue    │
              └─────────────────────────────────────┘
```

**Output:** Compliance verdict (COMPLIANT / VIOLATION / UNCERTAIN), regulatory risk level (LOW / MEDIUM / HIGH / CRITICAL), bias finding with anomaly score, full audit report citing provenance node IDs and regulation sections — all in under 60 seconds.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Business User (Browser)                       │
│                   Streamlit Dashboard :8502                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                  FastAPI Application :8003                        │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────────────────┐  │
│  │ AuthMiddlware│  │RateLimitMiddle│  │  RequestIDMiddleware   │  │
│  └─────────────┘  └───────────────┘  └───────────────────────┘  │
│                                                                   │
│  POST /api/v1/investigations           ← submit (background)     │
│  GET  /api/v1/investigations/{id}      ← poll + final report      │
│  GET  /api/v1/escalations              ← HITL review queue        │
│  POST /api/v1/escalations/{id}/resolve ← human approval          │
│  GET  /api/v1/provenance/{id}/trace    ← decision chain          │
│  GET  /api/v1/analytics               ← trend metrics            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│             LangGraph State Machine  (9 nodes)                   │
│                                                                   │
│  discovery → investigation → legal ──┐                           │
│                             bias ────┤ fan-out / fan-in          │
│                                      ▼                           │
│                            evidence_assembly                      │
│                                      │                           │
│                                      ▼                           │
│                              report_agent                         │
│                                      │                           │
│                              route_after_report                   │
│                              ├─ confidence ≥ 0.85 → complete     │
│                              └─ hitl_node (graph pause + resume) │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   PostgreSQL          Ollama :11434      OpenAI / Anthropic
   decisions +         llama3.2:3b        gpt-4o-mini /
   provenance +        nomic-embed-text   claude-haiku
   investigations      (local, free)      (configurable)
   + pgvector
```

**Guardrails at every system boundary:**

| Boundary | Guard | What it blocks |
|----------|-------|----------------|
| API input | `input_guard.py` | SQL injection, prompt injection, SSRF, XSS, PII in queries |
| Agent output | `output_guard.py` | PII in report, uncited claims, low-confidence auto-resolve |
| DB access | `tenant_id` on every query | Cross-tenant data leakage → `IsolationBreachError` |
| Provenance | SHA-256 per node | Tampered records detected on next read |

---

## Technical Stack

| Layer | Technology | Why This Choice |
|-------|-----------|----------------|
| Agent orchestration | **LangGraph 0.2** | Stateful graph with PostgreSQL checkpoint — HITL pause/resume without losing state |
| API | **FastAPI + asyncio** | Background tasks per investigation; async DB sessions prevent thread blocking |
| Database | **PostgreSQL + SQLAlchemy async** | JSONB for flexible provenance content; asyncpg pooling |
| Regulation search | **pgvector (cosine similarity)** | 1536-dim embeddings, top-k retrieval; legal agent fetches only relevant sections |
| Local LLM | **Ollama (llama3.2:3b + nomic-embed-text)** | Zero API cost for classification and local embeddings; fits in 8 GB RAM |
| Reasoning LLM | **OpenAI gpt-4o-mini / Anthropic claude-haiku** | Provider-agnostic via `configs/models.yaml` — switch with one line |
| Semantic re-ranking | **DistilBERT (HuggingFace transformers)** | CPU-only, 250 MB, `lru_cache` for instant subsequent calls |
| Keyword pre-filter | **rank_bm25** | Eliminates 95% of records before BERT; deterministic, auditable |
| Anomaly detection | **Isolation Forest (scikit-learn)** | Unsupervised — finds bias patterns without labeled training data |
| PII detection | **Microsoft Presidio** | Named entity recognition; separate entity lists for input vs output |
| Provenance standard | **W3C PROV-O** | prov:Entity (decisions) + prov:Activity (investigation) + prov:Agent (AI agent) |
| Observability | **LangFuse + LangSmith** | LangFuse: production cost/latency per tenant; LangSmith: LangGraph trace debugging |
| Dashboard | **Streamlit** | Live agent progress, interactive provenance graph, escalation queue, analytics |
| Graph visualization | **pyvis + NetworkX** | Interactive decision chain rendering in browser with physics layout |

---

## Key Engineering Decisions & Tradeoffs

### 1. BM25 → DistilBERT → llama3.2:3b — Three-Stage Discovery

**The naive approach:** Send all 10,000 decisions to GPT-4o and ask it to find relevant ones.

| Problem with naive | Impact |
|--------------------|--------|
| 10,000 records × ~500 tokens = 5M tokens per run | ~$150/run at GPT-4o rates — unusable at scale |
| LLM context windows cap at 128K | Cannot process full dataset in one call |
| Non-deterministic LLM relevance scores | Compliance requires reproducible, auditable selection |

**SENTINEL three-stage hybrid:**
```
BM25  (milliseconds, zero cost)    → eliminates ~95% of records
DistilBERT  (2–4 s, CPU-only)      → cosine similarity re-ranks survivors
llama3.2:3b  (local, zero API cost) → resolves only the 3–8 "borderline" cases
```
**Result:** ~$0.001 per investigation vs $150. Every selection is traceable to a deterministic algorithm.

**Tradeoff:** DistilBERT loaded at startup uses 250 MB RAM. On memory-constrained systems, this can be disabled and BM25 alone used as the pre-filter.

---

### 2. LangGraph over a Simple Agent Loop

LangGraph's checkpoint system lets the graph **pause mid-execution** when human review is required, persist full state to PostgreSQL, and **resume exactly where it stopped** after human approval. A plain `while` loop loses all in-flight state on pause.

**Tradeoff:** LangGraph adds ~200ms overhead per node for state serialization. Acceptable for compliance investigations (45-second total pipeline) but would be too slow for real-time latency-sensitive use cases.

---

### 3. Parallel Legal + Bias Agents (Fan-Out)

Legal analysis and bias detection are independent — neither uses the other's output. Running them concurrently cuts total pipeline time from ~90s to ~45s.

**Tradeoff:** Both agents make LLM calls simultaneously, doubling concurrent API usage. Under strict rate limits, one agent may slow the other via backpressure.

---

### 4. Separate PII Entity Lists for Input vs Output

The input guard blocks PERSON, LOCATION, DATE_TIME, EMAIL, SSN, etc. The output guard uses a narrower list (SSN, EMAIL, PHONE, CREDIT_CARD only). Compliance reports legitimately contain location names (census tracts) and regulatory dates. Using the same entity list for both blocked valid, correctly anonymized reports.

---

### 5. pgvector for Regulation RAG (Not FAISS)

FAISS requires an offline indexing step and is rebuilt from scratch on schema changes. pgvector stores embeddings alongside regulation metadata in the same PostgreSQL database — transactional consistency, no separate index server, and the legal agent queries it live per investigation. New regulations added to the DB are available immediately to the next investigation without a service restart.

**Tradeoff:** pgvector cosine search on 17 embeddings is trivially fast. At 100,000+ regulation sections, a dedicated vector DB (Weaviate, Qdrant) would outperform pgvector.

---

### 6. Single YAML Config Source of Truth

Model names, risk thresholds, bias dimensions, PII entity lists, and rate limits live in YAML — never in Python source. Switching providers, adjusting the HITL confidence threshold, or adding a new bias dimension requires editing one config file and restarting the API. No redeployment.

---

## Key Achievements

- **17 regulation sections** embedded across two domains: finance (ECOA, FCRA, HMDA, FHAct, CRA) and pharma/AI (FDA 21 CFR 312, ICH E6, EU AI Act Articles 9 & 13, FDA 21 CFR 11) — legal agent dynamically retrieves only what's relevant to each investigation
- **Multi-domain support** from a single pipeline — domain specified per investigation request, no code change
- **Isolation Forest bias detection** across 3 demographic dimensions (age, income, geography) with no labeled training data; disparity threshold configurable per domain
- **W3C PROV-O provenance graph** with SHA-256 tamper detection — satisfies SR 11-7, GDPR Article 22, and CFPB examination requirements
- **HITL graph interrupt** that pauses mid-graph, persists full LangGraph state to PostgreSQL, resumes on human approval — compliance officer modifies or approves the draft report before it becomes final
- **Zero-overhead observability** — LangFuse and LangSmith operate in no-op mode when keys are absent; no errors, no performance hit in local dev
- **300 synthetic decisions** with injected anomalies (geographic bias, broken provenance chains, GDPR deletion violations) for reproducible demo and testing
- **Output guardrail** verifies every citation: each provenance node ID in the report is checked against the DB before the report is released — no hallucinated citations

---

## Project Structure

```
sentinel/
├── configs/                      # All configuration — no values hardcoded in code
│   ├── models.yaml               # Model routing: provider, model ID, temperature per tier
│   ├── agents.yaml               # Per-agent thresholds, HITL triggers, RAG top-k
│   ├── security.yaml             # OWASP patterns, PII entity lists, rate limits
│   └── domains/
│       └── finance.yaml          # Regulations, bias dimensions, disparity thresholds
│
├── sentinel/
│   ├── agents/
│   │   ├── classifiers/
│   │   │   ├── bm25_ranker.py        # Stage 1: term-frequency pre-filter
│   │   │   ├── bert_classifier.py    # Stage 2: DistilBERT cosine re-ranking
│   │   │   └── anomaly_detector.py   # Isolation Forest for bias detection
│   │   ├── discovery_agent.py        # Orchestrates BM25→BERT→LLM pipeline
│   │   ├── investigation_agent.py    # Provenance chain load + hash verification
│   │   ├── legal_agent.py            # pgvector RAG → regulation mapping
│   │   ├── bias_detection_agent.py   # Statistical disparity testing
│   │   └── report_agent.py           # Synthesis + output guard validation
│   │
│   ├── graph/
│   │   ├── builder.py                # Compiles 9-node LangGraph + PostgreSQL checkpoint
│   │   └── edges.py                  # Routing: auto-resolve vs HITL escalation
│   │
│   ├── provenance/
│   │   ├── store.py                  # PostgreSQL JSONB read/write + NetworkX graph builder
│   │   ├── query.py                  # trace_decision_chain, detect_broken_chains
│   │   └── schema.py                 # ProvNode, ProvEdge, NodeType, RelationType
│   │
│   ├── guardrails/
│   │   ├── input_guard.py            # OWASP blocking + PII redaction on queries
│   │   ├── output_guard.py           # Citation verification + PII scan + confidence gate
│   │   └── pii_detector.py           # Presidio wrapper with input/output entity separation
│   │
│   ├── api/
│   │   ├── main.py                   # All endpoints + background investigation runner
│   │   ├── middleware.py             # Auth, rate limiting, request ID injection
│   │   └── models.py                 # Pydantic request/response schemas
│   │
│   ├── observability/
│   │   ├── langfuse_tracer.py        # LangFuse v4 span instrumentation
│   │   ├── cost_tracker.py           # Per-agent token cost accumulation
│   │   └── heartbeat.py              # Stuck-agent detection with configurable timeout
│   │
│   └── dashboard/pages/
│       ├── 1_investigate.py          # Submit query + live agent progress
│       ├── 2_provenance.py           # Interactive pyvis decision chain graph
│       ├── 3_escalations.py          # HITL review queue with approve/modify/close
│       └── 4_analytics.py            # Compliance rate, bias rate, cost trends
│
├── souls/                        # Agent system prompts (LLM persona / soul files)
├── data/
│   ├── regulations/              # Regulation YAML source files (per domain)
│   └── synthetic/                # 300 synthetic decisions (gitignored, regenerated)
├── tests/
│   ├── unit/                     # Component tests — classifiers, guardrails, state schema
│   ├── integration/              # Full pipeline tests — no Docker required
│   ├── security/                 # OWASP injection + PII leakage boundary tests
│   └── performance/              # Latency benchmarks per agent
└── scripts/
    ├── generate_synthetic_data.py  # 300 decisions with injected anomalies
    ├── seed_database.py            # Create tables + load synthetic decisions
    └── ingest_regulations.py       # Embed regulation sections into pgvector
```

---

## Setup

### Prerequisites
- Python 3.11+
- Docker (for PostgreSQL + pgvector)
- [Ollama](https://ollama.ai) installed locally
- OpenAI API key (or Anthropic — configure in `configs/models.yaml`)

### 1. Clone and install
```bash
git clone <repo-url>
cd rag/projects/sentinel

python -m venv ../../.venv
source ../../.venv/bin/activate      # Linux/macOS
# ../../.venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — add your API keys (see .env.example for all required fields)
```

### 3. Start PostgreSQL with pgvector
```bash
docker-compose up -d postgres
```

### 4. Generate data and initialize database
```bash
python scripts/generate_synthetic_data.py   # generates data/synthetic/decisions.json
python scripts/seed_database.py             # creates tables + loads decisions + provenance nodes
python scripts/ingest_regulations.py        # embeds ECOA, HMDA, FDA, EU AI Act into pgvector
```

### 5. Pull Ollama models (local, no API cost)
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 6. Start all services
```bash
# Terminal 1 — local LLM server
ollama serve

# Terminal 2 — FastAPI backend
python -m uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8003

# Terminal 3 — Streamlit dashboard
python -m streamlit run sentinel/dashboard/Home.py --server.port 8502
```

Open **http://localhost:8502** → Investigate → submit a query.

---

## Quick API Demo

```bash
# Submit investigation
curl -X POST http://localhost:8003/api/v1/investigations \
  -H "X-API-Key: $SENTINEL_API_KEY" \
  -H "X-Tenant-ID: bank-acme" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Review credit decisions Jan 1–15 2024 for ECOA fair lending compliance",
    "date_from": "2024-01-01",
    "date_to": "2024-01-15",
    "domain": "finance"
  }'
# → {"investigation_id":"INV-7AA30B1C59D0","status":"queued"}

# Poll until complete (~45 seconds)
curl http://localhost:8003/api/v1/investigations/INV-7AA30B1C59D0 \
  -H "X-API-Key: $SENTINEL_API_KEY" -H "X-Tenant-ID: bank-acme"
# → {"status":"pending_human","compliance_verdict":"VIOLATION","regulatory_risk":"HIGH",
#    "bias_detected":true,"case_count":12,"report_confidence":0.78,"final_report":"..."}

# Human approval (HITL)
curl -X POST http://localhost:8003/api/v1/escalations/INV-7AA30B1C59D0/resolve \
  -H "X-API-Key: $SENTINEL_API_KEY" -H "X-Tenant-ID: bank-acme" \
  -H "Content-Type: application/json" \
  -d '{"response":"Confirmed VIOLATION — geographic bias in CT-015.","action":"approve_draft","reviewer_id":"officer-01"}'
# → {"status":"resolved"}
```

---

## Running Tests

```bash
# Unit tests (no external services required)
python -m pytest tests/unit/ -v

# Integration tests (requires PostgreSQL running)
python -m pytest tests/integration/ -v

# Security boundary tests
python -m pytest tests/security/ -v

# All tests
python -m pytest tests/unit/ tests/integration/ tests/security/ tests/performance/ -v
```

---

## Synthetic Data

`data/synthetic/decisions.json` — 300 credit decisions with injected anomalies (gitignored, regenerated via script):

| Anomaly Type | Count | What It Tests |
|-------------|-------|---------------|
| Geographic bias | 30 | Disparate approval rates by `zip_code_census_tract` |
| Provenance integrity breaks | 10 | Missing / tampered decision chains |
| GDPR deletion violations | 5 | Records present after required erasure date |

Use date range `2024-01-01` → `2024-06-30` to reliably hit injected anomalies.

---

## Observability

| Tool | Tracks | Access |
|------|--------|--------|
| **LangFuse** | Agent latency p50/p95, cost per tenant, tokens per investigation | cloud.langfuse.com → your project |
| **LangSmith** | LangGraph node traces, routing decisions, chain-of-thought per agent | smith.langchain.com → `sentinel-dev` |
| **Structured JSON logs** | Every agent event, cost, heartbeat — queryable in production | stdout / structured log output |

LangFuse and LangSmith operate in no-op mode if keys are not set — zero overhead, zero errors in local dev.

---

## Configuration Reference

All behavior is controlled via YAML — no values hardcoded in Python source:

| File | Controls |
|------|---------|
| `configs/models.yaml` | Model provider, model ID, temperature, max tokens per tier |
| `configs/agents.yaml` | HITL confidence threshold, escalation risk levels, RAG top-k |
| `configs/security.yaml` | OWASP blocked patterns, PII entity lists (input vs output), rate limits |
| `configs/domains/finance.yaml` | Regulations loaded, bias dimensions tested, disparity threshold |

Switch from OpenAI to Anthropic: change `provider` and `model` in `configs/models.yaml`. Restart API. Zero code changes.

---

## License

MIT
