# PDF Analyzer

A visual tool for inspecting the typography of any PDF. Upload a file and see,
for every text block, its **font, size, style (bold/italic), margins
(cm / inch / pt), line spacing, color**, and any **tables** — all overlaid on a
rendered image of the page.

## Features

- **Annotated page render** — each text block is boxed on the page image; hover
  to see its font, size, margins and color.
- **Accurate font detection** — reports the font actually embedded in the PDF
  (weighted by character count, so a short label span never masks the real
  content font). Type3 outline fonts and generator font-substitutions are
  reported honestly as what they really are.
- **Measurements in three units** — every distance is shown in cm, inch and pt.
- **Tables** — detected via PyMuPDF, with row/column counts, cell contents and
  the fonts used inside.
- **Color palette** — every text color with a hex value and swatch.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 and upload a PDF.

## Command-line summary

```bash
python main.py path/to/file.pdf
```

## Tech

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF parsing, text/layout, table
  detection and page rendering.
- [Streamlit](https://streamlit.io/) — web interface.

The analysis engine ([analyzer.py](analyzer.py)) is UI-free and can be imported
on its own; [app.py](app.py) is the Streamlit interface and
[main.py](main.py) is a thin CLI.
