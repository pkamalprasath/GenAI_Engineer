"""
Investigation Agent — traverses the provenance graph to reconstruct decision chains.

Uses the unified LLM client — provider determined by configs/models.yaml
reasoning.provider (openai | anthropic). Zero code changes to switch providers.
Runs in parallel with legal_agent and bias_detection_agent via LangGraph fan-out.

Soul file: souls/investigation_agent.md
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import agents_cfg, models_cfg, settings
from sentinel.llm.client import chat as llm_chat
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


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """
    Investigation agent node.
    Traverses provenance graph for each discovered case and builds evidence chain.
    """
    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("investigation_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("investigation_agent", inv_id, tenant_id):
        try:
            store = ProvenanceStore(session)
            case_ids = state["relevant_case_ids"]

            if not case_ids:
                return {
                    **hb_start,
                    "status": "investigating",
                    "investigation_sufficient": False,
                    "messages": [{"agent": "investigation_agent", "event": "no_cases"}],
                    "error_log": ["investigation_agent: no cases to investigate"],
                }

            # Build in-memory NetworkX graph for this tenant's cases
            graph = await store.build_graph(tenant_id, case_ids)

            # Trace decision chain for each case
            all_chains = []
            evidence_items: list[EvidenceItem] = []

            # Collect all chains first, then batch-verify hashes (avoids N+1 queries)
            hash_pairs: list[tuple[str, str]] = []
            for case_id in case_ids[:20]:  # Cap at 20 to stay within token budget
                decision_node_id = f"decision-{case_id}"
                chain = trace_decision_chain(graph, decision_node_id, max_depth=_MAX_DEPTH)
                if chain:
                    all_chains.append({"case_id": case_id, "chain": chain})
                    for node in chain:
                        nid = node["node_id"]
                        # Only include the decision node itself — skip agent/activity
                        # nodes from other investigations to keep evidence clean
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

            # Single batch query for all hash verifications
            if hash_pairs:
                hash_results = await store.verify_hashes_batch(hash_pairs, tenant_id)
                tampered = [nid for nid, valid in hash_results.items() if not valid]
                if tampered:
                    logger.error(
                        '{"event":"tamper_detected","count":%d,"node_ids":%s}',
                        len(tampered), str(tampered[:5]),
                    )

            # ── Write provenance Activity + Agent nodes + edges to DB ─────────
            denied_cases   = [ev for ev in evidence_items if "DENIED"   in ev.get("description","").upper()]
            approved_cases = [ev for ev in evidence_items if "APPROVED" in ev.get("description","").upper()]

            # Agent node — WHO ran this: full identity of the agent
            agent_node = ProvNode(
                node_id=f"agent-investigation-{inv_id}",
                node_type=NodeType.AGENT,
                tenant_id=tenant_id,
                content={
                    "agent_name":        "InvestigationAgent",
                    "investigation_id":  inv_id,
                    "tenant_id":         tenant_id,
                    "cases_analyzed":    len(case_ids),
                    "denied_count":      len(denied_cases),
                    "approved_count":    len(approved_cases),
                    "tampered_nodes":    len(tampered) if 'tampered' in dir() else 0,
                    "pipeline_version":  "sentinel-v1",
                },
            )
            await store.add_node(agent_node)

            # Activity node — WHAT was investigated: query, date range, domain, results
            query      = state.get("query", "")
            date_range = state.get("date_range", {})
            domain     = state.get("domain", "finance")
            activity_node = ProvNode(
                node_id=f"activity-investigation-{inv_id}",
                node_type=NodeType.ACTIVITY,
                tenant_id=tenant_id,
                content={
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
                    "broken_chains":   len(broken) if 'broken' in dir() else 0,
                    "inputs_summary":  query or f"Analyzed {len(case_ids)} cases",
                    "outputs_summary": (
                        f"{len(case_ids)} cases reviewed — "
                        f"{len(denied_cases)} denials, {len(approved_cases)} approvals. "
                        f"{'Tampered nodes detected.' if ('tampered' in dir() and tampered) else 'All hashes verified.'}"
                    ),
                },
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

            # Use Haiku to assess if investigation is sufficient
            broken = detect_broken_chains(graph, case_ids)
            sufficient = len(evidence_items) >= 3 and len(broken) < len(case_ids) * 0.5

            # Build denial reason summary for the LLM
            denial_summary = []
            for ev in evidence_items:
                desc = ev.get("description", "")
                if "DENIED" in desc.upper() and "Denial reason:" in desc:
                    denial_summary.append(desc)

            # Ask LLM to summarize findings — provider determined by models.yaml
            prompt = f"""Cases analyzed: {len(case_ids)}
Evidence items found: {len(evidence_items)}
Broken provenance chains: {len(broken)} out of {len(case_ids)}
Denial cases with reasons ({len(denial_summary)} total):
{chr(10).join(denial_summary[:10])}

Sample provenance chain:
{json.dumps(all_chains[:2], indent=2)[:1500]}

Respond ONLY with JSON:
{{"investigation_sufficient": true/false, "investigation_iterations": 1,
  "summary": "one sentence summary including denial reasons and applicant profiles observed"}}"""

            response = await llm_chat(prompt, tier="reasoning", system=_SOUL)

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            llm_result = json.loads(raw)

            log_agent_event(
                logger, inv_id, tenant_id, "investigation_agent", "investigation_complete",
                details={"evidence_count": len(evidence_items), "broken_chains": len(broken)},
            )

            hb_end = heartbeat.emit("investigation_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "investigation_agent", response.model, response.provider,
                response.input_tokens, response.output_tokens,
                state_total=state["total_cost_usd"],
            )

            return {
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
                    "broken_chains": len(broken),
                }],
            }

        except Exception as exc:
            log_error(logger, inv_id, tenant_id, "investigation_agent", type(exc).__name__, str(exc))
            hb_fail = heartbeat.emit("investigation_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "status": "investigating",
                "investigation_sufficient": False,
                "messages": [{"agent": "investigation_agent", "event": "error", "error": str(exc)[:200]}],
                "error_log": [f"investigation_agent: {type(exc).__name__}: {str(exc)[:200]}"],
            }
