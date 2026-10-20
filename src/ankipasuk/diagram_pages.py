"""The diagram view as a document: pesuqim drawn as their diagrams (see
:mod:`ankipasuk.diagram`), saved as HTML or PDF to read from or print.

The diagrams are drawn by the app itself (``snapshotDiagrams`` in
``webgui/static/diagram.js``), at the width of the page's text block
(:func:`content_width_px`), and arrive here already drawn: text, brackets
and labels, nothing left for a script to do. This wraps them in a page with
the STAM font and the app's own diagram styles, laid out by the page
options (:func:`page_options`): paper, margins, spacing, and what to show
around the diagrams. The HTML carries the font inside it, so the file works
anywhere and prints as it shows; on screen it looks like the sheet it
prints on, which is also how the app's print preview shows it. The PDF is
rendered from the same page with WeasyPrint, the optional dependency the
'ammud pages use too (see :mod:`ankipasuk.ammud_pages`).
"""

from __future__ import annotations

import base64
import tempfile
from html import escape
from pathlib import Path

from .cache import SefariaCache
from .tikkun import get_font_base64

FONT_FAMILY = "ShlomosemiStam"

PAPER_MM = {"A4": (210, 297), "Letter": (215.9, 279.4)}

DEFAULT_OPTIONS = {
    "paper": "A4",
    "orientation": "portrait",  # or "landscape"
    "margin_mm": 15,
    "spacing_px": 8,  # above and below each pasuq
    "references": True,  # "Bereshit 1:1" over each pasuq
    "separators": True,  # a thin line between pesuqim
    "header": True,  # the title, subtitle and legend
    "bw": False,  # black and white (the drawing itself is done in the app)
    "grey": True,  # whether the drawing has the grey brackets (for the legend)
}

_DIAGRAM_CSS = (Path(__file__).parent / "webgui" / "static" / "diagram.css").read_text(encoding="utf-8")

PASUQ_START = '<div class="dg-pasuq">'

# How many pesuqim WeasyPrint lays out at a time: a whole book in one go
# takes more memory than a desktop has.
PDF_CHUNK = 150

_MM_TO_PX = 96 / 25.4  # CSS's 96px to the inch


def page_options(raw: dict | None = None) -> dict:
    """:data:`DEFAULT_OPTIONS` with ``raw``'s values where they're valid,
    so whatever the page sends, the result can be laid out."""
    o = dict(DEFAULT_OPTIONS)
    raw = raw or {}
    if raw.get("paper") in PAPER_MM:
        o["paper"] = raw["paper"]
    if raw.get("orientation") in ("portrait", "landscape"):
        o["orientation"] = raw["orientation"]
    for key, low, high in (("margin_mm", 5, 40), ("spacing_px", 0, 60)):
        try:
            o[key] = min(high, max(low, float(raw[key])))
        except (KeyError, TypeError, ValueError):
            pass
    for key in ("references", "separators", "header", "bw", "grey"):
        if key in raw:
            o[key] = bool(raw[key])
    return o


def paper_mm(o: dict) -> tuple[float, float]:
    """The sheet's width and height in mm, turned for landscape."""
    w, h = PAPER_MM[o["paper"]]
    return (h, w) if o["orientation"] == "landscape" else (w, h)


def content_width_px(options: dict | None = None) -> int:
    """The width of the text block, between the margins, in CSS px: what
    the app draws the diagrams at (A4 portrait, 15mm margins: 680px)."""
    o = page_options(options)
    return int((paper_mm(o)[0] - 2 * o["margin_mm"]) * _MM_TO_PX)


def _legend(bw: bool, grey: bool) -> str:
    if bw:
        swatches = [("white", "#222", "a card's division"), ("white", "#aaa", "not a card")]
    else:
        swatches = [
            ("#fff9c4", "#f9a825", "rank 1"), ("#bbdefb", "#1976d2", "2"), ("#c8e6c9", "#388e3c", "3"),
            ("#f8bbd0", "#c2185b", "4"), ("white", "#b8b8b8", "not a card"),
        ]
    if not grey:
        swatches = swatches[:-1]
    return '<span class="legend">' + "".join(
        f'<span style="background:{bg};border-color:{border}"></span>{label}'
        for bg, border, label in swatches
    ) + "</span>"


