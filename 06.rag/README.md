# RAG — Retrieval-Augmented Generation

A deep-dive into building, benchmarking, and deploying RAG systems from first principles.
Every design decision is tested empirically — not taken from blog posts.

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

| What | Variants | Key Finding |
|---|---|---|
| Chunking strategies | 6 | Semantic chunking best faithfulness |
| Embedding models | 6 | `text-embedding-3-small` best quality/cost |
| Vector stores | 6 | FAISS fastest in-memory; Supabase best managed |
| LLMs | 4 | GPT-4o-mini best quality/cost ratio |
| Top-K retrieval | 5 values | k=5 optimal for this corpus |
| Retrieval methods | 4 | Hybrid (Dense+BM25) outperforms dense by ~15% |
| Re-ranking | Cross-encoder | +12% faithfulness with minimal latency cost |
| Prompt templates | 4 | Expert-persona + CoT scores highest |

[View Experiments →](./experiments/)

---

### 3. Projects — Production Deployment

**Nutrition RAG Chat** — Full-stack chat app. Ask questions about a 1,200-page nutrition textbook, get cited answers with page numbers.

```
Query → OpenAI embedding → Supabase pgvector → GPT-4o-mini → Cited answer [p. X]
```

[View Project →](./projects/nutrition-rag-chat/)

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
| Next.js API routes (TypeScript) | `projects/nutrition-rag-chat/app/api/` |
| Supabase pgvector + SQL RPC | `projects/nutrition-rag-chat/` |
| Production PDF ingestion pipeline | `projects/nutrition-rag-chat/ingest.py` |

## Tech Stack

**Python:** PyMuPDF · SentenceTransformers · FAISS · ChromaDB · Qdrant · LanceDB · RAGAS · tiktoken · spaCy · rank-bm25

**TypeScript / Next.js:** App Router · Server Components · API Routes · Tailwind CSS

**Cloud:** OpenAI (embeddings + chat) · Supabase pgvector · Anthropic Claude
