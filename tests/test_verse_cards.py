"""Tests for ankipasuk.verse_cards -- word-precise verse-anchored LPCG
cards.

segment_rows_by_verse and build_verse_cards_from_words are pure (no cache
access), so exercised directly here with hand-built row/word-count data.
A row is ``(fragments, is_petucha, page_num)``, where ``fragments`` is a
list of word lists -- one per tikkun.io fragment (see
:func:`ankipasuk.tikkun._row_fragments`); a single-fragment row on 'ammud 1
is written here as e.g. ``[["a", "b", "c"]], False, 1``. Most fixtures
below keep every row on the same page (1) since :func:`segment_rows_by_verse`
itself doesn't care about page boundaries -- see the dedicated amud-break
tests near the bottom for the page-number-aware rendering behavior.

The cache-driven entry points (build_verse_cards, build_amud_verse_cards)
are exercised at the API layer in tests/test_webgui/test_api.py, the same
way ankipasuk.tikkun's own cache-driven functions are.
"""

from ankipasuk.verse_cards import (
    build_verse_cards_from_words,
    segment_rows_by_verse,
)


# =============================================================
#  segment_rows_by_verse -- the core word-alignment
# =============================================================
def test_single_row_single_verse_no_sharing():
    rows = [([["a", "b", "c"]], False, 1)]
    result = segment_rows_by_verse(rows, [3])
    assert result == [
        [{"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["a", "b", "c"], "trailing": []},
        ]}],
    ]


def test_verse_spanning_multiple_rows_with_no_sharing():
    rows = [([["a", "b"]], False, 1), ([["c", "d"]], False, 1), ([["e"]], False, 1)]
    result = segment_rows_by_verse(rows, [5])
    assert result == [[
        {"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["a", "b"], "trailing": []},
        ]},
        {"row_index": 1, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["c", "d"], "trailing": []},
        ]},
        {"row_index": 2, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["e"], "trailing": []},
        ]},
    ]]


def test_two_verses_sharing_one_row_evenly_split():
    # Row 0 is entirely verse 0 ("a","b"); row 1 is split between verse 0
    # ("c") and verse 1 ("d","e"), all within one fragment.
    rows = [([["a", "b"]], False, 1), ([["c", "d", "e"]], False, 1)]
    result = segment_rows_by_verse(rows, [3, 2])

    verse0, verse1 = result
    assert verse0 == [
        {"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["a", "b"], "trailing": []},
        ]},
        {"row_index": 1, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["c"], "trailing": ["d", "e"]},
        ]},
    ]
    assert verse1 == [
        {"row_index": 1, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": ["c"], "own": ["d", "e"], "trailing": []},
        ]},
    ]


def test_multi_row_verse_ending_on_a_row_shared_with_the_next_verse():
    """Regression case for the original bug: a verse spanning several
    rows, whose LAST row is shared with the next verse, must still
    include that row in full (not stop one row short)."""
    rows = [
        ([["a"]], False, 1),          # row0: fully verse0
        ([["b", "c"]], False, 1),     # row1: fully verse0 (interior)
        ([["d", "e", "f"]], False, 1),  # row2: verse0's tail ("d") + verse1's head ("e","f")
    ]
    result = segment_rows_by_verse(rows, [4, 2])
    verse0, verse1 = result

    assert [seg["row_index"] for seg in verse0] == [0, 1, 2]
    assert verse0[2] == {
        "row_index": 2, "is_petucha": False, "page_num": 1,
        "fragments": [{"leading": [], "own": ["d"], "trailing": ["e", "f"]}],
    }
    assert verse1 == [
        {"row_index": 2, "is_petucha": False, "page_num": 1,
         "fragments": [{"leading": ["d"], "own": ["e", "f"], "trailing": []}]},
    ]


def test_three_verses_the_middle_one_entirely_within_a_shared_row():
    # A short middle verse ("c") entirely sandwiched between verse0's tail
    # ("a","b") and verse2's head ("d","e") on the SAME row/fragment.
    rows = [([["a", "b", "c", "d", "e"]], False, 1)]
    result = segment_rows_by_verse(rows, [2, 1, 2])
    verse0, verse1, verse2 = result

    assert verse0 == [{"row_index": 0, "is_petucha": False, "page_num": 1,
                        "fragments": [{"leading": [], "own": ["a", "b"], "trailing": ["c", "d", "e"]}]}]
    assert verse1 == [{"row_index": 0, "is_petucha": False, "page_num": 1,
                        "fragments": [{"leading": ["a", "b"], "own": ["c"], "trailing": ["d", "e"]}]}]
    assert verse2 == [{"row_index": 0, "is_petucha": False, "page_num": 1,
                        "fragments": [{"leading": ["a", "b", "c"], "own": ["d", "e"], "trailing": []}]}]


