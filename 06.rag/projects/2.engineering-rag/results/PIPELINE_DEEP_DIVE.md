# Pipeline Deep Dive — Engineering RAG System
## Architecture · Models · Per-Run Scores · Cost Analysis · Lessons Learned (5 Evaluation Runs)

---

## System Pipeline Overview

```
PDF File
   │
   ├─► Text  ──► pypdf (PyPDFLoader) ──► SemanticChunker (all-MiniLM-L6-v2, local)
   ├─► Tables ──► pdfplumber (grid-aware) ──► Markdown rows, split every 6 rows
   └─► Images ──► pymupdf get_images() ──► Vision LLM caption ──► text chunk
         └─► fallback: full-page PNG render @ 150 DPI (for vector GHS graphics)
   │
   ▼
Contextual prefix added to ALL chunks before embedding:
  "[filename — section heading, p.N]\n<chunk content>"
   │
   ▼
Embedding: all-MiniLM-L6-v2 (384-dim, local sentence-transformers, no API)
   │
   ▼
Storage: PostgreSQL + pgvector (Supabase, IVFFlat index, probes=10 for filtered queries)
```

**At query time:**
```
User query
   │
   ├─► Query Decomposition: Claude Haiku breaks multihop into up to 4 sub-questions
   ├─► HyDE: Haiku expands each sub-query into hypothetical answer paragraph
   ├─► Hybrid search: pgvector (cosine ANN) + BM25 (exact term), merged via RRF
   │     └─► 8 text + 8 table + 8 image chunks retrieved per sub-query
   ├─► SDS boost: extra targeted search on doc_type="sds" for safety keywords
   ├─► CRAG: Haiku scores all chunks in one call (RELEVANT / AMBIGUOUS / IRRELEVANT)
   │     └─► Multihop: keep ambiguous (bridging context needed)
   │     └─► Single-hop: drop ambiguous when relevant exist
   ├─► Generator: Claude Sonnet produces answer with citations + confidence
   │     └─► Each chunk labelled with which sub-query it answers
   └─► Self-RAG: Haiku critiques own answer (SUPPORTED / PARTIALLY / NOT_SUPPORTED)
                 → 1 retry if NOT_SUPPORTED
```

---

## Token Flow Architecture — How Each Content Type Travels Through the Pipeline

### PHASE 1: INGESTION (one-time, when PDF arrives)

```
                        PDF FILE
                           │
                    document_parser.py
                    ┌──────┴──────┐
                    │  3 extractors│
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
        pypdf           pdfplumber       pymupdf
      (text)            (tables)        (images)
           │               │               │
    raw text blocks   markdown rows    raw PNG/JPEG bytes
    "Bolt M12 must    | Bolt | Nm |     [b'\xff\xd8\xff...']
     be torqued..."   | M12  | 85 |
           │               │               │
           ▼               ▼               ▼
    ─────────────────────────────────────────────────────
                         chunker.py
    ─────────────────────────────────────────────────────
           │               │               │
           ▼               ▼               ▼

  ┌──────────────┐   ┌────────────┐   ┌────────────────────┐
  │SemanticChunker│   │Split every │   │ image_captioner.py │
  │(local MiniLM │   │ 6 rows,    │   │                    │
  │ embeddings,  │   │ repeat hdr │   │  Claude Haiku      │
  │ no API cost) │   │ in each    │   │  vision call       │
  │              │   │ group      │   │  (type-aware prompt│
  │PARENT chunk  │   │            │   │   + few-shot eg.)  │
  │(threshold=75)│   │            │   │                    │
  │              │   │            │   │ "Bearing housing   │
  │CHILD chunk   │   │            │   │  assembly. (1)     │
  │(threshold=95)│   │            │   │  Outer bearing ring│
  │smaller, more │   │            │   │  top-right, bolted │
  │precise       │   │            │   │  with 4×M8 bolts.."│
  └──────┬───────┘   └─────┬──────┘   └─────────┬──────────┘
         │                 │                     │
         ▼                 ▼                     ▼
  ┌──────────────────────────────────────────────────────┐
  │   Add context prefix to EVERY chunk before embedding │
  │   "[gearbox_manual.pdf — Section X, p.47]"           │
  │   → anchors embedding to engineering domain          │
  │   → same prefix used for child, parent, table, image │
  └──────────────────────────────────────────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
  {content: child,   {content: tbl,       {content: caption,
   parent_content:    chunk_type:          chunk_type:
    parent text,      "table",             "image",
   chunk_type:        page: 23,            image_path:
    "text",           section: "..."}       "page5_img2.png"}
   page: 47}
         │                 │                     │
         └─────────────────┴─────────────────────┘
                           │
                           ▼
              SentenceTransformer.encode()
              "all-MiniLM-L6-v2" (384-dim)
              Converts text → [0.12, -0.34, ...]
                           │
                           ▼
              ┌─────────────────────────┐
              │   PostgreSQL + pgvector  │
              │   (Supabase)             │
              │  id | content | embed.. │
              │   1 | [text]  | [384]   │
              │   2 | [table] | [384]   │
              │   3 | [image] | [384]   │
              └─────────────────────────┘
```

