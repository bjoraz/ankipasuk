from ankipasuk.stats import compute_corpus_stats, format_stats_summary, write_stats_csv
from ankipasuk.text_processing import strip_vowels_and_trope


def _verse_data(genesis_1_1, genesis_1_2):
    return [
        {"ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": strip_vowels_and_trope(genesis_1_1)},
        {"ch": 1, "vs": 2, "pointed": genesis_1_2, "plain": strip_vowels_and_trope(genesis_1_2)},
        # A second chapter, to exercise the by-chapter aggregation.
        {"ch": 2, "vs": 1, "pointed": genesis_1_1, "plain": strip_vowels_and_trope(genesis_1_1)},
    ]


def test_compute_corpus_stats_returns_none_for_empty_input():
    assert compute_corpus_stats([], max_leaf_disj=2) is None


def test_word_count_bins_reconcile_with_verse_count(genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)

    assert stats["n_verses"] == 3
    total_from_bins = sum(len(v) for v in stats["word_count_bins"].values())
    assert total_from_bins == stats["n_verses"]


def test_longest_and_shortest_are_consistent(genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)

    longest_words, longest_label = stats["longest"]
    shortest_words, shortest_label = stats["shortest"]
    assert longest_words >= shortest_words
    assert longest_label == "1:2"  # the 12-word verse
    assert shortest_label in ("1:1", "2:1")  # both are the 7-word verse


def test_chapter_aggregation_groups_correctly(genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)

    assert stats["chapters"] == [1, 2]
    assert set(stats["chapter_bins"][1]) == {"1:1", "1:2"}
    assert set(stats["chapter_bins"][2]) == {"2:1"}


def test_verse_lookup_contains_original_text(genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)

    assert stats["verse_lookup"]["1:1"]["pointed"] == genesis_1_1
    assert stats["verse_lookup"]["1:2"]["pointed"] == genesis_1_2


def test_format_stats_summary_is_non_empty(genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)
    summary = format_stats_summary(stats, max_leaf_disj=2)
    assert "Verses analyzed: 3" in summary
    assert "Disjunctive trope frequency" in summary


def test_write_stats_csv_has_one_row_per_verse(tmp_path, genesis_1_1, genesis_1_2):
    verse_data = _verse_data(genesis_1_1, genesis_1_2)
    stats = compute_corpus_stats(verse_data, max_leaf_disj=2)

    out_path = tmp_path / "stats.csv"
    write_stats_csv(out_path, stats, max_leaf_disj=2)

    lines = out_path.read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(lines) == 1 + stats["n_verses"]  # header + one row per verse
