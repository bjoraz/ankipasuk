"""Tests for ankipasuk.tikkun -- scroll-accurate line layout from
tikkun.io.

Exercises the real line-slicing logic (page/line boundary arithmetic,
cross-chapter ranges, end-of-book) with zero network access by seeding
SefariaCache directly with a small fake table of contents and fake pages,
the same approach tests/test_sefaria_aliyot.py uses for parasha structure.
"""

import pytest

from ankipasuk.cache import SefariaCache
from ankipasuk.tikkun import (
    TOTAL_AMUDIM,
    get_amud_lines,
    get_amud_row_fragments,
    get_book_for_page,
    get_preceding_row,
    get_preceding_row_fragments,
    get_row_fragments_for_range,
    get_scroll_lines_for_range,
    get_verse_row_indices_on_amud,
    get_verses_starting_on_amud,
    leading_verses_needing_alignment,
    scroll_plain_text,
    scroll_pointed_text,
)

BOOK = "Genesis"


def _h(text: str, is_petucha: bool = False) -> dict:
    """Shorthand for the {"html": ..., "is_petucha": ..., "char_count":
    ...} shape get_scroll_lines_for_range returns for an ordinary
    (non-setuma) single-fragment line -- the column/fragment markup
    tikkun.io's own Line.ts renders, ported in
    ankipasuk.tikkun._render_line."""
    html = f'<div class="column"><span class="fragment">{text}</span></div>'
    return {"html": html, "is_petucha": is_petucha, "char_count": len(text)}


@pytest.fixture(autouse=True)
def _small_genesis(monkeypatch):
    """get_scroll_lines_for_range's chapter-rollover logic (_next_ref)
    reads real chapter lengths off ankipasuk.tikkun.TORAH_VERSE_COUNTS --
    override it to a tiny 2-chapter book so the fake TOC/pages below
    (chapter 1 has 4 verses, chapter 2 has 2) actually reflect where each
    chapter starts and ends, instead of real Genesis's 31/25."""
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [4, 2]})


def _line(text: str, verses=(), isPetucha=False):
    return {"text": [[text]], "verses": list(verses), "aliyot": [], "isPetucha": isPetucha}


def _seed(tmp_path, toc, pages):
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_tikkun_toc(toc)
    for page_num, lines in pages.items():
        cache.set_tikkun_page(page_num, lines)
    return cache


def _two_chapter_toc():
    """Genesis chapter 1 (4 verses, page 1) followed by chapter 2 (2
    verses, page 2). Verse 1 owns line 1 alone; verse 2 starts line 2;
    verse 3 also starts on line 2 (i.e. verse 2 ends and verse 3 begins on
    the same physical line); verse 4 starts line 3, which is also the
    chapter's last line."""
    return {
        "1": {
            "1": {
                "1": {"p": 1, "l": 1},
                "2": {"p": 1, "l": 2},
                "3": {"p": 1, "l": 2},
                "4": {"p": 1, "l": 3},
            },
            "2": {
                "1": {"p": 2, "l": 1},
                "2": {"p": 2, "l": 2},
            },
        }
    }


def _page_one():
    return [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
        _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
        _line("גגג", verses=[{"chapter": 1, "verse": 4}]),
    ]


def _page_two():
    return [
        _line("ההה", verses=[{"chapter": 2, "verse": 1}]),
        _line("וו", verses=[{"chapter": 2, "verse": 2}]),
    ]


# =============================================================
#  scroll_plain_text -- port of tikkun.io's own "annotations off" filter
# =============================================================
def test_strips_nikud_and_trope():
    assert scroll_plain_text("בְּרֵאשִׁ֖ית בָּרָ֣א") == "בראשית ברא"


def test_strips_sof_pasuk():
    assert scroll_plain_text("אֱלֹהִ֑ים׃") == "אלהים"


def test_maqaf_becomes_a_space():
    assert scroll_plain_text("וְאֵ֥ת־הָאָֽרֶץ") == "ואת הארץ"


def test_strips_petucha_marker():
    assert scroll_plain_text("וַֽיְהִי־בֹ֖קֶר׃#(פ)") == "ויהי בקר"


def test_fragment_that_is_only_punctuation_becomes_empty():
    assert scroll_plain_text("׃") == ""


# =============================================================
#  scroll_pointed_text -- port of tikkun.io's "annotations on" filter
# =============================================================
def test_pointed_text_keeps_nikud_and_trope():
    assert scroll_pointed_text("בְּרֵאשִׁ֖ית בָּרָ֣א") == "בְּרֵאשִׁ֖ית בָּרָ֣א"