**Best module per data type — ingestion:**

| Data Type | Best Extractor | Best Chunker | Best Caption Model | Why |
|---|---|---|---|---|
| **Text** | pypdf | SemanticChunker (parent+child, threshold 75/95) | — | Parent gives LLM rich context; child gives precise retrieval |
| **Table** | pdfplumber | 6-row groups with header repeated | — | Specific enough per lookup; large enough for range queries |
| **Image** | pymupdf + full-page PNG fallback | One chunk = one caption | Claude Haiku | Haiku: less strict content filtering than Sonnet, covers all diagrams |

---

### PHASE 2: RETRIEVAL (every query)

```
USER QUERY: "What torque and safety gear for M12 bolt near motor?"
                           │
                           ▼
              ┌────────────────────────┐
              │  adaptive_router.py    │
              │  SIMPLE → answer direct│
              │  COMPLEX → full RAG    │
              └────────────┬───────────┘
                  COMPLEX  │
                           ▼
              ┌────────────────────────────┐
              │  query_decomposer.py       │ ← Run 4/5
              │  Claude Haiku              │
              │  Up to 4 sub-questions:    │
              │   1. "torque spec M12"     │
              │   2. "PPE near motor"      │
              │   3. "bolt grade standard" │
              └────────────┬───────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
    sub-query 1                     sub-query 2
           │                               │
           ▼                               ▼
   hyde.py (Haiku)                hyde.py (Haiku)
   Hypothetical answer             Hypothetical answer
   "M12 bolts grade 8.8            "PPE includes insulated
    require 85 Nm dry..."           gloves, lockout required"
           │                               │
           ▼                               ▼
   MiniLM embed →                  MiniLM embed →
   384-dim vector                  384-dim vector
           │                               │
           └───────────────┬───────────────┘
                           ▼
          ┌──────────────────────────────────┐
          │  3 pgvector searches per sub-query│
          │  chunk_type = "text"  → top 8    │
          │  chunk_type = "table" → top 8    │
          │  chunk_type = "image" → top 8    │
          │  = 48 candidates total            │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │  SDS Section Boost (Run 5)        │
          │  If query has safety keywords     │
          │  (ppe, hazard, first aid, ghs...) │
          │  → extra search on doc_type="sds" │
          │  → appended to ranked lists       │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │  BM25 keyword search             │
          │  Numbers get 2× token weight:    │
          │  "85" → ["85","85"] in corpus    │
          │  Catches "DIN EN 13463-1","T4"   │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │  Reciprocal Rank Fusion (RRF)    │
          │  score = 1 / (rank + 60)         │
          │                                  │
          │  Merges up to 9 ranked lists:    │
          │  (3 dense + 1 BM25) × sub-queries│
          │  + SDS boost list                │
          │                                  │
          │  Each chunk tagged:              │
          │  sub_query = "torque spec M12"   │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │  crag.py  — quality filter        │
          │  Claude Haiku scores each chunk  │
          │                                  │
          │  Single-hop query:               │
          │   RELEVANT  → kept ✅            │
          │   AMBIGUOUS → dropped ❌         │
          │   IRRELEVANT→ dropped ❌         │
          │                                  │
          │  Multihop query:                 │
          │   RELEVANT  → kept ✅            │
          │   AMBIGUOUS → kept ✅ (bridging) │
          │   IRRELEVANT→ dropped ❌         │
          └────────────────┬─────────────────┘
                           │
                    top 6 filtered chunks
```

**Best module per data type — retrieval:**

| Data Type | Best Retrieval Signal | Why |
|---|---|---|
| **Text** | Semantic (HyDE expanded query) + BM25 | HyDE bridges vocabulary gap; BM25 catches exact technical terms |
| **Table** | BM25 with 2× numeric boost + semantic | Numeric values like "85 ksi", "1.75 mm" are unique identifiers — BM25 catches them exactly |
| **Image** | Semantic on caption text | Captions written in natural language — semantic similarity matches question vocabulary |

---

### PHASE 3: GENERATION (every query)

