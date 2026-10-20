# RAG — Retrieval-Augmented Generation

A deep-dive into building, benchmarking, and deploying RAG systems from first principles.
Every design decision is tested empirically — not taken from blog posts.

## What's Inside

```
rag/
├── notebooks/       Learn  — build RAG from scratch, no frameworks
├── experiments/     Bench  — 10 systematic experiments, 40+ variants tested
└── projects/        Ship   — 2 production RAG systems
    ├── 1.nutrition-rag-chat   Full-stack chat app (Next.js + Supabase)
    └── 2.engineering-rag      Industrial multimodal RAG (Python + FastAPI + pgvector)
```

## The Learning Path

### 1. Notebooks — Understanding the Fundamentals
> *"I don't use a framework until I can build it without one."*

Built a complete RAG pipeline in raw Python:
- PDF parsing → sentence chunking → local embeddings → PyTorch cosine similarity → LLM generation
- No LangChain. No abstractions. Full visibility into what each step does.

[View Notebooks →](./notebooks/)

---

### 2. Experiments — Benchmarking Every Design Decision

Ran 10 systematic experiments on a 1,200-page nutrition textbook comparing:

| What | Variants | Key Finding |
|---|---|---|
| Chunking strategies | 6 | Fixed-512 scored highest (5.0); all strategies within 4.87–5.0 |
| Embedding models | 6 | Local `all-MiniLM-L6-v2` matched the top score with no API cost |
| Vector stores | 6 | FAISS and ChromaDB fastest (~160 ms average query) |
| LLMs | 4 | Claude Haiku had the lowest latency (4.7 s average) |
| Top-K retrieval | 5 values | k=1 too little; k=3 recovered most of the quality |
| Retrieval methods | 4 | HyDE scored highest; hybrid did not beat dense on this corpus |
| Re-ranking | Cross-encoder | No quality gain and added latency, so it was left out |
| Prompt templates | 4 | Simple prompts beat chain-of-thought and expert-persona |

[View Experiments →](./experiments/)

---

### 3. Projects — Production Deployment

#### Project 1: Nutrition RAG Chat
Full-stack chat app. Ask questions about a 1,200-page nutrition textbook, get cited answers with page numbers.

```
Query → OpenAI embedding → Supabase pgvector → GPT-4o-mini → Cited answer [p. X]
```

[View Project →](./projects/1.nutrition-rag-chat/)

---

#### Project 2: Engineering Knowledge Assistant — Industrial Multimodal RAG
Production RAG pipeline for industrial engineering documents. Handles text, tables, and images (diagrams, GHS safety labels, schematics) across PDF manuals, datasheets, and safety sheets.

**Benchmark: 3.87 / 5.0 (50 questions, Claude Haiku judge)**

```
PDF (text + tables + images)
    │
    ├── Semantic chunking (parent+child) + table Markdown + Haiku vision captions
    └── PostgreSQL + pgvector (2,500+ chunks)

User Query
    ├── Adaptive Router → simple queries answered directly (no retrieval)
    ├── Query Decomposer → multihop split into sub-questions
    ├── HyDE → short query expanded to hypothetical answer for better embeddings
    ├── Hybrid Search → pgvector dense + BM25, merged with RRF
    ├── CRAG → chunk relevance scoring, confidence level
    └── Claude Sonnet + Self-RAG → grounded answer with citations
```

Key features: Langfuse observability · OWASP security hardening · PII redaction · incremental indexing · FastAPI REST + Streamlit UI

[View Project →](./projects/2.engineering-rag/)  
[Pipeline Deep Dive →](./projects/2.engineering-rag/results/PIPELINE_DEEP_DIVE.md)

---

## Skills Demonstrated

| Skill | Where |
|---|---|
| RAG pipeline from scratch (no frameworks) | Notebooks |
| Embedding model benchmarking | `experiments/02_embeddings.py` |
| Vector store comparison | `experiments/03_vectorstores.py` |
| RAGAS + LLM-as-judge evaluation | `experiments/05_evaluation.py` |
| Hybrid retrieval (BM25 + Dense + RRF) | `experiments/08_retrieval_methods.py` |
| Cross-encoder re-ranking | `experiments/09_reranking.py` |
| Multimodal ingestion (text + tables + images) | `projects/2.engineering-rag/src/ingest/` |
| CRAG + Self-RAG quality verification | `projects/2.engineering-rag/src/retrieval/crag.py` |
| HyDE + query decomposition | `projects/2.engineering-rag/src/retrieval/` |
| Langfuse pipeline observability (v4 API) | `projects/2.engineering-rag/src/observability/` |
| FastAPI REST API + rate limiting | `projects/2.engineering-rag/api.py` |
| Next.js API routes (TypeScript) | `projects/1.nutrition-rag-chat/app/api/` |
| Supabase pgvector + SQL RPC | `projects/1.nutrition-rag-chat/` |

## Tech Stack

**Python:** Claude Sonnet/Haiku (Anthropic) · FastAPI · Streamlit · PyMuPDF · pdfplumber · SentenceTransformers · pgvector · rank-bm25 · Langfuse · Presidio · RAGAS

**TypeScript / Next.js:** App Router · Server Components · API Routes · Tailwind CSS

**Infrastructure:** PostgreSQL + pgvector · Supabase · Docker · OpenAI (embeddings + vision)
