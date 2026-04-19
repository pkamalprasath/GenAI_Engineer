# Engineering Knowledge Assistant — Industrial Multimodal RAG

> **Ask any question about your engineering documents. Get a cited, grounded answer in seconds.**
>
> Understands text procedures, data tables, and diagrams — all from your PDF manuals, datasheets, and safety sheets.

---

## What This System Does

Imagine a plant engineer asking: *"What torque do I apply to M12 bolts near the motor, and what PPE do I need?"*

The system:
1. Breaks the question into sub-questions (`torque spec for M12` + `PPE near motor`)
2. Searches 2,500+ indexed chunks — text, tables, and image captions simultaneously
3. Scores each chunk for relevance (CRAG) and discards noise
4. Generates a grounded answer with page citations and confidence level
5. Self-verifies the answer is supported by the retrieved context

**No hallucinations. No guessing. Every fact cited to a source page.**

---

## Benchmark Results — 5 Completed Runs, 50 Questions Each

> Scoring: LLM-as-judge (Claude Haiku), 1–5 scale. Questions span text, tables, images, multihop reasoning, and unanswerable queries.

| Category | Run 1 | Run 2 | Run 3 | Run 4 | **Run 5** |
|---|:---:|:---:|:---:|:---:|:---:|
| Text | 3.30 | 3.77 | 3.43 | 3.67 | **4.13** ✅ |
| Table | 3.30 | 4.20 | 4.10 | **4.30** ✅ | 3.93 |
| Image | 2.70 | 2.77 | 3.30 | **3.37** ✅ | 2.53 |
| Multihop | 2.00 | 3.73 | 2.63 | **3.27** ✅ | 3.00 |
| Unanswerable | 4.40 | 4.23 | 4.77 | **4.73** ✅ | 4.67 |
| **Overall** | **3.13** | **3.59** | **3.65** | **3.87** 🏆 | **3.65** |

**Best run: Run 4 — 3.87 / 5.0** (Claude Sonnet generation + query decomposition + parent-child chunking)

Each run is a full re-ingest + 50-question evaluation. Run 6 DB is prepared (2,528 chunks with adaptive CRAG fixes applied) — evaluation pending Anthropic API key configuration.

See [`results/PIPELINE_DEEP_DIVE.md`](results/PIPELINE_DEEP_DIVE.md) for the full per-category breakdown, cost analysis, and what changed each run.

### What drove the score from 3.13 → 3.87

| Change | Run | Score Impact |
|---|---|---|
| Contextual prefix (filename+section+page on every chunk) | R2 | +0.46 overall |
| Full-page PNG render for GHS/SDS vector graphics | R2 | +18 → 344 image chunks |
| Batched CRAG scoring (5 calls → 1 call) | R2 | −3s latency |
| Type-aware image caption prompt (separate instructions per image type) | R3 | +0.53 on images |
| Local HuggingFace embeddings (replaced OpenAI bug) | R3 | −$0.50/run |
| Claude Sonnet for generation (replaced Haiku) | R4 | +0.22 overall |
| Query decomposition (multihop → sub-questions) | R4 | +0.64 on multihop |
| Parent-child chunking (child retrieval, parent generation) | R4 | +0.24 on text |
| SDS keyword boost (safety queries get targeted search) | R5 | +0.46 on text |

---

## Architecture

```
                    ┌──────────────────────────────┐
                    │  PDF Documents               │
                    │  (manuals, datasheets, SDS)  │
                    └──────────┬───────────────────┘
                               │  ONE TIME (or when files change)
                               ▼
┌──────────────────────────────────────────────────────┐
│  INGESTION PIPELINE                                  │
│                                                      │
│  pypdf → text  ──► SemanticChunker  ──► parent+child │
│  pdfplumber → tables ──► 6-row markdown groups       │
│  pymupdf → images ──► Claude Haiku vision caption    │
│      └── full-page PNG fallback (GHS vector graphics)│
│                                                      │
│  All chunks: prepend [filename — section, page]      │
│  Embed: all-MiniLM-L6-v2 (384-dim, local, no API)    │
│  Store: PostgreSQL + pgvector                        │
└──────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │  PostgreSQL + pgvector        │
                    │  2,528 chunks across 3 docs  │
                    │  (1,262 text + 895 table      │
                    │   + 371 image)               │
                    └──────────┬───────────────────┘
                               │  ON EVERY QUESTION
                               ▼
┌──────────────────────────────────────────────────────┐
│  RETRIEVAL PIPELINE                                  │
│                                                      │
│  1. Adaptive Router — simple query? answer directly  │
│  2. Query Decomposition — multihop → sub-questions   │
│  3. HyDE — short query → hypothetical answer para    │
│  4. Hybrid Search — pgvector + BM25 per chunk type   │
│     (text/table/image searched separately)           │
│  5. SDS Boost — safety keywords get extra sds search │
│  6. RRF — merge all ranked lists by position         │
│  7. CRAG — score relevance, drop noise, set confidence│
└──────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────┐
│  GENERATION PIPELINE                                 │
│                                                      │
│  Build P2-style prompt with sub-query labels         │
│  Route: text → Claude Sonnet | images → vision model │
│  Self-RAG critique (SUPPORTED / PARTIALLY / RETRY)   │
│  Return: answer + citations + confidence level       │
└──────────────────────────────────────────────────────┘
                               │
                               ▼
         "M12 bolt torque: 85 Nm (Source: gearbox_manual.pdf, p.47)
          PPE: insulated gloves, safety glasses (Source: safety_manual.pdf, p.12)
          Confidence: HIGH"
```

