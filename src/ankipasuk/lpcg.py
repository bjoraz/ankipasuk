"""Builds Anki notes for overlapping-context recitation practice (the
technique the ``AnkiLPCG`` add-on -- https://github.com/sobjornstad/AnkiLPCG
-- uses for memorizing poetry/song lyrics verbatim, in order), so a whole
range of aliyot can be pushed to Anki programmatically in one call instead
of pasting one aliyah at a time into that add-on's import dialog.

This is an independent reimplementation of the overlapping-context
windowing technique, written from scratch against AnkiLPCG's documented
behavior (https://ankilpcg.readthedocs.io/en/latest/importing.html) rather
than derived from its source (which is AGPLv3-licensed) -- so this module
carries no AGPL entanglement and is free to live under ankipasuk's own
license.

The note type built here (:data:`MODEL_NAME`) is a distinct, ankipasuk-owned
note type, not the "LPCG 1.0" note type the real add-on creates -- keeping
them separate avoids any assumption of field-for-field compatibility if
that add-on's own schema changes in a later version, and gives ankipasuk
room to add tikkun-specific styling (RTL layout, trope/nikud toggling)
later without touching a third-party add-on's note type.

Pipeline: a list of already-fully-rendered lines goes in, a list of
Anki-note field dicts comes out. A line may be a plain string, or (as
:func:`ankipasuk.tikkun.get_scroll_lines_for_range` produces)
``{"html": ..., "is_petucha": ..., "char_count": ...}`` -- rendered
unjustified when it's a petucha, since a petucha's whole point is that it
stops short of the line's end. Callers are responsible for grouping the
returned field dicts under "deckName"/"modelName"/"tags" and pushing them
via :func:`ankipasuk.anki_connect.operations.add_notes`.
"""

from __future__ import annotations

from .tikkun import FONT_ANKI_FILENAME

MODEL_NAME = "Ankipasuk Aliyah"
FIELD_NAMES = ["Line", "Context", "Title", "Author", "Sequence", "Prompt", "BoxWidth"]
BEGINNING_MARKER = "[Beginning]"

# Small on-card controls (not a export-time setting) for font size and
# line spacing -- identical block embedded in both Front and Back, since
# Anki templates are independent HTML fragments with no shared-partial
# mechanism. Persisted via localStorage (same origin/profile across every
# card and both review sides), and applied as CSS custom properties on the
# document root so the CSS below can reference them.
#
# Bumping font size doesn't need any width recalculation of its own: the
# "BoxWidth" field is in CSS "ch" units (see _box_width), which are
# already defined relative to the element's own font-size -- so as
# --ankipasuk-font-size changes, every ch-based width recomputes in the
# same ratio automatically.
_SIZE_CONTROLS_HTML = """\
<div class="ankipasuk-controls">
    <button type="button" onclick="ankipasukAdjustFont(-1)">A-</button>
    <button type="button" onclick="ankipasukAdjustFont(1)">A+</button>
    <button type="button" onclick="ankipasukAdjustLineHeight(-1)">≡-</button>
    <button type="button" onclick="ankipasukAdjustLineHeight(1)">≡+</button>
</div>
<script>
(function () {
    var FONT_KEY = "ankipasuk_font_size_px";
    var LINE_KEY = "ankipasuk_line_height_scale";
    var FONT_STEP = 2, FONT_MIN = 8, FONT_MAX = 60, FONT_DEFAULT = 14;
    var LINE_STEP = 0.1, LINE_MIN = 0.7, LINE_MAX = 2.5, LINE_DEFAULT = 1;

    function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

    function readFontSize() {
        var stored = localStorage.getItem(FONT_KEY);
        return stored ? parseFloat(stored) : FONT_DEFAULT;
    }
    function readLineHeight() {
        var stored = localStorage.getItem(LINE_KEY);
        return stored ? parseFloat(stored) : LINE_DEFAULT;
    }
    function applyFontSize(px) {
        document.documentElement.style.setProperty("--ankipasuk-font-size", px + "px");
    }
    function applyLineHeight(scale) {
        document.documentElement.style.setProperty("--ankipasuk-line-height-scale", scale);
    }

    window.ankipasukAdjustFont = function (direction) {
        var next = clamp(readFontSize() + direction * FONT_STEP, FONT_MIN, FONT_MAX);
        localStorage.setItem(FONT_KEY, next);
        applyFontSize(next);
    };
    window.ankipasukAdjustLineHeight = function (direction) {
        var next = clamp(readLineHeight() + direction * LINE_STEP, LINE_MIN, LINE_MAX);
        localStorage.setItem(LINE_KEY, next);
        applyLineHeight(next);
    };

    applyFontSize(readFontSize());
    applyLineHeight(readLineHeight());
})();
</script>"""

