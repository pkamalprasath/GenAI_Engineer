"""
adaptive_router.py — Classify queries as simple or complex before retrieval.

WHY DO WE NEED THIS?
Not every question requires searching our document database.

"What is Newton's second law?" → LLM already knows this (general knowledge)
"What is the pressure rating of valve V-200?" → Must search our docs (specific)

Doing full RAG for every simple query:
  - Wastes ~1.5 seconds of embedding + vector search
  - Increases database load (1000 queries/min SLA from case study is harder)
  - Increases cost (embedding + search have per-call costs)

FROM THE IMPLEMENTATION GUIDE:
"Adaptive-RAG: route simple queries differently from complex"

ROUTING LOGIC:
  SIMPLE  → Answer directly with LLM (no retrieval)
             Use case: general knowledge, math, definitions of standard terms
             Target latency: ~0.5s

  COMPLEX → Full RAG pipeline (HyDE + search + CRAG + generation)
             Use case: company-specific info, product specs, procedures
             Target latency: ~2s

HOW CLASSIFICATION WORKS:
We use a small LLM call to classify the query. This is fast (~0.2s)
and much more accurate than keyword matching.

Signals of a COMPLEX (retrieval-needed) query:
  - Contains product names, part numbers, model numbers
  - Asks about "our" system, equipment, or documents
  - Asks about specific specs, tolerances, procedures
  - Contains "in the manual", "according to", "as specified"

Signals of a SIMPLE (no-retrieval) query:
  - Asks for definitions of standard industry terms
  - General physics/chemistry/engineering questions
  - Calculation questions with given values
  - Conversational questions
"""

import logging

from openai import OpenAI
from configs.settings import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    TEXT_LLM,
    TEXT_LLM_FAST,
    HAS_OPENAI,
    HAS_ANTHROPIC,
    ROUTER_CLASSIFY_MAX_TOKENS,
    ROUTER_ANSWER_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


# Classification prompt — returns just one word: SIMPLE or COMPLEX
ROUTER_PROMPT = """You are a query classifier for an engineering document search system
that indexes pump manuals, safety data sheets, and technical datasheets.

Classify the following question as either:
- SIMPLE: Pure conversational or trivially general (e.g. "hello", "what is 2+2", "what does PDF stand for")
- COMPLEX: Anything about engineering, components, specifications, diagrams, procedures, chemicals, safety, maintenance, materials, dimensions, tolerances, standards, or equipment — even if it sounds like general knowledge

When in doubt, always choose COMPLEX. It is ALWAYS better to search the documents.

SIMPLE examples (extremely rare):
  "hello", "thanks", "what is your name", "what year is it"

COMPLEX examples (almost everything else):
  thread pitch specs, bearing diagrams, maintenance procedures, chemical safety,
  bolt torque values, operating temperatures, lubrication intervals, wiring details,
  any question about a physical component, material, or technical process

Respond with ONLY one word: SIMPLE or COMPLEX

Question: {query}"""


def classify_query(query: str) -> str:
    """
    Classify a query as 'simple' or 'complex'.

    Returns:
        'simple'  → answer directly, no retrieval needed
        'complex' → run full RAG pipeline

    Defaults to 'complex' on any failure (safer: better to over-retrieve
    than to miss a document-specific answer).
    """
    prompt = ROUTER_PROMPT.format(query=query)

    try:
        result = _call_llm(prompt, max_tokens=ROUTER_CLASSIFY_MAX_TOKENS)
        result = result.strip().upper()

        if result == "SIMPLE":
            return "simple"
        else:
            return "complex"
    except Exception as e:
        logger.warning("Router classification failed, defaulting to complex: %s", e, exc_info=True)
        return "complex"   # safe default


def answer_simple_query(query: str) -> str:
    """
    Answer a simple query directly without retrieval.

    Used when classify_query() returns 'simple'.
    No context is passed — the LLM uses its pretrained knowledge.
    """
    prompt = (
        f"Answer this engineering/technical question clearly and concisely.\n\n"
        f"Question: {query}\n\nAnswer:"
    )
    try:
        return _call_llm(prompt, max_tokens=ROUTER_ANSWER_MAX_TOKENS)
    except Exception as e:
        return f"Could not generate answer: {e}"


def _call_llm(prompt: str, max_tokens: int = 512) -> str:
    if HAS_ANTHROPIC:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=TEXT_LLM_FAST,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    if HAS_OPENAI:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=TEXT_LLM,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    raise RuntimeError("No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
