"""Renders a cloze split tree (see :mod:`ankipasuk.cloze`) as HTML.

Structurally a faithful port of the original Tk render_colored_tree (see
gui/app.py, kept for reference): same recursion, same depth-to-color
mapping, same growing indent-guide strip distinct from each leaf's own
depth color. The one deliberate difference is *how* RTL is achieved --
plain HTML with a native dir="rtl" attribute, letting the browser's own
standards-compliant Unicode Bidirectional Algorithm implementation do the
reordering, rather than Tk's manual word-reversal-plus-embedding-
characters workaround, which could not be made reliable (confirmed on the
actual Windows target: word/spacing corruption on long lines, and text
visibly rearranging on selection -- both traced to genuine Tk/Windows
Tk-bidi limitations, not something fixable with more workarounds).
"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..config import GUIDE_BG, INDENT_UNIT_PX, UNIT_COLORS

_INDENT_PER_LEVEL_PX = INDENT_UNIT_PX


def _leaf_to_html(node, depth: int, indent_level: float, chip: str = "") -> str:
    color = UNIT_COLORS[depth % len(UNIT_COLORS)]
    words_html = []
    for u in node:
        for sub in u["subs"]:
            cls = "conj" if sub["level"] == 0 else "word"
            words_html.append(f'<span class="{cls}">{escape(sub["text"])}</span>')
    words = " ".join(words_html)

    # A growing indent-guide strip, its own GUIDE_BG background distinct
    # from the leaf's own depth color -- matching the original Tk
    # visualization's two-tone treatment (a light-gray "guide" region,
    # separate from the colored word content) rather than one solid
    # color spanning the whole row including its indent. The guide sits
    # on the RIGHT (the side Hebrew reading starts from), so deeper
    # nesting indents inward from the right -- the RTL mirror of how
    # indentation normally grows from the left in an LTR layout.
    indent_px = indent_level * _INDENT_PER_LEVEL_PX
    guide_html = (
        f'<div class="viz-guide" style="width:{indent_px:g}px;background:{GUIDE_BG}"></div>'
        if indent_px
        else ""
    )

    chip_html = f'<div class="viz-chip">{escape(chip)}</div>' if chip else ""
    return (
        '<div class="viz-row">'
        f"{chip_html}"
        f'<div class="viz-line" dir="rtl" style="background:{color}">{words}</div>'
        f"{guide_html}"
        "</div>"
    )


def tree_to_html(
    node, depth: int = 0, indent_level: float = 0, extra_bias: float = 0,
    chips: Iterator[str] | None = None,
) -> str:
    """Render one verse's split tree as a block of rows, most-significant
    clause first, matching the original Tk visualization's top-to-bottom
    reading order, depth-based coloring, and growing indent guide.

    A "sibling leaf pair" -- a node whose *both* children are leaves,
    neither one further split -- gets its first (upper, logically-earlier)
    leaf nudged in by an extra half indent step. A leaf paired with a
    further-nested subtree on the other side does not qualify; only a
    genuine terminal pair does.

    ``chips``, if given, yields one short label per leaf in reading order
    (see :func:`leaf_chips`), shown beside that leaf's row.
    """
    eff_indent = indent_level + extra_bias

    if isinstance(node, dict):
        left, right = node["left"], node["right"]
        half_bump = -0.25 if not isinstance(left, dict) and not isinstance(right, dict) else 0

        left_html = tree_to_html(left, depth + 1, indent_level + 1 + half_bump, extra_bias, chips)
        right_html = tree_to_html(right, depth + 1, indent_level, extra_bias + 1, chips)
        return left_html + right_html

    return _leaf_to_html(node, depth, eff_indent, next(chips, "") if chips is not None else "")


# =============================================================
#  The analysis view (see ankipasuk.analysis)
# =============================================================
def _taam_label(taam: dict | None) -> str:
    if taam is None:
        return "no mafsiq"
    return f"{taam['name'] or 'unknown'} (rank {taam['rank']})"


def leaf_chips(breakdown: list[dict]) -> Iterator[str]:
    """The chip for each leaf row: its cloze number and closing ta'am."""
    for row in breakdown:
        if row["kind"] == "clause":
            taam = row["ends_on"]
            yield f"c{row['n']} · {taam['name'] or '?'} {taam['rank']}" if taam else f"c{row['n']}"


def analysis_to_html(label: str, signature: str, breakdown: list[dict]) -> str:
    """The collapsible "how this pasuq splits" table shown under a pasuq:
    its structure signature, then every cloze in card order with the
    words it covers and the mafsiq behind it."""
    rows = []
    for row in breakdown:
        if row["kind"] == "split":
            taam = row["split_after"]
            why = "split after " + (
                f'<bdi dir="rtl" lang="he">{escape(taam["word"])}</bdi>, ' if taam else ""
            ) + escape(_taam_label(taam))
        else:
            why = "ends on " + escape(_taam_label(row["ends_on"]))
        whole = " (whole pasuq)" if row["depth"] == 0 else ""
        rows.append(
            f"<tr><td class=\"cloze-n\">c{row['n']}{whole}</td>"
            f'<td class="cloze-text" dir="rtl" lang="he">{escape(row["text"])}</td>'
            f"<td>{why}</td></tr>"
        )
    return (
        '<details class="viz-analysis">'
        f"<summary>How {escape(label)} splits: {len(breakdown)} clozes</summary>"
        f'<div class="viz-signature">Structure: <code>{escape(signature)}</code></div>'
        '<table class="cloze-table"><thead><tr><th>Cloze</th><th>Words</th><th>Why</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</details>"
    )
