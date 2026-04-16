# Nutrition RAG Chat

A Retrieval-Augmented Generation (RAG) chat application built with Next.js, OpenAI, and Supabase. Ask questions about the Human Nutrition textbook and get cited, page-referenced answers.

## Architecture

```
User Query
    │
    ▼
Next.js API Route (/api/chat)
    │
    ├── OpenAI text-embedding-3-small  →  1536-dim query vector
    │
    ├── Supabase match_documents RPC   →  top-15 relevant chunks (cosine similarity)
    │
    └── GPT-4o-mini                    →  answer with [1], [2] citations + page numbers
```

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | Next.js 16 (App Router) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector Store | Supabase pgvector |
| LLM | OpenAI `gpt-4o-mini` |
| Ingestion | Python + PyMuPDF + tiktoken |

## Project Structure

```
rag-chat/
├── app/
│   ├── api/chat/route.ts   # RAG API endpoint
│   ├── layout.tsx
│   ├── page.tsx            # Chat UI
│   └── globals.css
├── ingest.py               # PDF → chunk → embed → Supabase
├── test_embeddings.py      # Probe Supabase retrieval
├── .env.example
└── package.json
```

## Setup

### 1. Supabase

Create a table and RPC function in your Supabase project:

```sql
create extension if not exists vector;

create table public.chunks (
  id bigserial primary key,
  doc_id text not null,
  chunk_index int not null,
  content text not null,
  metadata jsonb default '{}'::jsonb,
  embedding vector(1536)
);

create or replace function public.match_documents(
  query_embedding vector(1536),
  match_count int default 5,
  filter jsonb default '{}'::jsonb
)
returns table (id bigint, doc_id text, chunk_index int, content text, metadata jsonb, similarity float)
language plpgsql stable as $$
begin
  return query
  select c.id, c.doc_id, c.chunk_index, c.content, c.metadata,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.chunks c
  where (filter = '{}'::jsonb) or (c.metadata @> filter)
  order by c.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

### 2. Environment Variables

```bash
cp .env.example .env.local
# Fill in your keys in .env.local
```

### 3. Ingest the PDF

```bash
pip install pymupdf tiktoken supabase openai tqdm python-dotenv
python ingest.py
```

Place your `human-nutrition-text.pdf` in the `rag-chat/` directory before running.

### 4. Run the Web App

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key (secret) |
