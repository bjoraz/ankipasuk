"""Builds verse-anchored LPCG tiqqun cards with true word-level
precision at row boundaries.

:mod:`ankipasuk.tikkun`'s row data never trims a physical scroll row --
when a verse starts or ends mid-row, the whole row (including a few words
belonging to the verse just before/after) is what's actually written on
the scroll. That's exactly right for a *row-anchored* card, but wrong for
a *verse-anchored* one: the tested content should be precisely this
verse's own words, no more, no less, with any neighboring words on the
same row surfacing only as context (visible, but not part of what's
recited).

Since tikkun.io's row text carries no sub-row word offsets, this module
finds them by aligning tikkun.io's own row-flattened word stream against
Sefaria's per-verse word count for every verse in the range being
exported. Both sides are normalized the same way (niqqud/ta'amim stripped,
maqaf split into a separate word -- see
:func:`ankipasuk.tikkun.scroll_plain_text` and
:func:`ankipasuk.text_processing.strip_vowels_and_trope`), so their word
counts should agree exactly: tikkun.io itself sources its text from
Sefaria's own API (see tikkun.py's module docstring), so both are
ultimately the same underlying Masoretic text.

A row is never just a flat word list here -- it's a list of tikkun.io's
own *fragments* (see :func:`ankipasuk.tikkun._row_fragments`), since a
setuma/poetic ("brick") gap between two fragments is a real feature of
the row's own layout, independent of where any verse boundary happens to
fall. A gap can sit between two fragments that belong to different
verses (an ordinary setuma between them), or entirely *within* one
verse's own text (Az Yashir/Shirat HaYam's poetic layout, or the 'Aseret
haDibberot's), so word-level verse splitting and fragment-level gap
rendering are two independent things this module has to get right at
once, not one implying the other.

The word alignment's own first row also needs care at the START of an
export, not just its end: a card range's very first requested verse can
itself start mid-row, sharing that row with the TAIL of the verse right
before it (e.g. Exodus 20:1's own row also carries the last word of
19:25) -- exactly the same shape of problem as a verse's own tail
bleeding into a row shared with the next verse (see
:func:`ankipasuk.tikkun.get_row_fragments_for_range`'s own
``generous_tail``), just at the other end. Left unhandled, that leading
bleed word would silently eat into the first requested verse's own word
budget, shifting *every* verse after it by however many words the bleed
is. Unlike the tail side, this can chain arbitrarily deep -- the verse
just before the range can ITSELF share leading words with the verse
before IT, and so on, for as long as consecutive rows keep landing verse
boundaries mid-fragment (which ordinary Tora text does constantly; the
'Aseret haDibberot's run of one-per-line "commandments" needs many verses'
worth of this before reaching a safe starting point) -- see
:func:`ankipasuk.tikkun.leading_verses_needing_alignment` for how far
back :func:`_build_from_verse_refs` walks to find one, and that function
itself for how those extra verses are included purely for alignment,
then discarded from the output.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from itertools import groupby

from .cache import SefariaCache
from .config import POINTED_VERSION
from .lpcg import BEGINNING_MARKER, box_width_from_char_counts
from .sefaria import fetch_torah_range
from .tikkun import (
    get_amud_row_fragments,
    get_book_verses_on_amud,
    get_preceding_row_fragments,
    get_row_fragments_for_range,
    leading_verses_needing_alignment,
)

# A row, as this module consumes it: tikkun.io's own fragments (each a
# word list; more than one fragment means a real gap belongs between them
# -- see the module docstring), the row's petuḥa flag, and its own 'ammud
# (page) number -- used to notice when consecutive rendered rows belong
# to different physical scroll columns (see AMUD_BREAK_MARKER).
Row = tuple[list[list[str]], bool, int]

# Marks a transition to a new physical scroll column on a card -- see
# build_verse_cards_from_words's own rendering of it. Bracketed like
# BEGINNING_MARKER, for the same reason: it's a structural note about the
# scroll, not text anyone recites.
AMUD_BREAK_MARKER = "['Ammud {page_num}]"


def _verse_word_count(book: str, ch: int, vs: int, cache: SefariaCache) -> int:
    """Sefaria's own word count for verse (ch, vs), normalized the same
    way tikkun.io's row text is (see the module docstring)."""
    verses = fetch_torah_range(book, ch, vs, ch, vs, cache, POINTED_VERSION)
    return len(verses[0]["plain"].split())


def _row_word_count(fragments: list[list[str]]) -> int:
    return sum(len(frag) for frag in fragments)


