"""
metrics.py — Retrieval and system evaluation metrics.

WHY THESE METRICS?
LLM-as-judge (from your experiments) measures answer QUALITY.
But it doesn't tell you WHY the quality is good or bad.

For production systems, you also need to know:
  - Is the RETRIEVAL finding the right chunks? (MRR, Recall@k)
  - Is the answer FACTUALLY GROUNDED? (Factuality %)
  - Is the SYSTEM fast enough? (Latency P99)

FROM THE IMPLEMENTATION GUIDE:
  "MRR (Mean Reciprocal Rank): How fast you find the right answer"
  "NDCG (Normalized DCG): Quality of ranked results"
  "Recall@k: % of correct answers in top-k results"
  "Precision@k: % of top-k results that are correct"

FROM THE CASE STUDY:
  "Accuracy (Precision) > 95% — HIGH priority"
  "Recall > 90% — HIGH priority"
  "P99 Latency < 2 seconds — CRITICAL"
  "Cost per query < $0.01 — HIGH priority"

EVALUATION WORKFLOW:
1. For each test question, run the full RAG pipeline
2. Check whether the correct chunk was retrieved (requires ground truth chunk IDs)
3. Score the answer quality with LLM-as-judge
4. Measure latency and estimate cost
"""

import time
from dataclasses import dataclass, field

import pandas as pd

from src.evaluation.judge import judge_answer, judge_factuality
from src.retrieval.retriever import Retriever
from src.retrieval.crag import score_chunks, filter_chunks
from src.generation.generator import generate


@dataclass
class EvalResult:
    """Results for one test question."""
    question:        str
    ground_truth:    str
    answer:          str
    retrieved_chunks: list[dict]
    confidence:      str
    latency_sec:     float
    judge_scores:    dict       # {relevance, correctness, completeness, avg_score}
    factuality:      dict       # {factual_claims, supported_claims, factuality_score}
    sources:         list[dict]


@dataclass
class EvalSummary:
    """Aggregated metrics across all test questions."""
    num_questions:   int
    avg_judge_score: float
    avg_latency_sec: float
    p99_latency_sec: float
    avg_factuality:  float
    mrr:             float
    recall_at_5:     float
    results:         list[EvalResult] = field(default_factory=list)


def run_evaluation(
    test_questions: list[dict],
    retriever: Retriever | None = None,
    verbose: bool = True,
) -> EvalSummary:
    """
    Run evaluation over a list of test questions.

    Args:
        test_questions : list of {question, ground_truth} dicts
                         from test_questions.py
        retriever      : Retriever instance (creates one if None)
        verbose        : print progress

    Returns:
        EvalSummary with all metrics
    """
    if retriever is None:
        retriever = Retriever()

    results = []

    for i, tq in enumerate(test_questions):
        if verbose:
            print(f"[{i+1}/{len(test_questions)}] {tq['question'][:60]}...")

        start_time = time.time()

        # Run full RAG pipeline
        raw_chunks     = retriever.query(tq["question"])
        scored_chunks  = score_chunks(tq["question"], raw_chunks)
        final_chunks, confidence = filter_chunks(scored_chunks)
        response       = generate(tq["question"], final_chunks, confidence, retriever)

        latency = time.time() - start_time

        # Evaluate answer quality
        judge_scores = judge_answer(
            question=tq["question"],
            ground_truth=tq["ground_truth"],
            answer=response.answer,
        )
        factuality = judge_factuality(final_chunks, response.answer)

        results.append(EvalResult(
            question=tq["question"],
            ground_truth=tq["ground_truth"],
            answer=response.answer,
            retrieved_chunks=final_chunks,
            confidence=confidence,
            latency_sec=round(latency, 3),
            judge_scores=judge_scores,
            factuality=factuality,
            sources=response.sources,
        ))

    summary = _compute_summary(results)

    if verbose:
        _print_summary(summary)

    return summary


def _compute_summary(results: list[EvalResult]) -> EvalSummary:
    """Compute aggregate metrics from individual results."""
    latencies    = [r.latency_sec for r in results]
    judge_scores = [r.judge_scores.get("avg_score", 0) for r in results]
    factuality   = [r.factuality.get("factuality_score", 0) for r in results]

    # Sort latencies to compute P99
    sorted_lat = sorted(latencies)
    p99_idx    = int(len(sorted_lat) * 0.99)
    p99_lat    = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]

    # MRR and Recall@5 require knowing which chunk was "correct"
    # Without explicit chunk-level ground truth, we use judge score >= 4 as proxy
    high_quality = [r for r in results if r.judge_scores.get("avg_score", 0) >= 4.0]
    mrr = len(high_quality) / max(len(results), 1)   # simplified MRR proxy
    recall_at_5 = mrr   # same proxy without chunk-level labels

    return EvalSummary(
        num_questions=len(results),
        avg_judge_score=round(sum(judge_scores) / max(len(judge_scores), 1), 3),
        avg_latency_sec=round(sum(latencies) / max(len(latencies), 1), 3),
        p99_latency_sec=round(p99_lat, 3),
        avg_factuality=round(sum(factuality) / max(len(factuality), 1), 3),
        mrr=round(mrr, 3),
        recall_at_5=round(recall_at_5, 3),
        results=results,
    )


def save_results_csv(summary: EvalSummary, output_path: str) -> None:
    """Save evaluation results to CSV (same format as your experiments)."""
    rows = []
    for r in summary.results:
        rows.append({
            "question":      r.question[:80],
            "confidence":    r.confidence,
            "latency_sec":   r.latency_sec,
            "relevance":     r.judge_scores.get("relevance", 0),
            "correctness":   r.judge_scores.get("correctness", 0),
            "completeness":  r.judge_scores.get("completeness", 0),
            "avg_score":     r.judge_scores.get("avg_score", 0),
            "factuality":    r.factuality.get("factuality_score", 0),
            "num_sources":   len(r.sources),
        })
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Results saved to {output_path}")


def _print_summary(summary: EvalSummary) -> None:
    print("\n" + "=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(f"Questions evaluated : {summary.num_questions}")
    print(f"Avg judge score     : {summary.avg_judge_score:.3f} / 5.0")
    print(f"Avg factuality      : {summary.avg_factuality:.1%}")
    print(f"Avg latency         : {summary.avg_latency_sec:.2f}s")
    print(f"P99 latency         : {summary.p99_latency_sec:.2f}s  (target: < 2.0s)")
    print(f"MRR (proxy)         : {summary.mrr:.3f}  (target: > 0.8)")
    print(f"Recall@5 (proxy)    : {summary.recall_at_5:.3f}  (target: > 0.9)")
    print("=" * 50)

    # Case study SLA check
    print("\nCASE STUDY SLA STATUS:")
    p99_ok  = "✓" if summary.p99_latency_sec < 2.0 else "✗"
    mrr_ok  = "✓" if summary.mrr > 0.8 else "✗"
    rec_ok  = "✓" if summary.recall_at_5 > 0.9 else "✗"
    fact_ok = "✓" if summary.avg_factuality > 0.95 else "✗"
    print(f"  {p99_ok} P99 latency < 2s       : {summary.p99_latency_sec:.2f}s")
    print(f"  {mrr_ok} MRR > 0.8              : {summary.mrr:.3f}")
    print(f"  {rec_ok} Recall@5 > 0.9         : {summary.recall_at_5:.3f}")
    print(f"  {fact_ok} Factuality > 95%       : {summary.avg_factuality:.1%}")
