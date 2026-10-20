"""'Ammudim as pages: each 'ammud laid out as its sefer column, one per
page, saved as HTML or PDF -- for reading from, printing, or checking
against a sefer.

The column is the same markup the tiqqun cards and the main window's
scroll view use (:func:`ankipasuk.lpcg.render_scroll_html`), in the same
STAM font, sized so an 'ammud's 42 lines fill one A4 page, blank lines
between books included. The HTML
carries the font inside it, so the file works anywhere and prints a page
per 'ammud from a browser. The PDF is rendered from the same page with
WeasyPrint, an optional dependency (``pip install "ankipasuk[pdf]"``).
"""

from __future__ import annotations

import base64
import tempfile
from html import escape
from pathlib import Path

from .cache import SefariaCache
from .config import BOOK_HEBREW_NAMES
from .lpcg import SCROLL_CSS, render_scroll_html
from .tikkun import TOTAL_AMUDIM, get_amud_lines, get_book_for_page, get_book_verses_on_amud, get_font_base64

FONT_FAMILY = "ShlomosemiStam"

# SCROLL_CSS with its adjustable values fixed (WeasyPrint doesn't evaluate
# CSS variables inside calc()): 12.5pt at 1.32 lines fits 42 lines on A4.
_PAGE_CSS = SCROLL_CSS.replace("var(--ankipasuk-font-size, 16px)", "12.5pt").replace(
    "calc(130% * var(--ankipasuk-line-height-scale, 1))", "1.32"
) + f"""
@page {{ size: A4; margin: 16mm; }}
body {{ margin: 0; background: white; color: black; }}
.lines {{ font-family: "{FONT_FAMILY}", "SBL Hebrew", "Ezra SIL", "Noto Serif Hebrew", serif; }}
.ammud {{ break-after: page; padding: 0 0 8mm; }}
.ammud:last-child {{ break-after: auto; }}
.caption {{ font-family: sans-serif; font-size: 8pt; color: #888; text-align: center; margin-bottom: 4mm; }}
"""


def caption(ammud_num: int, cache: SefariaCache) -> str:
    """E.g. "Bereshit -- 'Ammud 1", or "Shemot–Vayyiqra -- 'Ammud 111" for
    an 'ammud where one book ends and the next begins."""
    books = list(dict.fromkeys(book for book, _ch, _vs in get_book_verses_on_amud(ammud_num, cache)))
    books = books or [get_book_for_page(ammud_num, cache)]
    return f"{'–'.join(BOOK_HEBREW_NAMES.get(b, b) for b in books)} — 'Ammud {ammud_num}"


def ammud_pages_html(ammudim: list[int], cache: SefariaCache, *, font_url: str | None = None) -> str:
    """A complete HTML document with each 'ammud in ``ammudim`` (once, in
    order) on its own page. The font is embedded as a data URI unless
    ``font_url`` points at a font file instead (the PDF export does that)."""
    unique = sorted({int(n) for n in ammudim})
    if not unique:
        raise ValueError("Choose at least one 'ammud.")
    for n in unique:
        if not 1 <= n <= TOTAL_AMUDIM:
            raise ValueError(f"'Ammud must be between 1 and {TOTAL_AMUDIM} (got {n}).")
    if font_url is None:
        font_url = f"data:font/ttf;base64,{get_font_base64(cache)}"
    sections = "".join(
        f'<section class="ammud"><div class="caption">{escape(caption(n, cache), quote=False)}</div>'
        f"{render_scroll_html(get_amud_lines(n, cache, keep_blank=True), scalable=False)}</section>"
        for n in unique
    )
    title = f"'Ammud {unique[0]}" if len(unique) == 1 else f"'Ammudim {unique[0]}–{unique[-1]}"
    return (
        '<!doctype html><html lang="he"><head><meta charset="utf-8">'
        f"<title>{escape(title, quote=False)}</title><style>"
        f'@font-face {{ font-family: "{FONT_FAMILY}"; src: url("{font_url}") format("truetype"); }}'
        f"{_PAGE_CSS}</style></head><body>{sections}</body></html>"
    )


def write_pdf(ammudim: list[int], cache: SefariaCache, path: str | Path) -> int:
    """Render the pages of :func:`ammud_pages_html` to a PDF at ``path``,
    and return how many pages it has. Raises RuntimeError if WeasyPrint
    isn't installed."""
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
        html = ammud_pages_html(ammudim, cache, font_url=font.as_uri())
        document = weasyprint.HTML(string=html, base_url=tmp).render()
        document.write_pdf(str(path))
        return len(document.pages)