_FRONT_TEMPLATE = f"""\
{_SIZE_CONTROLS_HTML}

<div class="title">{{{{Title}}}} {{{{Sequence}}}}</div>
{{{{#Author}}}}<div class="author">{{{{Author}}}}</div>{{{{/Author}}}}

<br>

<div class="lines" style="width: {{{{BoxWidth}}}}">
    {{{{Context}}}}
    <div class="line cloze">
        {{{{#Prompt}}}}{{{{Prompt}}}}{{{{/Prompt}}}}
        {{{{^Prompt}}}}[...]{{{{/Prompt}}}}
    </div>
</div>"""

_BACK_TEMPLATE = f"""\
{_SIZE_CONTROLS_HTML}

<div class="title">{{{{Title}}}} {{{{Sequence}}}}</div>
{{{{#Author}}}}<div class="author">{{{{Author}}}}</div>{{{{/Author}}}}

<br>

<div class="lines" style="width: {{{{BoxWidth}}}}">
    {{{{Context}}}}
    {{{{Line}}}}
</div>"""

CARD_TEMPLATES = [{"Name": "Recite", "Front": _FRONT_TEMPLATE, "Back": _BACK_TEMPLATE}]

# Adapted from tikkun.io's own page.css (github.com/akivajgordon/
# tikkun.io) -- same class names, same fragment/column/setumah mechanism,
# since that's the visual technique a scroll-accurate recitation card
# should reproduce -- but NOT its HTML structure:
#
#  - tikkun.io uses an HTML table, letting its auto layout *discover* a
#    shared column width from its widest row. That only works because
#    tikkun.io always renders a long run of lines together, and even then
#    only in the ONE browser engine tikkun.io targets (a real user's
#    browser). A 2-3 line flashcard doesn't give a table auto-layout
#    algorithm enough rows to work with, and -- confirmed directly against
#    a real Anki review, where a table-based version of this rendered
#    correctly in this project's own browser-based preview but visibly
#    broke (context lines collapsing to an unstretched width) -- table
#    auto-layout's handling of a display:flex table cell is NOT consistent
#    across engines. So each line here is instead a plain block-level
#    <div>, which fills its parent's width exactly like any other block
#    box in any engine: no table, no ambiguous column-width algorithm.
#    The box width itself is computed once in Python from the aliyah's
#    actual longest line (see build_lpcg_fields's BoxWidth field) and set
#    as an explicit inline style on that parent -- a predetermined box,
#    not a discovered one.
#  - "text-align: justify" + "text-align-last: justify" stretches a
#    single (non-wrapping) line to fill that fixed width edge-to-edge.
#  - A setumah (more than one ".fragment" in a ".column") gets
#    "justify-content: space-between" real gap between the two fragments,
#    each sized to its own content -- a visibly distinct gap, not just
#    another wide word-spacing stretch.
CSS = f"""\
@font-face {{
    font-family: "ShlomosemiStam";
    src: url("{FONT_ANKI_FILENAME}");
}}

:root {{
    /* Matches the script's own FONT_DEFAULT below -- this is just the
       pre-JS fallback, e.g. for the sliver of time before the script
       runs. */
    --ankipasuk-font-size: 14px;
    --ankipasuk-line-height-scale: 1;
}}

.card {{
    font-family: "ShlomosemiStam", "SBL Hebrew", "Ezra SIL", "Noto Serif Hebrew", arial;
    font-size: var(--ankipasuk-font-size);
    color: black;
    background-color: white;
}}

.ankipasuk-controls {{
    position: fixed;
    top: 6px;
    right: 6px;
    direction: ltr;
    font-family: sans-serif;
    font-size: 14px;
    opacity: 0.35;
    z-index: 1000;
}}

.ankipasuk-controls:hover {{
    opacity: 1;
}}

.ankipasuk-controls button {{
    margin-left: 2px;
    min-width: 1.8em;
    cursor: pointer;
}}

.lines {{
    direction: rtl;
    margin: 0 auto;
}}

.lines .line {{
    text-align: justify;
    text-align-last: justify;
    line-height: calc(130% * var(--ankipasuk-line-height-scale));
}}

/* A petucha ends its paragraph partway through the line on purpose -- the
   rest of the line is blank on the actual scroll, so unlike an ordinary
   line it must NOT be stretched to fill the box's width. Same for the
   synthetic "[Beginning]" marker, which isn't scroll text at all. */
.lines .line.petucha,
.lines .line.beginning-marker {{
    text-align: start;
    text-align-last: start;
}}

.column {{
    display: flex;
    justify-content: space-between;
}}

.fragment {{
    width: 100%;
}}

/* A setumah -- more than one fragment in a column -- gets real space
   between its two halves, each sized to its own content. */
.fragment.setuma {{
    width: auto;
}}

.lines .line.cloze {{
    font-weight: bold;
    color: blue;
}}

.nightMode .lines .line.cloze {{
    filter: invert(85%);
}}

.title, .author {{
    text-align: center;
    font-size: small;
    direction: ltr;
}}
"""


