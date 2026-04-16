"""
08_retrieval_methods.py  —  Compare retrieval strategies.

Methods:
  R1  Dense only     PyTorch dot-product (identical to Data_ingestion.ipynb baseline)
  R2  BM25 only      rank_bm25, keyword/TF-IDF based, no embeddings needed
  R3  Hybrid         Reciprocal Rank Fusion of R1 + R2 scores (no extra model)
  R4  HyDE           Hypothetical Document Embeddings — ask LLM to write a fake
                     answer, embed that for retrieval (improves recall on hard Qs)

All use top_k=5, C1 sentence chunks, all-mpnet-base-v2 embeddings.

Run:  python 08_retrieval_methods.py
Output: results/retrieval_stats.csv  +  results/chart_retrieval.png
"""

import json
import re
import time
import importlib.util
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer, util as st_util
from tqdm import tqdm

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

EMBED_MODEL = "all-mpnet-base-v2"
TOP_K = 5


# ── LLM caller ────────────────────────────────────────────────────────────

def call_llm(prompt: str, max_tokens: int = 512) -> str:
    if HAS_CLAUDE:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    elif HAS_OPENAI:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    raise RuntimeError("No LLM available")


# ── LLM-as-Judge ──────────────────────────────────────────────────────────

JUDGE_PROMPT = (
    "Score this RAG answer 1-5 for relevance, correctness, completeness.\n"
    "Return ONLY JSON: {{\"relevance\":<int>,\"correctness\":<int>,\"completeness\":<int>}}\n\n"
    "Question: {question}\nGround Truth: {ground_truth}\nAnswer: {answer}"
)


def judge(question: str, ground_truth: str, answer: str) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, ground_truth=ground_truth, answer=answer)
    try:
        raw = call_llm(prompt, max_tokens=128)
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {"relevance": 0, "correctness": 0, "completeness": 0}


def mean_score(scores: list[dict]) -> float:
    vals = [(s.get("relevance", 0) + s.get("correctness", 0) + s.get("completeness", 0)) / 3
            for s in scores]
    return round(float(np.mean(vals)), 3) if vals else 0.0


# ── R1: Dense retrieval (Data_ingestion.ipynb baseline) ───────────────────

def build_dense_index(chunks: list[str], embedder):
    embs = embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_tensor=True, show_progress_bar=True,
    )
    return embs


def retrieve_dense(query: str, embedder, embeddings: torch.Tensor,
                   chunks: list[str], top_k: int = TOP_K) -> list[dict]:
    q_emb = embedder.encode(query, normalize_embeddings=True, convert_to_tensor=True)
    dot_scores = st_util.dot_score(q_emb, embeddings)[0]
    scores, indices = torch.topk(dot_scores, k=min(top_k, len(chunks)))
    return [{"sentence_chunk": chunks[i], "score": float(s), "rank": r}
            for r, (i, s) in enumerate(zip(indices.tolist(), scores.tolist()))]


# ── R2: BM25 keyword retrieval ────────────────────────────────────────────

def build_bm25_index(chunks: list[str]):
    from rank_bm25 import BM25Okapi
    tokenized = [re.sub(r"[^\w\s]", "", c.lower()).split() for c in chunks]
    return BM25Okapi(tokenized)


def retrieve_bm25(query: str, bm25, chunks: list[str], top_k: int = TOP_K) -> list[dict]:
    from rank_bm25 import BM25Okapi
    tokens = re.sub(r"[^\w\s]", "", query.lower()).split()
    scores = bm25.get_scores(tokens)
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [{"sentence_chunk": chunks[i], "score": float(scores[i]), "rank": r}
            for r, i in enumerate(top_idx)]


# ── R3: Hybrid — Reciprocal Rank Fusion (RRF) ─────────────────────────────

def reciprocal_rank_fusion(dense_results: list[dict], bm25_results: list[dict],
                            chunks: list[str], k: int = 60,
                            top_k: int = TOP_K) -> list[dict]:
    """
    RRF score = 1/(k + rank_dense) + 1/(k + rank_bm25)
    No extra model needed — purely a score combination.
    """
    rrf_scores: dict[str, float] = {}

    for r in dense_results:
        chunk = r["sentence_chunk"]
        rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1.0 / (k + r["rank"] + 1)

    for r in bm25_results:
        chunk = r["sentence_chunk"]
        rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1.0 / (k + r["rank"] + 1)

    sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"sentence_chunk": c, "score": s} for c, s in sorted_chunks]


