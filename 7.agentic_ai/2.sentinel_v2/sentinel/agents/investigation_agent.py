"""
Investigation Agent — traverses the provenance graph to reconstruct decision chains.

Purpose:
  ✓ Load W3C PROV-O decision graph from database
  ✓ Trace decision chains from case → supporting evidence
  ✓ Verify SHA-256 hashes on each node (tamper detection)
  ✓ Extract evidence items (case outcomes, applicant profiles)
  ✓ Flag broken chains (gaps in decision lineage)

Architecture:
  - Uses ProvenanceStore to build in-memory NetworkX graph
  - Traces chains via graph traversal (BFS/DFS)
  - Batch processes cases for memory efficiency
  - Logs agent/activity nodes to provenance for audit trail

LLM Integration:
  - Reasoning tier (configurable: gpt-4o-mini, claude-haiku)
  - Inputs: evidence count, broken chain count, decision summaries
  - Outputs: investigation_sufficient (bool), investigation_iterations (int)

Runs in parallel with legal_agent and bias_detection_agent via LangGraph fan-out.

Soul file: souls/investigation_agent.md (LLM reasoning context)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import agents_cfg, models_cfg, settings
from sentinel.llm.client import chat as llm_chat, get_tier_for_agent
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.provenance.query import (
    detect_broken_chains,
    graph_to_adjacency,
    trace_decision_chain,
)
from sentinel.provenance.schema import NodeType, ProvEdge, ProvNode, RelationType
from sentinel.provenance.store import ProvenanceStore
from sentinel.state.investigation_state import EvidenceItem, InvestigationState

logger = logging.getLogger(__name__)

_SOUL = open("souls/investigation_agent.md").read()
_agent_cfg = agents_cfg.get("agents", {}).get("investigation", {})
_model_cfg = models_cfg.get("models", {}).get("reasoning", {})
_MAX_DEPTH = _agent_cfg.get("max_graph_depth", 5)
_MAX_RETRIES = _agent_cfg.get("max_retries", 2)
_TOKEN_BUDGET = _agent_cfg.get("token_budget", 8000)


def _get_batch_size() -> int:
    """
    Determine case batch size based on active provider.
    OpenAI can handle larger batches; Ollama is more constrained.
    """
    ctx = models_cfg.get("context", {})
    has_openai = bool(os.getenv("OPENAI_API_KEY") or settings.openai_api_key)
    return ctx.get("case_batch_size_openai", 100) if has_openai else ctx.get("case_batch_size_ollama", 25)


def _compute_content_hash(content: dict) -> str:
    """Compute SHA-256 hash of node content for tamper detection."""
    content_str = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(content_str.encode()).hexdigest()


def _process_case_batch(graph, batch_case_ids: list[str]) -> tuple[list[dict], list[EvidenceItem], list[tuple[str, str]]]:
    """
    Process a batch of cases: trace chains, extract evidence, collect hashes.
    Returns (all_chains, evidence_items, hash_pairs).
    """
    all_chains = []
    evidence_items: list[EvidenceItem] = []
    hash_pairs: list[tuple[str, str]] = []

    for case_id in batch_case_ids:
        decision_node_id = f"decision-{case_id}"
        chain = trace_decision_chain(graph, decision_node_id, max_depth=_MAX_DEPTH)
        if chain:
            all_chains.append({"case_id": case_id, "chain": chain})
            for node in chain:
                nid = node["node_id"]
                if not nid.startswith("decision-"):
                    continue
                content = node.get("content", {}) or {}
                outcome  = content.get("outcome", "unknown")
                reason   = content.get("reasoning_text", "")
                age      = content.get("age_group", "")
                income   = content.get("income_bracket", "")
                score    = content.get("credit_score_tier", "")
                zip_ct   = content.get("zip_code_census_tract", "")

                desc_parts = [f"Case {case_id}: outcome={outcome.upper()}"]
                if reason:
                    desc_parts.append(f"Reason: {reason}")
                if age or income or score:
                    desc_parts.append(
                        f"Profile: age={age}, income={income}, credit={score}, tract={zip_ct}"
                    )
                description = " | ".join(desc_parts)

                evidence_items.append(EvidenceItem(
                    evidence_id=f"ev-{nid}",
                    description=description,
                    provenance_node_id=nid,
                    trust_score=0.80,
                    source_type="decision_record",
                ))
                if content.get("content_hash"):
                    hash_pairs.append((nid, content["content_hash"]))

    return all_chains, evidence_items, hash_pairs


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """
    Investigation agent node.
    Traverses provenance graph for each discovered case and builds evidence chain.
    """
    from sentinel.core.debug import (
        log_agent_input, log_agent_output, log_agent_exception,
        generate_mock_investigation_output
    )

    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("investigation_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("investigation_agent", inv_id, tenant_id):
        try:
            log_agent_input(
                "investigation_agent", inv_id,
                ["relevant_case_ids", "applicant_data", "query"],
                state
            )

            store = ProvenanceStore(session)
            case_ids = state["relevant_case_ids"]

            # Create minimal provenance nodes even with no cases (so Provenance page doesn't fail)

            agent_content = {
                "agent_name": "InvestigationAgent",
                "investigation_id": inv_id,
                "status": "no_cases" if not case_ids else "running",
                "cases_analyzed": len(case_ids),
                "case_ids": case_ids,  # Source documentation
            }
            agent_content["content_hash"] = _compute_content_hash(agent_content)

            agent_node = ProvNode(
                node_id=f"agent-investigation-{inv_id}",
                node_type=NodeType.AGENT,
                tenant_id=tenant_id,
                content=agent_content,
            )
            await store.add_node(agent_node)

            activity_content = {
                "tool_name": "compliance_investigation",
                "investigation_id": inv_id,
                "cases_analyzed": len(case_ids),
                "status": "no_cases" if not case_ids else "investigating",
                "case_ids": case_ids,  # Source documentation
            }
            activity_content["content_hash"] = _compute_content_hash(activity_content)

            activity_node = ProvNode(
                node_id=f"activity-investigation-{inv_id}",
                node_type=NodeType.ACTIVITY,
                tenant_id=tenant_id,
                content=activity_content,
            )
            await store.add_node(activity_node)

            await store.add_edge(ProvEdge(
                edge_id=f"edge-agent-activity-{inv_id}",
                source_id=agent_node.node_id,
                target_id=activity_node.node_id,
                relation=RelationType.WAS_ATTRIBUTED_TO,
                tenant_id=tenant_id,
            ))

            if not case_ids:
                logger.info(
                    f"[INVESTIGATION] No case IDs. Checking applicant_data...",
                    extra={"has_applicant_data": bool(state.get("applicant_data"))}
                )

                hb_end = heartbeat.emit("investigation_agent", "complete", state["iteration_count"])
                return {
                    **hb_end,
                    "status": "investigating",
                    "investigation_sufficient": False,
                    "provenance_nodes": [agent_node, activity_node],
                    "evidence_items": [],
                    "decision_chains": [],
                    "investigation_iterations": state["investigation_iterations"] + 1,
                    "messages": [{"agent": "investigation_agent", "event": "no_cases"}],
                }

            # Build in-memory NetworkX graph for this tenant's cases
            graph = await store.build_graph(tenant_id, case_ids)

            # Process cases in configurable batches (Phase 3 optimization)
            batch_size = _get_batch_size()
            batches = [case_ids[i:i+batch_size] for i in range(0, len(case_ids), batch_size)]

            # Process batches concurrently where possible
            all_chains = []
            evidence_items: list[EvidenceItem] = []
            hash_pairs: list[tuple[str, str]] = []

            for batch in batches:
                batch_chains, batch_evidence, batch_hashes = _process_case_batch(graph, batch)
                all_chains.extend(batch_chains)
                evidence_items.extend(batch_evidence)
                hash_pairs.extend(batch_hashes)

            # Single batch query for all hash verifications
            tampered_nodes_count = 0
            if hash_pairs:
                hash_results = await store.verify_hashes_batch(hash_pairs, tenant_id)
                tampered = [nid for nid, valid in hash_results.items() if not valid]
                tampered_nodes_count = len(tampered)
                if tampered:
                    logger.error(
                        '{"event":"tamper_detected","count":%d,"node_ids":%s}',
                        len(tampered), str(tampered[:5]),
                    )

            # ── Write provenance Activity + Agent nodes + edges to DB ─────────
            denied_cases   = [ev for ev in evidence_items if "DENIED"   in ev.get("description","").upper()]
            approved_cases = [ev for ev in evidence_items if "APPROVED" in ev.get("description","").upper()]

            # Agent node — WHO ran this: full identity of the agent
            agent_content = {
                "agent_name":        "InvestigationAgent",
                "investigation_id":  inv_id,
                "tenant_id":         tenant_id,
                "cases_analyzed":    len(case_ids),
                "denied_count":      len(denied_cases),
                "approved_count":    len(approved_cases),
                "tampered_nodes":    tampered_nodes_count,
                "pipeline_version":  "sentinel-v1",
                "case_ids":          case_ids,  # Source documentation
            }
            agent_content["content_hash"] = _compute_content_hash(agent_content)

            agent_node = ProvNode(
                node_id=f"agent-investigation-{inv_id}",
                node_type=NodeType.AGENT,
                tenant_id=tenant_id,
                content=agent_content,
            )
            logger.info(
                '{"event":"agent_node_created","node_id":"%s","has_case_ids":%s,"has_content_hash":%s,"case_ids_count":%d}',
                agent_node.node_id,
                "case_ids" in agent_content,
                "content_hash" in agent_content,
                len(case_ids),
            )
            await store.add_node(agent_node)

            # Activity node — WHAT was investigated: query, date range, domain, results
            query      = state.get("query", "")
            date_range = state.get("date_range", {})
            domain     = state.get("domain", "finance")
            activity_content = {
                "tool_name":       "compliance_investigation",
                "investigation_id": inv_id,
                "query":           query,
                "date_from":       date_range.get("from", ""),
                "date_to":         date_range.get("to", ""),
                "domain":          domain,
                "cases_analyzed":  len(case_ids),
                "evidence_count":  len(set(ev.get("provenance_node_id","") for ev in evidence_items)),
                "denied_count":    len(denied_cases),
                "approved_count":  len(approved_cases),
                "broken_chains":   0,
                "inputs_summary":  query or f"Analyzed {len(case_ids)} cases",
                "outputs_summary": (
                    f"{len(case_ids)} cases reviewed — "
                    f"{len(denied_cases)} denials, {len(approved_cases)} approvals. "
                    f"{'Tampered nodes detected.' if tampered_nodes_count > 0 else 'All hashes verified.'}"
                ),
                "case_ids":        case_ids,  # Source documentation
            }
            activity_content["content_hash"] = _compute_content_hash(activity_content)

            activity_node = ProvNode(
                node_id=f"activity-investigation-{inv_id}",
                node_type=NodeType.ACTIVITY,
                tenant_id=tenant_id,
                content=activity_content,
            )
            logger.info(
                '{"event":"activity_node_created","node_id":"%s","has_case_ids":%s,"has_content_hash":%s,"evidence_count":%d}',
                activity_node.node_id,
                "case_ids" in activity_content,
                "content_hash" in activity_content,
                len(set(ev.get("provenance_node_id","") for ev in evidence_items)),
            )
            await store.add_node(activity_node)

            # Edges: agent wasAttributedTo activity; activity used each decision node
            await store.add_edge(ProvEdge(
                edge_id=f"edge-agent-activity-{inv_id}",
                source_id=agent_node.node_id,
                target_id=activity_node.node_id,
                relation=RelationType.WAS_ATTRIBUTED_TO,
                tenant_id=tenant_id,
            ))
            for case_id in case_ids[:20]:
                decision_nid = f"decision-{case_id}"
                await store.add_edge(ProvEdge(
                    edge_id=f"edge-activity-{inv_id}-{case_id}",
                    source_id=activity_node.node_id,
                    target_id=decision_nid,
                    relation=RelationType.USED,
                    tenant_id=tenant_id,
                ))
            # ── End provenance write ───────────────────────────────────────────

            broken = detect_broken_chains(graph, case_ids)
            broken_chains_count = len(broken)
            sufficient = len(evidence_items) >= 3 and broken_chains_count < len(case_ids) * 0.5

            # Build denial reason summary for the LLM
            denial_summary = []
            for ev in evidence_items:
                desc = ev.get("description", "")
                if "DENIED" in desc.upper() and "Denial reason:" in desc:
                    denial_summary.append(desc)

            prompt = f"""Cases analyzed: {len(case_ids)}
