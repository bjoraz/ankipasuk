"""The diagram view as a document: pesuqim drawn as their diagrams (see
:mod:`ankipasuk.diagram`), saved as HTML or PDF to read from or print.

The diagrams are drawn by the app itself (``snapshotDiagrams`` in
``webgui/static/diagram.js``), at the width of an A4 page, and arrive here
already drawn: text, brackets and labels, nothing left for a script to do.
This wraps them in a page with the STAM font and the app's own diagram
styles. The HTML carries the font inside it, so the file works anywhere and
prints as it shows; the PDF is rendered from the same page with WeasyPrint,
the optional dependency the 'ammud pages use too (see
:mod:`ankipasuk.ammud_pages`).
"""

from __future__ import annotations

import base64
import tempfile
from html import escape
from pathlib import Path

from .cache import SefariaCache
from .tikkun import get_font_base64

FONT_FAMILY = "ShlomosemiStam"

# The width the diagrams are drawn at: A4 less the page margins below
# (210mm - 2 x 15mm = 180mm, at CSS's 96px to the inch).
PAGE_WIDTH_PX = 680

_DIAGRAM_CSS = (Path(__file__).parent / "webgui" / "static" / "diagram.css").read_text(encoding="utf-8")

_PAGE_CSS = """
@page { size: A4; margin: 15mm;
        @bottom-center { content: counter(page); font: 8pt sans-serif; color: #999; } }
body { margin: 0; background: white; color: #222; font-family: sans-serif; }
@media screen { body { width: 680px; margin: 24px auto; } }
h1 { font-size: 15pt; font-weight: 600; margin: 0 0 1mm; }
.subtitle { font-size: 8.5pt; color: #777; margin: 0 0 5mm; }
.legend { display: inline-block; margin-left: 6px; }
.legend span { display: inline-block; width: 9px; height: 9px; border: 1px solid; margin: 0 2px 0 8px;
               vertical-align: -1px; }
.dg-pasuq { break-inside: avoid; }
.dg-unit { overflow: visible; }
"""

_LEGEND = (
    '<span class="legend">'
    '<span style="background:#fff9c4;border-color:#f9a825"></span>rank 1'
    '<span style="background:#bbdefb;border-color:#1976d2"></span>2'
    '<span style="background:#c8e6c9;border-color:#388e3c"></span>3'
    '<span style="background:#f8bbd0;border-color:#c2185b"></span>4'
    '<span style="background:white;border-color:#b8b8b8"></span>not a card'
    "</span>"
)


PASUQ_START = '<div class="dg-pasuq">'

# How many pesuqim WeasyPrint lays out at a time: a whole book in one go
# takes more memory than a desktop has.
PDF_CHUNK = 150


def diagram_document(
    body_html: str, title: str, subtitle: str, font_url: str, *, header: bool = True, first_page: int = 1,
) -> str:
    """A complete HTML document of the drawn diagrams ``body_html``, under
    ``title`` and ``subtitle`` (unless ``header`` is false), with the font
    at ``font_url``, its pages numbered from ``first_page``."""
    # The reset is the number the page itself shows (WeasyPrint).
    numbering = f"@page :first {{ counter-reset: page {first_page}; }}" if first_page > 1 else ""
    head = (
        f"<h1>{escape(title, quote=False)}</h1>"
        f'<p class="subtitle">{escape(subtitle, quote=False)}{_LEGEND}</p>'
    ) if header else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title, quote=False)}</title><style>"
        f'@font-face {{ font-family: "{FONT_FAMILY}"; src: url("{font_url}") format("truetype"); }}'
        f"{_DIAGRAM_CSS}{_PAGE_CSS}{numbering}</style></head><body>"
        f"{head}{body_html}</body></html>"
    )


def chunks(body_html: str, size: int) -> list[str]:
    """``body_html`` cut into runs of ``size`` pesuqim, each whole."""
    pesuqim = [PASUQ_START + p for p in body_html.split(PASUQ_START)[1:]]
    if not pesuqim:
        return [body_html]
    return ["".join(pesuqim[i:i + size]) for i in range(0, len(pesuqim), size)]


def diagrams_html(body_html: str, title: str, subtitle: str, cache: SefariaCache) -> str:
    """:func:`diagram_document` with the font embedded, for saving as HTML."""
    return diagram_document(body_html, title, subtitle, f"data:font/ttf;base64,{get_font_base64(cache)}")


def write_pdf(body_html: str, title: str, subtitle: str, cache: SefariaCache, path: str | Path) -> int:
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
                chunk, title, subtitle, font.as_uri(), header=i == 0, first_page=pages + 1,
            )
            document = weasyprint.HTML(string=html, base_url=tmp).render()
            documents.append(document)
            pages += len(document.pages)
        whole = documents[0].copy([page for document in documents for page in document.pages])
        whole.write_pdf(str(path))
        return pages
