"""
test_modules.py — Module-by-module validation of the Engineering RAG pipeline.

Runs WITHOUT Docker and WITHOUT live API keys.
All LLM calls and DB connections are mocked so every test is self-contained.

Structure (one class per source module):
  TestDocumentParser   — document_parser.py
  TestChunker          — chunker.py
  TestImageCaptioner   — image_captioner.py
  TestVectorStore      — vectorstore.py  (DB mocked)
  TestHyDE             — hyde.py         (LLM mocked)
  TestRetrieverRRF     — retriever.py    (pure RRF logic)
  TestAdaptiveRouter   — adaptive_router.py (LLM mocked)
  TestCRAG             — crag.py         (LLM mocked + pure filter logic)
  TestPrompts          — prompts.py      (pure Python)
  TestGenerator        — generator.py    (LLM mocked)
  TestJudge            — judge.py        (LLM mocked)
  TestMetrics          — metrics.py      (full pipeline mocked)

Run:
    cd projects/engineering-rag
    python -m pytest tests/test_modules.py -v
    python -m pytest tests/test_modules.py -v --tb=short  # compact tracebacks
"""

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Make project root importable ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 1: document_parser.py
# Tests: text extraction, table→markdown conversion, image filtering
# No external deps needed for these tests (pure logic)
# ═══════════════════════════════════════════════════════════════════════════

