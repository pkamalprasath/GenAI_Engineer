"""
06_patch.py — Fill gaps in all_results.csv without re-running everything.

Runs only the missing combos:
  C4_semantic       — chunking sweep (was skipped/missing)
  E5_fastembed-bge  — embedding sweep (fastembed now installed)
  L1_claude-haiku   — LLM sweep (run crashed before Sweep D)
  L2_claude-sonnet  — LLM sweep
  V2_Chroma         — vectorstore sweep (stale folder caused failure)

Then merges into all_results.csv and regenerates all charts.
"""

import json, shutil, time
import numpy as np
import pandas as pd
import faiss
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import importlib.util

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

SAMPLE_QS = TEST_QUESTIONS[:5]


# ── Load modules ──────────────────────────────────────────────────────────

def _load(filename, alias):
    spec = importlib.util.spec_from_file_location(alias, filename)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

chunking_mod = _load("01_chunking.py", "chunking")


# ── LLM callers ───────────────────────────────────────────────────────────

def call_claude(prompt, model="claude-haiku-4-5"):
    import anthropic, time as t
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    for attempt in range(5):
        try:
            msg = client.messages.create(
                model=model, max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"   [overloaded, retrying in {wait}s]")
                t.sleep(wait)
            else:
                raise

def call_openai(prompt, model="gpt-4o-mini"):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=model, max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


# ── Judge ─────────────────────────────────────────────────────────────────

JUDGE_PROMPT = (
    "Score this RAG answer 1-5 for relevance, correctness, completeness.\n"
    "Return ONLY JSON: {{\"relevance\":<int>,\"correctness\":<int>,\"completeness\":<int>}}\n\n"
    "Question: {question}\nGround Truth: {ground_truth}\nAnswer: {answer}"
)

def judge(record, judge_fn):
    prompt = JUDGE_PROMPT.format(**record)
    try:
        raw = judge_fn(prompt)
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {"relevance": 0, "correctness": 0, "completeness": 0}

def mean_score(scores):
    vals = [(s.get("relevance",0)+s.get("correctness",0)+s.get("completeness",0))/3
            for s in scores]
    return round(float(np.mean(vals)), 3) if vals else 0.0


# ── Embed helpers ─────────────────────────────────────────────────────────

def encode_st(model, texts):
    return model.encode(
        texts, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=False
    ).astype(np.float32)

def encode_fastembed(texts, model_name="BAAI/bge-small-en-v1.5"):
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=model_name)
    embs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


# ── Core combo runner ─────────────────────────────────────────────────────

def run_combo(label, chunk_texts, embed_fn, generate_fn, judge_fn):
    chunk_embs = embed_fn(chunk_texts)
    latencies, scores = [], []
    for q in SAMPLE_QS:
        q_emb = embed_fn([q["question"]])[0]
        sims  = chunk_embs @ q_emb
        top_idx = np.argsort(sims)[::-1][:5]
        ctx = [{"sentence_chunk": chunk_texts[i]} for i in top_idx]
        prompt = prompt_formatter(q["question"], ctx)
        t0 = time.time()
        answer = generate_fn(prompt)
        latencies.append(time.time() - t0)
        scores.append(judge({"question": q["question"],
                              "ground_truth": q["ground_truth"],
                              "answer": answer}, judge_fn))
    return {
        "config":          label,
        "num_chunks":      len(chunk_texts),
        "avg_latency_sec": round(float(np.mean(latencies)), 2),
        "judge_score":     mean_score(scores),
        "ingest_sec":      "",
        "error":           "",
    }


# ── Charts ────────────────────────────────────────────────────────────────

def bar_chart(df, x, y, title, fname, color):
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(df[x], df[y], color=color, edgecolor="white")
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(x); ax.set_ylabel(y)
    ax.set_ylim(0, min(df[y].max() * 1.25 + 0.1, 5.2))
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    plt.xticks(rotation=20, ha="right", fontsize=9)
    plt.tight_layout()
    out = RESULTS_DIR / fname
    plt.savefig(out, dpi=150); plt.close()
    print(f"  Chart -> {out}")

