"""
api.py — FastAPI REST API for the Engineering Knowledge Assistant.

ENDPOINTS:
    POST /query   → ask a question, get answer + sources + confidence
    POST /ingest  → trigger ingestion of a file path (server-side)
    GET  /health  → check DB connection + document counts
    GET  /stats   → detailed database statistics

RUN:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

EXAMPLE QUERY:
    curl -X POST http://localhost:8000/query \
         -H "Content-Type: application/json" \
         -d '{"question": "What is the torque spec for M12 bolts?"}'
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from configs.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)
from pydantic import BaseModel, Field

from configs.settings import HAS_OPENAI, HAS_ANTHROPIC, USE_CRAG, DATA_DIR
from src.ingest.vectorstore import VectorStore
from src.retrieval.retriever import Retriever
from src.retrieval.adaptive_router import classify_query, answer_simple_query
from src.retrieval.crag import score_chunks, filter_chunks
from src.generation.generator import generate
from src.guardrails.input_sanitizer import sanitize
from src.observability.tracing import start_trace, end_trace, flush as lf_flush


# ── Rate limiter ───────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── App setup ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Engineering Knowledge Assistant",
    description="Multimodal RAG system for engineering documents",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8511", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Shared instances (created once on startup, reused across requests)
_vs: VectorStore | None = None
_retriever: Retriever | None = None


@app.on_event("startup")
def startup():
    global _vs, _retriever
    try:
        _vs = VectorStore()
        _vs.init_schema()
        _retriever = Retriever(_vs)
        logger.info("API startup complete")
    except Exception as e:
        logger.critical("API startup failed: %s", e, exc_info=True)
        raise


@app.on_event("shutdown")
def shutdown():
    if _vs:
        _vs.close()
    lf_flush()


# ── Request / Response models ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    doc_type: str | None = None   # optional filter: 'sds', 'manual', etc.
    use_hyde: bool        = True

class SourceCitation(BaseModel):
    filename:   str
    page:       int | None
    chunk_type: str
    section:    str

class QueryResponse(BaseModel):
    answer:          str
    confidence:      str           # 'high' | 'medium' | 'low'
    query_type:      str           # 'simple' | 'complex'
    sources:         list[SourceCitation]
    model_used:      str
    self_rag_status: str
    retried:         bool

class IngestRequest(BaseModel):
    filepath: str   # absolute or relative path on the server
    doc_type: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
def query(req: QueryRequest, request: Request):
    """
    Ask a question and get an answer from the engineering documents.

    The pipeline:
    1. Sanitize input (prompt injection guard)
    2. Classify query (Adaptive-RAG: simple vs complex)
    3. If complex: HyDE + multi-type search + RRF + CRAG + generation + Self-RAG
    4. Return answer with citations and confidence level
    """
    if not HAS_OPENAI and not HAS_ANTHROPIC:
        raise HTTPException(status_code=503, detail="No LLM API key configured")

    question = sanitize(req.question)
    logger.info("Query received: '%s...'", question[:80])
    tracer = start_trace("rag_query", input=question)
    try:
        # Step 1: Adaptive routing
        query_type = classify_query(question)

        if query_type == "simple":
            answer = answer_simple_query(question)
            end_trace(tracer, output=answer, metadata={"query_type": "simple"})
            return QueryResponse(
                answer=answer,
                confidence="high",
                query_type="simple",
                sources=[],
                model_used="none",
                self_rag_status="supported",
                retried=False,
            )

        # Step 2: Full RAG pipeline
        with tracer.span("retrieval", input=question) as s:
            raw_chunks = _retriever.query(question, doc_type=req.doc_type, use_hyde=req.use_hyde)
            s.update(output={"chunks": len(raw_chunks)})

        if USE_CRAG:
            with tracer.span("crag", input={"query": question, "chunks": len(raw_chunks)}) as s:
                scored      = score_chunks(question, raw_chunks)
                final, conf = filter_chunks(scored)
                s.update(output={"confidence": conf, "kept": len(final)})
        else:
            # Mark all chunks as relevant so downstream confidence is consistent
            final = [{**c, "relevance": "relevant", "crag_score": 1.0} for c in raw_chunks]
            conf  = "high"

        response = generate(question, final, conf, _retriever, tracer=tracer)

        end_trace(tracer, output=response.answer, metadata={
            "confidence": response.confidence,
            "self_rag": response.self_rag_status,
            "retried": response.retried,
        })
        logger.info("Query answered: confidence=%s self_rag=%s retried=%s",
                    response.confidence, response.self_rag_status, response.retried)

        return QueryResponse(
            answer=response.answer,
            confidence=response.confidence,
            query_type="complex",
            sources=[
                SourceCitation(
                    filename=s["filename"],
                    page=s.get("page"),
                    chunk_type=s["chunk_type"],
                    section=s.get("section", ""),
                )
                for s in response.sources
            ],
            model_used=response.model_used,
            self_rag_status=response.self_rag_status,
            retried=response.retried,
        )
    except HTTPException:
        raise
    except Exception as e:
        end_trace(tracer, metadata={"error": str(e)})
        logger.error("Query pipeline failed for '%s...': %s", question[:60], e, exc_info=True)
        raise HTTPException(status_code=500, detail="Query pipeline error. Please try again.")


@app.post("/ingest")
@limiter.limit("5/minute")
def ingest(req: IngestRequest, request: Request):  # noqa: C901
    """
    Trigger ingestion of a document file.

    The file must exist on the server filesystem and must be inside DATA_DIR
    (path traversal protection).
    Incremental: unchanged files are automatically skipped.
    """
    if _vs is None:
        raise HTTPException(status_code=503, detail="Database not available")

    from src.ingest.document_parser import parse_document
    from src.ingest.chunker import chunk_document
    from src.ingest.image_captioner import caption_images

    # Path traversal protection: resolve to absolute, check it's under DATA_DIR
    try:
        filepath = Path(req.filepath).resolve()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not filepath.is_relative_to(DATA_DIR.resolve()):
            logger.warning("Path traversal attempt blocked: %s", req.filepath)
            raise HTTPException(status_code=403, detail="File path must be inside the data directory")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath.name}")

    status, _ = _vs.check_file_status(filepath)
    if status == "unchanged":
        return {"status": "skipped", "reason": "file unchanged"}

    parsed_doc = parse_document(filepath)
    if parsed_doc is None:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {filepath.suffix}")

    image_save_dir = filepath.parent / "extracted_images" / filepath.stem
    image_captions = caption_images(parsed_doc.all_images, filepath.name, image_save_dir)
    chunks         = chunk_document(parsed_doc, image_captions, image_save_dir)

    from ingest_docs import detect_doc_type
    doc_type = req.doc_type or detect_doc_type(filepath.name)
    doc_id   = _vs.upsert_document(filepath, doc_type, chunks)

    return {
        "status":   "ingested",
        "doc_id":   doc_id,
        "doc_type": doc_type,
        "chunks":   len(chunks),
    }


@app.get("/health")
def health():
    """Check system health: DB connection + document counts."""
    try:
        stats = _vs.get_stats()
        return {
            "status":    "healthy",
            "documents": stats["documents"],
            "chunks":    stats["total_chunks"],
            "llm":       "openai" if HAS_OPENAI else ("anthropic" if HAS_ANTHROPIC else "none"),
        }
    except Exception as e:
        logger.error("Health check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")


@app.get("/stats")
def stats():
    """Detailed database statistics."""
    if _vs is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return _vs.get_stats()
