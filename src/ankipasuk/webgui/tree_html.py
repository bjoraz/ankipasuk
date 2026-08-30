"""Renders a cloze split tree (see :mod:`ankipasuk.cloze`) as HTML.

This is the actual fix for the Tk bidi/selection bugs this project hit
repeatedly: rather than fighting Tk's incomplete, platform-inconsistent
bidi engine with manual word reversal and embedding characters, this emits
plain HTML with a native ``dir="rtl"`` attribute and lets the browser's own
(standards-compliant, thoroughly tested) Unicode Bidirectional Algorithm
implementation do the reordering -- correctly, including for text
selection, which Tk could never get right for niqud/teamim-heavy Hebrew.
"""

from __future__ import annotations

from html import escape

from ..config import INDENT_UNIT_PX, UNIT_COLORS

# Indent is expressed as a right-side CSS margin (padding-right), the
# mirror image of Tk's original left-margin approach -- because in an RTL
# layout, "start" (where reading begins, and where deeper nesting should
# visually indent *from*) is the right edge, not the left.
_INDENT_PER_LEVEL_PX = INDENT_UNIT_PX


def _leaf_to_html(node, depth: int, indent_level: int) -> str:
    color = UNIT_COLORS[depth % len(UNIT_COLORS)]
    words_html = []
    for u in node:
        for sub in u["subs"]:
            cls = "conj" if sub["level"] == 0 else "word"
            words_html.append(f'<span class="{cls}">{escape(sub["text"])}</span>')
    words = " ".join(words_html)
    style = f"background:{color};padding-right:{indent_level * _INDENT_PER_LEVEL_PX}px;"
    return f'<div class="viz-line" style="{style}">{words}</div>'


def tree_to_html(node, depth: int = 0, indent_level: int = 0, extra_bias: int = 0) -> str:
    """Render one verse's split tree as a block of ``<div class="viz-line">``
    rows, most-significant clause first, matching the original Tk
    visualization's top-to-bottom reading order and depth-based coloring."""
    eff_indent = indent_level + extra_bias

    if isinstance(node, dict):
        left_html = tree_to_html(node["left"], depth + 1, indent_level + 1, extra_bias)
        right_html = tree_to_html(node["right"], depth + 1, indent_level, extra_bias + 1)
        return left_html + right_html

    return _leaf_to_html(node, depth, eff_indent)