```
   6 chunks + confidence level + sub_query labels
                      │
                      ▼
   ┌──────────────────────────────────────────┐
   │  generator.py                             │
   │  Has image chunks?                        │
   │    YES → include image_path bytes too    │
   │    NO  → text/table only                 │
   └─────────────────┬────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────┐
   │  prompts.py  build_rag_prompt()           │
   │                                           │
   │  For each chunk:                          │
   │   text  → uses parent_content (large)    │ ← Run 4 (fuller context)
   │   table → full markdown table            │
   │   image → caption text + image bytes     │
   │                                           │
   │  Sub-query synthesis block:              │ ← Run 5
   │  "This question was decomposed into:     │
   │   1. torque spec M12                     │
   │   2. PPE near motor                      │
   │   Synthesise all sub-answers."           │
   │                                           │
   │  Chunk label shown to LLM:              │
   │  "[Context 2 — TABLE | Answers: 'torque  │
   │   spec M12' | from manual, p.47]"        │
   │                                           │
   │  P2 Notebook-style prompt:               │
   │  "Extract passages first, then answer.   │
   │   Cite (Source, Page X). Confidence."    │
   └─────────────────┬────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────┐
   │  Claude Sonnet 4.6 (TEXT_LLM_STRONG)     │ ← Run 4 (was Haiku)
   │                                           │
   │  "M12 bolt torque: 85 Nm                 │
   │   (Source: gearbox_manual, p.47)         │
   │   Safety: insulated gloves, lockout      │
   │   required per ATEX zone rules           │
   │   (Source: safety_manual, p.12)          │
   │   Confidence: HIGH"                      │
   └─────────────────┬────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────┐
   │  Self-RAG critique                        │
   │  Claude Haiku (TEXT_LLM_FAST)            │
   │  SUPPORTED     → emit answer             │
   │  PARTIAL       → add caveat              │
   │  NOT_SUPPORTED → retry once              │
   └─────────────────┬────────────────────────┘
                     │
                     ▼
              FINAL ANSWER TO USER
```

**Best module per data type — generation:**

| Data Type | What LLM Sees | Generation Model | Why |
|---|---|---|---|
| **Text** | parent_content (large semantic section) | Claude Sonnet | Parent gives full procedure/section context; Sonnet synthesises multi-step answers |
| **Table** | Full markdown table with header | Claude Sonnet | Markdown table format lets Sonnet read exact row/column values; re-formats as table in answer |
| **Image** | Caption text + actual image bytes (if vision call) | Claude Sonnet (vision) | Caption handles retrieval; image bytes let Sonnet re-verify spatial details at generation |

---

### Per-Type Summary (Best Configuration — after Run 5 analysis)

| | TEXT | TABLE | IMAGE |
|---|---|---|---|
| **Extracted by** | pypdf | pdfplumber | pymupdf + full-page PNG fallback |
| **Chunked by** | SemanticChunker parent+child (75/95 threshold) | 6-row groups, header repeated | One chunk = one caption |
| **What's embedded** | child chunk (small, precise) | full table group markdown | Claude Haiku caption text |
| **What LLM sees** | parent chunk (larger context) | full table group markdown | caption text + image bytes |
| **Caption model** | — | — | **Claude Haiku** (less content filtering, better coverage) |
| **Retrieval signal** | semantic (HyDE) + BM25 | semantic + BM25 (2× numeric weight) | semantic on caption text |
| **CRAG (single-hop)** | keep RELEVANT only | keep RELEVANT only | keep RELEVANT only |
| **CRAG (multihop)** | keep RELEVANT + AMBIGUOUS | keep RELEVANT + AMBIGUOUS | keep RELEVANT + AMBIGUOUS |
| **Generation model** | Sonnet (text) | Sonnet (text) | Sonnet (vision) |
| **Special boost** | SDS keyword → extra sds search | — | — |

---

## Models Used Per Run

| Component | Run 1 & 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|
| Embedding | all-MiniLM-L6-v2 (local) | all-MiniLM-L6-v2 (local) | all-MiniLM-L6-v2 (local) | all-MiniLM-L6-v2 (local) |
| SemanticChunker | OpenAIEmbeddings (bug!) | HuggingFaceEmbeddings (fixed) | HuggingFaceEmbeddings | HuggingFaceEmbeddings |
| Image captioning | GPT-4o vision | Claude Haiku | Claude Haiku | Claude Sonnet → **reverted to Haiku** |
| Query decomposition | — | — | Claude Haiku (2–3 sub-q) | Claude Haiku (up to 4 sub-q) |
| HyDE expansion | gpt-4o-mini | Claude Haiku | Claude Haiku | Claude Haiku |
| CRAG scoring | gpt-4o-mini | Claude Haiku | Claude Haiku | Claude Haiku |
| Answer generation | gpt-4o-mini | Claude Haiku | **Claude Sonnet** | Claude Sonnet |
| Self-RAG critique | gpt-4o-mini | Claude Haiku | Claude Haiku | Claude Haiku |
| Judge (evaluation) | gpt-4o-mini | Claude Haiku | Claude Haiku | Claude Haiku |

> Run 5 tried Claude Sonnet for image captioning — reverted due to stricter content filtering (102 chunks vs 359 with Haiku). Haiku is the better choice for engineering image coverage.

---

## Overall Scores Across All Runs

