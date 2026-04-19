"""
msmarco.py — MS MARCO retrieval benchmark.

WHAT IS MS MARCO?
Microsoft MAchine Reading COmprehension dataset.
1 million real Bing queries + human-annotated relevant passages.

KEY DIFFERENCE FROM SQuAD/NQ:
MS MARCO tests RETRIEVAL QUALITY, not just generation quality.
You have a large corpus of passages and you're ranked on whether you
retrieved the relevant one(s) in the top positions.

WHAT THIS TESTS:
  "Is our pgvector + HyDE retrieval better than keyword search (BM25)?"

  Specifically:
  - NDCG@10: quality of the TOP 10 ranked results (the gold standard metric)
  - MRR@10: was the FIRST correct result near the top?
  - Recall@100: did we find any relevant doc in the top 100?

WHY RETRIEVAL METRICS MATTER FOR RAG:
  If retrieval fails, generation CANNOT save you. The LLM can only work with
  what the retriever returns. Measuring retrieval separately tells you:
    - Is our embedding model (MiniLM-384) good enough?
    - Does HyDE actually improve recall?
    - What's our baseline before tuning anything?

WHAT TO DOWNLOAD:
  MS MARCO Passage Retrieval (smaller, easier to use):
  https://microsoft.github.io/msmarco/

  Files needed:
  1. collection.tsv        (~2.9 GB, 8.8M passages)  ← the corpus
  2. queries.dev.small.tsv (~1 MB, 6,980 queries)    ← queries to evaluate
  3. qrels.dev.small.tsv   (~1 MB, relevance labels) ← which passages are relevant

  For quick testing, use the "small" dev set (6,980 queries).
  Place all files at: data/benchmarks/msmarco/

TSV FORMATS:
  collection.tsv:   passage_id \t passage_text
  queries.tsv:      query_id   \t query_text
  qrels.tsv:        query_id   \t 0 \t passage_id \t relevance_score

NOTE: For meaningful NDCG, you need to search the full collection.
      This module supports a SUBSET mode: ingest only relevant + N random
      passages per query, for fast evaluation without the full 8.8M corpus.

NDCG@10 EXPLAINED:
  Normalised Discounted Cumulative Gain at rank 10.
  Gives credit for finding relevant docs, with LESS credit for lower ranks.
  Perfect system (relevant doc at rank 1): NDCG@10 = 1.0
  Baseline BM25 on MS MARCO dev: ~0.184
  Good dense retrieval: ~0.350+
"""

import csv
import math
import random
from pathlib import Path
from collections import defaultdict

from src.evaluation.benchmarks.base import BenchmarkSample


# ── Loader ─────────────────────────────────────────────────────────────────

