"""PDF Analyzer — CLI summary.

Usage:
    ./.venv/bin/python main.py <pdf_path>

For the visual interface:
    ./.venv/bin/streamlit run app.py
"""

import sys

import analyzer


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "file.pdf"
    data = analyzer.analyze_pdf(path)

    print(f"File: {path}  ({data['page_count']} pages)\n")

    # Font summary
    print("=" * 50)
    print("FONTS (by size)")
    print("=" * 50)
    print(f"{'Font':<28} {'Size':>7} {'Count':>7}")
    print("-" * 50)
    for f in data["font_summary"]:
        print(f"{f['font']:<28} {f['size']:>7} {f['count']:>7}")

    # Declared fonts (in the PDF's resources, rendered or not)
    declared = data.get("declared_fonts", [])
    if declared:
        print("\n" + "=" * 50)
        print("DECLARED FONTS (resources)")
        print("=" * 50)
        print(f"{'Font':<30} {'Type':<7} {'Emb':<4} {'Status':<14} Sizes")
        print("-" * 50)
        for d in declared:
            status = "rendered" if d["rendered"] else "DECLARED ONLY"
            sizes = ", ".join(str(s) for s in d["sizes"]) or "-"
            emb = "yes" if d["embedded"] else "no"
            print(f"{d['font']:<30} {d['type']:<7} {emb:<4} {status:<14} {sizes}")

    # Per-page block/table/size
    print("\n" + "=" * 50)
    print("PAGES")
    print("=" * 50)
    for p in data["pages"]:
        print(f"Page {p['number']}: "
              f"{p['width']['cm']}×{p['height']['cm']} cm, "
              f"{len(p['blocks'])} blocks, {len(p['tables'])} tables")

    # Color palette
    print("\n" + "=" * 50)
    print("COLORS")
    print("=" * 50)
    for c in data["color_palette"]:
        print(f"{c['color']}  —  {c['count']} spans")


if __name__ == "__main__":
    main()
