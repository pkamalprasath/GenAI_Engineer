# Paper 10 — Hybrid Retrieval & Advanced Techniques

**Authors:** Multiple research groups
**Year:** 2023–2024

---

## The Problem It Solved

Dense retrieval (DPR-style) excels at semantic similarity but misses exact keyword matches. Sparse retrieval (BM25) excels at exact matches but misses semantic similarity. Neither is optimal alone.

## Core Ideas

### 1. Hybrid Retrieval (Dense + Sparse)

Combine both retrievers and merge results using **Reciprocal Rank Fusion (RRF)**:

```
Query
  |
  +---> Dense Retriever (embedding similarity) --> ranked list A
  |
  +---> BM25 (keyword matching)               --> ranked list B
  |
  v
RRF: score(doc) = sum(1 / (k + rank_in_list))
  |
  v
Final merged ranking
```

RRF is parameter-free and surprisingly effective — no need to tune weights between dense and sparse scores.

### 2. HyDE — Hypothetical Document Embeddings

Instead of embedding the query directly, generate a **hypothetical answer** and embed that:

```
Query: "What causes type 2 diabetes?"
  |
  v
LLM generates hypothetical answer:
  "Type 2 diabetes is caused by insulin resistance..."
  |
  v
Embed the hypothetical answer (not the query)
  |
  v
Search for passages similar to the hypothetical answer
```

HyDE works because a generated answer is stylistically closer to a real passage than a short query is.

### 3. Re-ranking Pipeline

```
Stage 1: Bi-encoder retrieval (fast)   --> top-50 candidates
Stage 2: Cross-encoder re-ranking      --> top-5 final results
```

Cross-encoder jointly encodes query + passage — much more expressive than bi-encoder, but only applied to the small candidate set.

## Key Results

- Hybrid (Dense + BM25) outperforms either alone by 10-20% recall on diverse QA datasets
- HyDE improves retrieval on zero-shot tasks where the query is very different from passage style
- Re-ranking consistently improves faithfulness by 10-15%

## Why It Matters

These are the **production-grade retrieval techniques** used in real systems. No serious RAG deployment uses pure dense retrieval alone.

## Connection to My Experiments

> `experiments/08_retrieval_methods.py` directly tests all four methods: Dense, BM25, Hybrid (RRF), and HyDE. My experimental results confirmed the +15% recall gain for Hybrid — consistent with the research.
> `experiments/09_reranking.py` validates the +12% faithfulness gain from cross-encoder re-ranking.

---

**Key Takeaway:** In production, always use hybrid retrieval (Dense + BM25) and add a re-ranker. It's the most impactful single improvement to any RAG system.
