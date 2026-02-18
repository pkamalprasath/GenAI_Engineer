# Research Paper Q&A using RAG (LangChain + FAISS + Groq + Streamlit)

A Retrieval-Augmented Generation (RAG) application that allows users to query PDF research papers and receive accurate, context-grounded answers using a Large Language Model.

## Overview

The system retrieves relevant document chunks using semantic search and generates responses strictly based on the retrieved context — reducing hallucinations by design.

## Architecture

```
PDF Documents
    ↓
PyPDFDirectoryLoader
    ↓
RecursiveCharacterTextSplitter (chunk_size=1000, overlap=100)
    ↓
OpenAIEmbeddings
    ↓
FAISS Vector Store (in-memory, session-cached)
    ↓
Similarity Retriever
    ↓
Groq LLM (LLaMA-3.1-8B-Instant) + Prompt
    ↓
Answer (context-grounded only)
```

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq (`llama-3.1-8b-instant`) |
| Framework | LangChain |
| Vector Store | FAISS (in-memory) |
| Embeddings | OpenAI Embeddings |
| Document Loader | `PyPDFDirectoryLoader` |

## Project Structure

```
3.QA_ChatBot_WithGroq/
├── app.py
├── research_papers/
│   ├── Attention.pdf
│   └── LLM.pdf
├── .env.example
└── README.md
```

## Setup

```bash
# 1. Copy and fill in your API keys
cp .env.example .env

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

## How to Use

1. Place PDF files inside `research_papers/`
2. Launch the app
3. Click **"Document Embedding"** to build the vector database
4. Enter a question about the research papers
5. Expand **"Document similarity search"** to inspect matched chunks

## Environment Variables

See [.env.example](.env.example).

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Embeddings (OpenAI) |
| `GROQ_API_KEY` | LLM inference (Groq) |
| `LANGCHAIN_API_KEY` | LangSmith tracing (optional) |

## Important Notes

- Vector store is built once per session and cached in `st.session_state`
- Only the first 50 document chunks are embedded (performance optimization)
- In-memory FAISS resets on app restart — add persistence with `save_local()` if needed
- LLM is prompted to answer **only from retrieved context** — it will not hallucinate beyond the documents

## Limitations

- Scanned (image-only) PDFs have no extractable text — OCR required
- In-memory vector store is not persistent across restarts
- Designed for demo/research use, not production-hardened
