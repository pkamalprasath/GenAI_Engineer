"""
10_prompt_variants.py  —  Compare prompt templates for RAG generation.

Variants:
  P1  Minimal         "Answer the question using the context below."
  P2  Notebook        Data_ingestion.ipynb's detailed multi-instruction prompt (baseline)
  P3  Step-by-step    Chain-of-thought: "Think step by step before answering"
  P4  Expert persona  "You are a certified nutritionist. Answer only from context."
  P5  Structured      Ask for a structured answer: definition, explanation, examples

All use: C1 chunks, all-mpnet-base-v2, PyTorch retrieval, top_k=5, Claude/OpenAI.

Run:  python 10_prompt_variants.py
Output: results/prompt_stats.csv  +  results/chart_prompts.png
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
TOP_K = 5


# ── Prompt templates ──────────────────────────────────────────────────────

def fmt_minimal(query: str, context_items: list[dict]) -> str:
    """P1: Minimal — bare bones."""
    context = "\n".join(f"- {c['sentence_chunk']}" for c in context_items)
    return f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"


def fmt_notebook(query: str, context_items: list[dict]) -> str:
    """P2: Identical to Data_ingestion.ipynb (baseline)."""
    return prompt_formatter(query, context_items)


def fmt_cot(query: str, context_items: list[dict]) -> str:
    """P3: Chain-of-thought — ask model to reason step by step."""
    context = "\n".join(f"- {c['sentence_chunk']}" for c in context_items)
    return (
        "You are a nutrition expert. Use the context below to answer the question.\n"
        "Think step by step:\n"
        "  1. Identify the key facts from the context relevant to the question.\n"
        "  2. Reason through them carefully.\n"
        "  3. Give a clear, complete answer.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Step-by-step answer:"
    )


def fmt_expert(query: str, context_items: list[dict]) -> str:
    """P4: Expert persona with strict grounding instruction."""
    context = "\n".join(f"- {c['sentence_chunk']}" for c in context_items)
    return (
        "You are a certified nutritionist and dietitian with 20 years of experience.\n"
        "Answer the question using ONLY the information provided in the context below.\n"
        "If the context does not contain enough information, say so clearly.\n"
        "Do not add information from outside the context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Expert answer:"
    )


def fmt_structured(query: str, context_items: list[dict]) -> str:
    """P5: Structured output — definition, explanation, examples."""
    context = "\n".join(f"- {c['sentence_chunk']}" for c in context_items)
    return (
        "Using only the context provided, answer the question in this structured format:\n\n"
        "**Definition:** (1 sentence)\n"
        "**Explanation:** (2-3 sentences with key details)\n"
        "**Key points:** (bullet list of 3-5 items)\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Structured answer:"
    )


PROMPT_VARIANTS = [
    ("P1_Minimal",    fmt_minimal),
    ("P2_Notebook",   fmt_notebook),    # baseline
    ("P3_ChainOfThought", fmt_cot),
    ("P4_ExpertPersona",  fmt_expert),
    ("P5_Structured", fmt_structured),
]


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


# ── Retrieval (PyTorch tensor — same as notebook) ─────────────────────────

def build_index(chunks: list[str], embedder):
    return embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_tensor=True, show_progress_bar=True,
    )


def retrieve(query: str, embedder, embeddings, chunks, top_k=TOP_K) -> list[dict]:
    q_emb = embedder.encode(query, normalize_embeddings=True, convert_to_tensor=True)
    scores, indices = torch.topk(st_util.dot_score(q_emb, embeddings)[0], k=min(top_k, len(chunks)))
    return [{"sentence_chunk": chunks[i], "score": float(s)}
            for i, s in zip(indices.tolist(), scores.tolist())]


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_prompt_variants(chunks: list[str]) -> pd.DataFrame:
    embedder   = SentenceTransformer(EMBED_MODEL, device="cpu")
    print("Building index ...")
    embeddings = build_index(chunks, embedder)
    questions  = TEST_QUESTIONS[:10]

    results = []
    for label, fmt_fn in PROMPT_VARIANTS:
        print(f"\n>> {label}")
        latencies, judge_scores, answer_lens = [], [], []

        for q in tqdm(questions, desc=label):
            ctx    = retrieve(q["question"], embedder, embeddings, chunks)
            prompt = fmt_fn(q["question"], ctx)
            t0     = time.time()
            answer = call_llm(prompt)
            latencies.append(time.time() - t0)
            answer_lens.append(len(answer.split()))
            judge_scores.append(judge(q["question"], q["ground_truth"], answer))

        row = {
            "prompt_variant":    label,
            "avg_answer_words":  round(float(np.mean(answer_lens))),
            "avg_latency_sec":   round(float(np.mean(latencies)), 2),
            "judge_score":       mean_score(judge_scores),
        }
        results.append(row)
        print(f"   judge_score={row['judge_score']}  latency={row['avg_latency_sec']}s  "
              f"avg_words={row['avg_answer_words']}")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "prompt_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")

    # Chart — side by side bars: quality + answer length
    x = np.arange(len(df))
    width = 0.4
    fig, ax1 = plt.subplots(figsize=(10, 5))
    bars = ax1.bar(x - width / 2, df["judge_score"], width,
                   label="Judge Score (1-5)", color="#4C72B0", edgecolor="white")
    ax1.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    ax1.set_ylabel("Judge Score (avg 1-5)", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["prompt_variant"], rotation=15, ha="right", fontsize=9)
    ax1.set_ylim(0, df["judge_score"].max() * 1.3 + 0.2)

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, df["avg_answer_words"], width,
                    label="Avg Answer (words)", color="#55A868", alpha=0.7, edgecolor="white")
    ax2.set_ylabel("Avg Answer Length (words)", fontsize=10)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    ax1.set_title("Prompt Template: Quality vs Answer Length", fontsize=13, fontweight="bold")
    ax1.spines["top"].set_visible(False)
    plt.tight_layout()
    chart_out = RESULTS_DIR / "chart_prompts.png"
    plt.savefig(chart_out, dpi=150); plt.close()
    print(f"Chart -> {chart_out}")

    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 10 -- Prompt Variants")
    print("=" * 60)

    _, raw_text = load_document()
    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunks = mod.chunks_to_texts(mod.chunk_sentence(raw_text))
    print(f"Chunks: {len(chunks)}\n")

    df = run_all_prompt_variants(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