def _box_width(rows: list[Row]) -> str:
    """Same "ch"-unit box-width computation :mod:`ankipasuk.lpcg` uses for
    row-mode: each row's char count is the sum of its own fragments' word-
    joined lengths (no separator added *between* fragments, matching how
    :func:`ankipasuk.tikkun._render_line` counts a row's characters --
    the space a setuma/brick gap occupies is free layout space, not
    counted text width)."""
    return box_width_from_char_counts(
        sum(len(" ".join(frag)) for frag in fragments) for fragments, _is_petucha, _page_num in rows
    )


def _split_fragment(frag: list[str], frag_start: int, cut_a: int, cut_b: int) -> dict[str, list[str]]:
    """Split one fragment (starting at row-word-index ``frag_start``) into
    the portion before ``cut_a`` ("leading" -- a neighboring verse's
    tail), the portion in [cut_a, cut_b) ("own" -- this verse's own
    words), and the portion from ``cut_b`` on ("trailing" -- a
    neighboring verse's own start) -- any of the three may be empty. A
    verse boundary can fall inside a single fragment just as easily as
    between two fragments, so this has to be computed per fragment, not
    just per row.
    """
    frag_end = frag_start + len(frag)
    a = max(frag_start, min(frag_end, cut_a)) - frag_start
    b = max(frag_start, min(frag_end, cut_b)) - frag_start
    return {"leading": frag[:a], "own": frag[a:b], "trailing": frag[b:]}


def segment_rows_by_verse(rows: list[Row], verse_word_counts: list[int]) -> list[list[dict]]:
    """The core word-alignment, pure and cache-free (so directly
    testable): given ``rows`` (each a ``(fragments, is_petucha, page_num)``
    triple, in row order -- e.g. from :func:`ankipasuk.tikkun.get_row_fragments_for_range`)
    and ``verse_word_counts`` (the word count of verse 0, 1, 2, ... in the
    same order those verses' words appear across ``rows``), return, for
    each verse index, the list of rows its own row-span touches -- each
    ``{"row_index": int, "is_petucha": bool, "page_num": int, "fragments":
    [{"leading": [str], "own": [str], "trailing": [str]}, ...]}``, one
    ``fragments`` entry per fragment tikkun.io itself has on that row, in
    order.

    "leading"/"trailing" are the words in that fragment belonging to the
    verse just before/after -- non-empty only on a row (and, within it,
    only a fragment) this verse's span shares with a neighbor, i.e.
    exactly its own first and/or last row. A fragment entirely within
    this verse's own span gets an empty list for both.
    """
    row_ranges: list[tuple[int, int]] = []
    cursor = 0
    for fragments, _is_petucha, _page_num in rows:
        row_len = _row_word_count(fragments)
        row_ranges.append((cursor, cursor + row_len))
        cursor += row_len

    boundaries = [0]
    for count in verse_word_counts:
        boundaries.append(boundaries[-1] + count)

    per_verse: list[list[dict]] = []
    for i, count in enumerate(verse_word_counts):
        v_start, v_end = boundaries[i], boundaries[i + 1]
        own_rows: list[dict] = []
        if count > 0:
            for row_index, (row_start, row_end) in enumerate(row_ranges):
                if row_end <= v_start or row_start >= v_end:
                    continue
                fragments, is_petucha, page_num = rows[row_index]
                per_fragment = []
                frag_cursor = row_start
                for frag in fragments:
                    per_fragment.append(_split_fragment(frag, frag_cursor, v_start, v_end))
                    frag_cursor += len(frag)
                own_rows.append({
                    "row_index": row_index,
                    "is_petucha": is_petucha,
                    "page_num": page_num,
                    "fragments": per_fragment,
                })
        per_verse.append(own_rows)

    return per_verse


def _words_html(words: list[str], *, hover: bool) -> str:
    """Words joined by spaces. With ``hover`` (the answer side), a word
    that knows its pointed form (:class:`ankipasuk.tikkun.Word`) is
    wrapped so hovering it shows that form (see ``.w`` in
    :mod:`ankipasuk.lpcg`'s CSS)."""
    if not hover:
        return " ".join(words)
    return " ".join(
        f'<span class="w" data-p="{escape(word.pointed)}">{word}</span>'
        if getattr(word, "pointed", None) else word
        for word in words
    )