---

## Key Technical Choices (from Systematic Experiments)

| Component | Choice | Alternative Rejected | Why |
|---|---|---|---|
| **Chunking** | Semantic (SemanticChunker parent+child) | Fixed-size 512 tokens | Semantic splits at topic boundaries, keeps procedures intact |
| **Embedding** | all-MiniLM-L6-v2 (384-dim, local) | OpenAI text-embedding-3 | Same score (5.0), no API cost, no latency |
| **Vector Store** | PostgreSQL + pgvector | Chroma / Qdrant | SQL metadata filtering, one Docker container, fully transparent |
| **LLM (generation)** | Claude Sonnet 4.6 | Claude Haiku | Multihop score 3.27 vs 2.63 |
| **LLM (judgment)** | Claude Haiku | GPT-4o-mini | API quota, lower cost |
| **Retrieval** | HyDE + Dense + BM25 + RRF | Dense only | HyDE: 4.9 vs 4.833; BM25 catches exact specs like "DIN EN 13463-1" |
| **Reranking** | Skipped | cross-encoder reranker | +2.7s latency, zero quality gain |
| **Image captioning** | Claude Haiku | Claude Sonnet | Sonnet filtered 257/359 images; Haiku captured 354/359 |

---

## Observability

Full pipeline tracing via **Langfuse Cloud** — every query produces a trace with:

- Latency per step (HyDE, retrieval, CRAG, generation, Self-RAG)
- CRAG relevance labels per chunk
- LLM model and token counts
- Self-RAG grounding status
- Final confidence level

Set `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` in `.env` to enable. No-op if not configured.

---

## Production Features

| Feature | Implementation |
|---|---|
| **Incremental indexing** | SHA-256 file hash — unchanged files skip entirely, changed files auto-re-index |
| **Multimodal** | Text + tables (Markdown) + images (vision captions) all searchable |
| **OWASP security** | Path traversal protection, rate limiting (30/min), input sanitization, no stack traces in responses |
| **CORS** | Restricted to localhost:8501/8511 only |
| **PII guardrails** | Presidio-based redaction (configurable, off by default) |
| **Adaptive routing** | Simple factual queries answered directly (0 retrieval calls) |
| **Confidence scoring** | Every answer rated HIGH / MEDIUM / LOW based on CRAG output |
| **Self-RAG** | Answer verified against context, 1 retry if not grounded |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Docker (for PostgreSQL + pgvector)
- An Anthropic or OpenAI API key

### 1. Start the database
```bash
docker compose up -d
```

### 2. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