| Category | Run 1 | Run 2 | Run 3 | Run 4 | **Run 5** | Target |
|---|---|---|---|---|---|---|
| text | 3.30 | 3.77 | 3.43 | 3.67 | **4.13** ✅ | 4.5 |
| table | 3.30 | 4.20* | 4.10 | **4.30** ✅ | 3.93 | 4.5 |
| image | 2.70 | 2.77 | 3.30 | **3.37** ✅ | 2.53 | 4.5 |
| multihop | 2.00 | 3.73 | 2.63 | **3.27** ✅ | 3.00 | 4.5 |
| unanswerable | 4.40 | 4.23 | 4.77 | **4.73** ✅ | 4.67 | 4.5 |
| **Overall** | **3.13** | **3.59** | **3.65** | **3.87** 🏆 | **3.65** | **4.5** |

**Run 6 DB prepared but not yet evaluated** (2,528 chunks — 1,262 text + 895 table + 371 image).  
Run 6 applies: adaptive CRAG (keep AMBIGUOUS for multihop), TABLE_CHUNK_ROWS=6 restored, Haiku captioner restored.

*Table Run 2 was 3.47 before fixing 4 questions that referenced content not in the PDFs; 4.20 after.  
All runs use Claude Haiku as judge for fair comparison. Runs 4/5 use Claude Sonnet for generation.

**Chunk counts per run:**

| Run | Text | Table | Image | Total | Key Change |
|---|---|---|---|---|---|
| Run 1 | 185 | 554 | 18 | 757 | Fixed-size chunks, no image rendering |
| Run 2 | 185 | 743 | 344 | 1272 | Full-page PNG render for SDS vector graphics |
| Run 3 | 192 | 743 | 354 | 1289 | Claude Haiku captions, local HuggingFace chunker |
| Run 4 | 1262 | 743 | 359 | 2364 | Parent-child text chunking (child+parent both stored) |
| Run 5 | 1262 | 895 | 102 | 2259 | TABLE_CHUNK_ROWS 6→4 (more chunks); Sonnet filtering lost images |
| **Run 6 (DB ready)** | **1262** | **895** | **371** | **2528** | Haiku captioner restored; TABLE_CHUNK_ROWS=6 restored; adaptive CRAG (not yet evaluated) |

---

## Cost, Token Usage, and API Calls Per Run

### Ingestion Cost (one-time per run)

| Item | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|
| Images captioned | 18 | 344 | 354 | 359 | 102 successful (257 filtered/skipped) |
| Vision model | GPT-4o | GPT-4o | Claude Haiku | Claude Haiku | **Claude Sonnet** |
| Caption tokens in (est.) | ~36K | ~688K | ~708K | ~718K | ~204K |
| Caption tokens out (est.) | ~9K | ~172K | ~177K | ~180K | ~61K |
| Approx image cost | ~$0.18 | ~$3.50 | ~$1.29 | ~$1.29 | ~$0.80 |
| SemanticChunker API cost | ~$0.50 (OpenAI bug) | ~$0.50 (OpenAI bug) | $0 (local) | $0 (local) | $0 (local) |
| Ingestion time | ~10 min | ~25 min | ~30 min | ~51 min | **~37 min (2200s)** |
| **Total ingestion cost** | **~$0.68** | **~$4.00** | **~$1.29** | **~$1.29** | **~$0.80** |

> Run 5 ingestion cheaper than Run 4 because Sonnet content filtering rejected 257 images (no API cost for rejected calls), reducing total calls from 359 to 102.

### Per-Query API Calls and Tokens (Run 5 configuration)

| Pipeline Stage | Model | Calls/query | Input tokens | Output tokens | Cost/query |
|---|---|---|---|---|---|
| Query decomposition | Claude Haiku | 1 | ~200 | ~100 | ~$0.00004 |
| HyDE expansion | Claude Haiku | 1–4 (per sub-q) | ~300 | ~120 | ~$0.00010 |
| pgvector search | DB (no API) | 3–12 | — | — | $0 |
| BM25 rerank | Local (no API) | 1 | — | — | $0 |
| SDS boost search | DB (no API) | 0–1 | — | — | $0 |
| CRAG batch scoring | Claude Haiku | 1 | ~2,000 | ~100 | ~$0.00045 |
| Answer generation | Claude Sonnet | 1 | ~4,000 | ~500 | ~$0.02100 |
| Answer generation (vision) | Claude Sonnet | 1 | ~4,000 + image | ~500 | ~$0.02500 |
| Self-RAG critique | Claude Haiku | 1 | ~4,500 | ~20 | ~$0.00092 |
| Judge (eval only) | Claude Haiku | 1 | ~1,500 | ~50 | ~$0.00028 |
| **Total per query** | | **7–9 calls** | **~12,500** | **~890** | **~$0.022** |

### Benchmark Cost (50 questions per run)

