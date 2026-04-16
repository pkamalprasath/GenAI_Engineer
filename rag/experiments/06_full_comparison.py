"""
06_full_comparison.py  —  Full sweep: vary one dimension at a time, chart results.

Defaults (same as Data_ingestion.ipynb baseline):
  Chunking   -> C1  sentence (spaCy, 10-sentence groups)
  Embedding  -> E1  all-mpnet-base-v2 (768-dim, CPU)
  VectorStore-> V1  FAISS in-memory
  LLM        -> L1  claude-haiku-4-5

Each combo is scored with LLM-as-Judge (fast).
Best combo then gets full RAGAS evaluation.

Run:  python 06_full_comparison.py
Output:
  results/all_results.csv
  results/chart_chunking.png
  results/chart_embeddings.png
  results/chart_vectorstores.png
  results/chart_llms.png
  results/chart_latency_vs_quality.png
"""

import json
import time
import importlib.util
import shutil
import numpy as np
import pandas as pd
import faiss
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from config import (
    RESULTS_DIR, TEST_QUESTIONS, prompt_formatter,
    HAS_CLAUDE, CLAUDE_API_KEY, HAS_OPENAI, OPENAI_API_KEY,
)
from data_loader import load_document

SAMPLE_QS = TEST_QUESTIONS[:5]   # 5 questions per combo keeps API cost low


# ── Load experiment modules ───────────────────────────────────────────────

def _load(filename: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, filename)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


chunking_mod = _load("01_chunking.py", "chunking")
eval_mod     = _load("05_evaluation.py", "evaluation")


# ── LLM callers ───────────────────────────────────────────────────────────

def call_claude(prompt: str, model: str = "claude-haiku-4-5") -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model=model, max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def call_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=model, max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


# ── LLM-as-Judge (inline) ────────────────────────────────────────────────

JUDGE_PROMPT = (
    "Score this RAG answer 1-5 for relevance, correctness, completeness.\n"
    "Return ONLY JSON: {{\"relevance\":<int>,\"correctness\":<int>,\"completeness\":<int>}}\n\n"
    "Question: {question}\nGround Truth: {ground_truth}\nAnswer: {answer}"
)


def judge(record: dict, judge_fn) -> dict:
    prompt = JUDGE_PROMPT.format(**record)
    try:
        raw = judge_fn(prompt)
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {"relevance": 0, "correctness": 0, "completeness": 0}


def mean_score(scores: list[dict]) -> float:
    vals = [(s.get("relevance", 0) + s.get("correctness", 0) + s.get("completeness", 0)) / 3
            for s in scores]
    return round(float(np.mean(vals)), 3) if vals else 0.0


# ── Embedding helpers ─────────────────────────────────────────────────────

def encode_st(model, texts: list[str]) -> np.ndarray:
    return model.encode(
        texts, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=False
    ).astype(np.float32)


def encode_openai(texts: list[str], model_name: str = "text-embedding-3-small") -> np.ndarray:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    all_e = []
    for i in range(0, len(texts), 100):
        resp = client.embeddings.create(input=texts[i:i+100], model=model_name)
        all_e.extend([e.embedding for e in resp.data])
    embs = np.array(all_e, dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


def encode_fastembed(texts: list[str], model_name: str) -> np.ndarray:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=model_name)
    embs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


# ── Core: run one combo ───────────────────────────────────────────────────

def run_combo(label: str,
              chunk_texts: list[str],
              embed_fn,           # callable: texts -> np.ndarray
              retrieve_fn,        # callable: (query, chunk_embs, chunks) -> list[dict]
              generate_fn,
              judge_fn) -> dict:
    """Embed chunks, retrieve, generate, judge. Returns stats dict."""
    # Embed chunks
    chunk_embs = embed_fn(chunk_texts)

    latencies, scores = [], []
    for q in SAMPLE_QS:
        # Retrieve — dot product (same as notebook)
        q_emb = embed_fn([q["question"]])[0]
        sims  = chunk_embs @ q_emb
        top_k = 5
        top_idx = np.argsort(sims)[::-1][:top_k]
        ctx = [{"sentence_chunk": chunk_texts[i]} for i in top_idx]

        prompt = prompt_formatter(q["question"], ctx)
        t0 = time.time()
        answer = generate_fn(prompt)
        latencies.append(time.time() - t0)

        record = {"question": q["question"], "ground_truth": q["ground_truth"], "answer": answer}
        scores.append(judge(record, judge_fn))

    return {
        "config":          label,
        "num_chunks":      len(chunk_texts),
        "avg_latency_sec": round(float(np.mean(latencies)), 2),
        "judge_score":     mean_score(scores),
    }


# ── Chunk getter ──────────────────────────────────────────────────────────

