"""
crag.py — Corrective RAG: score retrieved chunks for relevance, filter poor ones.

WHAT IS CRAG?
"Corrective Retrieval-Augmented Generation" — a quality verification step
that runs AFTER retrieval and BEFORE generation.

THE PROBLEM IT SOLVES:
Sometimes vector search retrieves chunks that LOOK similar to the query
(high cosine similarity) but don't actually answer the question:

Query: "What is the torque spec for M12 bolts?"

Retrieved chunk (high similarity score):
  "The M12 bolt is used throughout the gearbox assembly. Selection of
   appropriate bolts is critical for system reliability and long-term
   maintenance. Refer to Table 4.2 for complete specifications."

This chunk mentions M12 bolts (hence high similarity) but doesn't contain
the actual torque value. If we pass it to the LLM, it might hallucinate
a torque value or generate a vague answer.

CRAG SOLUTION:
Score each retrieved chunk:
  RELEVANT    → Contains information that answers the question
  AMBIGUOUS   → Might be relevant but unclear (keep with lower confidence)
  IRRELEVANT  → Does not contain the answer (discard)

This prevents the LLM from hallucinating answers based on vaguely related context.

FROM THE IMPLEMENTATION GUIDE:
"CRAG: quality verification, prevents confident-wrong answers"
"Source Attribution: every answer must cite its source"
"Confidence Scoring: required for all answers"
"""

import logging

from openai import OpenAI
from anthropic import Anthropic

logger = logging.getLogger(__name__)

from configs.settings import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    TEXT_LLM,
    TEXT_LLM_FAST,
    HAS_OPENAI,
    HAS_ANTHROPIC,
    MAX_CRAG_JUDGE_TOKENS,
    CRAG_IMAGE_PASSAGE_TOKENS,
    CRAG_TEXT_PASSAGE_TOKENS,
    CRAG_SCORE_RELEVANT,
    CRAG_SCORE_AMBIGUOUS,
    CRAG_SCORE_IRRELEVANT,
)


# Single-call batch scoring prompt — scores all chunks in one LLM call
# instead of N separate calls, reducing latency from N×0.5s to ~0.8s total.
CRAG_BATCH_PROMPT = """You are evaluating whether text passages are relevant to a question.

Question: {query}

Rate each passage below. For each passage number, respond with ONLY one word:
RELEVANT, AMBIGUOUS, or IRRELEVANT.

Definitions:
- RELEVANT   : passage directly answers or contains key facts for the question
- AMBIGUOUS  : passage is related but doesn't clearly answer the question
- IRRELEVANT : passage does not contain information to answer the question

{passages}

Respond with ONLY a numbered list, one word per line. Example:
1. RELEVANT
2. IRRELEVANT
3. AMBIGUOUS"""

SCORE_MAP = {
    "relevant":   CRAG_SCORE_RELEVANT,
    "ambiguous":  CRAG_SCORE_AMBIGUOUS,
    "irrelevant": CRAG_SCORE_IRRELEVANT,
}


def score_chunks(query: str, chunks: list[dict]) -> list[dict]:
    """
    Score all chunks for relevance in a single batched LLM call.

    Previously: N chunks × 1 LLM call each = N × ~0.5s latency
    Now:        all N chunks in 1 LLM call = ~0.8s total

    Adds 'crag_score' and 'relevance' fields to each chunk.
    """
    if not chunks:
        return []

    # Build numbered passage list (truncate to save tokens)
    # Strip contextual prefix "[filename — section, p.N]\n" before scoring —
    # the prefix is noise for relevance judgement, especially for image captions.
    import re as _re
    passage_lines = []
    for i, chunk in enumerate(chunks, 1):
        raw = chunk.get("parent_content") or chunk["content"]
        # Remove the contextual retrieval prefix (first line if it starts with "[")
        lines = raw.strip().split("\n", 1)
        body  = lines[1].strip() if len(lines) > 1 and lines[0].startswith("[") else raw
        limit = CRAG_IMAGE_PASSAGE_TOKENS if chunk.get("chunk_type") == "image" else CRAG_TEXT_PASSAGE_TOKENS
        truncated = body[:limit].replace("\n", " ")
        passage_lines.append(f"{i}. {truncated}")

    prompt = CRAG_BATCH_PROMPT.format(
        query=query,
        passages="\n\n".join(passage_lines),
    )

    try:
        raw = _call_llm(prompt)
        relevance_list = _parse_batch_response(raw, len(chunks))
    except Exception as e:
        logger.warning("CRAG batch scoring failed, defaulting all chunks to ambiguous: %s", e, exc_info=True)
        relevance_list = ["ambiguous"] * len(chunks)

    scored = []
    for chunk, relevance in zip(chunks, relevance_list):
        chunk = dict(chunk)
        chunk["relevance"]  = relevance
        chunk["crag_score"] = SCORE_MAP.get(relevance, 0.5)
        scored.append(chunk)

    return scored


def _parse_batch_response(raw: str, expected: int) -> list[str]:
    """
    Parse the numbered batch response into a list of relevance labels.

    Handles: "1. RELEVANT\n2. IRRELEVANT\n3. AMBIGUOUS"
    Falls back to 'ambiguous' for any unparseable line.
    """
    import re
    lines   = raw.strip().split("\n")
    results = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove leading number and punctuation: "1. RELEVANT" → "RELEVANT"
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip().upper()
        if "IRRELEVANT" in cleaned:
            results.append("irrelevant")
        elif "RELEVANT" in cleaned:
            results.append("relevant")
        elif "AMBIGUOUS" in cleaned:
            results.append("ambiguous")
        # else skip non-label lines

    # Pad or truncate to match expected count
    while len(results) < expected:
        results.append("ambiguous")
    return results[:expected]


def filter_chunks(scored_chunks: list[dict], is_multihop: bool = False) -> tuple[list[dict], str]:
    """
    Filter scored chunks and determine overall confidence level.

    Strategy:
      - Keep all RELEVANT chunks
      - For multihop: also keep AMBIGUOUS (bridging context needed for chain reasoning)
      - For single-hop: drop AMBIGUOUS when RELEVANT exist (reduces noise)
      - Discard IRRELEVANT chunks

    Returns:
        (filtered_chunks, confidence_level)
        confidence_level: 'high' | 'medium' | 'low'
    """
    relevant   = [c for c in scored_chunks if c["relevance"] == "relevant"]
    ambiguous  = [c for c in scored_chunks if c["relevance"] == "ambiguous"]
    irrelevant = [c for c in scored_chunks if c["relevance"] == "irrelevant"]

    if relevant:
        # Always keep ambiguous alongside relevant — they add supporting context
        # especially for image/table chunks that CRAG may under-score
        if ambiguous:
            return relevant + ambiguous, "high"
        return relevant, "high"
    elif ambiguous:
        # Some related content but not definitive answers
        return ambiguous, "medium"
    else:
        # Nothing useful found — return all so LLM can try, flag low confidence
        return scored_chunks, "low"



def _call_llm(prompt: str) -> str:
    if HAS_ANTHROPIC:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=TEXT_LLM_FAST,
            max_tokens=MAX_CRAG_JUDGE_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    if HAS_OPENAI:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=TEXT_LLM,
            max_tokens=MAX_CRAG_JUDGE_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    raise RuntimeError("No LLM configured.")
