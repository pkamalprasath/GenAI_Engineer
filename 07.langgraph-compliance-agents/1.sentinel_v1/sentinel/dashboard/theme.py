"""CSS theme — enterprise design system for SENTINEL."""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Reset ──────────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Design tokens ──────────────────────────────────────────────────────────── */
:root {
  --font:      'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --fs-xs:     12px;
  --fs-sm:     13px;
  --fs-base:   14px;
  --fs-md:     15px;
  --fs-lg:     17px;
  --fs-xl:     21px;
  --fs-2xl:    28px;
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --border:    #e2e8f0;
  --bg-card:   #ffffff;
  --bg-page:   #f0f2f5;
  --bg-muted:  #f8fafc;
  --text-1:    #0f172a;
  --text-2:    #334155;
  --text-3:    #64748b;
  --text-4:    #94a3b8;
  --green:     #10b981;
  --green-dk:  #059669;
  --green-bg:  #ecfdf5;
  --green-bd:  #a7f3d0;
  --red:       #ef4444;
  --red-dk:    #dc2626;
  --amber:     #f59e0b;
  --blue:      #3b82f6;
  --blue-dk:   #1d4ed8;
  --purple:    #7c3aed;
}

/* ── Base ───────────────────────────────────────────────────────────────────── */
.stApp {
    background: var(--bg-page);
    color: var(--text-1);
    font-family: var(--font);
    font-size: var(--fs-base);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}

/* ── Hide Streamlit chrome ──────────────────────────────────────────────────── */
header[data-testid="stHeader"]  { display: none !important; }
[data-testid="stToolbar"]        { display: none !important; }
#MainMenu                        { visibility: hidden; }
footer                           { visibility: hidden; }

/* ── Block container ────────────────────────────────────────────────────────── */
.main .block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1300px !important;
    margin: 0 auto !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none !important;
    min-width: 230px !important;
    transform: none !important;
    visibility: visible !important;
    display: block !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    background: #0f172a !important;
    color: #94a3b8 !important;
}
[data-testid="stSidebar"] .stMarkdown p { color: #94a3b8; font-size: var(--fs-sm); }
hr { border-color: rgba(255,255,255,0.08) !important; margin: 0.75rem 0 !important; }

/* ── Typography ─────────────────────────────────────────────────────────────── */
h1 {
    font-size: var(--fs-2xl) !important;
    font-weight: 800 !important;
    color: var(--text-1) !important;
    letter-spacing: -0.5px !important;
    line-height: 1.25 !important;
    margin-bottom: 8px !important;
    font-family: var(--font) !important;
}
h2 {
    font-size: var(--fs-xl) !important;
    font-weight: 700 !important;
    color: var(--text-2) !important;
    letter-spacing: -0.3px !important;
    font-family: var(--font) !important;
}
h3 {
    font-size: var(--fs-lg) !important;
    font-weight: 600 !important;
    color: var(--text-2) !important;
    font-family: var(--font) !important;
}
p { color: var(--text-3); font-size: var(--fs-md); }
label {
    font-size: var(--fs-sm) !important;
    font-weight: 600 !important;
    color: var(--text-2) !important;
    letter-spacing: 0.1px !important;
}

/* ── Page header ────────────────────────────────────────────────────────────── */
.page-header {
    padding-bottom: 20px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border);
}
.page-header p { font-size: var(--fs-md); color: var(--text-3); margin-top: 4px; }

/* ── Navigation cards (home page) — equal height grid ───────────────────────── */
.nav-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px 22px 20px;
    min-height: 210px;
    height: 100%;
    display: flex;
    flex-direction: column;
    transition: box-shadow 0.15s, border-color 0.15s, transform 0.1s;
    cursor: pointer;
}
.nav-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.09);
    border-color: #cbd5e1;
    transform: translateY(-2px);
}
.nav-card-title {
    font-size: var(--fs-lg);
    font-weight: 700;
    color: var(--text-1);
    margin-bottom: 10px;
    font-family: var(--font);
}
.nav-card-desc {
    font-size: var(--fs-base);
    color: var(--text-3);
    line-height: 1.55;
    flex: 1;
}
.nav-card-btn {
    margin-top: auto;
    padding-top: 14px;
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--green-dk);
    letter-spacing: 0.1px;
}

