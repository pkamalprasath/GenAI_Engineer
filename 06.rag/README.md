# Retrieval-augmented generation (RAG)

**A multimodal RAG system for engineering PDFs, evaluated on 50 questions after every change (best run 3.87/5, Claude Haiku judge), plus a benchmark study of 35 completed configurations (38 attempted) across 8 sweeps that decided its design.**

| Folder | What it is | Type |
|---|---|---|
| [`projects/2.engineering-rag`](./projects/2.engineering-rag/) | Question answering over text, tables and diagrams in engineering PDFs. FastAPI, PostgreSQL + pgvector, Claude, Langfuse; five evaluation runs including a regression and its cause; 147 tests in CI. | **Flagship** |
| [`experiments`](./experiments/) | One design choice changed at a time (chunking, embeddings, vector stores, LLMs, top-k, retrieval method, re-ranking, prompts) on a 1,208-page textbook, scored by an LLM judge. Findings and limits stated from the CSVs. | Benchmark study |
| [`projects/1.nutrition-rag-chat`](./projects/1.nutrition-rag-chat/) | Next.js chat app over a nutrition textbook: OpenAI embeddings, Supabase pgvector, GPT-4o-mini, page citations. No tests. | Learning |
| [`notebooks`](./notebooks/) | RAG built step by step in plain Python (PDF parsing, chunking, local embeddings, PyTorch similarity search). | Learning |
| [`research-papers`](./research-papers/) | Reading notes on ten RAG papers (RAG, DPR, REALM, RETRO, ColBERT, CRAG, Adaptive-RAG, Self-RAG, agentic RAG, hybrid retrieval). | Learning |

Start with the engineering project's [results table](./projects/2.engineering-rag/README.md#results); [`PIPELINE_DEEP_DIVE.md`](./projects/2.engineering-rag/results/PIPELINE_DEEP_DIVE.md) has the per-run detail.

**How to read the numbers.** All quality scores come from an LLM judge, not from human raters. In the engineering project the judge changed after run 2, so compare runs 1–2 and runs 3–5 only within each group. In the benchmark study each sweep used 5–10 questions, so most differences are within judge noise, and its RAGAS columns were not computed.
