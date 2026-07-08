"""PDF analysis engine — UI-free, pure functions.

Opens a PDF and, for each text block, returns font, size, style, margins
(cm/inch/pt), gap between blocks, color and table info as a structured dict.
app.py (Streamlit) and main.py (CLI) both use this engine.
"""

import base64
from collections import Counter

import fitz  # PyMuPDF

# --- Unit conversions ---
PT_PER_INCH = 72.0
CM_PER_INCH = 2.54


def pt_to_inch(pt: float) -> float:
    return pt / PT_PER_INCH


def pt_to_cm(pt: float) -> float:
    return pt / PT_PER_INCH * CM_PER_INCH


def measure(pt: float) -> dict:
    """Returns a length in all three units at once."""
    return {
        "pt": round(pt, 1),
        "cm": round(pt_to_cm(pt), 2),
        "inch": round(pt_to_inch(pt), 2),
    }


def clean_font(name: str) -> str:
    """Strips the embedded subset prefix: 'ABCDEF+Arial' -> 'Arial'.

    Type3 fonts (embedded as drawing procedures) carry no usable name — e.g.
    'Type3 (33 0 R)' — so they get a friendly label instead.
    """
    if not name:
        return name
    if name.startswith("Type3"):
        return "Type3 (outline font, no name)"
    return name.split("+")[-1]


def color_to_hex(color: int) -> str:
    """Converts a PyMuPDF color integer to #RRGGBB."""
    return "#{:06X}".format(color & 0xFFFFFF)


def decode_flags(flags: int) -> dict:
    """Decodes the span['flags'] bitfield into readable styles."""
    return {
        "superscript": bool(flags & 1),
        "italic": bool(flags & 2),
        "serif": bool(flags & 4),
        "mono": bool(flags & 8),
        "bold": bool(flags & 16),
    }


# Only explicit "bold" style suffixes — NOT weight names like "black"/"heavy",
# which belong to distinct display families (e.g. Arial Black) and shouldn't be
# reported as a bold styling of a base font.
_BOLD_KEYWORDS = ("bold", "semibold", "demibold", "-bd")
_ITALIC_KEYWORDS = ("italic", "oblique", "-it")


def style_label(flags: int, font: str = "") -> str:
    """Short style label: 'Bold', 'Italic', 'Bold+Italic' or 'Normal'.

    Uses the PyMuPDF flags bitfield first; if a style is not flagged, falls
    back to keywords in the font name (e.g. 'Arial-BoldMT'). This catches
    Type3/substituted fonts whose flags don't carry style information.
    """
    f = decode_flags(flags)
    name = (font or "").lower()
    bold = f["bold"] or any(k in name for k in _BOLD_KEYWORDS)
    italic = f["italic"] or any(k in name for k in _ITALIC_KEYWORDS)
    parts = []
    if bold:
        parts.append("Bold")
    if italic:
        parts.append("Italic")
    return "+".join(parts) if parts else "Normal"


def _dominant(weighted):
    """Most representative value, weighted by character count.

    `weighted` is a list of (value, weight) pairs. Weighting by text length
    (not span count) matters because a line can mix a short label span in one
    font with a long content span in another — the content should win.
    """
    if not weighted:
        return None
    c = Counter()
    for value, weight in weighted:
        c[value] += weight
    return c.most_common(1)[0][0]


def _analyze_block(block: dict, page_rect: fitz.Rect, prev_bottom):
    """Measures a single text block."""
    x0, y0, x1, y1 = block["bbox"]

    spans_out = []
    fonts, sizes, colors, styles = [], [], [], []
    line_tops = []

    for line in block.get("lines", []):
        if line.get("spans"):
            line_tops.append(line["bbox"][1])
        for span in line["spans"]:
            text = span["text"]
            if not text.strip():
                continue
            font = clean_font(span["font"])
            size = round(span["size"], 1)
            hexcol = color_to_hex(span["color"])
            style = style_label(span["flags"], font)
            w = len(text.strip())  # weight by visible character count
            fonts.append((font, w))
            sizes.append((size, w))
            colors.append((hexcol, w))
            styles.append((style, w))
            spans_out.append({
                "text": text,
                "font": font,
                "size": size,
                "style": style,
                "color": hexcol,
                "bbox": [round(v, 1) for v in span["bbox"]],
            })

    # In-block line spacing: average gap between consecutive line top edges
    line_spacing = None
    if len(line_tops) > 1:
        diffs = [line_tops[i + 1] - line_tops[i] for i in range(len(line_tops) - 1)]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            line_spacing = measure(sum(diffs) / len(diffs))

    return {
        "bbox": [round(v, 1) for v in block["bbox"]],
        "text": " ".join(s["text"] for s in spans_out).strip(),
        "spans": spans_out,
        "dominant_font": _dominant(fonts),
        "dominant_size": _dominant(sizes),
        "dominant_color": _dominant(colors),
        "dominant_style": _dominant(styles) or "Normal",
        "margins": {
            "left": measure(x0),
            "right": measure(page_rect.width - x1),
            "top": measure(y0),
            "bottom": measure(page_rect.height - y1),
        },
        "gap_before": measure(y0 - prev_bottom) if prev_bottom is not None else None,
        "line_spacing": line_spacing,
    }


