"""Fetches scroll-accurate line-layout data from the tikkun.io project
(https://github.com/akivajgordon/tikkun.io, MIT licensed).

Tora scribes follow a fixed, traditional line-by-line layout for each
column ('ammud) of a sefer -- line breaks fall in specific
places regardless of verse or 'aliyya boundaries. tikkun.io has precomputed
that layout for the whole Tora and checked it in as static per-'ammud JSON
("pages" -- tikkun.io's own name for them, kept here for consistency with
its source; there are exactly 245 of them, the traditional total 'ammud
count), plus a table of contents mapping every (book, chapter, verse) to
the page/line it starts on. This module fetches that data live (like
Sefaria data elsewhere in this project) and caches it locally via
:class:`~ankipasuk.cache.SefariaCache`, since it never changes.

tikkun.io itself never trims a physical scroll line at a verse or 'aliyya
boundary -- when an 'aliyya starts or ends mid-line, it just labels the
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

# The STAM-style (sefer handwriting) font tikkun.io itself renders
# with -- "Shlomo semiStam" by Shlomo Orbach, SIL Open Font License, so
# freely redistributable. Fetched live (not vendored) like everything else
# here, and pushed into the user's own Anki collection as media -- see
# ankipasuk.anki_connect.operations.ensure_media_file -- so cards render
# with it offline, the same way tikkun.io renders with it online.
FONT_RAW_URL = "https://raw.githubusercontent.com/akivajgordon/tikkun.io/master/assets/fonts/ShlomosemiStam.ttf"
FONT_ANKI_FILENAME = "_ankipasuk_shlomosemistam.ttf"

# tikkun.io's table of contents numbers Tora books 1-5 in reading order --
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
    """One 'ammud's line data (tikkun.io's own term for it is "page" --
    ``page_num`` is 1-245, see :data:`TOTAL_AMUDIM`): a list of line
    entries, each ``{"text": [[fragment, ...], ...], "verses": [...],
    "aliyot": [...], "isPetucha": bool}``. ``text`` is a list of columns
    (almost always one -- a rare poetic layout aside, see _render_line),
    each a list of fragments -- more than one fragment in a column marks a
    setuma (mid-line paragraph gap)."""
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


def scroll_pointed_text(fragment: str) -> str:
    """Like :func:`scroll_plain_text`, but keeps niqqud/ta'amim and the
    maqaf character itself (as ``־``, not collapsed to a space) -- a
    direct port of tikkun.io's own ``text-filter.ts`` ``annotated: true``
    branch (its "nikud on" scroll view), used for a pointed-text
    tikkun-style display (see :mod:`ankipasuk.webgui.api`).

    Unlike :func:`scroll_plain_text`, this does NOT run a Hebrew-letter
    whitelist filter -- it only removes the petuḥa marker and resolves
    ketiv/qeri word annotations (a ``#`` inside a maqaf-separated word
    marks a ketiv/qeri correction; only the text AFTER the ``#`` -- the
    "read as" form -- is kept, matching a real Tikkun's own display), so
    punctuation like sof pasuq survives untouched, as real pointed Tora
    text should show it.
    """
    text = fragment.replace("#(פ)", "")
    text = text.replace(f"({NUN_HAFUCHA})#", f"{NUN_HAFUCHA} ")
    text = text.replace(f"#({NUN_HAFUCHA})", f" {NUN_HAFUCHA}")

    def _resolve(word: str) -> str:
        parts = word.split("#")
        return parts[0] if len(parts) <= 1 else ",".join(parts[1:])

    words = [
        "־".join(_resolve(w) for w in maqaf_word.split("־"))
        for maqaf_word in text.split(" ")
    ]
    text = " ".join(words)
    return text.replace("[", "{").replace("]", "}")


def _render_line(entry: dict, *, pointed: bool = False) -> dict | None:
    """Render one page-line entry into ``{"html": ..., "is_petucha": ...,
    "char_count": ...}``, using the same ``<div class="column"><span
    class="fragment">...</span></div>`` markup tikkun.io's own ``Line.ts``
    renders -- so the CSS in :mod:`ankipasuk.lpcg` (a port of tikkun.io's
    ``page.css``) can lay it out identically: a setuma (more than one
    fragment) spaced apart with a real gap instead of running its two
    halves together. Returns None if the line strips down to nothing (e.g.
    a stray punctuation-only fragment).

    ``pointed`` swaps the text filter from :func:`scroll_plain_text` to
    :func:`scroll_pointed_text` -- for the HTML content only.
    ``char_count`` -- the line's total visible letter count, ignoring
    markup -- always comes from the PLAIN filter regardless, even in
    pointed mode: niqqud and ta'amim stack on their base letter in a proper
    Hebrew rendering and add no horizontal width of their own, so
    counting their own Unicode codepoints here would overestimate how
    wide the line actually renders. This is what
    :func:`ankipasuk.lpcg.build_lpcg_fields` (and
    :func:`ankipasuk.lpcg.render_scroll_html`) use to pin every line in a
    range to one shared, predetermined box width, rather than leaving it
    to the browser's own (cross-engine-inconsistent) table auto-layout to
    guess a width from HTML content.

    More than one column (a rare poetic layout, e.g. Ha'azinu) is
    approximated by simply rendering multiple ``.column`` divs -- side-by-
    side poetic layout is out of scope for a recitation flashcard.
    """
    display_filter = scroll_pointed_text if pointed else scroll_plain_text
    column_htmls = []
    char_count = 0
    for column in entry["text"]:
        display_fragments = []
        plain_lengths = []
        for frag in column:
            display_text = display_filter(frag)
            if not display_text:
                continue
            display_fragments.append(display_text)
            plain_lengths.append(len(scroll_plain_text(frag)))
        if not display_fragments:
            continue
        char_count += sum(plain_lengths)
        setuma_class = " setuma" if len(display_fragments) > 1 else ""
        spans = "".join(f'<span class="fragment{setuma_class}">{f}</span>' for f in display_fragments)
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


def previous_verse_ref(book: str, chapter: int, verse: int) -> tuple[int, int] | None:
    """The (chapter, verse) immediately before this one within ``book``,
    or None if this is that book's very first verse -- the mirror image
    of :func:`_next_ref`. Public (not underscore-prefixed) because
    :mod:`ankipasuk.verse_cards` needs it too, to find the verse whose own
    tail might bleed onto a card range's own first row (see that
    module's docstring)."""
    if verse > 1:
        return (chapter, verse - 1)
    if chapter > 1:
        counts = TORAH_VERSE_COUNTS[book]
        return (chapter - 1, counts[chapter - 2])
    return None


def leading_verses_needing_alignment(
    book: str, chapter: int, verse: int, cache: SefariaCache,
) -> list[tuple[int, int]]:
    """Every verse from the nearest row that's GUARANTEED to start with
    no bleed from anything before it, up to but NOT including (chapter,
    verse) itself, in order -- the verses :mod:`ankipasuk.verse_cards`
    must prepend (with their own Sefaria word counts, purely for
    alignment) before a card range whose own first requested verse is
    (chapter, verse), so word-alignment can correctly separate every
    verse's own words. Empty if (chapter, verse) is itself already such
    a verse.

    Unlike the tail side (see :func:`get_row_fragments_for_range`'s own
    ``generous_tail``, always resolved by exactly the *one* very next
    verse), there is no fixed bound on how many verses deep this can go:
    (chapter, verse)'s own row can share leading words with the verse
    just before it, and THAT verse's own row can, in turn, share leading
    words with the verse before IT, and so on for as long as consecutive
    rows keep landing verse boundaries mid-fragment instead of at a
    fragment break (ordinary Tora text almost always does exactly this
    -- see that module's own docstring) -- e.g. the 'Aseret haDibberot's
    entire run of one-per-line "commandments" needs many verses' worth
    of this walk-back before reaching a safe starting point.

    A verse is safe to stop at once reached (i.e. does NOT itself need
    prepending) if it's the Tora's very first verse (nothing before it
    at all), or if its own row is NOT also the verse-just-before-it's own
    row (they don't share a row) AND the row immediately before its own
    row is a petuḥa (a paragraph genuinely ending there, leaving the
    rest of that row blank) -- either way, nothing can bleed onto it.
    Two verses sharing the exact same own-row (tikkun.io registers each
    verse's row independently, so a short verse and the one right after
    it can both be tagged to the very same row) is NEVER by itself a safe
    stopping point, regardless of page position -- the row being the very
    first row of its own page does NOT mean nothing precedes this verse
    ON that row (a sefer's own column boundaries don't
    align with verse boundaries, so an earlier verse's tail can still
    land there).
    """
    book_num = str(TIKKUN_BOOK_NUMBERS[book])
    toc = get_toc(cache)

    chain: list[tuple[int, int]] = []
    ch, vs = chapter, verse
    while True:
        prev_ref = previous_verse_ref(book, ch, vs)
        if prev_ref is None:
            break

        same_row = toc[book_num][str(prev_ref[0])][str(prev_ref[1])] == toc[book_num][str(ch)][str(vs)]
        if not same_row:
            preceding = _preceding_entry(book, ch, vs, cache)
            if preceding is None or preceding[0].get("isPetucha"):
                break

        chain.append(prev_ref)
        ch, vs = prev_ref

    chain.reverse()
    return chain


def _row_entries_for_range(
    book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int, cache: SefariaCache,
    *, generous_tail: bool = False,
) -> list[tuple[dict, int]]:
    """The raw tikkun.io page-line entries spanning verses (start_ch,
    start_vs) through (end_ch, end_vs) inclusive, each paired with its own
    'ammud (page) number -- the boundary-walking logic shared by
    :func:`get_scroll_lines_for_range` (renders each entry to HTML) and
    :func:`get_row_fragments_for_range` (extracts each entry's words) --
    see either's docstring for the boundary semantics (why a returned row
    may carry a few extra words from just outside the
    range).

    ``generous_tail`` controls how far the fetch extends past the end
    verse's own start row:

    - False (the default, used by row-anchored :func:`get_scroll_lines_for_range`):
      stop at the row just before the next verse's own start row, and
      never past the end verse's own starting PAGE -- unless the end
      verse's OWN start row is that same row (a very short verse sharing
      its start line with the verse right after it), in which case that
      shared row is still included.
    - True (used by word-anchored :func:`get_row_fragments_for_range`):
      always stop at the next verse's own start row itself, wherever
      that is -- even on a LATER page, when the end verse's own tail
      crosses an 'ammud boundary (a verse's length is fixed by its text,
      not by where a scribe's column happens to end). The False formula
      silently drops the end verse's own tail whenever that verse spans
      *more than one* row before reaching a row it shares with the next
      verse -- it only special-cases sharing on the end verse's own
      first row, not a later one, and never looks past the end verse's
      own starting page at all. A word-anchored caller can safely
      request the more generous bound: any harmless extra content it
      pulls in (an unshared row belongs entirely to the next, out-of-
      range verse) simply falls outside every requested verse's own word
      span and is discarded, whereas a row-anchored caller has no such
      built-in filter and must not over-fetch.
    """
    if book not in TIKKUN_BOOK_NUMBERS:
        raise ValueError(f"No tikkun.io layout data for {book!r} (Tora only).")

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
        if generous_tail:
            # Unlike the False branch below, this may push end_page past
            # the end verse's own starting page -- the whole point being
            # to never lose a tail that crosses an 'ammud boundary.
            end_page, end_line = next_loc["p"], next_loc["l"]
        elif next_loc["p"] == end_page:
            end_line = max(end_loc["l"], next_loc["l"] - 1)

    entries: list[tuple[dict, int]] = []
    for page_num in range(start_page, end_page + 1):
        page = get_page(page_num, cache)
        from_l = start_line if page_num == start_page else 1
        to_l = end_line if (page_num == end_page and end_line is not None) else len(page)
        entries.extend((entry, page_num) for entry in page[from_l - 1:to_l])

    return entries


def get_scroll_lines_for_range(
    book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int, cache: SefariaCache,
    *, pointed: bool = False,
) -> list[dict]:
    """Return the scroll-accurate lines spanning verses (start_ch,
    start_vs) through (end_ch, end_vs) inclusive, broken exactly where a
    real sefer's column would break -- unvoweled block letters by
    default, or full niqqud/ta'amim if ``pointed`` (see
    :func:`scroll_pointed_text`).

    Each line is ``{"html": ..., "is_petucha": ...}`` -- see
    :func:`ankipasuk.lpcg.build_lpcg_fields`, which accepts this shape
    directly and renders a petuḥa line unjustified (its text stops short
    of the line's end, exactly as on the actual scroll) and a setuma gap
    as real whitespace, instead of treating every line as an ordinary
    justified paragraph line.

    A returned line is always whole -- see the module docstring for why a
    boundary line may carry a few extra words from just outside the range.
    """
    entries = _row_entries_for_range(book, start_ch, start_vs, end_ch, end_vs, cache)
    lines: list[dict] = []
    for entry, _page_num in entries:
        line = _render_line(entry, pointed=pointed)
        if line is not None:
            lines.append(line)
    return lines


def _row_fragments(entry: dict, page_num: int) -> tuple[list[list[str]], bool, int]:
    """A page-line entry's own fragments (see :func:`get_page`), its
    petuḥa flag, and its own 'ammud (page) number -- the word-level
    counterpart to :func:`_render_line`, used by
    :mod:`ankipasuk.verse_cards` to align tikkun.io's own row text against
    Sefaria's per-verse word counts, to reproduce a setuma/poetic
    ("brick") gap's exact position when only part of a row is being
    rendered (see :func:`ankipasuk.verse_cards.segment_rows_by_verse`),
    AND to mark a real transition from one physical scroll column to the
    next when a verse's own content crosses an 'ammud boundary (see
    :func:`get_row_fragments_for_range`'s own docstring).

    Multiple COLUMNS (the rare side-by-side poetic layout, e.g. Ha'azinu)
    are flattened together in array order, same as :func:`_render_line`
    approximates them -- true side-by-side reading order is out of scope
    for a recitation flashcard either way (see that function's own
    docstring). Fragment boundaries *within* a column are real and always
    preserved, though: a poetic "brick" layout (e.g. Az Yashir/Shirat
    HaYam) uses that exact same multi-fragment mechanism to lay out
    several visually-gapped runs on one row, and can do so entirely
    *within* a single verse's own text -- not just at a setuma paragraph
    break -- so this must never collapse fragments into one flat run the
    way a mere word list would.
    """
    fragments: list[list[str]] = []
    for column in entry["text"]:
        for frag in column:
            words = scroll_plain_text(frag).split()
            if words:
                fragments.append(words)
    return fragments, bool(entry.get("isPetucha")), page_num


def get_row_fragments_for_range(
    book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int, cache: SefariaCache,
) -> list[tuple[list[list[str]], bool, int]]:
    """Like :func:`get_scroll_lines_for_range`, but each row is its own
    fragments (see :func:`_row_fragments`) instead of rendered HTML -- one
    ``(fragments, is_petucha, page_num)`` triple per row, in row order.
    Unlike that function, a row with zero fragments (would otherwise be
    dropped) is kept, so the result always has exactly one entry per
    physical row in range, keeping row indices meaningful to a caller
    correlating them against other row-indexed data.

    Fetches with ``generous_tail=True`` (see :func:`_row_entries_for_range`):
    the end verse's own tail can span more than one row -- even crossing
    onto a LATER 'ammud entirely -- before reaching a row it shares with
    the very next verse, which the row-anchored fetch's own tighter bound
    can silently drop. A word-precise caller can safely discard whatever
    harmless extra this pulls in (see that function's docstring), so it
    always requests the safe bound instead. ``page_num`` on each row
    lets :mod:`ankipasuk.verse_cards` notice and mark that crossing on
    the rendered card, rather than silently splicing the new column's
    lines onto the old one as if they were still the same column.
    """
    entries = _row_entries_for_range(
        book, start_ch, start_vs, end_ch, end_vs, cache, generous_tail=True,
    )
    return [_row_fragments(entry, page_num) for entry, page_num in entries]


def get_amud_row_fragments(amud_num: int, cache: SefariaCache) -> list[tuple[list[list[str]], bool, int]]:
    """Like :func:`get_amud_lines`, but each row is its own fragments
    (see :func:`_row_fragments`) instead of rendered HTML."""
    if not (1 <= amud_num <= TOTAL_AMUDIM):
        raise ValueError(f"'Ammud must be between 1 and {TOTAL_AMUDIM} (got {amud_num}).")
    return [_row_fragments(entry, amud_num) for entry in get_page(amud_num, cache)]


# The traditional total column count for a sefer written to the
# widely-followed Chabad/Vilna Gaon layout -- and, not by coincidence,
# exactly how many page files tikkun.io's own data has (1-245): its
# "pages" are 'ammudim, not chapters, even though early Genesis happens to
# have one chapter per 'ammud (misleading if read too quickly).
TOTAL_AMUDIM = 245


def get_book_for_page(page_num: int, cache: SefariaCache) -> str:
    """Which of the 5 Tora books 'ammud ``page_num`` falls in.

    A sefer always starts each of the 5 books (Ḥummashim) at
    the top of a fresh column -- so an 'ammud can never straddle two books,
    and this always has a single unambiguous answer.
    """
    if not (1 <= page_num <= TOTAL_AMUDIM):
        raise ValueError(f"'Ammud must be between 1 and {TOTAL_AMUDIM} (got {page_num}).")

    toc = get_toc(cache)
    for book, book_num in TIKKUN_BOOK_NUMBERS.items():
        counts = TORAH_VERSE_COUNTS[book]
        last_ch, last_vs = len(counts), counts[-1]
        last_page = toc[str(book_num)][str(last_ch)][str(last_vs)]["p"]
        if page_num <= last_page:
            return book

    raise ValueError(f"'Ammud {page_num} is out of range (the Tora has {TOTAL_AMUDIM} 'ammudim).")


def _preceding_entry(book: str, ch: int, vs: int, cache: SefariaCache) -> tuple[dict, int] | None:
    """The raw tikkun.io entry (and its own 'ammud/page number) for the row
    immediately before the row where verse (ch, vs) itself begins -- the
    fixed one-row lookback a verse-based recitation card uses (see
    :mod:`ankipasuk.verse_cards`). None if that row is the very first row
    of the Tora (Genesis 1:1's own first row), the one case with nothing
    to look back to.
    """
    if book not in TIKKUN_BOOK_NUMBERS:
        raise ValueError(f"No tikkun.io layout data for {book!r} (Tora only).")

    book_num = str(TIKKUN_BOOK_NUMBERS[book])
    toc = get_toc(cache)
    try:
        loc = toc[book_num][str(ch)][str(vs)]
    except KeyError as e:
        raise ValueError(f"{book} {ch}:{vs} not found in tikkun.io data.") from e

    page_num, line = loc["p"], loc["l"]
    if line > 1:
        return get_page(page_num, cache)[line - 2], page_num
    if page_num > 1:
        prev_page = get_page(page_num - 1, cache)
        if prev_page:
            return prev_page[-1], page_num - 1
    return None


def get_preceding_row(book: str, ch: int, vs: int, cache: SefariaCache) -> dict | None:
    """Like :func:`_preceding_entry`, rendered to HTML (see
    :func:`_render_line`)."""
    preceding = _preceding_entry(book, ch, vs, cache)
    return _render_line(preceding[0]) if preceding is not None else None


def get_preceding_row_fragments(
    book: str, ch: int, vs: int, cache: SefariaCache,
) -> tuple[list[list[str]], bool, int] | None:
    """Like :func:`_preceding_entry`, as its own fragments (see
    :func:`_row_fragments`)."""
    preceding = _preceding_entry(book, ch, vs, cache)
    return _row_fragments(*preceding) if preceding is not None else None


def get_verses_starting_on_amud(amud_num: int, cache: SefariaCache) -> list[tuple[int, int]]:
    """Every (chapter, verse) whose own first row is on 'ammud ``amud_num``,
    in row order -- i.e. exactly the verses a verse-based recitation card
    (see :mod:`ankipasuk.verse_cards`) should get its own card for when
    exporting this 'ammud.

    A verse whose OWN first row is on an earlier 'ammud (this 'ammud's first
    row merely continues it) is not included -- its card belongs to
    whichever 'ammud it actually starts on. That verse's tail end on this
    'ammud's first row still surfaces on-card, just as another verse's
    context row rather than its own card -- see the module docstring on
    row/verse-boundary overlap.
    """
    return [vs for vs, _row_index in get_verse_row_indices_on_amud(amud_num, cache)]


def get_verse_row_indices_on_amud(amud_num: int, cache: SefariaCache) -> list[tuple[tuple[int, int], int]]:
    """Like :func:`get_verses_starting_on_amud`, but each verse paired
    with the 0-based row index (within this 'ammud's own page -- see
    :func:`get_page`) its own tag appears on. :mod:`ankipasuk.verse_cards`
    uses this to know exactly where the 'ammud's first tagged verse's own
    content begins, so it can exclude any earlier, untagged rows (belonging
    to a verse that actually started on a previous 'ammud) from what gets
    tested on this 'ammud's very first card.
    """
    if not (1 <= amud_num <= TOTAL_AMUDIM):
        raise ValueError(f"'Ammud must be between 1 and {TOTAL_AMUDIM} (got {amud_num}).")

    page = get_page(amud_num, cache)
    return [
        ((v["chapter"], v["verse"]), row_index)
        for row_index, entry in enumerate(page)
        for v in entry.get("verses", [])
    ]


def get_amud_lines(amud_num: int, cache: SefariaCache) -> list[dict]:
    """Every scroll-accurate line on 'ammud ``amud_num`` (1-245), in the
    same ``{"html": ..., "is_petucha": ..., "char_count": ...}`` shape as
    :func:`get_scroll_lines_for_range` -- see that function's docstring
    for what each field means. Unlike a verse/'aliyya range, this needs no
    slicing at all: an 'ammud already *is* tikkun.io's own per-page unit
    (see :func:`get_page`), so the whole page's lines are returned as-is.
    """
    if not (1 <= amud_num <= TOTAL_AMUDIM):
        raise ValueError(f"'Ammud must be between 1 and {TOTAL_AMUDIM} (got {amud_num}).")

    page = get_page(amud_num, cache)
    lines = []
    for entry in page:
        line = _render_line(entry)
        if line is not None:
            lines.append(line)
    return lines