| Item | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|
| LLM calls per query | 8 | 5 (batch CRAG) | 5 | 7 (decomp added) | 7–9 |
| Total LLM calls (50 q) | 400 | 250 | 250 | 350 | 400 |
| Est. input tokens (total) | ~420K | ~270K | ~270K | ~450K | ~625K |
| Est. output tokens (total) | ~50K | ~30K | ~30K | ~45K | ~45K |
| Generation model | gpt-4o-mini | gpt-4o-mini | Claude Haiku | Claude Sonnet | Claude Sonnet |
| Judge model | gpt-4o-mini | gpt-4o-mini | Claude Haiku | Claude Haiku | Claude Haiku |
| **Benchmark cost (est.)** | **~$0.09** | **~$0.06** | **~$0.34** | **~$1.10** | **~$1.10** |
| Benchmark time | — | — | — | 1065s (17.8 min) | **1073s (17.9 min)** |
| Avg latency / query | 15.0s | ~8s | ~5s | 21.3s | **21.5s** |

### Score vs Cost Summary

| Run | Score | Score Δ | Ingestion cost | Cost/query | Avg latency | Notable change |
|---|---|---|---|---|---|---|
| Run 1 | 3.13 | baseline | ~$0.68 | ~$0.005 | 15.0s | Initial pipeline |
| Run 2 | 3.59 | +0.46 | ~$4.00 | ~$0.005 | ~8s | Contextual retrieval + BM25 + GHS render |
| Run 3 | 3.65 | +0.06 | ~$1.29 | ~$0.014 | ~5s | Claude migration + type-aware caption prompt |
| Run 4 | 3.87 | +0.22 | ~$1.29 | ~$0.022 | 21.3s | Sonnet gen + query decomposition + parent-child |
| **Run 5** | **3.65** | **-0.22** | **~$0.80** | **~$0.022** | **21.5s** | CRAG/table/image regressions identified |

---

## Per-Category Deep Dive Across 5 Runs

### Image Questions

| Image Type | R1 | R2 | R3 | R4 | R5 | Best / Why |
|---|---|---|---|---|---|---|
| ATEX nameplate / equipment label | 2.0 | 4.7 | 5.0 | 5.0 | 5.0 | R3: type-aware prompt reads label text correctly |
| Screw thread / spec diagram | 2.0 | 3.5 | 4.3 | 4.3 | 4.0 | R3: prompt extracts standard, dimensions, tolerances |
| GHS / hazard communication label | 1.5 | 2.0 | 3.7 | 3.7 | 1.3 | R5 regressed — Sonnet filtered this image entirely |
| Cross-section assembly diagram | 1.0 | 1.5 | 1.7 | 2.0 | 2.0 | Slow improvement — few-shot example in Run 5 helps slightly |
| Tolerance zone diagram | 2.0 | 2.5 | 3.7 | 3.7 | 2.7 | R5 regressed — Sonnet content filtering |
| Alignment diagram (spatial) | 1.5 | 2.0 | 2.3 | 2.3 | 1.3 | Still weak — spatial relationships hard to describe |
| Warning label | 1.0 | 1.3 | 1.3 | 1.3 | 1.3 | No improvement across all runs |
| ATEX nameplate symbol | 3.0 | 4.0 | 4.7 | 4.7 | 4.7 | Stable best performer |

**Image captioner model comparison:**

| Model | Images captured (of 359) | Avg image score | Content filtering | Cost/image |
|---|---|---|---|---|
| GPT-4o (Run 1/2) | 344 / 344 | 2.77 | Low | ~$0.004 |
| Claude Haiku (Run 3/4) | 354 / 359 | 3.30 / 3.37 | Low | ~$0.002 |
| Claude Sonnet (Run 5) | 102 / 359 | 2.53 | **High — 257 filtered** | ~$0.008 |
| **→ Best: Claude Haiku** | ✅ | ✅ best coverage | ✅ | ✅ cheapest |

**Caption prompt evolution:**

| Version | Style | Key Addition | Score Impact |
|---|---|---|---|
| Run 1/2 | Generic: "describe the image" | None | 2.70 |
| Run 3 | Type-aware: separate instructions per image type | GHS symbol names, component enumeration | +0.60 |
| Run 4 | Type-aware + spatial relationships instruction | left/right/above/below/connected-to | +0.07 |
| Run 5 | Type-aware + spatial + few-shot example | Detailed bearing housing example | +0.06 (Sonnet filtering negated gains) |

---

### Table Questions

