"""
05_evaluation.py  —  Evaluate RAG quality (no LangChain in core pipeline).

Two methods:
  1. RAGAS  — faithfulness, answer_relevancy, context_precision, context_recall
               Judge LLM: Claude claude-haiku-4-5 via langchain_anthropic wrapper
  2. LLM-as-Judge  — Claude/OpenAI scores each answer 1-5 on relevance,
                      correctness, completeness; returns JSON

Core pipeline mirrors Data_ingestion.ipynb exactly:
  - FAISS retrieval with dot-product on normalised all-mpnet-base-v2 embeddings
  - prompt_formatter() from config.py (same as notebook)

Run:  python 05_evaluation.py
Output: results/eval_ragas.csv  +  results/eval_llm_judge.csv
"""

import json
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


# ── FAISS retriever ───────────────────────────────────────────────────────

def build_retriever(chunks: list[str]):
    embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
    embs = embedder.encode(
        chunks, batch_size=32, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True
    ).astype(np.float32)
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs)
    return embedder, index, chunks


def retrieve(query: str, embedder, index, chunks, top_k: int = 5) -> list[dict]:
    q = embedder.encode([query], normalize_embeddings=True,
                        convert_to_numpy=True).astype(np.float32)
    scores, idxs = index.search(q, top_k)
    return [{"sentence_chunk": chunks[i], "score": float(scores[0][j])}
            for j, i in enumerate(idxs[0]) if i < len(chunks)]


# ── LLM generate ─────────────────────────────────────────────────────────

def call_claude(prompt: str, model: str = "claude-haiku-4-5", max_tokens: int = 512) -> str:
    import anthropic, time
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    for attempt in range(5):
        try:
            msg = client.messages.create(
                model=model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"   [overloaded, retrying in {wait}s]")
                time.sleep(wait)
            else:
                raise


def call_openai(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 512) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


def get_default_generator():
    if HAS_CLAUDE:
        return lambda p: call_claude(p, "claude-haiku-4-5")
    elif HAS_OPENAI:
        return lambda p: call_openai(p, "gpt-4o-mini")
    raise RuntimeError("No LLM available. Set CLAUDE_API_KEY or OPENAI_API_KEY in .env")


# ── Build RAG dataset ─────────────────────────────────────────────────────

def build_rag_dataset(questions: list[dict], embedder, index, chunks,
                      generate_fn) -> list[dict]:
    records = []
    for q in tqdm(questions, desc="RAG answers"):
        ctx = retrieve(q["question"], embedder, index, chunks)
        prompt = prompt_formatter(q["question"], ctx)
        t0 = time.time()
        answer = generate_fn(prompt)
        records.append({
            "question":     q["question"],
            "answer":       answer,
            "contexts":     [c["sentence_chunk"] for c in ctx],
            "ground_truth": q["ground_truth"],
            "latency_sec":  round(time.time() - t0, 2),
        })
    return records


# ── Method 1: RAGAS ───────────────────────────────────────────────────────

def run_ragas(records: list[dict]) -> pd.DataFrame:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.run_config import RunConfig
    from ragas.metrics import (
        faithfulness, answer_relevancy,
        context_precision, context_recall,
    )
    run_cfg = RunConfig(timeout=None)

    dataset = Dataset.from_dict({
        "question":    [r["question"] for r in records],
        "answer":      [r["answer"] for r in records],
        "contexts":    [r["contexts"] for r in records],
        "ground_truth":[r["ground_truth"] for r in records],
    })

    # Configure judge LLM
    if HAS_CLAUDE:
        from langchain_anthropic import ChatAnthropic
        from ragas.llms import LangchainLLMWrapper
        from sentence_transformers import SentenceTransformer as ST
        from ragas.embeddings import BaseRagasEmbeddings

        # Thin wrapper so RAGAS can use sentence-transformers for embedding
        class STEmbeddings(BaseRagasEmbeddings):
            def __init__(self):
                self._model = ST("all-MiniLM-L6-v2", device="cpu")
            def embed_query(self, text: str) -> list[float]:
                return self._model.encode([text], normalize_embeddings=True)[0].tolist()
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return self._model.encode(texts, normalize_embeddings=True).tolist()
            async def aembed_query(self, text: str) -> list[float]:
                return self.embed_query(text)
            async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
                return self.embed_documents(texts)

        llm = LangchainLLMWrapper(
            ChatAnthropic(model="claude-haiku-4-5", api_key=CLAUDE_API_KEY, max_tokens=1024)
        )
        emb = STEmbeddings()
        print("  RAGAS judge: Claude claude-haiku-4-5  embeddings: all-MiniLM-L6-v2")
        import asyncio
        result = asyncio.run(evaluate(dataset,
                          metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                          llm=llm, embeddings=emb, run_config=run_cfg, is_async=True))
    elif HAS_OPENAI:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY))
        emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(api_key=OPENAI_API_KEY))
        print("  RAGAS judge: gpt-4o-mini")
        import asyncio
        result = asyncio.run(evaluate(dataset,
                          metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                          llm=llm, embeddings=emb, run_config=run_cfg, is_async=True))
    else:
        raise RuntimeError("RAGAS requires CLAUDE_API_KEY or OPENAI_API_KEY")

    df = result.to_pandas()
    out = RESULTS_DIR / "eval_ragas.csv"
    df.to_csv(out, index=False)
    print(f"\nRAGAS saved -> {out}")

    metric_cols = [c for c in ["faithfulness","answer_relevancy","context_precision","context_recall"]
                   if c in df.columns]
    print("\nRAGAS mean scores:")
    for col in metric_cols:
        print(f"  {col}: {round(float(df[col].mean()), 4)}")
    return df


