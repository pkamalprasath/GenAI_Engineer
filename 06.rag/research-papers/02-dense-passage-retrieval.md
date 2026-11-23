# Paper 02 — Dense Passage Retrieval (DPR)

**Authors:** Vladimir Karpukhin, Barlas Oguz, Sewon Min et al. (Meta AI)
**Published:** 2020 — EMNLP 2020
**Citations:** 2,500+

---

## The Problem It Solved

BM25 (sparse keyword matching) had dominated information retrieval for decades. It works well for exact keyword matches but fails on semantic similarity — "heart attack" vs "myocardial infarction" score zero similarity in BM25.

## Core Idea

Train two separate BERT encoders — one for queries, one for passages:

```
Query Encoder  -->  q_vector (768-dim)
                         |
                    dot product
                         |
Passage Encoder -->  p_vector (768-dim)
```

Both encoders are trained end-to-end with **contrastive learning** — maximize similarity for relevant (query, passage) pairs, minimize for irrelevant ones.

At inference time, passage embeddings are pre-computed and stored. Retrieval is a fast nearest-neighbor search (FAISS).

## Key Results

- Outperformed BM25 on multiple QA datasets by 9-19% top-20 accuracy
- Showed that dense > sparse for semantic retrieval tasks
- FAISS index enables sub-millisecond retrieval over millions of passages

## Why It Matters

DPR became the **standard retrieval backbone** for RAG systems. OpenAI's `text-embedding-3-small`, Cohere embeddings, and all modern embedding models follow the same dual-encoder principle DPR established.

## Connection to My Experiments

> `experiments/02_embeddings.py` benchmarks dual-encoder embedding models, all descendants of DPR (4 of the 6 planned models ran). In the end-to-end sweep the small local `all-MiniLM-L6-v2` (384-dim) scored 5.0 and `text-embedding-3-small` (1536-dim) 4.93, on 5 questions each, so a small dual encoder was enough for this corpus.

---

**Key Takeaway:** Dense embeddings encode *meaning*, not just keywords. This is what makes semantic search possible.