def scatter_chart(df, fname="chart_latency_vs_quality.png"):
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab20(np.linspace(0, 1, len(df)))
    for idx, (_, row) in enumerate(df.iterrows()):
        ax.scatter(row["avg_latency_sec"], row["judge_score"],
                   color=colors[idx], s=80, zorder=3)
        ax.annotate(row["config"], (row["avg_latency_sec"], row["judge_score"]),
                    fontsize=7, xytext=(5, 5), textcoords="offset points")
    ax.set_xlabel("Avg Latency (sec)"); ax.set_ylabel("Judge Score (avg 1-5)")
    ax.set_title("Latency vs Quality — All Configs", fontsize=13, fontweight="bold")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    plt.tight_layout()
    out = RESULTS_DIR / fname
    plt.savefig(out, dpi=150); plt.close()
    print(f"  Chart -> {out}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("06_patch.py — Filling missing combos")
    print("=" * 60)

    _, raw_text = load_document()

    # Judge + default generator
    if HAS_CLAUDE:
        judge_fn    = lambda p: call_claude(p, "claude-haiku-4-5")
        default_gen = judge_fn
        print("Judge + Generator: Claude claude-haiku-4-5")
    elif HAS_OPENAI:
        judge_fn    = lambda p: call_openai(p, "gpt-4o-mini")
        default_gen = judge_fn
        print("Judge + Generator: gpt-4o-mini")
    else:
        raise RuntimeError("Set CLAUDE_API_KEY or OPENAI_API_KEY")

    # Default chunks + embedder
    print("\nBuilding default C1 chunks ...")
    default_chunks = chunking_mod.chunks_to_texts(chunking_mod.chunk_sentence(raw_text))
    print(f"  {len(default_chunks)} chunks")

    from sentence_transformers import SentenceTransformer
    print("Loading default embedder all-mpnet-base-v2 ...")
    default_st    = SentenceTransformer("all-mpnet-base-v2", device="cpu")
    default_embed = lambda texts: encode_st(default_st, texts)
    print("Embedding default chunks ...")
    default_embs  = default_embed(default_chunks)
    print("Done.\n")

    new_rows = []

    # ── 1. C4_semantic chunking ───────────────────────────────────────────
    print("-" * 50)
    print("PATCH 1: C4_semantic chunking")
    print("-" * 50)
    try:
        print("  Building semantic chunks (embedding sentences) ...")
        c4_chunks = chunking_mod.chunks_to_texts(chunking_mod.chunk_semantic(raw_text))
        print(f"  {len(c4_chunks)} chunks")
        row = run_combo("C4_semantic", c4_chunks, default_embed, default_gen, judge_fn)
        row["sweep"] = "chunking"
        new_rows.append(row)
        print(f"  score={row['judge_score']}  latency={row['avg_latency_sec']}s")
    except Exception as e:
        print(f"  [FAILED: {e}]")
        new_rows.append({"config":"C4_semantic","judge_score":0,"avg_latency_sec":0,
                         "num_chunks":0,"ingest_sec":0,"sweep":"chunking","error":str(e)})

    # ── 2. E5_fastembed embedding ─────────────────────────────────────────
    print("\n" + "-" * 50)
    print("PATCH 2: E5_fastembed-bge embedding")
    print("-" * 50)
    try:
        print("  Encoding chunks with fastembed BGE-small ...")
        fe_embed = lambda texts: encode_fastembed(texts, "BAAI/bge-small-en-v1.5")
        row = run_combo("E5_fastembed-bge", default_chunks, fe_embed, default_gen, judge_fn)
        row["sweep"] = "embedding"
        new_rows.append(row)
        print(f"  score={row['judge_score']}  latency={row['avg_latency_sec']}s")
    except Exception as e:
        print(f"  [FAILED: {e}]")
        new_rows.append({"config":"E5_fastembed-bge","judge_score":0,"avg_latency_sec":0,
                         "num_chunks":0,"ingest_sec":0,"sweep":"embedding","error":str(e)})

    # ── 3. V2_Chroma vectorstore ──────────────────────────────────────────
    print("\n" + "-" * 50)
    print("PATCH 3: V2_Chroma vectorstore")
    print("-" * 50)
    try:
        import chromadb
        chroma_path = str(RESULTS_DIR / "chroma_sweep")
        shutil.rmtree(chroma_path, ignore_errors=True)   # clear stale folder
        c = chromadb.PersistentClient(path=chroma_path)
        col = c.create_collection("rag_sweep", metadata={"hnsw:space": "cosine"})
        print(f"  Inserting {len(default_chunks)} chunks into Chroma ...")
        t0 = time.time()
        for i in range(0, len(default_chunks), 100):
            batch = default_chunks[i:i+100]
            col.add(
                embeddings=default_embs[i:i+100].tolist(),
                documents=batch,
                ids=[f"doc{i+j}" for j in range(len(batch))],
            )
        ingest_sec = round(time.time() - t0, 2)
        print(f"  Ingested in {ingest_sec}s")

        latencies, scores = [], []
        for q in SAMPLE_QS:
            q_emb = default_embed([q["question"]])[0]
            r = col.query(query_embeddings=[q_emb.tolist()], n_results=5)
            ctx = [{"sentence_chunk": t} for t in r["documents"][0]]
            prompt = prompt_formatter(q["question"], ctx)
            t_q = time.time()
            answer = default_gen(prompt)
            latencies.append(time.time() - t_q)
            scores.append(judge({"question": q["question"],
                                  "ground_truth": q["ground_truth"],
                                  "answer": answer}, judge_fn))
        row = {
            "config": "V2_Chroma", "sweep": "vectorstore",
            "num_chunks": len(default_chunks),
            "ingest_sec": ingest_sec,
            "avg_latency_sec": round(float(np.mean(latencies)), 2),
            "judge_score": mean_score(scores), "error": "",
        }
        new_rows.append(row)
        print(f"  score={row['judge_score']}  latency={row['avg_latency_sec']}s")
    except Exception as e:
        print(f"  [FAILED: {e}]")
        new_rows.append({"config":"V2_Chroma","judge_score":0,"avg_latency_sec":0,
                         "num_chunks":0,"ingest_sec":0,"sweep":"vectorstore","error":str(e)})

    # ── 4. L1 + L2 LLMs ──────────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("PATCH 4: LLM sweep — L1_claude-haiku + L2_claude-sonnet")
    print("-" * 50)
    llm_configs = []
    if HAS_CLAUDE:
        llm_configs += [
            ("L1_claude-haiku",  lambda p: call_claude(p, "claude-haiku-4-5")),
            ("L2_claude-sonnet", lambda p: call_claude(p, "claude-sonnet-4-5")),
        ]
    for llm_label, gen_fn in llm_configs:
        print(f"\n  >> {llm_label}")
        try:
            row = run_combo(llm_label, default_chunks, default_embed, gen_fn, judge_fn)
            row["sweep"] = "llm"
            new_rows.append(row)
            print(f"  score={row['judge_score']}  latency={row['avg_latency_sec']}s")
        except Exception as e:
            print(f"  [FAILED: {e}]")
            new_rows.append({"config":llm_label,"judge_score":0,"avg_latency_sec":0,
                             "num_chunks":0,"ingest_sec":0,"sweep":"llm","error":str(e)})

    # ── Merge into all_results.csv ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Merging into all_results.csv ...")
    existing_path = RESULTS_DIR / "all_results.csv"
    df_existing = pd.read_csv(existing_path) if existing_path.exists() else pd.DataFrame()

    # Remove any old rows for configs we just re-ran
    patched_configs = [r["config"] for r in new_rows]
    if not df_existing.empty:
        df_existing = df_existing[~df_existing["config"].isin(patched_configs)]

    df_new  = pd.DataFrame(new_rows)
    df_all  = pd.concat([df_existing, df_new], ignore_index=True)
    df_all.to_csv(existing_path, index=False)
    print(f"Saved -> {existing_path}  ({len(df_all)} rows total)")

    # ── Regenerate charts ─────────────────────────────────────────────────
    print("\nRegenerating charts ...")
    for sweep, fname, title, color in [
        ("chunking",    "chart_chunking.png",    "LLM-Judge Score by Chunking Strategy", "#4C72B0"),
        ("embedding",   "chart_embeddings.png",  "LLM-Judge Score by Embedding Model",   "#55A868"),
        ("vectorstore", "chart_vectorstores.png","LLM-Judge Score by Vector Store",       "#C44E52"),
        ("llm",         "chart_llms.png",        "LLM-Judge Score by LLM",               "#8172B2"),
    ]:
        df_s = df_all[df_all["sweep"] == sweep].copy()
        if df_s.empty: continue
        df_s = df_s[df_s["judge_score"] > 0]   # exclude failed rows
        if df_s.empty: continue
        bar_chart(df_s, "config", "judge_score", title, fname, color)

    scatter_chart(df_all[df_all["judge_score"] > 0])

    # ── Final leaderboard ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL LEADERBOARD (by judge score)")
    print("=" * 60)
    show_cols = ["config", "sweep", "num_chunks", "avg_latency_sec", "judge_score"]
    df_show = df_all[[c for c in show_cols if c in df_all.columns]].copy()
    df_show = df_show[df_show["judge_score"] > 0].sort_values("judge_score", ascending=False)
    print(df_show.to_string(index=False))


if __name__ == "__main__":
    main()
