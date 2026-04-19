"""
ingest_docs.py — CLI for ingesting documents into the Engineering RAG system.

USAGE:
    python ingest_docs.py data/                    # ingest all PDFs in a folder
    python ingest_docs.py data/gearbox_manual.pdf  # ingest a single file
    python ingest_docs.py data/ --doc-type sds     # force a document type

HOW INCREMENTAL INDEXING WORKS:
    For each file:
      1. Compute SHA-256 hash of the file content
      2. Check if this hash exists in the 'documents' table
      3. If unchanged → SKIP (most common case — saves time and money)
      4. If changed   → DELETE old chunks, re-process
      5. If new       → Process and insert

This handles the case study's "500 new documents daily" efficiently.
Running this script every night on a folder processes only new/changed files.

DOCUMENT TYPES (used for metadata filtering in queries):
    manual      → technical manuals, operation guides
    sds         → Safety Data Sheets (MSDS)
    datasheet   → product datasheets, spec sheets
    compliance  → ISO, OSHA, regulatory documents
    other       → everything else (default)
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from configs.logging_config import setup_logging
setup_logging()

from configs.settings import DATA_DIR, HAS_ANTHROPIC

logger = logging.getLogger(__name__)
from src.ingest.document_parser import parse_document
from src.ingest.chunker import chunk_document
from src.ingest.image_captioner import caption_images
from src.ingest.vectorstore import VectorStore


# ── Document type auto-detection ──────────────────────────────────────────

def detect_doc_type(filename: str) -> str:
    """
    Guess document type from filename.
    Overridable with --doc-type argument.
    """
    name = filename.lower()
    if any(kw in name for kw in ("sds", "msds", "safety_data", "safety-data")):
        return "sds"
    elif any(kw in name for kw in ("manual", "guide", "operation", "instruction")):
        return "manual"
    elif any(kw in name for kw in ("datasheet", "spec", "specification", "product")):
        return "datasheet"
    elif any(kw in name for kw in ("iso", "osha", "compliance", "standard", "regulation")):
        return "compliance"
    return "other"


# ── Main ingestion function ───────────────────────────────────────────────

def ingest_file(
    filepath: Path,
    vs: VectorStore,
    doc_type: str | None = None,
    caption_images_flag: bool = True,
) -> dict:
    """
    Ingest one file. Returns status dict with counts and timing.

    STATUS values:
      'skipped'  → file unchanged, no work done
      'ingested' → file successfully processed and stored
      'failed'   → error during processing
    """
    start = time.time()

    # ── Incremental check ─────────────────────────────────────────────────
    status, existing_id = vs.check_file_status(filepath)

    if status == "unchanged":
        logger.info("SKIP %s (unchanged)", filepath.name)
        return {"status": "skipped", "filename": filepath.name}

    action = "NEW" if status == "new" else "UPDATE"
    logger.info("%s %s", action, filepath.name)

    # ── Parse the document ────────────────────────────────────────────────
    parsed_doc = parse_document(filepath)
    if parsed_doc is None:
        logger.warning("Unsupported file type '%s', skipping", filepath.suffix)
        return {"status": "skipped", "filename": filepath.name}

    logger.info("  pages=%d text_blocks=%d tables=%d images=%d",
                len(parsed_doc.pages), len(parsed_doc.all_text_blocks),
                len(parsed_doc.all_tables), len(parsed_doc.all_images))

    # ── Caption images with GPT-4o ────────────────────────────────────────
    image_captions = []
    if caption_images_flag and parsed_doc.all_images:
        _vision = "Claude" if HAS_ANTHROPIC else "GPT-4o"
        logger.info("Captioning %d images with %s...", len(parsed_doc.all_images), _vision)
        image_save_dir = filepath.parent / "extracted_images" / filepath.stem
        image_captions = caption_images(
            images=parsed_doc.all_images,
            document_filename=filepath.name,
            image_save_dir=image_save_dir,
        )
        logger.info("Captioned: %d images (decorative filtered out)", len(image_captions))
    else:
        image_save_dir = filepath.parent / "extracted_images" / filepath.stem

    # ── Chunk the document ────────────────────────────────────────────────
    chunks = chunk_document(
        parsed_doc=parsed_doc,
        image_captions=image_captions,
        image_save_dir=image_save_dir,
    )

    text_chunks  = sum(1 for c in chunks if c["chunk_type"] == "text")
    table_chunks = sum(1 for c in chunks if c["chunk_type"] == "table")
    image_chunks = sum(1 for c in chunks if c["chunk_type"] == "image")
    logger.info("  chunks: %d text, %d tables, %d images", text_chunks, table_chunks, image_chunks)

    if not chunks:
        logger.warning("No chunks produced for %s", filepath.name)
        return {"status": "failed", "filename": filepath.name, "error": "no chunks"}

    # ── Store in pgvector ─────────────────────────────────────────────────
    effective_doc_type = doc_type or detect_doc_type(filepath.name)
    doc_id = vs.upsert_document(
        filepath=filepath,
        doc_type=effective_doc_type,
        chunks=chunks,
    )

    elapsed = time.time() - start
    logger.info("Done in %.1fs (doc_id=%d, type=%s)", elapsed, doc_id, effective_doc_type)

    return {
        "status":        "ingested",
        "filename":      filepath.name,
        "doc_id":        doc_id,
        "doc_type":      effective_doc_type,
        "text_chunks":   text_chunks,
        "table_chunks":  table_chunks,
        "image_chunks":  image_chunks,
        "elapsed_sec":   round(elapsed, 2),
    }


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into the Engineering RAG system"
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a PDF file or directory containing PDFs",
    )
    parser.add_argument(
        "--doc-type",
        choices=["manual", "sds", "datasheet", "compliance", "other"],
        default=None,
        help="Force document type (default: auto-detect from filename)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image captioning (faster, no GPT-4o vision cost)",
    )
    args = parser.parse_args()

    # Collect files to process
    target = args.path
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("*.pdf"))
        if not files:
            logger.warning("No PDF files found in %s", target)
            return
    else:
        logger.error("Path not found: %s", target)
        sys.exit(1)

    logger.info("Engineering RAG — Document Ingestion")
    logger.info("Files to process: %d", len(files))
    logger.info("Image captioning: %s", "disabled" if args.no_images else "enabled")

    # Initialise vector store and ensure schema exists
    vs = VectorStore()
    vs.init_schema()

    # Process each file
    summary = {"ingested": 0, "skipped": 0, "failed": 0}
    start_total = time.time()

    for filepath in files:
        result = ingest_file(
            filepath=filepath,
            vs=vs,
            doc_type=args.doc_type,
            caption_images_flag=not args.no_images,
        )
        summary[result["status"]] = summary.get(result["status"], 0) + 1

    elapsed_total = time.time() - start_total
    vs.close()

    logger.info("INGESTION COMPLETE in %.1fs — ingested=%d skipped=%d failed=%d",
                elapsed_total, summary["ingested"], summary["skipped"], summary["failed"])

    vs2 = VectorStore()
    db_stats = vs2.get_stats()
    vs2.close()
    logger.info("DB: documents=%d total_chunks=%d %s",
                db_stats["documents"], db_stats["total_chunks"],
                " ".join(f"{k}={v}" for k, v in db_stats.get("chunks_by_type", {}).items()))


if __name__ == "__main__":
    main()
