"""Nested Anki cloze generation from a verse's disjunctive split tree."""

from __future__ import annotations

from itertools import count

from .text_processing import (
    group_into_units,
    split_segment,
    strip_vowels_and_trope,
    tokenize_pasuk,
)


def tree_depth(node) -> int:
    """Depth of the cloze split tree (0 = never split)."""
    if isinstance(node, dict):
        return 1 + max(tree_depth(node["left"]), tree_depth(node["right"]))
    return 0


def tree_leaf_count(node) -> int:
    """Number of leaves (clauses) the verse was split into."""
    if isinstance(node, dict):
        return tree_leaf_count(node["left"]) + tree_leaf_count(node["right"])
    return 1


def render_to_cloze_and_plain(node, counter):
    if isinstance(node, dict):
        l_m, l_p, _ = render_to_cloze_and_plain(node["left"], counter)
        r_m, r_p, _ = render_to_cloze_and_plain(node["right"], counter)
        plain = (l_p + " " + r_p).strip()
        n = next(counter)
        hint = strip_vowels_and_trope(plain)
        markup = f"{{{{c{n}::{l_m} {r_m}::{hint}}}}}"
        return markup, plain, n

    parts = []
    for u in node:
        parts.extend(t["text"] for t in u["subs"])
    plain = " ".join(parts)
    n = next(counter)
    hint = strip_vowels_and_trope(plain)
    markup = f"{{{{c{n}::{plain}::{hint}}}}}"
    return markup, plain, n


def verse_to_nested_cloze(pasuk: str, start_counter: int = 1, max_leaf_disj: int = 2):
    tokens = tokenize_pasuk(pasuk)
    units = group_into_units(tokens)
    tree = split_segment(units, max_leaf_disj=max_leaf_disj)
    counter = count(start_counter)
    markup, _, last_num = render_to_cloze_and_plain(tree, counter)
    return markup, last_num, tree, tokens, units
