"""
judge.py — LLM-as-judge evaluation, same pattern as your experiments.

This is the same evaluation approach used in experiments 05-10:
Ask an LLM to score each answer on relevance, correctness, and completeness.

The LLM acts as an expert evaluator who:
  1. Reads the question
  2. Reads the ground truth answer
  3. Reads the system's answer
  4. Scores each dimension 1-5

SCORING RUBRIC (same as experiments):
  5 = Perfect match with ground truth, complete and accurate
  4 = Mostly correct with minor omissions or slight inaccuracies
  3 = Partially correct, missing important information
  2 = Mostly incorrect but some relevant content
  1 = Completely wrong or irrelevant

EXTENDED METRICS (beyond the original experiments):
  - factuality     : are facts verifiable in retrieved context?
  - citation_ok    : does the cited source actually exist?
"""

import json

from openai import OpenAI
from configs.settings import OPENAI_API_KEY, ANTHROPIC_API_KEY, TEXT_LLM, TEXT_LLM_FAST, HAS_OPENAI, HAS_ANTHROPIC


# ── Prompts ────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """Score this RAG system answer on three dimensions (1-5 each).

Question: {question}
Ground Truth Answer: {ground_truth}
System Answer: {answer}

Scoring rubric (1-5):
5 = Perfect: complete, accurate, matches ground truth
4 = Good: mostly correct, minor omissions
3 = Fair: partially correct, missing key information
2 = Poor: mostly incorrect but some relevant content
1 = Bad: completely wrong or irrelevant

Return ONLY valid JSON with no other text:
{{"relevance": <int>, "correctness": <int>, "completeness": <int>}}"""


FACTUALITY_PROMPT = """Given this retrieved context and this answer, assess factuality.

Context:
{context}

Answer:
{answer}

For each factual claim in the answer (numbers, specific values, names, procedures),
check if it is supported by the context.

Return ONLY valid JSON:
{{"factual_claims": <int>, "supported_claims": <int>, "factuality_score": <float 0-1>}}"""


def judge_answer(
    question: str,
    ground_truth: str,
    answer: str,
) -> dict:
    """
    Score an answer using LLM-as-judge.

    Same API as used in your experiments (07-10).
    Returns dict with: relevance, correctness, completeness (all 1-5)
    and avg_score (average of the three).
    """
    prompt = JUDGE_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        answer=answer,
    )
    try:
        raw = _call_llm(prompt, max_tokens=128)
        # Extract JSON from response
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        scores = json.loads(raw[start:end])

        # Validate and clamp scores
        for key in ("relevance", "correctness", "completeness"):
            scores[key] = max(1, min(5, int(scores.get(key, 3))))

        scores["avg_score"] = round(
            (scores["relevance"] + scores["correctness"] + scores["completeness"]) / 3, 3
        )
        return scores
    except Exception as e:
        print(f"  [Judge] Scoring failed: {e}")
        return {"relevance": 0, "correctness": 0, "completeness": 0, "avg_score": 0.0}


def judge_factuality(context_chunks: list[dict], answer: str) -> dict:
    """
    Check how many claims in the answer are supported by the retrieved context.

    Returns: {factual_claims, supported_claims, factuality_score}
    """
    context_str = "\n\n".join(c.get("content", "") for c in context_chunks)
    prompt = FACTUALITY_PROMPT.format(context=context_str[:3000], answer=answer)

    try:
        raw = _call_llm(prompt, max_tokens=128)
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        result = json.loads(raw[start:end])
        return result
    except Exception:
        return {"factual_claims": 0, "supported_claims": 0, "factuality_score": 0.0}


def _call_llm(prompt: str, max_tokens: int = 128) -> str:
    if HAS_ANTHROPIC:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=TEXT_LLM_FAST,
            max_tokens=max_tokens,
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

    raise RuntimeError("No LLM configured.")