def test_pointed_text_keeps_the_maqaf_character_itself():
    assert scroll_pointed_text("וְאֵ֥ת־הָאָֽרֶץ") == "וְאֵ֥ת־הָאָֽרֶץ"


def test_pointed_text_strips_the_petucha_marker():
    assert scroll_pointed_text("וַֽיְהִי־בֹ֖קֶר׃#(פ)") == "וַֽיְהִי־בֹ֖קֶר׃"


def test_pointed_text_keeps_sof_pasuk():
    assert scroll_pointed_text("אֱלֹהִ֑ים׃") == "אֱלֹהִ֑ים׃"


def test_pointed_text_resolves_ketiv_kri_to_the_kri_reading():
    # "#" inside a word marks a ketiv/qeri correction -- only the text
    # AFTER it (the "read as" form) is kept, matching a real Tikkun.
    assert scroll_pointed_text("כתיב#קרי") == "קרי"


def test_pointed_text_converts_brackets_to_braces():
    assert scroll_pointed_text("א[ב]ג") == "א{ב}ג"


# =============================================================
#  get_scroll_lines_for_range -- page/line boundary arithmetic
# =============================================================
def test_single_line_range(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert get_scroll_lines_for_range(BOOK, 1, 1, 1, 1, cache) == [_h("אאא")]


def test_range_within_one_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # Verses 1-3: verse 3 starts on the same line as verse 2 (line 2), so
    # the included lines are 1-2 (line 3, where verse 4 starts, is excluded).
    assert get_scroll_lines_for_range(BOOK, 1, 1, 1, 3, cache) == [_h("אאא"), _h("בבב")]


def test_range_ending_mid_line_still_includes_the_whole_line(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # Verse 2 alone: verse 3 starts on the SAME line (line 2), so that
    # whole line is included even though part of it is verse 3's text --
    # a real sefer doesn't split a line at a verse boundary.
    assert get_scroll_lines_for_range(BOOK, 1, 2, 1, 2, cache) == [_h("בבב")]


def test_range_ending_at_last_verse_of_chapter_includes_rest_of_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # Verse 4 is chapter 1's last verse -- the next verse (2:1) starts a
    # new page, so all remaining lines of page 1 belong to verse 4.
    assert get_scroll_lines_for_range(BOOK, 1, 4, 1, 4, cache) == [_h("גגג")]


def test_range_spanning_chapters_includes_full_pages_in_between(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    result = get_scroll_lines_for_range(BOOK, 1, 4, 2, 1, cache)
    assert result == [_h("גגג"), _h("ההה")]


def test_range_ending_at_the_books_last_verse_includes_rest_of_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # 2:2 is the last verse in this fake TOC's last chapter -- no next_ref.
    assert get_scroll_lines_for_range(BOOK, 2, 2, 2, 2, cache) == [_h("וו")]


def test_blank_lines_are_omitted(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 3}, "3": {"p": 1, "l": 3}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
        _line("׃"),  # strips to empty -- e.g. a stray punctuation-only line
        _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    assert get_scroll_lines_for_range(BOOK, 1, 1, 1, 2, cache) == [_h("אאא"), _h("בבב")]


def test_petucha_flag_is_passed_through(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}, "3": {"p": 1, "l": 2}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}], isPetucha=True),
        _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_scroll_lines_for_range(BOOK, 1, 1, 1, 2, cache)
    assert result == [_h("אאא", is_petucha=True), _h("בבב")]


