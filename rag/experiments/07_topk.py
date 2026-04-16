"""
07_topk.py  —  Sweep top_k (number of retrieved chunks) and measure impact.

Data_ingestion.ipynb default: top_k = 5
Values tested: 1, 3, 5, 10, 20

Pipeline (identical to notebook):
  - C1 sentence chunks + all-mpnet-base-v2 + PyTorch tensor retrieval
  - prompt_formatter() from config.py
  - Claude claude-haiku-4-5 for generation
  - LLM-as-Judge scoring

Run:  python 07_topk.py
Output: results/topk_stats.csv  +  results/chart_topk.png
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
from sentence_transformers import SentenceTransformer, util as st_util
from tqdm import tqdm

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

EMBED_MODEL = "all-mpnet-base-v2"
TOP_K_VALUES = [1, 3, 5, 10, 20]


# ── Build PyTorch tensor store (same as Data_ingestion.ipynb) ─────────────

def build_tensor_store(chunks: list[str], embedder):
    print(f"Embedding {len(chunks)} chunks with {EMBED_MODEL} ...")
    embs = embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_tensor=True, show_progress_bar=True,
    )
    return embs  # torch.Tensor (N, D)


def retrieve_topk(query: str, embedder, embeddings: torch.Tensor,
                  chunks: list[str], top_k: int) -> list[dict]:
    """Identical to Data_ingestion.ipynb retrieve_relevant_resources()."""
    q_emb = embedder.encode(query, normalize_embeddings=True, convert_to_tensor=True)
    dot_scores = st_util.dot_score(q_emb, embeddings)[0]
    scores, indices = torch.topk(dot_scores, k=min(top_k, len(chunks)))
    return [{"sentence_chunk": chunks[i], "score": float(s)}
            for i, s in zip(indices.tolist(), scores.tolist())]


# ── LLM caller ────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    if HAS_CLAUDE:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    elif HAS_OPENAI:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=512,
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
        raw = call_llm(prompt)
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {"relevance": 0, "correctness": 0, "completeness": 0}


def mean_score(scores: list[dict]) -> float:
    vals = [(s.get("relevance", 0) + s.get("correctness", 0) + s.get("completeness", 0)) / 3
            for s in scores]
    return round(float(np.mean(vals)), 3) if vals else 0.0


# ── Main ──────────────────────────────────────────────────────────────────

def run_topk_sweep(chunks: list[str]) -> pd.DataFrame:
    embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
    embeddings = build_tensor_store(chunks, embedder)

    results = []
    questions = TEST_QUESTIONS[:10]   # 5 questions to keep cost low

    for top_k in TOP_K_VALUES:
        print(f"\n>> top_k = {top_k}")
        latencies, judge_scores = [], []
        context_lengths = []

        for q in tqdm(questions, desc=f"top_k={top_k}"):
            ctx = retrieve_topk(q["question"], embedder, embeddings, chunks, top_k)
            prompt = prompt_formatter(q["question"], ctx)
            context_lengths.append(sum(len(c["sentence_chunk"]) for c in ctx))

            t0 = time.time()
            answer = call_llm(prompt)
            latencies.append(time.time() - t0)

            judge_scores.append(judge(q["question"], q["ground_truth"], answer))

        row = {
            "top_k":              top_k,
            "avg_context_chars":  round(float(np.mean(context_lengths))),
            "avg_latency_sec":    round(float(np.mean(latencies)), 2),
            "judge_score":        mean_score(judge_scores),
        }
        results.append(row)
        print(f"   judge_score={row['judge_score']}  latency={row['avg_latency_sec']}s  "
              f"avg_ctx={row['avg_context_chars']} chars")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "topk_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")

    # Chart
    fig, ax1 = plt.subplots(figsize=(8, 5))
    color1 = "#4C72B0"
    ax1.plot(df["top_k"], df["judge_score"], "o-", color=color1, linewidth=2, markersize=8, label="Judge Score")
    ax1.set_xlabel("top_k (chunks retrieved)", fontsize=11)
    ax1.set_ylabel("Judge Score (avg 1-5)", color=color1, fontsize=11)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_xticks(TOP_K_VALUES)

    ax2 = ax1.twinx()
    color2 = "#C44E52"
    ax2.plot(df["top_k"], df["avg_latency_sec"], "s--", color=color2, linewidth=2, markersize=8, label="Latency")
    ax2.set_ylabel("Avg Latency (sec)", color=color2, fontsize=11)
    ax2.tick_params(axis="y", labelcolor=color2)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower right")
    ax1.set_title("Top-K Retrieval: Quality vs Latency", fontsize=13, fontweight="bold")
    ax1.spines["top"].set_visible(False)
    plt.tight_layout()
    chart_out = RESULTS_DIR / "chart_topk.png"
    plt.savefig(chart_out, dpi=150); plt.close()
    print(f"Chart -> {chart_out}")

    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 07 -- top_k Sweep")
    print("=" * 60)

    _, raw_text = load_document()

    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunks = mod.chunks_to_texts(mod.chunk_sentence(raw_text))
    print(f"Chunks: {len(chunks)}\n")

    df = run_topk_sweep(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
