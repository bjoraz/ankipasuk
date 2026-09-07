"""Tests for ankipasuk.webgui.api.Api.

Every method is a thin wrapper around already-tested core logic
(cloze.py, sefaria.py) -- these tests focus on the wrapping itself: does
the JSON-serializable shape returned to JS match what the frontend
expects, are errors reported as {"ok": False, "error": ...} rather than
raised, and is state (_current_verse_data, accumulated across fetches
and stamped per-verse with "book" rather than tracked as a single
Api-wide _current_book) threaded through correctly between calls.
"""

from ankipasuk.webgui.api import Api


def test_get_books_returns_categorized_dict():
    api = Api()
    books = api.get_books()
    assert "Genesis" in books["Torah"]
    assert "Deuteronomy" in books["Torah"]
    assert "Isaiah" in books["Nevi'im"]
    assert "I Samuel" in books["Nevi'im"]
    assert "Esther" in books["Megillot"]


def test_get_chapter_count_and_verse_count():
    api = Api()
    assert api.get_chapter_count("Genesis") == {"ok": True, "count": 50}
    assert api.get_verse_count("Genesis", 1) == {"ok": True, "count": 31}


def test_get_verse_count_out_of_range_chapter_is_safe():
    api = Api()
    # Doesn't raise -- returns a harmless default for an invalid chapter.
    assert api.get_verse_count("Genesis", 999) == {"ok": True, "count": 1}


def test_get_chapter_count_reports_error_for_unknown_book():
    api = Api()
    result = api.get_chapter_count("Not A Real Book")
    assert result["ok"] is False
    assert "error" in result


def test_generate_cloze_without_fetched_verses_reports_error():
    api = Api()
    result = api.generate_cloze(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_generate_cloze_matches_verse_to_nested_cloze(genesis_1_1):
    from ankipasuk.cloze import verse_to_nested_cloze

    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]

    result = api.generate_cloze(2, True)
    assert result["ok"] is True

    expected_cloze, _last, _tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=2)
    assert result["output"] == expected_cloze
    assert "viz-line" in result["viz_html"]


def test_generate_cloze_wraps_each_verse_for_spacing(genesis_1_1, genesis_1_2):
    """Each verse's rows must be wrapped in its own container so CSS can
    put a gap between verses without affecting the (smaller) gap between
    rows within the same verse."""
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_2, "plain": genesis_1_2},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert result["viz_html"].count('class="viz-verse"') == 2


def test_generate_cloze_skips_blank_lines(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": "   ", "plain": ""},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert result["output"].count("\n") == 0  # only one non-blank verse -> one line


def test_generate_cloze_reset_per_line_vs_continuous(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_1, "plain": genesis_1_1},
    ]
    reset = api.generate_cloze(2, True)
    continuous = api.generate_cloze(2, False)
    # With reset, both lines' cloze numbering starts at c1; without reset,
    # the second line continues from where the first left off.
    assert reset["output"].split("\n")[1].startswith("{{c1::") or "{{c1::" in reset["output"].split("\n")[1]
    assert "{{c1::" not in continuous["output"].split("\n")[1]


def test_fetch_chapter_verse_accumulates_across_calls_and_books(genesis_1_1, monkeypatch):
    """The core of the new multi-range feature: calling fetch_chapter_verse
    more than once appends rather than replaces, and different calls can
    name different books -- each verse keeps track of its own book."""
    api = Api()

    def fake_fetch(book, start_ch, start_vs, end_ch, end_vs, cache, version_param):
        return [{"book": book, "ch": start_ch, "vs": start_vs, "pointed": genesis_1_1, "plain": genesis_1_1}]

    monkeypatch.setattr("ankipasuk.webgui.api.fetch_verse_range", fake_fetch)

    first = api.fetch_chapter_verse("Genesis", 1, 1, 1, 1)
    assert first["ok"] is True
    assert len(first["verses"]) == 1

    second = api.fetch_chapter_verse("Isaiah", 6, 1, 6, 1)
    assert second["ok"] is True
    assert len(second["verses"]) == 2
    assert [v["book"] for v in second["verses"]] == ["Genesis", "Isaiah"]


def test_clear_ranges_empties_accumulated_verse_data(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]
    result = api.clear_ranges()
    assert result == {"ok": True, "verses": []}
    assert api._current_verse_data == []


def test_export_csv_without_fetched_verses_reports_error():
    api = Api()
    result = api.export_csv(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_export_csv_without_window_reports_error(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]
    api._window = None
    result = api.export_csv(2, True)
    assert result["ok"] is False


def test_export_csv_uses_each_verses_own_book_for_the_label(genesis_1_1, tmp_path):
    """A CSV built from a concatenated multi-book range must label each
    row with ITS OWN book, not one book for the whole export -- this is
    the specific regression the removal of a single Api-wide
    _current_book was meant to fix."""
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Isaiah", "ch": 6, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
    ]

    out_path = tmp_path / "cloze_cards.csv"

    class FakeWindow:
        def create_file_dialog(self, *a, **kw):
            return str(out_path)

    api._window = FakeWindow()
    result = api.export_csv(2, True)
    assert result["ok"] is True

    content = out_path.read_text(encoding="utf-8-sig")
    assert "Bereshit 1:1" in content
    assert "Yeshayahu 6:1" in content



def test_cache_status_text_reflects_stats():
    api = Api()
    status = api.get_cache_status()
    assert "Cache:" in status
    assert "ref(s)" in status
    assert "book structure(s)" in status