| Table Type | R1 | R2 | R3 | R4 | R5 | Best / Why |
|---|---|---|---|---|---|---|
| Temperature class (DIN EN 13463-1) | 1.3* | 4.7 | 4.7 | 4.7 | 4.7 | R2: ground truth fixed; BM25 catches "DIN EN 13463-1" |
| Thread specification (M12 pitch) | 2.5 | 4.7 | 4.7 | 4.7 | 4.7 | BM25 2× numeric boost catches "1.75 mm" exactly |
| Bolt grade / proof strength | 2.0* | 4.7 | 4.7 | 5.0 | 5.0 | Ground truth fixed; parent-child context helps |
| Chemical properties (viscosity) | 2.5 | 4.0 | 3.7 | 4.3 | 3.7 | R5 regressed — TABLE_CHUNK_ROWS=4 split rows too small |
| Sensor spec (PT100, 4–20 mA) | 2.0 | 3.5 | 3.0 | 3.7 | 2.0 | R5 regressed — 4-row chunks split related specs |
| Supply voltage spec | — | — | — | 4.0 | 3.7 | R5 regression from smaller chunks |

*Run 1 failures partly caused by questions referencing IECEx limits not in the PDFs — fixed in Run 2.

**Table chunking evolution:**

| Version | TABLE_CHUNK_ROWS | Impact |
|---|---|---|
| Run 1 | Full table (no split) | Large tables → diluted embeddings |
| Run 2–4 | 6 rows | Good balance — specific enough, large enough for ranges |
| Run 5 | 4 rows | Too small — range queries split across chunks, scores dropped |
| **→ Best: 6 rows** | ✅ | Reverted after Run 5 regression |

---

### Text Questions

| Text Type | R1 | R2 | R3 | R4 | R5 | Best / Why |
|---|---|---|---|---|---|---|
| PPE / safety handling | 3.0 | 4.7 | 4.7 | 4.7 | 5.0 | SDS boost (Run 5) correctly surfaces PPE sections |
| ATEX / regulatory reference | 3.0 | 4.5 | 5.0 | 5.0 | 5.0 | Contextual prefix anchors to engineering domain |
| Procedure (pump startup steps) | 3.0 | 4.7 | 4.7 | 4.7 | 4.7 | Semantic chunker keeps full procedure together |
| Environmental hazard / disposal | 2.5 | 3.5 | 3.7 | 4.0 | 4.7 | SDS boost helps surface environmental sections |
| Shaft seal type | 2.5 | 3.5 | 3.5 | 4.3 | 4.7 | Parent-child gives fuller procedure context |
| Storage / handling | 3.0 | 4.0 | 4.0 | 4.0 | 4.0 | Stable |
| Maintenance action | 2.5 | 3.5 | 3.7 | 3.3 | 3.3 | Inconsistent — symptom + action sometimes split |
| First-aid measures | 2.5 | 2.7 | 2.7 | 2.7 | 2.7 | SDS sections scattered — still inconsistent |

**Text improvement drivers:**
- R2: Contextual prefix + BM25 for exact term matching
- R3: Semantic chunker switched to local (no API cost)
- R4: Parent-child chunking — LLM sees full section, not just the matched sentence
- R5: SDS keyword boost surfaces safety/chemical content reliably

---

### Multihop Questions

| Multihop Pattern | R1 | R2 | R3 | R4 | R5 | Why Changed |
|---|---|---|---|---|---|---|
| Image + text (ATEX category → zones) | 1.5 | 4.7 | 4.7 | 4.7 | 4.7 | Caption gives category; text gives zone |
| Table cross-ref (T4 op temp → lubricant safe?) | 2.0 | 3.7 | 3.7 | 3.7 | 4.0 | Sub-query decomposition retrieves each table separately |
| Conditional (T4 + mech seal → 90°C safe?) | 2.0 | 3.7 | 3.7 | 4.3 | 4.3 | Query decomposition + synthesis prompt |
| Cross-document (viscosity → pump compat.) | 1.5 | 2.7 | 2.7 | 3.3 | 2.7 | R5: stricter CRAG dropped bridging chunks |
| Arithmetic (total bolts = flanges × bolts/flange) | 1.0 | 1.3 | 1.3 | 1.3 | 2.3 | Marginal — RAG retrieves facts, Sonnet attempts reasoning |
| Multi-step (thread pitch → torque) | 1.0 | 1.3 | 1.3 | 1.3 | 3.0 | Sub-query decomposition + synthesis instruction helped |

**Multihop improvement drivers:**
- R2: doc_type bug fix — correct PDF searched for each sub-document
- R4: Query decomposition (Haiku breaks into 2–3 sub-questions) + Claude Sonnet generation
- R5 regression: Stricter CRAG dropped AMBIGUOUS chunks that cross-document queries need as bridging context
- **Fix applied for R6**: CRAG keeps AMBIGUOUS for multihop queries (`is_multihop=True`)

---

### Unanswerable Questions