def _page_css(o: dict) -> str:
    width, height = paper_mm(o)
    margin = f'{o["margin_mm"]:g}'
    css = f"""
@page {{ size: {width}mm {height}mm; margin: {margin}mm;
        @bottom-center {{ content: counter(page); font: 8pt sans-serif; color: #999; }} }}
body {{ margin: 0; background: white; color: #222; font-family: sans-serif; }}
@media screen {{
  html {{ background: #8d8d8d; }}
  body {{ box-sizing: border-box; width: {width}mm; min-height: {height}mm; padding: {margin}mm;
          margin: 16px auto; box-shadow: 0 1px 6px rgba(0, 0, 0, 0.35); }}
}}
h1 {{ font-size: 15pt; font-weight: 600; margin: 0 0 1mm; }}
.subtitle {{ font-size: 8.5pt; color: #777; margin: 0 0 5mm; }}
.legend {{ display: inline-block; margin-left: 6px; }}
.legend span {{ display: inline-block; width: 9px; height: 9px; border: 1px solid; margin: 0 2px 0 8px;
               vertical-align: -1px; }}
.dg-pasuq {{ break-inside: avoid; padding: {o["spacing_px"]:g}px 0; }}
.dg-unit {{ overflow: visible; }}
"""
    if not o["references"]:
        css += ".dg-ref { display: none; }\n"
    if not o["separators"]:
        css += ".dg-pasuq { border-bottom: none; }\n"
    return css


def diagram_document(
    body_html: str, title: str, subtitle: str, font_url: str, options: dict | None = None, *,
    header: bool = True, first_page: int = 1,
) -> str:
    """A complete HTML document of the drawn diagrams ``body_html``, laid
    out by ``options`` (see :func:`page_options`), under ``title`` and
    ``subtitle`` (unless ``header`` is false, or the options leave it out),
    with the font at ``font_url``, its pages numbered from ``first_page``."""
    o = page_options(options)
    # Black and white is diagram.css's dg-bw, for the whole page.
    body_class = ' class="dg-bw"' if o["bw"] else ""
    # The reset is the number the page itself shows (WeasyPrint).
    numbering = f"@page :first {{ counter-reset: page {first_page}; }}" if first_page > 1 else ""
    head = (
        f"<h1>{escape(title, quote=False)}</h1>"
        f'<p class="subtitle">{escape(subtitle, quote=False)}{_legend(o["bw"], o["grey"])}</p>'
    ) if header and o["header"] else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title, quote=False)}</title><style>"
        f'@font-face {{ font-family: "{FONT_FAMILY}"; src: url("{font_url}") format("truetype"); }}'
        f"{_DIAGRAM_CSS}{_page_css(o)}{numbering}</style></head><body{body_class}>"
        f"{head}{body_html}</body></html>"
    )


def chunks(body_html: str, size: int) -> list[str]:
    """``body_html`` cut into runs of ``size`` pesuqim, each whole."""
    pesuqim = [PASUQ_START + p for p in body_html.split(PASUQ_START)[1:]]
    if not pesuqim:
        return [body_html]
    return ["".join(pesuqim[i:i + size]) for i in range(0, len(pesuqim), size)]


def diagrams_html(
    body_html: str, title: str, subtitle: str, cache: SefariaCache, options: dict | None = None,
) -> str:
    """:func:`diagram_document` with the font embedded: for saving as HTML,
    and for the print preview."""
    font_url = f"data:font/ttf;base64,{get_font_base64(cache)}"
    return diagram_document(body_html, title, subtitle, font_url, options)


def write_pdf(
    body_html: str, title: str, subtitle: str, cache: SefariaCache, path: str | Path,
    options: dict | None = None,
) -> int:
    """Render the diagrams to a PDF at ``path``, and return how many pages
    it has. Raises RuntimeError if WeasyPrint isn't installed."""
    try:
        import weasyprint
    except ImportError as e:
        raise RuntimeError(
            'PDF export needs WeasyPrint. Install it with: pip install "ankipasuk[pdf]" '
            "(with pipx: pipx inject ankipasuk weasyprint). HTML export works without it."
        ) from e
    # WeasyPrint loads the font from a file more reliably than from a data URI.
    with tempfile.TemporaryDirectory() as tmp:
        font = Path(tmp) / "stam.ttf"
        font.write_bytes(base64.b64decode(get_font_base64(cache)))
        # A chunk of pesuqim at a time, the pages then joined into one
        # document, numbered on from the chunk before.
        documents = []
        pages = 0
        for i, chunk in enumerate(chunks(body_html, PDF_CHUNK)):
            html = diagram_document(
                chunk, title, subtitle, font.as_uri(), options, header=i == 0, first_page=pages + 1,
            )
            document = weasyprint.HTML(string=html, base_url=tmp).render()
            documents.append(document)
            pages += len(document.pages)
        whole = documents[0].copy([page for document in documents for page in document.pages])
        whole.write_pdf(str(path))
        return pages