def _render_row_html(fragment_htmls: list[str], *, is_petucha: bool) -> str:
    """The shared ``.line`` > ``.column`` > ``.fragment`` markup
    :mod:`ankipasuk.tikkun`'s own ``_render_line`` uses (see that
    function's docstring and the CSS comment in :mod:`ankipasuk.lpcg`):
    more than one fragment gets the "setuma" class, which the shared CSS
    spaces apart with a real gap via flexbox instead of running them
    together in one justified block. Reused here (rather than
    reinvented) so a row split between two verses, a poetic "brick" gap
    entirely within one verse, or both at once, all render with the same
    real gap tikkun.io itself draws on the scroll.
    """
    setuma_class = " setuma" if len(fragment_htmls) > 1 else ""
    spans = "".join(f'<span class="fragment{setuma_class}">{html}</span>' for html in fragment_htmls)
    css_class = "line" + (" petucha" if is_petucha else "")
    return f'<div class="{css_class}"><div class="column">{spans}</div></div>'


def _render_split_fragment(seg: dict[str, list[str]], *, revealed: bool) -> str:
    """One fragment's own inner HTML, split into its (up to three)
    leading-context/own-words/trailing-context runs.

    "leading" (a row shared with the tail of the verse just BEFORE this
    one) is plain, always-visible text -- already-recited content, not a
    spoiler. "own" is this verse's own tested content, as an inline
    ``cloze-inline`` span containing the literal words on BOTH sides,
    ``revealed`` or not: hiding them is done with a ``redacted`` CSS
    class (transparent text over a solid bar), not by swapping in
    shorter placeholder text -- see the class-level rationale below for
    why. "trailing" (a row shared with the START of the verse just
    AFTER this one) is masked on BOTH sides, always -- unlike "own", it
    never reveals: showing the next verse's opening words on THIS card
    would spoil the very next card's own cloze before the reader gets
    there.

    Both masks use the same literal-words-under-a-solid-bar technique,
    for the same reason: a row's ``text-align: justify`` stretches each
    fragment to fill its own share of the box based on its actual word/
    space layout, so a masked run must carry the same real text as its
    unmasked counterpart elsewhere -- a shorter placeholder (e.g. an
    ellipsis) would leave it with fewer/narrower justify break points,
    visibly stretching its spacing differently from that same row
    rendered (unmasked, as "own") on ITS own verse's card.
    """
    parts = []
    if seg["leading"]:
        parts.append(_words_html(seg["leading"], hover=revealed))
    if seg["own"]:
        cloze_text = _words_html(seg["own"], hover=revealed)
        css_class = "cloze-inline" if revealed else "cloze-inline redacted"
        parts.append(f'<span class="{css_class}">{cloze_text}</span>')
    if seg["trailing"]:
        trailing_text = " ".join(seg["trailing"])
        parts.append(f'<span class="cloze-inline masked">{trailing_text}</span>')
    return " ".join(parts)


def _render_split_row(seg: dict, *, revealed: bool) -> str:
    fragment_htmls = [_render_split_fragment(frag, revealed=revealed) for frag in seg["fragments"]]
    return _render_row_html(fragment_htmls, is_petucha=seg["is_petucha"])


def _render_amud_break(page_num: int) -> str:
    """A visible divider marking a transition to a new physical scroll
    column -- inserted whenever two consecutively-rendered rows on one
    card come from different 'ammudim (see :func:`_render_own_rows`), most
    often a verse whose own tail crosses onto the next 'ammud (see
    :func:`ankipasuk.tikkun.get_row_fragments_for_range`'s own
    ``generous_tail``, which is what makes that content available to
    render here in the first place)."""
    return f'<div class="amud-break">{AMUD_BREAK_MARKER.format(page_num=page_num)}</div>'


def _render_own_rows(own_rows: list[dict], *, revealed: bool, starting_page_num: int | None) -> str:
    """Render every row of ``own_rows`` in order, inserting
    :func:`_render_amud_break` wherever the 'ammud (page) number changes
    from the previously rendered row -- including the transition INTO
    ``own_rows`` itself, if ``starting_page_num`` (the context row's own
    page, or None if there's no real context row -- see
    build_verse_cards_from_words) differs from ``own_rows[0]``'s.
    """
    parts = []
    previous_page_num = starting_page_num
    for seg in own_rows:
        page_num = seg["page_num"]
        if previous_page_num is not None and page_num != previous_page_num:
            parts.append(_render_amud_break(page_num))
        parts.append(_render_split_row(seg, revealed=revealed))
        previous_page_num = page_num
    return "".join(parts)


def _render_whole_row(row: Row, *, hover: bool = False) -> str:
    """A whole, unsplit row rendered as plain context -- used for the
    extra "one row before" lookback (see build_verse_cards_from_words),
    which -- except possibly for the very first verse in the whole range
    -- always falls entirely within the *previous* verse's own content,
    so needs no word-level splitting of its own (its own fragment/gap
    structure is still preserved, though -- see :func:`_render_row_html`)."""
    fragments, is_petucha, _page_num = row
    fragment_htmls = [_words_html(frag, hover=hover) for frag in fragments]
    return _render_row_html(fragment_htmls, is_petucha=is_petucha)