def group_lines(lines: list[str], group_size: int) -> list[list[str]]:
    """Chunk ``lines`` into consecutive groups of ``group_size`` (the last
    group may be shorter). ``group_size=1`` -- the common case -- makes
    every physical line its own group, i.e. a no-op grouping."""
    if group_size < 1:
        raise ValueError("group_size must be at least 1.")
    return [lines[i:i + group_size] for i in range(0, len(lines), group_size)]


def _normalize_line(line) -> dict:
    """A line is either a plain string, or a
    ``{"html": ..., "is_petucha": ..., "char_count": ...}`` dict (see the
    module docstring) -- normalize to the latter so rendering has one
    shape to deal with. A plain string is wrapped in the same
    column/fragment markup a tikkun line uses, so it still gets the
    single-line-justify treatment in CSS."""
    if isinstance(line, dict):
        return line
    return {
        "html": f'<div class="column"><span class="fragment">{line}</span></div>',
        "is_petucha": False,
        "char_count": len(line),
    }


def _as_rows(groups: list[list], extra_class: str = "") -> str:
    """Render each line as its own ``<div class="line ...">`` -- see the
    module-level CSS comment for why a plain block-level div, not a table
    row."""
    parts = []
    for group in groups:
        for line in group:
            rendered = _normalize_line(line)
            classes = ["line"]
            if rendered["is_petucha"]:
                classes.append("petucha")
            if extra_class:
                classes.append(extra_class)
            parts.append(f'<div class="{" ".join(classes)}">{rendered["html"]}</div>')
    return "".join(parts)


def _prompt_for(n_lines: int) -> str:
    """AnkiLPCG shows a bare "[...]" cloze prompt (the template's own
    default, encoded here as an empty Prompt field) when exactly one line
    is being recited, and "[...N]" when reciting more than one -- e.g. at
    the end of a recitation window that runs past the end of the text."""
    return "" if n_lines == 1 else f"[...{n_lines}]"


# A CSS "ch" unit is defined from a font's "0" glyph, which -- at least
# for the STAM font here -- turns out to be somewhat WIDER than an average
# Hebrew letter; empirically (tested directly against real Anki reviews,
# not guessed) 0.9x the longest line's raw letter count gives the ideal
# word spacing once justified, tight enough to look like real scroll
# text without the longest line actually wrapping.
_BOX_WIDTH_FACTOR = 0.9


def _box_width(lines: list) -> str:
    """One shared box width for every card built from ``lines``, in CSS
    "ch" units, from the single longest line's own visible letter count --
    see the module-level CSS comment for why this is computed here in
    Python rather than left to the browser to guess from HTML content."""
    max_chars = max((_normalize_line(line)["char_count"] for line in lines), default=0)
    return f"{max(1, round(max_chars * _BOX_WIDTH_FACTOR))}ch"


def build_lpcg_fields(
    lines: list[str],
    *,
    title: str,
    author: str = "",
    context_lines: int = 2,
    recite_lines: int = 1,
    group_size: int = 1,
) -> list[dict[str, str]]:
    """Build one field-dict per card -- shaped like :data:`FIELD_NAMES` --
    implementing the same overlapping-context sliding window AnkiLPCG's
    import dialog produces: each card shows ``context_lines`` lines (or
    groups, if ``group_size`` > 1) of already-seen text as a prompt, and
    asks for the next ``recite_lines``.

    ``lines`` must already be fully rendered (HTML is fine -- each line
    becomes its own block-level div, see the module-level CSS comment). No
    blank-line, comment, or indentation conventions are applied here:
    unlike AnkiLPCG's own poem-editor preprocessing, this deliberately
    does *no* text munging, so a tikkun-styled HTML line containing e.g. a
    "#" in a hex color can't be silently mistaken for a comment.

    Every card gets the same "BoxWidth" field -- computed once from
    ``lines`` as a whole (see :func:`_box_width`), not per card -- so the
    text box doesn't visibly resize from one card to the next while
    reciting through the same aliyah. Font size and line spacing are
    adjustable on the card itself instead (see ``_SIZE_CONTROLS_HTML``);
    BoxWidth being in "ch" units means it scales automatically with
    whatever font size the reader has picked, no recomputation needed.
    """
    box_width = _box_width(lines)
    groups = group_lines(lines, group_size)
    fields: list[dict[str, str]] = []

    for seq, _group in enumerate(groups, start=1):
        context_start = max(0, seq - 1 - context_lines)
        context_groups = groups[context_start:seq - 1]
        context_html = _as_rows(context_groups)
        if len(context_groups) < context_lines:
            beginning_row = f'<div class="line beginning-marker">{BEGINNING_MARKER}</div>'
            context_html = beginning_row + context_html

        recite_groups = groups[seq - 1:seq - 1 + recite_lines]
        n_recite_lines = sum(len(g) for g in recite_groups)

        fields.append({
            "Line": _as_rows(recite_groups, extra_class="cloze"),
            "Context": context_html,
            "Title": title,
            "Author": author,
            "Sequence": str(seq),
            "Prompt": _prompt_for(n_recite_lines),
            "BoxWidth": box_width,
        })

    return fields