def get_chunks(strategy: str, raw_text: str) -> list[str]:
    mapping = {
        "C1": lambda t: chunking_mod.chunk_sentence(t),
        "C2": lambda t: chunking_mod.chunk_fixed(t, 512, 50),
        "C3": lambda t: chunking_mod.chunk_fixed(t, 1024, 100),
        "C4": lambda t: chunking_mod.chunk_semantic(t),
        "C5": lambda t: chunking_mod.chunk_structural(t),
        "C6": lambda t: chunking_mod.chunk_llm_based(t),
    }
    dicts = mapping[strategy](raw_text)
    return chunking_mod.chunks_to_texts(dicts)


# ── Charts ────────────────────────────────────────────────────────────────

def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, fname: str, color: str):
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


def scatter_chart(df: pd.DataFrame, fname: str = "chart_latency_vs_quality.png"):
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab20(np.linspace(0, 1, len(df)))
    for idx, (_, row) in enumerate(df.iterrows()):
        ax.scatter(row["avg_latency_sec"], row["judge_score"], color=colors[idx], s=80, zorder=3)
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
    print("Experiment 06 -- Full Comparison Sweep")
    print("=" * 60)

    _, raw_text = load_document()

    # ── Set up judge and default generator ───────────────────────────────
    print("\nSetting up judge and generator ...")
    if HAS_CLAUDE:
        judge_fn   = lambda p: call_claude(p, "claude-haiku-4-5")
        default_gen = judge_fn
        print("Judge + Generator: Claude claude-haiku-4-5")
    elif HAS_OPENAI:
        judge_fn    = lambda p: call_openai(p, "gpt-4o-mini")
        default_gen = judge_fn
        print("Judge + Generator: gpt-4o-mini")
    else:
        raise RuntimeError("Set CLAUDE_API_KEY or OPENAI_API_KEY in .env")

    # Default chunks (C1) and embed function (E1)
    print("\nBuilding default chunks C1 (sentence) ...")
    default_chunks = get_chunks("C1", raw_text)
    print(f"  {len(default_chunks)} chunks")

    print("  Loading embedding model all-mpnet-base-v2 ...")
    default_st = SentenceTransformer("all-mpnet-base-v2", device="cpu")
    print("  Embedding model loaded.")
    default_embed = lambda texts: encode_st(default_st, texts)

    all_results = []

    # ── SWEEP A: Chunking ─────────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("SWEEP A -- Chunking Strategies")
    print("-" * 50)
    sweep_a = []
    for cid, label in [("C1","sentence"), ("C2","fixed-512"), ("C3","fixed-1024"),
                       ("C4","semantic"), ("C5","structural")]:
        print(f"\n  >> {cid}_{label}")
        chunks = get_chunks(cid, raw_text)
        row = run_combo(f"{cid}_{label}", chunks, default_embed, None, default_gen, judge_fn)
        row["sweep"] = "chunking"
        sweep_a.append(row); all_results.append(row)
        print(f"     score={row['judge_score']}  latency={row['avg_latency_sec']}s  chunks={row['num_chunks']}")
    bar_chart(pd.DataFrame(sweep_a), "config", "judge_score",
              "LLM-Judge Score by Chunking Strategy", "chart_chunking.png", "#4C72B0")

    # ── SWEEP B: Embedding Models ─────────────────────────────────────────
    print("\n" + "-" * 50)
    print("SWEEP B -- Embedding Models")
    print("-" * 50)
    embed_configs = [
        ("E1_mpnet-768",  lambda: encode_st(SentenceTransformer("all-mpnet-base-v2", device="cpu"), default_chunks)),
        ("E2_minilm-384", lambda: encode_st(SentenceTransformer("all-MiniLM-L6-v2",  device="cpu"), default_chunks)),
        ("E3_bge-small",  lambda: encode_st(SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"), default_chunks)),
    ]
    if HAS_OPENAI:
        embed_configs.append(("E4_openai-3-small", lambda: encode_openai(default_chunks)))
    try:
        from fastembed import TextEmbedding
        embed_configs.append(("E5_fastembed-bge", lambda: encode_fastembed(default_chunks, "BAAI/bge-small-en-v1.5")))
    except ImportError:
        print("  [FastEmbed not installed — skipping E5]")

    sweep_b = []
    for label, chunk_embed_lazy in embed_configs:
        print(f"\n  >> {label}")
        # Build embed_fn that wraps the model for queries too
        # Determine model for query encoding
        if "mpnet" in label:
            _m = SentenceTransformer("all-mpnet-base-v2", device="cpu")
            embed_fn = lambda texts, m=_m: encode_st(m, texts)
        elif "minilm" in label:
            _m = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            embed_fn = lambda texts, m=_m: encode_st(m, texts)
        elif "bge" in label and "fastembed" not in label:
            _m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
            embed_fn = lambda texts, m=_m: encode_st(m, texts)
        elif "openai" in label:
            embed_fn = lambda texts: encode_openai(texts)
        elif "fastembed" in label:
            embed_fn = lambda texts: encode_fastembed(texts, "BAAI/bge-small-en-v1.5")
        else:
            continue

        row = run_combo(label, default_chunks, embed_fn, None, default_gen, judge_fn)
        row["sweep"] = "embedding"
        sweep_b.append(row); all_results.append(row)
        print(f"     score={row['judge_score']}  latency={row['avg_latency_sec']}s")
    bar_chart(pd.DataFrame(sweep_b), "config", "judge_score",
              "LLM-Judge Score by Embedding Model", "chart_embeddings.png", "#55A868")

    # ── SWEEP C: Vector Stores ────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("SWEEP C -- Vector Stores")
    print("-" * 50)

    # Pre-embed default chunks once
    default_embs = encode_st(default_st, default_chunks)

    vs_results = []
    for vs_label, retrieve_fn_builder in [
        ("V0_PyTorch", "torch"),
        ("V1_FAISS", "faiss"),
        ("V2_Chroma", "chroma"),
        ("V3_Qdrant", "qdrant"),
        ("V4_LanceDB", "lancedb"),
        ("V5_Milvus", "milvus"),
    ]:
        print(f"\n  >> {vs_label}")
        t0 = time.time()
        try:
            if retrieve_fn_builder == "torch":
                import torch
                from sentence_transformers import util as st_util
                # Encode as tensors — same as Data_ingestion.ipynb
                chunk_tensors = default_st.encode(
                    default_chunks, batch_size=32, normalize_embeddings=True,
                    convert_to_tensor=True, show_progress_bar=False
                )
                def retrieve_vs(q_emb_np, _ct=chunk_tensors, _chunks=default_chunks):
                    q_t = torch.tensor(q_emb_np)
                    scores = st_util.dot_score(q_t, _ct)[0]
                    _, ids = torch.topk(scores, k=5)
                    return [_chunks[i] for i in ids.tolist()]

            elif retrieve_fn_builder == "faiss":
                idx = faiss.IndexFlatIP(default_embs.shape[1])
                idx.add(default_embs)
                def retrieve_vs(q_emb, _idx=idx):
                    sc, ids = _idx.search(q_emb[None, :], 5)
                    return [default_chunks[i] for i in ids[0] if i < len(default_chunks)]

            elif retrieve_fn_builder == "chroma":
                import chromadb
                p = str(RESULTS_DIR / "chroma_sweep")
                c = chromadb.PersistentClient(path=p)
                try: c.delete_collection("sweep")
                except: pass
                col = c.create_collection("sweep", metadata={"hnsw:space": "cosine"})
                for i in range(0, len(default_chunks), 100):
                    col.add(embeddings=default_embs[i:i+100].tolist(),
                            documents=default_chunks[i:i+100],
                            ids=[f"d{i+j}" for j in range(len(default_chunks[i:i+100]))])
                def retrieve_vs(q_emb, _col=col):
                    r = _col.query(query_embeddings=[q_emb.tolist()], n_results=5)
                    return r["documents"][0]

            elif retrieve_fn_builder == "qdrant":
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams, PointStruct
                qc = QdrantClient(":memory:")
                qc.create_collection("s", vectors_config=VectorParams(size=default_embs.shape[1], distance=Distance.COSINE))
                pts = [PointStruct(id=i, vector=default_embs[i].tolist(), payload={"t": default_chunks[i]}) for i in range(len(default_chunks))]
                for i in range(0, len(pts), 256): qc.upsert("s", pts[i:i+256])
                def retrieve_vs(q_emb, _qc=qc):
                    if hasattr(_qc, "query_points"):
                        result = _qc.query_points(collection_name="s", query=q_emb.tolist(), limit=5)
                        hits = result.points
                    else:
                        hits = _qc.search("s", query_vector=q_emb.tolist(), limit=5)
                    return [h.payload["t"] for h in hits]

            elif retrieve_fn_builder == "lancedb":
                import lancedb
                db_path = str(RESULTS_DIR / "lancedb_sweep")
                shutil.rmtree(db_path, ignore_errors=True)
                db = lancedb.connect(db_path)
                data = [{"vector": default_embs[i].tolist(), "text": default_chunks[i]} for i in range(len(default_chunks))]
                tbl = db.create_table("s", data=data, mode="overwrite")
                def retrieve_vs(q_emb, _tbl=tbl):
                    return [r["text"] for r in _tbl.search(q_emb.tolist()).limit(5).to_list()]

            elif retrieve_fn_builder == "milvus":
                from pymilvus import MilvusClient
                db_path = str(RESULTS_DIR / "milvus_sweep.db")
                mc = MilvusClient(uri=db_path)
                if mc.has_collection("s"): mc.drop_collection("s")
                mc.create_collection("s", dimension=default_embs.shape[1], metric_type="COSINE")
                data = [{"id": i, "vector": default_embs[i].tolist(), "text": default_chunks[i]} for i in range(len(default_chunks))]
                for i in range(0, len(data), 1000): mc.insert("s", data[i:i+1000])
                def retrieve_vs(q_emb, _mc=mc):
                    r = _mc.search("s", data=[q_emb.tolist()], limit=5, output_fields=["text"])[0]
                    return [h["entity"]["text"] for h in r]

            ingest_sec = time.time() - t0

            # Run 5 questions
            lats, sc_list = [], []
            for q in SAMPLE_QS:
                q_emb = encode_st(default_st, [q["question"]])[0]
                ctx_texts = retrieve_vs(q_emb)
                ctx = [{"sentence_chunk": t} for t in ctx_texts]
                prompt = prompt_formatter(q["question"], ctx)
                t_q = time.time()
                answer = default_gen(prompt)
                lats.append(time.time() - t_q)
                sc_list.append(judge({"question": q["question"], "ground_truth": q["ground_truth"], "answer": answer}, judge_fn))

            row = {
                "config":          vs_label,
                "num_chunks":      len(default_chunks),
                "ingest_sec":      round(ingest_sec, 2),
                "avg_latency_sec": round(float(np.mean(lats)), 2),
                "judge_score":     mean_score(sc_list),
                "sweep":           "vectorstore",
            }
        except Exception as e:
            print(f"  [FAILED: {e}]")
            row = {"config": vs_label, "judge_score": 0, "avg_latency_sec": 0,
                   "num_chunks": 0, "ingest_sec": 0, "sweep": "vectorstore", "error": str(e)}
        vs_results.append(row); all_results.append(row)
        print(f"     score={row['judge_score']}  latency={row['avg_latency_sec']}s")

    bar_chart(pd.DataFrame(vs_results), "config", "judge_score",
              "LLM-Judge Score by Vector Store", "chart_vectorstores.png", "#C44E52")

    # ── SWEEP D: LLMs ─────────────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("SWEEP D -- LLMs")
    print("-" * 50)
    llm_configs = []
    if HAS_CLAUDE:
        llm_configs.append(("L1_claude-haiku",  lambda p: call_claude(p, "claude-haiku-4-5")))
        llm_configs.append(("L2_claude-sonnet", lambda p: call_claude(p, "claude-sonnet-4-5")))
    if HAS_OPENAI:
        llm_configs.append(("L3_gpt4o-mini",    lambda p: call_openai(p, "gpt-4o-mini")))

    sweep_d = []
    for llm_label, gen_fn in llm_configs:
        print(f"\n  >> {llm_label}")
        row = run_combo(llm_label, default_chunks, default_embed, None, gen_fn, judge_fn)
        row["sweep"] = "llm"
        sweep_d.append(row); all_results.append(row)
        print(f"     score={row['judge_score']}  latency={row['avg_latency_sec']}s")
    if sweep_d:
        bar_chart(pd.DataFrame(sweep_d), "config", "judge_score",
                  "LLM-Judge Score by LLM", "chart_llms.png", "#8172B2")

    # ── Save all results + scatter ─────────────────────────────────────────
    df_all = pd.DataFrame(all_results)
    out_csv = RESULTS_DIR / "all_results.csv"
    df_all.to_csv(out_csv, index=False)
    print(f"\nAll results saved -> {out_csv}")
    scatter_chart(df_all)

    # ── Best combo -> RAGAS ───────────────────────────────────────────────
    best = df_all.loc[df_all["judge_score"].idxmax()]
    print(f"\n{'='*60}")
    print(f"BEST CONFIG: {best['config']}  judge_score={best['judge_score']}")
    print("Running full RAGAS evaluation on best config ...")

    # Reconstruct best chunks
    cid = best["config"].split("_")[0]
    if cid in ("C1","C2","C3","C4","C5","C6"):
        best_chunks = get_chunks(cid, raw_text)
    else:
        best_chunks = default_chunks

    df_ragas, df_judge = eval_mod.run_evaluation(best_chunks)

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL LEADERBOARD (by judge score)")
    print("=" * 60)
    summary_cols = [c for c in ["config","sweep","num_chunks","avg_latency_sec","judge_score"] if c in df_all.columns]
    print(df_all[summary_cols].sort_values("judge_score", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
