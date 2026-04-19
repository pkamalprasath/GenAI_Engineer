"""
test_pipeline.py — Integration tests for the Engineering RAG pipeline.

These tests verify that each component works correctly.
They require:
  - Docker running (docker compose up -d)
  - OPENAI_API_KEY set in .env

Run:
    python -m pytest tests/test_pipeline.py -v
    python -m pytest tests/test_pipeline.py -v -k "not slow"  # skip LLM tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── VectorStore tests ──────────────────────────────────────────────────────

class TestVectorStore:
    """Test that the database schema and operations work."""

    def test_init_schema(self):
        """Schema creation should be idempotent (safe to call multiple times)."""
        from src.ingest.vectorstore import VectorStore
        vs = VectorStore()
        vs.init_schema()
        vs.init_schema()   # second call should not fail
        vs.close()

    def test_get_stats(self):
        """Stats should return valid dict."""
        from src.ingest.vectorstore import VectorStore
        vs = VectorStore()
        vs.init_schema()
        stats = vs.get_stats()
        vs.close()

        assert "documents" in stats
        assert "total_chunks" in stats
        assert isinstance(stats["documents"], int)

    def test_embed_query(self):
        """Embedding a string should return a 384-dim vector."""
        from src.ingest.vectorstore import VectorStore
        vs = VectorStore()
        emb = vs.embed_query("test query about engineering")
        vs.close()

        assert isinstance(emb, list)
        assert len(emb) == 384
        assert all(isinstance(x, float) for x in emb)

    def test_upsert_and_search(self):
        """Insert a chunk and find it via similarity search."""
        from src.ingest.vectorstore import VectorStore, _compute_hash
        import tempfile
        import os

        vs = VectorStore()
        vs.init_schema()

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Test document content for pytest")
            tmppath = Path(f.name)

        try:
            chunks = [{
                "content":    "The M12 bolt requires 85 Nm tightening torque for gearbox assembly.",
                "chunk_type": "text",
                "page":       1,
                "section":    "Torque Specifications",
                "image_path": None,
            }]
            doc_id = vs.upsert_document(tmppath, "manual", chunks)
            assert isinstance(doc_id, int)

            # Search for it
            query_emb = vs.embed_query("M12 bolt torque specification")
            results   = vs.search(query_emb, limit=5)
            assert len(results) >= 1
            assert any("M12" in r["content"] for r in results)

        finally:
            tmppath.unlink()
            vs.close()

    def test_incremental_skip(self):
        """Same file ingested twice should be marked as unchanged."""
        from src.ingest.vectorstore import VectorStore
        import tempfile

        vs = VectorStore()
        vs.init_schema()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Stable content that will not change")
            tmppath = Path(f.name)

        try:
            # First ingest
            status1, _ = vs.check_file_status(tmppath)
            vs.upsert_document(tmppath, "other", [{
                "content": "test", "chunk_type": "text", "page": 1,
                "section": "", "image_path": None,
            }])

            # Second check — should be unchanged
            status2, doc_id2 = vs.check_file_status(tmppath)
            assert status2 == "unchanged"
            assert doc_id2 is not None
        finally:
            tmppath.unlink()
            vs.close()


# ── Document Parser tests ──────────────────────────────────────────────────

class TestDocumentParser:
    """Test PDF parsing."""

    def test_parse_text_file(self, tmp_path):
        """Plain text file should parse correctly."""
        from src.ingest.document_parser import parse_text_file
        txtfile = tmp_path / "test.txt"
        txtfile.write_text("This is a test document. It has some text content.")

        doc = parse_text_file(txtfile)
        assert doc.filename == "test.txt"
        assert len(doc.pages) == 1
        assert "test document" in doc.pages[0].text

    def test_parse_unsupported_type(self, tmp_path):
        """Unsupported file type should return None."""
        from src.ingest.document_parser import parse_document
        xlsfile = tmp_path / "data.xlsx"
        xlsfile.write_bytes(b"fake xlsx content")

        result = parse_document(xlsfile)
        assert result is None


# ── HyDE tests ─────────────────────────────────────────────────────────────

class TestHyDE:
    """Test HyDE query expansion."""

    @pytest.mark.slow
    def test_expand_returns_string(self):
        """HyDE should return a non-empty string."""
        from src.retrieval.hyde import expand_with_hyde
        result = expand_with_hyde("M12 bolt torque specification")
        assert isinstance(result, str)
        assert len(result) > 20

    def test_fallback_on_failure(self, monkeypatch):
        """If LLM fails, should return original query."""
        from src.retrieval import hyde

        def fail(*args, **kwargs):
            raise Exception("simulated failure")

        monkeypatch.setattr(hyde, "_call_openai", fail)
        monkeypatch.setattr(hyde, "_call_anthropic", fail)

        result = hyde.expand_with_hyde("test query")
        assert result == "test query"


# ── RRF tests ─────────────────────────────────────────────────────────────

class TestRRF:
    """Test Reciprocal Rank Fusion."""

    def test_merges_and_deduplicates(self):
        """Same chunk in multiple lists should get combined score."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        chunk_a = {"id": 1, "content": "A", "chunk_type": "text"}
        chunk_b = {"id": 2, "content": "B", "chunk_type": "table"}

        list1 = [chunk_a, chunk_b]
        list2 = [chunk_a]   # chunk_a appears in both lists

        merged = _reciprocal_rank_fusion([list1, list2], k=60)

        assert merged[0]["id"] == 1   # chunk_a should rank first (2 lists)
        assert len(merged) == 2       # deduplicated: only 2 unique chunks

    def test_empty_lists(self):
        from src.retrieval.retriever import _reciprocal_rank_fusion
        merged = _reciprocal_rank_fusion([[], []])
        assert merged == []

    def test_rrf_scores_assigned(self):
        from src.retrieval.retriever import _reciprocal_rank_fusion
        chunks = [{"id": i, "content": f"chunk {i}", "chunk_type": "text"} for i in range(3)]
        merged = _reciprocal_rank_fusion([chunks], k=60)
        assert all("rrf_score" in c for c in merged)


