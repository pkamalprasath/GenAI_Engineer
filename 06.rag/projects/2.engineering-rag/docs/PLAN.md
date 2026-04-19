# Engineering Knowledge Assistant — Industrial RAG Project

## Use Case

**Client**: A mid-size industrial manufacturing company (think: Siemens, ABB, or a process plant)

**Problem**: Their 200+ engineers spend 2-3 hours/day hunting through:
- Technical manuals (PDFs with schematics and diagrams)
- Safety Data Sheets (SDS/MSDS) with chemical property tables
- Equipment datasheets (spec tables, tolerance images)
- Maintenance & troubleshooting guides (step-by-step text + photos)
- Compliance/regulatory documents (ISO, OSHA, IEC standards)

**Pain Points**:
- Documents mix text, tables, and images — keyword search fails completely
- Engineers can't ask natural-language questions like "What is the torque spec for bolt M12 on the gearbox assembly?"
- Safety officers can't quickly cross-reference chemical exposure limits across hundreds of SDS sheets
- Critical information is locked inside scanned PDFs and images

**Solution**: A multimodal RAG system that understands text, tables, AND images — answering technical queries in under 3 seconds.

---

## What Makes This Project Industrial-Grade (vs. the Experiments)

The experiments used a single clean text PDF (human-nutrition-text.pdf).
This project adds:

| Dimension | Experiments | This Project |
|---|---|---|
| Document types | Plain text PDF | Text + Tables + Images + Scanned pages |
| Chunking | Single strategy | Multi-modal: text chunks + table records + image captions |
| Vectors | Single vector per chunk | Multi-vector: text + image embeddings in same store |
| Retrieval | Dense / BM25 / HyDE | HyDE + metadata filtering + table-aware retrieval |
| Generation | Text-only | Text + image context (GPT-4o multimodal) |
| Evaluation | LLM-as-judge | LLM judge + RAGAS + human eval checklist |
| Deployment | Scripts | FastAPI + Streamlit UI |

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │           DOCUMENT SOURCES           │
                    │  PDFs  │  Word  │  Images  │  Excel  │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │         INGESTION PIPELINE           │
                    │                                      │
                    │  ┌──────────┐  ┌──────────────────┐ │
                    │  │ Text     │  │ Table Extractor  │ │
                    │  │ Splitter │  │ (camelot/pdfplumber)│
                    │  └────┬─────┘  └───────┬──────────┘ │
                    │       │                │            │
                    │  ┌────▼─────┐  ┌───────▼──────────┐ │
                    │  │ Image    │  │ Table → Markdown  │ │
                    │  │ Extractor│  │ + Structured JSON │ │
                    │  └────┬─────┘  └───────┬──────────┘ │
                    │       │                │            │
                    │  ┌────▼──────────────────────────┐  │
                    │  │  GPT-4o Vision                │  │
                    │  │  → Image caption + description│  │
                    │  └────┬──────────────────────────┘  │
                    └───────┼────────────────────────────┘
                            │
                    ┌───────▼────────────────────────────┐
                    │        MULTI-VECTOR STORE           │
                    │  Chroma (dev) / Qdrant (prod)       │
                    │                                     │
                    │  Collection: text_chunks            │
                    │    → MiniLM-384 embeddings          │
                    │    → metadata: {source, page,       │
                    │                 doc_type, section}  │
                    │                                     │
                    │  Collection: table_records          │
                    │    → MiniLM-384 (table markdown)    │
                    │    → metadata: {table_id, caption}  │
                    │                                     │
                    │  Collection: image_summaries        │
                    │    → MiniLM-384 (vision caption)    │
                    │    → metadata: {image_path, page}   │
                    └───────┬────────────────────────────┘
                            │
                    ┌───────▼────────────────────────────┐
                    │       RETRIEVAL PIPELINE            │
                    │                                     │
                    │  1. Query → HyDE (generate          │
                    │     hypothetical doc with LLM)      │
                    │  2. Embed HyDE doc with MiniLM-384  │
                    │  3. Search all 3 collections        │
                    │  4. Metadata filter (doc_type,      │
                    │     date_range, department)         │
                    │  5. Reciprocal Rank Fusion           │
                    │     (merge results from 3 stores)   │
                    │  6. Top-5 across all modalities     │
                    └───────┬────────────────────────────┘
                            │
                    ┌───────▼────────────────────────────┐
                    │       GENERATION PIPELINE           │
                    │                                     │
                    │  Context = text chunks              │
                    │          + table markdown           │
                    │          + image captions           │
                    │          + actual image bytes       │
                    │             (if image retrieved)    │
                    │                                     │
                    │  LLM: GPT-4o-mini (text-only query) │
                    │       GPT-4o (if image in context)  │
                    │                                     │
                    │  Prompt: Notebook-style (P2 winner) │
                    │  + Source citation requirement      │
                    └───────┬────────────────────────────┘
                            │
                    ┌───────▼────────────────────────────┐
                    │         FASTAPI + STREAMLIT         │
                    │  POST /query → JSON answer          │
                    │  GET  /sources → cited docs         │
                    │  POST /ingest → add new docs        │
                    └────────────────────────────────────┘
