"""
Pattern Extractor — uses LLM to extract 3-5 compliance patterns from a final report.

Called by report_agent after writing the final report.
Extracted patterns are stored in investigation_patterns via pattern_store.py.
Future legal agent calls retrieve relevant past patterns and inject them into their
system prompt, giving SENTINEL institutional memory across investigations.
"""
from __future__ import annotations

import json
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.memory.pattern_store import store_patterns, _embed

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """You are a compliance knowledge curator.

Read this compliance investigation report and extract 3-5 concise, reusable patterns.
Each pattern should be a factual observation that would help future investigations in
the same domain. Focus on: which regulations were triggered, what demographic patterns
were found, what denial reasons appeared, and what risk indicators emerged.

Report:
{report}

Respond ONLY with valid JSON — no markdown, no explanation:
[
  {{
    "pattern_text": "One clear sentence describing the compliance pattern observed",
    "regulation": "ECOA | HMDA | FCRA | FDA_21CFR | EU_AI_ACT | etc (most relevant one)"
  }},
  ...
]

Rules:
- Maximum 5 patterns
- Each pattern_text must be self-contained and under 150 characters
- Focus on patterns that would generalize to future investigations
- Never include PII or specific case IDs
- If the report shows COMPLIANT, extract what was verified as compliant
"""


async def extract_and_store(
    session: AsyncSession,
    report: str,
    domain: str,
    investigation_id: str,
) -> int:
    """
    Extract compliance patterns from the report and store them.

    Called after report_agent completes. Silently absorbs failures —
    pattern extraction is non-critical and must never block the pipeline.

    Returns number of patterns stored.
    """
    if not report or len(report) < 100:
        return 0

    try:
        raw_patterns = await _call_llm(report[:6000])
        if not raw_patterns:
            return 0

        # Embed each pattern for future similarity retrieval
        enriched = []
        for p in raw_patterns[:5]:
            text_val = p.get("pattern_text", "").strip()
            if not text_val:
                continue
            embedding = await _embed(text_val)
            enriched.append({
                "pattern_text": text_val,
                "regulation":   p.get("regulation", ""),
                "embedding":    embedding,
            })

        stored = await store_patterns(session, enriched, domain)
        logger.info(
            '{"event":"patterns_extracted","investigation_id":"%s","stored":%d}',
            investigation_id, stored,
        )
        return stored

    except Exception as exc:
        logger.warning(
            '{"event":"pattern_extraction_failed","investigation_id":"%s","error":"%s"}',
            investigation_id, str(exc)[:100],
        )
        return 0


async def _call_llm(report_excerpt: str) -> list[dict]:
    """Call LLM to extract patterns. Returns list of pattern dicts."""
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": _EXTRACT_PROMPT.format(report=report_excerpt),
                }
            ],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as exc:
        logger.warning('{"event":"pattern_llm_failed","error":"%s"}', str(exc)[:100])
        return []
