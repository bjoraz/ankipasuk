"""Tests for ankipasuk.lpcg.build_lpcg_fields / group_lines.

The expected windowing behavior is taken directly from AnkiLPCG's own
documentation (https://ankilpcg.readthedocs.io/en/latest/importing.html),
since this module is an independent reimplementation of it.
"""

import pytest

from ankipasuk.lpcg import FIELD_NAMES, build_lpcg_fields, group_lines, render_scroll_html


def _row(text: str, extra_class: str = "") -> str:
    """A plain-string line's expected rendering: its own block-level div,
    wrapped in the column/fragment markup CSS hooks the justify trick to."""
    classes = "line" + (f" {extra_class}" if extra_class else "")
    inner = f'<div class="column"><span class="fragment">{text}</span></div>'
    return f'<div class="{classes}">{inner}</div>'


def _beginning_row() -> str:
    return '<div class="line beginning-marker">[Beginning]</div>'


def test_group_lines_default_size_one_is_a_noop():
    assert group_lines(["a", "b", "c"], 1) == [["a"], ["b"], ["c"]]


def test_group_lines_groups_and_keeps_a_short_final_group():
    assert group_lines(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]


def test_group_lines_rejects_size_below_one():
    with pytest.raises(ValueError):
        group_lines(["a"], 0)


def test_field_dict_has_every_expected_field():
    # build_lpcg_fields only ever populates its own row-mode fields --
    # "FrontRows"/"BackRows" (ankipasuk.verse_cards's verse-mode fields)
    # are left unset, which is fine: AnkiConnect defaults an omitted
    # field to empty, and the card template's {{^FrontRows}} section
    # falls back to this row-mode rendering exactly when it's empty.
    fields = build_lpcg_fields(["a", "b"], title="T")
    assert set(fields[0].keys()) == {"Line", "Context", "Prompt", "Title", "Author", "Sequence", "BoxWidth"}
    assert set(fields[0].keys()) <= set(FIELD_NAMES)


def test_sequence_numbers_are_one_based_and_consecutive():
    fields = build_lpcg_fields(["a", "b", "c"], title="T")
    assert [f["Sequence"] for f in fields] == ["1", "2", "3"]


def test_first_card_context_is_beginning_only():
    fields = build_lpcg_fields(["a", "b", "c"], title="T", context_lines=2)
    assert fields[0]["Context"] == _beginning_row()
    assert fields[0]["Line"] == _row("a", "cloze")


def test_second_card_context_is_beginning_plus_one_line_when_not_enough_yet():
    fields = build_lpcg_fields(["a", "b", "c"], title="T", context_lines=2)
    assert fields[1]["Context"] == _beginning_row() + _row("a")
    assert fields[1]["Line"] == _row("b", "cloze")


def test_third_card_onward_has_full_sliding_window_no_beginning_marker():
    fields = build_lpcg_fields(["a", "b", "c", "d"], title="T", context_lines=2)
    assert fields[2]["Context"] == _row("a") + _row("b")
    assert fields[2]["Line"] == _row("c", "cloze")
    assert fields[3]["Context"] == _row("b") + _row("c")
    assert fields[3]["Line"] == _row("d", "cloze")
    assert "[Beginning]" not in fields[2]["Context"]
    assert "[Beginning]" not in fields[3]["Context"]


def test_single_line_recite_has_no_prompt():
    fields = build_lpcg_fields(["a", "b"], title="T", recite_lines=1)
    assert fields[0]["Prompt"] == ""


def test_multi_line_recite_gets_bracketed_count_prompt():
    fields = build_lpcg_fields(["a", "b", "c", "d"], title="T", recite_lines=2)
    assert fields[0]["Line"] == _row("a", "cloze") + _row("b", "cloze")
    assert fields[0]["Prompt"] == "[...2]"


def test_recite_lines_truncates_gracefully_at_the_end():
    """One card is still generated per physical line (LPCG's card count
    is anchored to lines, not to recite_lines-sized chunks) -- but the
    last card's recitation window runs past the end of the text, so it
    recites whatever's left, with the prompt count adjusted accordingly."""
    fields = build_lpcg_fields(["a", "b", "c"], title="T", recite_lines=2)
    assert len(fields) == 3
    assert fields[0]["Line"] == _row("a", "cloze") + _row("b", "cloze")
    assert fields[0]["Prompt"] == "[...2]"
    assert fields[1]["Line"] == _row("b", "cloze") + _row("c", "cloze")
    assert fields[2]["Line"] == _row("c", "cloze")
    assert fields[2]["Prompt"] == ""  # only 1 line left to recite


def test_title_and_author_are_stamped_on_every_card():
    fields = build_lpcg_fields(["a", "b"], title="Aliyah 1", author="Me")
    assert all(f["Title"] == "Aliyah 1" for f in fields)
    assert all(f["Author"] == "Me" for f in fields)


def test_lines_may_contain_html_without_being_treated_as_a_comment():
    """Unlike AnkiLPCG's own comment-stripping preprocessing, this module
    does no text munging -- a '#' in styled HTML (e.g. a hex color) must
    survive untouched."""
    styled = '<span style="color:#3366cc">בְּרֵאשִׁית</span>'
    fields = build_lpcg_fields([styled], title="T")
    assert "#3366cc" in fields[0]["Line"]


def test_group_size_greater_than_one_groups_physical_lines_together():
    fields = build_lpcg_fields(["a", "b", "c", "d"], title="T", group_size=2, context_lines=1, recite_lines=1)
    assert fields[0]["Line"] == _row("a", "cloze") + _row("b", "cloze")
    assert fields[1]["Context"] == _row("a") + _row("b")
    assert fields[1]["Line"] == _row("c", "cloze") + _row("d", "cloze")


def test_box_width_is_the_same_on_every_card_from_the_longest_line():
    fields = build_lpcg_fields(["ab", "a" * 50], title="T")
    assert fields[0]["BoxWidth"] == fields[1]["BoxWidth"] == "45ch"  # round(50 * 0.9)


def test_box_width_has_a_floor_for_short_content():
    fields = build_lpcg_fields(["ab", "abcdefghij"], title="T")
    assert fields[0]["BoxWidth"] == fields[1]["BoxWidth"] == "40ch"  # MIN_BOX_WIDTH_CH floor


def test_render_scroll_html_wraps_lines_in_a_shared_width_box():
    html = render_scroll_html(["a", "b"])
    style = "width: calc(40ch * var(--ankipasuk-width-scale, 1))"
    assert html == f'<div class="lines" style="{style}">{_row("a")}{_row("b")}</div>'


def test_render_scroll_html_marks_a_petucha_line_unjustified():
    html = render_scroll_html([
        {"html": "<span>a</span>", "is_petucha": True, "char_count": 1},
    ])
    assert '<div class="line petucha">' in html


def test_render_scroll_html_empty_lines_gives_an_empty_string():
    assert render_scroll_html([]) == ""