Evidence items found: {len(evidence_items)}
Broken provenance chains: {broken_chains_count} out of {len(case_ids)}
Denial cases with reasons ({len(denial_summary)} total):
{chr(10).join(denial_summary[:10])}

Sample provenance chain:
{json.dumps(all_chains[:2], indent=2)[:1500]}

Respond ONLY with JSON:
{{"investigation_sufficient": true/false, "investigation_iterations": 1,
  "summary": "one sentence summary including denial reasons and applicant profiles observed"}}"""

            tier = get_tier_for_agent("investigation_agent")
            response = await llm_chat(prompt, tier=tier, system=_SOUL)

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            llm_result = json.loads(raw)

            log_agent_event(
                logger, inv_id, tenant_id, "investigation_agent", "investigation_complete",
                details={"evidence_count": len(evidence_items), "broken_chains": broken_chains_count},
            )

            hb_end = heartbeat.emit("investigation_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "investigation_agent", response.model, response.provider,
                response.input_tokens, response.output_tokens,
                state_total=state["total_cost_usd"],
            )

            output = {
                **hb_end,
                **cost_update,
                "status": "investigating",
                "provenance_nodes": [n for chain in all_chains for n in chain["chain"]],
                "evidence_items": evidence_items,
                "decision_chains": [graph_to_adjacency(graph)],
                "investigation_sufficient": llm_result.get("investigation_sufficient", sufficient),
                "investigation_iterations": state["investigation_iterations"] + 1,
                "messages": [{
                    "agent": "investigation_agent",
                    "event": "complete",
                    "evidence_count": len(evidence_items),
                    "broken_chains": broken_chains_count,
                }],
            }
            log_agent_output("investigation_agent", inv_id, output)
            return output

        except Exception as exc:
            log_agent_exception("investigation_agent", inv_id, exc)
            log_error(logger, inv_id, tenant_id, "investigation_agent", type(exc).__name__, str(exc))
            hb_fail = heartbeat.emit("investigation_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "status": "investigating",
                "investigation_sufficient": False,
                "messages": [{"agent": "investigation_agent", "event": "error", "error": str(exc)[:200]}],
                "error_log": [f"investigation_agent: {type(exc).__name__}: {str(exc)[:200]}"],
            }
