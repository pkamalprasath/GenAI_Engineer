# Paper 09 — Agentic RAG: Beyond the Pipeline

**Authors:** Multiple (survey / emerging paradigm)
**Year:** 2024–2025

---

## The Problem It Solved

Standard RAG is a fixed pipeline: retrieve → generate. But complex questions require multiple retrieval steps, reasoning between steps, tool use, and adaptive planning. A pipeline can't handle this — an agent can.

## Core Idea

Transform RAG from a static pipeline into a **reasoning agent** with:

```
Standard RAG (pipeline):
  Query --> Retrieve --> Generate --> Answer

Agentic RAG (agent loop):
  Query
    |
    v
  Plan: what do I need to find?
    |
    v
  Retrieve (step 1) --> Reason --> Need more?
    |
    v
  Retrieve (step 2) --> Reason --> Need more?
    |
    v
  Synthesise across multiple retrievals
    |
    v
  Critique: is this answer complete and faithful?
    |
    v
  Answer
```

Key capabilities added:
- **Planning** — decompose complex queries before retrieving
- **Multi-step retrieval** — retrieve iteratively based on intermediate findings
- **Tool use** — retrieval is one tool among many (web search, code execution, APIs)
- **Self-critique** — evaluate answer completeness before returning

## Key Results

- Dramatically better on multi-hop QA (questions requiring chaining multiple facts)
- Handles queries that require different data sources
- More robust to retrieval failures (can retry with different strategies)

## Why It Matters

This is where RAG is heading in production. Systems like Perplexity AI, NotebookLM, and advanced copilots all use agentic retrieval — not a fixed pipeline.

## Connection to My Experiments

> The full experimental stack in `experiments/` is a systematic exploration of what Agentic RAG optimises automatically — chunking strategy, embedding model, retrieval method, re-ranking. The next step is building an agent that selects these dynamically.

---

**Key Takeaway:** RAG is not a pipeline — it's a reasoning strategy. Agents that plan retrieval outperform pipelines that execute it blindly.
