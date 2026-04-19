"""
hyde.py — Hypothetical Document Embeddings (HyDE) query expansion.

WHAT IS HYDE?
A user query is typically short: "M12 bolt torque spec" (4 words).
Document chunks are long: full paragraphs from the manual.

When we embed both and compare them, the short query and the long chunk
live in slightly different regions of the embedding space — even if they're
about the same topic. This hurts retrieval quality.

HyDE SOLUTION:
Before embedding the query, ask the LLM to write a hypothetical answer
document (as if the information exists in the manual). This hypothetical
document:
1. Uses the same technical vocabulary as real documents
2. Is similar in length to actual document chunks
3. Bridges the vocabulary gap (user's words → document's words)

We embed the HYPOTHETICAL DOCUMENT, not the original short query.

EXPERIMENT RESULT:
Your experiment 08_retrieval_methods.py showed:
  R4_HyDE: 4.9 (highest)
  R1_Dense: 4.833
  R3_Hybrid: 4.767

The 0.067 improvement is meaningful for precision-critical engineering queries.
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
    MAX_HYDE_TOKENS,
    HYDE_TEMPERATURE,
)


HYDE_PROMPT = """You are a technical document expert. Given a question about engineering,
manufacturing, or safety, write a short technical paragraph (80-120 words) that would
be a direct answer to this question — as if it were text from an engineering manual,
datasheet, or safety document.

Use precise technical language. Include specific values, units, and terminology where
appropriate. Do NOT say "I don't know" — write the most likely technical content
even if you are uncertain.

Question: {query}

Technical paragraph:"""


def expand_with_hyde(query: str) -> str:
    """
    Generate a hypothetical answer document for a query.

    The caller then embeds this text (not the original query) for retrieval.

    Args:
        query: the user's natural language question

    Returns:
        Hypothetical document text (80-120 words).
        Falls back to the original query if LLM call fails.
    """
    prompt = HYDE_PROMPT.format(query=query)

    try:
        if HAS_ANTHROPIC:
            return _call_anthropic(prompt)
        elif HAS_OPENAI:
            return _call_openai(prompt)
    except Exception as e:
        logger.warning("HyDE LLM call failed, falling back to original query: %s", e, exc_info=True)

    # Fallback: use original query (standard dense retrieval)
    return query


def _call_openai(prompt: str) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=TEXT_LLM,
        max_tokens=MAX_HYDE_TOKENS,
        temperature=HYDE_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


def _call_anthropic(prompt: str) -> str:
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=TEXT_LLM_FAST,
        max_tokens=MAX_HYDE_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