# ── R4: HyDE — Hypothetical Document Embeddings ───────────────────────────

HYDE_PROMPT = (
    "Write a short 2-3 sentence passage from a nutrition textbook that would "
    "directly answer the following question. Write only the passage, no preamble.\n\n"
    "Question: {question}"
)


def retrieve_hyde(query: str, embedder, embeddings: torch.Tensor,
                  chunks: list[str], top_k: int = TOP_K) -> list[dict]:
    """
    1. Ask LLM to write a hypothetical answer
    2. Embed the hypothetical answer (not the query)
    3. Use that embedding for dense retrieval
    """
    hypothetical = call_llm(HYDE_PROMPT.format(question=query), max_tokens=150)
    # Embed the hypothetical passage instead of the raw query
    h_emb = embedder.encode(hypothetical, normalize_embeddings=True, convert_to_tensor=True)
    dot_scores = st_util.dot_score(h_emb, embeddings)[0]
    scores, indices = torch.topk(dot_scores, k=min(top_k, len(chunks)))
    return [{"sentence_chunk": chunks[i], "score": float(s)}
            for i, s in zip(indices.tolist(), scores.tolist())]


# ── Run one retrieval method ───────────────────────────────────────────────

def run_method(label: str, retrieve_fn, questions: list[dict]) -> dict:
    latencies, judge_scores = [], []

    for q in tqdm(questions, desc=label):
        ctx = retrieve_fn(q["question"])
        prompt = prompt_formatter(q["question"], ctx)
        t0 = time.time()
        answer = call_llm(prompt)
        latencies.append(time.time() - t0)
        judge_scores.append(judge(q["question"], q["ground_truth"], answer))

    return {
        "method":          label,
        "avg_latency_sec": round(float(np.mean(latencies)), 2),
        "judge_score":     mean_score(judge_scores),
    }


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_retrieval_methods(chunks: list[str]) -> pd.DataFrame:
    embedder  = SentenceTransformer(EMBED_MODEL, device="cpu")

    print("Building dense index ...")
    embeddings = build_dense_index(chunks, embedder)

    print("Building BM25 index ...")
    bm25 = build_bm25_index(chunks)

    questions = TEST_QUESTIONS[:10]

    methods = [
        ("R1_Dense",  lambda q: retrieve_dense(q, embedder, embeddings, chunks)),
        ("R2_BM25",   lambda q: retrieve_bm25(q, bm25, chunks)),
        ("R3_Hybrid", lambda q: reciprocal_rank_fusion(
            retrieve_dense(q, embedder, embeddings, chunks),
            retrieve_bm25(q, bm25, chunks),
            chunks,
        )),
        ("R4_HyDE",   lambda q: retrieve_hyde(q, embedder, embeddings, chunks)),
    ]

    results = []
    for label, retrieve_fn in methods:
        print(f"\n>> {label}")
        row = run_method(label, retrieve_fn, questions)
        results.append(row)
        print(f"   judge_score={row['judge_score']}  latency={row['avg_latency_sec']}s")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "retrieval_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")

    # Chart
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(df["method"], df["judge_score"], color=colors[:len(df)], edgecolor="white")
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_title("Retrieval Strategy: Dense vs BM25 vs Hybrid vs HyDE",
                 fontsize=12, fontweight="bold")
    ax.set_ylabel("Judge Score (avg 1-5)", fontsize=10)
    ax.set_ylim(0, df["judge_score"].max() * 1.25 + 0.1)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    plt.tight_layout()
    chart_out = RESULTS_DIR / "chart_retrieval.png"
    plt.savefig(chart_out, dpi=150); plt.close()
    print(f"Chart -> {chart_out}")

    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 08 -- Retrieval Methods")
    print("=" * 60)

    _, raw_text = load_document()
    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunks = mod.chunks_to_texts(mod.chunk_sentence(raw_text))
    print(f"Chunks: {len(chunks)}\n")

    df = run_all_retrieval_methods(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
