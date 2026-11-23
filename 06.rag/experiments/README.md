# RAG design benchmarks

**I changed one RAG design choice at a time (chunking, embeddings, vector store, LLM, top-k, retrieval method, re-ranking, prompt) and scored each variant on a 1,208-page textbook: 35 completed configurations (38 attempted) across 8 sweeps.** The honest result is that most choices made little difference on this corpus. The clear signals were cost and latency: re-ranking added 2.7–21 s per query for no gain, and a free local embedding model scored as well as a paid API model.

> n = 5–10 questions per sweep; most differences are within judge noise.

These findings fed the design of the [engineering RAG project](../projects/2.engineering-rag/). Each script is self-contained, uses no LangChain in the core pipeline, and writes a CSV and a chart to `results/`.

## What was compared

Corpus: the open *Human Nutrition* textbook (`../data/human-nutrition-text.pdf`, 1,208 pages). Baseline pipeline: 10-sentence chunks, `all-mpnet-base-v2` embeddings, FAISS, Claude Haiku 4.5 as generator. Each sweep changes one component and keeps the others at the baseline.

| Sweep | Script | Variants attempted / completed | Questions per variant | Source CSV |
|---|---|:---:|:---:|---|
| Chunking | `01_chunking.py`, `06_full_comparison.py` | 6 / 6 | 5 | `chunking_stats.csv`, `all_results.csv` |
| Embedding models | `02_embeddings.py`, `06_full_comparison.py` | 6 / 4 | 5 | `embedding_stats.csv`, `all_results.csv` |
| Vector stores | `03_vectorstores.py`, `06_full_comparison.py` | 5 / 4 | 5 | `vectorstore_stats.csv`, `all_results.csv` |
| LLMs | `04_llms.py`, `06_full_comparison.py` | 3 / 3 | 5 | `llm_stats.csv`, `all_results.csv` |
| Top-k | `07_topk.py` | 5 / 5 | 10 | `topk_stats.csv` |
| Retrieval method | `08_retrieval_methods.py` | 4 / 4 | 10 | `retrieval_stats.csv` |
| Re-ranking | `09_reranking.py` | 4 / 4 | 10 | `reranking_stats.csv` |
| Prompt template | `10_prompt_variants.py` | 5 / 5 | 10 | `prompt_stats.csv` |
| **Total** | | **38 / 35** | | |

Not completed: two embedding models were skipped (FastEmbed would not install on Python 3.14; no Cohere API key) and Milvus Lite failed to build. FastEmbed was later run end-to-end only, by `06_patch.py` (4.93 in `all_results.csv`).

**Scoring.** Quality is an LLM-as-judge score from 1 to 5. The scripts use Claude Haiku 4.5 as judge when an Anthropic key is set and fall back to gpt-4o-mini otherwise; the CSVs do not record which judge scored each row. In the end-to-end sweeps the Haiku judge also scored answers from a Haiku generator.

**RAGAS columns not computed; scoring is LLM-as-judge.** `05_evaluation.py` contains RAGAS code, but `results/eval_ragas.csv` is empty in all four RAGAS columns (faithfulness, answer relevancy, context precision, context recall) for all 57 rows. The file is kept as a record of the attempted run. The same script's LLM-judge output, `results/eval_llm_judge.csv` (57 questions), averages 4.98 relevance, 4.81 correctness and 4.84 completeness.

## Findings

Every number below is copied from the CSVs in `results/`.

