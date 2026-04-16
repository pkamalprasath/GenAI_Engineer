# Paper 04 — RETRO: Retrieval-Enhanced Transformer

**Authors:** Borgeaud et al. (DeepMind)
**Year:** 2021

---

## The Problem It Solved

Scaling LLMs requires exponentially more parameters and compute. Is there a more efficient path to knowledge?

## Core Idea

RETRO achieves better performance with **smaller models** by pairing them with retrieval over a large external database:

```
Key Finding:
  4B parameter model + retrieval
  BEATS
  12B parameter model without retrieval
```

Technical innovation: **Chunked Cross-Attention** — instead of attending over the full retrieved document at every layer (expensive), RETRO chunks the input and attends to retrieved neighbours only at specific layers. Much more efficient.

## Key Results

- 25x smaller model can match GPT-3's performance on language modelling with retrieval
- Linear scaling — adding more retrieval data improves performance without retraining
- Separates *parametric knowledge* (in weights) from *non-parametric knowledge* (in retrieval database)

## Why It Matters

RETRO made the economic case for RAG. You don't need a 70B model if you have good retrieval. This principle drives real production decisions today — use a fast, cheap model (GPT-4o-mini) with good retrieval rather than an expensive model without it.

## Connection to My Experiments

> `experiments/04_llms.py` validates this — GPT-4o-mini with well-retrieved context matches GPT-4o quality at a fraction of the cost. Retrieval quality matters more than model size.

---

**Key Takeaway:** Retrieval is more compute-efficient than parameters. A smaller model with good retrieval beats a bigger model without it.
