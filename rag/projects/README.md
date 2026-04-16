# RAG Projects

Production-grade RAG applications built on top of the research done in the experiments module.

## Projects

### Nutrition RAG Chat
[View Project →](./nutrition-rag-chat/)

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
    |
Next.js API Route (/api/chat)
    |
    +-- OpenAI text-embedding-3-small  -->  1536-dim query vector
    |
    +-- Supabase match_documents RPC   -->  top-15 chunks (cosine similarity)
    |
    +-- GPT-4o-mini                    -->  cited answer with page numbers
```