```

---

## Experiment-Backed Design Decisions

### Chunking Strategy
- **Text**: Semantic chunking (score 5.0 in C4 sweep) — keeps related sentences together
- **Tables**: One Markdown block per table — never split a table row across chunks
- **Images**: One "chunk" per image = the GPT-4o generated caption (100-200 words)
- **Why not fixed-512?** Fixed-512 also scored 5.0 but semantic handles variable document structure better for engineering docs

### Embedding Model
- **Winner from experiments**: `all-MiniLM-L6-v2` (384-dim) — score 5.0, fastest
- All three modalities (text, tables, image captions) use the SAME embedding model
- This allows cross-modal retrieval: a text query can retrieve a relevant image caption

### Vector Store
- **Development**: Chroma (score 5.0, 3.15s ingest, zero setup)
- **Production**: Qdrant (score 4.933, supports payload filtering, distributed)
- Multi-collection approach instead of single collection — cleaner metadata, separate search budgets

### Retrieval Method
- **HyDE** (score 4.9) as primary — best quality in retrieval sweep
- **Why HyDE for engineering docs?** Queries like "torque spec M12 bolt" are short; HyDE expands them into full technical sentences before embedding, dramatically improving recall
- **RRF** (Reciprocal Rank Fusion) to merge text + table + image results without score normalization issues

### LLM
- **GPT-4o-mini** (score 4.933) — best score in LLM sweep AND cheapest
- **GPT-4o** only activated when an image is in the retrieved context (vision queries)
- Claude Haiku as fallback (score 4.6)

### Top-k
- **k=5 per collection** = up to 15 total candidates (text + tables + images)
- After RRF: final top-5 passed to LLM
- Experiment showed k=3 best latency/quality (4.8 @ 3.56s); k=5 more complete for multi-modal

### Prompt
- P2 Notebook-style (score 4.8) as base template
- Extended with: source citation requirement, table formatting instruction, confidence level

---

## Project Structure

```
engineering-rag/
├── PLAN.md                    ← this file
├── README.md
├── requirements.txt
├── .env.example
├── configs/
│   └── settings.py            ← all config in one place
├── src/
│   ├── ingest/
│   │   ├── document_parser.py ← PDF → text + tables + images
│   │   ├── chunker.py         ← semantic text chunks + table records
│   │   ├── image_captioner.py ← GPT-4o vision → text description
│   │   └── vectorstore.py     ← Chroma multi-collection manager
│   ├── retrieval/
│   │   ├── hyde.py            ← HyDE query expansion
│   │   ├── retriever.py       ← multi-collection search + RRF
│   │   └── filters.py         ← metadata filtering helpers
│   ├── generation/
│   │   ├── prompts.py         ← all prompt templates
│   │   └── generator.py       ← LLM caller (GPT-4o-mini / GPT-4o)
│   └── evaluation/
│       ├── judge.py           ← LLM-as-judge (same as experiments)
│       └── metrics.py         ← RAGAS integration
├── app.py                     ← Streamlit UI
├── api.py                     ← FastAPI server
├── ingest_docs.py             ← CLI: python ingest_docs.py data/
├── data/
│   └── sample_docs/           ← put test PDFs here
├── tests/
│   └── test_pipeline.py
└── notebooks/
    └── 00_explore.ipynb       ← interactive exploration
