"""
query_decomposer.py — Break multihop questions into simple sub-questions.

WHY THIS EXISTS:
A multihop question like "Is Chevron ISO VG 220 safe at T4 operating temperature?"
requires two separate lookups:
  1. What is the T4 max operating temperature? (pump manual table)
  2. What is the operating range of ISO VG 220? (SDS table)

A single vector search rarely returns both chunks in the top-5.
By decomposing into sub-questions and retrieving each separately,
we ensure both relevant chunks are in the context before generation.

WHEN NOT TO DECOMPOSE:
Simple questions ("What is the M12 thread pitch?") are already single-hop.
The LLM is instructed to return just the original query in that case.
"""

import logging

from anthropic import Anthropic
from openai import OpenAI

from configs.settings import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    TEXT_LLM_FAST,
    TEXT_LLM,
    HAS_ANTHROPIC,
    HAS_OPENAI,
    MAX_HYDE_TOKENS,
    DECOMP_MAX_SUBQUERIES,
    DECOMP_MIN_QUERY_LENGTH,
)

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """Break this engineering question into simple sub-questions.
Each sub-question must be answerable from a single document section (one table row, one paragraph, or one diagram caption).

Rules:
- If the question is already simple (answerable from one source), return ONLY: 1. {query}
- Sub-questions should be specific and self-contained
- Do NOT include reasoning steps, only the sub-questions
- Use up to 4 sub-questions for complex multi-step questions
- For 3-hop chains (e.g. "sensor reads X → what class → what limit?"), create one sub-question per hop

Question: {query}

Return ONLY a numbered list:"""


def decompose_query(query: str) -> list[str]:
    """
    Break a query into sub-questions for separate retrieval passes.

    Returns a list of sub-question strings.
    Falls back to [query] if decomposition fails or query is already simple.
    """
    prompt = DECOMPOSE_PROMPT.format(query=query)

    try:
        raw = _call_llm(prompt)
        sub_queries = _parse_sub_questions(raw, query)
        # If decomposition returned only the original query, no benefit
        if len(sub_queries) <= 1:
            return [query]
        return sub_queries
    except Exception as e:
        logger.warning("Query decomposition failed, using original query: %s", e, exc_info=True)
        return [query]   # safe fallback: treat as single query


def _parse_sub_questions(raw: str, original: str) -> list[str]:
    """Parse numbered list response into clean sub-question strings."""
    lines = raw.strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip leading number + period/paren: "1. " or "1) "
        import re
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        if cleaned and len(cleaned) > DECOMP_MIN_QUERY_LENGTH:
            results.append(cleaned)

    if not results:
        return [original]

    return results[:DECOMP_MAX_SUBQUERIES]


def _call_llm(prompt: str) -> str:
    if HAS_ANTHROPIC:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=TEXT_LLM_FAST,
            max_tokens=MAX_HYDE_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    if HAS_OPENAI:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=TEXT_LLM,
            max_tokens=MAX_HYDE_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    raise RuntimeError("No LLM configured.")
