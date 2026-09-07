"""Fetches scroll-accurate line-layout data from the tikkun.io project
(https://github.com/akivajgordon/tikkun.io, MIT licensed).

Torah scribes follow a fixed, traditional line-by-line layout for each
column (amud) of a kosher Sefer Torah -- line breaks fall in specific
places regardless of verse or aliyah boundaries. tikkun.io has precomputed
that layout for the whole Torah and checked it in as static per-amud JSON
("pages" -- tikkun.io's own name for them, kept here for consistency with
its source; there are exactly 245 of them, the traditional total amud
count), plus a table of contents mapping every (book, chapter, verse) to
the page/line it starts on. This module fetches that data live (like
Sefaria data elsewhere in this project) and caches it locally via
:class:`~ankipasuk.cache.SefariaCache`, since it never changes.

tikkun.io itself never trims a physical scroll line at a verse or aliyah
boundary -- when an aliyah starts or ends mid-line, it just labels the
line, leaving the full line's text (which may include a few words from the
verse just before or after) intact. :func:`get_scroll_lines_for_range`
does the same: a returned line may carry a couple of words belonging to
the verse immediately before ``start`` or after ``end``, exactly as a real
practicing reader would see them positioned on the actual scroll.
"""

from __future__ import annotations

import base64
import re

import requests

from .cache import SefariaCache
from .config import REQUEST_TIMEOUT, TORAH_VERSE_COUNTS

TIKKUN_RAW_BASE = "https://raw.githubusercontent.com/akivajgordon/tikkun.io/master/src/data"

# The STAM-style (Torah scroll handwriting) font tikkun.io itself renders
# with -- "Shlomo semiStam" by Shlomo Orbach, SIL Open Font License, so
# freely redistributable. Fetched live (not vendored) like everything else
# here, and pushed into the user's own Anki collection as media -- see
# ankipasuk.anki_connect.operations.ensure_media_file -- so cards render
# with it offline, the same way tikkun.io renders with it online.
FONT_RAW_URL = "https://raw.githubusercontent.com/akivajgordon/tikkun.io/master/assets/fonts/ShlomosemiStam.ttf"
FONT_ANKI_FILENAME = "_ankipasuk_shlomosemistam.ttf"

# tikkun.io's table of contents numbers Torah books 1-5 in reading order --
# the same order TORAH_VERSE_COUNTS is already defined in.
TIKKUN_BOOK_NUMBERS = {book: i for i, book in enumerate(TORAH_VERSE_COUNTS, start=1)}

NUN_HAFUCHA = "׆"  # ׆ -- a rare editorial mark (around Numbers 10:35-36)


def _fetch_json(url: str):
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Network/API error while fetching {url}: {e}") from e
    except ValueError as e:
        raise RuntimeError(f"Invalid JSON returned from {url}.") from e


