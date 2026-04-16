# Paper 07 — Adaptive RAG

**Authors:** Xie et al.
**Year:** 2024

---

## The Problem It Solved

RAG always retrieves — even for queries that don't need it ("What is 2+2?"). Unnecessary retrieval adds latency and can introduce noise. But never retrieving fails for knowledge-intensive queries. How do you know when to retrieve?

## Core Idea

Train a **router model** that classifies query complexity and decides the retrieval strategy:

```
Query
  |
  v
Router Model classifies:
  - Simple     -->  answer directly (no retrieval)
  - Medium     -->  single-step retrieval
  - Complex    -->  multi-step retrieval with reasoning
  |
  v
Execute appropriate strategy
```

The router is a small classifier trained on query-answer pairs — lightweight enough to run before the main RAG pipeline.

## Key Results

- Reduces unnecessary retrievals by 30-40% on simple queries
- Maintains quality on complex queries that need retrieval
- Lower overall latency than always-on RAG

## Why It Matters

In production, not every user query needs vector search. Adaptive RAG reduces cost and latency by being smart about when to retrieve. This is the direction production systems are heading — retrieval on demand, not retrieval by default.

## Connection to My Experiments

> `experiments/07_topk.py` shows that k=5 is optimal — more chunks add noise. Adaptive RAG extends this: sometimes k=0 (no retrieval) is optimal. The experiments implicitly explore this space.

---

**Key Takeaway:** Retrieval is not free. Know when to retrieve, when to reason, and when to do both.