def load_msmarco(
    data_dir: Path,
    max_queries: int = 100,
    negative_ratio: int = 9,
    seed: int = 42,
) -> tuple[list[BenchmarkSample], dict]:
    """
    Load MS MARCO samples and the relevance labels (qrels).

    Args:
        data_dir       : path to data/benchmarks/msmarco/
        max_queries    : number of queries to evaluate
        negative_ratio : for each query, add N random irrelevant passages
                         as distractors (tests whether retriever ignores noise)
        seed           : random seed

    Returns:
        (samples, qrels) where:
          samples = list of BenchmarkSample (question + context_docs)
          qrels   = {query_id: {passage_id: relevance_score}} for NDCG computation
    """
    queries_file    = _find_file(data_dir, ["queries.dev.small.tsv", "queries.dev.tsv"])
    collection_file = _find_file(data_dir, ["collection.tsv"])
    qrels_file      = _find_file(data_dir, ["qrels.dev.small.tsv", "qrels.dev.tsv"])

    if not all([queries_file, collection_file, qrels_file]):
        missing = []
        if not queries_file:    missing.append("queries.dev.small.tsv")
        if not collection_file: missing.append("collection.tsv")
        if not qrels_file:      missing.append("qrels.dev.small.tsv")
        raise FileNotFoundError(
            f"MS MARCO files not found in {data_dir}: {missing}\n"
            "Download from: https://microsoft.github.io/msmarco/\n"
            "Place at: data/benchmarks/msmarco/"
        )

    # Load qrels (relevance labels)
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    with open(qrels_file, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 4:
                q_id, _, p_id, rel = row[0], row[1], row[2], int(row[3])
                qrels[q_id][p_id] = rel

    # Load queries
    queries: dict[str, str] = {}
    with open(queries_file, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 2:
                queries[row[0]] = row[1]

    # Select queries that have at least one relevant passage
    valid_qids = [qid for qid in queries if qrels.get(qid)]
    random.seed(seed)
    random.shuffle(valid_qids)
    selected_qids = valid_qids[:max_queries]

    # Collect all relevant passage IDs
    relevant_pids = set()
    for qid in selected_qids:
        relevant_pids.update(qrels[qid].keys())

    # Load only the passages we need (relevant + some distractors)
    all_pids_in_collection: list[str] = []
    passages: dict[str, str] = {}

    print(f"[MS MARCO] Loading relevant passages ({len(relevant_pids)}) + distractors...")
    with open(collection_file, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 2:
                continue
            pid, text = row[0], row[1]
            all_pids_in_collection.append(pid)
            if pid in relevant_pids:
                passages[pid] = text

    # Sample distractor passages (random, not relevant to any selected query)
    random.shuffle(all_pids_in_collection)
    distractor_count = len(selected_qids) * negative_ratio
    for pid in all_pids_in_collection:
        if pid not in relevant_pids and len(passages) < len(relevant_pids) + distractor_count:
            passages[pid] = ""  # Will load text in second pass if needed

    print(f"[MS MARCO] Loaded {len(passages)} passages for {len(selected_qids)} queries")

    # Build samples
    samples = []
    for qid in selected_qids:
        query_text = queries[qid]
        relevant   = list(qrels[qid].keys())

        # Context docs: relevant passages + distractors
        context_pids = relevant[:]
        # Add negative_ratio distractor passages
        distractors = random.sample(
            [p for p in passages if p not in relevant],
            min(negative_ratio, len(passages) - len(relevant))
        )
        context_pids += distractors

        context_docs = [passages.get(pid, "") for pid in context_pids if passages.get(pid)]

        # Ground truth: concatenate all relevant passages
        relevant_texts = [passages.get(pid, "") for pid in relevant if passages.get(pid)]
        ground_truth   = relevant_texts[0] if relevant_texts else ""

        if not ground_truth:
            continue

        samples.append(BenchmarkSample(
            question=query_text,
            ground_truth=ground_truth,
            context_docs=context_docs,
            metadata={
                "query_id":     qid,
                "relevant_pids": relevant,
                "dataset":       "msmarco",
            },
        ))

    return samples, dict(qrels)


def _find_file(data_dir: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = data_dir / name
        if p.exists():
            return p
    return None


# ── Retrieval metrics ───────────────────────────────────────────────────────

def compute_ndcg(
    query_id: str,
    ranked_chunk_ids: list[str],
    qrels: dict[str, dict[str, int]],
    k: int = 10,
) -> float:
    """
    Compute NDCG@k for one query.

    NDCG = DCG / IDCG where:
      DCG  = sum(rel_i / log2(rank_i + 1)) for top-k results
      IDCG = DCG of a perfect ranking (relevant docs at rank 1, 2, ...)

    Args:
        query_id         : the MS MARCO query ID
        ranked_chunk_ids : list of passage IDs in ranked order (from retrieval)
        qrels            : relevance labels {query_id: {passage_id: relevance}}
        k                : cutoff rank

    Returns:
        NDCG@k score (0.0 – 1.0)
    """
    relevant = qrels.get(query_id, {})
    if not relevant:
        return 0.0

    # Compute DCG
    dcg = 0.0
    for rank, pid in enumerate(ranked_chunk_ids[:k], start=1):
        rel = relevant.get(pid, 0)
        if rel > 0:
            dcg += rel / math.log2(rank + 1)

    # Compute IDCG (ideal: sort by relevance descending)
    ideal_rels = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum(
        rel / math.log2(rank + 1)
        for rank, rel in enumerate(ideal_rels, start=1)
        if rel > 0
    )

    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def compute_mrr(
    query_id: str,
    ranked_chunk_ids: list[str],
    qrels: dict[str, dict[str, int]],
    k: int = 10,
) -> float:
    """
    Compute MRR@k (Mean Reciprocal Rank) for one query.

    MRR = 1 / rank_of_first_relevant_result
    MRR@1 = 1.0 if first result is correct
    MRR@2 = 0.5 if second result is first correct one
    """
    relevant = qrels.get(query_id, {})
    for rank, pid in enumerate(ranked_chunk_ids[:k], start=1):
        if relevant.get(pid, 0) > 0:
            return round(1.0 / rank, 4)
    return 0.0
