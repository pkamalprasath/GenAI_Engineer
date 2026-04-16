# RAG Research Papers — Study Notes

Notes from 10 foundational papers that shaped Retrieval-Augmented Generation.
Read before building — these papers explain *why* every design decision in the experiments works.

## Reading Order

| # | Paper | Year | Why Read It |
|---|---|---|---|
| 01 | [RAG — Foundational Paper](./01-rag-foundational.md) | 2020 | The original paper that started it all |
| 02 | [Dense Passage Retrieval (DPR)](./02-dense-passage-retrieval.md) | 2020 | How to do retrieval right — dual encoders |
| 03 | [REALM — Pre-Training with Retrieval](./03-realm-pretraining.md) | 2020 | What if retrieval is baked into pre-training? |
| 04 | [RETRO — Retrieval-Enhanced Transformer](./04-retro.md) | 2021 | Small model + retrieval beats large model alone |
| 05 | [ColBERT — Late Interaction](./05-colbert.md) | 2022 | Token-level retrieval for speed + quality |
| 06 | [CRAG — Corrective RAG](./06-crag.md) | 2024 | Self-correcting retrieval based on quality assessment |
| 07 | [Adaptive RAG](./07-adaptive-rag.md) | 2024 | Intelligently decide *when* to retrieve |
| 08 | [Self-RAG](./08-self-rag.md) | 2023 | Models that critique their own retrieval |
| 09 | [Agentic RAG](./09-agentic-rag.md) | 2024 | RAG as an intelligent agent, not a pipeline |
| 10 | [Hybrid Retrieval](./10-hybrid-retrieval.md) | 2023–24 | Combining dense + sparse for optimal recall |

## The RAG Evolution

```
2020  RAG Foundation (Lewis et al.)
       └─ Combine dense retrieval + seq2seq generation

2020  DPR (Karpukhin et al.)
       └─ Dual-encoder BERT retrieval beats BM25

2020  REALM (Guu et al.)
       └─ Learn retrieval during pre-training, not post-hoc

2021  RETRO (DeepMind)
       └─ 4B + retrieval > 12B without it — efficiency over parameters

2022  ColBERT (Santhanam et al.)
       └─ Late interaction: token-level embeddings for speed + accuracy

2023  Self-RAG (Asai et al.)
       └─ Models learn when to retrieve and critique their own output

2024  CRAG (Yan et al.)
       └─ Automatically evaluate and correct retrieval quality

2024  Adaptive RAG (Xie et al.)
       └─ Route queries — retrieve only when necessary

2024  Agentic RAG
       └─ Planning, multi-tool, non-linear retrieval with reasoning

2024  Hybrid Retrieval
       └─ Dense + BM25 + RRF — the production-grade retrieval stack
```

## Connection to Experiments

Each paper directly influenced the experiments in [`../experiments/`](../experiments/):

| Paper | Experiment |
|---|---|
| DPR | `02_embeddings.py` — dense embedding model comparison |
| RETRO / DPR | `03_vectorstores.py` — in-memory vs managed vector stores |
| Hybrid Retrieval | `08_retrieval_methods.py` — Dense + BM25 + RRF + HyDE |
| ColBERT / DPR | `09_reranking.py` — cross-encoder re-ranking |
| Self-RAG / CRAG | `05_evaluation.py` — RAGAS faithfulness scoring |
| Adaptive RAG | `07_topk.py` — adaptive top-k retrieval |
