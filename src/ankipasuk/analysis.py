"""What each cloze on a pasuq's note covers, and why it was split there.

The split tree (see :func:`ankipasuk.text_processing.split_segment`) is
what the cloze export numbers, post-order, so the whole pasuq is always
the last cloze. This walks the same tree in the same order and, for each
cloze, records the words it covers and the mafsiq behind it: for a clause
(a leaf), the ta'am it ends on; for a merged cloze, the mafsiq it was
split after -- the strongest one inside it, first occurrence winning
ties. That's the information the app's analysis view shows, and the
numbers match the exported ``{{cN::...}}`` markup exactly (see
tests/test_analysis.py).

Pure logic, like :mod:`ankipasuk.structure`: no GUI, no network.
"""

from __future__ import annotations

import unicodedata
from itertools import count

from .config import AZLA, QADMA, TERE_QADMIN_NAME


def _units(node) -> list[dict]:
    if isinstance(node, dict):
        return _units(node["left"]) + _units(node["right"])
    return list(node)


def _text(node) -> str:
    return " ".join(sub["text"] for u in _units(node) for sub in u["subs"])


def _closing_taam(unit: dict) -> dict | None:
    """The mafsiq that closes ``unit``: its word, ta'am name and rank.
    ``None`` for a unit with no mafsiq (only ever a fragment, never a
    real pasuq, which ends on sof pasuq)."""
    if not 1 <= unit["level"] <= 4:
        return None
    word = next(sub["text"] for sub in reversed(unit["subs"]) if sub["level"] == unit["level"])
    name = unit.get("trope_name")
    marks = unicodedata.normalize("NFD", word)
    if QADMA in marks and AZLA in marks:
        name = TERE_QADMIN_NAME  # qadma doubled: same ta'am, its usual name
    return {"word": word, "name": name, "rank": unit["level"]}


def cloze_breakdown(tree, start_counter: int = 1) -> list[dict]:
    """One entry per cloze, in cloze-number order.

    Each entry has ``n`` (the cloze number), ``depth`` (0 for the whole
    pasuq), ``text`` (the pointed words it covers) and ``kind``:

    - ``"clause"``: a leaf of the tree, with ``ends_on`` -- the mafsiq it
      ends on, as ``{"word", "name", "rank"}``, or ``None``.
    - ``"split"``: a merged cloze, with ``split_after`` -- the mafsiq its
      two halves were divided after, in the same shape.

    ``start_counter`` is the first cloze number, as for
    :func:`ankipasuk.cloze.verse_to_nested_cloze`.
    """
    rows: list[dict] = []
    counter = count(start_counter)

    def walk(node, depth: int) -> None:
        if isinstance(node, dict):
            walk(node["left"], depth + 1)
            walk(node["right"], depth + 1)
            rows.append({
                "n": next(counter), "depth": depth, "kind": "split", "text": _text(node),
                "split_after": _closing_taam(_units(node["left"])[-1]),
            })
        else:
            rows.append({
                "n": next(counter), "depth": depth, "kind": "clause", "text": _text(node),
                "ends_on": _closing_taam(node[-1]) if node else None,
            })

    walk(tree, 0)
    return rows
