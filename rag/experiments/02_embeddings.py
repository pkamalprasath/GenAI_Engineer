"""
02_embeddings.py  —  Compare 6 embedding models (no LangChain wrappers).

Models:
  E1  all-mpnet-base-v2          768-dim  SentenceTransformers  ~420 MB  CPU
  E2  all-MiniLM-L6-v2           384-dim  SentenceTransformers  ~80 MB   CPU
  E3  BAAI/bge-small-en-v1.5     384-dim  SentenceTransformers  ~130 MB  CPU
  E4  text-embedding-3-small     1536-dim OpenAI API            cloud
  E5  BAAI/bge-small-en-v1.5     384-dim  FastEmbed (Qdrant)    ~130 MB  CPU
  E6  embed-english-light-v3.0   384-dim  Cohere API            cloud (free tier)

Evaluation proxy: for each model, encode all chunks + 10 queries,
compute mean top-1 cosine similarity (higher = better retrieval signal).

Run:  python 02_embeddings.py
Output: results/embedding_stats.csv
"""

import time
import numpy as np
import pandas as pd
from tqdm import tqdm

from config import RESULTS_DIR, TEST_QUESTIONS, HAS_OPENAI, OPENAI_API_KEY, HAS_COHERE, COHERE_API_KEY
from data_loader import load_document


# ── Embedding functions ───────────────────────────────────────────────────

def embed_sentence_transformers(texts: list[str], model_name: str) -> np.ndarray:
    """E1 / E2 / E3 — pure SentenceTransformers, CPU."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name, device="cpu")
    embs = model.encode(
        texts, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True
    )
    return embs.astype(np.float32)


def embed_openai(texts: list[str], model_name: str = "text-embedding-3-small") -> np.ndarray:
    """E4 — OpenAI API."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    all_embs = []
    batch = 100
    for i in tqdm(range(0, len(texts), batch), desc="OpenAI embed"):
        resp = client.embeddings.create(input=texts[i: i + batch], model=model_name)
        all_embs.extend([e.embedding for e in resp.data])
    embs = np.array(all_embs, dtype=np.float32)
    # normalise
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


def embed_fastembed(texts: list[str], model_name: str = "BAAI/bge-small-en-v1.5") -> np.ndarray:
    """E5 — FastEmbed (Qdrant's CPU-optimised ONNX-based library)."""
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=model_name)
    embs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


def embed_cohere(texts: list[str], model_name: str = "embed-english-light-v3.0") -> np.ndarray:
    """E6 — Cohere API (free tier: 1 000 req/month)."""
    import cohere
    co = cohere.Client(api_key=COHERE_API_KEY)
    all_embs = []
    batch = 96   # Cohere max batch
    for i in tqdm(range(0, len(texts), batch), desc="Cohere embed"):
        resp = co.embed(
            texts=texts[i: i + batch],
            model=model_name,
            input_type="search_document",
        )
        all_embs.extend(resp.embeddings)
    embs = np.array(all_embs, dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return (embs / norms).astype(np.float32)


# ── Quality proxy ─────────────────────────────────────────────────────────

def retrieval_proxy(chunk_embs: np.ndarray, query_embs: np.ndarray) -> float:
    """
    Mean top-1 dot-product similarity across all queries.
    (Same retrieval logic as Data_ingestion.ipynb — dot product on normalised vecs.)
    """
    scores = []
    for q_emb in query_embs:
        sims = chunk_embs @ q_emb          # (N,)
        scores.append(float(np.max(sims)))
    return round(float(np.mean(scores)), 4)


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_embedding_models(chunks: list[str]) -> pd.DataFrame:
    questions = [q["question"] for q in TEST_QUESTIONS]
    results = []

    def _has_fastembed():
        try: import fastembed; return True
        except ImportError: return False

    # ── Registry ──────────────────────────────────────────────────────────
    models = [
        # (id, label, backend, model_name, enabled)
        ("E1", "all-mpnet-base-v2",          "st",        "all-mpnet-base-v2",          True),
        ("E2", "all-MiniLM-L6-v2",           "st",        "all-MiniLM-L6-v2",           True),
        ("E3", "BAAI/bge-small-en-v1.5 (ST)","st",        "BAAI/bge-small-en-v1.5",     True),
        ("E4", "text-embedding-3-small",      "openai",    "text-embedding-3-small",      HAS_OPENAI),
        ("E5", "bge-small FastEmbed",         "fastembed", "BAAI/bge-small-en-v1.5",     _has_fastembed()),
        ("E6", "embed-english-light Cohere",  "cohere",    "embed-english-light-v3.0",   HAS_COHERE),
    ]

    for eid, label, backend, model_name, enabled in models:
        if not enabled:
            reason = "OPENAI_API_KEY" if backend == "openai" else "COHERE_API_KEY"
            print(f"\n>> {eid} {label}  [SKIPPED — {reason} not set]")
            continue

        print(f"\n>> {eid} {label}  [{backend}]")
        t0 = time.time()

        try:
            if backend == "st":
                chunk_embs = embed_sentence_transformers(chunks, model_name)
                query_embs = embed_sentence_transformers(questions, model_name)
            elif backend == "openai":
                chunk_embs = embed_openai(chunks, model_name)
                query_embs = embed_openai(questions, model_name)
            elif backend == "fastembed":
                chunk_embs = embed_fastembed(chunks, model_name)
                query_embs = embed_fastembed(questions, model_name)
            elif backend == "cohere":
                chunk_embs = embed_cohere(chunks, model_name)
                import cohere
                co = cohere.Client(api_key=COHERE_API_KEY)
                resp = co.embed(texts=questions, model=model_name, input_type="search_query")
                query_embs_raw = np.array(resp.embeddings, dtype=np.float32)
                norms = np.linalg.norm(query_embs_raw, axis=1, keepdims=True) + 1e-9
                query_embs = (query_embs_raw / norms).astype(np.float32)
            else:
                continue
        except Exception as e:
            print(f"   [FAILED: {e}]")
            results.append({"id": eid, "model": label, "backend": backend,
                            "dims": 0, "embed_time_sec": 0, "top1_sim_proxy": 0,
                            "status": f"failed: {e}"})
            continue

        elapsed = time.time() - t0
        proxy = retrieval_proxy(chunk_embs, query_embs)
        dims  = chunk_embs.shape[1]

        row = {
            "id":              eid,
            "model":           label,
            "backend":         backend,
            "dims":            dims,
            "embed_time_sec":  round(elapsed, 2),
            "top1_sim_proxy":  proxy,
            "status":          "ok",
        }
        results.append(row)
        print(f"   dims={dims}  time={elapsed:.1f}s  top1_sim={proxy}")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "embedding_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    return df


if __name__ == "__main__":
    import importlib.util
    print("=" * 60)
    print("Experiment 02 -- Embedding Models")
    print("=" * 60)

    _, raw_text = load_document()

    # Build chunks with C1 (sentence-based, same as notebook)
    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunk_dicts = mod.chunk_sentence(raw_text)
    chunks = mod.chunks_to_texts(chunk_dicts)
    print(f"Chunks: {len(chunks)}\n")

    df = run_all_embedding_models(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
