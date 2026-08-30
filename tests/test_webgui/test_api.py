"""Tests for ankipasuk.webgui.api.Api.

Every method is a thin wrapper around already-tested core logic
(cloze.py, sefaria.py) -- these tests focus on the wrapping itself: does
the JSON-serializable shape returned to JS match what the frontend
expects, are errors reported as {"ok": False, "error": ...} rather than
raised, and is state (current_verse_data, current_book) threaded through
correctly between calls.
"""

from ankipasuk.webgui.api import Api


def test_get_books_returns_torah_books():
    api = Api()
    books = api.get_books()
    assert "Genesis" in books
    assert "Deuteronomy" in books


def test_get_chapter_count_and_verse_count():
    api = Api()
    assert api.get_chapter_count("Genesis") == 50
    assert api.get_verse_count("Genesis", 1) == 31


def test_get_verse_count_out_of_range_chapter_is_safe():
    api = Api()
    # Doesn't raise -- returns a harmless default for an invalid chapter.
    assert api.get_verse_count("Genesis", 999) == 1


def test_generate_cloze_without_fetched_verses_reports_error():
    api = Api()
    result = api.generate_cloze(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_generate_cloze_matches_verse_to_nested_cloze(genesis_1_1):
    from ankipasuk.cloze import verse_to_nested_cloze

    api = Api()
    api.current_verse_data = [{"ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}]

    result = api.generate_cloze(2, True)
    assert result["ok"] is True

    expected_cloze, _last, _tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=2)
    assert result["output"] == expected_cloze
    assert "viz-line" in result["viz_html"]


def test_generate_cloze_skips_blank_lines(genesis_1_1):
    api = Api()
    api.current_verse_data = [
        {"ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"ch": 1, "vs": 2, "pointed": "   ", "plain": ""},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert result["output"].count("\n") == 0  # only one non-blank verse -> one line


def test_generate_cloze_reset_per_line_vs_continuous(genesis_1_1):
    api = Api()
    api.current_verse_data = [
        {"ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"ch": 1, "vs": 2, "pointed": genesis_1_1, "plain": genesis_1_1},
    ]
    reset = api.generate_cloze(2, True)
    continuous = api.generate_cloze(2, False)
    # With reset, both lines' cloze numbering starts at c1; without reset,
    # the second line continues from where the first left off.
    assert reset["output"].split("\n")[1].startswith("{{c1::") or "{{c1::" in reset["output"].split("\n")[1]
    assert "{{c1::" not in continuous["output"].split("\n")[1]


def test_export_csv_without_fetched_verses_reports_error():
    api = Api()
    result = api.export_csv(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_export_csv_without_window_reports_error(genesis_1_1):
    api = Api()
    api.current_verse_data = [{"ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}]
    api.current_book = "Genesis"
    api.window = None
    result = api.export_csv(2, True)
    assert result["ok"] is False


def test_cache_status_text_reflects_stats():
    api = Api()
    status = api.get_cache_status()
    assert "Cache:" in status
    assert "ref(s)" in status
    assert "book structure(s)" in status