class TestDocumentParser:
    """
    Tests for src/ingest/document_parser.py

    What we test:
      - _table_to_markdown converts list-of-lists to valid Markdown
      - Unsupported file types return None from parse_document()
      - Plain text files parse correctly
      - ParsedDocument properties (all_text_blocks, all_tables, all_images)
    """

    def test_table_to_markdown_basic(self):
        """Table with header + 2 data rows should produce valid Markdown."""
        from src.ingest.document_parser import _table_to_markdown

        data = [
            ["Bolt", "Torque (Nm)", "Grade"],
            ["M12",  "85",          "8.8"],
            ["M8",   "25",          "8.8"],
        ]
        result = _table_to_markdown(data)

        assert "| Bolt" in result
        assert "| M12" in result
        assert "| M8" in result
        assert "| -" in result         # separator row must exist (padded: | ---- |)
        assert result.count("\n") >= 3  # header + separator + 2 data rows

    def test_table_to_markdown_handles_none_cells(self):
        """None cells in table data should become empty strings, not crash."""
        from src.ingest.document_parser import _table_to_markdown

        data = [["Col1", None, "Col3"], [None, "val", None]]
        result = _table_to_markdown(data)
        assert "Col1" in result
        assert "val" in result

    def test_table_to_markdown_empty_returns_empty(self):
        """Empty table data should return empty string."""
        from src.ingest.document_parser import _table_to_markdown
        assert _table_to_markdown([]) == ""

    def test_parse_document_unsupported_extension(self, tmp_path):
        """Unsupported file type (.xlsx) should return None."""
        from src.ingest.document_parser import parse_document
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"fake xlsx")
        assert parse_document(f) is None

    def test_parse_text_file(self, tmp_path):
        """Plain .txt file should parse into one page with all text."""
        from src.ingest.document_parser import parse_text_file
        f = tmp_path / "doc.txt"
        f.write_text("Line one.\nLine two about torque specs.\nLine three.")
        doc = parse_text_file(f)

        assert doc.filename == "doc.txt"
        assert len(doc.pages) == 1
        assert "torque specs" in doc.pages[0].text
        assert doc.pages[0].tables == []
        assert doc.pages[0].images == []

    def test_parsed_document_all_text_blocks(self, tmp_path):
        """all_text_blocks should only include pages with non-empty text."""
        from src.ingest.document_parser import parse_text_file
        f = tmp_path / "multi.txt"
        f.write_text("Some meaningful text here.")
        doc = parse_text_file(f)
        blocks = doc.all_text_blocks
        assert len(blocks) == 1
        assert blocks[0]["page"] == 1
        assert "meaningful" in blocks[0]["text"]

    def test_parsed_document_all_tables_empty_for_txt(self, tmp_path):
        """Text file should have no tables."""
        from src.ingest.document_parser import parse_text_file
        f = tmp_path / "t.txt"
        f.write_text("just text")
        doc = parse_text_file(f)
        assert doc.all_tables == []

    def test_image_filter_small_images(self):
        """Images smaller than 50x50 should be filtered out in _extract_images."""
        # We test this by creating a mock fitz page that returns a tiny image
        from src.ingest.document_parser import _extract_images

        tiny_img = io.BytesIO()
        from PIL import Image as PILImage
        PILImage.new("RGB", (20, 20), color="red").save(tiny_img, format="PNG")
        tiny_bytes = tiny_img.getvalue()

        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "", "")]
        mock_page.parent.extract_image.return_value = {
            "image": tiny_bytes,
            "ext":   "png",
        }

        results = _extract_images(mock_page, page_num=1)
        assert results == []  # tiny image filtered out

    def test_image_filter_keeps_large_images(self):
        """Images 100x100 or larger should be kept."""
        from src.ingest.document_parser import _extract_images

        large_img = io.BytesIO()
        from PIL import Image as PILImage
        PILImage.new("RGB", (200, 200), color="blue").save(large_img, format="PNG")
        large_bytes = large_img.getvalue()

        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "", "")]
        mock_page.parent.extract_image.return_value = {
            "image": large_bytes,
            "ext":   "png",
        }

        results = _extract_images(mock_page, page_num=1)
        assert len(results) == 1
        assert results[0]["width"] == 200
        assert results[0]["height"] == 200
        assert results[0]["page"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 2: chunker.py
# Tests: table chunking, image caption chunking, section heading extraction
# SemanticChunker (requires OpenAI) is mocked
# ═══════════════════════════════════════════════════════════════════════════

class TestChunker:
    """
    Tests for src/ingest/chunker.py

    What we test:
      - Table chunks: one chunk per table, content = caption + markdown
      - Image caption chunks: content = caption text, image_path set correctly
      - Section heading extraction from text
      - chunk_type field is correctly set on each chunk
    """

    def test_table_chunks_one_per_table(self, tmp_path):
        """Each table in the document should become exactly one chunk."""
        from src.ingest.chunker import _chunk_tables
        from src.ingest.document_parser import ParsedDocument, ParsedPage

        doc = ParsedDocument(filename="manual.pdf")
        doc.pages.append(ParsedPage(
            page_num=1,
            text="Some text",
            tables=[
                {"markdown": "| A | B |\n|---|---|\n| 1 | 2 |", "caption": "Table 1: specs"},
                {"markdown": "| X | Y |\n|---|---|\n| 3 | 4 |", "caption": "Table 2: ratings"},
            ],
            images=[],
        ))

        chunks = _chunk_tables(doc)

        assert len(chunks) == 2
        assert chunks[0]["chunk_type"] == "table"
        assert "Table 1: specs" in chunks[0]["content"]
        assert "| A | B |" in chunks[0]["content"]
        assert chunks[0]["page"] == 1

    def test_table_chunk_content_combines_caption_and_markdown(self, tmp_path):
        """Table chunk content should be 'caption\\n\\nmarkdown'."""
        from src.ingest.chunker import _chunk_tables
        from src.ingest.document_parser import ParsedDocument, ParsedPage

        doc = ParsedDocument(filename="test.pdf")
        doc.pages.append(ParsedPage(
            page_num=3,
            text="",
            tables=[{"markdown": "| Bolt | 85 Nm |", "caption": "Bolt torque table"}],
            images=[],
        ))

        chunks = _chunk_tables(doc)
        assert "Bolt torque table" in chunks[0]["content"]
        assert "| Bolt | 85 Nm |" in chunks[0]["content"]

    def test_image_chunks_from_captions(self, tmp_path):
        """Image chunks should have chunk_type='image' and image_path set."""
        from src.ingest.chunker import _chunk_images

        save_dir = tmp_path / "images"
        save_dir.mkdir()

        captions = [
            {"page": 5, "index": 0, "caption": "Three-phase wiring diagram showing panel A3."},
            {"page": 7, "index": 1, "caption": "Safety warning: HIGH VOLTAGE label."},
        ]

        chunks = _chunk_images(captions, save_dir)

        assert len(chunks) == 2
        assert chunks[0]["chunk_type"] == "image"
        assert chunks[0]["page"] == 5
        assert "wiring diagram" in chunks[0]["content"]
        assert "page5_img0.png" in chunks[0]["image_path"]
        assert chunks[1]["page"] == 7

    def test_image_chunks_skip_empty_captions(self, tmp_path):
        """Captions that are empty or whitespace-only should be skipped."""
        from src.ingest.chunker import _chunk_images

        captions = [
            {"page": 1, "index": 0, "caption": ""},
            {"page": 2, "index": 1, "caption": "   "},
            {"page": 3, "index": 2, "caption": "Valid caption text here."},
        ]

        chunks = _chunk_images(captions, tmp_path)
        assert len(chunks) == 1
        assert "Valid caption" in chunks[0]["content"]

    def test_extract_section_heading_numbered(self):
        """Numbered sections like '3.2 Maintenance' should be detected."""
        from src.ingest.chunker import _extract_section_heading

        text = "3.2 Maintenance Procedures\nReplace the oil filter every 500 hours..."
        heading = _extract_section_heading(text)
        assert heading == "3.2 Maintenance Procedures"

    def test_extract_section_heading_allcaps(self):
        """ALL CAPS short line should be detected as heading."""
        from src.ingest.chunker import _extract_section_heading

        text = "SAFETY WARNINGS\nAlways wear protective equipment..."
        heading = _extract_section_heading(text)
        assert heading == "SAFETY WARNINGS"

    def test_extract_section_heading_fallback(self):
        """No heading pattern → return empty string."""
        from src.ingest.chunker import _extract_section_heading

        text = "This is a long body paragraph with no heading. It goes on and on."
        heading = _extract_section_heading(text)
        assert heading == ""

    def test_chunk_document_aggregates_all_types(self, tmp_path):
        """chunk_document() should combine text + table + image chunks."""
        from src.ingest.document_parser import ParsedDocument, ParsedPage
        from src.ingest.chunker import chunk_document

        doc = ParsedDocument(filename="test.pdf")
        doc.pages.append(ParsedPage(
            page_num=1,
            text="The gearbox requires regular oil changes for optimal performance.",
            tables=[{"markdown": "| Part | Interval |", "caption": "Service intervals"}],
            images=[],
        ))

        # Mock the SemanticChunker so we don't need OpenAI
        mock_lc_doc = MagicMock()
        mock_lc_doc.page_content = "The gearbox requires regular oil changes for optimal performance."

        with patch("src.ingest.chunker.SemanticChunker") as MockSC, \
             patch("src.ingest.chunker.OpenAIEmbeddings"):
            MockSC.return_value.create_documents.return_value = [mock_lc_doc]

            image_captions = [{"page": 1, "index": 0, "caption": "Wiring diagram for motor M1."}]
            chunks = chunk_document(doc, image_captions, tmp_path / "images")

        types = {c["chunk_type"] for c in chunks}
        assert "text"  in types
        assert "table" in types
        assert "image" in types


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 3: image_captioner.py
# Tests: image resizing, save logic, decorative image filtering, API mock
# ═══════════════════════════════════════════════════════════════════════════

class TestImageCaptioner:
    """
    Tests for src/ingest/image_captioner.py

    What we test:
      - _resize_image reduces large images
      - _resize_image returns original if already small enough
      - _save_image writes PNG to disk
      - Decorative images (GPT-4o returns "DECORATIVE_IMAGE") are excluded
      - Failed API calls are skipped (don't crash ingestion)
    """

    def _make_png_bytes(self, w: int, h: int) -> bytes:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (w, h), color="green").save(buf, format="PNG")
        return buf.getvalue()

    def test_resize_reduces_large_image(self):
        """Image larger than max_pixels should be resized."""
        from src.ingest.image_captioner import _resize_image
        from PIL import Image

        large = self._make_png_bytes(2000, 2000)   # 4M pixels
        max_px = 512 * 512                          # 262K pixels

        resized = _resize_image(large, max_pixels=max_px)
        img = Image.open(io.BytesIO(resized))
        assert img.size[0] * img.size[1] <= max_px * 1.1  # within 10% tolerance

    def test_resize_keeps_small_image_unchanged(self):
        """Image smaller than max_pixels should be returned unchanged."""
        from src.ingest.image_captioner import _resize_image

        small = self._make_png_bytes(100, 100)
        result = _resize_image(small, max_pixels=1024 * 1024)
        assert result == small

    def test_save_image_writes_file(self, tmp_path):
        """_save_image should create a PNG file on disk."""
        from src.ingest.image_captioner import _save_image

        img_bytes = self._make_png_bytes(200, 200)
        out_path  = tmp_path / "test_image.png"

        _save_image(img_bytes, out_path)

        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_decorative_image_excluded(self, tmp_path):
        """If GPT-4o returns DECORATIVE_IMAGE, the image should be excluded."""
        from src.ingest.image_captioner import caption_images

        img_bytes = self._make_png_bytes(200, 200)
        images = [{"page": 1, "bytes": img_bytes, "index": 0, "width": 200, "height": 200}]

        with patch("src.ingest.image_captioner.OpenAI") as MockOpenAI:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "DECORATIVE_IMAGE"
            MockOpenAI.return_value.chat.completions.create.return_value = mock_resp

            results = caption_images(images, "manual.pdf", tmp_path)

        assert results == []

    def test_valid_caption_included(self, tmp_path):
        """A valid GPT-4o caption should produce one result."""
        from src.ingest.image_captioner import caption_images

        img_bytes = self._make_png_bytes(300, 300)
        images = [{"page": 2, "bytes": img_bytes, "index": 0, "width": 300, "height": 300}]

        with patch("src.ingest.image_captioner.OpenAI") as MockOpenAI:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "This is a wiring diagram showing panel B2."
            MockOpenAI.return_value.chat.completions.create.return_value = mock_resp

            results = caption_images(images, "manual.pdf", tmp_path)

        assert len(results) == 1
        assert results[0]["page"] == 2
        assert "wiring diagram" in results[0]["caption"]

    def test_api_failure_skipped_gracefully(self, tmp_path):
        """If the vision API raises an exception, the image should be skipped (not crash)."""
        from src.ingest.image_captioner import caption_images

        img_bytes = self._make_png_bytes(200, 200)
        images = [{"page": 1, "bytes": img_bytes, "index": 0, "width": 200, "height": 200}]

        with patch("src.ingest.image_captioner.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.side_effect = Exception("API error")
            results = caption_images(images, "manual.pdf", tmp_path)

        assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 4: vectorstore.py
# Tests: SHA-256 hash, SQL vector format, incremental status logic
# psycopg2 is mocked — no real DB needed
# ═══════════════════════════════════════════════════════════════════════════

class TestVectorStore:
    """
    Tests for src/ingest/vectorstore.py

    What we test:
      - _compute_hash: same content → same hash; different content → different hash
      - _list_to_pgvector: correct string format '[x,y,z]'
      - check_file_status: returns 'new', 'unchanged', or 'changed' correctly
      - embed_query: returns 384-dim float list (real model, no mock)
    """

    def test_compute_hash_deterministic(self, tmp_path):
        """Same file content should always produce the same hash."""
        from src.ingest.vectorstore import _compute_hash

        f = tmp_path / "file.txt"
        f.write_bytes(b"stable content here")

        hash1 = _compute_hash(f)
        hash2 = _compute_hash(f)
        assert hash1 == hash2
        assert len(hash1) == 64   # SHA-256 = 64 hex chars

    def test_compute_hash_different_content(self, tmp_path):
        """Different file content must produce different hashes."""
        from src.ingest.vectorstore import _compute_hash

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")

        assert _compute_hash(f1) != _compute_hash(f2)

    def test_list_to_pgvector_format(self):
        """Vector list must be formatted as '[x,y,z]' for pgvector."""
        from src.ingest.vectorstore import _list_to_pgvector

        result = _list_to_pgvector([0.1, 0.2, 0.3])
        assert result.startswith("[")
        assert result.endswith("]")
        assert "0.10000000" in result
        assert result.count(",") == 2

    def test_list_to_pgvector_large_vector(self):
        """384-dim vector should format correctly."""
        from src.ingest.vectorstore import _list_to_pgvector

        vec    = [0.001 * i for i in range(384)]
        result = _list_to_pgvector(vec)
        assert result.count(",") == 383

    def test_check_file_status_new(self, tmp_path):
        """File not in DB → status 'new'."""
        from src.ingest.vectorstore import VectorStore

        f = tmp_path / "new_file.pdf"
        f.write_bytes(b"new document")

        with patch("src.ingest.vectorstore.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchone.return_value = None   # not in DB
            mock_conn.return_value.cursor.return_value = mock_cursor

            vs = VectorStore.__new__(VectorStore)
            vs._conn = mock_conn.return_value
            vs._embedder = MagicMock()

            status, doc_id = vs.check_file_status(f)

        assert status == "new"
        assert doc_id is None

    def test_check_file_status_unchanged(self, tmp_path):
        """File in DB with same hash → status 'unchanged'."""
        from src.ingest.vectorstore import VectorStore, _compute_hash

        f = tmp_path / "existing.pdf"
        f.write_bytes(b"stable content")
        current_hash = _compute_hash(f)

        with patch("src.ingest.vectorstore.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchone.return_value = (42, current_hash)  # same hash
            mock_conn.return_value.cursor.return_value = mock_cursor

            vs = VectorStore.__new__(VectorStore)
            vs._conn = mock_conn.return_value
            vs._embedder = MagicMock()

            status, doc_id = vs.check_file_status(f)

        assert status == "unchanged"
        assert doc_id == 42

    def test_check_file_status_changed(self, tmp_path):
        """File in DB with different hash → status 'changed'."""
        from src.ingest.vectorstore import VectorStore

        f = tmp_path / "changed.pdf"
        f.write_bytes(b"new version content")

        with patch("src.ingest.vectorstore.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = lambda s: s
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchone.return_value = (7, "old_hash_different")
            mock_conn.return_value.cursor.return_value = mock_cursor

            vs = VectorStore.__new__(VectorStore)
            vs._conn = mock_conn.return_value
            vs._embedder = MagicMock()

            status, doc_id = vs.check_file_status(f)

        assert status == "changed"
        assert doc_id == 7

    def test_embed_query_returns_correct_dim(self):
        """embed_query should return a 384-dim float list (real MiniLM model)."""
        from src.ingest.vectorstore import VectorStore

        with patch("src.ingest.vectorstore.psycopg2.connect"):
            vs = VectorStore.__new__(VectorStore)
            vs.conn = MagicMock()
            # Load the real model — this verifies the model is available
            from sentence_transformers import SentenceTransformer
            vs._embedder = SentenceTransformer("all-MiniLM-L6-v2")

        result = vs.embed_query("maximum torque specification for M12 bolt")

        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 5: hyde.py
# Tests: fallback on LLM failure, output is non-empty string
# ═══════════════════════════════════════════════════════════════════════════

class TestHyDE:
    """
    Tests for src/retrieval/hyde.py

    What we test:
      - When LLM succeeds: returns generated hypothetical document
      - When LLM fails: returns original query (graceful fallback)
      - Output is always a non-empty string
    """

    def test_returns_llm_output_when_openai_available(self):
        """Should return the LLM-generated hypothetical doc text."""
        from src.retrieval import hyde

        expected = "For M12 metric bolts, the standard torque specification is 85 Nm."

        with patch("src.retrieval.hyde.HAS_OPENAI", True), \
             patch("src.retrieval.hyde._call_openai", return_value=expected):
            result = hyde.expand_with_hyde("M12 bolt torque spec")

        assert result == expected

    def test_fallback_to_original_query_on_openai_failure(self):
        """When OpenAI fails and Anthropic not available, return original query."""
        from src.retrieval import hyde

        with patch("src.retrieval.hyde.HAS_OPENAI", True), \
             patch("src.retrieval.hyde.HAS_ANTHROPIC", False), \
             patch("src.retrieval.hyde._call_openai", side_effect=Exception("network error")):
            result = hyde.expand_with_hyde("max pressure valve V-200")

        assert result == "max pressure valve V-200"

    def test_returns_string_type(self):
        """expand_with_hyde should always return a str."""
        from src.retrieval import hyde

        with patch("src.retrieval.hyde.HAS_OPENAI", False), \
             patch("src.retrieval.hyde.HAS_ANTHROPIC", False):
            result = hyde.expand_with_hyde("test query")

        assert isinstance(result, str)

    def test_uses_anthropic_when_openai_unavailable(self):
        """Should fall through to Anthropic when no OpenAI key."""
        from src.retrieval import hyde

        expected = "A hypothetical technical answer about bearings."

        with patch("src.retrieval.hyde.HAS_OPENAI", False), \
             patch("src.retrieval.hyde.HAS_ANTHROPIC", True), \
             patch("src.retrieval.hyde._call_anthropic", return_value=expected):
            result = hyde.expand_with_hyde("bearing failure signs")

        assert result == expected


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 6: retriever.py — RRF logic (pure Python, zero external deps)
# ═══════════════════════════════════════════════════════════════════════════

class TestRRF:
    """
    Tests for _reciprocal_rank_fusion() in src/retrieval/retriever.py

    This is pure Python math — no mocking needed.

    What we test:
      - Chunk appearing in multiple lists ranks higher than chunk in one list
      - Chunks deduplicated correctly across lists
      - Empty input lists work
      - rrf_score field is added to each result
      - Order: chunk with most list appearances (or highest-rank appearances) comes first
    """

    def _make_chunk(self, id_: int, content: str, ctype: str = "text") -> dict:
        return {"id": id_, "content": content, "chunk_type": ctype}

    def test_chunk_in_two_lists_outranks_chunk_in_one(self):
        """Chunk appearing in both lists should rank higher."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        shared = self._make_chunk(1, "shared chunk")
        only1  = self._make_chunk(2, "only in list1")
        only2  = self._make_chunk(3, "only in list2")

        list1 = [only1, shared]
        list2 = [shared, only2]

        merged = _reciprocal_rank_fusion([list1, list2], k=60)

        # shared appears in both lists → should rank first
        assert merged[0]["id"] == 1

    def test_deduplication(self):
        """Same chunk in multiple lists should appear only once in output."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        c = self._make_chunk(99, "duplicate chunk")
        merged = _reciprocal_rank_fusion([[c], [c], [c]], k=60)

        ids = [x["id"] for x in merged]
        assert ids.count(99) == 1

    def test_rrf_score_assigned_to_all_results(self):
        """Every result must have an rrf_score field."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        chunks = [self._make_chunk(i, f"chunk {i}") for i in range(5)]
        merged = _reciprocal_rank_fusion([chunks], k=60)

        assert all("rrf_score" in c for c in merged)

    def test_empty_lists_return_empty(self):
        """All empty input lists should return empty result."""
        from src.retrieval.retriever import _reciprocal_rank_fusion
        assert _reciprocal_rank_fusion([[], [], []]) == []

    def test_single_list_order_preserved_by_rank(self):
        """In a single list, earlier items should have higher rrf_score."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        chunks = [self._make_chunk(i, f"chunk {i}") for i in range(4)]
        merged = _reciprocal_rank_fusion([chunks], k=60)

        scores = [c["rrf_score"] for c in merged]
        # Scores should be strictly decreasing (first result is best)
        assert scores == sorted(scores, reverse=True)

    def test_different_chunk_types_merged(self):
        """Text, table, and image chunks should all be merged together."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        text_chunks  = [self._make_chunk(1, "text",  "text")]
        table_chunks = [self._make_chunk(2, "table", "table")]
        image_chunks = [self._make_chunk(3, "image", "image")]

        merged = _reciprocal_rank_fusion([text_chunks, table_chunks, image_chunks])
        types  = {c["chunk_type"] for c in merged}
        assert types == {"text", "table", "image"}

    def test_rrf_k_parameter_affects_scores(self):
        """Lower k should give higher score to rank-1 result."""
        from src.retrieval.retriever import _reciprocal_rank_fusion

        chunk = self._make_chunk(1, "only chunk")
        result_k1  = _reciprocal_rank_fusion([[chunk]], k=1)
        result_k60 = _reciprocal_rank_fusion([[chunk]], k=60)

        # With k=1: score = 1/(0+1) = 1.0
        # With k=60: score = 1/(0+60) = 0.0167
        assert result_k1[0]["rrf_score"] > result_k60[0]["rrf_score"]


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 7: adaptive_router.py
# Tests: routing decisions, fallback to 'complex' on failure
# ═══════════════════════════════════════════════════════════════════════════

class TestAdaptiveRouter:
    """
    Tests for src/retrieval/adaptive_router.py

    What we test:
      - classify_query returns 'simple' when LLM says SIMPLE
      - classify_query returns 'complex' when LLM says COMPLEX
      - Falls back to 'complex' on any LLM failure (safe default)
      - answer_simple_query returns string from LLM
    """

    def test_classifies_as_simple(self):
        """LLM saying SIMPLE → classify_query returns 'simple'."""
        from src.retrieval.adaptive_router import classify_query

        with patch("src.retrieval.adaptive_router._call_llm", return_value="SIMPLE"):
            result = classify_query("What is Newton's second law?")

        assert result == "simple"

    def test_classifies_as_complex(self):
        """LLM saying COMPLEX → classify_query returns 'complex'."""
        from src.retrieval.adaptive_router import classify_query

        with patch("src.retrieval.adaptive_router._call_llm", return_value="COMPLEX"):
            result = classify_query("What is the pressure rating of valve V-200?")

        assert result == "complex"

    def test_defaults_to_complex_on_failure(self):
        """When LLM throws, should default to 'complex' (safer)."""
        from src.retrieval.adaptive_router import classify_query

        with patch("src.retrieval.adaptive_router._call_llm", side_effect=Exception("fail")):
            result = classify_query("any query")

        assert result == "complex"

    def test_defaults_to_complex_on_unexpected_response(self):
        """Unexpected LLM response (not SIMPLE/COMPLEX) → 'complex'."""
        from src.retrieval.adaptive_router import classify_query

        with patch("src.retrieval.adaptive_router._call_llm", return_value="MAYBE"):
            result = classify_query("ambiguous query")

        assert result == "complex"

    def test_answer_simple_query_returns_string(self):
        """answer_simple_query should return the LLM response string."""
        from src.retrieval.adaptive_router import answer_simple_query

        expected = "Newton's second law states F = ma."
        with patch("src.retrieval.adaptive_router._call_llm", return_value=expected):
            result = answer_simple_query("What is Newton's second law?")

        assert result == expected


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 8: crag.py
# Tests: filter logic (pure Python) + LLM scoring mock
# ═══════════════════════════════════════════════════════════════════════════

class TestCRAG:
    """
    Tests for src/retrieval/crag.py

    What we test:
      filter_chunks() — pure Python, no mocking needed:
        - All relevant → HIGH confidence, no irrelevant returned
        - Mix of relevant + ambiguous → HIGH, ambiguous kept
        - Only ambiguous → MEDIUM confidence
        - Only irrelevant → LOW confidence, all returned as fallback

      score_chunks() — LLM mocked:
        - RELEVANT response sets crag_score=1.0
        - IRRELEVANT response sets crag_score=0.0
        - Failure defaults to ambiguous
    """

    def _scored(self, id_: int, relevance: str) -> dict:
        scores = {"relevant": 1.0, "ambiguous": 0.5, "irrelevant": 0.0}
        return {"id": id_, "content": f"chunk {id_}", "relevance": relevance,
                "crag_score": scores[relevance]}

    def test_filter_all_relevant_high_confidence(self):
        chunks = [self._scored(1, "relevant"), self._scored(2, "relevant")]
        from src.retrieval.crag import filter_chunks
        filtered, confidence = filter_chunks(chunks)
        assert confidence == "high"
        assert all(c["relevance"] == "relevant" for c in filtered)

    def test_filter_relevant_plus_ambiguous(self):
        chunks = [self._scored(1, "relevant"), self._scored(2, "ambiguous"),
                  self._scored(3, "irrelevant")]
        from src.retrieval.crag import filter_chunks
        filtered, confidence = filter_chunks(chunks)
        assert confidence == "high"
        ids = [c["id"] for c in filtered]
        assert 1 in ids   # relevant kept
        assert 2 in ids   # ambiguous kept (since relevant exists)
        assert 3 not in ids  # irrelevant dropped

    def test_filter_only_ambiguous_medium_confidence(self):
        chunks = [self._scored(1, "ambiguous"), self._scored(2, "ambiguous")]
        from src.retrieval.crag import filter_chunks
        filtered, confidence = filter_chunks(chunks)
        assert confidence == "medium"
        assert len(filtered) == 2

    def test_filter_only_irrelevant_low_confidence(self):
        chunks = [self._scored(1, "irrelevant"), self._scored(2, "irrelevant")]
        from src.retrieval.crag import filter_chunks
        filtered, confidence = filter_chunks(chunks)
        assert confidence == "low"
        assert len(filtered) == 2  # fallback: return all

    def test_score_chunks_sets_relevant(self):
        """When LLM returns RELEVANT, crag_score should be 1.0."""
        from src.retrieval.crag import score_chunks

        input_chunks = [{"id": 1, "content": "M12 bolt torque is 85 Nm."}]

        with patch("src.retrieval.crag._score_one_chunk", return_value="relevant"):
            scored = score_chunks("What is M12 torque?", input_chunks)

        assert scored[0]["relevance"] == "relevant"
        assert scored[0]["crag_score"] == 1.0

    def test_score_chunks_sets_irrelevant(self):
        """When LLM returns IRRELEVANT, crag_score should be 0.0."""
        from src.retrieval.crag import score_chunks

        input_chunks = [{"id": 1, "content": "Color coding for pipes."}]

        with patch("src.retrieval.crag._score_one_chunk", return_value="irrelevant"):
            scored = score_chunks("What is M12 torque?", input_chunks)

        assert scored[0]["relevance"] == "irrelevant"
        assert scored[0]["crag_score"] == 0.0

    def test_score_one_chunk_defaults_ambiguous_on_failure(self):
        """LLM failure during scoring should default to 'ambiguous'."""
        from src.retrieval.crag import _score_one_chunk

        with patch("src.retrieval.crag._call_llm", side_effect=Exception("LLM down")):
            result = _score_one_chunk("test query", "test passage")

        assert result == "ambiguous"

    def test_score_does_not_mutate_original_chunks(self):
        """score_chunks should not mutate the input list."""
        from src.retrieval.crag import score_chunks

        original = [{"id": 1, "content": "test"}]
        original_copy = [dict(c) for c in original]

        with patch("src.retrieval.crag._score_one_chunk", return_value="relevant"):
            score_chunks("q", original)

        # Original should be unchanged
        assert original[0] == original_copy[0]


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 9: prompts.py — pure Python, no mocking needed
# ═══════════════════════════════════════════════════════════════════════════

class TestPrompts:
    """
    Tests for src/generation/prompts.py

    Pure Python — no LLM, no DB, no mocking.

    What we test:
      build_rag_prompt:
        - Query appears in prompt
        - Each chunk's content appears
        - Source citation info included
        - Confidence instruction varies by level

      build_self_rag_critique_prompt:
        - Answer text included
        - SUPPORTED/NOT_SUPPORTED keywords present

      _format_context:
        - chunk_type='table' gets TABLE label
        - chunk_type='image' gets IMAGE DESCRIPTION label
        - Source filename and page appear
    """

    def _chunk(self, ctype: str, content: str, page: int = 1) -> dict:
        return {"chunk_type": ctype, "content": content, "page": page,
                "filename": "manual.pdf", "section": ""}

    def test_rag_prompt_contains_query(self):
        from src.generation.prompts import build_rag_prompt
        prompt = build_rag_prompt(
            "What is the torque spec?",
            [self._chunk("text", "M12 requires 85 Nm.")],
            "high"
        )
        assert "What is the torque spec?" in prompt

    def test_rag_prompt_contains_chunk_content(self):
        from src.generation.prompts import build_rag_prompt
        prompt = build_rag_prompt(
            "query",
            [self._chunk("text", "unique_content_xyz_789")],
            "high"
        )
        assert "unique_content_xyz_789" in prompt

    def test_rag_prompt_contains_source_filename(self):
        from src.generation.prompts import build_rag_prompt
        prompt = build_rag_prompt(
            "query",
            [self._chunk("text", "content")],
            "high"
        )
        assert "manual.pdf" in prompt

    def test_rag_prompt_high_confidence_instruction(self):
        from src.generation.prompts import build_rag_prompt
        prompt = build_rag_prompt("q", [self._chunk("text", "c")], "high")
        assert "confidently" in prompt.lower() or "confidence" in prompt.lower()

    def test_rag_prompt_low_confidence_instruction(self):
        from src.generation.prompts import build_rag_prompt
        prompt = build_rag_prompt("q", [self._chunk("text", "c")], "low")
        assert "fabricate" in prompt or "uncertain" in prompt

    def test_format_context_table_label(self):
        from src.generation.prompts import _format_context
        chunks = [self._chunk("table", "| A | B |", page=5)]
        ctx = _format_context(chunks)
        assert "TABLE" in ctx
        assert "Page 5" in ctx

    def test_format_context_image_label(self):
        from src.generation.prompts import _format_context
        chunks = [self._chunk("image", "Wiring diagram description", page=7)]
        ctx = _format_context(chunks)
        assert "IMAGE DESCRIPTION" in ctx
        assert "Page 7" in ctx

    def test_format_context_multiple_chunks_numbered(self):
        from src.generation.prompts import _format_context
        chunks = [
            self._chunk("text", "text chunk", page=1),
            self._chunk("table", "table chunk", page=2),
        ]
        ctx = _format_context(chunks)
        assert "Context 1" in ctx
        assert "Context 2" in ctx

    def test_self_rag_critique_contains_answer(self):
        from src.generation.prompts import build_self_rag_critique_prompt
        prompt = build_self_rag_critique_prompt(
            query="test query",
            context_str="some context",
            answer="The torque is 85 Nm."
        )
        assert "The torque is 85 Nm." in prompt

    def test_self_rag_critique_contains_supported_keywords(self):
        from src.generation.prompts import build_self_rag_critique_prompt
        prompt = build_self_rag_critique_prompt("q", "ctx", "answer")
        assert "SUPPORTED" in prompt
        assert "NOT_SUPPORTED" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 10: generator.py
# Tests: LLM routing, Self-RAG grounding check, source extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestGenerator:
    """
    Tests for src/generation/generator.py

    What we test:
      - Text-only chunks → TEXT_LLM (gpt-4o-mini) used
      - Image chunk present → VISION_LLM (gpt-4o) used
      - Self-RAG SUPPORTED → answer emitted as-is
      - Self-RAG NOT_SUPPORTED → retry attempted (if retriever provided)
      - Empty chunks → graceful "not found" response
      - _extract_sources deduplicates correctly
    """

    def _text_chunk(self, content: str = "torque is 85 Nm") -> dict:
        return {"id": 1, "content": content, "chunk_type": "text",
                "page": 5, "filename": "manual.pdf", "section": "Specs",
                "image_path": None}

    def _image_chunk(self, tmp_path) -> dict:
        from PIL import Image
        img_path = tmp_path / "img.png"
        Image.new("RGB", (100, 100)).save(str(img_path))
        return {"id": 2, "content": "Wiring diagram for panel A3",
                "chunk_type": "image", "page": 7, "filename": "manual.pdf",
                "section": "", "image_path": str(img_path)}

    def test_empty_chunks_returns_not_found(self):
        """Empty chunk list should return a graceful 'not found' response."""
        from src.generation.generator import generate
        response = generate("any query", [], "low")
        assert "not find" in response.answer.lower() or "could not" in response.answer.lower()
        assert response.confidence == "low"

    def test_text_only_uses_text_llm(self):
        """Text-only context should route to TEXT_LLM (gpt-4o-mini)."""
        from src.generation.generator import generate

        with patch("src.generation.generator._call_llm", return_value="Answer text.") as mock_llm, \
             patch("src.generation.generator._check_grounding", return_value="SUPPORTED"):

            response = generate("What is torque?", [self._text_chunk()], "high")

        # _call_llm should be called with TEXT_LLM model
        from configs.settings import TEXT_LLM
        call_args = mock_llm.call_args
        assert call_args[0][2] == TEXT_LLM   # third positional arg = model

    def test_image_chunk_uses_vision_llm(self, tmp_path):
        """Image chunk should route to VISION_LLM (gpt-4o)."""
        from src.generation.generator import generate
        from configs.settings import VISION_LLM

        with patch("src.generation.generator._call_llm", return_value="Diagram shows...") as mock_llm, \
             patch("src.generation.generator._check_grounding", return_value="SUPPORTED"):

            response = generate(
                "What does the diagram show?",
                [self._image_chunk(tmp_path)],
                "high"
            )

        call_args = mock_llm.call_args
        assert call_args[0][2] == VISION_LLM

    def test_self_rag_supported_emits_answer(self):
        """When Self-RAG says SUPPORTED, answer should be returned without retry."""
        from src.generation.generator import generate

        with patch("src.generation.generator._call_llm", return_value="Correct answer."), \
             patch("src.generation.generator._check_grounding", return_value="SUPPORTED"):

            response = generate("query", [self._text_chunk()], "high")

        assert response.answer == "Correct answer."
        assert response.self_rag_status == "supported"
        assert response.retried is False

    def test_self_rag_not_supported_triggers_retry(self):
        """NOT_SUPPORTED should trigger one retry if retriever is provided."""
        from src.generation.generator import generate

        mock_retriever = MagicMock()
        mock_retriever.query.return_value = [self._text_chunk("retry chunk content")]

        call_count = {"n": 0}
        def mock_llm(prompt, img_chunks, model):
            call_count["n"] += 1
            return "Retry answer."

        with patch("src.generation.generator._call_llm", side_effect=mock_llm), \
             patch("src.generation.generator._check_grounding", return_value="NOT_SUPPORTED"):
            response = generate("query", [self._text_chunk()], "medium", mock_retriever)

        assert response.retried is True
        assert call_count["n"] == 2   # original + 1 retry

    def test_extract_sources_deduplicates(self):
        """_extract_sources should not return duplicate (filename, page) pairs."""
        from src.generation.generator import _extract_sources

        chunks = [
            {"filename": "manual.pdf", "page": 5, "chunk_type": "text",  "section": ""},
            {"filename": "manual.pdf", "page": 5, "chunk_type": "text",  "section": ""},  # dup
            {"filename": "manual.pdf", "page": 6, "chunk_type": "table", "section": ""},
        ]
        sources = _extract_sources(chunks)
        assert len(sources) == 2   # page 5 deduplicated

    def test_response_includes_sources(self):
        """RAGResponse.sources should list cited documents."""
        from src.generation.generator import generate

        with patch("src.generation.generator._call_llm", return_value="Answer."), \
             patch("src.generation.generator._check_grounding", return_value="SUPPORTED"):

            response = generate("query", [self._text_chunk()], "high")

        assert len(response.sources) == 1
        assert response.sources[0]["filename"] == "manual.pdf"
        assert response.sources[0]["page"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 11: judge.py
# Tests: JSON parsing, score clamping, fallback on bad response
# ═══════════════════════════════════════════════════════════════════════════

class TestJudge:
    """
    Tests for src/evaluation/judge.py

    What we test:
      - Valid JSON response → correct score extraction
      - avg_score is average of three dimensions
      - Scores clamped to 1-5 range
      - Malformed JSON → returns zeros (doesn't crash)
      - factuality check returns expected keys
    """

    def test_judge_answer_valid_response(self):
        """Valid JSON from LLM should parse to correct scores."""
        from src.evaluation.judge import judge_answer

        mock_response = '{"relevance": 5, "correctness": 4, "completeness": 4}'

        with patch("src.evaluation.judge._call_llm", return_value=mock_response):
            scores = judge_answer("q", "ground truth", "answer")

        assert scores["relevance"]    == 5
        assert scores["correctness"]  == 4
        assert scores["completeness"] == 4
        assert scores["avg_score"]    == pytest.approx(4.333, abs=0.01)

    def test_judge_answer_avg_score_computed(self):
        """avg_score should be (relevance + correctness + completeness) / 3."""
        from src.evaluation.judge import judge_answer

        with patch("src.evaluation.judge._call_llm",
                   return_value='{"relevance": 3, "correctness": 4, "completeness": 5}'):
            scores = judge_answer("q", "gt", "ans")

        assert scores["avg_score"] == pytest.approx(4.0, abs=0.01)

    def test_judge_answer_scores_clamped_to_1_5(self):
        """Scores outside 1-5 should be clamped."""
        from src.evaluation.judge import judge_answer

        # LLM returns out-of-range values
        with patch("src.evaluation.judge._call_llm",
                   return_value='{"relevance": 10, "correctness": 0, "completeness": 3}'):
            scores = judge_answer("q", "gt", "ans")

        assert scores["relevance"]   == 5   # clamped from 10
        assert scores["correctness"] == 1   # clamped from 0

    def test_judge_answer_malformed_json_returns_zeros(self):
        """Malformed JSON from LLM should return zeros (not crash)."""
        from src.evaluation.judge import judge_answer

        with patch("src.evaluation.judge._call_llm", return_value="not json at all"):
            scores = judge_answer("q", "gt", "ans")

        assert scores["avg_score"] == 0.0

    def test_judge_answer_llm_failure_returns_zeros(self):
        """LLM exception during judging should return zeros."""
        from src.evaluation.judge import judge_answer

        with patch("src.evaluation.judge._call_llm", side_effect=Exception("API down")):
            scores = judge_answer("q", "gt", "ans")

        assert scores["avg_score"] == 0.0

    def test_judge_factuality_returns_required_keys(self):
        """judge_factuality should return factual_claims, supported_claims, factuality_score."""
        from src.evaluation.judge import judge_factuality

        mock_response = '{"factual_claims": 5, "supported_claims": 4, "factuality_score": 0.8}'
        chunks = [{"content": "M12 bolt torque is 85 Nm."}]

        with patch("src.evaluation.judge._call_llm", return_value=mock_response):
            result = judge_factuality(chunks, "answer with 5 claims")

        assert "factual_claims"    in result
        assert "supported_claims"  in result
        assert "factuality_score"  in result
        assert result["factuality_score"] == pytest.approx(0.8)


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 12: metrics.py
# Tests: aggregation logic, SLA check output, CSV save
# ═══════════════════════════════════════════════════════════════════════════

class TestMetrics:
    """
    Tests for src/evaluation/metrics.py

    What we test:
      - _compute_summary aggregates latencies and judge scores correctly
      - P99 latency is computed from sorted latencies
      - SLA fields present in summary
      - save_results_csv creates a CSV file with expected columns
    """

    def _make_result(self, latency: float, avg_score: float):
        from src.evaluation.metrics import EvalResult
        return EvalResult(
            question="test question",
            ground_truth="ground truth",
            answer="answer",
            retrieved_chunks=[],
            confidence="high",
            latency_sec=latency,
            judge_scores={"relevance": 4, "correctness": 4, "completeness": 4,
                          "avg_score": avg_score},
            factuality={"factual_claims": 3, "supported_claims": 3, "factuality_score": 1.0},
            sources=[],
        )

    def test_avg_judge_score_computed(self):
        from src.evaluation.metrics import _compute_summary

        results = [self._make_result(1.0, 4.0), self._make_result(1.5, 5.0)]
        summary = _compute_summary(results)

        assert summary.avg_judge_score == pytest.approx(4.5, abs=0.01)

    def test_avg_latency_computed(self):
        from src.evaluation.metrics import _compute_summary

        results = [self._make_result(1.0, 4.0), self._make_result(3.0, 4.0)]
        summary = _compute_summary(results)

        assert summary.avg_latency_sec == pytest.approx(2.0, abs=0.01)

    def test_p99_latency_single_element(self):
        from src.evaluation.metrics import _compute_summary

        results = [self._make_result(1.5, 4.0)]
        summary = _compute_summary(results)

        assert summary.p99_latency_sec == pytest.approx(1.5, abs=0.01)

    def test_summary_has_all_sla_fields(self):
        from src.evaluation.metrics import _compute_summary

        results = [self._make_result(1.0, 4.0)]
        summary = _compute_summary(results)

        assert hasattr(summary, "p99_latency_sec")
        assert hasattr(summary, "mrr")
        assert hasattr(summary, "recall_at_5")
        assert hasattr(summary, "avg_factuality")

    def test_save_results_csv_creates_file(self, tmp_path):
        from src.evaluation.metrics import save_results_csv, _compute_summary

        results = [self._make_result(1.0, 4.0), self._make_result(1.5, 5.0)]
        summary = _compute_summary(results)

        out_path = str(tmp_path / "eval_results.csv")
        save_results_csv(summary, out_path)

        assert Path(out_path).exists()

        import pandas as pd
        df = pd.read_csv(out_path)
        assert "question"    in df.columns
        assert "avg_score"   in df.columns
        assert "latency_sec" in df.columns
        assert len(df) == 2

    def test_high_quality_threshold_affects_mrr(self):
        """MRR proxy increases when more answers score >= 4.0."""
        from src.evaluation.metrics import _compute_summary

        good_results = [self._make_result(1.0, 4.5)] * 8 + [self._make_result(1.0, 3.0)] * 2
        summary = _compute_summary(good_results)

        assert summary.mrr == pytest.approx(0.8, abs=0.01)
