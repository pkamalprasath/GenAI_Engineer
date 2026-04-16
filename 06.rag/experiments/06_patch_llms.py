"""
06_patch_llms.py — Add L1_claude-haiku + L2_claude-sonnet to all_results.csv
"""

import json, time
import numpy as np
import pandas as pd
import faiss
import importlib.util

from config import RESULTS_DIR, TEST_QUESTIONS, prompt_formatter, CLAUDE_API_KEY, HAS_CLAUDE
from data_loader import load_document

SAMPLE_QS = TEST_QUESTIONS[:5]


def call_claude(prompt, model):
    import anthropic
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
                time.sleep(wait)
            else:
                raise


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
    vals = [(s.get("relevance",0)+s.get("correctness",0)+s.get("completeness",0))/3 for s in scores]
    return round(float(np.mean(vals)), 3) if vals else 0.0


def main():
    if not HAS_CLAUDE:
        print("ERROR: CLAUDE_API_KEY not set in .env")
        return

    print("=" * 60)
    print("06_patch_llms.py — L1 claude-haiku + L2 claude-sonnet")
    print("=" * 60)

    _, raw_text = load_document()

    spec = importlib.util.spec_from_file_location("chunking", "01_chunking.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("Building C1 chunks ...")
    chunks = mod.chunks_to_texts(mod.chunk_sentence(raw_text))
    print(f"  {len(chunks)} chunks")

    from sentence_transformers import SentenceTransformer
    print("Embedding with all-mpnet-base-v2 ...")
    st = SentenceTransformer("all-mpnet-base-v2", device="cpu")
    embs = st.encode(chunks, batch_size=32, normalize_embeddings=True,
                     convert_to_numpy=True, show_progress_bar=True).astype(np.float32)

    judge_fn = lambda p: call_claude(p, "claude-haiku-4-5")

    llm_configs = [
        ("L1_claude-haiku",  lambda p: call_claude(p, "claude-haiku-4-5")),
        ("L2_claude-sonnet", lambda p: call_claude(p, "claude-sonnet-4-5")),
    ]

    new_rows = []
    for label, gen_fn in llm_configs:
        print(f"\n>> {label}")
        try:
            latencies, scores = [], []
            for q in SAMPLE_QS:
                q_emb = st.encode([q["question"]], normalize_embeddings=True,
                                  convert_to_numpy=True).astype(np.float32)[0]
                sims    = embs @ q_emb
                top_idx = np.argsort(sims)[::-1][:5]
                ctx     = [{"sentence_chunk": chunks[i]} for i in top_idx]
                prompt  = prompt_formatter(q["question"], ctx)
                t0      = time.time()
                answer  = gen_fn(prompt)
                latencies.append(time.time() - t0)
                scores.append(judge({"question": q["question"],
                                     "ground_truth": q["ground_truth"],
                                     "answer": answer}, judge_fn))
            row = {
                "config":          label,
                "sweep":           "llm",
                "num_chunks":      len(chunks),
                "avg_latency_sec": round(float(np.mean(latencies)), 2),
                "judge_score":     mean_score(scores),
                "ingest_sec":      "",
                "error":           "",
            }
            new_rows.append(row)
            print(f"  score={row['judge_score']}  latency={row['avg_latency_sec']}s")
        except Exception as e:
            print(f"  [FAILED: {e}]")
            new_rows.append({"config": label, "sweep": "llm", "num_chunks": 0,
                             "avg_latency_sec": 0, "judge_score": 0,
                             "ingest_sec": 0, "error": str(e)})

    # Merge
    print("\nMerging into all_results.csv ...")
    path = RESULTS_DIR / "all_results.csv"
    df = pd.read_csv(path) if path.exists() else pd.DataFrame()
    patched = [r["config"] for r in new_rows]
    if not df.empty:
        df = df[~df["config"].isin(patched)]
    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    df.to_csv(path, index=False)
    print(f"Saved -> {path}  ({len(df)} rows total)")

    print("\nLLM sweep results:")
    llm_df = df[df["sweep"] == "llm"][["config", "avg_latency_sec", "judge_score"]]
    print(llm_df.to_string(index=False))


if __name__ == "__main__":
    main()