def _analyze_tables(page: fitz.Page, spans_xy):
    """Finds tables on the page and associates the fonts inside them.

    spans_xy: list of (cx, cy, font, size) tuples — span centers.
    """
    tables_out = []
    try:
        found = page.find_tables()
    except Exception:
        return tables_out

    for tab in found.tables:
        tx0, ty0, tx1, ty1 = tab.bbox
        try:
            cells = tab.extract()
        except Exception:
            cells = []

        # Fonts of spans whose center falls inside the table bbox
        inside = Counter()
        for cx, cy, font, size in spans_xy:
            if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                inside[(font, size)] += 1

        tables_out.append({
            "bbox": [round(v, 1) for v in tab.bbox],
            "rows": tab.row_count,
            "cols": tab.col_count,
            "cells": cells,
            "fonts_inside": [
                {"font": f, "size": s, "count": c}
                for (f, s), c in inside.most_common()
            ],
        })
    return tables_out


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _page_line_spacing(text_dict: dict):
    """Typical line spacing of a page, measured across block boundaries.

    Collects every text line's baseline and left edge, then takes the median
    gap between vertically consecutive lines that sit in the same column and
    are close enough to belong to the same paragraph. This still works when
    PyMuPDF splits a widely-spaced paragraph into single-line blocks.
    """
    lines = []  # (left_x, baseline_y, size)
    for block in text_dict["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            baseline = spans[0]["origin"][1]
            size = max(s["size"] for s in spans)
            lines.append((line["bbox"][0], baseline, size))

    lines.sort(key=lambda t: t[1])  # by vertical position
    gaps = []
    for i in range(len(lines) - 1):
        x0, y0, sz = lines[i]
        x1, y1, _ = lines[i + 1]
        dy = y1 - y0
        # Same column (similar left edge) and a plausible line-to-line gap
        if abs(x1 - x0) <= 3 and 0.3 * sz <= dy <= 3.5 * sz:
            gaps.append(dy)
    med = _median(gaps)
    return measure(med) if med else None


def analyze_pdf(source, zoom: float = 2.0) -> dict:
    """Fully analyzes a PDF and returns a structured dict.

    `source` is either a filesystem path (str) or the raw PDF bytes. Passing
    bytes opens the document straight from memory — no temp file is written,
    so nothing accumulates on disk when many users upload files.
    """
    if isinstance(source, (bytes, bytearray)):
        doc = fitz.open(stream=bytes(source), filetype="pdf")
        path = "<uploaded>"
    else:
        doc = fitz.open(source)
        path = source

    pages_out = []
    font_summary = Counter()
    color_palette = Counter()

    for page_num, page in enumerate(doc, start=1):
        rect = page.rect
        data = page.get_text("dict")

        blocks_out = []
        spans_xy = []  # for table association
        prev_bottom = None

        for block in data["blocks"]:
            if block.get("type") != 0:  # text blocks only
                continue
            has_text = any(
                sp["text"].strip()
                for ln in block.get("lines", [])
                for sp in ln["spans"]
            )
            if not has_text:
                continue

            b = _analyze_block(block, rect, prev_bottom)
            blocks_out.append(b)
            prev_bottom = block["bbox"][3]

            for sp in b["spans"]:
                font_summary[(sp["font"], sp["size"])] += 1
                color_palette[sp["color"]] += 1
                sx0, sy0, sx1, sy1 = sp["bbox"]
                spans_xy.append(((sx0 + sx1) / 2, (sy0 + sy1) / 2, sp["font"], sp["size"]))

        tables_out = _analyze_tables(page, spans_xy)

        # Render page → base64 PNG
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")

        pages_out.append({
            "number": page_num,
            "width": measure(rect.width),
            "height": measure(rect.height),
            "width_pt": rect.width,
            "height_pt": rect.height,
            "zoom": zoom,
            "image_png": img_b64,
            "img_w": pix.width,
            "img_h": pix.height,
            "line_spacing": _page_line_spacing(data),
            "blocks": blocks_out,
            "tables": tables_out,
        })

    result = {
        "path": path,
        "page_count": doc.page_count,
        "pages": pages_out,
        "font_summary": [
            {"font": f, "size": s, "count": c}
            for (f, s), c in sorted(font_summary.items(), key=lambda x: -x[0][1])
        ],
        "color_palette": [
            {"color": col, "count": c}
            for col, c in color_palette.most_common()
        ],
    }
    doc.close()
    return result