def test_is_petucha_flag_is_preserved_per_row():
    rows = [([["a"]], True, 1), ([["b"]], False, 1)]
    result = segment_rows_by_verse(rows, [1, 1])
    assert result[0][0]["is_petucha"] is True
    assert result[1][0]["is_petucha"] is False


def test_page_num_is_preserved_per_row():
    rows = [([["a"]], False, 5), ([["b"]], False, 6)]
    result = segment_rows_by_verse(rows, [1, 1])
    assert result[0][0]["page_num"] == 5
    assert result[1][0]["page_num"] == 6


def test_zero_word_verse_gets_no_rows():
    rows = [([["a", "b"]], False, 1)]
    result = segment_rows_by_verse(rows, [0, 2])
    assert result[0] == []
    assert result[1] == [{"row_index": 0, "is_petucha": False, "page_num": 1,
                           "fragments": [{"leading": [], "own": ["a", "b"], "trailing": []}]}]


def test_a_rows_own_setuma_fragments_stay_separate_within_one_verse():
    """The poetic "brick" case (e.g. Az Yashir/Shirat HaYam): a row can
    have more than one tikkun.io fragment entirely WITHIN a single
    verse's own span -- that gap must survive per fragment, not collapse
    into one flat run, or the rendered card loses the gap entirely."""
    rows = [([["a"], ["b", "c"], ["d"]], False, 1)]
    result = segment_rows_by_verse(rows, [4])
    assert result == [[
        {"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
            {"leading": [], "own": ["a"], "trailing": []},
            {"leading": [], "own": ["b", "c"], "trailing": []},
            {"leading": [], "own": ["d"], "trailing": []},
        ]},
    ]]


def test_a_verse_boundary_can_fall_inside_a_single_fragment_of_a_multi_fragment_row():
    # Row's own 2 fragments: fragment0 = "a b" (verse0's tail), fragment1
    # = "c d e" -- verse1 starts partway through fragment1 ("d","e"),
    # not at the fragment boundary.
    rows = [([["a", "b"], ["c", "d", "e"]], False, 1)]
    result = segment_rows_by_verse(rows, [3, 2])
    verse0, verse1 = result

    assert verse0 == [{"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
        {"leading": [], "own": ["a", "b"], "trailing": []},
        {"leading": [], "own": ["c"], "trailing": ["d", "e"]},
    ]}]
    assert verse1 == [{"row_index": 0, "is_petucha": False, "page_num": 1, "fragments": [
        {"leading": ["a", "b"], "own": [], "trailing": []},
        {"leading": ["c"], "own": ["d", "e"], "trailing": []},
    ]}]


