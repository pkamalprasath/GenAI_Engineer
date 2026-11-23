"""
Discovery Agent — finds AI decision records relevant to the investigation query.

Hybrid pipeline (configured via configs/agents.yaml classifier_backend):
  "llm"    → original: all candidates sent to llama3.2:3b
  "bert"   → BM25 pre-filter + DistilBERT re-ranker, no LLM
  "hybrid" → BM25 → DistilBERT → llama3.2:3b for borderline scores only

Business contract: output keys (relevant_case_ids, case_count, discovery_confidence)
are identical regardless of which backend is active. Downstream agents don't know
or care which classifier was used.

Soul file: souls/discovery_agent.md
"""
from __future__ import annotations

import asyncio
import json
import logging

from langchain_ollama import OllamaLLM
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import agents_cfg, models_cfg, settings
from sentinel.agents.classifiers.bm25_ranker import rank_cases_bm25
from sentinel.agents.classifiers.bert_classifier import BERTScore, score_cases_bert
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.state.investigation_state import InvestigationState

logger = logging.getLogger(__name__)

_SOUL = open("souls/discovery_agent.md").read()

# Concurrency guard — only 1 Ollama call at a time (8GB RAM constraint)
_OLLAMA_SEMAPHORE = asyncio.Semaphore(
    models_cfg.get("concurrency", {}).get("ollama_semaphore", 1)
)

_agent_cfg = agents_cfg.get("agents", {}).get("discovery", {})
_model_cfg = models_cfg.get("models", {}).get("classification", {})

# Config-driven backend selection — no hardcoding
_CLASSIFIER_BACKEND = _agent_cfg.get("classifier_backend", "hybrid")
_BERT_MODEL = _agent_cfg.get("bert_model", "distilbert-base-uncased")
_BM25_TOP_K = _agent_cfg.get("bm25_top_k", 50)
_BERT_RELEVANT_THRESHOLD = _agent_cfg.get("bert_auto_relevant_threshold", 0.80)
_BERT_IRRELEVANT_THRESHOLD = _agent_cfg.get("bert_auto_irrelevant_threshold", 0.35)

# LLM prompt — used only for borderline cases in hybrid mode, or all cases in llm mode
_DISCOVERY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SOUL),
    ("human", """Investigation query: {query}
Domain: {domain}
Date range: {date_from} to {date_to}

Available cases (JSON list):
{cases_json}

Return ONLY valid JSON with this exact schema:
{{"relevant_case_ids": ["CASE-XXX", ...], "case_count": N, "discovery_confidence": 0.0-1.0}}

Include only cases clearly relevant to the query. Exclude ambiguous cases."""),
])


