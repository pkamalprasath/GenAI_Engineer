"""
03_vectorstores.py  —  Compare 6 free local vector stores (no paid services, no server).

Stores:
  V0  PyTorch Tensor  torch.topk on dot-product  (IDENTICAL to Data_ingestion.ipynb)
  V1  FAISS           faiss-cpu, in-memory
  V2  ChromaDB        chromadb, persistent local file
  V3  Qdrant          qdrant-client, in-memory mode
  V4  LanceDB         lancedb, embedded local file
  V5  Milvus          pymilvus Milvus Lite, local file (Linux/Mac only)

All use all-mpnet-base-v2 (CPU) for fair comparison.
Retrieval: dot product on L2-normalised vectors (same as Data_ingestion.ipynb).

Run:  python 03_vectorstores.py
Output: results/vectorstore_stats.csv
"""

import time
import importlib.util
import shutil
import numpy as np
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from config import RESULTS_DIR, TEST_QUESTIONS
from data_loader import load_document

EMBED_MODEL = "all-mpnet-base-v2"


# ── V0: PyTorch Tensor — identical to Data_ingestion.ipynb ───────────────

def build_torch(chunks: list[str], embedder) -> dict:
    """
    Store embeddings as a plain torch.Tensor.
    Retrieval via torch.topk on dot-product scores —
    exactly the same as Data_ingestion.ipynb.
    """
    import torch
    from sentence_transformers import util as st_util

    print("  Building PyTorch tensor store ...")
    embs = embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=False, show_progress_bar=True,
        convert_to_tensor=True,
    )  # shape: (N, D), torch.Tensor on CPU
    return {"name": "V0_PyTorch", "embeddings": embs, "chunks": chunks, "embedder": embedder}


def query_torch(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    import torch
    from sentence_transformers import util as st_util

    q_emb = store["embedder"].encode(
        query, normalize_embeddings=True, convert_to_tensor=True
    )
    # dot_score — same function used in Data_ingestion.ipynb
    dot_scores = st_util.dot_score(q_emb, store["embeddings"])[0]
    scores, indices = torch.topk(dot_scores, k=min(top_k, len(store["chunks"])))
    return [(store["chunks"][i], float(s)) for i, s in zip(indices.tolist(), scores.tolist())]


# ── Shared embedder ───────────────────────────────────────────────────────

def load_embedder():
    print(f"Loading embedder: {EMBED_MODEL} (CPU) ...")
    return SentenceTransformer(EMBED_MODEL, device="cpu")


def encode(embedder, texts: list[str], desc: str = "Embedding") -> np.ndarray:
    return embedder.encode(
        texts, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True
    ).astype(np.float32)


# ── V1: FAISS (identical retrieval to Data_ingestion.ipynb) ──────────────

def build_faiss(chunks: list[str], embedder) -> dict:
    import faiss
    embs = encode(embedder, chunks, "FAISS ingest")
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs)
    return {"name": "V1_FAISS", "index": index, "chunks": chunks, "embedder": embedder}


