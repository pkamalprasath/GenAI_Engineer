"""
document_parser.py — Extract text, tables, and images from PDF files.

Why three separate tools?
  - pypdf     : fastest for clean text; mangles table cells into runs of text
  - pdfplumber: grid-aware table extraction; preserves rows and columns
  - pymupdf   : best for extracting embedded image bytes from PDFs

The output of this module feeds into chunker.py (text + tables)
and image_captioner.py (images).
"""

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz          # pymupdf — image extraction
import pdfplumber   # table extraction
from PIL import Image
from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    """One page worth of extracted content."""
    page_num: int
    text: str                       # raw text (may be empty for image-only pages)
    tables: list[dict]              # list of {"markdown": str, "caption": str}
    images: list[dict]              # list of {"bytes": bytes, "index": int}


@dataclass
class ParsedDocument:
    """Full extraction result for one PDF file."""
    filename: str
    pages: list[ParsedPage] = field(default_factory=list)

    @property
    def all_text_blocks(self) -> list[dict]:
        """Flat list of {page, text} dicts for chunker.py."""
        return [
            {"page": p.page_num, "text": p.text}
            for p in self.pages
            if p.text.strip()
        ]

    @property
    def all_tables(self) -> list[dict]:
        """Flat list of {page, markdown, caption} dicts."""
        result = []
        for p in self.pages:
            for tbl in p.tables:
                result.append({"page": p.page_num, **tbl})
        return result

    @property
    def all_images(self) -> list[dict]:
        """Flat list of {page, bytes, index} dicts."""
        result = []
        for p in self.pages:
            for img in p.images:
                result.append({"page": p.page_num, **img})
        return result


def parse_pdf(filepath: Path) -> ParsedDocument:
    """
    Main entry point. Parses a PDF file and returns a ParsedDocument.

    Strategy:
    1. Use pdfplumber to find table bounding boxes on each page
    2. Use pypdf to extract text (excluding table regions to avoid duplicates)
    3. Use pymupdf to extract embedded images

    Args:
        filepath: Path to the PDF file

    Returns:
        ParsedDocument with text, tables, and images per page
    """
    doc = ParsedDocument(filename=filepath.name)
    logger.info("Parsing PDF: %s", filepath.name)

    # Open with both libraries simultaneously
    plumber_doc = pdfplumber.open(filepath)
    fitz_doc    = fitz.open(str(filepath))
    pypdf_reader = PdfReader(str(filepath))

    num_pages = len(pypdf_reader.pages)

    for page_idx in range(num_pages):
        page_num     = page_idx + 1
        plumber_page = plumber_doc.pages[page_idx]
        pypdf_page   = pypdf_reader.pages[page_idx]
        fitz_page    = fitz_doc[page_idx]

        # ── Step 1: Extract tables with pdfplumber ────────────────────────
        # pdfplumber detects grid lines and extracts structured table data
        tables = _extract_tables(plumber_page)

        # ── Step 2: Extract text with pypdf ───────────────────────────────
        # Extract all text; table text will overlap but that's acceptable
        # at this stage — SemanticChunker will handle any repetition
        raw_text = pypdf_page.extract_text() or ""

        # ── Step 3: Extract images with pymupdf ───────────────────────────
        images = _extract_images(fitz_page, page_num)

        doc.pages.append(ParsedPage(
            page_num=page_num,
            text=raw_text,
            tables=tables,
            images=images,
        ))

    plumber_doc.close()
    fitz_doc.close()

    total_images = sum(len(p.images) for p in doc.pages)
    total_tables = sum(len(p.tables) for p in doc.pages)
    logger.info("Parsed %s: %d pages → %d text blocks, %d tables, %d images",
                filepath.name, num_pages,
                sum(len(p.text) > 0 for p in doc.pages),
                total_tables, total_images)

    return doc


def _extract_tables(plumber_page) -> list[dict]:
    """
    Extract tables from a pdfplumber page object.

    Returns list of dicts with:
      - markdown: table as Markdown string (| col1 | col2 | ...)
      - caption: auto-generated description of the table

    Why Markdown?
    The LLM reads Markdown tables easily. Storing as Markdown also means
    the table content is human-readable when you inspect the database.
    """
    tables = []
    for tbl in plumber_page.extract_tables():
        if not tbl or len(tbl) < 2:
            # Skip empty or single-row tables (likely headers or artifacts)
            continue

        markdown = _table_to_markdown(tbl)
        if not markdown.strip():
            continue

        # Auto-generate a simple caption from the first row (header)
        header_cells = [str(c or "").strip() for c in tbl[0] if c]
        caption = f"Table with columns: {', '.join(header_cells[:5])}"

        tables.append({"markdown": markdown, "caption": caption})

    return tables


