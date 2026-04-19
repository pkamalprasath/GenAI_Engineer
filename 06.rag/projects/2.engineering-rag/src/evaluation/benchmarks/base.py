"""
base.py — Shared types and utilities for all benchmark loaders.

DESIGN PATTERN:
Every benchmark (SQuAD, NQ, HotpotQA, MS MARCO) is different in format,
but the RAG pipeline always needs the same thing:
  - A question to ask
  - A ground truth answer to compare against
  - The source documents to ingest (so retrieval has something to search)

BenchmarkSample is the common format every loader normalises to.
The runner only knows about BenchmarkSample — it doesn't care which dataset it came from.

This is the Adapter pattern: each loader is an adapter between a dataset's
native format and BenchmarkSample.
"""

from dataclasses import dataclass, field
from pathlib import Path


# ── Standard sample format ─────────────────────────────────────────────────

@dataclass
class BenchmarkSample:
    """
    One evaluation sample, normalised from any dataset format.

    Fields:
      question        : the question to ask the RAG system
      ground_truth    : the expected answer (for LLM-judge comparison)
      context_docs    : the source text passages to ingest into pgvector
                        (each doc is one chunk; for SQuAD this is the passage,
                         for HotpotQA it's the two supporting paragraphs)
      answer_spans    : for extractive QA (SQuAD), the exact quoted spans
                        that should appear in the answer; empty for generative
      supporting_facts: for HotpotQA, which (title, sent_idx) pairs are needed
      metadata        : dataset-specific fields (id, type, difficulty, etc.)
    """
    question:         str
    ground_truth:     str
    context_docs:     list[str]          = field(default_factory=list)
    answer_spans:     list[str]          = field(default_factory=list)
    supporting_facts: list[tuple]        = field(default_factory=list)
    metadata:         dict               = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """
    Result for one sample after running through the RAG pipeline.
    """
    sample:           BenchmarkSample
    answer:           str
    retrieved_chunks: list[dict]
    confidence:       str
    latency_sec:      float

    # Standard metrics (computed after generation)
    exact_match:      float = 0.0     # 1.0 if any answer span matches exactly
    f1_score:         float = 0.0     # token-level F1 (SQuAD standard)
    judge_score:      float = 0.0     # LLM-as-judge average (1-5)
    factuality:       float = 0.0     # % claims supported by context
    supporting_recall:float = 0.0     # HotpotQA: % supporting facts retrieved

    # RAGAS metrics (only populated when ragas is used)
    ragas_faithfulness:     float = 0.0
    ragas_answer_relevancy: float = 0.0
    ragas_context_recall:   float = 0.0


@dataclass
class BenchmarkReport:
    """
    Aggregated metrics for one full benchmark run.
    """
    dataset_name:    str
    num_samples:     int
    avg_em:          float          # exact match rate
    avg_f1:          float          # avg token F1
    avg_judge_score: float          # avg LLM judge (1-5)
    avg_factuality:  float          # % factually grounded
    avg_latency_sec: float
    p99_latency_sec: float
    mrr:             float          # mean reciprocal rank (judge >= 4 proxy)
    ndcg_at_10:      float          # MS MARCO retrieval metric
    recall_at_5:     float
    results:         list[BenchmarkResult] = field(default_factory=list)

    # SLA checks (from case study)
    @property
    def sla_latency_ok(self) -> bool:
        return self.p99_latency_sec < 2.0

    @property
    def sla_factuality_ok(self) -> bool:
        return self.avg_factuality > 0.95

    @property
    def sla_quality_ok(self) -> bool:
        return self.avg_judge_score > 4.0


# ── Text scoring utilities ──────────────────────────────────────────────────

def exact_match_score(prediction: str, ground_truths: list[str]) -> float:
    """
    SQuAD-style exact match: 1.0 if prediction (normalised) matches any ground truth.

    Normalisation: lowercase, remove articles (a/an/the), collapse whitespace,
    remove punctuation. This is the official SQuAD EM formula.
    """
    pred_norm = _normalise(prediction)
    return 1.0 if any(pred_norm == _normalise(gt) for gt in ground_truths) else 0.0


def f1_score(prediction: str, ground_truths: list[str]) -> float:
    """
    SQuAD-style token-level F1: measures word overlap between prediction and best GT.

    WHY F1 INSTEAD OF JUST EM?
    EM is binary — either exact or 0. F1 gives partial credit.
    "The torque is 85 Nm" vs "85 Nm" → EM=0, F1=0.67 (some overlap)

    Returns the MAX F1 across all ground truth variants.
    """
    pred_tokens = _normalise(prediction).split()
    best_f1 = 0.0

    for gt in ground_truths:
        gt_tokens = _normalise(gt).split()
        if not pred_tokens or not gt_tokens:
            continue

        common = set(pred_tokens) & set(gt_tokens)
        if not common:
            continue

        precision = len(common) / len(pred_tokens)
        recall    = len(common) / len(gt_tokens)
        f1        = 2 * precision * recall / (precision + recall)
        best_f1   = max(best_f1, f1)

    return round(best_f1, 4)


def _normalise(text: str) -> str:
    """Official SQuAD normalisation for EM/F1 scoring."""
    import re
    import string

    text = text.lower()
    # Remove articles
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Collapse whitespace
    text = ' '.join(text.split())
    return text


# ── Context document ingestion helper ──────────────────────────────────────

def docs_to_chunks(docs: list[str], source_name: str = "benchmark") -> list[dict]:
    """
    Convert plain text passages to the chunk format expected by VectorStore.upsert_document().

    Each passage becomes one 'text' chunk.
    Used by the runner to ingest benchmark context docs before querying.
    """
    return [
        {
            "content":    doc,
            "chunk_type": "text",
            "page":       i + 1,
            "section":    source_name,
            "image_path": None,
        }
        for i, doc in enumerate(docs)
    ]


# ── Summary printer ─────────────────────────────────────────────────────────

def print_report(report: BenchmarkReport) -> None:
    """Print a formatted benchmark report to stdout."""
    w = 56
    print("\n" + "=" * w)
    print(f"  BENCHMARK: {report.dataset_name.upper()}")
    print("=" * w)
    print(f"  Samples evaluated : {report.num_samples}")
    print(f"  Exact Match (EM)  : {report.avg_em:.1%}")
    print(f"  Token F1          : {report.avg_f1:.1%}")
    print(f"  Judge score       : {report.avg_judge_score:.2f} / 5.0")
    print(f"  Factuality        : {report.avg_factuality:.1%}")
    print(f"  Avg latency       : {report.avg_latency_sec:.2f}s")
    print(f"  P99 latency       : {report.p99_latency_sec:.2f}s")
    print(f"  MRR               : {report.mrr:.3f}")
    print(f"  NDCG@10           : {report.ndcg_at_10:.3f}")
    print(f"  Recall@5          : {report.recall_at_5:.3f}")
    print("-" * w)
    print("  SLA STATUS (case study targets):")
    print(f"  {'✓' if report.sla_latency_ok else '✗'}  P99 < 2.0s     : {report.p99_latency_sec:.2f}s")
    print(f"  {'✓' if report.sla_factuality_ok else '✗'}  Factuality > 95% : {report.avg_factuality:.1%}")
    print(f"  {'✓' if report.sla_quality_ok else '✗'}  Quality > 4.0  : {report.avg_judge_score:.2f}")
    print("=" * w)
