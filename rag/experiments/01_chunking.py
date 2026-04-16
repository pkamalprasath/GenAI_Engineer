"""
01_chunking.py  —  Compare 5 chunking strategies (no LangChain).

Strategies:
  C1  sentence    spaCy sentencizer, 10-sentence groups  (same as Data_ingestion.ipynb)
  C2  fixed-small Fixed character windows, size=512, overlap=50
  C3  fixed-large Fixed character windows, size=1024, overlap=100
  C4  semantic    Split where cosine similarity between adjacent sentences drops
  C5  structural  Split on paragraph / section patterns (regex)
  C6  llm-based   Claude API identifies topic boundaries

Run:  python 01_chunking.py
Output: results/chunking_stats.csv
"""

import re
import time
import json
import pandas as pd
from tqdm import tqdm
from config import RESULTS_DIR, HAS_CLAUDE, CLAUDE_API_KEY
from data_loader import load_document


# ── helpers ───────────────────────────────────────────────────────────────

def _stats(chunks: list[str], name: str, elapsed: float) -> dict:
    lens = [len(c) for c in chunks]
    return {
        "strategy":  name,
        "num_chunks": len(chunks),
        "avg_chars":  round(sum(lens) / max(len(lens), 1)),
        "min_chars":  min(lens) if lens else 0,
        "max_chars":  max(lens) if lens else 0,
        "time_sec":   round(elapsed, 2),
    }


# ── C1: Sentence-based — identical to Data_ingestion.ipynb ───────────────

def chunk_sentence(raw_text: str,
                   num_sentence_chunk_size: int = 10,
                   min_token_length: int = 30) -> list[dict]:
    """
    Splits text into sentences with spaCy, groups them into fixed windows.
    Returns list of dicts with 'sentence_chunk' key (same as notebook).
    """
    from spacy.lang.en import English
    nlp = English()
    nlp.add_pipe("sentencizer")
    nlp.max_length = len(raw_text) + 100

    doc = nlp(raw_text)
    sentences = [str(s).strip() for s in doc.sents if str(s).strip()]

    # group into windows of num_sentence_chunk_size
    chunks = []
    for i in range(0, len(sentences), num_sentence_chunk_size):
        group = sentences[i: i + num_sentence_chunk_size]
        joined = " ".join(group)
        chunks.append({
            "sentence_chunk":    joined,
            "chunk_char_count":  len(joined),
            "chunk_word_count":  len(joined.split()),
            "chunk_token_count": len(joined) // 4,
        })

    # filter short chunks (same as notebook)
    chunks = [c for c in chunks if c["chunk_token_count"] >= min_token_length]
    return chunks


def chunks_to_texts(chunks: list[dict]) -> list[str]:
    """Extract plain text from chunk dicts."""
    return [c["sentence_chunk"] for c in chunks]


# ── C2 / C3: Fixed-character windows (no LangChain) ─────────────────────

def chunk_fixed(raw_text: str, chunk_size: int = 512, overlap: int = 50) -> list[dict]:
    """Sliding window over characters."""
    results = []
    start = 0
    while start < len(raw_text):
        end = min(start + chunk_size, len(raw_text))
        chunk = raw_text[start:end].strip()
        if len(chunk) // 4 >= 30:
            results.append({
                "sentence_chunk":    chunk,
                "chunk_char_count":  len(chunk),
                "chunk_word_count":  len(chunk.split()),
                "chunk_token_count": len(chunk) // 4,
            })
        start += chunk_size - overlap
    return results


# ── C4: Semantic chunking (cosine similarity between adjacent sentences) ──

