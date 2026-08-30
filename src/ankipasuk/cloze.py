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


def structure_signature(node):
    """Canonical, hashable signature of a split tree's shape, reduced to
    just the trope *levels* that drove each split.

    A leaf (a list of disjunctive units, as produced by
    :func:`ankipasuk.text_processing.group_into_units`) is represented as
    its terminal disjunctive level -- an int 1-4, or 0 only in the
    degenerate case of a fragment with no disjunctive at all (never
    happens for a real, complete verse, which always ends in Sof Pasuq).
    An internal node is a 2-tuple ``(left_signature, right_signature)``.

    Two verses have "the same structure" iff their signatures compare
    equal -- this is exactly the traditional cantillation hierarchy when
    the tree comes from ``split_segment(units, max_leaf_disj=1)``: the
    strongest disjunctive divides the verse first, then the next-strongest
    *present* mark divides each half, and so on down to individual
    minimum-disjunctive units. See :mod:`ankipasuk.structure`.
    """
    if isinstance(node, dict):
        return (structure_signature(node["left"]), structure_signature(node["right"]))
    return node[-1]["level"] if node else 0


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
