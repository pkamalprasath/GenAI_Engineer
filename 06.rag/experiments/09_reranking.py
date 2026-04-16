"""
09_reranking.py  —  Compare retrieval with and without cross-encoder re-ranking.

Pipeline:
  Step 1: Dense retrieval — top-20 candidates (wider net)
  Step 2: Re-rank with cross-encoder — pick best top-5 from those 20

Re-rankers tested:
  RR0  No reranker     dense top-5 only (baseline)
  RR1  MiniLM          cross-encoder/ms-marco-MiniLM-L-6-v2   ~80MB  CPU
  RR2  MiniLM-L12      cross-encoder/ms-marco-MiniLM-L-12-v2  ~130MB CPU
  RR3  BGE-reranker    BAAI/bge-reranker-base                  ~280MB CPU

All use C1 chunks, all-mpnet-base-v2 embeddings, Claude/OpenAI for generation.

Run:  python 09_reranking.py
Output: results/reranking_stats.csv  +  results/chart_reranking.png
"""

import json
import time
import importlib.util
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer, util as st_util, CrossEncoder
from tqdm import tqdm

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

EMBED_MODEL = "all-mpnet-base-v2"
RETRIEVAL_CANDIDATE_K = 20    # wider first-pass retrieval
FINAL_TOP_K           = 5     # after re-ranking


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


# ── Dense retrieval (first pass) ──────────────────────────────────────────

def build_dense_index(chunks: list[str], embedder):
    return embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_tensor=True, show_progress_bar=True,
    )


def retrieve_dense(query: str, embedder, embeddings: torch.Tensor,
                   chunks: list[str], top_k: int) -> list[str]:
    q_emb = embedder.encode(query, normalize_embeddings=True, convert_to_tensor=True)
    dot_scores = st_util.dot_score(q_emb, embeddings)[0]
    _, indices = torch.topk(dot_scores, k=min(top_k, len(chunks)))
    return [chunks[i] for i in indices.tolist()]


# ── Cross-encoder re-ranking ───────────────────────────────────────────────

def rerank(query: str, candidates: list[str],
           cross_encoder: CrossEncoder, top_k: int = FINAL_TOP_K) -> list[dict]:
    """Score all (query, candidate) pairs and return top_k."""
    pairs = [(query, c) for c in candidates]
    scores = cross_encoder.predict(pairs, show_progress_bar=False)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [{"sentence_chunk": c, "score": float(s)} for s, c in ranked[:top_k]]


# ── Run one reranker config ────────────────────────────────────────────────

def run_reranker(label: str, cross_encoder, questions: list[dict],
                 embedder, embeddings, chunks) -> dict:
    latencies, judge_scores, rerank_times = [], [], []

    for q in tqdm(questions, desc=label):
        # Wide first-pass retrieval
        candidates = retrieve_dense(q["question"], embedder, embeddings, chunks,
                                    top_k=FINAL_TOP_K if cross_encoder is None else RETRIEVAL_CANDIDATE_K)

        # Re-rank (or skip for baseline)
        t_rerank = time.time()
        if cross_encoder is not None:
            ctx = rerank(q["question"], candidates, cross_encoder, FINAL_TOP_K)
        else:
            ctx = [{"sentence_chunk": c} for c in candidates[:FINAL_TOP_K]]
        rerank_times.append(time.time() - t_rerank)

        prompt = prompt_formatter(q["question"], ctx)
        t0 = time.time()
        answer = call_llm(prompt)
        latencies.append(time.time() - t0)
        judge_scores.append(judge(q["question"], q["ground_truth"], answer))

    return {
        "reranker":          label,
        "avg_rerank_ms":     round(float(np.mean(rerank_times)) * 1000, 1),
        "avg_latency_sec":   round(float(np.mean(latencies)), 2),
        "judge_score":       mean_score(judge_scores),
    }


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_rerankers(chunks: list[str]) -> pd.DataFrame:
    embedder   = SentenceTransformer(EMBED_MODEL, device="cpu")
    print("Building dense index ...")
    embeddings = build_dense_index(chunks, embedder)
    questions  = TEST_QUESTIONS[:10]

    reranker_configs = [
        ("RR0_NoReranker", None),
        ("RR1_MiniLM-L6",  "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        ("RR2_MiniLM-L12", "cross-encoder/ms-marco-MiniLM-L-12-v2"),
        ("RR3_BGE-base",   "BAAI/bge-reranker-base"),
    ]

    results = []
    for label, model_name in reranker_configs:
        print(f"\n>> {label}")
        if model_name:
            print(f"   Loading cross-encoder: {model_name} ...")
            try:
                ce = CrossEncoder(model_name, device="cpu")
            except Exception as e:
                print(f"   [FAILED to load: {e}]")
                results.append({"reranker": label, "avg_rerank_ms": 0,
                                "avg_latency_sec": 0, "judge_score": 0,
                                "status": f"failed: {e}"})
                continue
        else:
            ce = None

        row = run_reranker(label, ce, questions, embedder, embeddings, chunks)
        row["status"] = "ok"
        results.append(row)
        print(f"   judge_score={row['judge_score']}  latency={row['avg_latency_sec']}s  "
              f"rerank={row['avg_rerank_ms']}ms")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "reranking_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")

    # Chart
    ok_df = df[df.get("status", "ok") == "ok"] if "status" in df.columns else df
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(ok_df["reranker"], ok_df["judge_score"],
                  color=colors[:len(ok_df)], edgecolor="white")
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_title("Re-ranking: Impact on RAG Quality", fontsize=13, fontweight="bold")
    ax.set_ylabel("Judge Score (avg 1-5)", fontsize=10)
    ax.set_ylim(0, ok_df["judge_score"].max() * 1.25 + 0.1)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    chart_out = RESULTS_DIR / "chart_reranking.png"
    plt.savefig(chart_out, dpi=150); plt.close()
    print(f"Chart -> {chart_out}")

    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 09 -- Re-ranking")
    print("=" * 60)

    _, raw_text = load_document()
    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunks = mod.chunks_to_texts(mod.chunk_sentence(raw_text))
    print(f"Chunks: {len(chunks)}\n")

    df = run_all_rerankers(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
