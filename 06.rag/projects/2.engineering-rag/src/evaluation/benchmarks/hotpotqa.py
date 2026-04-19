"""
hotpotqa.py — HotpotQA multi-hop reasoning benchmark.

WHAT IS HOTPOTQA?
Multi-hop QA: answering requires COMBINING facts from TWO separate documents.

Example:
  Q: "Were Scott Derrickson and Ed Wood of the same nationality?"
  Doc 1: "Scott Derrickson is an American director..."
  Doc 2: "Ed Wood was an American filmmaker..."
  A: "Yes" (both are American — requires reading both docs)

WHY MULTI-HOP IS HARD FOR RAG:
  Standard RAG retrieves the top-k most similar chunks.
  For multi-hop: the SECOND document might not be similar to the QUESTION —
  it's similar to the ANSWER from the first document.

  Example of the failure:
    Query: "nationality of Scott Derrickson"
    Retrieves: ✓ Doc about Scott Derrickson (American)
    Misses:    ✗ Doc about Ed Wood (because the question doesn't mention Ed Wood)

  Our RRF merges text+table+image — but all three searches still use the SAME query.
  Multi-hop tests whether we retrieve BOTH supporting documents.

WHAT THIS TESTS IN OUR SYSTEM:
  1. RRF: does merging 15 candidates (5 per type) surface both supporting docs?
  2. CRAG: does it score BOTH supporting chunks as "relevant"?
  3. Generation: does GPT-4o-mini connect the facts from both sources?
  4. Supporting fact recall: specific HotpotQA metric — did we use the right evidence?

WHAT TO DOWNLOAD:
  hotpot_dev_distractor_v1.json from https://hotpotqa.github.io/
  Place at: data/benchmarks/hotpotqa/hotpot_dev_distractor_v1.json
  (~54 MB, 7,405 questions)

  "Distractor" setting = 10 paragraphs per question (2 supporting + 8 distractors)
  This is realistic: our retriever sees 10 candidate docs and must find the 2 right ones.

FILE FORMAT:
  [
    {
      "_id": "5a8b57f25542995d1e6f1371",
      "question": "Were Scott Derrickson and Ed Wood of the same nationality?",
      "answer": "yes",
      "type": "comparison",
      "level": "easy",
      "supporting_facts": [
        ["Scott Derrickson", 0],   // [title, sentence_index]
        ["Ed Wood", 0]
      ],
      "context": [
        ["Scott Derrickson", ["sent0", "sent1", ...]],
        ["Ed Wood", ["sent0", "sent1", ...]],
        // 8 more distractor paragraphs...
      ]
    }
  ]

METRICS:
  - Answer EM/F1 (standard)
  - Supporting fact recall: % of [title, sent_idx] pairs retrieved
  - Joint EM: both answer correct AND all supporting facts retrieved
    (joint EM is the main HotpotQA leaderboard metric)
"""

import json
import random
from pathlib import Path

from src.evaluation.benchmarks.base import BenchmarkSample


# ── Loader ─────────────────────────────────────────────────────────────────

def load_hotpotqa(
    data_dir: Path,
    max_samples: int = 100,
    question_types: list[str] | None = None,
    seed: int = 42,
) -> list[BenchmarkSample]:
    """
    Load HotpotQA distractor-setting samples from local JSON file.

    Args:
        data_dir       : path to data/benchmarks/hotpotqa/
        max_samples    : number of samples to load (dev set has 7,405)
        question_types : filter by "comparison" or "bridge" (None = both)
                         "comparison" = compare attributes of two entities
                         "bridge"     = answer requires entity from doc1 to find doc2
        seed           : random seed

    Returns:
        list of BenchmarkSample with 10 context_docs each (2 supporting + 8 distractors)
    """
    hotpot_file = data_dir / "hotpot_dev_distractor_v1.json"
    if not hotpot_file.exists():
        raise FileNotFoundError(
            f"HotpotQA file not found: {hotpot_file}\n"
            "Download from: https://hotpotqa.github.io/\n"
            "Place at: data/benchmarks/hotpotqa/hotpot_dev_distractor_v1.json"
        )

    with open(hotpot_file, encoding="utf-8") as f:
        data = json.load(f)

    # Optionally filter by question type
    if question_types:
        data = [ex for ex in data if ex.get("type", "") in question_types]

    random.seed(seed)
    random.shuffle(data)
    selected = data[:max_samples]

    samples = []
    for ex in selected:
        sample = _parse_hotpot_example(ex)
        if sample:
            samples.append(sample)

    return samples