# ── Method 2: LLM-as-Judge ────────────────────────────────────────────────

JUDGE_PROMPT = """\
You are an expert evaluator for RAG systems.
Score the answer below on three dimensions using integers 1-5:
  relevance    — Is the answer on-topic for the question?
  correctness  — Is the answer factually correct per the ground truth?
  completeness — Does the answer cover the key points in the ground truth?

Return ONLY valid JSON, no other text:
{{"relevance":<int>,"correctness":<int>,"completeness":<int>,"reasoning":"<one sentence>"}}

Question:     {question}
Ground Truth: {ground_truth}
RAG Answer:   {answer}
"""


def judge_one(record: dict, judge_fn) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=record["question"],
        ground_truth=record["ground_truth"],
        answer=record["answer"],
    )
    try:
        raw = judge_fn(prompt)
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {"relevance": 0, "correctness": 0, "completeness": 0, "reasoning": "parse_error"}


def run_llm_judge(records: list[dict]) -> pd.DataFrame:
    if HAS_CLAUDE:
        judge_fn = lambda p: call_claude(p, "claude-haiku-4-5", max_tokens=128)
        judge_name = "Claude claude-haiku-4-5"
    elif HAS_OPENAI:
        judge_fn = lambda p: call_openai(p, "gpt-4o-mini", max_tokens=128)
        judge_name = "gpt-4o-mini"
    else:
        raise RuntimeError("No judge LLM available")

    print(f"  Judge: {judge_name}")
    rows = []
    for rec in tqdm(records, desc="LLM-as-Judge"):
        scores = judge_one(rec, judge_fn)
        rows.append({
            "question":     rec["question"],
            "latency_sec":  rec["latency_sec"],
            "relevance":    scores.get("relevance", 0),
            "correctness":  scores.get("correctness", 0),
            "completeness": scores.get("completeness", 0),
            "reasoning":    scores.get("reasoning", ""),
            "answer_preview": rec["answer"][:80],
        })

    df = pd.DataFrame(rows)
    out = RESULTS_DIR / "eval_llm_judge.csv"
    df.to_csv(out, index=False)
    print(f"\nLLM-judge saved -> {out}")
    print("\nLLM-as-Judge mean scores (out of 5):")
    for col in ["relevance", "correctness", "completeness"]:
        print(f"  {col}: {round(float(df[col].mean()), 2)}")
    return df


# ── Main ──────────────────────────────────────────────────────────────────

def run_evaluation(chunks: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Building FAISS retriever ...")
    embedder, index, chunks = build_retriever(chunks)
    generate_fn = get_default_generator()

    print("\nGenerating RAG answers ...")
    records = build_rag_dataset(TEST_QUESTIONS, embedder, index, chunks, generate_fn)

    print("\n-- Method 1: RAGAS ------------------------------------------")
    df_ragas = run_ragas(records)

    print("\n-- Method 2: LLM-as-Judge -----------------------------------")
    df_judge = run_llm_judge(records)

    return df_ragas, df_judge


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 05 -- Evaluation (RAGAS + LLM-as-Judge)")
    print("=" * 60)

    _, raw_text = load_document()

    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("\nBuilding C1 sentence chunks ...")
    chunk_dicts = mod.chunk_sentence(raw_text)
    chunks = mod.chunks_to_texts(chunk_dicts)
    print(f"Chunks: {len(chunks)}\n")

    df_ragas, df_judge = run_evaluation(chunks)

    print("\n" + "=" * 60)
    ragas_cols = [c for c in ["faithfulness","answer_relevancy","context_precision","context_recall"]
                  if c in df_ragas.columns]
    if ragas_cols and "question" in df_ragas.columns:
        print("RAGAS per-question:")
        print(df_ragas[["question"] + ragas_cols].to_string(index=False))
    elif ragas_cols:
        print("RAGAS per-question:")
        print(df_ragas[ragas_cols].to_string(index=False))
    print("\nLLM-Judge per-question:")
    print(df_judge[["question","relevance","correctness","completeness"]].to_string(index=False))
