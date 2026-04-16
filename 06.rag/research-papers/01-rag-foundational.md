# Paper 01 — Retrieval-Augmented Generation (RAG)

**Authors:** Patrick Lewis, Ethan Perez, Aleksandra Piktus et al. (Meta AI / UCL)
**Published:** 2020 — ACL 2020
**Citations:** 3,000+ (one of the most cited NLP papers of the decade)

---

## The Problem It Solved

Large language models have knowledge frozen at training time. They hallucinate when asked about facts they weren't trained on. Retraining is expensive. This paper asked: what if we let the model *look things up* at inference time?

## Core Idea

Combine a **dense retriever** (DPR) with a **sequence-to-sequence generator** (BART) end-to-end:

```
Query
  |
  v
DPR Retriever  -->  top-k documents from Wikipedia
  |
  v
BART Generator -->  answer conditioned on query + retrieved docs
```

Two variants proposed:
- **RAG-Sequence** — retrieve once, generate full answer from same docs
- **RAG-Token** — retrieve at each generation step (different docs per token)

## Key Results

- Outperformed parametric-only models on Open-Domain QA benchmarks (NaturalQuestions, TriviaQA, WebQ)
- Reduced hallucination compared to purely parametric models
- More factually grounded, more specific answers
- Showed retrieval + generation is better than either alone

## Why It Matters

This paper established the **RAG paradigm** — the idea that LLMs don't need to memorize everything, they just need to retrieve the right context. Every modern RAG system (LangChain, LlamaIndex, production chatbots) descends from this architecture.

## Connection to My Experiments

> The baseline in my `experiments/` module follows this exact architecture — embed the query, retrieve top-k chunks, pass to LLM. `01_chunking.py` through `04_llms.py` all benchmark variations of this pipeline.

---

**Key Takeaway:** You don't need a bigger model. You need a smarter retrieval strategy.
