# 📄 Conversational RAG with PDF Uploads & Chat History

A **Streamlit-based Conversational Retrieval-Augmented Generation (RAG)** application that allows users to upload PDF files and interact with their content using a Large Language Model (LLM).  
The app supports **multi-turn conversations**, **history-aware retrieval**, and **semantic search** over PDF content.

---

## 🚀 Features

- 📂 Upload one or more PDF files
- 🔍 Semantic search using vector embeddings
- 💬 Conversational Q&A with chat history
- 🧠 History-aware question rewriting for better retrieval
- ⚡ Fast inference using **Groq-hosted LLMs**
- 🗂️ Vector storage with **Chroma**
- 🧩 Modular LangChain-based architecture

---

## 🏗️ Architecture Overview

PDF Upload
↓
PyPDFLoader → Documents (per page)
↓
Text Splitter (chunking + overlap)
↓
Embeddings (HuggingFace)
↓
Chroma Vector Store
↓
Retriever
↓
History-Aware Question Rewriting
↓
Context Retrieval
↓
LLM Answer Generation
↓
Chat History Stored (per session)


---

## 🧠 Core Concepts Used

- **RAG (Retrieval-Augmented Generation)**  
  Combines document retrieval with LLM generation to reduce hallucinations.

- **History-Aware Retrieval**  
  Follow-up questions are rewritten into standalone queries using chat history.

- **Session-Based Memory**  
  Each session ID maintains an independent conversation history.

---

## 🛠️ Tech Stack

- **UI**: Streamlit  
- **LLM**: Groq (`llama-3.1-8b-instant`)  
- **Embeddings**: HuggingFace (`all-MiniLM-L6-v2`)  
- **Vector Store**: Chroma  
- **Framework**: LangChain  

---

## 📦 Project Structure

```text
app.py                # Main Streamlit application
.env                  # Environment variables (HF_TOKEN, etc.)
venv/                 # Virtual environment

Environment Variables

Create a .env file:
HF_TOKEN=your_huggingface_token
Groq API key is entered at runtime via the Streamlit UI.

1.How to Run

Create and activate a virtual environment

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate


2.Install dependencies

pip install streamlit langchain chromadb python-dotenv
pip install langchain-community langchain-groq langchain-huggingface


3.Run the app

streamlit run app.py


How It Works (Step-by-Step)
1. PDF Ingestion

Uploaded PDFs are written temporarily to disk.

PyPDFLoader extracts text page-by-page into LangChain Document objects.

2. Chunking

RecursiveCharacterTextSplitter breaks documents into overlapping chunks.

Overlap preserves semantic continuity.

3. Embeddings & Storage

Each chunk is embedded using HuggingFace embeddings.

Chunks + vectors are stored in Chroma for similarity search.

4. History-Aware Retrieval

User questions + chat history are rewritten into standalone queries.

This avoids ambiguity in follow-up questions (e.g., “What about that?”).

5. Answer Generation

Retrieved chunks are injected into the LLM prompt as {context}.

The LLM answers concisely using only retrieved content.

6. Chat History Management

Each session_id maps to a ChatMessageHistory.

Stored in st.session_state to survive Streamlit reruns.

🧾 Prompt Design Highlights

- Question Rewriting Prompt

- Converts conversational queries into standalone questions.

- Improves retrieval accuracy.

Answering Prompt

Forces grounding in retrieved context.

Limits responses to 3 sentences.

Explicitly allows “I don’t know” if context is missing.

⚠️ Known Limitations & Best Practices

Scanned PDFs

Image-only PDFs have no extractable text.

OCR is required for such documents.

Temporary File Handling

Current implementation overwrites temp.pdf.

For production, use unique temp files or tempfile.NamedTemporaryFile.

Performance

Vector store is rebuilt on every rerun.

Recommended: cache vectorstore in st.session_state.

