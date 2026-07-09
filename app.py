"""PDF Analyzer — Streamlit visual interface.

Run:  ./.venv/bin/streamlit run app.py
"""

import html

import pandas as pd
import streamlit as st

import analyzer

st.set_page_config(page_title="PDF Analyzer — Typography Inspector",
                   layout="wide", page_icon="◐")

# --- Design system (type-specimen aesthetic: warm paper, ink, pen-blue) ---
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --paper:#FAF8F4; --surface:#FFFFFF; --ink:#1C1A17; --muted:#6B655C;
  --accent:#2E4A7B; --accent-soft:#EAEEF6; --hairline:#E7E2D8;
  --serif:'Fraunces',Georgia,serif; --sans:'Inter',-apple-system,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,monospace;
}

/* Base */
html, body, [class*="css"], .stApp { font-family: var(--sans); color: var(--ink); }
.stApp { background: var(--paper); }
.block-container { padding-top: 2.9rem; max-width: 1400px; }
/* Tighten global vertical rhythm */
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .7rem; }
hr { margin: .5rem 0 !important; }

/* Headings in the display serif */
h1, h2, h3, h4 { font-family: var(--serif); color: var(--ink); letter-spacing:-.01em; }
h1 { font-weight:600; } h2, h3 { font-weight:500; }

/* Custom header band */
.pa-header { border-bottom:1px solid var(--hairline); padding:0 0 .5rem; margin-bottom:.7rem; }
.pa-eyebrow { font-family:var(--mono); font-size:.72rem; letter-spacing:.22em;
  text-transform:uppercase; color:var(--accent); font-weight:500; }
.pa-title { font-family:var(--serif); font-weight:600; font-size:2.5rem; line-height:1.05;
  margin:.28rem 0 .35rem; color:var(--ink); }
.pa-title .dim { color:var(--muted); font-weight:400; }
.pa-sub { color:var(--muted); font-size:.95rem; max-width:60ch; }
.pa-file { font-family:var(--mono); font-size:.8rem; color:var(--accent);
  background:var(--accent-soft); padding:.15rem .5rem; border-radius:5px; }

/* Metric cards */
[data-testid="stMetric"] { background:var(--surface); border:1px solid var(--hairline);
  border-radius:12px; padding:1rem 1.1rem; box-shadow:0 1px 2px rgba(28,26,23,.03); }
[data-testid="stMetricLabel"] { font-family:var(--mono); font-size:.68rem !important;
  letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
[data-testid="stMetricValue"] { font-family:var(--serif); font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink); }
[data-testid="stMetricDelta"] { font-family:var(--mono); font-size:.75rem; }

/* Sidebar as a control panel */
[data-testid="stSidebar"] { background:var(--surface); border-right:1px solid var(--hairline); }
[data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] label { color:var(--ink); }

/* Expanders as specimen cards */
[data-testid="stExpander"] { border:1px solid var(--hairline) !important; border-radius:10px !important;
  background:var(--surface); margin-bottom:.5rem; box-shadow:none; }
[data-testid="stExpander"] summary { font-family:var(--mono); font-size:.85rem; }
[data-testid="stExpander"] summary:hover { color:var(--accent); }

/* Tabs — this Streamlit build uses data-testid=stTab / role=tablist */
[data-testid="stTabs"] [role="tablist"] { gap:1.6rem; border-bottom:1px solid var(--hairline); }
[data-testid="stTab"] { padding:.55rem .1rem; }
[data-testid="stTab"] [data-testid="stMarkdownContainer"] p {
  font-size:1.4rem !important; font-weight:600 !important; color:var(--muted); }
[data-testid="stTab"][aria-selected="true"] [data-testid="stMarkdownContainer"] p { color:var(--accent); }
[data-testid="stTab"] [data-testid="stIconMaterial"] {
  font-size:1.75rem !important; margin-right:.4rem; vertical-align:-.28em; }

/* Tighten the stacked block cards on the right */
.stTabs [data-testid="stVerticalBlock"] { gap:.15rem; }
[data-testid="stExpander"] { margin-bottom:.15rem; }

/* Tables & code */
code, .stCode, pre { font-family:var(--mono) !important; }
[data-testid="stTable"], .stDataFrame { font-variant-numeric:tabular-nums; }
[data-testid="stDataFrame"] { border:1px solid var(--hairline); border-radius:8px; }

/* Captions */
[data-testid="stCaptionContainer"], .stCaption { color:var(--muted); }
hr { border-color:var(--hairline); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# Color palette for overlay boxes (assigned to blocks in order)
BOX_COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#008080", "#9a6324", "#800000", "#808000", "#000075",
    "#e07a5f", "#2a9d8f", "#e9c46a", "#264653", "#d62828",
]