| Pattern | R1 | R2 | R3 | R4 | R5 | Notes |
|---|---|---|---|---|---|---|
| Commercial info (price, lead time) | 4.5 | 5.0 | 5.0 | 5.0 | 5.0 | CRAG marks chunks irrelevant → low confidence → correct refusal |
| Unlisted specs (weight, noise, RPM) | 4.5 | 4.5 | 5.0 | 5.0 | 5.0 | |
| Operational metadata (serial number) | 4.5 | 4.5 | 5.0 | 5.0 | 5.0 | |
| Component provenance (bearing maker) | 4.5 | 4.0 | 5.0 | 4.7 | 4.7 | |
| Borderline (CAS number — may be in SDS) | 3.0 | 2.7 | 2.7 | 2.7 | 2.7 | Inconsistent — sometimes in SDS |
| Warranty period | 4.5 | 5.0 | 5.0 | 5.0 | 2.3 | R5 regression — SDS boost incorrectly retrieved tangentially related SDS content |

**Unanswerable consistently the strongest category** because CRAG correctly marks off-topic chunks as irrelevant, triggering low confidence and appropriate refusal.

---

## Latency Breakdown Per Run

| Pipeline Step | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|
| Query decomposition | — | — | — | +0.3s | +0.3s |
| HyDE expansion | ~1.5s | ~1.5s | ~0.5s | ~0.8s (×2 sub-q) | ~0.8s (×2–4) |
| pgvector search | ~0.1s | ~0.1s | ~0.1s | ~0.2s (×2) | ~0.3s |
| BM25 rerank | ~0.05s | ~0.05s | ~0.05s | ~0.05s | ~0.05s |
| SDS boost search | — | — | — | — | ~0.05s (if triggered) |
| CRAG batch scoring | ~3.5s (5 calls) | ~0.8s (batched) | ~0.5s | ~0.8s | ~0.8s |
| Answer generation | ~1.5s | ~1.5s | ~1.0s | ~3.0s (Sonnet) | ~3.0s (Sonnet) |
| Self-RAG critique | ~0.8s | ~0.8s | ~0.5s | ~0.8s | ~0.8s |
| **Measured avg** | **15.0s** | **~8s** | **~5s** | **21.3s** | **21.5s** |

> Latency increased R3→R4 because Claude Sonnet generation is slower than Haiku, and query decomposition added 2 HyDE calls. This is the cost of quality improvement. Production latency would improve with query caching and prompt caching.

---

## Trade-offs Summary

### Chunking
| Option | Score | Cost | Decision |
|---|---|---|---|
| Fixed-size 512 tokens | Medium | Free | Rejected — cuts procedures in half |
| Semantic (SemanticChunker local) | High | Free | ✅ Chosen — splits at topic boundaries |
| Parent-child (threshold 75/95) | Highest | Free | ✅ Chosen in R4 — child for retrieval, parent for generation |
| TABLE_CHUNK_ROWS=4 | Worse for ranges | Free | ❌ Reverted after R5 regression |
| TABLE_CHUNK_ROWS=6 | Best balance | Free | ✅ Restored |

### Retrieval
| Method | Score | Latency | Decision |
|---|---|---|---|
| Dense only | 4.833 | ~20ms | Rejected — misses exact values |
| BM25 only | 4.5 | ~10ms | Rejected — misses semantic paraphrases |
| Hybrid (Dense + BM25 + RRF) | 4.767 | ~30ms | ✅ Used |
| HyDE + Hybrid | 4.9 | +0.8s | ✅ Used — best score |
| Query decomposition | +0.64 multihop | +0.5s | ✅ Used — essential for multihop |

### Image Captioning
| Model | Coverage | Score | Cost | Decision |
|---|---|---|---|---|
| GPT-4o | 344/344 | 2.77 | $0.004/img | Rejected (expensive) |
| Claude Haiku | 354–359/359 | 3.30–3.37 | $0.002/img | ✅ Best — cheap, good coverage |
| Claude Sonnet | 102/359 | 2.53 | $0.008/img | ❌ Rejected — too much content filtering |

### Generation
| Model | Multihop | Cost | Decision |
|---|---|---|---|
| gpt-4o-mini | 3.73 | $0.002 | Strong, but quota exhausted |
| Claude Haiku | 2.63 | $0.008 | ❌ Too weak for multihop |
| Claude Sonnet | 3.27 | $0.022 | ✅ Current best with Anthropic |

### CRAG
| Strategy | Effect | Decision |
|---|---|---|
| Drop AMBIGUOUS always | R5: multihop -0.27 | ❌ Too aggressive |
| Keep AMBIGUOUS always | More noise in single-hop | ❌ Too permissive |
| **Adaptive: keep AMBIGUOUS for multihop only** | Best of both | ✅ Applied for R6 |

---

## Final Assessment — 5 Run Summary

### What Worked (clear improvements across runs)

