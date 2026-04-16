# RAG Experiments

A systematic benchmarking suite comparing every major RAG design decision on a real-world 1,200-page nutrition textbook.

Each script is self-contained, LangChain-free, and produces benchmark CSVs + charts in `results/`.

## Experiment Pipeline

| Script | What It Tests | Output |
|---|---|---|
| `01_chunking.py` | 6 chunking strategies (sentence, fixed-small, fixed-large, semantic, structural, LLM) | `chunking_stats.csv` |
| `02_embeddings.py` | 6 embedding models (MiniLM, MPNet, BGE, OpenAI-small, OpenAI-large, Cohere) | `embedding_stats.csv` |
| `03_vectorstores.py` | 6 vector stores (PyTorch, FAISS, ChromaDB, Qdrant, LanceDB, Weaviate) | `vectorstore_stats.csv` |
| `04_llms.py` | 4 LLMs (GPT-4o-mini, GPT-4o, Claude Haiku, Mistral/Ollama) | `llm_stats.csv` |
| `05_evaluation.py` | RAGAS metrics + LLM-as-judge scoring | `eval_ragas.csv`, `eval_llm_judge.csv` |
| `06_full_comparison.py` | End-to-end pipeline comparison | `all_results.csv` |
| `07_topk.py` | Top-K sweep (k = 1, 3, 5, 10, 20) | `topk_stats.csv` |
| `08_retrieval_methods.py` | Dense vs BM25 vs Hybrid RRF vs HyDE | `retrieval_stats.csv` |
| `09_reranking.py` | No reranker vs cross-encoder re-ranking | `reranking_stats.csv` |
| `10_prompt_variants.py` | 4 prompt templates (minimal, detailed, CoT, expert-persona) | `prompt_stats.csv` |

## Results

All charts are in `results/` — generated automatically by each script:

| Chart | What It Shows |
|---|---|
| `chart_chunking.png` | Chunk quality by strategy |
| `chart_embeddings.png` | Retrieval scores by embedding model |
| `chart_vectorstores.png` | Latency + recall by vector store |
| `chart_llms.png` | Answer quality + cost by LLM |
| `chart_topk.png` | Quality vs number of retrieved chunks |
| `chart_retrieval.png` | Dense vs Hybrid vs HyDE recall |
| `chart_reranking.png` | Faithfulness with and without cross-encoder |
| `chart_prompts.png` | RAGAS scores by prompt template |
| `chart_latency_vs_quality.png` | Full pipeline Pareto chart |

## Key Findings

- **Hybrid retrieval** (Dense + BM25 via Reciprocal Rank Fusion) outperforms pure dense by ~15% recall
- **Cross-encoder re-ranking** adds ~12% faithfulness with <50ms latency overhead
- **`text-embedding-3-small`** beats 768-dim local models at 1/10th the memory footprint
- **Expert-persona + chain-of-thought** prompts score highest on RAGAS across all LLMs
- **k=5** is the sweet spot — more chunks add noise, fewer miss context

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env
# Fill in OPENAI_API_KEY (CLAUDE_API_KEY optional for LLM experiment)
```

## Run

```bash
python 01_chunking.py
python 02_embeddings.py
# ... run each in order
python 06_full_comparison.py   # run last — aggregates all results
```