> First run also downloads the spaCy model for PII detection:
> `python -m spacy download en_core_web_lg`

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY (or OPENAI_API_KEY)
```

### 4. Ingest documents
```bash
python ingest_docs.py data/
# Incremental: unchanged files are automatically skipped on re-runs
```

Expected output:
```
NEW: pump_maintenance_manual.pdf  → 412 text, 78 table, 45 image chunks
NEW: hydraulic_oil_sds.pdf        → 89 text, 8 table, 22 image chunks
SKIP: pump_maintenance_manual.pdf (unchanged)  ← on second run
```

### 5. Start the chat UI
```bash
streamlit run app.py
# Opens at http://localhost:8501
```

### 6. Or use the REST API
```bash
uvicorn api:app --reload
# POST http://localhost:8000/query
# GET  http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the torque spec for M12 bolts?"}'
```

---

## Project Structure

```
engineering-rag/
│
├── docker-compose.yml          # PostgreSQL + pgvector (one command)
├── requirements.txt            # All dependencies, grouped by category
├── .env.example                # All env vars with placeholder values
├── ingest_docs.py              # Entrypoint: python ingest_docs.py data/
├── app.py                      # Streamlit chat UI
├── api.py                      # FastAPI REST API
│
├── configs/
│   ├── settings.py             # Single source of truth for all config
│   └── logging_config.py       # Structured JSON logging
│
└── src/
    ├── ingest/
    │   ├── document_parser.py  # PDF → {text blocks, tables, images}
    │   ├── chunker.py          # Semantic/table/image chunking strategies
    │   ├── image_captioner.py  # Claude Haiku vision → searchable caption
    │   └── vectorstore.py      # pgvector: schema, hash-based upsert, search
    │
    ├── retrieval/
    │   ├── adaptive_router.py  # Simple vs complex query classification
    │   ├── hyde.py             # Short query → hypothetical answer paragraph
    │   ├── query_decomposer.py # Multihop → sub-questions (up to 4)
    │   ├── retriever.py        # Hybrid search + BM25 + RRF merge
    │   └── crag.py             # Chunk relevance scoring + confidence
    │
    ├── generation/
    │   ├── prompts.py          # P2 notebook-style + citation templates
    │   └── generator.py        # LLM routing, vision, Self-RAG critique
    │
    ├── guardrails/
    │   ├── input_sanitizer.py  # Prompt injection protection
    │   └── pii_detector.py     # Presidio-based PII detection/redaction
    │
    ├── observability/
    │   └── tracing.py          # Langfuse v4 pipeline tracing (no-op if unconfigured)
    │
    └── evaluation/
        ├── judge.py            # LLM-as-judge scoring
        ├── metrics.py          # MRR, NDCG, Recall@k, RAGAS
        ├── test_questions.py   # 50 questions across 5 categories
        └── benchmarks/         # SQuAD, HotpotQA, NQ, MS MARCO, custom loaders
```

---

## Environment Variables

All config lives in `.env`. Copy `.env.example` to get started.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes* | — | Claude Haiku (CRAG/HyDE/judge) + Sonnet (generation) |
| `OPENAI_API_KEY` | Yes* | — | GPT-4o-mini (text) + GPT-4o (vision) — alternative to Anthropic |
| `POSTGRES_HOST` | No | `localhost` | DB host — use Supabase/Neon host for cloud |
| `POSTGRES_PORT` | No | `5432` | DB port |
| `POSTGRES_USER` | No | `raguser` | DB user |
| `POSTGRES_PASSWORD` | No | `ragpass` | DB password |
| `POSTGRES_DB` | No | `ragdb` | DB name |
| `POSTGRES_SSL` | No | `` | Set to `require` for cloud providers |
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse Cloud observability |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse Cloud observability |
| `USE_HYDE` | No | `true` | Enable/disable HyDE query expansion |
| `USE_QUERY_DECOMPOSITION` | No | `true` | Enable/disable multihop decomposition |
| `USE_CRAG` | No | `true` | Enable/disable CRAG chunk filtering |
| `USE_SELF_RAG` | No | `true` | Enable/disable Self-RAG critique |
| `PII_REDACTION_ENABLED` | No | `false` | Enable Presidio PII redaction |

*At least one of `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is required.

---

## Running the Evaluation

```bash
# Full 50-question benchmark
python -c "
import sys; sys.path.insert(0, '.')
from src.evaluation.benchmarks.runner import BenchmarkRunner
from src.evaluation.test_questions import QUESTIONS_BY_CATEGORY

samples = [{'question': q, 'category': c, 'ground_truth': '', 'doc_hint': ''}
           for c, qs in QUESTIONS_BY_CATEGORY.items() for q in qs]
runner = BenchmarkRunner()
runner.run('custom', samples, cleanup_after=False)
"
```

---

## Cost Estimates

| Item | Cost |
|---|---|
| Ingestion (3 PDFs, 2,528 chunks) | ~$1.29 (mostly image captioning) |
| Per query (text answer) | ~$0.022 |
| Per query (vision answer) | ~$0.025 |
| 50-question benchmark run | ~$1.10 |
| Embedding (all-MiniLM-L6-v2) | **$0** — local model |

---

## Deployment Options

| Mode | How | When to use |
|---|---|---|
| Local | `docker compose up -d` + `streamlit run app.py` | Development, personal use |
| Cloud DB | Point `POSTGRES_HOST` to Supabase/Neon, run app locally | Persistent shared DB |
| Full cloud | Containerise `app.py` + `api.py`, deploy alongside managed Postgres | Production, team access |

---

## Built On

Systematic experiments (01–10) covering chunking strategies, embedding models, vector stores, LLM comparisons, retrieval methods, reranking, and prompt variants. Each experiment result is referenced in the architecture decisions above.

Framework: custom Python pipeline (no LangChain runtime dependency for retrieval/generation — direct Anthropic/OpenAI SDK calls for predictable latency and cost).
