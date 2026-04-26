# Agentic AI — Multi-Agent Systems for Compliance & Investigation

## Projects

### 1. SENTINEL v1 (sentinel_v1/)
**Status:** Legacy (stable, reference implementation)

Original SENTINEL architecture with all core features:
- Multi-agent compliance investigation pipeline
- W3C PROV-O provenance graph
- Streaming Streamlit dashboard
- Support for Finance, Pharma, EU AI Act domains

**Setup:** See `sentinel_v1/README.md`

### 2. SENTINEL v2 (sentinel_v2/)
**Status:** Current (production-ready, enhanced)

Production-grade version with:
- Microservices architecture (API + Worker + Scheduler)
- Async/await processing (non-blocking)
- Background job queue (arq/Redis)
- HNSW vector indexes (10x faster search)
- Automated audit trail (SR 11-7, GDPR compliant)
- Real-time streaming API
- Kubernetes-ready health probes

**Key Improvements:**
- 99% cheaper discovery (BM25→BERT→LLM hybrid)
- 10x faster semantic search (HNSW)
- Asynchronous API (non-blocking)
- Automated compliance audit trail
- Enhanced provenance (source documentation + content hashes)

**Setup:** See `sentinel_v2/README.md`

## Comparison

| Feature | v1 | v2 |
|---------|----|----|
| Agents | 6 | 7 (+ audit_agent) |
| Architecture | Monolithic | Microservices |
| Processing | Sync (blocking) | Async (non-blocking) |
| Vector Search | pgvector baseline | HNSW (10x faster) |
| Audit Trail | Manual | Automated |
| Deployment | Single service | docker-compose (7 services) |

## Quick Start

### SENTINEL v2 (Recommended)
```bash
cd sentinel_v2
cp .env.example .env
docker-compose up -d
# Visit: http://localhost:8501
```

### SENTINEL v1
```bash
cd sentinel_v1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn sentinel.api.main:app --port 8003
```

## Documentation

- **SENTINEL v2 README:** `sentinel_v2/README.md`
- **SENTINEL v2 Architecture:** `sentinel_v2/ARCHITECTURE.md`
- **SENTINEL v2 Setup:** `sentinel_v2/SETUP.md`
- **Contributing:** `sentinel_v2/CONTRIBUTING.md`

## Next Steps

1. **Run SENTINEL v2** (recommended for production)
2. **Review architecture** decisions in ARCHITECTURE.md
3. **Set up locally** following SETUP.md
4. **Contribute** improvements via CONTRIBUTING.md

