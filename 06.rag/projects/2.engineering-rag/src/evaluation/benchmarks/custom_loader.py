"""
custom_loader.py — Load test_questions.py as BenchmarkSamples.

These questions are grounded in the 3 ingested PDFs (pump manual,
Machinery's Handbook, Chevron SDS). Unlike SQuAD/HotpotQA, there is NO
context to ingest — the PDFs are already in Supabase. The runner queries
the real DB without doc_type filtering so all 3 docs are searched.
"""

import random
from pathlib import Path

from src.evaluation.benchmarks.base import BenchmarkSample
from src.evaluation.test_questions import (
    ALL_QUESTIONS,
    QUESTIONS_BY_CATEGORY,
    TestQuestion,
)


def load_custom(
    max_samples: int = 10,
    categories: list[str] | None = None,
    seed: int = 42,
) -> list[BenchmarkSample]:
    """
    Load questions from test_questions.py as BenchmarkSamples.

    Args:
        max_samples : total questions to return (randomly sampled)
        categories  : filter to specific categories
                      (text, table, image, multihop, unanswerable)
                      None = all categories
        seed        : reproducible random sampling

    Returns:
        list of BenchmarkSample (context_docs=[] — use real ingested PDFs)
    """
    if categories:
        pool: list[TestQuestion] = []
        for cat in categories:
            pool.extend(QUESTIONS_BY_CATEGORY.get(cat, []))
    else:
        pool = list(ALL_QUESTIONS)

    random.seed(seed)
    random.shuffle(pool)
    selected = pool[:max_samples]

    return [_to_benchmark_sample(q) for q in selected]


def load_custom_balanced(
    per_category: int = 2,
    seed: int = 42,
) -> list[BenchmarkSample]:
    """
    Load an equal number of questions from each category.

    Args:
        per_category : questions per category (2 × 5 categories = 10 total)
        seed         : reproducible random sampling

    Returns:
        list of BenchmarkSample
    """
    random.seed(seed)
    samples = []

    for cat, questions in QUESTIONS_BY_CATEGORY.items():
        shuffled = list(questions)
        random.shuffle(shuffled)
        for q in shuffled[:per_category]:
            samples.append(_to_benchmark_sample(q))

    return samples


def _to_benchmark_sample(q: TestQuestion) -> BenchmarkSample:
    return BenchmarkSample(
        question=q.question,
        ground_truth=q.ground_truth,
        context_docs=[],          # already in DB — no temp ingestion needed
        answer_spans=[],
        supporting_facts=[],
        metadata={
            "dataset":  "custom",
            "category": q.category,
            "doc_hint": q.doc_hint,
        },
    )
