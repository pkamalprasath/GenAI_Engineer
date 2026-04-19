# RAG Projects

Production-grade RAG applications built on top of the research done in the experiments module.

---

## 1. Nutrition RAG Chat
[View Project →](./1.nutrition-rag-chat/)

A full-stack chat application for querying a 1,200-page nutrition textbook with AI-powered, cited answers.

**What makes it production-ready:**
- Supabase pgvector — managed, scalable vector store with SQL-based similarity search
- Server-side API route — API keys never exposed to the browser
- Sentence-level chunking with overlap — preserves context at chunk boundaries
- Metadata filtering — architecture supports multi-document RAG
- Source citations — every answer includes page numbers from the original PDF
- GPT-4o-mini — cost-efficient generation with high quality

**Stack:** Next.js 16 · TypeScript · OpenAI · Supabase pgvector · Python ingestion

**Architecture:**
```
User Query
    │
Next.js API Route (/api/chat)
    │
    ├── OpenAI text-embedding-3-small  →  1536-dim query vector
    │
    ├── Supabase match_documents RPC   →  top-15 chunks (cosine similarity)
    │
    └── GPT-4o-mini                    →  cited answer with page numbers
```

---

## 2. Engineering Knowledge Assistant — Industrial Multimodal RAG
[View Project →](./2.engineering-rag/)

A production RAG pipeline for industrial engineering documents — PDF manuals, safety datasheets, and technical specifications. Handles text, tables, and images (diagrams, GHS labels, schematics).

**Benchmark results (50 questions, 5 evaluation runs):**

| Category | Best Score | Run |
|---|:---:|---|
| Text | **4.13** / 5.0 | Run 5 |
| Table | **4.30** / 5.0 | Run 4 |
| Image | **3.37** / 5.0 | Run 4 |
| Multihop | **3.27** / 5.0 | Run 4 |
| Unanswerable | **4.77** / 5.0 | Run 3 |
| **Overall best** | **3.87** / 5.0 | **Run 4** |

**What makes it production-ready:**
- Multimodal ingestion — text (semantic chunking), tables (Markdown), images (vision captions)
- Hybrid retrieval — pgvector dense + BM25 keyword, merged with Reciprocal Rank Fusion
- HyDE — short queries expanded into hypothetical answer paragraphs before embedding
- Query decomposition — multihop questions split into sub-questions, each retrieved separately
- CRAG — every retrieved chunk scored for relevance; noise filtered before generation
- Self-RAG — answer verified against context, one retry if not grounded
- Observability — full Langfuse Cloud traces per query (latency, tokens, CRAG scores)
- OWASP security — path traversal protection, rate limiting, input sanitization
- Incremental indexing — SHA-256 file hash; unchanged files skipped automatically

**Stack:** Python · FastAPI · Streamlit · Claude Sonnet/Haiku · PostgreSQL + pgvector · sentence-transformers (local)

**Architecture:**
```
PDF Documents (text + tables + images)
    │
    ├── pypdf → SemanticChunker (parent + child)
    ├── pdfplumber → 6-row Markdown table groups
    └── pymupdf → Claude Haiku vision caption
    │
    ▼
PostgreSQL + pgvector  (2,500+ chunks)
    │
User Query
    ├── Adaptive Router  (simple → answer direct, complex → full RAG)
    ├── Query Decomposer (multihop → up to 4 sub-questions)
    ├── HyDE             (query → hypothetical answer paragraph)
    ├── Hybrid Search    (dense + BM25 per chunk type, RRF merge)
    ├── CRAG             (relevance scoring → confidence level)
    └── Generator        (Claude Sonnet + Self-RAG critique)
    │
    ▼
Answer + citations + confidence level
```

See [`2.engineering-rag/results/PIPELINE_DEEP_DIVE.md`](./2.engineering-rag/results/PIPELINE_DEEP_DIVE.md) for the full per-run analysis, cost breakdown, and lessons learned.
