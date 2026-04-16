# Projects

End-to-end RAG applications built on top of the experiments and learning in this repo.

## Projects

| Project | Stack | Description |
|---|---|---|
| [nutrition-rag-chat](./nutrition-rag-chat/) | Next.js · OpenAI · Supabase pgvector | Full-stack chat app — ask questions about a nutrition textbook, get cited answers with page references |

## What Makes These Production-Ready

- **Supabase pgvector** — managed vector store with cosine similarity search via SQL RPC
- **OpenAI `text-embedding-3-small`** — 1536-dim embeddings, better than local models at a fraction of the cost
- **GPT-4o-mini** — fast, cheap generation with strict RAG prompting
- **Next.js App Router** — streaming-ready API routes, server-side env var protection
- **Sentence-level chunking with overlap** — preserves context across chunk boundaries
- **Metadata filtering** — multi-document support via `doc_id` and `source` fields
