# Paper 03 — REALM: Retrieval-Augmented Language Model Pre-Training

**Authors:** Kelvin Guu, Kenton Lee, Zora Tung et al. (Google Research)
**Year:** 2020

---

## The Problem It Solved

RAG and DPR treat retrieval as an add-on — retrieve first, then generate. But the retriever is trained separately from the generator. REALM asked: what if they learned together from the start?

## Core Idea

Pre-train the language model *with* a retriever jointly, so retrieval is not post-hoc but baked into the model's core reasoning:

```
Pre-training objective:
  - Mask a span in the document
  - Model must retrieve relevant docs to fill the mask
  - Retriever and generator update together end-to-end
```

The model learns to retrieve documents that help predict masked tokens — forcing it to develop useful retrieval behavior from the ground up.

## Key Results

- State-of-the-art on Open-Domain QA at time of publication
- Retriever learns to find genuinely useful documents (not just relevant-looking ones)
- Joint training means retriever and generator are aligned by design

## Why It Matters

REALM showed that **retrieval is a learnable skill** — not just a lookup operation. It inspired later work on Self-RAG (models that decide when to retrieve) and Agentic RAG (retrieval as a planned action).

## Connection to My Experiments

> `experiments/05_evaluation.py` uses RAGAS to measure whether retrieved chunks actually help answer the question — the same question REALM addresses through joint training.

---

**Key Takeaway:** The best retrieval systems learn what "useful" means, not just what "relevant" means.
