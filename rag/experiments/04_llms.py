"""
04_llms.py  —  Compare LLMs for RAG generation (API-only, no local download).

LLMs:
  L1  claude-haiku-4-5     Anthropic API  fast + cheap
  L2  claude-sonnet-4-5    Anthropic API  best quality
  L3  gpt-4o-mini          OpenAI API     reference baseline

Pipeline (same as Data_ingestion.ipynb):
  1. Encode query with all-mpnet-base-v2
  2. Dot-product retrieval on FAISS (top-5)
  3. Build prompt using prompt_formatter() from config.py
  4. Send to LLM, collect answer + latency

Run:  python 04_llms.py
Output: results/llm_answers.csv  +  results/llm_stats.csv
"""

import time
import importlib.util
import numpy as np
import pandas as pd
import faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

EMBED_MODEL = "all-mpnet-base-v2"
SAMPLE_SIZE = 10   # use first 5 questions (keep costs low)


# ── FAISS retriever (identical to Data_ingestion.ipynb) ──────────────────

def build_retriever(chunks: list[str]):
    print(f"Building FAISS retriever with {EMBED_MODEL} ...")
    embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
    embs = embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True
    ).astype(np.float32)
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs)
    return embedder, index, chunks


def retrieve_relevant_resources(query: str,
                                 embedder,
                                 index,
                                 chunks: list[str],
                                 n_resources: int = 5) -> list[dict]:
    """
    Same function signature as Data_ingestion.ipynb.
    Returns list of dicts with 'sentence_chunk' key for prompt_formatter.
    """
    q_emb = embedder.encode([query], normalize_embeddings=True,
                             convert_to_numpy=True).astype(np.float32)
    scores, indices = index.search(q_emb, n_resources)
    return [{"sentence_chunk": chunks[i], "score": float(scores[0][j])}
            for j, i in enumerate(indices[0]) if i < len(chunks)]


# ── LLM generators ───────────────────────────────────────────────────────

def generate_claude(prompt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def generate_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


# ── Run one LLM ───────────────────────────────────────────────────────────

def run_llm(llm_id: str, generate_fn, questions: list[dict],
            embedder, index, chunks) -> tuple[list[dict], dict]:
    answers, latencies = [], []

    for q in tqdm(questions, desc=f"[{llm_id}]"):
        # Retrieve context (same as notebook)
        context_items = retrieve_relevant_resources(q["question"], embedder, index, chunks)

        # Format prompt (same function as notebook)
        prompt = prompt_formatter(q["question"], context_items)

        t0 = time.time()
        answer = generate_fn(prompt)
        latency = time.time() - t0

        answers.append({
            "llm":          llm_id,
            "question":     q["question"],
            "ground_truth": q["ground_truth"],
            "answer":       answer,
            "latency_sec":  round(latency, 2),
        })
        latencies.append(latency)

    stats = {
        "llm":               llm_id,
        "avg_latency_sec":   round(float(np.mean(latencies)), 2),
        "p99_latency_sec":   round(float(np.percentile(latencies, 99)), 2),
        "questions_answered": len(answers),
    }
    return answers, stats


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_llms(chunks: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    embedder, index, chunks = build_retriever(chunks)
    questions = TEST_QUESTIONS[:SAMPLE_SIZE]

    llm_registry = []
    if HAS_CLAUDE:
        llm_registry.append(("L1_claude-haiku",  lambda p: generate_claude(p, "claude-haiku-4-5")))
        llm_registry.append(("L2_claude-sonnet", lambda p: generate_claude(p, "claude-sonnet-4-5")))
    else:
        print("CLAUDE_API_KEY not set — skipping L1, L2")

    if HAS_OPENAI:
        llm_registry.append(("L3_gpt4o-mini", lambda p: generate_openai(p, "gpt-4o-mini")))
    else:
        print("OPENAI_API_KEY not set — skipping L3")

    if not llm_registry:
        raise RuntimeError("No LLM available. Set CLAUDE_API_KEY or OPENAI_API_KEY in .env")

    all_answers, all_stats = [], []
    for llm_id, gen_fn in llm_registry:
        print(f"\n>> {llm_id}")
        try:
            answers, stats = run_llm(llm_id, gen_fn, questions, embedder, index, chunks)
            all_answers.extend(answers)
            all_stats.append(stats)
        except Exception as e:
            print(f"   [FAILED: {e}]")
            all_stats.append({"llm": llm_id, "avg_latency_sec": 0, "judge_score": 0, "status": f"failed: {e}"})

    df_answers = pd.DataFrame(all_answers)
    df_stats   = pd.DataFrame(all_stats)

    df_answers.to_csv(RESULTS_DIR / "llm_answers.csv", index=False)
    df_stats.to_csv(RESULTS_DIR / "llm_stats.csv", index=False)
    print(f"\nSaved -> {RESULTS_DIR / 'llm_answers.csv'}")
    print(f"Saved -> {RESULTS_DIR / 'llm_stats.csv'}")
    return df_answers, df_stats


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 04 -- LLMs (Claude + OpenAI)")
    print("=" * 60)

    _, raw_text = load_document()

    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunk_dicts = mod.chunk_sentence(raw_text)
    chunks = mod.chunks_to_texts(chunk_dicts)
    print(f"Chunks: {len(chunks)}\n")

    df_answers, df_stats = run_all_llms(chunks)

    print("\n" + "=" * 60)
    print("LATENCY")
    print("=" * 60)
    print(df_stats.to_string(index=False))

    print("\n" + "=" * 60)
    print("SAMPLE ANSWERS")
    print("=" * 60)
    for llm in df_answers["llm"].unique():
        row = df_answers[df_answers["llm"] == llm].iloc[0]
        print(f"\n[{llm}]")
        print(f"Q: {row['question']}")
        answer_safe = row["answer"][:300].encode("ascii", errors="replace").decode()
        print(f"A: {answer_safe}")
