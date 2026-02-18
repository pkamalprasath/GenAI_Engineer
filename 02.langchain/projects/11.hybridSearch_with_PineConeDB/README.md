# Hybrid Search with PineconeDB (BM25 + Dense Vectors)

Experiments demonstrating hybrid search — combining keyword-based BM25 retrieval with semantic dense vector search — using Pinecone as the vector database.

## Overview

Pure semantic search (dense vectors) can miss exact keyword matches. Pure keyword search (BM25) misses semantic meaning. Hybrid search combines both for better retrieval quality, especially for technical and domain-specific queries.

## Architecture

```
User Query
    ↓
    ├── BM25 (keyword match)     → sparse vector scores
    └── Embeddings (semantic)    → dense vector scores
              ↓
    Reciprocal Rank Fusion (or weighted combination)
              ↓
    Top-K retrieved documents
              ↓
    LLM Answer Generation
```

## Tech Stack

| Component | Technology |
|---|---|
| Vector Database | Pinecone |
| Sparse Retrieval | BM25 (`rank_bm25`) |
| Dense Retrieval | Embeddings (sentence-transformers) |
| Framework | LangChain |
| Notebook | Jupyter |

## Project Structure

```
11.hybridSearch_with_PineConeDB/
├── experiments.ipynb
└── README.md
```

## Setup

```bash
# 1. Set your Pinecone API key
cp ../../.env.example .env
# Add PINECONE_API_KEY and PINECONE_ENV to .env

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Launch Jupyter
jupyter notebook experiments.ipynb
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `PINECONE_API_KEY` | Pinecone API access |
| `PINECONE_ENV` | Pinecone environment (e.g. `us-east-1-aws`) |

## Key Concepts

- **BM25** — term frequency/inverse document frequency keyword ranking
- **Dense vectors** — embedding-based semantic similarity
- **Hybrid search** — weighted combination of both scores improves retrieval for mixed query types
- **Pinecone** supports both sparse (BM25) and dense vectors in a single index
