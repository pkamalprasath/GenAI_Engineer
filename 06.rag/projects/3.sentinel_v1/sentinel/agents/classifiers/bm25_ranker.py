"""
BM25 pre-filter for discovery — eliminates obviously irrelevant cases
before BERT or LLM scoring.

BM25 (Okapi BM25) is a probabilistic retrieval model that scores documents
by term frequency and inverse document frequency. Runs in milliseconds on
500 records — no model loading, no GPU, no network.

Used as Stage 1 in the hybrid discovery pipeline:
  BM25 (top-K) → DistilBERT (re-rank) → llama3.2:3b (borderline only)
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def _case_to_text(case: dict) -> str:
    """
    Convert a decision record dict to a flat text string for BM25 tokenization.
    Concatenates outcome, reasoning_text, and metadata values.
    """
    parts = [
        str(case.get("outcome", "")),
        str(case.get("reasoning_text", "")),
    ]
    metadata = case.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    for v in metadata.values():
        parts.append(str(v))
    return " ".join(p for p in parts if p).lower()


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer — no NLTK dependency."""
    return re.findall(r"[a-z0-9]+", text.lower())


def rank_cases_bm25(
    query: str,
    cases: list[dict],
    top_k: int = 50,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict]:
    """
    Score all cases against the query using BM25, return top_k by score.

    Args:
        query: Investigation query string
        cases: List of decision record dicts from DB
        top_k: Number of top cases to return
        k1: BM25 term frequency saturation parameter (default: 1.5)
        b: BM25 document length normalization parameter (default: 0.75)

    Returns:
        List of dicts: original case dict + "_bm25_score" key, sorted descending.
        Length <= top_k.
    """
    if not cases:
        return []

    query_tokens = set(_tokenize(query))
    if not query_tokens:
        # Empty query — return all cases unscored (let BERT/LLM decide)
        return cases[:top_k]

    # Build corpus
    corpus = [_tokenize(_case_to_text(c)) for c in cases]
    avg_doc_len = sum(len(doc) for doc in corpus) / len(corpus)

    # Build inverted index: term → document frequency
    doc_freq: dict[str, int] = {}
    for doc in corpus:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    N = len(corpus)

    def bm25_score(doc_tokens: list[str]) -> float:
        score = 0.0
        doc_len = len(doc_tokens)
        tf_map: dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        for term in query_tokens:
            if term not in doc_freq:
                continue
            tf = tf_map.get(term, 0)
            df = doc_freq[term]
            # IDF with smoothing (Robertson-Sparck Jones)
            idf = (N - df + 0.5) / (df + 0.5)
            # TF normalization
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
            score += idf * tf_norm
        return score

    scored = [
        {**case, "_bm25_score": bm25_score(corpus[i])}
        for i, case in enumerate(cases)
    ]

    # Sort descending by score
    scored.sort(key=lambda x: x["_bm25_score"], reverse=True)
    top = scored[:top_k]

    logger.debug(
        "BM25 pre-filter: %d cases → top %d (best_score=%.3f, worst_score=%.3f)",
        len(cases), len(top),
        top[0]["_bm25_score"] if top else 0,
        top[-1]["_bm25_score"] if top else 0,
    )
    return top