def color_for(i: int) -> str:
    return BOX_COLORS[i % len(BOX_COLORS)]


def m3(m: dict) -> str:
    """Formats a {'pt','cm','inch'} dict as 'x.x cm / x.x in / x pt'."""
    if not m:
        return "—"
    return f"{m['cm']} cm / {m['inch']} in / {m['pt']} pt"


@st.cache_data(show_spinner="Analyzing PDF…")
def run_analysis(file_bytes: bytes, zoom: float) -> dict:
    """Analyzes the uploaded PDF straight from memory (cached, no temp file)."""
    return analyzer.analyze_pdf(file_bytes, zoom=zoom)


def render_overlay(page: dict, color_mode: str, show_boxes: bool, display_w: int):
    """Draws the rendered page image with positioned block boxes on top.

    Boxes are positioned in percentages relative to the page, so the whole
    view scales responsively to its column (never overflows) while staying
    perfectly aligned with the image.
    """
    pw, ph = page["width_pt"], page["height_pt"]  # page size in points

    # Color groups (consistent color by font/size)
    keys = []
    for b in page["blocks"]:
        if color_mode == "By font":
            keys.append(b["dominant_font"])
        elif color_mode == "By size":
            keys.append(b["dominant_size"])
        else:
            keys.append(None)
    uniq = {k: i for i, k in enumerate(dict.fromkeys(keys))}

    boxes = ""
    if show_boxes:
        for i, b in enumerate(page["blocks"]):
            x0, y0, x1, y1 = b["bbox"]
            left, top = x0 / pw * 100, y0 / ph * 100          # % of page
            w, h = (x1 - x0) / pw * 100, (y1 - y0) / ph * 100
            ci = uniq[keys[i]] if color_mode != "By block" else i
            col = color_for(ci)
            tip = (
                f"#{i + 1} | {b['dominant_font']} {b['dominant_size']}pt "
                f"{b['dominant_style']} | color {b['dominant_color']} | "
                f"left {b['margins']['left']['cm']}cm right {b['margins']['right']['cm']}cm"
            )
            label = f"{i + 1}"
            boxes += (
                f'<div title="{html.escape(tip)}" style="position:absolute;'
                f"left:{left:.2f}%;top:{top:.2f}%;width:{w:.2f}%;height:{h:.2f}%;"
                f"border:1.5px solid {col};background:{col}1a;box-sizing:border-box;"
                f'border-radius:2px;cursor:help;">'
                f'<span style="position:absolute;top:-9px;left:-2px;font-size:9px;'
                f"font-family:monospace;color:#fff;background:{col};padding:0 3px;"
                f'border-radius:2px;white-space:nowrap;">{label}</span></div>'
            )

    img = (
        f'<img src="data:image/png;base64,{page["image_png"]}" '
        f'style="width:100%;height:auto;display:block;" />'
    )
    # Container is responsive: fills its column but never exceeds display_w px.
    container = (
        f'<div style="position:relative;width:100%;max-width:{display_w}px;'
        f'box-shadow:0 2px 12px rgba(0,0,0,.25);">{img}{boxes}</div>'
    )
    st.markdown(container, unsafe_allow_html=True)


def color_chip(hexcol: str, size: int = 14) -> str:
    return (
        f'<span style="display:inline-block;width:{size}px;height:{size}px;'
        f"background:{hexcol};border:1px solid #8888;border-radius:3px;"
        f'vertical-align:middle;margin-right:6px;"></span>'
    )


def header(subtitle: str, file_name: str = ""):
    """Renders the type-specimen header band."""
    file_html = f'<span class="pa-file">{html.escape(file_name)}</span>' if file_name else ""
    st.markdown(
        f'<div class="pa-header">'
        f'<div class="pa-eyebrow">Typography &amp; Layout Inspector</div>'
        f'<div class="pa-title">PDF <span class="dim">Analyzer</span></div>'
        f'<div class="pa-sub">{subtitle} {file_html}</div>'
        f'</div>',
        unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.markdown(
    '<div class="pa-eyebrow" style="margin-bottom:.6rem;">Controls</div>',
    unsafe_allow_html=True)
uploaded = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
zoom = st.sidebar.slider("Render quality (zoom)", 1.0, 4.0, 2.0, 0.5)
display_w = st.sidebar.slider("Max image width (px)", 400, 1000, 700, 50)
show_boxes = st.sidebar.checkbox("Show block boxes", value=True)
color_mode = st.sidebar.radio(
    "Color by", ["By font", "By block", "By size"]
)

if uploaded is None:
    header("Upload a PDF to reveal the font, size, style, margins, spacing, "
           "color and tables behind every block of text.")
    st.info("Upload a PDF from the left to get started.")
    st.stop()

data = run_analysis(uploaded.getvalue(), zoom)

# Page selection
page_labels = [f"Page {p['number']}" for p in data["pages"]]
sel = st.sidebar.selectbox("Page", range(len(page_labels)),
                           format_func=lambda i: page_labels[i])
page = data["pages"][sel]

# ----------------------------------------------------------------------------
# Top metrics
# ----------------------------------------------------------------------------
header("Analysis of", uploaded.name)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Page size",
          f"{page['width']['cm']}×{page['height']['cm']} cm",
          f"{page['width']['inch']}×{page['height']['inch']} in")
