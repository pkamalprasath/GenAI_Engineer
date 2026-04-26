"""
DistilBERT re-ranker for discovery — scores BM25-filtered cases for relevance
to the investigation query.

Uses HuggingFace transformers (CPU only, no GPU required).
Model is loaded once and cached — ~250MB RAM for DistilBERT.

Relevance score: cosine similarity between [CLS] embeddings of
  (query + domain context) and (case metadata + outcome + reasoning).

This is Stage 2 in the hybrid discovery pipeline:
  BM25 (top-K) → DistilBERT (re-rank) → llama3.2:3b (borderline only)

The model is loaded lazily — only when discovery actually runs.
Swappable via configs/agents.yaml: bert_model: distilbert-base-uncased
                                              or nlpaueb/legal-bert-base-uncased
                                              or ProsusAI/finbert
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BERTScore:
    case_id: str
    score: float           # 0.0–1.0 cosine similarity
    verdict: str           # "relevant" | "irrelevant" | "borderline"
    case: dict             # Original case dict


@lru_cache(maxsize=1)
def _load_model(model_name: str) -> tuple[Any, Any]:
    """
    Load tokenizer and model once, cache for the process lifetime.
    lru_cache(maxsize=1) ensures only one model is in memory at a time.
    """
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch  # noqa: F401 — validate torch is installed

        logger.info("Loading BERT model: %s (first call only)", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()  # Inference mode — disables dropout
        logger.info("BERT model loaded: %s", model_name)
        return tokenizer, model
    except ImportError as exc:
        raise RuntimeError(
            "transformers or torch not installed. "
            "Run: pip install transformers torch --index-url https://download.pytorch.org/whl/cpu"
        ) from exc


def _embed(tokenizer: Any, model: Any, text: str) -> list[float]:
    """
    Get [CLS] token embedding for text.
    [CLS] embedding represents the entire sequence — standard for classification.
    Truncated to 512 tokens (BERT limit).
    """
    import torch

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    with torch.no_grad():
        outputs = model(**inputs)
    # [CLS] token is the first token in the last hidden state
    cls_embedding = outputs.last_hidden_state[:, 0, :].squeeze()
    return cls_embedding.tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors — range [-1, 1], returns [0, 1]."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    raw = dot / (norm_a * norm_b)
    # Normalize from [-1, 1] to [0, 1]
    return (raw + 1.0) / 2.0


def _case_to_text(case: dict) -> str:
    """Format case for embedding — outcome + reasoning + key metadata."""
    import json
    metadata = case.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    parts = [
        f"outcome: {case.get('outcome', '')}",
        f"reasoning: {case.get('reasoning_text', '')[:300]}",
        f"credit_tier: {metadata.get('credit_score_tier', '')}",
        f"income: {metadata.get('income_bracket', '')}",
        f"census_tract: {metadata.get('zip_code_census_tract', '')}",
    ]
    return " | ".join(p for p in parts if p.split(": ", 1)[-1])


def score_cases_bert(
    query: str,
    cases: list[dict],
    model_name: str = "distilbert-base-uncased",
    auto_relevant_threshold: float = 0.80,
    auto_irrelevant_threshold: float = 0.35,
) -> list[BERTScore]:
    """
    Score each case for relevance to the query using DistilBERT embeddings.

    Returns BERTScore list sorted descending by score, with verdict:
      - "relevant"   (score >= auto_relevant_threshold)
      - "borderline" (auto_irrelevant_threshold < score < auto_relevant_threshold)
      - "irrelevant" (score <= auto_irrelevant_threshold)

    Business contract: output structure is identical regardless of model used.
    The calling agent uses the verdict to decide whether to invoke llama3.2:3b.
    """
    if not cases:
        return []

    tokenizer, model = _load_model(model_name)

    # Embed query once — reused for all cases
    query_embedding = _embed(tokenizer, model, query)

    results: list[BERTScore] = []
    for case in cases:
        case_text = _case_to_text(case)
        case_embedding = _embed(tokenizer, model, case_text)
        score = _cosine_similarity(query_embedding, case_embedding)

        if score >= auto_relevant_threshold:
            verdict = "relevant"
        elif score <= auto_irrelevant_threshold:
            verdict = "irrelevant"
        else:
            verdict = "borderline"

        results.append(BERTScore(
            case_id=case.get("case_id", ""),
            score=round(score, 4),
            verdict=verdict,
            case=case,
        ))

    results.sort(key=lambda x: x.score, reverse=True)

    relevant = sum(1 for r in results if r.verdict == "relevant")
    borderline = sum(1 for r in results if r.verdict == "borderline")
    irrelevant = sum(1 for r in results if r.verdict == "irrelevant")
    logger.info(
        "BERT scoring: %d relevant | %d borderline (→ LLM) | %d irrelevant",
        relevant, borderline, irrelevant,
    )
    return results
