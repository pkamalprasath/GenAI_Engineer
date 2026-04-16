"""
data_loader.py  —  Load PDF, identical logic to Data_ingestion.ipynb.
Run: python data_loader.py
"""

import fitz  # PyMuPDF
from pathlib import Path
from tqdm import tqdm
from config import PDF_PATH


def text_formatter(text: str) -> str:
    """Normalise whitespace — same as Data_ingestion.ipynb."""
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text


def open_and_read_pdf(pdf_path: Path = PDF_PATH) -> list[dict]:
    """
    Extract text page-by-page.
    Returns list of dicts identical to the notebook:
      page_number, text, page_char_count, page_word_count,
      page_sentence_count_raw, page_token_count
    """
    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num, page in tqdm(enumerate(doc), total=len(doc), desc="Reading PDF"):
        text = page.get_text()
        text = text_formatter(text)
        pages.append({
            "page_number":           page_num,
            "text":                  text,
            "page_char_count":       len(text),
            "page_word_count":       len(text.split()),
            "page_sentence_count_raw": text.count(". "),
            "page_token_count":      len(text) // 4,
        })
    doc.close()
    return pages


def get_raw_text(pages: list[dict]) -> str:
    return " ".join(p["text"] for p in pages)


def load_document() -> tuple[list[dict], str]:
    """Returns (pages, raw_text)."""
    pages = open_and_read_pdf()
    return pages, get_raw_text(pages)


if __name__ == "__main__":
    pages, raw_text = load_document()
    print(f"Pages   : {len(pages)}")
    print(f"Chars   : {len(raw_text):,}")
    print(f"Words   : {len(raw_text.split()):,}")
    print(f"Tokens  : {len(raw_text)//4:,} (approx)")
    sample = raw_text[:300].encode("ascii", errors="replace").decode()
    print(f"\nSample  : {sample}")
