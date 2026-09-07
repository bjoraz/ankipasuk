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
    get_book_for_page,
    get_scroll_lines_for_range,
    scroll_plain_text,
)

BOOK = "Genesis"


def _h(text: str, is_petucha: bool = False) -> dict:
    """Shorthand for the {"html": ..., "is_petucha": ..., "char_count":
    ...} shape get_scroll_lines_for_range returns for an ordinary
    (non-setumah) single-fragment line -- the column/fragment markup
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
    # a real Torah scroll doesn't split a line at a verse boundary.
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


def test_unknown_book_raises(tmp_path):
    cache = _seed(tmp_path, {}, {})
    with pytest.raises(ValueError, match="Torah only"):
        get_scroll_lines_for_range("Isaiah", 1, 1, 1, 1, cache)


def test_verse_missing_from_toc_raises(tmp_path):
    cache = _seed(tmp_path, _two_chapter_toc(), {1: _page_one(), 2: _page_two()})
    with pytest.raises(ValueError, match="not found in tikkun.io data"):
        get_scroll_lines_for_range(BOOK, 1, 1, 5, 99, cache)


# =============================================================
#  get_book_for_page / get_amud_lines -- amud (column) export
# =============================================================
def _five_book_toc_and_pages(tmp_path, monkeypatch):
    """A tiny 5-book fake Torah: Genesis (amud 1, 2 verses), Exodus (amud
    2, 2 verses), Leviticus (amud 3, 1 verse), Numbers (amud 4, 1 verse),
    Deuteronomy (amud 5, 1 verse) -- every book starting a fresh amud,
    same as a real kosher Sefer Torah always does."""
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
    # Genesis's only amud is 1 -- amud 2 must belong to Exodus, not Genesis.
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
