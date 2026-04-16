# Notebooks — RAG from Scratch

Step-by-step Jupyter notebooks that build a complete RAG system without any high-level frameworks.
The goal: understand what happens at every step before abstracting it away.

## Notebooks

### 01 — Data Ingestion
`01_data_ingestion.ipynb`

Builds the full RAG pipeline from scratch:
- **PDF parsing** with PyMuPDF (`fitz`) — extract clean text page by page
- **Sentence chunking** — split into 10-sentence groups with 2-sentence overlap
- **Embedding** — `all-mpnet-base-v2` via SentenceTransformers (768-dim, runs locally)
- **Vector store** — PyTorch tensor store with `torch.topk` cosine similarity search
- **Retrieval** — semantic search returning top-k most relevant chunks
- **Generation** — LLM answer with retrieved context
- **Evaluation** — visualize retrieved pages from the source PDF

### 02 — Chunking Strategies
`02_chunking_strategies.ipynb`

Compares chunking approaches side by side:
- Fixed-size character windows
- Sentence-based chunking with overlap
- Semantic chunking (split where meaning changes)
- Structural chunking (paragraphs, sections)
- Chunk size distribution visualization

## Why No Frameworks?

LangChain and LlamaIndex abstract away the details. These notebooks implement every step manually so you can see:
- How embeddings are compared (dot product vs cosine)
- What "retrieval" actually looks like in memory
- Why chunk size matters for context quality
- How page metadata is preserved through the pipeline

## Stack

- `pymupdf` — PDF parsing
- `sentence-transformers` — local embeddings (no API key needed)
- `torch` — vector similarity search
- `matplotlib` — visualization
- `spacy` — sentence boundary detection

## Setup

```bash
pip install pymupdf sentence-transformers torch matplotlib spacy jupyter
python -m spacy download en_core_web_sm
jupyter notebook
```

Place your PDF at `../data/` before running.
