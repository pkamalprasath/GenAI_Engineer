# Kamal Prasath — GenAI Engineer Portfolio

A structured, evidence-based portfolio of GenAI engineering — from NLP foundations to production-grade AI systems.
Every design decision is benchmarked, not assumed.

---

## Portfolio at a Glance

| Module | What I Built | Key Outcomes |
|---|---|---|
| [01. NLP Foundations](./01.nlp/) | Classical NLP → deep learning from scratch | Word2Vec, RNNs, ANNs — zero framework dependency |
| [02. LangChain](./02.langchain/) | 15+ LLM application patterns | LCEL chains, RAG, Agents, Tools, LangGraph flows |
| [03. Guardrails](./03.guardrails/) | AI safety & red-teaming | Prompt injection detection, hallucination scoring, Garak fuzzing |
| [04. Slack AI Agent](./04.open_claw_slack_bot/) | Production multi-tool agent | Memory, scheduler, MCP integration, 10+ tools |
| [05. Claude Patterns](./05.claude_skill_rules_agents/) | AI development workflow | Skills, rules, custom agent patterns |
| [RAG Deep-Dive](./06.rag/) | End-to-end RAG systems | 10 experiments + 2 production projects |

---

## Flagship: RAG Deep-Dive

The most comprehensive module — built systematically from first principles through production deployment.

### The Journey: Notebooks → Experiments → Production

**Step 1 — Notebooks:** Built RAG from scratch in raw Python. No LangChain, no abstractions. Direct embeddings, cosine similarity, LLM calls. Understand before you use.

**Step 2 — Experiments (10 systematic benchmarks):**  
Tested every major RAG design decision on a 1,200-page nutrition textbook:

| Experiment | What I Tested | Key Finding |
|---|---|---|
| Chunking | 6 strategies | Semantic chunking best faithfulness |
| Embeddings | 6 models | `all-MiniLM-L6-v2` best quality/cost |
| Vector stores | 6 options | pgvector best for SQL metadata filtering |
| LLMs | 4 models | GPT-4o-mini best quality/cost |
| Retrieval | 4 methods | Hybrid (Dense+BM25+RRF) outperforms dense |
| Re-ranking | Cross-encoder | +12% faithfulness, minimal latency cost |
| Prompt templates | 4 variants | P2 notebook-style + citations scores highest |

**Step 3 — Projects: Two Production Systems**

---

### Project 1: Nutrition RAG Chat
[View →](./06.rag/projects/1.nutrition-rag-chat/)

Full-stack chat app for a 1,200-page nutrition textbook. Every answer cites the source page.

**Stack:** Next.js 16 · TypeScript · OpenAI · Supabase pgvector

---

### Project 2: Engineering Knowledge Assistant — Industrial Multimodal RAG
[View →](./06.rag/projects/2.engineering-rag/) · [Pipeline Deep Dive →](./06.rag/projects/2.engineering-rag/results/PIPELINE_DEEP_DIVE.md)

The most complex project in this portfolio. A production RAG system for industrial engineering documents — handling text, tables, and images simultaneously.

**The problem it solves:**  
An engineer asks *"What torque for M12 bolts near the motor, and what PPE applies?"*  
The answer spans a spec table (torque value), a text procedure (installation steps), and an image caption (safety diagram). Standard RAG returns one or the other. This system retrieves all three and synthesises a cited answer.

**Benchmark: 3.87 / 5.0 — measured across 50 questions, 5 evaluation runs**

| Category | Best Score |
|---|:---:|
| Text retrieval | **4.13** / 5.0 |
| Table retrieval | **4.30** / 5.0 |
| Image retrieval | **3.37** / 5.0 |
| Multihop reasoning | **3.27** / 5.0 |
| Unanswerable (refusals) | **4.77** / 5.0 |

**What separates this from a tutorial RAG:**

| Feature | What it does |
|---|---|
| **Multimodal ingestion** | Text (semantic parent+child), tables (Markdown), images (vision captions) — all searchable |
| **Hybrid retrieval** | pgvector cosine + BM25 keyword, merged with Reciprocal Rank Fusion |
| **HyDE** | Short queries expanded to hypothetical answer paragraphs — improves embedding quality |
| **Query decomposition** | Multihop questions split into sub-questions, each retrieved independently |
| **CRAG** | Every chunk scored RELEVANT / AMBIGUOUS / IRRELEVANT — noise filtered before generation |
| **Self-RAG** | Answer verified against context after generation — one retry if not grounded |
| **Langfuse observability** | Full trace per query: latency per step, CRAG labels, token counts |
| **Adaptive routing** | Simple factual queries answered directly — no unnecessary retrieval |
| **Incremental indexing** | SHA-256 file hashing — only new/changed files are re-processed |
| **OWASP hardening** | Path traversal protection, rate limiting (30/min), input sanitization |

**What the 5 evaluation runs taught me:**

- Run 1→2 (+0.46): Contextual prefix on every chunk + BM25 hybrid search — biggest single improvement
- Run 3 (+0.06): Type-aware image caption prompt — images went from 2.7 → 3.3
- Run 4 (+0.22): Claude Sonnet generation + query decomposition — multihop +0.64
- Run 5 (−0.22): Three regressions identified and root-caused — Sonnet content filtering killed image coverage, 4-row table chunks too small for range queries, aggressive CRAG hurt multihop cross-document reasoning
- Run 6 DB: All regressions fixed — evaluation pending

**Stack:** Python · FastAPI · Streamlit · Claude Sonnet 4.6 · Claude Haiku · PostgreSQL + pgvector · sentence-transformers (local, no API)

---

## What This Portfolio Demonstrates

| Capability | Evidence |
|---|---|
| Systematic benchmarking | 10 experiments with controlled variables and measurable outcomes |
| Production architecture | FastAPI + OWASP security + rate limiting + observability |
| Multimodal AI | Text + table + image retrieval in a single unified pipeline |
| LLM evaluation | LLM-as-judge, RAGAS faithfulness, factuality scoring, 5 evaluation runs |
| Full-stack development | Next.js TypeScript app + Python API + Docker infrastructure |
| AI safety | Guardrails, PII redaction, prompt injection protection |
| Agent development | Multi-tool Slack agent with memory, scheduler, MCP server |

---

## Tech Stack

**LLMs & APIs:** Claude Sonnet/Haiku (Anthropic) · GPT-4o/GPT-4o-mini (OpenAI) · Ollama · AWS Bedrock · Groq · HuggingFace

**RAG & Retrieval:** pgvector · ChromaDB · FAISS · Qdrant · LanceDB · rank-bm25 · sentence-transformers · RAGAS · Langfuse

**Frameworks:** LangChain · LangGraph · FastAPI · Streamlit · Slack Bolt · Next.js

**AI Safety:** Guardrails AI · NeMo Guardrails · Garak · Presidio (PII)

**Languages:** Python · TypeScript

**Infrastructure:** PostgreSQL · Docker · Supabase · SQLite · Neo4j

---

> Built to understand the internals — not just call the APIs.
> Every number in this portfolio came from running the code.
