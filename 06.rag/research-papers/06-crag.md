# Paper 06 — CRAG: Corrective Retrieval Augmented Generation

**Authors:** Yan et al.
**Year:** 2024

---

## The Problem It Solved

Standard RAG retrieves blindly — it always retrieves, regardless of whether the retrieved documents are actually relevant. Bad retrieval leads to worse answers than no retrieval at all.

## Core Idea

Add a **retrieval evaluator** that scores document relevance before generation:

```
Query
  |
  v
Retrieve top-k docs
  |
  v
Evaluator scores each doc:
  - CORRECT    -->  use the document directly
  - AMBIGUOUS  -->  refine/decompose the document
  - INCORRECT  -->  discard, fall back to web search
  |
  v
Generate from filtered/supplemented context
```

Three-way classification: relevant, partially relevant, irrelevant. If quality is low, CRAG routes to a web search fallback to supplement.

## Key Results

- Significant improvement in faithfulness over standard RAG on multiple QA benchmarks
- Handles the case where the knowledge base doesn't contain the answer
- Particularly effective for time-sensitive queries (falls back to web search)

## Why It Matters

CRAG formalises what any good RAG engineer does intuitively — check if your retrieval is actually useful before trusting it. This is the production insight: garbage retrieval = garbage answer, regardless of LLM quality.

## Connection to My Experiments

> `experiments/05_evaluation.py` uses RAGAS faithfulness scores to measure exactly this — whether retrieved chunks genuinely support the generated answer. Low faithfulness = CRAG-style detection that something went wrong.

---

**Key Takeaway:** Always evaluate your retrieval quality. Don't blindly trust retrieved documents — verify before generating.
