"""Verse grammatical-nesting-structure analysis.

A verse's nesting structure is its cantillation-driven binary split tree
at ``max_leaf_disj=1`` (see :func:`ankipasuk.text_processing.split_segment`)
-- this *is* the traditional disjunctive-accent hierarchy, not an
approximation of it: the strongest disjunctive mark divides the verse
first, then the next-strongest *present* mark divides each resulting half,
and so on down to individual minimum-disjunctive units. Two verses have
"the same structure" iff their split trees, reduced to just the trope
levels that drove each split (see
:func:`ankipasuk.cloze.structure_signature`), are identical -- regardless
of whatever ``max_leaf_disj`` setting is actually used to generate cloze
cards elsewhere in the app.

Everything here is pure logic operating on the same
``{"ch", "vs", "pointed", ...}`` verse-data shape used throughout the app
(see :mod:`ankipasuk.stats`), with no GUI or network dependency -- usable
from a script, a test, or a future GUI panel alike.
"""

from __future__ import annotations

from collections import defaultdict

from .cloze import structure_signature
from .text_processing import group_into_units, split_segment, tokenize_pasuk

# The nesting structure is a fixed grammatical property of the verse, not
# a user-configurable card-splitting setting -- always computed at
# max_leaf_disj=1 regardless of what's used for actual cloze generation.
_STRUCTURE_MAX_LEAF_DISJ = 1


def verse_structure_signature(pointed: str):
    """The structure signature (see module docstring) of a single pointed
    verse."""
    tokens = tokenize_pasuk(pointed)
    units = group_into_units(tokens)
    tree = split_segment(units, max_leaf_disj=_STRUCTURE_MAX_LEAF_DISJ)
    return structure_signature(tree)


def _word_count_and_structure(pointed: str) -> tuple[int, object]:
    """Both the word count and structure signature of one verse, computed
    from a single tokenization pass (shared by
    :func:`group_verses_by_word_count_and_structure`, rather than
    tokenizing twice)."""
    tokens = tokenize_pasuk(pointed)
    units = group_into_units(tokens)
    tree = split_segment(units, max_leaf_disj=_STRUCTURE_MAX_LEAF_DISJ)
    return len(tokens), structure_signature(tree)


def signature_leaf_count(signature) -> int:
    """The number of leaves in a structure signature -- equivalently, the
    verse's minimum-disjunctive-group count. These are the same number
    for any real, complete verse: at ``max_leaf_disj=1``, splitting stops
    exactly when each leaf holds one disjunctive unit, so counting a
    signature's leaves *is* counting disjunctive groups -- no separate
    computation needed."""
    if isinstance(signature, tuple):
        return signature_leaf_count(signature[0]) + signature_leaf_count(signature[1])
    return 1


def group_verses_by_structure(verse_data: list[dict]) -> dict[tuple, list[str]]:
    """Group every verse in ``verse_data`` by its structure signature.

    Returns ``{signature: [verse_labels]}``, each verse labeled
    ``"ch:vs"`` in the order it appears in ``verse_data``.
    """
    groups: dict[tuple, list[str]] = defaultdict(list)
    for item in verse_data:
        pointed = item["pointed"].strip()
        if not pointed:
            continue
        sig = verse_structure_signature(pointed)
        groups[sig].append(f"{item['ch']}:{item['vs']}")
    return dict(groups)


def group_verses_by_word_count_and_structure(verse_data: list[dict]) -> dict[int, dict[tuple, list[str]]]:
    """Two-level grouping: word count -> structure signature -> verse
    labels sharing that (word count, structure) combination -- "which
    shapes occur among 7-word verses", etc."""
    out: dict[int, dict[tuple, list[str]]] = defaultdict(lambda: defaultdict(list))
    for item in verse_data:
        pointed = item["pointed"].strip()
        if not pointed:
            continue
        word_count, sig = _word_count_and_structure(pointed)
        out[word_count][sig].append(f"{item['ch']}:{item['vs']}")
    return {wc: dict(structs) for wc, structs in out.items()}


def group_verses_by_disj_count_and_structure(verse_data: list[dict]) -> dict[int, dict[tuple, list[str]]]:
    """Two-level grouping: minimum-disjunctive-group count -> structure
    signature -> verse labels sharing that combination -- "which shapes
    occur among verses with 5 disjunctive groups", etc.

    The group count is exactly a structure's leaf count (see
    :func:`signature_leaf_count`), so -- unlike the word-count grouping,
    where word count and structure are independent -- every structure
    that appears here appears under exactly one group-count bin. This
    still isn't a 1:1 mapping the other way: several *different*
    structures can share the same leaf count (e.g. ``((1, 2), 3)`` and
    ``(1, (2, 3))`` both have 3 leaves), which is exactly what makes this
    grouping useful on its own.
    """
    out: dict[int, dict[tuple, list[str]]] = defaultdict(dict)
    for sig, labels in group_verses_by_structure(verse_data).items():
        out[signature_leaf_count(sig)][sig] = labels
    return dict(out)


def verses_matching_structure(verse_data: list[dict], signature) -> list[str]:
    """All verse labels in ``verse_data`` whose structure signature is
    exactly ``signature``. Empty list if none match."""
    return group_verses_by_structure(verse_data).get(signature, [])


def structure_of_label(verse_data: list[dict], label: str):
    """The structure signature of the verse labeled ``label`` (e.g.
    ``"1:1"``) within ``verse_data``, or ``None`` if no such verse is
    present or its text is blank. The natural building block for a "find
    other verses shaped like this one" query:
    ``verses_matching_structure(verse_data, structure_of_label(verse_data, label))``.
    """
    for item in verse_data:
        if f"{item['ch']}:{item['vs']}" == label:
            pointed = item["pointed"].strip()
            return verse_structure_signature(pointed) if pointed else None
    return None


def structure_summary(verse_data: list[dict]) -> list[tuple]:
    """``(signature, [verse_labels])`` pairs, most-shared structure first
    (ties broken by the signature's string rendering, for a stable order)
    -- the natural entry point for browsing "which shapes actually
    recur", since with a large enough range most individual signatures
    are unique to one verse and not interesting on their own.
    """
    groups = group_verses_by_structure(verse_data)
    # Tiebreak on the formatted string, not the raw signature: a signature
    # can be a bare int (an unsplit, single-leaf verse) or a tuple (a
    # split verse), and those aren't mutually comparable in Python, so
    # sorting on the signature itself can raise on a tie between the two
    # shapes.
    return sorted(groups.items(), key=lambda kv: (-len(kv[1]), format_structure(kv[0])))


def format_structure(signature) -> str:
    """A compact, human-readable rendering of a structure signature, e.g.
    ``((3, 1), 2)`` -> ``"((L3 L1) L2)"``."""
    if isinstance(signature, tuple):
        return f"({format_structure(signature[0])} {format_structure(signature[1])})"
    return f"L{signature}"