def build_verse_cards_from_words(
    rows: list[Row],
    verse_refs: list[tuple[int, int]],
    verse_word_counts: list[int],
    preceding_row: Row | None,
    *,
    title: str,
    author: str = "",
    box_width: str,
    leading_extra_verses: int = 0,
) -> list[dict[str, str]]:
    """Build one field-dict per verse in ``verse_refs`` -- pure (no cache
    access), given already-fetched/computed inputs, so directly testable.
    See :func:`build_verse_cards` for the cache-driven entry point that
    fetches ``rows``/``verse_word_counts``/``preceding_row`` itself.

    Each field-dict has "FrontRows"/"BackRows" (see the module docstring
    -- word-precise row-by-row HTML for each side) instead of
    :func:`ankipasuk.lpcg.build_lpcg_fields`'s "Context"/"Line"/"Prompt";
    the shared card template renders whichever pair is populated.

    ``verse_word_counts`` may carry ``leading_extra_verses`` extra entries
    at its very FRONT, for verses before ``verse_refs[0]`` -- not
    themselves turned into cards, only included so
    :func:`segment_rows_by_verse` can correctly tell their own trailing
    words on ``rows[0]`` apart from ``verse_refs[0]``'s own (see the
    module docstring on why ``rows[0]`` isn't always exactly
    ``verse_refs[0]``'s own first word). Their own segmentation output is
    simply discarded here.

    Every card's "one row before" context (see the module docstring)
    comes straight out of ``rows`` -- the row immediately before whichever
    row that verse's own span starts on -- except when its own span
    starts on ``rows[0]`` itself: that row lies outside ``rows``
    entirely, so ``preceding_row`` (from
    :func:`ankipasuk.tikkun.get_preceding_row_fragments`, fetched
    separately) is used instead, or the "[Beginning]" marker if there's
    no such row (rows[0] is the very first row of the Tora).
    """
    per_verse = segment_rows_by_verse(rows, verse_word_counts)[leading_extra_verses:]

    fields: list[dict[str, str]] = []
    for i, (ch, vs) in enumerate(verse_refs):
        own_rows = per_verse[i]
        first_row_index = own_rows[0]["row_index"] if own_rows else None

        if first_row_index is not None and first_row_index > 0:
            context_row = rows[first_row_index - 1]
        else:
            context_row = preceding_row
        if context_row is not None:
            context_html = _render_whole_row(context_row)
            back_context_html = _render_whole_row(context_row, hover=True)
            context_page_num = context_row[2]
        else:
            context_html = back_context_html = f'<div class="line beginning-marker">{BEGINNING_MARKER}</div>'
            context_page_num = None  # no real row to compare an 'ammud break against

        fields.append({
            "FrontRows": context_html + _render_own_rows(
                own_rows, revealed=False, starting_page_num=context_page_num,
            ),
            "BackRows": back_context_html + _render_own_rows(
                own_rows, revealed=True, starting_page_num=context_page_num,
            ),
            "Title": title,
            "Author": author,
            "Sequence": str(i + 1),
            "BoxWidth": box_width,
        })

    return fields