```

---

## Implementation Phases

### Phase 1 — Text-only RAG (1-2 days)
Apply everything learned from experiments. Baseline system that works.

1. `document_parser.py` — extract text from PDFs (PyPDFLoader)
2. `chunker.py` — semantic chunking (winner from C4 sweep)
3. `vectorstore.py` — Chroma with `text_chunks` collection
4. `retriever.py` — HyDE + dense search (winner from retrieval sweep)
5. `generator.py` — GPT-4o-mini with P2 prompt template
6. `app.py` — basic Streamlit chat interface
7. Test with 2-3 engineering PDFs

**Success metric**: Answers engineering questions correctly, cites page numbers

---

### Phase 2 — Table Intelligence (2-3 days)
The most critical gap for engineering docs — spec tables are everywhere.

1. `document_parser.py` — extend with `pdfplumber` table extraction
2. Tables → Markdown strings ("| Parameter | Value | Unit |")
3. New Chroma collection: `table_records`
4. `retriever.py` — search both collections, merge with RRF
5. Prompt update: tell LLM to format table data in answers

**Success metric**: "What is the max operating temperature of the XYZ pump?" retrieves spec table row correctly

---

### Phase 3 — Image/Diagram Understanding (3-4 days)
The most novel component — what separates this from your experiments.

1. `document_parser.py` — extract images from PDFs (PyMuPDF/fitz)
2. `image_captioner.py` — GPT-4o vision generates rich caption per image
3. New Chroma collection: `image_summaries` (stores caption + image path)
4. `retriever.py` — search 3 collections, include image bytes in context
5. `generator.py` — route to GPT-4o when image context present

**Success metric**: "Show me the wiring diagram for panel A3" retrieves correct image and describes it

---

### Phase 4 — API + Production Hardening (2-3 days)

1. `api.py` — FastAPI with `/query`, `/ingest`, `/health` endpoints
2. Incremental ingestion (only embed new/changed docs)
3. Response caching (Redis or in-memory for top queries)
4. Evaluation harness: 20 engineering questions with ground truth
5. `README.md` with setup guide

---

## Key Technical Challenges (and Solutions)

| Challenge | Solution |
|---|---|
| Tables get split by text chunker | Use pdfplumber to extract tables BEFORE text chunking, store separately |
| Image context too large for LLM | GPT-4o vision with image_url, not base64 in prompt text |
| Multi-collection RRF score normalization | Use rank positions (1/rank), not raw scores |
| HyDE adds latency | Cache HyDE expansions for repeated similar queries |
| Scanned PDFs (no text layer) | pytesseract OCR fallback |
| Same concept in text + table + image | RRF naturally handles this — all three can contribute |

---

## Evaluation Plan

**15 test questions per modality**:
- 5 text-only questions (from engineering manual text)
- 5 table-lookup questions ("What is the voltage rating of fuse F3?")
- 5 image/diagram questions ("What does the safety warning label on page 12 say?")

**Metrics** (same as experiments + more):
- LLM-as-judge: relevance, correctness, completeness (1-5)
- Latency: target < 3 seconds end-to-end
- Citation accuracy: does the cited page actually contain the answer?
- Hallucination rate: answers not supported by retrieved context

**Baseline comparison**: Plain text RAG (Phase 1) vs full multimodal RAG (Phase 3)

---

## Technology Stack

```python
# requirements.txt (grouped as per global CLAUDE.md)

# --- Core RAG ---
langchain
langchain-community
langchain-openai

# --- Document Parsing ---
pypdf                    # basic PDF text
pdfplumber               # table extraction
pymupdf                  # image extraction from PDF
pytesseract              # OCR fallback for scanned PDFs
pillow                   # image handling
unstructured             # universal document parser

# --- Embeddings ---
sentence-transformers    # all-MiniLM-L6-v2 (winner from experiments)
fastembed               # alternative fast inference

# --- Vector Store ---
chromadb                 # development (winner: score 5.0)
qdrant-client            # production option

# --- LLM ---
openai                   # GPT-4o-mini (winner) + GPT-4o (vision)
anthropic                # Claude Haiku fallback

# --- API + UI ---
fastapi
uvicorn
streamlit

# --- Evaluation ---
ragas                    # retrieval + generation metrics
pandas
```

---

## What You Will Learn Building This

1. **Multi-modal document parsing** — real PDFs are messy; tables and images need special treatment
2. **Multi-vector RAG** — different representations of the same doc in the same vector store
3. **HyDE in practice** — query expansion before embedding, not just theory
4. **Reciprocal Rank Fusion** — how to merge ranked lists from multiple sources without score issues
5. **Vision LLM integration** — when and how to use GPT-4o vs GPT-4o-mini based on context
6. **Production patterns** — FastAPI endpoint, incremental ingestion, caching
7. **Evaluation design** — writing test questions that expose real weaknesses, not just easy wins

This project covers everything from the case study (FinanceAI-style requirements) and implementation guide, grounded in your own experimental data about what actually works.
