from ankipasuk.text_processing import (
    disj_count,
    group_into_units,
    split_segment,
    strip_vowels_and_trope,
    tokenize_pasuk,
)


def test_tokenize_word_count(genesis_1_1):
    tokens = tokenize_pasuk(genesis_1_1)
    assert len(tokens) == 7


def test_tokenize_assigns_disjunctive_levels(genesis_1_1):
    tokens = tokenize_pasuk(genesis_1_1)
    # first word has no trope mark at all -> conjunctive (level 0)
    assert tokens[0]["level"] == 0
    # last word carries Sof Pasuq -> level 1
    assert tokens[-1]["level"] == 1
    assert tokens[-1]["trope_name"] == "Sof pasuq"


def test_munach_legarmeh_upgrade(munach_legarmeh_verse):
    tokens = tokenize_pasuk(munach_legarmeh_verse)
    # word 1 (index 1) should be upgraded to level 4 and flagged
    assert tokens[1]["is_legarmeh"] is True
    assert tokens[1]["level"] == 4
    assert tokens[1]["trope_name"] == "Munach legarmeh"


def test_group_into_units_covers_all_words(genesis_1_1):
    tokens = tokenize_pasuk(genesis_1_1)
    units = group_into_units(tokens)
    total_words_in_units = sum(len(u["subs"]) for u in units)
    assert total_words_in_units == len(tokens)


def test_disj_count_matches_disjunctive_tokens(genesis_1_2):
    tokens = tokenize_pasuk(genesis_1_2)
    units = group_into_units(tokens)
    expected = sum(1 for t in tokens if 1 <= t["level"] <= 4)
    assert disj_count(units) == expected


def test_split_segment_respects_max_leaf_disj(genesis_1_2):
    tokens = tokenize_pasuk(genesis_1_2)
    units = group_into_units(tokens)

    def leaf_disj_counts(node):
        if isinstance(node, dict):
            return leaf_disj_counts(node["left"]) + leaf_disj_counts(node["right"])
        return [disj_count(node)]

    for max_leaf in (1, 2, 3):
        tree = split_segment(units, max_leaf_disj=max_leaf)
        for count in leaf_disj_counts(tree):
            assert count <= max_leaf


def test_split_segment_no_split_needed_returns_units_unchanged(genesis_1_1):
    tokens = tokenize_pasuk(genesis_1_1)
    units = group_into_units(tokens)
    # A very generous max_leaf_disj should never trigger a split.
    tree = split_segment(units, max_leaf_disj=100)
    assert tree is units


def test_strip_vowels_and_trope_removes_marks(genesis_1_1):
    plain = strip_vowels_and_trope(genesis_1_1)
    # No leftover combining marks (nikud/trope) should remain.
    import unicodedata
    normalized = unicodedata.normalize("NFD", plain)
    assert not any(unicodedata.category(ch) == "Mn" for ch in normalized)
    # Word count should be preserved.
    assert len(plain.split()) == len(genesis_1_1.split())
