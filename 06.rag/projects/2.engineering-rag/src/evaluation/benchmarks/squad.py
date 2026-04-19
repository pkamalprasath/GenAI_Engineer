"""
squad.py — SQuAD 2.0 benchmark loader and evaluator.

WHAT IS SQuAD?
Stanford Question Answering Dataset. 100,000+ question-answer pairs where:
  - A Wikipedia passage is given
  - A question about that passage is asked
  - The answer is a SPAN from the passage (exact text extraction)
  - SQuAD 2.0 adds ~50K UNANSWERABLE questions (tests whether system says "I don't know")

WHY IT'S A GOOD RAG TEST:
  1. Tests RETRIEVAL: given many passages ingested, does our system find the RIGHT one?
  2. Tests GENERATION: does the answer come from the context (not hallucinated)?
  3. The UNANSWERABLE questions test whether our CRAG filtering works
     (if no relevant chunk → confidence LOW → "I don't know" → correct)
  4. EM/F1 are objective metrics: no need for expensive LLM judge on every answer

WHAT TO DOWNLOAD:
  dev-v2.0.json from https://rajpurkar.github.io/SQuAD-explorer/
  Place at: data/benchmarks/squad/dev-v2.0.json
  (~3.8 MB, 11,873 questions)

FILE FORMAT:
  {
    "version": "v2.0",
    "data": [
      {
        "title": "Super_Bowl_50",
        "paragraphs": [
          {
            "context": "Super Bowl 50 was an American football...",
            "qas": [
              {
                "id": "56be4db0acb8001400a502ec",
                "question": "Which NFL team represented the AFC...",
                "answers": [{"text": "Denver Broncos", "answer_start": 177}],
                "is_impossible": false
              }
            ]
          }
        ]
      }
    ]
  }

EVALUATION METRICS:
  - Exact Match (EM): 1 if answer exactly matches any ground truth (normalised)
  - F1: token-level word overlap between prediction and ground truth
  - "I don't know" rate: for unanswerable questions, did system abstain?

These are the official SQuAD metrics used to rank systems on the leaderboard.
"""

import json
import random
from pathlib import Path

from src.evaluation.benchmarks.base import BenchmarkSample


# ── Loader ─────────────────────────────────────────────────────────────────

def load_squad(
    data_dir: Path,
    max_samples: int = 100,
    include_unanswerable: bool = True,
    seed: int = 42,
) -> list[BenchmarkSample]:
    """
    Load SQuAD 2.0 samples from local JSON file.

    Args:
        data_dir             : path to data/benchmarks/squad/
        max_samples          : how many questions to evaluate (100 = fast, 1000 = thorough)
        include_unanswerable : whether to include SQuAD 2.0's unanswerable questions
                               (good for testing CRAG's "I don't know" behaviour)
        seed                 : random seed for reproducible sampling

    Returns:
        list of BenchmarkSample, one per question
    """
    squad_file = data_dir / "dev-v2.0.json"
    if not squad_file.exists():
        raise FileNotFoundError(
            f"SQuAD file not found: {squad_file}\n"
            "Download from: https://rajpurkar.github.io/SQuAD-explorer/\n"
            "Place at: data/benchmarks/squad/dev-v2.0.json"
        )

    with open(squad_file, encoding="utf-8") as f:
        squad = json.load(f)

    samples = []

    for article in squad["data"]:
        title = article["title"].replace("_", " ")

        for para in article["paragraphs"]:
            context = para["context"]  # the passage text

            for qa in para["qas"]:
                is_impossible = qa.get("is_impossible", False)

                if is_impossible and not include_unanswerable:
                    continue

                # Ground truth: multiple valid answer strings
                if is_impossible:
                    # For unanswerable questions, ground truth is "I don't know"
                    ground_truth  = "This question cannot be answered from the given context."
                    answer_spans  = []
                else:
                    # Deduplicate answer texts
                    answer_spans = list({a["text"] for a in qa["answers"]})
                    ground_truth = answer_spans[0]  # primary GT for judge

                samples.append(BenchmarkSample(
                    question=qa["question"],
                    ground_truth=ground_truth,
                    context_docs=[context],   # the passage to ingest
                    answer_spans=answer_spans,
                    metadata={
                        "id":             qa["id"],
                        "title":          title,
                        "is_impossible":  is_impossible,
                        "dataset":        "squad2",
                    },
                ))

    # Random sample (reproducible)
    random.seed(seed)
    random.shuffle(samples)
    return samples[:max_samples]


# ── Metrics ─────────────────────────────────────────────────────────────────

def compute_squad_metrics(samples: list[BenchmarkSample], answers: list[str]) -> dict:
    """
    Compute official SQuAD EM and F1 across all samples.

    Args:
        samples : the BenchmarkSamples (contain ground truth spans)
        answers : the RAG system's answers (one per sample, same order)

    Returns:
        {exact_match_rate, avg_f1, unanswerable_abstain_rate}
    """
    from src.evaluation.benchmarks.base import exact_match_score, f1_score

    em_scores      = []
    f1_scores      = []
    abstain_scores = []

    for sample, answer in zip(samples, answers):
        is_impossible = sample.metadata.get("is_impossible", False)

        if is_impossible:
            # Good behaviour: say "I don't know" or "cannot be answered"
            abstained = _is_abstention(answer)
            abstain_scores.append(1.0 if abstained else 0.0)
            em_scores.append(1.0 if abstained else 0.0)
            f1_scores.append(1.0 if abstained else 0.0)
        else:
            gt_list = sample.answer_spans if sample.answer_spans else [sample.ground_truth]
            em_scores.append(exact_match_score(answer, gt_list))
            f1_scores.append(f1_score(answer, gt_list))

    result = {
        "exact_match_rate": round(sum(em_scores) / max(len(em_scores), 1), 4),
        "avg_f1":           round(sum(f1_scores) / max(len(f1_scores), 1), 4),
    }
    if abstain_scores:
        result["unanswerable_abstain_rate"] = round(
            sum(abstain_scores) / len(abstain_scores), 4
        )
    return result


def _is_abstention(answer: str) -> bool:
    """
    Check if the answer is a valid abstention for an unanswerable question.

    Our CRAG system produces LOW confidence + "could not find" phrasing when
    no relevant chunks are found. That counts as correct for unanswerable SQuAD.
    """
    lower = answer.lower()
    abstention_phrases = [
        "cannot be answered",
        "could not find",
        "don't have",
        "no information",
        "not mentioned",
        "i don't know",
        "not available",
        "insufficient information",
    ]
    return any(p in lower for p in abstention_phrases)
