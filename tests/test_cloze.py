import re

from ankipasuk.cloze import structure_signature, tree_depth, tree_leaf_count, verse_to_nested_cloze
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


def test_structure_signature_leaf_is_terminal_disjunctive_level(genesis_1_1):
    _markup, _last, _tree, tokens, units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=100)
    # No split at all -> the whole verse is one leaf; its signature is the
    # level of its last (verse-final, Sof Pasuq) disjunctive unit.
    assert structure_signature(units) == units[-1]["level"] == 1


def test_structure_signature_internal_node_is_pair_of_child_signatures(genesis_1_2):
    _markup, _last, tree, _tokens, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    assert isinstance(tree, dict)
    sig = structure_signature(tree)
    assert sig == (structure_signature(tree["left"]), structure_signature(tree["right"]))


def test_structure_signature_identical_for_identical_shapes(genesis_1_1):
    # Splitting the same verse twice must yield the same signature -- the
    # whole point is that it's a stable, hashable, comparable value.
    _markup1, _last1, tree1, *_ = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=1)
    _markup2, _last2, tree2, *_ = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=1)
    assert structure_signature(tree1) == structure_signature(tree2)
    assert hash(structure_signature(tree1)) == hash(structure_signature(tree2))
