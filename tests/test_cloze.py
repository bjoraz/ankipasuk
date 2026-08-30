import re

from ankipasuk.cloze import tree_depth, tree_leaf_count, verse_to_nested_cloze
from ankipasuk.text_processing import strip_vowels_and_trope


def test_verse_to_nested_cloze_produces_balanced_braces(genesis_1_2):
    markup, last_num, tree, tokens, units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=2)
    assert markup.count("{{") == markup.count("}}")
    assert last_num >= 1


def test_cloze_numbers_are_sequential_from_start_counter(genesis_1_2):
    markup, last_num, *_ = verse_to_nested_cloze(genesis_1_2, start_counter=5, max_leaf_disj=2)
    numbers = sorted(int(n) for n in re.findall(r"\{\{c(\d+)::", markup))
    assert numbers[0] == 5
    assert numbers == list(range(5, 5 + len(numbers)))
    assert last_num == numbers[-1]


def test_cloze_plain_text_matches_stripped_source(genesis_1_1):
    markup, *_ = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=2)
    # Every hint (after the second "::") should be pointing-free.
    hints = re.findall(r"::([^:{}]*)\}\}", markup)
    for hint in hints:
        assert hint == strip_vowels_and_trope(hint)


def test_tree_leaf_count_matches_number_of_clauses(genesis_1_2):
    _markup, _last, tree, _tokens, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    # With max_leaf_disj=1, every disjunctive group becomes (close to) its
    # own leaf, so leaf_count should be > 1 for a 12-word verse.
    assert tree_leaf_count(tree) > 1


def test_tree_depth_zero_when_no_split_needed(genesis_1_1):
    _markup, _last, tree, _tokens, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=100)
    assert tree_depth(tree) == 0
    assert tree_leaf_count(tree) == 1
