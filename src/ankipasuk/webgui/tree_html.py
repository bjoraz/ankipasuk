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

from html import escape

from ..config import GUIDE_BG, INDENT_UNIT_PX, UNIT_COLORS

_INDENT_PER_LEVEL_PX = INDENT_UNIT_PX


def _leaf_to_html(node, depth: int, indent_level: float) -> str:
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

    return (
        '<div class="viz-row">'
        f'<div class="viz-line" dir="rtl" style="background:{color}">{words}</div>'
        f"{guide_html}"
        "</div>"
    )


def tree_to_html(node, depth: int = 0, indent_level: float = 0, extra_bias: float = 0) -> str:
    """Render one verse's split tree as a block of rows, most-significant
    clause first, matching the original Tk visualization's top-to-bottom
    reading order, depth-based coloring, and growing indent guide.

    A "sibling leaf pair" -- a node whose *both* children are leaves,
    neither one further split -- gets its first (upper, logically-earlier)
    leaf nudged in by an extra half indent step. A leaf paired with a
    further-nested subtree on the other side does not qualify; only a
    genuine terminal pair does.
    """
    eff_indent = indent_level + extra_bias

    if isinstance(node, dict):
        left, right = node["left"], node["right"]
        half_bump = 0.5 if not isinstance(left, dict) and not isinstance(right, dict) else 0

        left_html = tree_to_html(left, depth + 1, indent_level + 1 + half_bump, extra_bias)
        right_html = tree_to_html(right, depth + 1, indent_level, extra_bias + 1)
        return left_html + right_html

    return _leaf_to_html(node, depth, eff_indent)
