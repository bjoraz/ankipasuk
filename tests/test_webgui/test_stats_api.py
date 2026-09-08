"""Tests for ankipasuk.webgui.stats_api.StatsApi."""

from ankipasuk.webgui.stats_api import StatsApi


def _verse_data(entries):
    return [{"book": "Genesis", "ch": ch, "vs": vs, "pointed": text, "plain": ""} for ch, vs, text in entries]


def test_get_summary_matches_format_stats_summary(genesis_1_1):
    from ankipasuk.stats import compute_corpus_stats, format_stats_summary

    verse_data = _verse_data([(1, 1, genesis_1_1)])
    sapi = StatsApi(verse_data, max_leaf_disj=2)

    expected_stats = compute_corpus_stats(verse_data, 2)
    assert sapi.get_summary() == format_stats_summary(expected_stats, 2)


def test_get_verse_lookup_contains_fetched_verse(genesis_1_1):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1)]), max_leaf_disj=2)
    lookup = sapi.get_verse_lookup()
    assert "Genesis 1:1" in lookup
    assert lookup["Genesis 1:1"]["pointed"] == genesis_1_1


def test_get_distributions_shape(genesis_1_1, genesis_1_2):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)]), max_leaf_disj=2)
    dist = sapi.get_distributions()
    assert set(dist.keys()) == {"word_count", "disj_count", "clause_count", "depth", "ratio", "max_leaf_disj"}
    assert dist["max_leaf_disj"] == 2
    for bar in dist["word_count"]:
        assert set(bar.keys()) == {"key", "count", "verses"}


def test_get_distributions_on_empty_data_returns_empty_dict():
    sapi = StatsApi([], max_leaf_disj=2)
    assert sapi.get_distributions() == {}
    assert sapi.get_summary() == "No verses to analyze."


def test_get_trope_frequency_sorted_descending(genesis_1_1, genesis_1_2):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)]), max_leaf_disj=2)
    tropes = sapi.get_trope_frequency()
    counts = [t["count"] for t in tropes]
    assert counts == sorted(counts, reverse=True)


def test_get_structure_by_word_count_groups_correctly(genesis_1_1):
    verse_data = _verse_data([(1, 1, genesis_1_1), (5, 3, genesis_1_1)])  # same text, same shape
    sapi = StatsApi(verse_data, max_leaf_disj=2)
    groups = sapi.get_structure_by_word_count()
    assert len(groups) == 1  # both verses have 7 words
    assert groups[0]["axis_value"] == 7
    assert sorted(groups[0]["structures"][0]["verses"]) == ["Genesis 1:1", "Genesis 5:3"]


def test_get_structure_summary_ranked_by_frequency(genesis_1_1, genesis_1_2):
    verse_data = _verse_data([
        (1, 1, genesis_1_1), (5, 1, genesis_1_1), (5, 2, genesis_1_1), (1, 2, genesis_1_2),
    ])
    sapi = StatsApi(verse_data, max_leaf_disj=2)
    summary = sapi.get_structure_summary()
    assert summary[0]["count"] == 3  # genesis_1_1's shape appears 3 times, must be first


def test_get_chapter_data_shape(genesis_1_1):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1)]), max_leaf_disj=2)
    data = sapi.get_chapter_data()
    assert data["chapters"][0]["book"] == "Genesis"
    assert data["chapters"][0]["chapter"] == 1
    assert data["chapters"][0]["avg_words"] == 7.0


def test_get_chapter_data_does_not_merge_same_chapter_number_across_books(genesis_1_1, genesis_1_2):
    """The actual regression this whole book/chapter-key change exists to
    fix: before, chapter_bins was keyed by bare chapter number, so
    "chapter 1" from two different books would silently combine into one
    bucket -- a verse from Isaiah 1 would show up (and get averaged in)
    under what looked like Genesis's chapter-1 bar, and vice versa."""
    verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": ""},
        {"book": "Isaiah", "ch": 1, "vs": 1, "pointed": genesis_1_2, "plain": ""},
    ]
    sapi = StatsApi(verse_data, max_leaf_disj=2)
    data = sapi.get_chapter_data()

    assert len(data["chapters"]) == 2  # NOT merged into a single "chapter 1"
    by_book = {c["book"]: c for c in data["chapters"]}
    assert by_book["Genesis"]["chapter"] == 1
    assert by_book["Genesis"]["verses"] == ["Genesis 1:1"]
    assert by_book["Isaiah"]["chapter"] == 1
    assert by_book["Isaiah"]["verses"] == ["Isaiah 1:1"]
    # And each book's own average reflects only its own verse, not a
    # blend of both -- genesis_1_1 and genesis_1_2 are different lengths.
    assert by_book["Genesis"]["avg_words"] != by_book["Isaiah"]["avg_words"]


def test_export_csv_without_window_reports_error(genesis_1_1):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1)]), max_leaf_disj=2)
    sapi._window = None
    result = sapi.export_csv()
    assert result["ok"] is False
