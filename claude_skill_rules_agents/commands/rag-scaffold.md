Create a complete, working RAG (Retrieval-Augmented Generation) pipeline for the current project or a new project.

## Usage
/rag-scaffold [vector-store] [llm-provider]

Options:
- vector-store: `faiss` (default) | `chroma` | `pinecone`
- llm-provider: `openai` (default) | `groq` | `ollama` | `bedrock`

Parse options from $ARGUMENTS.

## What to Build

### Architecture to implement

```
Document(s)
    ↓
Loader (PyPDFLoader / WebBaseLoader / DirectoryLoader)
    ↓
RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    ↓
Embeddings (OpenAIEmbeddings / HuggingFaceEmbeddings)
    ↓
Vector Store (FAISS / Chroma / Pinecone)
    ↓
Retriever (.as_retriever(search_kwargs={"k": 4}))
    ↓
create_stuff_documents_chain(llm, prompt)
    ↓
create_retrieval_chain(retriever, document_chain)
    ↓
Answer (context-grounded)
```

### Create these files

**`rag_pipeline.py`** — core RAG logic as a reusable class:
```python
class RAGPipeline:
    def __init__(self, docs_path: str): ...
    def build(self): ...           # load → split → embed → store
    def query(self, question: str) -> dict: ...  # retrieve → generate
```

**`app.py`** — Streamlit UI wrapping the RAGPipeline:
- File upload or directory path input
- "Build Index" button (calls `pipeline.build()`)
- Question input
- Shows answer + source document chunks in expander

**`requirements.txt`** additions based on choices.

**`.env.example`** additions based on chosen providers.

### Key implementation rules
1. Cache vectorstore in `st.session_state` — never rebuild on every rerun
2. Use `create_retrieval_chain` + `create_stuff_documents_chain` (LCEL pattern)
3. Prompt must include `{context}` and `{input}` variables
4. Ground the LLM: "Answer ONLY from the provided context. If not in context, say 'I don't know'."
5. For FAISS: show how to use `save_local()` / `load_local()` for persistence
6. For Chroma: show how to use `persist_directory` for persistence

### Important notes to add as comments
- FAISS: in-memory by default, resets on restart unless `save_local()` used
- Chroma: persists to disk automatically if `persist_directory` set
- Scanned PDFs (image-only) have no extractable text — mention OCR limitation
- Only first 50 chunks used by default — configurable

### After creating files
Show the full implementation and explain:
1. Where to put source documents
2. How to run
3. How to switch vector stores or LLM providers