c2.metric("Blocks", len(page["blocks"]))
c3.metric("Distinct fonts", len({(f['font'], f['size']) for f in data['font_summary']}))
c4.metric("Tables", len(page["tables"]))
c5.metric("Total pages", data["page_count"])

st.divider()

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("Annotated view")
    ls = page.get("line_spacing")
    ls_txt = f" · Typical line spacing: {ls['pt']} pt / {ls['cm']} cm" if ls else ""
    st.caption("Hover over a box to see its font, size, margins and color." + ls_txt)
    render_overlay(page, color_mode, show_boxes, display_w)

with right:
    tab_blocks, tab_fonts, tab_tables, tab_colors = st.tabs(
        [":material/view_agenda: Blocks", ":material/text_fields: Fonts",
         ":material/table_chart: Tables", ":material/palette: Colors"]
    )

    # --- Blocks ---
    with tab_blocks:
        st.caption(f"{len(page['blocks'])} text blocks")
        for i, b in enumerate(page["blocks"]):
            title = f"#{i + 1} · {b['dominant_font']} · {b['dominant_size']}pt · {b['dominant_style']}"
            with st.expander(title):
                st.markdown(
                    f"**Text:** {html.escape(b['text'][:200])}", unsafe_allow_html=True)
                st.markdown(
                    f"**Font / size / style:** {b['dominant_font']} · "
                    f"{b['dominant_size']} pt · {b['dominant_style']}")
                st.markdown(
                    f"**Color:** {color_chip(b['dominant_color'])} `{b['dominant_color']}`",
                    unsafe_allow_html=True)
                mtab = pd.DataFrame({
                    "Edge": ["Left", "Right", "Top", "Bottom"],
                    "cm": [b["margins"][k]["cm"] for k in ("left", "right", "top", "bottom")],
                    "inch": [b["margins"][k]["inch"] for k in ("left", "right", "top", "bottom")],
                    "pt": [b["margins"][k]["pt"] for k in ("left", "right", "top", "bottom")],
                })
                st.dataframe(mtab, hide_index=True, use_container_width=True)
                st.markdown(f"**Gap to previous block:** {m3(b['gap_before'])}")
                st.markdown(f"**Line spacing:** {m3(b['line_spacing'])}")
                if len(b["spans"]) > 1:
                    sdf = pd.DataFrame([
                        {"text": s["text"][:30], "font": s["font"],
                         "size": s["size"], "style": s["style"], "color": s["color"]}
                        for s in b["spans"]
                    ])
                    st.dataframe(sdf, hide_index=True, use_container_width=True)

    # --- Fonts ---
    with tab_fonts:
        fdf = pd.DataFrame(data["font_summary"]).rename(
            columns={"font": "Font", "size": "Size (pt)", "count": "Count"})
        st.dataframe(fdf, hide_index=True, use_container_width=True)

    # --- Tables ---
    with tab_tables:
        if not page["tables"]:
            st.info("No tables detected on this page.")
        for ti, t in enumerate(page["tables"]):
            st.markdown(f"**Table {ti + 1}** — {t['rows']} rows × {t['cols']} columns")
            st.caption(f"Position (pt): {t['bbox']}")
            if t["cells"]:
                st.dataframe(pd.DataFrame(t["cells"]), use_container_width=True)
            if t["fonts_inside"]:
                st.caption("Fonts inside:")
                st.dataframe(
                    pd.DataFrame(t["fonts_inside"]).rename(
                        columns={"font": "Font", "size": "Size", "count": "Count"}),
                    hide_index=True, use_container_width=True)
            st.divider()

    # --- Colors ---
    with tab_colors:
        st.caption(f"{len(data['color_palette'])} distinct text colors")
        for c in data["color_palette"]:
            st.markdown(
                f"{color_chip(c['color'], 18)} `{c['color']}` — {c['count']} spans",
                unsafe_allow_html=True)
