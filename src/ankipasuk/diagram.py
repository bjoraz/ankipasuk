"""A pasuq's division as a diagram, after Joshua Jacobson's (*Chanting the
Hebrew Bible*): the pasuq's words with, above them, one bracket for each
mafsiq, spanning the stretch of text that mafsiq closes and labelled with
its rank and Hebrew name. As in his diagrams, a bracket's row is how deep
its division lies: the unit's own bracket on top, each division one row
below the one it divides. So a mafsiq that only divides what's left after
an earlier one of the same rank -- a "downgraded" one, like the tevir
after the ravia' in Bereshit 31:33 -- sits a row lower than it.

The brackets are the split tree of :func:`ankipasuk.text_processing.split_segment`
at its finest (one group per leaf): every split puts a bracket over its
first part, which ends on the mafsiq the split was made after. A
part that ends where its parent does closes on the parent's mafsiq and
needs no bracket of its own. The pasuq is shown as two units, the atnaḥ
half and the sof pasuq half (or one, if it has no atnaḥ), each with its
own top bracket.

Brackets for divisions the cloze cards don't make at the current setting
(``card_n``, the most groups a card's clause may hold) are marked
``grey``. This module only describes the diagram; it is drawn in the
browser (``webgui/static/diagram.js``), which measures where each word
landed.
"""

from __future__ import annotations

from .config import TROPE_HEBREW_NAMES
from .text_processing import group_into_units, split_segment, tokenize_pasuk


def _span(node) -> tuple[int, int]:
    """The first and last group a tree node covers."""
    if isinstance(node, dict):
        return _span(node["left"])[0], _span(node["right"])[1]
    return node[0]["g"], node[-1]["g"]


def _last_unit(node) -> dict:
    return _last_unit(node["right"]) if isinstance(node, dict) else node[-1]


def _spans(node) -> set[tuple[int, int]]:
    out = {_span(node)}
    if isinstance(node, dict):
        out |= _spans(node["left"]) | _spans(node["right"])
    return out


def taam_label(unit: dict) -> tuple[int, str]:
    """A group's mafsiq as (rank, Hebrew name)."""
    name = unit.get("trope_name") or ""
    return unit["level"], TROPE_HEBREW_NAMES.get(name, name)


def _box(node, card_spans: set, depth: int) -> dict:
    first, last = _span(node)
    rank, name = taam_label(_last_unit(node))
    return {
        "from": first, "to": last, "rank": rank, "name": name,
        "grey": (first, last) not in card_spans, "depth": depth,
    }


def _boxes(node, card_spans: set, depth: int) -> list[dict]:
    """The brackets below ``node`` (at ``depth``): each split's first part
    gets one, a row below the node it divides. Both parts go one level
    deeper, so a split of what's left after the first part sits lower
    than that first part's bracket."""
    if not isinstance(node, dict):
        return []
    left, right = node["left"], node["right"]
    return ([_box(left, card_spans, depth + 1)]
            + _boxes(left, card_spans, depth + 1) + _boxes(right, card_spans, depth + 1))


def _with_heights(boxes: list[dict]) -> list[dict]:
    """``h``: the bracket's row counted up from the words (the deepest
    division is 1), which is what the drawing uses."""
    deepest = max(b["depth"] for b in boxes)
    for box in boxes:
        box["h"] = deepest - box.pop("depth") + 1
    return boxes


def pasuq_diagram(pointed: str, card_n: int = 1) -> dict:
    """The diagram of one pointed pasuq: ``{"units": [...]}``, one or two
    units, each with ``words`` (``{"text", "g"}``, ``g`` being the word's
    group) and ``boxes`` (``{"from", "to", "rank", "name", "grey", "h"}``,
    ``from``/``to`` being groups and ``h`` the row, counted up from the
    words)."""
    tokens = tokenize_pasuk(pointed)
    units = group_into_units(tokens)
    if not units:
        return {"units": []}
    words = []
    for g, unit in enumerate(units):
        unit["g"] = g
        words += [{"text": sub["text"], "g": g} for sub in unit["subs"]]

    full = split_segment(units, max_leaf_disj=1)
    card_spans = _spans(split_segment(units, max_leaf_disj=max(1, card_n)))
    halves = isinstance(full, dict) and _last_unit(full["left"])["level"] == 1
    parts = [full["left"], full["right"]] if halves else [full]

    out_units = []
    for part in parts:
        first, last = _span(part)
        top = _box(part, card_spans, 0) | {"grey": False}  # a unit's own bracket is always shown
        out_units.append({
            "words": [w for w in words if first <= w["g"] <= last],
            "boxes": _with_heights([top] + _boxes(part, card_spans, 0)),
        })
    return {"units": out_units}