| Sweep | Result (judge score /5 unless stated) | What I take from it |
|---|---|---|
| Chunking | Fixed-512 5.0, semantic 5.0, sentence 4.93, structural 4.93, fixed-1024 4.87; LLM-based chunking was not scored end-to-end | Quality was flat. Cost was not: semantic chunking took 310.8 s and LLM-based 1,312.8 s, against 0.05 s for fixed-512. |
| Embedding models | `all-MiniLM-L6-v2` (384-dim, local) 5.0, BGE-small 4.93, `text-embedding-3-small` 4.93, MPNet 4.87 | A free local model matched the top score, so the engineering project uses MiniLM. |
| Vector stores (latency) | FAISS 159.8 ms, ChromaDB 166.8 ms, LanceDB 237.1 ms average query; **Qdrant failed**; Milvus Lite failed to build | See the Qdrant note below. End-to-end judge scores were 4.87–5.0 for every store that ran, so the store did not change answer quality. |
| LLMs | gpt-4o-mini 4.93, Claude Haiku 4.60, Claude Sonnet 4.47; average latency Haiku 4.68 s, gpt-4o-mini 6.25 s, Sonnet 9.06 s | Five questions per model is too few to rank them; Haiku was the fastest. |
| Top-k | k=1 3.93, k=3 4.80, k=5 4.67, k=10 4.73, k=20 4.93 | k=1 is clearly too little. Beyond k=3 the differences are within noise, while context grows from 4,084 to 26,695 characters. |
| Retrieval method | HyDE 4.90, dense 4.83, hybrid RRF 4.77, BM25 4.73 | Hybrid did not beat dense on this corpus. BM25 is still kept in the engineering project because it catches exact identifiers such as standard numbers. |
| Re-ranking | No reranker 4.8; MiniLM-L6 4.7, MiniLM-L12 4.8, BGE-base 4.8; re-ranking time 2,716–21,161 ms per query | No quality gain and a large time cost, so re-ranking was left out of the engineering project. |
| Prompt template | Notebook-style 4.80, minimal 4.77, structured 4.67, expert-persona 4.63, chain-of-thought 4.50 | Simple prompts did at least as well as chain-of-thought and expert-persona. |

**Qdrant row.** `vectorstore_stats.csv` records Qdrant with `avg_query_ms 0.0`, `avg_top1_similarity 0.0` and status `ok`. The benchmark loop in `03_vectorstores.py` catches each query error and still writes `ok`, so every Qdrant query failed and no latency was measured. Treat that row as failed. Qdrant did complete in the end-to-end sweep (`all_results.csv`, 4.93), which is why it is counted as completed above.

## Charts

`results/` holds one chart per sweep, each generated by its script: `chart_chunking.png`, `chart_embeddings.png`, `chart_vectorstores.png`, `chart_llms.png`, `chart_topk.png`, `chart_retrieval.png`, `chart_reranking.png`, `chart_prompts.png` and `chart_latency_vs_quality.png`.

## Limitations

- **Small samples.** 5 questions per variant in the end-to-end sweeps and 10 in the others. Scores sit between 3.93 and 5.0, mostly between 4.5 and 5.0, so a gap of 0.1–0.2 is not evidence that one option is better.
- **Saturated, unvalidated judge.** One LLM judge, no human-labelled subset and no repeated runs to measure judge variance. With an Anthropic key, Haiku judged its own answers in the end-to-end sweeps.
- **No retrieval metrics.** Nothing here measures recall or precision directly; the embedding script's `top1_sim_proxy` is a similarity proxy, not a recall score.
- **One corpus.** A single, well-written textbook. Results may not carry over to messy technical PDFs, which is why the engineering project ran its own 50-question evaluation.
- **RAGAS not computed** (see above).
- **Patched runs.** Some end-to-end rows were filled in later by `06_patch.py` and `06_patch_llms.py` after crashes or missing dependencies, not in a single clean run.

## Setup and run

The scripts call the OpenAI and Anthropic APIs, so running them costs money.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Create 06.rag/.env with OPENAI_API_KEY and, optionally, CLAUDE_API_KEY (read by config.py)

python 01_chunking.py
python 02_embeddings.py
# ... then each script in order
python 06_full_comparison.py       # end-to-end sweep; writes all_results.csv
```

The source PDF is expected at `../data/human-nutrition-text.pdf` (see `config.py`).