def query_faiss(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    q = encode(store["embedder"], [query])
    scores, indices = store["index"].search(q, top_k)
    return [(store["chunks"][i], float(scores[0][j]))
            for j, i in enumerate(indices[0]) if i < len(store["chunks"])]


# ── V2: ChromaDB ──────────────────────────────────────────────────────────

def build_chroma(chunks: list[str], embedder) -> dict:
    import chromadb
    persist = str(RESULTS_DIR / "chroma_db")
    client = chromadb.PersistentClient(path=persist)
    try:
        client.delete_collection("rag_exp")
    except Exception:
        pass
    col = client.create_collection("rag_exp", metadata={"hnsw:space": "cosine"})
    embs = encode(embedder, chunks, "Chroma ingest")
    batch = 100
    for i in tqdm(range(0, len(chunks), batch), desc="Chroma add"):
        col.add(
            embeddings=embs[i: i + batch].tolist(),
            documents=chunks[i: i + batch],
            ids=[f"d{i+j}" for j in range(len(chunks[i: i + batch]))],
        )
    return {"name": "V2_ChromaDB", "col": col, "embedder": embedder}


def query_chroma(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    q = encode(store["embedder"], [query]).tolist()
    res = store["col"].query(query_embeddings=q, n_results=top_k)
    docs = res["documents"][0]
    dists = res["distances"][0]          # cosine distance (lower = better)
    sims = [1.0 - d for d in dists]
    return list(zip(docs, sims))


# ── V3: Qdrant in-memory ──────────────────────────────────────────────────

def build_qdrant(chunks: list[str], embedder) -> dict:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct

    client = QdrantClient(":memory:")
    embs = encode(embedder, chunks, "Qdrant ingest")
    dim = embs.shape[1]

    client.create_collection(
        collection_name="rag",
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    points = [
        PointStruct(id=i, vector=embs[i].tolist(), payload={"text": chunks[i]})
        for i in range(len(chunks))
    ]
    # upload in batches
    batch = 256
    for i in tqdm(range(0, len(points), batch), desc="Qdrant add"):
        client.upsert(collection_name="rag", points=points[i: i + batch])

    return {"name": "V3_Qdrant", "client": client, "embedder": embedder}


def query_qdrant(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    q = encode(store["embedder"], [query])[0].tolist()
    client = store["client"]
    # qdrant-client >=1.7 uses query_points(); older versions use search()
    if hasattr(client, "query_points"):
        result = client.query_points(collection_name="rag", query=q, limit=top_k)
        hits = result.points
    else:
        hits = client.search(collection_name="rag", query_vector=q, limit=top_k)
    return [(h.payload["text"], h.score) for h in hits]


# ── V4: LanceDB ───────────────────────────────────────────────────────────

def build_lancedb(chunks: list[str], embedder) -> dict:
    import lancedb
    db_path = str(RESULTS_DIR / "lancedb")
    shutil.rmtree(db_path, ignore_errors=True)
    db = lancedb.connect(db_path)

    embs = encode(embedder, chunks, "LanceDB ingest")
    data = [
        {"vector": embs[i].tolist(), "text": chunks[i]}
        for i in range(len(chunks))
    ]
    tbl = db.create_table("rag", data=data, mode="overwrite")
    return {"name": "V4_LanceDB", "table": tbl, "embedder": embedder}


def query_lancedb(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    q = encode(store["embedder"], [query])[0].tolist()
    results = store["table"].search(q).limit(top_k).to_list()
    return [(r["text"], 1.0 - r.get("_distance", 0)) for r in results]


# ── V5: Milvus Lite ───────────────────────────────────────────────────────

def build_milvus(chunks: list[str], embedder) -> dict:
    from pymilvus import MilvusClient

    db_path = str(RESULTS_DIR / "milvus_lite.db")
    client = MilvusClient(uri=db_path)

    embs = encode(embedder, chunks, "Milvus ingest")
    dim = embs.shape[1]

    if client.has_collection("rag"):
        client.drop_collection("rag")
    client.create_collection(
        collection_name="rag",
        dimension=dim,
        metric_type="COSINE",
    )
    data = [
        {"id": i, "vector": embs[i].tolist(), "text": chunks[i]}
        for i in range(len(chunks))
    ]
    batch = 1000
    for i in tqdm(range(0, len(data), batch), desc="Milvus add"):
        client.insert(collection_name="rag", data=data[i: i + batch])

    return {"name": "V5_Milvus_Lite", "client": client, "embedder": embedder}


def query_milvus(store: dict, query: str, top_k: int = 5) -> list[tuple[str, float]]:
    q = encode(store["embedder"], [query])[0].tolist()
    results = store["client"].search(
        collection_name="rag",
        data=[q],
        limit=top_k,
        output_fields=["text"],
    )[0]
    return [(r["entity"]["text"], r["distance"]) for r in results]


# ── Benchmark ─────────────────────────────────────────────────────────────

def benchmark(name: str, build_fn, query_fn, chunks: list[str], embedder) -> dict:
    t0 = time.time()
    try:
        store = build_fn(chunks, embedder)
    except Exception as e:
        print(f"  [BUILD FAILED: {e}]")
        return {"store": name, "status": "build_failed", "error": str(e)}
    ingest_sec = time.time() - t0
    print(f"  Ingest: {ingest_sec:.2f}s")

    query_times, top1_sims = [], []
    for q in tqdm(TEST_QUESTIONS, desc=f"Querying {name}"):
        t_q = time.time()
        try:
            hits = query_fn(store, q["question"])
            query_times.append(time.time() - t_q)
            if hits:
                top1_sims.append(hits[0][1])
        except Exception as e:
            print(f"  [QUERY ERROR: {e}]")

    return {
        "store":              name,
        "num_chunks":         len(chunks),
        "ingest_time_sec":    round(ingest_sec, 2),
        "avg_query_ms":       round(float(np.mean(query_times)) * 1000, 1) if query_times else 0,
        "p99_query_ms":       round(float(np.percentile(query_times, 99)) * 1000, 1) if query_times else 0,
        "avg_top1_similarity": round(float(np.mean(top1_sims)), 4) if top1_sims else 0,
        "status":             "ok",
    }


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_vectorstores(chunks: list[str]) -> pd.DataFrame:
    embedder = load_embedder()

    stores = [
        ("V0_PyTorch",     build_torch,   query_torch),
        ("V1_FAISS",       build_faiss,   query_faiss),
        ("V2_ChromaDB",    build_chroma,  query_chroma),
        ("V3_Qdrant",      build_qdrant,  query_qdrant),
        ("V4_LanceDB",     build_lancedb, query_lancedb),
        ("V5_Milvus_Lite", build_milvus,  query_milvus),
    ]

    results = []
    for name, build_fn, query_fn in stores:
        print(f"\n>> {name}")
        stats = benchmark(name, build_fn, query_fn, chunks, embedder)
        results.append(stats)
        print(f"   -> {stats}")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "vectorstore_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 03 -- Vector Stores")
    print("=" * 60)

    _, raw_text = load_document()

    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunk_dicts = mod.chunk_sentence(raw_text)
    chunks = mod.chunks_to_texts(chunk_dicts)
    print(f"Chunks: {len(chunks)}\n")

    df = run_all_vectorstores(chunks)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