def _parse_hotpot_example(ex: dict) -> BenchmarkSample | None:
    """
    Parse one HotpotQA example.

    The 10 context paragraphs (2 supporting + 8 distractors) are all ingested.
    The supporting_facts list records which paragraphs/sentences are actually needed.
    """
    question = ex.get("question", "").strip()
    answer   = ex.get("answer", "").strip()
    if not question or not answer:
        return None

    # Build context docs: each paragraph title + sentences as one string
    context_docs = []
    for title, sentences in ex.get("context", []):
        passage = f"{title}\n" + " ".join(sentences)
        context_docs.append(passage)

    # Supporting facts: list of (title, sentence_index)
    supporting_facts = [
        (sf[0], sf[1])
        for sf in ex.get("supporting_facts", [])
    ]

    return BenchmarkSample(
        question=question,
        ground_truth=answer,
        context_docs=context_docs,
        answer_spans=[answer],
        supporting_facts=supporting_facts,
        metadata={
            "id":    ex.get("_id", ""),
            "type":  ex.get("type", ""),        # "comparison" or "bridge"
            "level": ex.get("level", ""),       # "easy", "medium", "hard"
            "dataset": "hotpotqa",
        },
    )


# ── Supporting fact recall metric ───────────────────────────────────────────

def supporting_fact_recall(
    sample: BenchmarkSample,
    retrieved_chunks: list[dict],
) -> float:
    """
    HotpotQA-specific metric: did we retrieve the supporting evidence?

    For each (title, sent_idx) in supporting_facts, check if any retrieved
    chunk's content contains text from that specific sentence.

    Args:
        sample           : the BenchmarkSample (has supporting_facts list)
        retrieved_chunks : chunks returned by the retriever

    Returns:
        fraction of supporting facts found in retrieved chunks (0.0 – 1.0)

    WHY THIS MATTERS:
    A RAG system can get the right ANSWER while using the WRONG evidence
    (e.g., by hallucinating). Supporting fact recall checks whether the
    answer is actually grounded in the correct source documents.
    """
    if not sample.supporting_facts or not retrieved_chunks:
        return 0.0

    # Build the actual text of each supporting sentence
    # (from context_docs, which are title + sentences)
    supporting_texts = _get_supporting_texts(sample)
    if not supporting_texts:
        return 0.0

    retrieved_text = " ".join(c.get("content", "") for c in retrieved_chunks).lower()

    found = 0
    for text in supporting_texts:
        # Check if a significant fragment of the supporting sentence appears
        # in the retrieved context (partial match, at least 10 chars)
        key_phrase = text.lower()[:60].strip()
        if key_phrase and key_phrase in retrieved_text:
            found += 1

    return round(found / len(supporting_texts), 4)


def _get_supporting_texts(sample: BenchmarkSample) -> list[str]:
    """
    Extract the actual text of the supporting sentences from context_docs.

    supporting_facts = [(title, sent_idx), ...]
    context_docs = ["Title\nSent0 Sent1 Sent2...", ...]

    Map title → paragraph, then extract sentence at sent_idx.
    """
    # Build title → sentences mapping from context_docs
    title_to_sents: dict[str, list[str]] = {}
    for doc in sample.context_docs:
        lines = doc.split("\n", 1)
        title = lines[0].strip()
        body  = lines[1] if len(lines) > 1 else ""
        # Very rough sentence split (the original data joined with spaces)
        sents = [s.strip() for s in body.split(". ") if s.strip()]
        title_to_sents[title] = sents

    texts = []
    for title, sent_idx in sample.supporting_facts:
        sents = title_to_sents.get(title, [])
        if sent_idx < len(sents):
            texts.append(sents[sent_idx])

    return texts
