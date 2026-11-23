# RAG projects

| Project | What it is | Evidence |
|---|---|---|
| [2. Multimodal RAG for engineering documents](./2.engineering-rag/) (flagship) | Question answering over text, tables and diagrams in engineering PDFs. FastAPI, Streamlit, PostgreSQL + pgvector, Claude Sonnet and Haiku, query decomposition, corrective RAG, Langfuse tracing. | 50-question evaluation after every change; best run 3.87/5 (Claude Haiku judge); multi-hop 2.63 → 3.27 under the same judge; 147 tests in CI. See its [results table](./2.engineering-rag/README.md#results). |
| [1. Nutrition RAG chat](./1.nutrition-rag-chat/) (learning) | Next.js chat app over a nutrition textbook: OpenAI `text-embedding-3-small`, Supabase pgvector, GPT-4o-mini, answers with page citations. | Runs locally; no tests or evaluation. |

The design choices in project 2 were informed by the [benchmark study](../experiments/).