# =============================================================
#  build_verse_cards_from_words -- field assembly
# =============================================================
def test_one_field_dict_per_verse():
    rows = [([["a"]], False, 1), ([["b"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 1), (1, 2)], [1, 1], None, title="T", box_width="5ch",
    )
    assert len(fields) == 2
    assert [f["Sequence"] for f in fields] == ["1", "2"]


def test_first_verse_uses_beginning_marker_when_no_preceding_row():
    rows = [([["a"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [1], None, title="T", box_width="5ch")
    assert '<div class="line beginning-marker">[Beginning]</div>' in fields[0]["FrontRows"]
    assert '<div class="line beginning-marker">[Beginning]</div>' in fields[0]["BackRows"]


def test_first_verse_uses_the_externally_fetched_preceding_row_when_given():
    rows = [([["b"]], False, 1)]
    preceding = ([["a"]], False, 1)
    fields = build_verse_cards_from_words(rows, [(1, 2)], [1], preceding, title="T", box_width="5ch")
    row_html = '<div class="line"><div class="column"><span class="fragment">a</span></div></div>'
    assert fields[0]["FrontRows"].startswith(row_html)
    assert fields[0]["BackRows"].startswith(row_html)


def test_later_verses_get_one_row_before_from_within_rows_itself():
    rows = [([["a"]], False, 1), ([["b"]], False, 1), ([["c"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 1), (1, 2), (1, 3)], [1, 1, 1], None, title="T", box_width="5ch",
    )
    # verse 2's context is verse 1's own row ("b"), found directly in rows.
    row_a = '<div class="line"><div class="column"><span class="fragment">a</span></div></div>'
    row_b = '<div class="line"><div class="column"><span class="fragment">b</span></div></div>'
    assert fields[1]["BackRows"].startswith(row_a)
    assert fields[2]["BackRows"].startswith(row_b)


def test_leading_extra_verses_excludes_a_prior_verses_bleed_from_the_first_card():
    """Regression: a card range's own first requested verse can start
    mid-row, sharing that row with the TAIL of the verse right before it
    (e.g. Exodus 20:1 sharing its row with 19:25's last word). Without
    accounting for that verse (passed here as the leading extra entry in
    verse_word_counts, discarded from the output), the alignment would
    wrongly eat that leading word into the first requested verse's own
    tested content -- see the module docstring."""
    # row0 = the excluded verse's own last word ("x") + verse0's own
    # first word ("a"); row1 = verse0's second word ("b"); row2 = verse1.
    rows = [([["x", "a"]], False, 1), ([["b"]], False, 1), ([["c"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 2), (1, 3)], [1, 2, 1], None, title="T", box_width="5ch",
        leading_extra_verses=1,
    )
    assert len(fields) == 2  # only verse_refs' own 2 verses get cards, not the excluded one

    # verse0's own card: "x" shows as plain leading context (never
    # cloze), "a"+"b" are its own tested content.
    assert '<span class="cloze-inline">a</span>' in fields[0]["BackRows"]
    assert '<span class="cloze-inline">b</span>' in fields[0]["BackRows"]
    assert '<span class="cloze-inline">x</span>' not in fields[0]["BackRows"]
    # "[Beginning]" still applies -- rows[0] (the excluded verse's own
    # row) has nothing before IT either in this tiny fixture.
    assert fields[0]["BackRows"] == (
        '<div class="line beginning-marker">[Beginning]</div>'
        '<div class="line"><div class="column"><span class="fragment">'
        'x <span class="cloze-inline">a</span></span></div></div>'
        '<div class="line"><div class="column"><span class="fragment">'
        '<span class="cloze-inline">b</span></span></div></div>'
    )


def test_front_hides_own_words_back_reveals_them():
    """Front and Back must carry the SAME literal words -- hiding is done
    with the "redacted" CSS class, not shorter placeholder text -- so a
    row's text-align: justify stretches identically on both sides (see
    verse_cards._render_split_fragment's docstring)."""
    rows = [([["a", "b"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [2], None, title="T", box_width="5ch")
    assert '<span class="cloze-inline">a b</span>' not in fields[0]["FrontRows"]
    assert '<span class="cloze-inline redacted">a b</span>' in fields[0]["FrontRows"]
    assert '<span class="cloze-inline">a b</span>' in fields[0]["BackRows"]


def test_shared_row_shows_context_words_plainly_alongside_the_cloze_span():
    rows = [([["a", "b", "c"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 1), (1, 2)], [1, 2], None, title="T", box_width="5ch",
    )
    # Verse 2 ("b","c") shares its row with verse 1's tail ("a"). Its own
    # first row is ALSO rows[0] (row index 0, same as verse 1's), so it
    # too falls back to the "[Beginning]" marker for its extra lookback
    # row (there's nothing before rows[0] in this tiny fixture).
    beginning = '<div class="line beginning-marker">[Beginning]</div>'
    back_row = (
        '<div class="line"><div class="column"><span class="fragment">'
        'a <span class="cloze-inline">b c</span></span></div></div>'
    )
    front_row = (
        '<div class="line"><div class="column"><span class="fragment">'
        'a <span class="cloze-inline redacted">b c</span></span></div></div>'
    )
    assert fields[1]["BackRows"] == beginning + back_row
    assert fields[1]["FrontRows"] == beginning + front_row


def test_trailing_context_is_masked_on_both_front_and_back():
    """The NEXT verse's own opening words, sharing THIS verse's own last
    row, must never appear as plain text on either side -- unlike
    leading context (already-recited, safe to show), showing the next
    verse's start here would spoil that verse's own card before the
    reader gets to it."""
    rows = [([["a", "b", "c"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 1), (1, 2)], [1, 2], None, title="T", box_width="5ch",
    )
    # Verse 1's own card: "a" is its own tested word, "b c" is verse 2's
    # opening -- masked, always, regardless of front/back.
    beginning = '<div class="line beginning-marker">[Beginning]</div>'
    assert fields[0]["BackRows"] == beginning + (
        '<div class="line"><div class="column"><span class="fragment">'
        '<span class="cloze-inline">a</span> <span class="cloze-inline masked">b c</span>'
        '</span></div></div>'
    )
    assert fields[0]["FrontRows"] == beginning + (
        '<div class="line"><div class="column"><span class="fragment">'
        '<span class="cloze-inline redacted">a</span> <span class="cloze-inline masked">b c</span>'
        '</span></div></div>'
    )


def test_petucha_row_gets_the_petucha_class():
    rows = [([["a"]], True, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [1], None, title="T", box_width="5ch")
    assert '<div class="line petucha">' in fields[0]["BackRows"]


def test_a_setuma_gap_within_one_verse_gets_the_setuma_class_and_a_real_gap():
    """The exact regression this was built for: a poetic "brick" gap
    (Az Yashir/Shirat HaYam, or the 'Aseret haDibberot) entirely within one
    verse's OWN tested content must still render as separate
    .fragment.setuma spans -- not collapse into one plain justified
    run -- so the CSS still draws the real gap tikkun.io itself does."""
    rows = [([["a"], ["b", "c"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [3], None, title="T", box_width="5ch")
    expected_back = (
        '<div class="line"><div class="column">'
        '<span class="fragment setuma"><span class="cloze-inline">a</span></span>'
        '<span class="fragment setuma"><span class="cloze-inline">b c</span></span>'
        "</div></div>"
    )
    assert expected_back in fields[0]["BackRows"]


def test_title_author_sequence_box_width_stamped_on_every_card():
    rows = [([["a"]], False, 1), ([["b"]], False, 1)]
    fields = build_verse_cards_from_words(
        rows, [(1, 1), (1, 2)], [1, 1], None, title="Verse test", author="Me", box_width="9ch",
    )
    assert all(f["Title"] == "Verse test" for f in fields)
    assert all(f["Author"] == "Me" for f in fields)
    assert all(f["BoxWidth"] == "9ch" for f in fields)


def test_field_dict_has_no_row_mode_fields():
    rows = [([["a"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [1], None, title="T", box_width="5ch")
    assert set(fields[0].keys()) == {"FrontRows", "BackRows", "Title", "Author", "Sequence", "BoxWidth"}


# =============================================================
#  'ammud breaks -- a verse's own tail crossing a physical column boundary
# =============================================================
def test_amud_break_inserted_between_own_rows_on_different_pages():
    """A verse whose own content spans two 'ammudim (its tail crosses onto
    the next physical scroll column) must show a visible break between
    the two rows, not silently splice them together as if they were
    still the same column."""
    rows = [([["a"]], False, 1), ([["b"]], False, 2)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [2], None, title="T", box_width="5ch")
    row_a = '<div class="line"><div class="column"><span class="fragment"><span class="cloze-inline">a'
    break_marker = '<div class="amud-break">[\'Ammud 2]</div>'
    assert row_a in fields[0]["BackRows"]
    assert break_marker in fields[0]["BackRows"]
    # The break sits strictly between the two rows.
    assert fields[0]["BackRows"].index(break_marker) > fields[0]["BackRows"].index(row_a)
    assert fields[0]["BackRows"].index(break_marker) < fields[0]["BackRows"].rindex("cloze-inline")


def test_no_amud_break_when_own_rows_share_a_page():
    rows = [([["a"]], False, 1), ([["b"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [2], None, title="T", box_width="5ch")
    assert "amud-break" not in fields[0]["BackRows"]


def test_amud_break_between_context_row_and_own_rows():
    """The context ("one row before") row can itself be on a different
    'ammud than the verse's own first row -- e.g. this verse is the very
    first verse tagged on its own 'ammud, so its lookback context is the
    previous 'ammud's own last row."""
    rows = [([["b"]], False, 2)]
    preceding = ([["a"]], False, 1)
    fields = build_verse_cards_from_words(rows, [(1, 1)], [1], preceding, title="T", box_width="5ch")
    assert '<div class="amud-break">[\'Ammud 2]</div>' in fields[0]["BackRows"]


def test_no_amud_break_against_the_beginning_marker():
    """The synthetic "[Beginning]" marker isn't a real row, so it must
    never trigger a break against it."""
    rows = [([["a"]], False, 1)]
    fields = build_verse_cards_from_words(rows, [(1, 1)], [1], None, title="T", box_width="5ch")
    assert "amud-break" not in fields[0]["BackRows"]
