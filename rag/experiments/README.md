# RAG Experiments

A systematic benchmarking suite comparing every major RAG design decision — from chunking to re-ranking — on a real-world 1,200-page nutrition textbook.

Each script is self-contained, dependency-free of LangChain wrappers, and outputs benchmark CSVs + charts to `results/`.

## Experiment Pipeline

```
PDF
 │
 ├─ 01_chunking.py        Compare 6 chunking strategies
 ├─ 02_embeddings.py      Compare 6 embedding models
 ├─ 03_vectorstores.py    Compare 6 vector stores
 ├─ 04_llms.py            Compare 4 LLMs for generation
 ├─ 05_evaluation.py      RAGAS + LLM-as-judge evaluation
 ├─ 06_full_comparison.py End-to-end pipeline comparison
 ├─ 07_topk.py            Sweep top-k retrieval count
 ├─ 08_retrieval_methods.py  Dense vs BM25 vs Hybrid vs HyDE
 ├─ 09_reranking.py       Cross-encoder re-ranking
 └─ 10_prompt_variants.py 4 prompt templates compared
```

## What Was Tested

| Experiment | Variants | Key Finding |
|---|---|---|
| Chunking | Sentence, Fixed-small, Fixed-large, Semantic, Structural, LLM-based | Semantic chunking best faithfulness |
| Embeddings | all-mpnet, MiniLM, BGE-small, OpenAI-small, OpenAI-large, Cohere | OpenAI-small best quality/cost ratio |
| Vector Stores | PyTorch, FAISS, ChromaDB, Qdrant, LanceDB, Weaviate | FAISS fastest in-memory |
| LLMs | GPT-4o-mini, GPT-4o, Claude Haiku, Ollama Mistral | GPT-4o-mini best quality/cost |
| Top-K | 1, 3, 5, 10, 20 chunks | k=5 optimal for this corpus |
| Retrieval | Dense, BM25, Hybrid (RRF), HyDE | Hybrid+HyDE best recall |
| Re-ranking | No reranker vs cross-encoder | +12% faithfulness with reranker |
| Prompts | Minimal, Detailed, CoT, Expert persona | Expert persona + CoT best |

## Results

Charts are in `results/` — each experiment generates a comparison chart:

| Chart | Description |
|---|---|
| `chart_chunking.png` | Chunk quality metrics by strategy |
| `chart_embeddings.png` | Retrieval scores by embedding model |
| `chart_vectorstores.png` | Latency + recall by vector store |
| `chart_llms.png` | Answer quality by LLM |
| `chart_topk.png` | Quality vs retrieval count |
| `chart_retrieval.png` | Dense vs Hybrid vs HyDE |
| `chart_reranking.png` | Impact of cross-encoder re-ranking |
| `chart_prompts.png` | RAGAS scores by prompt template |
| `chart_latency_vs_quality.png` | Full pipeline Pareto analysis |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env
# Fill in OPENAI_API_KEY (and optionally CLAUDE_API_KEY)
```

## Run Any Experiment

```bash
python 01_chunking.py        # outputs results/chunking_stats.csv
python 02_embeddings.py      # outputs results/embedding_stats.csv
# ... etc
python 06_full_comparison.py # end-to-end — runs after all individual scripts
```
