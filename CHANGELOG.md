# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [3.0] - 2026-04-26

### Added
- **7.agentic_ai**: SENTINEL v1 & v2 (multi-agent compliance system)
  - 7-agent orchestration with LangGraph state machine
  - Background job queue integration with arq + Redis
  - Multi-tenant scheduling and investigation workflows
  - W3C PROV-O provenance graphs with SHA-256 tamper detection
  - Kubernetes-ready deployment (health probes, graceful shutdown)
  - Production observability with LangFuse cost tracking

- **RAG Deep-Dive**: Systematic benchmarking and multimodal retrieval
  - 10 controlled experiments on chunking, embeddings, retrieval strategies
  - Multimodal RAG system (text + tables + images)
  - Production deployment with FastAPI + Streamlit
  - OWASP hardening, rate limiting, input sanitization

### Improved
- Guardrails module expanded with Garak fuzzing
- LangChain patterns documentation (15+ examples)
- Repository structure and professional standards

## [2.0] - 2026-01-15

### Added
- **04.open_claw_slack_bot**: Production Slack agent
  - 81 Python files with full test coverage
  - Multi-tool integration (10+ tools)
  - Conversation memory with MCP server integration
  - APScheduler for recurring tasks and reminders
  - Full production deployment experience

- **03.Guardrails**: AI safety and red-teaming module
  - Prompt injection detection
  - Hallucination scoring with LLM-as-judge
  - Garak fuzzing framework
  - PII detection with Presidio integration
  - OWASP top 10 vulnerability scanning

### Features
- Full-stack Slack integration with multiple tool types
- Scheduler-based task automation
- Memory persistence across conversations

## [1.0] - 2025-12-01

### Foundation
- **01.NLP**: Classical to deep learning progression
  - Word2Vec, RNNs, ANNs from scratch
  - 17 Jupyter notebooks for learning
  - Zero framework dependency implementations

- **02.LangChain**: 15+ LLM application patterns
  - LCEL (LangChain Expression Language) chains
  - RAG pipeline patterns
  - Agent and tool implementations
  - LangGraph state machine examples
  - 22 comprehensive notebooks

- **06.RAG**: End-to-end RAG systems
  - Nutrition RAG Chat (full-stack, Next.js + Python)
  - Engineering Multimodal RAG (benchmark score: 3.87/5.0)
  - 10 systematic benchmarking experiments
  - Production deployment patterns
  - Observability with Langfuse

### Capabilities
- 63,332 lines of production Python code
- 378 Python files across all projects
- 57 Jupyter notebooks for learning/reference
- Systematic benchmarking and evaluation framework