def test_setumah_fragments_get_the_setuma_class_for_a_real_flex_gap(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 2, "l": 1}}}}
    pages = {1: [
        {"text": [["אאא", "בבב"]], "verses": [{"chapter": 1, "verse": 1}], "aliyot": [], "isPetucha": False},
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_scroll_lines_for_range(BOOK, 1, 1, 1, 1, cache)
    assert result == [{
        "html": (
            '<div class="column">'
            '<span class="fragment setuma">אאא</span>'
            '<span class="fragment setuma">בבב</span>'
            "</div>"
        ),
        "is_petucha": False,
        "char_count": 6,
    }]


def test_pointed_mode_renders_full_nikud_but_char_count_stays_consonant_based(tmp_path):
    """char_count must still reflect visible CONSONANT width even in
    pointed mode -- niqqud/trope add no horizontal advance in a proper
    Hebrew rendering, so counting their own codepoints would grossly
    overestimate box width (see _render_line's own docstring)."""
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 2, "l": 1}}}}
    pages = {1: [
        {"text": [["בְּרֵאשִׁ֖ית"]], "verses": [{"chapter": 1, "verse": 1}], "aliyot": [], "isPetucha": False},
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_scroll_lines_for_range(BOOK, 1, 1, 1, 1, cache, pointed=True)
    assert result == [{
        "html": '<div class="column"><span class="fragment">בְּרֵאשִׁ֖ית</span></div>',
        "is_petucha": False,
        "char_count": 6,  # len("בראשית"), not the pointed string's own (longer) length
    }]


def test_unknown_book_raises(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="Tora only"):
        get_scroll_lines_for_range("Isaiah", 1, 1, 1, 1, cache)


def test_verse_missing_from_toc_raises(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    with pytest.raises(ValueError, match="not found in tikkun.io data"):
        get_scroll_lines_for_range(BOOK, 1, 1, 5, 99, cache)


# =============================================================
#  get_row_fragments_for_range / get_amud_row_fragments -- word-level data
# =============================================================
def test_get_row_fragments_for_range_splits_each_row_into_words(tmp_path):
    toc = {"1": {"1": {
        "1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}, "3": {"p": 1, "l": 2},
    }}}
    pages = {1: [
        _line("אא בב גג", verses=[{"chapter": 1, "verse": 1}]),
        _line("דד הה", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_row_fragments_for_range(BOOK, 1, 1, 1, 2, cache)
    assert result == [
        ([["אא", "בב", "גג"]], False, 1),
        ([["דד", "הה"]], False, 1),
    ]


def test_get_row_fragments_for_range_keeps_blank_rows_unlike_get_scroll_lines(tmp_path):
    toc = {"1": {"1": {
        "1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 3}, "3": {"p": 1, "l": 3},
    }}}
    pages = {1: [
        _line("אא", verses=[{"chapter": 1, "verse": 1}]),
        _line("׃"),  # strips to zero words
        _line("בב", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_row_fragments_for_range(BOOK, 1, 1, 1, 2, cache)
    assert result == [([["אא"]], False, 1), ([], False, 1), ([["בב"]], False, 1)]


def test_get_row_fragments_for_range_preserves_petucha_flag(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}}}}
    pages = {1: [
        _line("אא בב", verses=[{"chapter": 1, "verse": 1}], isPetucha=True),
        _line("גג", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    assert get_row_fragments_for_range(BOOK, 1, 1, 1, 1, cache) == [
        ([["אא", "בב"]], True, 1), ([["גג"]], False, 1),
    ]


def test_get_row_fragments_for_range_keeps_a_rows_setuma_fragments_separate(tmp_path):
    """A row's own multi-fragment structure (a setuma gap, or a poetic
    "brick" gap -- e.g. Az Yashir/Shirat HaYam -- entirely within one
    verse) must survive as separate fragments, not collapse into one
    flat word list -- see the module docstring on why this matters for
    :mod:`ankipasuk.verse_cards`'s rendering."""
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}}}}
    pages = {1: [
        {"text": [["אא בב", "גג"]], "verses": [{"chapter": 1, "verse": 1}], "aliyot": [], "isPetucha": False},
        _line("דד", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    result = get_row_fragments_for_range(BOOK, 1, 1, 1, 1, cache)
    assert result == [
        ([["אא", "בב"], ["גג"]], False, 1), ([["דד"]], False, 1),
    ]


def test_get_row_fragments_for_range_generous_tail_includes_a_shared_final_row(tmp_path):
    """Regression case: the end verse's own tail can span MORE than one
    row before reaching a row it shares with the very next verse -- the
    word-precise fetch must not stop one row short of that (see
    _row_entries_for_range's own docstring on why it requests the more
    generous bound). Real-world case: Exodus 15:21's own tail ("...His
    horse and rider He hurled into the sea") lands on the same row as
    Exodus 15:22's own start.
    """
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}, "3": {"p": 1, "l": 3}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
        _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
        {"text": [["גגג", "דדד"]], "verses": [{"chapter": 1, "verse": 3}], "aliyot": [], "isPetucha": False},
    ]}
    cache = _seed(tmp_path, toc, pages)

    result = get_row_fragments_for_range(BOOK, 1, 1, 1, 2, cache)
    assert result == [
        ([["אאא"]], False, 1),
        ([["בבב"]], False, 1),
        ([["גגג"], ["דדד"]], False, 1),
    ]

    # get_scroll_lines_for_range (row-anchored) deliberately does NOT use
    # this generous bound -- it would bleed a whole unshared row into
    # every row-mode export otherwise (see _row_entries_for_range).
    assert len(get_scroll_lines_for_range(BOOK, 1, 1, 1, 2, cache)) == 2


def test_get_row_fragments_for_range_generous_tail_crosses_an_amud_boundary(tmp_path, monkeypatch):
    """A verse's own tail isn't bounded by where its OWN starting 'ammud
    ends -- e.g. Exodus 20:whatever straddling 'ammud 83/84 -- so the
    generous fetch must follow it onto a later page entirely, not just
    to the end of the end verse's own starting page."""
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [3]})
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}, "3": {"p": 2, "l": 2}}}}
    pages = {
        1: [
            _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
            _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
        ],
        2: [
            _line("גגג"),  # continues verse 2's own tail onto 'ammud 2
            _line("דדד", verses=[{"chapter": 1, "verse": 3}]),
        ],
    }
    cache = _seed(tmp_path, toc, pages)

    result = get_row_fragments_for_range(BOOK, 1, 1, 1, 2, cache)
    assert result == [
        ([["אאא"]], False, 1),
        ([["בבב"]], False, 1),
        ([["גגג"]], False, 2),
        ([["דדד"]], False, 2),
    ]