def get_font_base64(cache: SefariaCache) -> str:
    """The tikkun.io STAM font's bytes, base64-encoded -- ready to hand
    straight to AnkiConnect's ``storeMediaFile`` (which takes base64 data),
    fetched once and cached forever after."""
    cached = cache.get_tikkun_font()
    if cached is not None:
        return cached

    try:
        resp = requests.get(FONT_RAW_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Network error while fetching the STAM font: {e}") from e

    encoded = base64.b64encode(resp.content).decode("ascii")
    cache.set_tikkun_font(encoded)
    return encoded


def get_toc(cache: SefariaCache) -> dict:
    """The tikkun.io table of contents: ``toc[book][chapter][verse] ==
    {"p": page_number, "l": line_number}`` (all keys are strings, since
    this is straight off the wire as JSON), giving the page and 1-based
    line index within that page where each verse's text begins."""
    cached = cache.get_tikkun_toc()
    if cached is not None:
        return cached
    toc = _fetch_json(f"{TIKKUN_RAW_BASE}/tables-of-contents/torah.json")
    cache.set_tikkun_toc(toc)
    return toc


def get_page(page_num: int, cache: SefariaCache) -> list[dict]:
    """One amud's line data (tikkun.io's own term for it is "page" --
    ``page_num`` is 1-245, see :data:`TOTAL_AMUDIM`): a list of line
    entries, each ``{"text": [[fragment, ...], ...], "verses": [...],
    "aliyot": [...], "isPetucha": bool}``. ``text`` is a list of columns
    (almost always one -- a rare poetic layout aside, see _render_line),
    each a list of fragments -- more than one fragment in a column marks a
    setumah (mid-line paragraph gap)."""
    cached = cache.get_tikkun_page(page_num)
    if cached is not None:
        return cached
    page = _fetch_json(f"{TIKKUN_RAW_BASE}/pages/torah/{page_num}.json")
    cache.set_tikkun_page(page_num, page)
    return page


def scroll_plain_text(fragment: str) -> str:
    """Strip a tikkun.io text fragment down to bare, unvoweled block
    letters -- a direct port of tikkun.io's own ``text-filter.ts`` (the
    ``annotated: false`` branch, i.e. its own "nikud off" scroll view), so
    this always matches what tikkun.io itself would render.
    """
    text = fragment.replace("#(פ)", "")
    text = text.replace(f"({NUN_HAFUCHA})#", f"{NUN_HAFUCHA} ")
    text = text.replace(f"#({NUN_HAFUCHA})", f" {NUN_HAFUCHA}")
    text = text.replace("־", " ")
    text = re.sub(r"#\[.+?\]", " ", text)
    text = re.sub(rf"[^א-ת\s{NUN_HAFUCHA}]", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _render_line(entry: dict) -> dict | None:
    """Render one page-line entry into ``{"html": ..., "is_petucha": ...,
    "char_count": ...}``, using the same ``<div class="column"><span
    class="fragment">...</span></div>`` markup tikkun.io's own ``Line.ts``
    renders -- so the CSS in :mod:`ankipasuk.lpcg` (a port of tikkun.io's
    ``page.css``) can lay it out identically: a setumah (more than one
    fragment) spaced apart with a real gap instead of running its two
    halves together. Returns None if the line strips down to nothing (e.g.
    a stray punctuation-only fragment).

    ``char_count`` -- the line's total visible letter count, ignoring
    markup -- is what :func:`ankipasuk.lpcg.build_lpcg_fields` uses to pin
    every card in an aliyah to one shared, predetermined box width, rather
    than leaving it to the browser's own (cross-engine-inconsistent) table
    auto-layout to guess a width from HTML content.

    More than one column (a rare poetic layout, e.g. Ha'azinu) is
    approximated by simply rendering multiple ``.column`` divs -- side-by-
    side poetic layout is out of scope for a recitation flashcard.
    """
    column_htmls = []
    char_count = 0
    for column in entry["text"]:
        fragments = [scroll_plain_text(frag) for frag in column]
        fragments = [f for f in fragments if f]
        if not fragments:
            continue
        char_count += sum(len(f) for f in fragments)
        setuma_class = " setuma" if len(fragments) > 1 else ""
        spans = "".join(f'<span class="fragment{setuma_class}">{f}</span>' for f in fragments)
        column_htmls.append(f'<div class="column">{spans}</div>')

    if not column_htmls:
        return None
    return {
        "html": "".join(column_htmls),
        "is_petucha": bool(entry.get("isPetucha")),
        "char_count": char_count,
    }


def _next_ref(book: str, chapter: int, verse: int) -> tuple[int, int] | None:
    """The (chapter, verse) immediately after this one within ``book``, or
    None if this is that book's very last verse."""
    counts = TORAH_VERSE_COUNTS[book]
    if verse < counts[chapter - 1]:
        return (chapter, verse + 1)
    if chapter < len(counts):
        return (chapter + 1, 1)
    return None


def get_scroll_lines_for_range(
    book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int, cache: SefariaCache,
) -> list[dict]:
    """Return the scroll-accurate (unvoweled) lines spanning verses
    (start_ch, start_vs) through (end_ch, end_vs) inclusive, broken exactly
    where a real Torah scroll's column would break.

    Each line is ``{"html": ..., "is_petucha": ...}`` -- see
    :func:`ankipasuk.lpcg.build_lpcg_fields`, which accepts this shape
    directly and renders a petucha line unjustified (its text stops short
    of the line's end, exactly as on the actual scroll) and a setumah gap
    as real whitespace, instead of treating every line as an ordinary
    justified paragraph line.

    A returned line is always whole -- see the module docstring for why a
    boundary line may carry a few extra words from just outside the range.
    """
    if book not in TIKKUN_BOOK_NUMBERS:
        raise ValueError(f"No tikkun.io layout data for {book!r} (Torah only).")

    book_num = str(TIKKUN_BOOK_NUMBERS[book])
    toc = get_toc(cache)

    try:
        start_loc = toc[book_num][str(start_ch)][str(start_vs)]
        end_loc = toc[book_num][str(end_ch)][str(end_vs)]
    except KeyError as e:
        raise ValueError(
            f"{book} {start_ch}:{start_vs}-{end_ch}:{end_vs} not found in tikkun.io data."
        ) from e

    start_page, start_line = start_loc["p"], start_loc["l"]
    end_page = end_loc["p"]

    next_ref = _next_ref(book, end_ch, end_vs)
    end_line = None  # None == "through the end of the page"
    if next_ref is not None:
        next_loc = toc[book_num][str(next_ref[0])][str(next_ref[1])]
        if next_loc["p"] == end_page:
            # Usually the line just before the next verse starts -- but a
            # very short verse can share its start line with the verse
            # right after it, in which case that shared line must still
            # be included (never end before end_loc's own line).
            end_line = max(end_loc["l"], next_loc["l"] - 1)

    lines: list[dict] = []
    for page_num in range(start_page, end_page + 1):
        page = get_page(page_num, cache)
        from_l = start_line if page_num == start_page else 1
        to_l = end_line if (page_num == end_page and end_line is not None) else len(page)
        for entry in page[from_l - 1:to_l]:
            line = _render_line(entry)
            if line is not None:
                lines.append(line)

    return lines


# The traditional total column count for a Sefer Torah written to the
# widely-followed Chabad/Vilna Gaon layout -- and, not by coincidence,
# exactly how many page files tikkun.io's own data has (1-245): its
# "pages" are amudim, not chapters, even though early Genesis happens to
# have one chapter per amud (misleading if read too quickly).
TOTAL_AMUDIM = 245


def get_book_for_page(page_num: int, cache: SefariaCache) -> str:
    """Which of the 5 Torah books amud ``page_num`` falls in.

    A kosher Sefer Torah always starts each of the 5 books (Chumashim) at
    the top of a fresh column -- so an amud can never straddle two books,
    and this always has a single unambiguous answer.
    """
    if not (1 <= page_num <= TOTAL_AMUDIM):
        raise ValueError(f"Amud must be between 1 and {TOTAL_AMUDIM} (got {page_num}).")

    toc = get_toc(cache)
    for book, book_num in TIKKUN_BOOK_NUMBERS.items():
        counts = TORAH_VERSE_COUNTS[book]
        last_ch, last_vs = len(counts), counts[-1]
        last_page = toc[str(book_num)][str(last_ch)][str(last_vs)]["p"]
        if page_num <= last_page:
            return book

    raise ValueError(f"Amud {page_num} is out of range (Torah has {TOTAL_AMUDIM} amudim).")


def get_amud_lines(amud_num: int, cache: SefariaCache) -> list[dict]:
    """Every scroll-accurate line on amud ``amud_num`` (1-245), in the
    same ``{"html": ..., "is_petucha": ..., "char_count": ...}`` shape as
    :func:`get_scroll_lines_for_range` -- see that function's docstring
    for what each field means. Unlike a verse/aliyah range, this needs no
    slicing at all: an amud already *is* tikkun.io's own per-page unit
    (see :func:`get_page`), so the whole page's lines are returned as-is.
    """
    if not (1 <= amud_num <= TOTAL_AMUDIM):
        raise ValueError(f"Amud must be between 1 and {TOTAL_AMUDIM} (got {amud_num}).")

    page = get_page(amud_num, cache)
    lines = []
    for entry in page:
        line = _render_line(entry)
        if line is not None:
            lines.append(line)
    return lines
