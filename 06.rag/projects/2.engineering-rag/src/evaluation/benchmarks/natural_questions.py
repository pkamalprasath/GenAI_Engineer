"""
natural_questions.py — Google Natural Questions benchmark loader.

WHAT IS NATURAL QUESTIONS (NQ)?
Real questions people typed into Google Search, answered by Wikipedia.

Key difference from SQuAD:
  - SQuAD questions are written BY ANNOTATORS looking at a passage
    → questions sound like textbook exercises
  - NQ questions are real user queries typed BEFORE seeing any document
    → natural language, varied vocabulary, sometimes ambiguous

This matters for RAG because:
  - SQuAD tests whether you can extract an answer from the RIGHT passage
  - NQ tests whether you can FIND the right passage at all
    (HyDE expansion helps here — real user queries are short and informal)

WHAT TO DOWNLOAD:
  v1.0-simplified_nq-dev.jsonl.gz from the official NQ download page:
  https://ai.google.com/research/NaturalQuestions/download
  (or the simplified 4.6 GB version)

  Simpler alternative — just the dev set (smaller):
  https://storage.googleapis.com/natural_questions/v1.0-simplified/simplified-nq-dev.jsonl.gz
  (~300 MB compressed)

  Place uncompressed file at: data/benchmarks/natural_questions/nq-dev.jsonl
  (One JSON object per line)

NQ FORMAT (simplified):
  {
    "example_id": 123,
    "question_text": "who wrote the song yesterday",
    "document_title": "Yesterday (Beatles song)",
    "document_text": "Yesterday is a song by the English rock band...",
    "annotations": [{
      "short_answers": [{"start_token": 15, "end_token": 18}],
      "long_answer": {"start_token": 0, "end_token": 50},
      "yes_no_answer": "NONE"
    }]
  }

WHY NQ IS HARDER THAN SQUAD:
  1. No passage is provided — must retrieve from a large corpus
  2. Many questions are conversational ("who wrote...", "when did...")
  3. Some questions have multiple valid answers
  4. Some are yes/no questions (different answer type)

EVALUATION:
  - Short answer EM/F1 (when answer is a named entity or span)
  - Long answer precision (when answer is a full paragraph)
  - LLM judge for quality assessment
"""

import json
import gzip
import random
from pathlib import Path

from src.evaluation.benchmarks.base import BenchmarkSample


# ── Loader ─────────────────────────────────────────────────────────────────

def load_natural_questions(
    data_dir: Path,
    max_samples: int = 100,
    seed: int = 42,
) -> list[BenchmarkSample]:
    """
    Load NQ samples from local JSONL file (compressed or uncompressed).

    Args:
        data_dir    : path to data/benchmarks/natural_questions/
        max_samples : number of samples (NQ dev has ~7,830 examples)
        seed        : for reproducible sampling

    Returns:
        list of BenchmarkSample
    """
    # Support both compressed and uncompressed files
    for filename in ("nq-dev.jsonl", "nq-dev.jsonl.gz", "simplified-nq-dev.jsonl",
                     "simplified-nq-dev.jsonl.gz"):
        nq_file = data_dir / filename
        if nq_file.exists():
            break
    else:
        raise FileNotFoundError(
            f"NQ file not found in {data_dir}\n"
            "Download from: https://ai.google.com/research/NaturalQuestions/download\n"
            "Place at: data/benchmarks/natural_questions/nq-dev.jsonl[.gz]"
        )

    # Read all lines first so we can sample reproducibly
    open_fn = gzip.open if str(nq_file).endswith(".gz") else open
    all_lines = []
    with open_fn(nq_file, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_lines.append(line)

    random.seed(seed)
    random.shuffle(all_lines)
    selected = all_lines[:max_samples]

    samples = []
    for line in selected:
        try:
            ex = json.loads(line)
            sample = _parse_nq_example(ex)
            if sample:
                samples.append(sample)
        except (json.JSONDecodeError, KeyError):
            continue

    return samples


def _parse_nq_example(ex: dict) -> BenchmarkSample | None:
    """
    Parse one NQ example into BenchmarkSample.

    NQ annotations can be complex — we extract the first short answer
    and the long-answer passage as context.
    """
    question = ex.get("question_text", "").strip()
    if not question:
        return None

    doc_text  = ex.get("document_text", "")
    doc_title = ex.get("document_title", "unknown")

    # Extract ground truth from annotations
    ground_truth = ""
    answer_spans = []

    annotations = ex.get("annotations", [])
    if annotations:
        ann = annotations[0]

        # Yes/no questions
        yes_no = ann.get("yes_no_answer", "NONE")
        if yes_no not in ("NONE", None):
            ground_truth = yes_no.lower()
            answer_spans = [ground_truth]
        else:
            # Short answers (token indices into doc_text)
            short_answers = ann.get("short_answers", [])
            if short_answers and doc_text:
                tokens = doc_text.split()
                for sa in short_answers:
                    start = sa.get("start_token", 0)
                    end   = sa.get("end_token", 0)
                    span  = " ".join(tokens[start:end]).strip()
                    if span:
                        answer_spans.append(span)
                if answer_spans:
                    ground_truth = answer_spans[0]

    if not ground_truth:
        return None  # Skip unannotated examples

    # Context: take the long-answer paragraph if available, else first 500 tokens
    context = _extract_context(ex, doc_text)

    return BenchmarkSample(
        question=question,
        ground_truth=ground_truth,
        context_docs=[context],
        answer_spans=answer_spans,
        metadata={
            "example_id": ex.get("example_id", ""),
            "title":      doc_title,
            "dataset":    "natural_questions",
        },
    )


def _extract_context(ex: dict, doc_text: str) -> str:
    """
    Extract the relevant context passage.

    Tries to use the long-answer paragraph from annotations.
    Falls back to first 1000 characters of document.
    """
    annotations = ex.get("annotations", [])
    if annotations:
        la = annotations[0].get("long_answer", {})
        start = la.get("start_token", 0)
        end   = la.get("end_token", 0)
        if end > start and doc_text:
            tokens = doc_text.split()
            passage = " ".join(tokens[start:end])
            if len(passage) > 50:
                return passage

    # Fallback: first 500 words of document
    tokens = doc_text.split()
    return " ".join(tokens[:500]) if tokens else doc_text[:2000]