def test_get_amud_row_fragments_returns_every_rows_fragments(tmp_path, monkeypatch):
    cache = _five_book_toc_and_pages(tmp_path, monkeypatch)
    assert get_amud_row_fragments(2, cache) == [([["גגג"]], False, 2), ([["דדד"]], False, 2)]


def test_get_amud_row_fragments_rejects_out_of_range_amud(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_amud_row_fragments(0, cache)
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_amud_row_fragments(TOTAL_AMUDIM + 1, cache)


# =============================================================
#  get_book_for_page / get_amud_lines -- 'ammud (column) export
# =============================================================
def _five_book_toc_and_pages(tmp_path, monkeypatch):
    """A tiny 5-book fake Tora: Genesis ('ammud 1, 2 verses), Exodus ('ammud
    2, 2 verses), Leviticus ('ammud 3, 1 verse), Numbers ('ammud 4, 1 verse),
    Deuteronomy ('ammud 5, 1 verse) -- every book starting a fresh 'ammud,
    same as a real sefer always does."""
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {
        "Genesis": [2], "Exodus": [2], "Leviticus": [1], "Numbers": [1], "Deuteronomy": [1],
    })
    toc = {
        "1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}}},
        "2": {"1": {"1": {"p": 2, "l": 1}, "2": {"p": 2, "l": 2}}},
        "3": {"1": {"1": {"p": 3, "l": 1}}},
        "4": {"1": {"1": {"p": 4, "l": 1}}},
        "5": {"1": {"1": {"p": 5, "l": 1}}},
    }
    pages = {
        1: [
            _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
            _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
        ],
        2: [
            _line("גגג", verses=[{"chapter": 1, "verse": 1}]),
            _line("דדד", verses=[{"chapter": 1, "verse": 2}]),
        ],
        3: [_line("ההה", verses=[{"chapter": 1, "verse": 1}])],
        4: [_line("ווו", verses=[{"chapter": 1, "verse": 1}])],
        5: [_line("זזז", verses=[{"chapter": 1, "verse": 1}])],
    }
    return _seed(tmp_path, toc, pages)


def test_get_book_for_page_first_amud_of_a_book(tmp_path, monkeypatch):
    cache = _five_book_toc_and_pages(tmp_path, monkeypatch)
    assert get_book_for_page(1, cache) == "Genesis"
    assert get_book_for_page(3, cache) == "Leviticus"


def test_get_book_for_page_at_a_book_boundary(tmp_path, monkeypatch):
    cache = _five_book_toc_and_pages(tmp_path, monkeypatch)
    # Genesis's only 'ammud is 1 -- 'ammud 2 must belong to Exodus, not Genesis.
    assert get_book_for_page(2, cache) == "Exodus"
    assert get_book_for_page(5, cache) == "Deuteronomy"


