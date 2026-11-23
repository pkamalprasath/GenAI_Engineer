# Changelog

Dates are taken from the commit history.

## 2026-11 — Portfolio clean-up
- Reorganised project folders with clearer names: `04.slack-workflow-agent`, `07.langgraph-compliance-agents`, `08.slm-pretraining`.
- Corrected README claims so every number matches the result files and the code. Removed unmeasured figures, "production" labels and self-ratings.
- Compliance agents: scenario harness now fails a case on any verdict or risk mismatch; stale reports removed.
- RAG benchmark findings rewritten to match the result CSVs.
- Finance SLM: removed an illustrative (non-measured) loss curve.
- Credited course material in the learning folders; stripped outputs from course notebooks.
- Added MIT licence text, root `.gitignore` and `.gitattributes`.

## 2026-09-27
- CI runs every test suite (Slack agent, engineering RAG with pgvector, compliance agents v1 and v2) plus a lint gate.
- Added small-language-model training notebooks with outputs.

## 2026-04 – 2026-05
- Added the multi-agent compliance platform (v1 and v2), the multimodal engineering RAG project, RAG benchmark experiments and research-paper notes.
- Added the Slack workflow agent.

## 2025-11 – 2026-02
- NLP, LangChain and guardrails learning folders; Claude Code rules and commands.
