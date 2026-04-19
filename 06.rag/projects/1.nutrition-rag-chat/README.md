# Nutrition RAG Chat

A production-ready Retrieval-Augmented Generation chat application.
Ask any question about the Human Nutrition textbook and get a cited, page-referenced answer in seconds.

## Demo

> **Q:** What are water-soluble vitamins?
>
> **A:** Water-soluble vitamins dissolve in water and are not stored significantly in the body.
> The primary ones include Vitamin C [1] (p. 594) and the B-vitamin group — Thiamine, Riboflavin,
> Niacin, B6, B12, Folate, Biotin, and Pantothenic Acid [2] (p. 606)...

## Architecture

```
User Query
    |
    v
Next.js API Route  (/api/chat)
    |
    +-- OpenAI text-embedding-3-small  -->  1536-dim query vector
    |
    +-- Supabase match_documents RPC   -->  top-15 chunks by cosine similarity
    |
    +-- GPT-4o-mini                    -->  answer with [1],[2] citations + page numbers
    |
    v
Chat UI (Next.js App Router)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 App Router · Tailwind CSS |
| API | Next.js Route Handler (TypeScript) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Vector Store | Supabase pgvector (cosine similarity) |
| LLM | OpenAI `gpt-4o-mini` |
| Ingestion | Python · PyMuPDF · tiktoken |

## Project Structure

```
nutrition-rag-chat/
├── app/
│   ├── api/chat/route.ts   # RAG pipeline — embed, retrieve, generate
│   ├── page.tsx            # Chat UI
│   ├── layout.tsx
│   └── globals.css
├── ingest.py               # PDF -> chunks -> embeddings -> Supabase
├── test_embeddings.py      # Test retrieval quality against Supabase
├── .env.example            # Required environment variables
└── package.json
```

## Setup

### 1. Supabase — Create table and search function

Run this SQL in your Supabase project (SQL Editor):

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

create index on public.chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

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

### 2. Environment variables

```bash
cp .env.example .env.local
```

Edit `.env.local`:
```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

### 3. Ingest the PDF

Place `human-nutrition-text.pdf` in this directory, then:

```bash
pip install pymupdf tiktoken supabase openai tqdm python-dotenv
python ingest.py
```

This will chunk the PDF into ~1,158 pieces, embed each with OpenAI, and upload to Supabase.

### 4. Run the app

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

| Variable | Where to Get It |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_KEY` | Supabase Dashboard → Project Settings → API → service_role |