def _build_from_verse_refs(
    book: str, verse_refs: list[tuple[int, int]], cache: SefariaCache, *,
    title: str, author: str, box_width_rows: list[Row] | None = None,
) -> list[dict[str, str]]:
    """Shared implementation for :func:`build_verse_cards` and
    :func:`build_amud_verse_cards`: fetch row/word data for a consecutive
    run of verses and build their cards, correctly excluding any leading
    bleed on the FIRST fetched row from whichever verse(s) come just
    before ``verse_refs[0]`` (see the module docstring and
    :func:`ankipasuk.tikkun.leading_verses_needing_alignment`) -- not
    just a row-mode-style "extra context word or two", but a real risk of
    silently shifting every single verse in the export by however many
    words that bleed is, since the word-alignment in
    :func:`segment_rows_by_verse` has no other way to tell where
    ``verse_refs[0]``'s own content actually starts.

    This works regardless of how far back those extra verses' own
    content reaches (even onto an earlier 'ammud) --
    :func:`ankipasuk.tikkun.get_row_fragments_for_range` already walks
    page boundaries freely, the same as it does at the end of a range
    (see that function's own docstring on ``generous_tail``).

    ``box_width_rows``, if given, is included ALONGSIDE the fetched
    ``rows`` for the "BoxWidth" field's own char-count basis (a plain max,
    so no harm in overlap) -- :func:`build_amud_verse_cards` passes the
    whole 'ammud's own fixed page, so the box stays at least as wide as the
    physical column even when word-alignment itself ends up fetching a
    narrower slice of it (e.g. starting mid-page because of an earlier
    verse's own bleed) -- and at least as wide as whatever a verse's own
    tail crossing onto the NEXT 'ammud adds to ``rows``, which isn't part
    of ``box_width_rows`` at all.
    """
    first_ch, first_vs = verse_refs[0]
    last_ch, last_vs = verse_refs[-1]

    leading_refs = leading_verses_needing_alignment(book, first_ch, first_vs, cache)
    fetch_ch, fetch_vs = leading_refs[0] if leading_refs else (first_ch, first_vs)

    rows = get_row_fragments_for_range(book, fetch_ch, fetch_vs, last_ch, last_vs, cache)
    preceding_row = get_preceding_row_fragments(book, fetch_ch, fetch_vs, cache)

    leading_counts = [_verse_word_count(book, ch, vs, cache) for ch, vs in leading_refs]
    verse_word_counts = leading_counts + [_verse_word_count(book, ch, vs, cache) for ch, vs in verse_refs]

    box_width = _box_width((box_width_rows or []) + rows)

    return build_verse_cards_from_words(
        rows, verse_refs, verse_word_counts, preceding_row,
        title=title, author=author, box_width=box_width,
        leading_extra_verses=len(leading_refs),
    )


def build_verse_cards(
    book: str, verse_refs: list[tuple[int, int]], cache: SefariaCache, *, title: str, author: str = "",
) -> list[dict[str, str]]:
    """The cache-driven entry point for a verse range (e.g. an 'aliyya):
    fetches tikkun.io's row-fragment data spanning ``verse_refs`` (its
    first verse through its last, plus whatever the verse just before it
    needs -- see :func:`_build_from_verse_refs`), each verse's own
    Sefaria word count, and the one row before the range -- then hands
    everything to :func:`build_verse_cards_from_words`. ``verse_refs``
    must be consecutive verses, in order (e.g. one 'aliyya's own
    ``verses`` list).
    """
    return _build_from_verse_refs(book, verse_refs, cache, title=title, author=author)


def build_amud_verse_cards(
    amud_num: int, cache: SefariaCache, *, title_for: Callable[[str], str], author: str = "",
) -> list[tuple[tuple[str, int, int], dict[str, str]]]:
    """The cache-driven entry point for a single 'ammud: one card per verse
    that starts on it, as ``((book, chapter, verse), fields)`` (see
    :func:`ankipasuk.tikkun.get_book_verses_on_amud`), via
    :func:`_build_from_verse_refs` -- so the 'ammud's own first card is
    just as word-precise as any other, even when its own first tagged row
    also carries a bleed word or two from whatever verse came right
    before it (which, since this is the 'ammud's OWN first tagged verse,
    always started on an earlier 'ammud when it exists at all).

    An 'ammud that holds the end of one book and the start of the next
    (111, 148, 200) is built one book at a time, each pasuq aligned
    against its own book's text; ``title_for(book)`` gives each card's
    title, and the cards are numbered (``Sequence``) through the whole
    'ammud.

    Symmetrically, this 'ammud's own LAST card can reach past this 'ammud's
    own last row too, when that verse's own tail crosses onto the NEXT
    'ammud (:func:`ankipasuk.tikkun.get_row_fragments_for_range`'s
    ``generous_tail`` already fetches it) -- rendered with a visible
    "['Ammud N]" break (see :func:`_render_amud_break`) rather than
    silently splicing the new column's lines onto this one, since a real
    reciter following along on an actual scroll needs to know they've
    turned to a new column mid-verse.

    The "BoxWidth" field is still sized from the 'ammud's own whole,
    physical page (see :func:`ankipasuk.tikkun.get_amud_row_fragments`)
    at minimum, so the box stays at least as wide as the actual column
    -- see :func:`_build_from_verse_refs` for how it also widens further
    for whatever a crossed-over verse's tail needs.
    """
    all_rows = get_amud_row_fragments(amud_num, cache)
    cards = []
    for book, run in groupby(get_book_verses_on_amud(amud_num, cache), key=lambda ref: ref[0]):
        run = list(run)
        fields_list = _build_from_verse_refs(
            book, [(ch, vs) for _book, ch, vs in run], cache,
            title=title_for(book), author=author, box_width_rows=all_rows,
        )
        cards += zip(run, fields_list)
    for seq, (_ref, fields) in enumerate(cards, start=1):
        fields["Sequence"] = str(seq)
    return cards
