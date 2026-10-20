"""A pasuq's division as a diagram, after Joshua Jacobson's (*Chanting the
Hebrew Bible*): the pasuq's words with, above them, one bracket for each
mafsiq, spanning the stretch of text that mafsiq closes and labelled with
its rank and Hebrew name. Stronger divisions sit higher, so rank 1 is on
top and the weakest are just above the words.

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


def _box(node, card_spans: set) -> dict:
    first, last = _span(node)
    rank, name = taam_label(_last_unit(node))
    return {"from": first, "to": last, "rank": rank, "name": name, "grey": (first, last) not in card_spans}


def _boxes(node, card_spans: set) -> list[dict]:
    if not isinstance(node, dict):
        return []
    left, right = node["left"], node["right"]
    return [_box(left, card_spans)] + _boxes(left, card_spans) + _boxes(right, card_spans)


def _with_heights(boxes: list[dict]) -> list[dict]:
    """``h``: 1 for a bracket with none inside it, else 1 + the tallest
    inside -- its row above the words."""
    by_size = sorted(boxes, key=lambda b: b["to"] - b["from"])
    for i, box in enumerate(by_size):
        inside = [c for c in by_size[:i] if box["from"] <= c["from"] and c["to"] <= box["to"]]
        box["h"] = 1 + max((c["h"] for c in inside), default=0)
    return boxes


def pasuq_diagram(pointed: str, card_n: int = 1) -> dict:
    """The diagram of one pointed pasuq: ``{"units", "groups"}``.

    ``units`` (one or two) each have ``words`` (``{"text", "g"}``, ``g``
    being the word's group) and ``boxes`` (``{"from", "to", "rank",
    "name", "grey", "h"}``, ``from``/``to`` being groups). ``groups`` is
    the plain list of groups: ``{"rank", "name", "text"}``."""
    tokens = tokenize_pasuk(pointed)
    units = group_into_units(tokens)
    if not units:
        return {"units": [], "groups": []}
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
        top = _box(part, card_spans) | {"grey": False}  # a unit's own bracket is always shown
        out_units.append({
            "words": [w for w in words if first <= w["g"] <= last],
            "boxes": _with_heights([top] + _boxes(part, card_spans)),
        })
    groups = []
    for unit in units:
        rank, name = taam_label(unit)
        groups.append({"rank": rank, "name": name, "text": " ".join(sub["text"] for sub in unit["subs"])})
    return {"units": out_units, "groups": groups}
