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


def test_get_trope_frequency_by_rank_then_count_with_hebrew_names(genesis_1_1, genesis_1_2):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)]), max_leaf_disj=2)
    tropes = sapi.get_trope_frequency()
    order = [(t["rank"], -t["count"]) for t in tropes]
    assert order == sorted(order)
    by_name = {t["name"]: t for t in tropes}
    assert by_name["Sof pasuq"]["rank"] == 1
    assert by_name["Sof pasuq"]["hebrew"] == "סוף פסוק"


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
    # Each shape is shown as its first pasuq's diagram.
    assert summary[0]["example"]["ref"] == "Bereshit 1:1"
    assert summary[0]["example"]["diagram"]["units"]


def test_export_csv_without_window_reports_error(genesis_1_1):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1)]), max_leaf_disj=2)
    sapi._window = None
    result = sapi.export_csv()
    assert result["ok"] is False


def test_get_diagrams_in_the_order_asked_skipping_unknown_labels(genesis_1_1, genesis_1_2):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)]), max_leaf_disj=2, font_css="x")
    out = sapi.get_diagrams(["Genesis 1:2", "Genesis 9:9", "Genesis 1:1"])
    assert [d["ref"] for d in out] == ["Bereshit 1:2", "Bereshit 1:1"]
    assert all(d["diagram"]["units"] for d in out)
    assert sapi.get_font_css() == "x"


def test_ratio_bars_fill_every_tenth_between_the_extremes():
    from collections import Counter

    from ankipasuk.webgui.stats_api import _ratio_bars

    bars = _ratio_bars(Counter({1.2: 2, 1.5: 1}), {1.2: ["a", "b"], 1.5: ["c"]})
    assert [(b["key"], b["count"]) for b in bars] == [("1.2", 2), ("1.3", 0), ("1.4", 0), ("1.5", 1)]
    assert bars[1]["verses"] == []


def test_shorashim_most_frequent_first_and_their_pesuqim(genesis_1_1, genesis_1_2):
    sapi = StatsApi(_verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)]), max_leaf_disj=2)
    rows = sapi.get_shorashim()
    counts = [r["count"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    earth = next(r for r in rows if r["display"] == "א־ר־צ")  # הָאָרֶץ, in both pesuqim
    assert (earth["count"], earth["pesuqim"]) == (2, 2)
    assert earth["total"] > 2000 and earth["ratio"] > 1 and "keyness" in earth
    verses = sapi.get_shorashim_verses(earth["g"])
    assert [v["ref"] for v in verses] == ["Bereshit 1:1", "Bereshit 1:2"]
    assert any(w[2] == earth["g"] for w in verses[0]["words"])
