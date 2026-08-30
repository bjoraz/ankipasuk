"""Tests for ankipasuk.structure and the structure_signature part of
ankipasuk.cloze.

The exact signature values asserted below were computed by running the
actual code against the shared fixtures (see conftest.py), not derived by
hand, then locked in as regression values.
"""

from ankipasuk import structure as st


def test_verse_structure_signature_bereshit(genesis_1_1):
    assert st.verse_structure_signature(genesis_1_1) == ((3, 1), (2, (2, (2, 1))))


def test_verse_structure_signature_longer_verse(genesis_1_2):
    sig = st.verse_structure_signature(genesis_1_2)
    assert sig == (((3, 2), ((3, (3, 2)), (3, (3, 1)))), ((3, (3, 2)), 1))


def test_verse_structure_signature_short_verse(munach_legarmeh_verse):
    assert st.verse_structure_signature(munach_legarmeh_verse) == (3, (3, 1))


def test_verse_structure_signature_is_independent_of_cloze_splitting_setting(genesis_1_1):
    # Nesting structure is a fixed grammatical property, not affected by
    # whatever max_leaf_disj a user has chosen for actual card generation
    # -- verse_structure_signature doesn't even take that as a parameter.
    import inspect
    assert "max_leaf_disj" not in inspect.signature(st.verse_structure_signature).parameters


def _verse_data(entries):
    """entries: list of (ch, vs, pointed_text)."""
    return [{"ch": ch, "vs": vs, "pointed": text, "plain": ""} for ch, vs, text in entries]


def test_group_verses_by_structure_groups_identical_shapes(genesis_1_1, genesis_1_2):
    verse_data = _verse_data([
        (1, 1, genesis_1_1),
        (1, 2, genesis_1_2),
        (5, 3, genesis_1_1),  # same text/shape as 1:1, different label
    ])
    groups = st.group_verses_by_structure(verse_data)

    bereshit_sig = st.verse_structure_signature(genesis_1_1)
    assert sorted(groups[bereshit_sig]) == ["1:1", "5:3"]

    other_sig = st.verse_structure_signature(genesis_1_2)
    assert groups[other_sig] == ["1:2"]
    assert len(groups) == 2


def test_group_verses_by_structure_skips_blank_verses(genesis_1_1):
    verse_data = _verse_data([(1, 1, genesis_1_1), (1, 2, "  ")])
    groups = st.group_verses_by_structure(verse_data)
    assert sum(len(labels) for labels in groups.values()) == 1


def test_verses_matching_structure(genesis_1_1, genesis_1_2):
    verse_data = _verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2), (5, 3, genesis_1_1)])
    sig = st.verse_structure_signature(genesis_1_1)
    assert sorted(st.verses_matching_structure(verse_data, sig)) == ["1:1", "5:3"]


def test_verses_matching_structure_returns_empty_for_unknown_signature(genesis_1_1):
    verse_data = _verse_data([(1, 1, genesis_1_1)])
    assert st.verses_matching_structure(verse_data, ("no", "such", "shape")) == []


def test_structure_of_label(genesis_1_1, genesis_1_2):
    verse_data = _verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2)])
    assert st.structure_of_label(verse_data, "1:1") == st.verse_structure_signature(genesis_1_1)
    assert st.structure_of_label(verse_data, "1:2") == st.verse_structure_signature(genesis_1_2)


def test_structure_of_label_missing_or_blank(genesis_1_1):
    verse_data = _verse_data([(1, 1, genesis_1_1), (1, 2, "  ")])
    assert st.structure_of_label(verse_data, "9:9") is None  # not present
    assert st.structure_of_label(verse_data, "1:2") is None  # blank text


def test_find_other_verses_shaped_like_this_one_workflow(genesis_1_1, genesis_1_2):
    """The intended end-to-end usage: given one verse's label, find every
    other verse in the range sharing its exact structure."""
    verse_data = _verse_data([(1, 1, genesis_1_1), (1, 2, genesis_1_2), (5, 3, genesis_1_1)])
    sig = st.structure_of_label(verse_data, "1:1")
    matches = st.verses_matching_structure(verse_data, sig)
    assert sorted(matches) == ["1:1", "5:3"]


def test_structure_summary_orders_by_frequency_then_signature(
    genesis_1_1, genesis_1_2, munach_legarmeh_verse
):
    verse_data = _verse_data([
        (1, 1, genesis_1_1),
        (1, 2, genesis_1_2),
        (1, 3, munach_legarmeh_verse),
        (5, 1, genesis_1_1),
        (5, 2, genesis_1_1),
    ])
    summary = st.structure_summary(verse_data)

    # genesis_1_1's shape appears 3 times -- must be first.
    top_sig, top_labels = summary[0]
    assert top_sig == st.verse_structure_signature(genesis_1_1)
    assert sorted(top_labels) == ["1:1", "5:1", "5:2"]

    # The other two shapes each appear once; total accounted for.
    assert sum(len(labels) for _sig, labels in summary) == 5
    assert len(summary) == 3


def test_format_structure_leaf():
    assert st.format_structure(3) == "L3"


def test_format_structure_nested():
    assert st.format_structure(((3, 1), 2)) == "((L3 L1) L2)"
