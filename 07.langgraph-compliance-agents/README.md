# LangGraph compliance agents (SENTINEL)

A LangGraph multi-agent workflow that reviews synthetic lending decisions against US fair-lending rules (ECOA, HMDA and related): BM25 → DistilBERT → local Llama 3.2 triage, three agents in parallel, human review below 0.85 confidence, and SHA-256 provenance hashes. Synthetic data only; not legal advice.

| Folder | Status | What it is |
|---|---|---|
| [`2.sentinel_v2`](2.sentinel_v2) | **Current version** | 11-node graph, 6 agents (3 in parallel), FastAPI + arq worker + scheduler + Streamlit dashboard (5 Docker Compose services), 228 test functions in CI |
| [`1.sentinel_v1`](1.sentinel_v1) | Earlier version, kept for history | 9-node graph, 5 agents, single API process; 218 test functions in CI |

Start with the [v2 README](2.sentinel_v2/README.md): it has the architecture diagram, design trade-offs, quick start, tests and limitations.

The end-to-end scenario pass rate for v2 is pending a re-run after a scoring fix; see the v2 README.
