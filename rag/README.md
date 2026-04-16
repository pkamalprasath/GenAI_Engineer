# RAG — Retrieval-Augmented Generation

A deep-dive into building, benchmarking, and deploying RAG systems from first principles. Every design decision is tested empirically — not taken from blog posts.

## What's Inside

```
rag/
├── notebooks/       Learn  — build RAG from scratch, no frameworks
├── experiments/     Bench  — 10 systematic experiments, 40+ variants tested
└── projects/        Ship   — production RAG chat app (Next.js + Supabase)
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

| What | Variants | Metric |
|---|---|---|
| Chunking strategies | 6 (sentence, fixed, semantic, structural, LLM) | Faithfulness, chunk quality |
| Embedding models | 6 (local + OpenAI + Cohere) | Retrieval score, latency, cost |
| Vector stores | 6 (FAISS, ChromaDB, Qdrant, LanceDB, Weaviate, PyTorch) | Recall, query latency |
| LLMs | 4 (GPT-4o-mini, GPT-4o, Claude Haiku, Mistral) | RAGAS faithfulness + answer relevance |
| Top-K retrieval | 5 values (1 → 20) | Quality vs. context cost |
| Retrieval methods | 4 (Dense, BM25, Hybrid RRF, HyDE) | Recall, answer quality |
| Re-ranking | Cross-encoder vs. none | Faithfulness delta |
| Prompt templates | 4 variants | RAGAS scores |

**Key findings:**
- Hybrid retrieval (Dense + BM25 via RRF) outperforms pure dense by ~15% recall
- Cross-encoder re-ranking adds ~12% faithfulness with minimal latency cost
- `text-embedding-3-small` beats local models at 1/10th the memory footprint
- Expert-persona + chain-of-thought prompts consistently score highest on RAGAS

[View Experiments →](./experiments/)

---

### 3. Projects — Production Deployment

Applied everything learned into a deployable full-stack application:

**Nutrition RAG Chat** — Ask questions about a nutrition textbook, get cited answers with page numbers.

```
Query → OpenAI embedding → Supabase pgvector search → GPT-4o-mini → Cited answer
```

- Next.js 16 (App Router) frontend + API route
- Supabase pgvector with cosine similarity RPC
- Sentence-level chunking with overlap (1,158 chunks from 1,200 pages)
- Metadata filtering for multi-document support

[View Project →](./projects/nutrition-rag-chat/)

---

## Skills Demonstrated

| Skill | Where |
|---|---|
| RAG pipeline design from scratch | Notebooks |
| Embedding model evaluation | `experiments/02_embeddings.py` |
| Vector store benchmarking | `experiments/03_vectorstores.py` |
| RAGAS + LLM-as-judge evaluation | `experiments/05_evaluation.py` |
| Hybrid retrieval (BM25 + Dense + RRF) | `experiments/08_retrieval_methods.py` |
| Cross-encoder re-ranking | `experiments/09_reranking.py` |
| Next.js API routes (TypeScript) | `projects/nutrition-rag-chat/app/api/` |
| Supabase pgvector + SQL RPC | `projects/nutrition-rag-chat/` |
| Production PDF ingestion pipeline | `projects/nutrition-rag-chat/ingest.py` |

## Tech Stack

**Python:** PyMuPDF · SentenceTransformers · FAISS · ChromaDB · Qdrant · LanceDB · RAGAS · tiktoken · spaCy · rank-bm25

**TypeScript / Next.js:** App Router · Server Components · API Routes · Tailwind CSS

**Cloud:** OpenAI (embeddings + chat) · Supabase pgvector · Anthropic Claude