def chunk_semantic(raw_text: str,
                   similarity_threshold: float = 0.75,
                   min_sentences: int = 3,
                   max_sentences: int = 15) -> list[dict]:
    """
    Split where cosine similarity between adjacent sentence embeddings
    drops below threshold — topic boundary detection without LangChain.
    Uses all-MiniLM-L6-v2 (fast, small) for boundary detection only.
    """
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from spacy.lang.en import English

    # Sentence split
    nlp = English()
    nlp.add_pipe("sentencizer")
    nlp.max_length = len(raw_text) + 100
    sentences = [str(s).strip() for s in nlp(raw_text).sents if str(s).strip()]

    if len(sentences) < 2:
        return [{"sentence_chunk": raw_text, "chunk_char_count": len(raw_text),
                 "chunk_word_count": len(raw_text.split()), "chunk_token_count": len(raw_text)//4}]

    # Embed all sentences (fast small model)
    print("  [C4] Embedding sentences for semantic boundary detection …")
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    embs = model.encode(sentences, batch_size=64, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=True)

    # Cosine similarity between adjacent sentences (dot product on normalised)
    sims = np.array([float(embs[i] @ embs[i + 1]) for i in range(len(embs) - 1)])

    # Build chunks: new chunk starts where similarity drops below threshold
    chunks, current = [], [sentences[0]]
    for i, sim in enumerate(sims):
        if (sim < similarity_threshold and len(current) >= min_sentences) \
                or len(current) >= max_sentences:
            joined = " ".join(current)
            chunks.append({
                "sentence_chunk":    joined,
                "chunk_char_count":  len(joined),
                "chunk_word_count":  len(joined.split()),
                "chunk_token_count": len(joined) // 4,
            })
            current = []
        current.append(sentences[i + 1])

    if current:
        joined = " ".join(current)
        chunks.append({
            "sentence_chunk":    joined,
            "chunk_char_count":  len(joined),
            "chunk_word_count":  len(joined.split()),
            "chunk_token_count": len(joined) // 4,
        })

    return [c for c in chunks if c["chunk_token_count"] >= 30]


# ── C5: Structural chunking (regex, no external libs) ────────────────────

def chunk_structural(raw_text: str, min_chars: int = 200) -> list[dict]:
    """
    Split on capitalised headings, numbered sections, or long whitespace runs.
    Works well for academic/textbook PDFs.
    """
    # Split on patterns that look like section starts:
    #  - "1.", "2.1", "Chapter", "Section", "Table", "Figure" at word boundary
    #  - All-caps words of 4+ chars (e.g. "INTRODUCTION")
    pattern = re.compile(
        r'(?<=[.!?])\s{2,}(?=[A-Z])'          # sentence end + gap + capital
        r'|(?=\b(?:Chapter|Section|Table|Figure|Introduction|Summary|References|'
        r'Appendix|Abstract|Background|Methods|Results|Discussion|Conclusion)\b)'
        r'|(?=\b[0-9]{1,2}\.[0-9]{0,2}\s+[A-Z])'  # numbered section
    )
    parts = pattern.split(raw_text)
    results = []
    for part in parts:
        part = part.strip()
        if len(part) >= min_chars:
            results.append({
                "sentence_chunk":    part,
                "chunk_char_count":  len(part),
                "chunk_word_count":  len(part.split()),
                "chunk_token_count": len(part) // 4,
            })
    return results


# ── C6: LLM-based chunking (Claude API) ──────────────────────────────────

def chunk_llm_based(raw_text: str,
                    window_chars: int = 3000,
                    model: str = "claude-haiku-4-5") -> list[dict]:
    """
    Send overlapping windows to Claude, ask it to identify topic boundaries.
    Falls back to C2 fixed-512 if CLAUDE_API_KEY is not set.
    """
    if not HAS_CLAUDE:
        print("  [C6] No CLAUDE_API_KEY — falling back to fixed-512 chunking")
        return chunk_fixed(raw_text, 512, 50)

    import anthropic
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    windows = [raw_text[i: i + window_chars]
               for i in range(0, len(raw_text), window_chars)]

    all_chunks: list[str] = []
    print(f"  [C6] LLM chunking with Claude ({model}) — {len(windows)} windows …")

    for window in tqdm(windows, desc="LLM chunking"):
        prompt = (
            "Split the following nutrition text into semantically coherent chunks.\n"
            "Each chunk should cover exactly ONE topic or idea.\n"
            "Separate chunks with the delimiter: ---\n"
            "Return ONLY the chunks separated by ---, no other text.\n\n"
            f"TEXT:\n{window}"
        )
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text
            parts = [p.strip() for p in raw.split("---") if len(p.strip()) >= 100]
            all_chunks.extend(parts)
        except Exception as e:
            # On error fall back to adding the window as-is
            all_chunks.append(window.strip())

    results = []
    for c in all_chunks:
        if len(c) // 4 >= 30:
            results.append({
                "sentence_chunk":    c,
                "chunk_char_count":  len(c),
                "chunk_word_count":  len(c.split()),
                "chunk_token_count": len(c) // 4,
            })
    return results


# ── Runner ────────────────────────────────────────────────────────────────

def run_all_chunking_strategies(raw_text: str) -> pd.DataFrame:
    strategies = [
        ("C1_sentence",    lambda t: chunk_sentence(t)),
        ("C2_fixed_512",   lambda t: chunk_fixed(t, 512, 50)),
        ("C3_fixed_1024",  lambda t: chunk_fixed(t, 1024, 100)),
        ("C4_semantic",    lambda t: chunk_semantic(t)),
        ("C5_structural",  lambda t: chunk_structural(t)),
        ("C6_llm_based",   lambda t: chunk_llm_based(t)),
    ]

    results = []
    for name, fn in strategies:
        print(f"\n>> {name}")
        t0 = time.time()
        chunks = fn(raw_text)
        elapsed = time.time() - t0
        stats = _stats(chunks_to_texts(chunks), name, elapsed)
        results.append(stats)
        print(f"   chunks={stats['num_chunks']}  avg={stats['avg_chars']} chars  "
              f"time={stats['time_sec']}s")
        if chunks:
            preview = chunks[0]["sentence_chunk"][:120].encode("ascii", errors="replace").decode()
            print(f"   Preview: {preview}...")

    df = pd.DataFrame(results)
    out = RESULTS_DIR / "chunking_stats.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("Experiment 01 -- Chunking Strategies")
    print("=" * 60)
    _, raw_text = load_document()
    print(f"Document: {len(raw_text):,} chars\n")
    df = run_all_chunking_strategies(raw_text)
    print("\n" + "=" * 60)
    print(df.to_string(index=False))