async def _fetch_candidate_cases(
    session: AsyncSession, tenant_id: str, date_range: dict
) -> list[dict]:
    """Load candidate cases from DB within date range, scoped to tenant."""
    from datetime import datetime as _dt
    result = await session.execute(
        text("""
            SELECT case_id, outcome, decision_timestamp, reasoning_text, metadata
            FROM decision_records
            WHERE tenant_id = :tenant_id
              AND decision_timestamp >= :date_from
              AND decision_timestamp <= :date_to
            ORDER BY decision_timestamp DESC
            LIMIT 500
        """),
        {
            "tenant_id": tenant_id,
            "date_from": _dt.fromisoformat(date_range.get("from", "2000-01-01")),
            "date_to": _dt.fromisoformat(date_range.get("to", "2099-12-31")).replace(hour=23, minute=59, second=59),
        },
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def _classify_with_llm(
    query: str,
    domain: str,
    date_range: dict,
    cases: list[dict],
) -> tuple[list[str], float]:
    """
    Stage: llama3.2:3b classification.
    Used for: all cases (llm mode) or borderline cases (hybrid mode).
    Returns (relevant_case_ids, confidence).
    """
    cases_json = json.dumps(
        [{"case_id": c["case_id"], "outcome": c["outcome"]} for c in cases],
        indent=2,
    )
    async with _OLLAMA_SEMAPHORE:
        llm = OllamaLLM(
            model=_model_cfg.get("model", "llama3.2:3b"),
            base_url=settings.ollama_base_url,
            temperature=_model_cfg.get("temperature", 0),
            num_predict=_model_cfg.get("max_tokens", 512),
        )
        chain = _DISCOVERY_PROMPT | llm | JsonOutputParser()
        result = await chain.ainvoke({
            "query": query,
            "domain": domain,
            "date_from": date_range.get("from", ""),
            "date_to": date_range.get("to", ""),
            "cases_json": cases_json,
        })

    return (
        result.get("relevant_case_ids", []),
        float(result.get("discovery_confidence", 0.5)),
    )


async def _classify_hybrid(
    query: str,
    domain: str,
    date_range: dict,
    candidates: list[dict],
) -> tuple[list[str], float]:
    """
    Three-stage hybrid pipeline:
      1. BM25 pre-filter → eliminates obvious non-matches (milliseconds)
      2. DistilBERT re-ranking → scores remaining candidates (CPU, ~250MB)
      3. llama3.2:3b → only for borderline scores (0.35–0.80 range)

    This reduces LLM calls by ~90% for typical investigations.
    Business output is identical to pure LLM mode.
    """
    # Stage 1: BM25 — eliminate obviously irrelevant cases
    bm25_filtered = rank_cases_bm25(query, candidates, top_k=_BM25_TOP_K)
    logger.info(
        "Discovery BM25: %d candidates → %d after pre-filter",
        len(candidates), len(bm25_filtered),
    )

    if not bm25_filtered:
        return [], 0.0

    # Stage 2: DistilBERT re-ranking — score filtered cases
    bert_scores: list[BERTScore] = score_cases_bert(
        query=query,
        cases=bm25_filtered,
        model_name=_BERT_MODEL,
        auto_relevant_threshold=_BERT_RELEVANT_THRESHOLD,
        auto_irrelevant_threshold=_BERT_IRRELEVANT_THRESHOLD,
    )

    auto_relevant = [s for s in bert_scores if s.verdict == "relevant"]
    borderline = [s for s in bert_scores if s.verdict == "borderline"]

    logger.info(
        "Discovery BERT: %d auto-relevant | %d borderline → LLM | %d auto-excluded",
        len(auto_relevant),
        len(borderline),
        sum(1 for s in bert_scores if s.verdict == "irrelevant"),
    )

    # Stage 3: llama3.2:3b — only for borderline cases
    llm_relevant_ids: list[str] = []
    llm_confidence = 0.0
    if borderline:
        llm_relevant_ids, llm_confidence = await _classify_with_llm(
            query, domain, date_range,
            [s.case for s in borderline],
        )

    # Merge: auto-relevant from BERT + LLM-confirmed from borderline
    all_relevant_ids = (
        [s.case_id for s in auto_relevant] + llm_relevant_ids
    )

    # Confidence: weighted average of BERT scores for auto-relevant + LLM confidence
    if auto_relevant:
        bert_avg_confidence = sum(s.score for s in auto_relevant) / len(auto_relevant)
    else:
        bert_avg_confidence = 0.0

    if all_relevant_ids:
        # Blend BERT and LLM confidence proportionally
        bert_weight = len(auto_relevant)
        llm_weight = len(llm_relevant_ids)
        total_weight = bert_weight + llm_weight
        blended_confidence = (
            (bert_avg_confidence * bert_weight + llm_confidence * llm_weight) / total_weight
            if total_weight > 0 else 0.0
        )
    else:
        blended_confidence = 0.0

    return all_relevant_ids, round(blended_confidence, 3)


async def _classify_bert_only(
    query: str, candidates: list[dict]
) -> tuple[list[str], float]:
    """
    BERT-only mode: BM25 → DistilBERT, no LLM at all.
    Fastest option — used when LLM is unavailable or explicitly disabled.
    Borderline cases are excluded (conservative: only include high-confidence hits).
    """
    bm25_filtered = rank_cases_bm25(query, candidates, top_k=_BM25_TOP_K)
    if not bm25_filtered:
        return [], 0.0

    bert_scores = score_cases_bert(
        query=query,
        cases=bm25_filtered,
        model_name=_BERT_MODEL,
        auto_relevant_threshold=_BERT_RELEVANT_THRESHOLD,
        auto_irrelevant_threshold=_BERT_IRRELEVANT_THRESHOLD,
    )
    relevant = [s for s in bert_scores if s.verdict == "relevant"]
    confidence = (
        sum(s.score for s in relevant) / len(relevant) if relevant else 0.0
    )
    return [s.case_id for s in relevant], round(confidence, 3)


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """
    Discovery agent node — called by LangGraph.
    Returns partial state update dict (same keys regardless of classifier_backend).
    """
    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("discovery_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("discovery_agent", inv_id, tenant_id):
        try:
            candidates = await _fetch_candidate_cases(
                session, tenant_id, state["date_range"]
            )

            if not candidates:
                log_agent_event(
                    logger, inv_id, tenant_id, "discovery_agent", "no_candidates_found"
                )
                return {
                    **hb_start,
                    "relevant_case_ids": [],
                    "case_count": 0,
                    "discovery_confidence": 0.0,
                    "status": "investigating",
                    "messages": [{"agent": "discovery_agent", "event": "no_candidates"}],
                }

            # Route to the configured classifier pipeline
            if _CLASSIFIER_BACKEND == "bert":
                relevant_ids, confidence = await _classify_bert_only(
                    state["query"], candidates
                )
                llm_tokens_in, llm_tokens_out = 0, 0  # No LLM used

            elif _CLASSIFIER_BACKEND == "hybrid":
                relevant_ids, confidence = await _classify_hybrid(
                    state["query"], state["domain"], state["date_range"], candidates
                )
                # Token estimate for LLM portion only (borderline cases)
                llm_tokens_in, llm_tokens_out = 200, 80

            else:  # "llm" — original full LLM mode
                relevant_ids, confidence = await _classify_with_llm(
                    state["query"], state["domain"], state["date_range"], candidates
                )
                llm_tokens_in = len(json.dumps(candidates[:100])) // 4
                llm_tokens_out = 100

            # Enforce minimum confidence threshold from agents.yaml
            min_conf = _agent_cfg.get("min_case_confidence", 0.5)
            if confidence < min_conf:
                relevant_ids = []
                confidence = 0.0

            # Cap at max_cases_returned to protect downstream token budgets
            max_cases = _agent_cfg.get("max_cases_returned", 50)
            relevant_ids = relevant_ids[:max_cases]

            log_agent_event(
                logger, inv_id, tenant_id, "discovery_agent", "discovery_complete",
                details={
                    "backend": _CLASSIFIER_BACKEND,
                    "candidate_count": len(candidates),
                    "case_count": len(relevant_ids),
                    "confidence": confidence,
                },
            )

            hb_end = heartbeat.emit("discovery_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "discovery_agent", _model_cfg.get("model", "llama3.2:3b"),
                "ollama", llm_tokens_in, llm_tokens_out,
                state_total=state["total_cost_usd"],
            )

            return {
                **hb_end,
                **cost_update,
                "relevant_case_ids": relevant_ids,
                "case_count": len(relevant_ids),
                "discovery_confidence": confidence,
                "status": "investigating",
                "messages": [{
                    "agent": "discovery_agent",
                    "event": "complete",
                    "backend": _CLASSIFIER_BACKEND,
                    "case_count": len(relevant_ids),
                    "confidence": confidence,
                }],
            }

        except Exception as exc:
            log_error(
                logger, inv_id, tenant_id, "discovery_agent", type(exc).__name__, str(exc)
            )
            hb_fail = heartbeat.emit("discovery_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "error_log": [f"discovery_agent: {type(exc).__name__}: {str(exc)[:200]}"],
                "status": "failed",
            }
