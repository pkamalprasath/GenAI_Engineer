# Notebooks — RAG Learning Journey

Step-by-step Jupyter notebooks that build a RAG system from scratch, without any high-level frameworks. Written to deeply understand what happens under the hood.

## Notebooks

| Notebook | What You'll Learn |
|---|---|
| `01_data_ingestion.ipynb` | Load a PDF, split into sentence chunks, generate embeddings with SentenceTransformer, build a local vector store with PyTorch tensors, run semantic search |
| `02_chunking_strategies.ipynb` | Compare fixed-size, sentence, semantic, and structural chunking — visualize chunk distributions and overlap |

## Stack

- **PDF parsing** — PyMuPDF (`fitz`)
- **Chunking** — regex sentence splitter + spaCy
- **Embeddings** — `all-mpnet-base-v2` via SentenceTransformers (local, no API key needed)
- **Vector store** — PyTorch tensors + `torch.topk` cosine similarity
- **Visualization** — matplotlib

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install pymupdf sentence-transformers torch matplotlib spacy jupyter
python -m spacy download en_core_web_sm
jupyter notebook
```

> The notebooks use `../data/human-nutrition-text.pdf` as the source document.
> Place any textbook-style PDF there to experiment with your own data.