/* ── Generic card ───────────────────────────────────────────────────────────── */
.s-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px 22px;
    transition: box-shadow 0.15s, border-color 0.15s;
}
.s-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-color: #cbd5e1; }
.s-card-label { font-size: 11px; font-weight: 700; color: var(--text-4); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }
.s-card-title { font-size: var(--fs-lg); font-weight: 700; color: var(--text-1); margin-bottom: 8px; }
.s-card-desc  { font-size: var(--fs-base); color: var(--text-3); line-height: 1.55; }

/* ── Metric cards ───────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    padding: 16px 18px !important;
}
[data-testid="stMetricLabel"] {
    font-size: var(--fs-xs) !important;
    font-weight: 700 !important;
    color: var(--text-4) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
}
[data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 800 !important;
    color: var(--text-1) !important;
    letter-spacing: -0.4px !important;
    font-family: var(--font) !important;
}

/* ── Buttons ────────────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, var(--green) 0%, var(--green-dk) 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 10px 22px !important;
    font-size: var(--fs-base) !important;
    font-weight: 600 !important;
    font-family: var(--font) !important;
    letter-spacing: 0.1px !important;
    transition: opacity 0.15s, transform 0.1s !important;
    box-shadow: 0 2px 8px rgba(16,185,129,0.28) !important;
    width: 100% !important;
}
.stButton > button:hover  { opacity: 0.92 !important; transform: translateY(-1px) !important; }
.stButton > button:active { transform: translateY(0) !important; }

/* ── Form inputs ────────────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-muted) !important;
    border: 1.5px solid var(--border) !important;
    color: var(--text-1) !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font) !important;
    font-size: var(--fs-base) !important;
    padding: 9px 12px !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--green) !important;
    box-shadow: 0 0 0 3px rgba(16,185,129,0.12) !important;
    background: #ffffff !important;
    outline: none !important;
}
.stSelectbox > div > div {
    background: var(--bg-muted) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-1) !important;
    font-size: var(--fs-base) !important;
}

/* ── Alerts ─────────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
    font-size: var(--fs-base) !important;
    border-left-width: 3px !important;
    font-family: var(--font) !important;
}

/* ── Expanders ──────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    margin-bottom: 10px !important;
}
[data-testid="stExpander"] summary {
    font-size: var(--fs-base) !important;
    font-weight: 600 !important;
    color: var(--text-2) !important;
    font-family: var(--font) !important;
    padding: 12px 16px !important;
}

/* ── Divider ────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.08) !important; }
.main hr, .main [data-testid="stDivider"] { border-color: var(--border) !important; margin: 1.25rem 0 !important; }

/* ── Badges ─────────────────────────────────────────────────────────────────── */
.badge { display: inline-flex; align-items: center; padding: 3px 11px; border-radius: 20px; font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.2px; gap: 5px; font-family: var(--font); }
.badge-green  { background: var(--green-bg); color: #065f46; border: 1px solid var(--green-bd); }
.badge-red    { background: #fef2f2; color: #7f1d1d; border: 1px solid #fca5a5; }
.badge-yellow { background: #fffbeb; color: #78350f; border: 1px solid #fcd34d; }
.badge-blue   { background: #eff6ff; color: #1e3a8a; border: 1px solid #93c5fd; }
.badge-gray   { background: var(--bg-muted); color: #475569; border: 1px solid var(--border); }

/* ── PII warning ────────────────────────────────────────────────────────────── */
.pii-warning {
    background: #fffbeb; border: 1px solid #fcd34d; border-radius: var(--radius-sm);
    padding: 10px 14px; color: #92400e; font-size: var(--fs-base); margin: 8px 0;
    font-family: var(--font);
}

/* ── Report container (escalations) ─────────────────────────────────────────── */
.report-box {
    background: var(--bg-muted);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 20px 22px;
    max-height: 420px;
    overflow-y: auto;
    font-size: var(--fs-base);
    line-height: 1.75;
    font-family: var(--font);
}
.report-box h1, .report-box h2, .report-box h3 {
    color: var(--text-1) !important;
    font-family: var(--font) !important;
    margin-top: 12px !important;
    margin-bottom: 6px !important;
}
.report-box h1 { font-size: var(--fs-xl) !important; }
.report-box h2 { font-size: var(--fs-lg) !important; }
.report-box h3 { font-size: var(--fs-md) !important; }
.report-box p  { color: var(--text-2); font-size: var(--fs-base); }

/* ── Columns equal alignment ─────────────────────────────────────────────────── */
[data-testid="stHorizontalBlock"] { gap: 16px !important; align-items: flex-start !important; }

/* ── Form border reset ──────────────────────────────────────────────────────── */
[data-testid="stForm"] { border: none !important; padding: 0 !important; }

/* ── DataFrame ──────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: var(--radius-md) !important; overflow: hidden !important; }

/* ── Reduce vertical gap between markdown blocks ────────────────────────────── */
section[data-testid="stMain"] [data-testid="stMarkdown"] + [data-testid="stMarkdown"] {
    margin-top: -10px !important;
}

/* ── Keyframes ──────────────────────────────────────────────────────────────── */
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
@keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(1.6); } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
"""

NAV_PAGES = [
    ("/investigate", "Investigate"),
    ("/provenance",  "Provenance"),
    ("/escalations", "Escalations"),
    ("/analytics",   "Analytics"),
]


def render_sidebar_nav(st_module, current: str = "") -> None:
    """Render sidebar nav as plain HTML links — full color control, version-agnostic."""
    links_html = ""
    for url, label in NAV_PAGES:
        is_active = current and current.lower() in url
        bg  = "rgba(16,185,129,0.18)" if is_active else "rgba(255,255,255,0.07)"
        col = "#10b981" if is_active else "#e2e8f0"
        brd = "rgba(16,185,129,0.35)" if is_active else "rgba(255,255,255,0.10)"
        fw  = "700" if is_active else "500"
        links_html += (
            f'<a href="{url}" target="_self" style="display:block;text-decoration:none;'
            f'background:{bg};border:1px solid {brd};border-radius:8px;'
            f'padding:9px 14px;margin-bottom:5px;font-size:14px;font-weight:{fw};'
            f'color:{col};font-family:Inter,sans-serif;transition:background 0.15s;">'
            f'{label}</a>'
        )
    st_module.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        f'letter-spacing:0.8px;padding:2px 4px 8px;font-family:Inter,sans-serif;">Navigation</div>'
        f'{links_html}',
        unsafe_allow_html=True,
    )


PLOTLY_COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
PLOTLY_BG = "#ffffff"
PLOTLY_PAPER_BG = "#ffffff"
PLOTLY_FONT_COLOR = "#374151"
PLOTLY_GRID_COLOR = "#f1f5f9"


def plotly_layout(title: str = "") -> dict:
    return {
        "title": {
            "text": title,
            "font": {"color": "#0f172a", "size": 14, "family": "Inter, sans-serif"},
            "x": 0, "pad": {"l": 0},
        },
        "paper_bgcolor": PLOTLY_PAPER_BG,
        "plot_bgcolor":  PLOTLY_BG,
        "font": {"color": PLOTLY_FONT_COLOR, "family": "Inter, sans-serif", "size": 13},
        "xaxis": {
            "gridcolor": PLOTLY_GRID_COLOR, "linecolor": "#e2e8f0",
            "tickfont": {"size": 12, "color": "#64748b"}, "showgrid": True,
        },
        "yaxis": {
            "gridcolor": PLOTLY_GRID_COLOR, "linecolor": "#e2e8f0",
            "tickfont": {"size": 12, "color": "#64748b"}, "showgrid": True,
        },
        "margin": {"t": 44, "r": 20, "b": 48, "l": 56},
        "legend": {
            "font": {"size": 13, "color": "#374151"},
            "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
        },
        "hoverlabel": {
            "bgcolor": "#ffffff", "bordercolor": "#e2e8f0",
            "font": {"size": 13, "color": "#0f172a", "family": "Inter, sans-serif"},
        },
    }
