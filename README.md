# Kamal Prasath Perumalsamy — AI engineering portfolio

**Mainframe modernisation & AI engineer.** 13+ years delivering COBOL, DB2 and Oracle systems for financial services, healthcare, energy and retail clients at Cognizant; now building and *measuring* RAG systems and LLM agents in Python.
Bristol, UK · open to London hybrid · [LinkedIn](https://www.linkedin.com/in/kamalprasath) · AWS Certified Solutions Architect – Associate · AWS Certified AI Practitioner

[![Tests](https://github.com/pkamalprasath/GenAI_Engineer/actions/workflows/tests.yml/badge.svg)](https://github.com/pkamalprasath/GenAI_Engineer/actions) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Start here: three projects, two minutes

### 1. Ask an engineering manual a question that needs a table, a diagram *and* a paragraph — get one cited answer
**[Multimodal engineering RAG →](06.rag/projects/2.engineering-rag)**

Real questions about equipment ("What torque for M12 bolts near the motor, and what PPE applies?") have answers spread across text, spec tables and diagrams. This system indexes all three and answers with citations.

- **Measured, not demoed:** a fixed 50-question test set (text, table, image, multi-hop, unanswerable) re-run after every change. Best run **3.87 / 5** (Claude Haiku as judge); multi-hop **2.63 → 3.27** under the same judge.
- **Honest about regressions:** run 5 scored lower, the cause was traced (an image-caption model refused 257 of 359 images) and the change was reverted.
- Hybrid retrieval (pgvector + BM25), query decomposition, corrective RAG, Langfuse tracing, ~$0.022 per query (estimated from token counts). 147 tests in CI.

`Python` `FastAPI` `PostgreSQL + pgvector` `Claude` `Langfuse`

### 2. Three AI agents review a lending decision in parallel — and hand it to a human when they're not sure
**[LangGraph compliance agents →](07.langgraph-compliance-agents/2.sentinel_v2)**

A multi-agent workflow that checks (synthetic) lending decisions against US fair-lending rules (ECOA, HMDA) and writes an evidence-backed report.

- **11-node LangGraph workflow**; investigation, legal and bias agents run in parallel.
- **Cheap first, LLM last:** a BM25 → DistilBERT → local Llama 3.2 triage sends only borderline cases to a large model.
- **Human in the loop:** reports below 0.85 confidence go to a reviewer; every finding carries SHA-256 provenance.
- FastAPI + Redis job queue + PostgreSQL, Docker Compose, 200+ tests in CI.

`LangGraph` `Multi-agent` `Human-in-the-loop` `FastAPI` `Ollama`

### 3. A Slack agent with 16 tools across Slack, GitHub and Notion — built without an agent framework
**[Slack workflow agent →](04.slack-workflow-agent)**

A team assistant that answers questions from channel history, opens GitHub issues, turns threads into Notion pages and sets reminders, using Claude's native tool use in a hand-written agent loop.

- **No LangChain, no LangGraph:** the tool-calling loop, memory and tool registry are written directly against the Claude API.
- FastMCP server for the Slack tools, ChromaDB retrieval over channel history, scheduled reminders.
- **267 unit tests in CI.** Run in a test workspace.

`Claude tool use` `MCP` `Slack Bolt` `ChromaDB`

---

## Built from scratch

| What | Proof |
|---|---|
| **LoRA written from scratch** in PyTorch — no PEFT library | [`08.slm-pretraining/01_finance_gpt_lora`](08.slm-pretraining) |
| **Agent loop without a framework** — native Claude tool use | [`04.slack-workflow-agent`](04.slack-workflow-agent) |
| **GPT-2 124M pretraining on 8 GPUs** (PyTorch DDP), reimplemented following Andrej Karpathy's build-nanoGPT — val loss 3.67, HellaSwag 26.0% | [`08.slm-pretraining/02_gpt2_124m_nanogpt_reimplementation`](08.slm-pretraining) |

---

## Also here

| Folder | What it is |
|---|---|
| [`06.rag/experiments`](06.rag/experiments) | **35 RAG configurations compared** (chunking, embeddings, vector stores, top-k, re-ranking, prompts). Findings are reported as the data shows them — including that re-ranking and hybrid retrieval did not help on this dataset. |
| [`08.slm-pretraining`](08.slm-pretraining) | Small language-model training notebooks with outputs kept as evidence. |
| [`05.claude_skill_rules_agents`](05.claude_skill_rules_agents) | Claude Code rules and commands I use for these projects. |
| [`01.nlp`](01.nlp) · [`02.langchain`](02.langchain) · [`03.guardrails`](03.guardrails) | Learning log: course labs (credited in each folder) on NLP, LangChain, guardrails and red-teaming. |

## At work

- Built two prompt-based AI tools (Python, FastAPI) adopted by 40 colleagues, and trained all 40 on AI tools.
- Use Claude, Amazon Q and GitHub Copilot for business-logic extraction, documentation, code review and test generation on client code, with every output checked by a developer.
- Assessed a mainframe estate for migration to AWS; migrated Micro Focus COBOL to NetCOBOL on Linux; built a PHI/PII discovery tool and data masking across four database platforms.

## Run a project

Each project is self-contained with its own README, `requirements.txt` and `.env.example`. Tests for the three main projects run in [GitHub Actions](.github/workflows/tests.yml).

MIT licence · [Changelog](CHANGELOG.md)