def _table_to_markdown(table_data: list[list]) -> str:
    """
    Convert pdfplumber table data (list of lists) to Markdown table string.

    Example input:  [["Bolt", "Torque (Nm)"], ["M12", "85"], ["M8", "25"]]
    Example output: "| Bolt | Torque (Nm) |\\n|------|------------|\\n| M12  | 85         |"

    The separator row (|---|---|) tells the LLM this is a proper table.
    """
    if not table_data:
        return ""

    # Clean cells: replace None with empty string, strip whitespace
    cleaned = [
        [str(cell or "").strip().replace("\n", " ") for cell in row]
        for row in table_data
    ]

    # Determine column widths for alignment
    num_cols = max(len(row) for row in cleaned)
    # Pad rows that have fewer columns
    cleaned = [row + [""] * (num_cols - len(row)) for row in cleaned]

    col_widths = [
        max(len(row[i]) for row in cleaned)
        for i in range(num_cols)
    ]

    def fmt_row(row: list[str]) -> str:
        cells = [row[i].ljust(col_widths[i]) for i in range(num_cols)]
        return "| " + " | ".join(cells) + " |"

    lines = [fmt_row(cleaned[0])]
    # Separator row
    lines.append("| " + " | ".join("-" * w for w in col_widths) + " |")
    for row in cleaned[1:]:
        lines.append(fmt_row(row))

    return "\n".join(lines)


def _extract_images(fitz_page, page_num: int, render_page_fallback: bool = True) -> list[dict]:
    """
    Extract images from a pymupdf page.

    Two strategies:
    1. Extract embedded raster images (PNG/JPEG) — works for most manuals
    2. If no raster images found, render the full page as PNG at 150 DPI
       and return it as a single image — catches vector graphics and GHS
       pictograms in SDS documents that are drawn as PDF vector commands.

    Size filtering: raster images < 50×50 px are decorative — skip them.
    """
    images = []
    image_list = fitz_page.get_images(full=True)

    seen_xrefs = set()
    for img_idx, img_info in enumerate(image_list):
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            base_image = fitz_page.parent.extract_image(xref)
            img_bytes  = base_image["image"]
            img_ext    = base_image["ext"]

            pil_img = Image.open(io.BytesIO(img_bytes))
            w, h    = pil_img.size

            # Skip tiny decorative images
            if w < 50 or h < 50:
                continue

            # Skip images with extreme aspect ratios (decorative lines, dividers)
            if min(w, h) > 0 and max(w, h) / min(w, h) > 20:
                continue

            if img_ext.lower() not in ("png", "jpeg", "jpg"):
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()

            images.append({
                "bytes":  img_bytes,
                "index":  img_idx,
                "width":  w,
                "height": h,
                "page":   page_num,
            })
        except Exception as e:
            logger.debug("Skipping unreadable image xref=%s page=%d: %s", xref, page_num, e)
            continue

    # Render pages with significant vector drawings — captures schematics,
    # GHS pictograms, and engineering diagrams drawn as PDF vector commands
    # that are invisible to get_images().
    # Always checked (not just when no embedded images) because a page may
    # have both a small embedded logo AND a large vector diagram.
    if render_page_fallback:
        try:
            drawings = fitz_page.get_drawings()
            has_vector_content = len(drawings) > 10  # >10 paths = likely a real diagram

            if has_vector_content:
                pixmap    = fitz_page.get_pixmap(dpi=150)
                img_bytes = pixmap.tobytes("png")
                pil_img   = Image.open(io.BytesIO(img_bytes))
                w, h      = pil_img.size

                if w > 100 and h > 100:
                    images.append({
                        "bytes":  img_bytes,
                        "index":  len(images),  # unique index per page
                        "width":  w,
                        "height": h,
                        "page":   page_num,
                        "is_page_render": True,
                    })
        except Exception as e:
            logger.warning("Page render failed page=%d: %s", page_num, e)

    if images:
        logger.debug("Page %d: extracted %d image(s) (embedded=%d, rendered=%d)",
                     page_num, len(images),
                     sum(1 for i in images if not i.get('is_page_render')),
                     sum(1 for i in images if i.get('is_page_render')))

    return images


def parse_text_file(filepath: Path) -> ParsedDocument:
    """
    Simple parser for plain text files (.txt).
    Used as fallback for non-PDF documents.
    """
    doc = ParsedDocument(filename=filepath.name)
    text = filepath.read_text(encoding="utf-8", errors="replace")
    doc.pages.append(ParsedPage(
        page_num=1,
        text=text,
        tables=[],
        images=[],
    ))
    return doc


def parse_document(filepath: Path) -> Optional[ParsedDocument]:
    """
    Route to the appropriate parser based on file extension.

    Supported: .pdf, .txt
    Returns None for unsupported file types (caller should log and skip).
    """
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(filepath)
    elif suffix == ".txt":
        return parse_text_file(filepath)
    else:
        return None