def test_get_book_for_page_rejects_out_of_range_amud(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_book_for_page(0, cache)
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_book_for_page(TOTAL_AMUDIM + 1, cache)


def test_get_amud_lines_returns_every_line_on_that_page(tmp_path, monkeypatch):
    cache = _five_book_toc_and_pages(tmp_path, monkeypatch)
    lines = get_amud_lines(2, cache)
    assert [line["html"] for line in lines] == [
        '<div class="column"><span class="fragment">גגג</span></div>',
        '<div class="column"><span class="fragment">דדד</span></div>',
    ]


def test_get_amud_lines_rejects_out_of_range_amud(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_amud_lines(0, cache)
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_amud_lines(TOTAL_AMUDIM + 1, cache)


# =============================================================
#  get_preceding_row / get_verses_starting_on_amud -- verse-based cards
# =============================================================
def test_get_preceding_row_within_the_same_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # Verse 1:2 starts on line 2 -- the row before it is line 1 ("אאא").
    row = get_preceding_row(BOOK, 1, 2, cache)
    assert row["html"] == '<div class="column"><span class="fragment">אאא</span></div>'


def test_get_preceding_row_crosses_into_the_previous_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    # Verse 2:1 starts on page 2, line 1 -- the row before it is page 1's
    # own last row ("גגג").
    row = get_preceding_row(BOOK, 2, 1, cache)
    assert row["html"] == '<div class="column"><span class="fragment">גגג</span></div>'


def test_get_preceding_row_is_none_at_the_very_start_of_the_torah(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert get_preceding_row(BOOK, 1, 1, cache) is None


def test_get_preceding_row_unknown_book_raises(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="Tora only"):
        get_preceding_row("Isaiah", 1, 1, cache)


def test_get_preceding_row_fragments_within_the_same_page(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert get_preceding_row_fragments(BOOK, 1, 2, cache) == ([["אאא"]], False, 1)


def test_get_preceding_row_fragments_is_none_at_the_very_start_of_the_torah(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert get_preceding_row_fragments(BOOK, 1, 1, cache) is None


# =============================================================
#  leading_verses_needing_alignment -- how far verse_cards must walk back
# =============================================================
def test_leading_verses_needing_alignment_empty_at_the_very_start_of_the_torah(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert leading_verses_needing_alignment(BOOK, 1, 1, cache) == []


def test_leading_verses_needing_alignment_stops_at_a_petucha(tmp_path):
    """The row right before this verse's own row is a petuḥa -- a
    paragraph genuinely ending there, so nothing can bleed forward onto
    this verse's row. No walk-back needed."""
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}], isPetucha=True),
        _line("בבב", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    assert leading_verses_needing_alignment(BOOK, 1, 2, cache) == []


def test_leading_verses_needing_alignment_walks_back_through_a_non_petucha_gap(tmp_path):
    """No petuḥa between verse 1 and verse 2's own rows -- verse 1 must
    be prepended (its own tail could bleed onto verse 2's row)."""
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert leading_verses_needing_alignment(BOOK, 1, 2, cache) == [(1, 1)]


def test_leading_verses_needing_alignment_a_shared_row_always_needs_the_verse_before_it(tmp_path):
    """Verse 2 and verse 3 are tagged to the exact same row (a short
    verse sharing its start line with the verse right after it) --
    that's NEVER a safe stopping point on its own, regardless of page
    position, so verse 2 is always included; the walk continues from
    there since there's still no petuḥa between verse 1 and verse 2."""
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert leading_verses_needing_alignment(BOOK, 1, 3, cache) == [(1, 1), (1, 2)]


def test_get_preceding_row_verse_missing_from_toc_raises(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    with pytest.raises(ValueError, match="not found in tikkun.io data"):
        get_preceding_row(BOOK, 9, 9, cache)


def test_get_verses_starting_on_amud_lists_every_tagged_verse_in_row_order(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    assert get_verses_starting_on_amud(1, cache) == [(1, 1), (1, 2), (1, 4)]


def test_get_verses_starting_on_amud_skips_untagged_rows(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 3}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
        _line("בבב"),  # continues verse 1, no new verse starts here
        _line("גגג", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    assert get_verses_starting_on_amud(1, cache) == [(1, 1), (1, 2)]


def test_get_verse_row_indices_on_amud_pairs_each_verse_with_its_0_based_row(tmp_path):
    toc = {"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 3}}}}
    pages = {1: [
        _line("אאא", verses=[{"chapter": 1, "verse": 1}]),
        _line("בבב"),  # continues verse 1, no new verse starts here
        _line("גגג", verses=[{"chapter": 1, "verse": 2}]),
    ]}
    cache = _seed(tmp_path, toc, pages)
    assert get_verse_row_indices_on_amud(1, cache) == [((1, 1), 0), ((1, 2), 2)]


def test_get_verses_starting_on_amud_rejects_out_of_range_amud(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_verses_starting_on_amud(0, cache)
    with pytest.raises(ValueError, match="between 1 and 245"):
        get_verses_starting_on_amud(TOTAL_AMUDIM + 1, cache)