| Improvement | First Run | Score Gain | Status |
|---|---|---|---|
| Contextual prefix (filename+section+page on every chunk) | R2 | +0.46 overall | ✅ Permanent — fundamental |
| Batch CRAG scoring (5 calls → 1 call) | R2 | Saves 3s latency | ✅ Permanent |
| Full-page PNG render for SDS vector graphics | R2 | +18 → 344 images | ✅ Permanent |
| Type-aware image caption prompt | R3 | +0.53 image | ✅ Permanent — biggest image gain |
| Local HuggingFace embeddings for SemanticChunker | R3 | Saves ~$0.50/run | ✅ Permanent — was a bug fix |
| Claude Sonnet for generation | R4 | +0.22 overall | ✅ Permanent |
| Query decomposition (up to 4 sub-questions) | R4/R5 | +0.64 multihop | ✅ Permanent |
| Parent-child chunking (child retrieve, parent generate) | R4 | +0.24 text | ✅ Permanent |
| BM25 2× numeric token boost | R4 | +0.20 table | ✅ Permanent |
| SDS section keyword boost | R5 | +0.46 text | ✅ Permanent |
| Sub-query labels in generation prompt | R5 | Synthesis improved | ✅ Permanent |

### What Was Tried and Reverted

| Change | Run | Reason for Revert |
|---|---|---|
| Claude Sonnet for image captioning | R5 | 257 of 359 images filtered by content policy → image score -0.84 |
| TABLE_CHUNK_ROWS=4 | R5 | Range queries need multiple rows → table score -0.37 |
| Strict CRAG (drop AMBIGUOUS always) | R5 | Multihop needs bridging chunks → multihop -0.27 |

### What Still Needs Work

| Issue | Category Impact | Root Cause | Next Fix |
|---|---|---|---|
| Spatial diagram captions | Image -0.84 | Alignment/bearing assembly descriptions lack positional language | Add explicit spatial instruction + more few-shot examples |
| Warning label text extraction | Image stable at 1.3 | Text on label images not OCR'd reliably | Consider pytesseract on image crop |
| Arithmetic multihop | Multihop 1.3–2.3 | RAG retrieves facts but doesn't compute | Consider tool-use for calculation |
| Cross-document multihop | Multihop 2.7 | SDS + pump manual chunks both needed but doc_type filter restricts | Ensure no doc_type filter on decomposed sub-queries |
| First-aid / scattered SDS sections | Text 2.7 | Sections span multiple pages, chunked separately | Consider SDS-specific chunker that keeps sections together |

### Score Trajectory Analysis

```
Score
 5.0 ┤                                              target ────────────
 4.5 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
 4.0 ┤
 3.87┤                                    ●  R4 (best)
 3.65┤                              ●  R3               ● R5
 3.59┤                    ●  R2
 3.5 ┤
 3.13┤    ●  R1
 3.0 ┤
     └─────────────────────────────────────────────────────────────
          R1       R2       R3       R4       R5    R6(not yet eval.)
```

**Gap to 4.5 target after Run 5: 0.85 points**

The score is at the same level as Run 3 (3.65). Run 4 was the best run (3.87). Run 5 identified three important failure modes by testing them: Sonnet image filtering, small table chunks, and over-aggressive CRAG. All three have been reverted/fixed for Run 6.

### Recommended Next Actions for Run 6

**No re-ingestion needed (all retrieval/generation changes):**
1. Adaptive CRAG (keep AMBIGUOUS for multihop) — **already applied**
2. Verify `_all_sub_queries` correctly detected in runner — **already applied**

**Requires re-ingestion (use Haiku, TABLE_CHUNK_ROWS=6 — already reverted):**
3. Full re-ingest: text + tables + images from scratch with Haiku captioner
4. Expected result: image chunks restore to ~354 (from 102), table chunks ~743

**Projected Run 6 score:**

| Category | Run 5 | Expected R6 | Improvement Source |
|---|---|---|---|
| text | 4.13 | 4.2+ | SDS boost + sub-query synthesis retained |
| table | 3.93 | 4.3+ | TABLE_CHUNK_ROWS=6 restored |
| image | 2.53 | 3.3+ | Haiku captioner restores 354 image chunks |
| multihop | 3.00 | 3.5+ | Adaptive CRAG keeps bridging chunks |
| unanswerable | 4.67 | 4.7 | Stable |
| **Overall** | **3.65** | **~4.0** | **Combined fixes** |

---

## Known Limitations

| Content Type | Issue | Priority |
|---|---|---|
| Spatial/layout diagrams | Alignment and orientation diagrams score 1.3–2.3 — captions describe parts but not spatial relationships | High |
| Multihop arithmetic | Questions requiring calculation (total bolts, % reduction) score ~1.3–2.3 — RAG retrieves facts, doesn't compute | High |
| Warning label text | Score stuck at 1.3 across all 5 runs — text on the label image not reliably OCR'd | Medium |
| Cross-document multihop | Combining SDS + pump manual still inconsistent | Medium |
| Scanned PDFs | No OCR active — `pytesseract` installed but not triggered | Low |
| Multi-page tables | Tables spanning 2+ pages treated separately — no joining logic | Low |
