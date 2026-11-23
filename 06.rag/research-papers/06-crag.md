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

> `experiments/05_evaluation.py` was written to measure this with RAGAS faithfulness (whether retrieved chunks support the answer), but the RAGAS scores were not computed. CRAG itself is implemented in the engineering RAG project (`projects/2.engineering-rag/src/retrieval/crag.py`), where one batched call grades every retrieved chunk before generation.

---

**Key Takeaway:** Always evaluate your retrieval quality. Don't blindly trust retrieved documents — verify before generating.
