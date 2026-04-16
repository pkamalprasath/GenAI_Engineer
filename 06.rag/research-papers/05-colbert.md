# Paper 05 — ColBERT: Efficient and Effective Passage Search

**Authors:** Santhanam et al. (Stanford)
**Year:** 2022

---

## The Problem It Solved

DPR compresses each passage into a **single vector** — fast but loses fine-grained token-level information. Cross-encoders keep all token interactions but are too slow for large-scale retrieval. ColBERT finds the middle ground.

## Core Idea

**Late Interaction** — keep token-level embeddings but defer the interaction to query time:

```
DPR (bi-encoder):
  query    -->  [CLS] vector
  passage  -->  [CLS] vector
  score = dot(q, p)  ← single number, loses detail

ColBERT (late interaction):
  query    -->  [token1_vec, token2_vec, ..., tokenN_vec]
  passage  -->  [token1_vec, token2_vec, ..., tokenM_vec]
  score = sum(max_similarity(each query token, all passage tokens))
```

The **MaxSim** operation: for each query token, find the most similar passage token. Sum those. This preserves semantic alignment at token level.

## Key Results

- Matches cross-encoder quality at near bi-encoder speed
- Sub-millisecond retrieval at scale
- Better at handling multi-faceted queries than single-vector DPR

## Why It Matters

ColBERT's late interaction is now used in production retrieval systems. It explains why **re-ranking** works — using a more expressive scorer after fast first-stage retrieval is the engineering realisation of this principle.

## Connection to My Experiments

> `experiments/09_reranking.py` implements this two-stage idea: fast dense retrieval (top-20) followed by cross-encoder re-ranking (top-5). The +12% faithfulness gain validates ColBERT's core insight.

---

**Key Takeaway:** Token-level interaction > single-vector similarity for retrieval quality. Two-stage retrieval (fast recall + expensive re-rank) is the practical implementation.
