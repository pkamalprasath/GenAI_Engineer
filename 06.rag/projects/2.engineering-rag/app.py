"""
app.py — Engineering RAG Chatbot
RUN: streamlit run app.py
"""
import logging
import os, re, sys
from pathlib import Path
import markdown as md_lib
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from configs.logging_config import setup_logging
setup_logging(app_mode=True)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Engineering RAG",
    page_icon="⚙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
}
/* Force dark background */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"],
section.main,
.main .block-container {
    background: #0d0d0d !important;
}
.block-container { padding: 2rem 1.5rem 6rem !important; max-width: 820px; margin: 0 auto; }
section[data-testid="stSidebar"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }

/* Nav */
.nav-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 0 14px; border-bottom: 1px solid #1e1e1e; margin-bottom: 2rem;
}
.nav-title { font-family:'Space Mono',monospace; font-size:1.1rem; font-weight:700; color:#fff; }
.nav-title span { color:#777; font-weight:400; }
.nav-by { font-size:0.82rem; color:#555; font-family:'Space Mono',monospace; margin-top:2px; }
.nav-by b { color:#f5c542; }
.nav-dot-wrap { display:flex; align-items:center; gap:6px; font-size:0.82rem; color:#777; }
.ndot { width:8px; height:8px; border-radius:50%; }
.ndot-on  { background:#22c55e; box-shadow:0 0 6px #22c55e88; }
.ndot-off { background:#444; }

/* Key gate */
.key-gate { max-width:460px; margin:3rem auto; text-align:center; }
.key-gate-icon { font-size:2.6rem; margin-bottom:1rem; }
.key-gate-title { font-family:'Space Mono',monospace; font-size:1.5rem; font-weight:700; color:#fff; margin-bottom:.5rem; }
.key-gate-sub   { font-size:.95rem; color:#666; line-height:1.7; margin-bottom:2rem; }
.key-hint { font-size:.78rem; color:#555; margin-top:4px; text-align:left; line-height:1.6; }
.key-hint code { color:#f5c542; background:#1a1a1a; padding:2px 6px; border-radius:4px; font-size:.76rem; }

/* Inputs */
.stTextInput input {
    background:#1a1a1a !important; border:1px solid #2a2a2a !important;
    border-radius:9px !important; color:#e8e8e8 !important;
    font-size:.95rem !important; padding:10px 14px !important;
    transition:border-color .15s !important;
}
.stTextInput input:focus { border-color:#f5c542 !important; box-shadow:0 0 0 2px rgba(245,197,66,.15) !important; }
.stTextInput label { color:#666 !important; font-size:.8rem !important; }

/* Primary button — yellow */
[data-testid="stBaseButton-primary"],
.btn-y > div > button,
.btn-y button {
    background:#f5c542 !important; color:#0d0d0d !important;
    border:none !important; border-radius:9px !important;
    font-weight:700 !important; font-size:1rem !important;
    padding:13px 24px !important; width:100% !important; cursor:pointer !important;
    font-family:'Space Mono',monospace !important; transition:all .15s !important;
    letter-spacing:.2px;
}
[data-testid="stBaseButton-primary"]:hover,
.btn-y > div > button:hover,
.btn-y button:hover {
    background:#ffd85c !important; transform:translateY(-1px);
    box-shadow:0 4px 18px rgba(245,197,66,.35) !important;
}

/* Ghost button */
.btn-g button {
    background:transparent !important; color:#666 !important;
    border:1px solid #252525 !important; border-radius:7px !important;
    font-size:.88rem !important; padding:6px 16px !important; transition:all .15s !important;
}
.btn-g button:hover { color:#999 !important; border-color:#333 !important; }

/* DB chips */
.db-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:1.4rem; }
.db-chip { background:#141414; border:1px solid #1e1e1e; border-radius:20px; padding:5px 14px; font-size:.8rem; color:#777; display:flex; align-items:center; gap:5px; }
.db-chip b { color:#f5c542; font-family:monospace; font-size:.88rem; }

/* Hero */
.hero { text-align:center; padding:2rem 0 .5rem; }
.hero-title { font-family:'Space Mono',monospace; font-size:1.6rem; font-weight:700; color:#fff; margin-bottom:.6rem; }
.hero-sub { font-size:.95rem; color:#666; line-height:1.7; max-width:500px; margin:0 auto 2rem; }

/* Sample question grid */
.sq-card button {
    background:#141414 !important; border:1px solid #1e1e1e !important;
    border-radius:11px !important; padding:14px 16px !important;
    text-align:left !important; white-space:normal !important; word-wrap:break-word !important;
    height:auto !important; font-size:.92rem !important; font-weight:400 !important;
    color:#ccc !important; line-height:1.5 !important; width:100% !important; transition:all .15s !important;
}
.sq-card button:hover {
    border-color:#f5c542 !important; color:#f5c542 !important;
    background:#1a1800 !important; transform:translateY(-1px) !important;
    box-shadow:0 4px 14px rgba(245,197,66,.08) !important;
}

/* User bubble */
.msg-user { display:flex; justify-content:flex-end; margin:12px 0 6px; }
.bubble-user {
    background:#f5c542; color:#0d0d0d; border-radius:18px 18px 4px 18px;
    padding:12px 18px; font-size:.97rem; font-weight:500; max-width:80%; line-height:1.55;
}

/* Assistant card */
.msg-asst { margin:6px 0 16px; display:block; width:100%; }
.msg-asst-row { display:block; width:100%; padding-left:44px; position:relative; box-sizing:border-box; }
.asst-avatar {
    position:absolute; left:0; top:2px;
    width:32px; height:32px; border-radius:8px;
    background:linear-gradient(135deg,#f5c542,#e6a800);
    display:flex; align-items:center; justify-content:center;
    font-size:.8rem; color:#0d0d0d; font-weight:700; font-family:'Space Mono',monospace;
}
.asst-card {
    display:block; width:100%; box-sizing:border-box;
    background:#141414; border:1px solid #1e1e1e; border-radius:4px 14px 14px 14px;
    padding:16px 18px; font-size:.97rem; line-height:1.8; color:#d4d4d4;
    overflow-wrap:break-word;
}
[data-testid="stMarkdownContainer"] { width:100% !important; max-width:100% !important; }

/* Markdown inside answer card */
.asst-card h1,.asst-card h2 { font-size:1.1rem; font-weight:700; color:#f0f0f0; margin:12px 0 5px; }
.asst-card h3,.asst-card h4 { font-size:1rem; font-weight:600; color:#e0e0e0; margin:10px 0 4px; }
.asst-card hr { border:none; border-top:1px solid #252525; margin:10px 0; }
.asst-card ul,.asst-card ol { padding-left:1.5rem; margin:5px 0; }
.asst-card li { margin:4px 0; font-size:.95rem; color:#d4d4d4; line-height:1.7; }
.asst-card strong { color:#f0f0f0; }
.asst-card em { color:#aaa; }
.asst-card code { background:#1a1a1a; padding:2px 6px; border-radius:4px; font-family:monospace; font-size:.85em; color:#f5c542; }
.asst-card p { margin:0 0 8px; }
.asst-card table { width:100%; border-collapse:collapse; margin:8px 0; font-size:.9rem; }
.asst-card th { background:#1e1e1e; color:#e0e0e0; padding:8px 12px; text-align:left; font-weight:600; border:1px solid #2a2a2a; }
.asst-card td { color:#c8c8c8; padding:7px 12px; border:1px solid #222; }
.asst-card tr:nth-child(even) td { background:#111; }
.asst-card blockquote { border-left:3px solid #f5c542; margin:8px 0; padding:6px 12px; background:#111; color:#999; font-size:.92rem; border-radius:0 6px 6px 0; }

/* Typing dots */
.tdots { display:flex; align-items:center; gap:5px; padding:8px 0 4px; }
.tdots span {
    width:8px; height:8px; border-radius:50%; background:#f5c542;
    animation:dp 1.2s ease-in-out infinite; opacity:.3;
}
.tdots span:nth-child(2){ animation-delay:.2s; }
.tdots span:nth-child(3){ animation-delay:.4s; }
@keyframes dp { 0%,80%,100%{opacity:.3;transform:scale(.85);} 40%{opacity:1;transform:scale(1.1);} }

/* Inline citation badge */
.cit-ref { position:relative; display:inline-block; }
.cit-ref summary {
    display:inline-flex; align-items:center; justify-content:center;
    width:20px; height:20px; background:#1e1800; border:1px solid #f5c54260;
    border-radius:5px; font-size:.72rem; font-weight:700; color:#f5c542;
    cursor:pointer; vertical-align:middle; margin:0 2px;
    list-style:none; transition:all .15s; font-family:monospace; user-select:none;
}
.cit-ref summary::-webkit-details-marker { display:none; }
.cit-ref summary:hover { background:#f5c542; color:#0d0d0d; box-shadow:0 0 8px rgba(245,197,66,.4); }
.cit-popup {
    position:absolute; bottom:calc(100% + 8px); left:50%; transform:translateX(-50%);
    width:340px; background:#111; border:1px solid #252525; border-radius:12px;
    padding:14px 16px; z-index:999;
    box-shadow:0 16px 48px rgba(0,0,0,.7), 0 0 0 1px #f5c54220;
    animation:pop-in .15s ease;
}
@keyframes pop-in { from{opacity:0;transform:translateX(-50%) translateY(6px);} to{opacity:1;transform:translateX(-50%) translateY(0);} }
.cit-popup-meta { display:flex; align-items:center; gap:7px; margin-bottom:8px; padding-bottom:8px; border-bottom:1px solid #1e1e1e; }
.cit-pill { display:inline-block; padding:3px 9px; border-radius:20px; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.4px; }
.cp-text  { background:#1a2d4a; color:#4a90d9; }
.cp-table { background:#0f2d1a; color:#4caf80; }
.cp-image { background:#2d1a0a; color:#e07a3a; }
.cit-popup-fname { font-size:.8rem; font-weight:600; color:#999; }
.cit-popup-page  { font-size:.74rem; color:#555; margin-left:auto; }
.cit-popup-text  { font-size:.82rem; color:#777; line-height:1.65; max-height:140px; overflow-y:auto; }
.cit-popup-text mark { background:rgba(245,197,66,.2); color:#f0f0f0; border-radius:3px; padding:0 2px; }

/* Source strip */
.src-strip { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; padding-top:12px; border-top:1px solid #1e1e1e; }
.src-chip { display:flex; align-items:center; gap:6px; background:#1a1a1a; border:1px solid #222; border-radius:20px; padding:4px 12px 4px 5px; font-size:.78rem; color:#777; }
.src-num { width:18px; height:18px; border-radius:4px; display:flex; align-items:center; justify-content:center; font-size:.68rem; font-weight:700; color:#0d0d0d; flex-shrink:0; font-family:monospace; }
.sn-text  { background:#4a90d9; }
.sn-table { background:#4caf80; }
.sn-image { background:#e07a3a; }
.src-fname { font-weight:500; color:#999; }

/* Warn / Info */
.warn-box { background:#1a1200; border:1px solid #3a2800; border-radius:7px; padding:9px 14px; font-size:.85rem; color:#b07828; margin-bottom:8px; }
.info-box  { background:#0a1220; border:1px solid #1a2840; border-radius:7px; padding:9px 14px; font-size:.85rem; color:#4a6a9a; }
.ok-txt   { font-size:.82rem; color:#4caf80; margin:4px 0; }
.err-txt  { font-size:.82rem; color:#e05050; margin:4px 0; }

/* Evidence expander */
.stExpander { background:#0e0e0e !important; border:1px solid #1e1e1e !important; border-radius:9px !important; margin-top:8px !important; }
.streamlit-expanderHeader { font-size:.88rem !important; color:#555 !important; background:transparent !important; padding:10px 14px !important; }
.streamlit-expanderHeader:hover { color:#888 !important; }
.ev-chunk { border:1px solid #1e1e1e; border-radius:8px; overflow:hidden; margin:8px 0; background:#0c0c0c; }
.ev-head { display:flex; align-items:center; gap:8px; padding:8px 13px; background:#0e0e0e; border-bottom:1px solid #181818; flex-wrap:wrap; }
.ev-fname { font-size:.82rem; color:#666; font-weight:500; }
.ev-page  { font-size:.78rem; color:#3a5a80; background:#0a1825; border:1px solid #1a2f40; border-radius:4px; padding:1px 7px; font-family:monospace; }
.ev-section { font-size:.74rem; color:#444; font-style:italic; margin-left:auto; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
/* Passage body — rendered markdown */
.ev-body { padding:13px 16px; font-size:.9rem; line-height:1.8; color:#bbb; }
.ev-body p { margin:0 0 8px; }
.ev-body h1,.ev-body h2 { font-size:.95rem; font-weight:700; color:#e0e0e0; margin:10px 0 5px; text-transform:none; letter-spacing:0; }
.ev-body h3,.ev-body h4 { font-size:.9rem; font-weight:600; color:#d0d0d0; margin:8px 0 4px; }
.ev-body strong { color:#e0e0e0; font-weight:600; }
.ev-body em { color:#aaa; font-style:italic; }
.ev-body ul,.ev-body ol { padding-left:1.4rem; margin:4px 0 8px; }
.ev-body li { margin:3px 0; color:#bbb; line-height:1.7; }
.ev-body blockquote { border-left:3px solid #333; padding:4px 10px; color:#888; margin:6px 0; }
.ev-body code { background:#1a1a1a; padding:1px 5px; border-radius:3px; font-family:monospace; font-size:.83em; color:#f5c542; }
/* Table in evidence — proper HTML table */
.ev-tbl-wrap { padding:12px 14px; overflow-x:auto; }
.ev-tbl-wrap table { width:100%; border-collapse:collapse; font-size:.88rem; }
.ev-tbl-wrap th { background:#111; color:#ccc; padding:8px 12px; text-align:left; font-weight:600; border:1px solid #222; }
.ev-tbl-wrap td { color:#bbb; padding:7px 12px; border:1px solid #1a1a1a; }
.ev-tbl-wrap tr:nth-child(even) td { background:#080808; }
.ev-tbl-wrap tr:hover td { background:#0f150f; color:#ddd; }
/* Image caption — plain readable text, not italic */
.ev-caption { padding:12px 16px 14px; font-size:.88rem; color:#aaa; line-height:1.8; border-top:1px solid #1a1a1a; }
.ev-caption p { margin:0 0 6px; }
.ev-caption strong { color:#ccc; font-weight:600; }
.ev-caption em { font-style:italic; color:#888; }
.ev-query-box { background:#080808; border:1px solid #181818; border-radius:8px; padding:10px 14px; margin-bottom:9px; font-family:monospace; font-size:.84rem; }
.ev-qlabel { color:#444; text-transform:uppercase; font-size:.72rem; letter-spacing:.6px; margin-bottom:5px; }
.ev-qitem  { color:#4a90d9; margin:3px 0; font-size:.86rem; }
.ev-qitem::before { content:"› "; color:#1e3a5a; }

/* Chat input */
.stChatInputContainer { background:#141414 !important; border:1px solid #252525 !important; border-radius:13px !important; }
.stChatInputContainer:focus-within { border-color:#f5c542 !important; box-shadow:0 0 0 2px rgba(245,197,66,.12) !important; }
.stChatInputContainer textarea { background:transparent !important; color:#e8e8e8 !important; font-size:.97rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Sound ─────────────────────────────────────────────────────────────────
def _sound(kind: str):
    pass  # audio disabled — st.html/components.html unstable on this Streamlit version


# ── Sample questions ──────────────────────────────────────────────────────
SAMPLE_QS = [
    "What must be done before starting the pump for the first time?",
    "What is the thread pitch for a standard M12 metric bolt?",
    "What safety pictograms appear on the hazard label?",
    "What PPE is needed when handling Chevron lubricant?",
    "If pump is ATEX 2G and installation is Zone 1, is this permitted?",
    "What is the max operating temperature with mechanical seal under T4?",
    "What does the pump operation sequence diagram show?",
    "Is Chevron ISO VG 220 safe at 95 °C for a T4 temperature class?",
]


# ── Helpers ───────────────────────────────────────────────────────────────
def _apply_keys(ak, ok):
    if ak: os.environ["ANTHROPIC_API_KEY"] = ak
    if ok: os.environ["OPENAI_API_KEY"]    = ok

def _validate(ak, ok):
    _apply_keys(ak, ok)
    if not ak and not ok: return False, "Enter at least one key."
    try:
        if ak:
            from anthropic import Anthropic
            Anthropic(api_key=ak).messages.create(model="claude-haiku-4-5-20251001",
                max_tokens=5, messages=[{"role":"user","content":"hi"}])
            return True, "Anthropic"
        from openai import OpenAI
        OpenAI(api_key=ok).chat.completions.create(model="gpt-4o-mini", max_tokens=5,
            messages=[{"role":"user","content":"hi"}])
        return True, "OpenAI"
    except Exception as e:
        m = str(e).lower()
        if "credit" in m or "quota" in m: return False, "Credits exhausted."
        if "invalid" in m or "401" in m:  return False, "Invalid API key."
        return False, str(e)[:80]

@st.cache_resource(show_spinner=False)
def _load_pipeline(ak, ok):
    _apply_keys(ak, ok)
    # Force CPU device BEFORE any torch/transformers imports
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from src.ingest.vectorstore import VectorStore
    from src.retrieval.retriever import Retriever
    vs = VectorStore()
    return Retriever(vs), vs

def _run(query, retriever, doc_type):
    from src.retrieval.adaptive_router import classify_query, answer_simple_query
    from src.retrieval.crag import score_chunks, filter_chunks
    from src.generation.generator import generate
    from configs.settings import USE_CRAG
    from src.guardrails.input_sanitizer import sanitize
    from src.observability.tracing import start_trace, end_trace
    query = sanitize(query)
    tracer = start_trace("rag_query", input=query)
    try:
        if classify_query(query) == "simple":
            answer = answer_simple_query(query)
            end_trace(tracer, output=answer, metadata={"query_type": "simple"})
            return answer, {"confidence":"high","sources":[],"all_chunks":[],"sub_queries":[query]}

        with tracer.span("retrieval", input=query) as s:
            raw = retriever.query(query, doc_type=doc_type)
            sub_q = raw[0].get("_all_sub_queries",[query]) if raw else [query]
            s.update(output={"chunks": len(raw), "sub_queries": sub_q})

        if USE_CRAG:
            with tracer.span("crag", input={"query": query, "chunks": len(raw)}) as s:
                scored      = score_chunks(query, raw)
                final, conf = filter_chunks(scored, is_multihop=len(sub_q)>1)
                s.update(output={"confidence": conf, "kept": len(final)})
        else:
            # Assign relevance field so _render() filtering works even without CRAG
            scored = [{**c, "relevance": "relevant", "crag_score": 1.0} for c in raw]
            final, conf = scored, "high"

        resp = generate(query, final, conf, retriever, tracer=tracer)
        end_trace(tracer, output=resp.answer, metadata={
            "confidence": resp.confidence,
            "self_rag": resp.self_rag_status,
            "retried": resp.retried,
            "sources": len(resp.sources),
        })
        logger.info("_run complete: answer=%d sources=%d chunks=%d", len(resp.answer), len(resp.sources), len(scored))
        return resp.answer, {"confidence":resp.confidence,"sources":resp.sources,
                             "all_chunks":scored,"sub_queries":sub_q}
    except Exception as e:
        end_trace(tracer, metadata={"error": str(e)})
        raise

def _dedup(sources):
    seen, out = set(), []
    for s in sources:
        k=(s.get("filename"),s.get("page"),s.get("chunk_type"))
        if k not in seen: seen.add(k); out.append(s)
    return out

def _highlight(chunk_text, answer):
    sentences = re.split(r'(?<=[.!?])\s+', chunk_text)
    al = answer.lower()
    out = []
    for s in sentences:
        w = " ".join(s.split()[:6]).lower()
        out.append(f"<mark>{s}</mark>" if len(w)>15 and w in al else s)
    return " ".join(out)

def _pill_cls(ct): return {"text":"cp-text","table":"cp-table","image":"cp-image"}.get(ct,"cp-text")
def _num_cls(ct):  return {"text":"sn-text","table":"sn-table","image":"sn-image"}.get(ct,"sn-text")
def _icon(ct):     return {"text":"📝","table":"📊","image":"🖼️"}.get(ct,"📄")
def _label(ct):    return {"text":"Passage","table":"Table","image":"Figure"}.get(ct,ct)

PDF_DIR = Path(__file__).parent / "data"

def _render_pdf_page(filename: str, page_num: int, dpi: int = 150) -> bytes | None:
    """Render a PDF page to PNG bytes."""
    import fitz
    pdf_path = PDF_DIR / filename
    if not pdf_path.exists():
        return None
    try:
        doc = fitz.open(str(pdf_path))
        idx = max(0, int(page_num) - 1)
        if idx >= len(doc):
            idx = len(doc) - 1
        pg  = doc.load_page(idx)
        pix = pg.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        doc.close()
        return pix.tobytes("png")
    except Exception as e:
        logger.warning("PDF page render failed for %s p.%s: %s", filename, page_num, e)
        return None


# ── Render answer ─────────────────────────────────────────────────────────
def _render(answer, meta):
    logger.info("_render: sources=%d all_chunks=%d sub_qs=%d conf=%s",
                len(meta.get("sources",[])), len(meta.get("all_chunks",[])),
                len(meta.get("sub_queries",[])), meta.get("confidence","?"))
    sources   = _dedup(meta.get("sources",[]))
    all_chks  = meta.get("all_chunks",[])
    sub_qs    = meta.get("sub_queries",[])
    conf      = meta.get("confidence","high")
    kept      = [c for c in all_chks if c.get("relevance") in ("relevant","ambiguous")]
    # For low-confidence answers show top-5 searched chunks so user sees what was tried
    if not kept and all_chks:
        kept = sorted(all_chks, key=lambda c: c.get("rrf_score", 0), reverse=True)[:5]
    n         = len(sources)
    logger.info("_render: kept=%d sources=%d", len(kept), n)

    # Build inline citation HTML per source
    def _badge(i, src):
        ct    = src.get("chunk_type","text")
        page  = src.get("page","?")
        fname = src.get("filename","")
        short = fname if len(fname)<=28 else fname[:25]+"…"
        # Find chunk content
        content = ""
        for c in kept:
            if c.get("chunk_type")==ct and c.get("page")==page:
                content = c.get("parent_content",c.get("content",""))
                if content and "\n" in content: content=content.split("\n",1)[1]
                break
        hl      = _highlight(content[:600], answer) if content else ""
        pc      = _pill_cls(ct)
        preview = hl or "<em style='color:#333'>No preview.</em>"
        return f"""<details class='cit-ref'><summary>{i}</summary>
<div class='cit-popup'>
  <div class='cit-popup-meta'>
    <span class='cit-pill {pc}'>{_icon(ct)} {_label(ct)}</span>
    <span class='cit-popup-fname'>{short}</span>
    <span class='cit-popup-page'>p.{page}</span>
  </div>
  <div class='cit-popup-text'>{preview}</div>
</div></details>"""

    # Place citation tokens [[N]] directly after sentences containing "(Source: ...)"
    # so badges appear right at the cited fact, not at paragraph end.
    def _inject_citations(text, sources):
        if not sources:
            return text
        result = text
        used = set()
        for i, src in enumerate(sources, 1):
            fname = src.get("filename","")
            page  = src.get("page","")
            # Match "(Source: filename, Page N)" patterns and replace with token after them
            pat = re.compile(
                r'(\(Source:[^)]*' + re.escape(fname.replace(".pdf","")) + r'[^)]*\))',
                re.IGNORECASE
            )
            def replacer(m, token=f"[[{i}]]"):
                if i not in used:
                    used.add(i)
                    return m.group(0) + token
                return m.group(0)
            result = pat.sub(replacer, result)
        # Any unused citations → append at end of first real paragraph
        for i, src in enumerate(sources, 1):
            if i not in used:
                paras2 = result.split("\n\n")
                for pi, p in enumerate(paras2):
                    if p.strip() and not p.strip().startswith("#"):
                        paras2[pi] = p.rstrip() + f"[[{i}]]"
                        used.add(i); break
                result = "\n\n".join(paras2)
        return result

    logger.info("_render: injecting citations")
    injected = _inject_citations(answer.strip(), sources)
    logger.info("_render: converting to HTML")
    ans_html  = md_lib.markdown(injected, extensions=["extra", "nl2br"])
    for i, src in enumerate(sources, 1):
        ans_html = ans_html.replace(f"[[{i}]]", _badge(i, src))

    logger.info("_render: building source strip")
    chips = ""
    for i, s in enumerate(sources, 1):
        ct=s.get("chunk_type","text"); page=s.get("page","?")
        fname=s.get("filename",""); short=fname if len(fname)<=28 else fname[:25]+"…"
        chips += f"""<div class='src-chip'><div class='src-num {_num_cls(ct)}'>{i}</div>
<span class='src-fname'>{_icon(ct)} {short}</span><span style='color:#333'>p.{page}</span></div>"""
    src_block = f"<div class='src-strip'>{chips}</div>" if chips else ""
    warn      = "<div class='warn-box'>⚠ Couldn't find a precise match — answer may be partial.</div>" if conf=="low" else ""

    logger.info("_render: writing answer card to Streamlit")
    st.markdown(f"""<div class='msg-asst'>
  <div class='msg-asst-row'>
    <div class='asst-avatar'>E</div>
    <div class='asst-card'>{warn}<div>{ans_html}</div>{src_block}</div>
  </div>
</div>""", unsafe_allow_html=True)
    logger.info("_render: answer card written OK")

    # Evidence expander
    if kept or sub_qs:
        logger.info("_render: opening evidence expander with %d chunks", len(kept))
        with st.expander("🔍  View retrieved evidence"):
            if sub_qs:
                rows="".join(f"<div class='ev-qitem'>{q}</div>" for q in sub_qs)
                st.markdown(f"<div class='ev-query-box'><div class='ev-qlabel'>Queries sent to knowledge base</div>{rows}</div>",
                            unsafe_allow_html=True)
            for ci, chunk in enumerate(kept):
                ct    = chunk.get("chunk_type","text")
                fname = chunk.get("filename","unknown")
                page  = chunk.get("page","?")
                logger.info("_render: chunk %d type=%s fname=%s page=%s", ci, ct, fname, page)
                raw   = chunk.get("parent_content", chunk.get("content",""))
                lines = raw.strip().split("\n", 1)
                content = lines[1].strip() if len(lines)>1 and lines[0].startswith("[") else raw.strip()
                content = content.replace("---PAGE_BREAK---", "").replace("\n\n\n", "\n\n").strip()
                short   = fname if len(fname)<=32 else fname[:29]+"…"
                section = chunk.get("section","") or ""
                pc      = _pill_cls(ct)
                icon    = _icon(ct)
                lbl     = _label(ct)
                sec_tag = f"<span class='ev-section'>{section[:60]}</span>" if section else ""

                st.markdown(
                    f"<div class='ev-chunk-open'>"
                    f"<div class='ev-head'>"
                    f"<span class='cit-pill {pc}'>{icon} {lbl}</span>"
                    f"<span class='ev-fname'>{short}</span>"
                    f"<span class='ev-page'>p.{page}</span>"
                    f"{sec_tag}</div>",
                    unsafe_allow_html=True
                )

                if ct == "image":
                    path = chunk.get("image_path","")
                    logger.info("_render: image chunk path=%s exists=%s", path, Path(path).exists() if path else False)
                    if path and Path(path).exists():
                        st.image(str(Path(path)), width=320)
                    if content.strip():
                        st.markdown(f"<div class='ev-caption'>{content}</div>", unsafe_allow_html=True)

                elif ct == "table":
                    tbl_html = md_lib.markdown(content, extensions=["extra", "tables"])
                    st.markdown(f"<div class='ev-tbl-wrap'>{tbl_html}</div>", unsafe_allow_html=True)

                else:
                    body_html = md_lib.markdown(content, extensions=["extra", "nl2br"])
                    st.markdown(f"<div class='ev-body'>{body_html}</div>", unsafe_allow_html=True)

                logger.info("_render: chunk %d content written", ci)
                st.caption(f"📄 {fname} • Page {page}")

                st.markdown("</div>", unsafe_allow_html=True)
                logger.info("_render: chunk %d done", ci)

    # Render PDF source pages outside the expander (st.image inside expander is unstable)
    rendered_pages = set()
    for chunk in kept:
        fname = chunk.get("filename", "unknown")
        page  = chunk.get("page")
        if fname and page and fname != "unknown" and (fname, page) not in rendered_pages:
            rendered_pages.add((fname, page))
            try:
                img_arr = _render_pdf_page(fname, page, dpi=150)
                if img_arr is not None:
                    st.caption(f"📄 Source page: {fname} • p.{page}")
                    st.image(img_arr)
                    logger.info("_render: PDF page rendered %s p.%s", fname, page)
            except Exception as e:
                logger.error("PDF render failed %s p.%s: %s", fname, page, e, exc_info=True)

    logger.info("_render: completed")


# ── Session init ──────────────────────────────────────────────────────────
for k,v in [("connected",False),("connect_msg",""),("provider",""),
            ("ak",""),("ok",""),("messages",[])]:
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.ak: st.session_state.ak=os.getenv("ANTHROPIC_API_KEY","")
if not st.session_state.ok: st.session_state.ok=os.getenv("OPENAI_API_KEY","")

# Auto-connect when keys are present in .env (or SKIP_AUTH=1)
if not st.session_state.connected:
    _ak = st.session_state.ak; _ok = st.session_state.ok
    if _ak or _ok:
        _apply_keys(_ak, _ok)
        st.session_state.connected = True
        st.session_state.provider  = "Anthropic" if _ak else "OpenAI"

# ── Nav ───────────────────────────────────────────────────────────────────
nd = "ndot-on" if st.session_state.connected else "ndot-off"
st.markdown(f"""<div class='nav-bar'>
  <div><div class='nav-title'>Engineering RAG: <span>Ask your documents</span></div>
       <div class='nav-by'>Presented by <b>kamal</b></div></div>
  <div class='nav-dot-wrap'><div class='ndot {nd}'></div>
       {"Connected · "+st.session_state.provider if st.session_state.connected else "Not connected"}</div>
</div>""", unsafe_allow_html=True)

# ── API key gate ──────────────────────────────────────────────────────────
if not st.session_state.connected:
    st.markdown("""<div class='key-gate'>
<div class='key-gate-title'>Connect your API key</div>
<div class='key-gate-sub'>Enter your <strong style='color:#e8e8e8'>OpenAI</strong> or <strong style='color:#e8e8e8'>Anthropic</strong> key to get started.<br>Your key lives only in this session and is never stored.</div>
</div>""", unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("<div class='key-hint'>OpenAI · <code>platform.openai.com</code><br>Format: <code>sk-proj-…</code></div>", unsafe_allow_html=True)
        ok_in = st.text_input("OpenAI key", type="password", placeholder="sk-proj-…",
                               value=st.session_state.ok, label_visibility="collapsed")
    with c2:
        st.markdown("<div class='key-hint'>Anthropic · <code>console.anthropic.com</code><br>Format: <code>sk-ant-api03-…</code></div>", unsafe_allow_html=True)
        ak_in = st.text_input("Anthropic key", type="password", placeholder="sk-ant-api03-…",
                               value=st.session_state.ak, label_visibility="collapsed")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    go = st.button("Connect →", width="stretch", type="primary")

    if st.session_state.connect_msg:
        st.markdown(f"<div class='err-txt' style='text-align:center'>{st.session_state.connect_msg}</div>", unsafe_allow_html=True)

    if go:
        with st.spinner("Verifying…"):
            ok_conn, msg = _validate(ak_in, ok_in)
        if ok_conn:
            st.session_state.connected=True; st.session_state.provider=msg
            st.session_state.ak=ak_in; st.session_state.ok=ok_in
            st.session_state.connect_msg=""
            st.cache_resource.clear(); st.rerun()
        else:
            st.session_state.connect_msg=msg; st.rerun()
    st.stop()

# ── Load pipeline ─────────────────────────────────────────────────────────
db_ok=False; retriever=None
try:
    retriever, vs = _load_pipeline(st.session_state.ak, st.session_state.ok)
    stats=vs.get_stats(); db_ok=True
    by_t=stats.get("chunks_by_type",{}); total=stats.get("total_chunks",0); docs=stats.get("documents",0)
    st.markdown(f"""<div class='db-row'>
<div class='db-chip'><b>{docs}</b> docs</div>
<div class='db-chip'><b>{by_t.get("text",0)}</b> passages</div>
<div class='db-chip'><b>{by_t.get("table",0)}</b> tables</div>
<div class='db-chip'><b>{by_t.get("image",0)}</b> figures</div>
<div class='db-chip'><b>{total:,}</b> total</div>
</div>""", unsafe_allow_html=True)
except Exception as e:
    st.markdown(f"<div class='warn-box'>Knowledge base unavailable: {e}</div>", unsafe_allow_html=True)

if not db_ok: st.stop()

# Doc filter + clear
cf, cc = st.columns([3,1])
with cf:
    doc_filter=st.selectbox("Filter documents",["All documents","Pump Manual","Safety Data Sheet","Machinery's Handbook"],label_visibility="collapsed")
with cc:
    st.markdown("<div class='btn-g'>", unsafe_allow_html=True)
    if st.button("✕ Clear", width="stretch"): st.session_state.messages=[]; st.rerun()  # noqa: rerun safe here (no LLM call)
    st.markdown("</div>", unsafe_allow_html=True)
doc_type={"All documents":None,"Pump Manual":"manual","Safety Data Sheet":"sds","Machinery's Handbook":"other"}[doc_filter]

# ── Hero + samples ────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""<div class='hero'>
<div class='hero-title'>Ask about engineering</div>
<div class='hero-sub'>Powered by RAG over pump manuals, safety data sheets, and technical handbooks.
Answers are grounded in your documents with clickable citations.</div>
</div>""", unsafe_allow_html=True)
    cols=st.columns(2)
    for i,q in enumerate(SAMPLE_QS):
        with cols[i%2]:
            st.markdown("<div class='sq-card'>", unsafe_allow_html=True)
            if st.button(q, key=f"sq_{i}", width="stretch"):
                st.session_state["pending_q"]=q; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ── Chat history ──────────────────────────────────────────────────────────
msgs=st.session_state.messages; i=0
while i<len(msgs):
    if msgs[i]["role"]=="user":
        q=msgs[i]["content"]
        st.markdown(f"<div class='msg-user'><div class='bubble-user'>{q}</div></div>", unsafe_allow_html=True)
        if i+1<len(msgs) and msgs[i+1]["role"]=="assistant":
            try:
                _render(msgs[i+1]["content"], msgs[i+1].get("meta",{}))
            except Exception as e:
                logger.error("_render failed for history message: %s", e, exc_info=True)
                st.error(f"Could not render answer: {e}")
            i+=2
        else: i+=1
    else: i+=1

# ── Input ─────────────────────────────────────────────────────────────────
pending=st.session_state.pop("pending_q",None)
typed  =st.chat_input("Ask anything about your engineering documents…")
active =pending or typed

if active:
    st.session_state.messages.append({"role":"user","content":active})
    st.markdown(f"<div class='msg-user'><div class='bubble-user'>{active}</div></div>", unsafe_allow_html=True)

    _sound("typing")
    slot=st.empty()
    slot.markdown("""<div class='msg-asst'>
  <div class='msg-asst-row'>
    <div class='asst-avatar'>E</div>
    <div class='asst-card'><div class='tdots'><span></span><span></span><span></span></div></div>
  </div>
</div>""", unsafe_allow_html=True)

    try:
        answer, meta = _run(active, retriever, doc_type)
    except Exception as e:
        answer=f"Something went wrong: {e}"
        meta={"confidence":"low","sources":[],"all_chunks":[],"sub_queries":[]}

    slot.empty()
    _sound("done")
    logger.info("Appending answer to session and rendering")
    st.session_state.messages.append({"role":"assistant","content":answer,"meta":meta})
    # Render inline — avoids st.rerun() which is unstable on Python 3.14
    try:
        logger.info("Calling _render")
        _render(answer, meta)
        logger.info("_render completed successfully")
    except Exception as e:
        logger.error("_render failed: %s", e, exc_info=True)
        st.error(f"Could not render answer: {e}")