# ── CRAG tests ─────────────────────────────────────────────────────────────

class TestCRAG:
    """Test CRAG filtering logic."""

    def test_filter_keeps_relevant(self):
        """Filter should keep relevant chunks and assign high confidence."""
        from src.retrieval.crag import filter_chunks

        scored = [
            {"id": 1, "content": "relevant", "relevance": "relevant",   "crag_score": 1.0},
            {"id": 2, "content": "bad",       "relevance": "irrelevant", "crag_score": 0.0},
        ]
        filtered, confidence = filter_chunks(scored)

        assert confidence == "high"
        assert all(c["relevance"] != "irrelevant" for c in filtered)

    def test_filter_medium_when_only_ambiguous(self):
        """When only ambiguous chunks, confidence should be medium."""
        from src.retrieval.crag import filter_chunks

        scored = [
            {"id": 1, "content": "maybe", "relevance": "ambiguous", "crag_score": 0.5},
        ]
        filtered, confidence = filter_chunks(scored)

        assert confidence == "medium"

    def test_filter_low_when_all_irrelevant(self):
        """When all chunks irrelevant, confidence should be low."""
        from src.retrieval.crag import filter_chunks

        scored = [
            {"id": 1, "content": "bad", "relevance": "irrelevant", "crag_score": 0.0},
        ]
        filtered, confidence = filter_chunks(scored)

        assert confidence == "low"


# ── Prompt tests ───────────────────────────────────────────────────────────

class TestPrompts:
    """Test prompt building."""

    def test_rag_prompt_includes_query(self):
        from src.generation.prompts import build_rag_prompt

        chunks = [{"content": "torque is 85 Nm", "chunk_type": "text",
                   "page": 5, "filename": "manual.pdf"}]
        prompt = build_rag_prompt("What is the torque?", chunks, "high")

        assert "What is the torque?" in prompt
        assert "85 Nm" in prompt
        assert "manual.pdf" in prompt

    def test_self_rag_prompt_includes_answer(self):
        from src.generation.prompts import build_self_rag_critique_prompt

        prompt = build_self_rag_critique_prompt(
            query="test question",
            context_str="context text here",
            answer="my generated answer",
        )
        assert "my generated answer" in prompt
        assert "SUPPORTED" in prompt
