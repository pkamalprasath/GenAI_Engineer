# PDF Query with LangChain (RAG over PDF)

A notebook-based RAG (Retrieval-Augmented Generation) pipeline for querying PDF documents using LangChain and a vector store.

## Overview

Demonstrates how to build an end-to-end pipeline that ingests a PDF, converts it into searchable vector embeddings, and answers natural language questions strictly from the document content.

## Architecture

```
PDF (budget_speech.pdf)
    ↓
PDF Loader (PyPDF / PyMuPDF)
    ↓
Text Chunking
    ↓
Embeddings
    ↓
Vector Store (ChromaDB / FAISS)
    ↓
Similarity Retriever
    ↓
LLM + Prompt (answer from context only)
    ↓
Answer
```

## Tech Stack

| Component | Technology |
|---|---|
| Document | `budget_speech.pdf` |
| Loader | PyPDF / LangChain document loaders |
| Embeddings | OpenAI / HuggingFace |
| Vector Store | ChromaDB or FAISS |
| Framework | LangChain |
| Notebook | Jupyter |

## Project Structure

```
PDFQuery_LangChain/
├── PDFQuery_LangChain.ipynb
├── budget_speech.pdf           # Sample document (Indian Budget Speech)
└── README.md
```

## Setup

```bash
# 1. Set API keys (from repo root)
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch Jupyter
jupyter notebook PDFQuery_LangChain.ipynb
```

## Key Concepts

- **PDF loading** — `PyPDFLoader` extracts text page-by-page into `Document` objects
- **Chunking** — `RecursiveCharacterTextSplitter` splits on paragraphs, sentences, then characters
- **Embeddings** — convert text chunks into numerical vectors for semantic search
- **Similarity search** — find the top-K most relevant chunks for the user's question
- **Stuff chain** — retrieved chunks are "stuffed" into the prompt context for the LLM to answer

## Sample Questions for `budget_speech.pdf`

- "What are the key highlights of the budget?"
- "What infrastructure investments were announced?"
- "What tax changes were proposed?"
