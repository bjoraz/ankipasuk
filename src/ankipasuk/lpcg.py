"""Builds Anki notes for overlapping-context recitation practice (the
technique the ``AnkiLPCG`` add-on -- https://github.com/sobjornstad/AnkiLPCG
-- uses for memorizing poetry/song lyrics verbatim, in order), so a whole
range of 'aliyyot can be pushed to Anki programmatically in one call instead
of pasting one 'aliyya at a time into that add-on's import dialog.

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
room to add tikkun-specific styling (RTL layout, ta'amim/niqqud toggling)
later without touching a third-party add-on's note type.

Pipeline: a list of already-fully-rendered lines goes in, a list of
Anki-note field dicts comes out. A line may be a plain string, or (as
:func:`ankipasuk.tikkun.get_scroll_lines_for_range` produces)
``{"html": ..., "is_petucha": ..., "char_count": ...}`` -- rendered
unjustified when it's a petuḥa, since a petuḥa's whole point is that it
stops short of the line's end. Callers are responsible for grouping the
returned field dicts under "deckName"/"modelName"/"tags" and pushing them
via :func:`ankipasuk.anki_connect.operations.add_notes`.

Two field shapes share this one note type/CSS: :func:`build_lpcg_fields`'s
row-anchored "Context"/"Line"/"Prompt" (a fixed-size sliding window over
physical rows), and :mod:`ankipasuk.verse_cards`'s verse-anchored
"FrontRows"/"BackRows" (one whole verse per card, word-precise at shared
row boundaries -- a row-level split can't be, see that module's
docstring). The card templates below render whichever pair is populated
on a given note, via Anki's own ``{{#Field}}``/``{{^Field}}`` sections.
"""

from __future__ import annotations

from .tikkun import FONT_ANKI_FILENAME

MODEL_NAME = "Ankipasuk Aliyah"
FIELD_NAMES = [
    # "Title" is deliberately first: Anki refuses to create a note whose
    # FIRST field (by the note type's own field order) is empty -- and
    # since the two card "shapes" sharing this note type each leave the
    # OTHER shape's fields unpopulated (row-mode never sets
    # FrontRows/BackRows; verse-mode never sets Line/Context/Prompt), no
    # single one of those fields is safe to put first. "Title" is the one
    # field both shapes always populate.
    "Title", "Line", "Context", "Prompt", "FrontRows", "BackRows",
    "Author", "Sequence", "BoxWidth",
]
BEGINNING_MARKER = "[Beginning]"

# Small on-card controls (not a export-time setting) for font size, line
# spacing, and box width -- identical block embedded in both Front and
# Back, since Anki templates are independent HTML fragments with no
# shared-partial mechanism. Persisted via localStorage (same origin/
# profile across every card and both review sides), and applied as CSS
# custom properties on the document root so the CSS below can reference
# them.
#
# Bumping font size doesn't need any width recalculation of its own: the
# "BoxWidth" field is in CSS "ch" units (see _box_width), which are
# already defined relative to the element's own font-size -- so as
# --ankipasuk-font-size changes, every ch-based width recomputes in the
# same ratio automatically.
#
# Width is a multiplier on top of "BoxWidth" (see the templates' own
# `calc({{BoxWidth}} * var(--ankipasuk-width-scale, 1))`), not a
# replacement for it -- BoxWidth still sets each export's own
# content-driven floor/minimum (see MIN_BOX_WIDTH_CH), and the ↔-/↔+
# buttons scale that up or down live, shared -- like font size and line
# spacing -- across every card of this note type instead of needing a
# re-export to change.
_SIZE_CONTROLS_HTML = """\
<div class="ankipasuk-controls">
    <button type="button" onclick="ankipasukAdjustFont(-1)">A-</button>
    <button type="button" onclick="ankipasukAdjustFont(1)">A+</button>
    <button type="button" onclick="ankipasukAdjustLineHeight(-1)">≡-</button>
    <button type="button" onclick="ankipasukAdjustLineHeight(1)">≡+</button>
    <button type="button" onclick="ankipasukAdjustWidth(-1)">↔-</button>
    <button type="button" onclick="ankipasukAdjustWidth(1)">↔+</button>
</div>
<script>
(function () {
    var FONT_KEY = "ankipasuk_font_size_px";
    var LINE_KEY = "ankipasuk_line_height_scale";
    var WIDTH_KEY = "ankipasuk_width_scale";
    var FONT_STEP = 2, FONT_MIN = 8, FONT_MAX = 60, FONT_DEFAULT = 14;
    var LINE_STEP = 0.1, LINE_MIN = 0.7, LINE_MAX = 2.5, LINE_DEFAULT = 1;
    var WIDTH_STEP = 0.1, WIDTH_MIN = 0.5, WIDTH_MAX = 2.5, WIDTH_DEFAULT = 1;

    function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

    function readFontSize() {
        var stored = localStorage.getItem(FONT_KEY);
        return stored ? parseFloat(stored) : FONT_DEFAULT;
    }
    function readLineHeight() {
        var stored = localStorage.getItem(LINE_KEY);
        return stored ? parseFloat(stored) : LINE_DEFAULT;
    }
    function readWidthScale() {
        var stored = localStorage.getItem(WIDTH_KEY);
        return stored ? parseFloat(stored) : WIDTH_DEFAULT;
    }
    function applyFontSize(px) {
        document.documentElement.style.setProperty("--ankipasuk-font-size", px + "px");
    }
    function applyLineHeight(scale) {
        document.documentElement.style.setProperty("--ankipasuk-line-height-scale", scale);
    }
    function applyWidthScale(scale) {
        document.documentElement.style.setProperty("--ankipasuk-width-scale", scale);
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
    window.ankipasukAdjustWidth = function (direction) {
        var next = clamp(readWidthScale() + direction * WIDTH_STEP, WIDTH_MIN, WIDTH_MAX);
        localStorage.setItem(WIDTH_KEY, next);
        applyWidthScale(next);
    };

    applyFontSize(readFontSize());
    applyLineHeight(readLineHeight());
    applyWidthScale(readWidthScale());
})();
</script>"""

# The width scale (see _SIZE_CONTROLS_HTML above) multiplies BoxWidth
# rather than replacing it -- BoxWidth is still each export's own
# content-driven floor. A plain (non-f-string) constant, so its literal
# "{{BoxWidth}}" needs no f-string brace-doubling; interpolated by name
# into the templates below to keep their own lines under the line-length
# limit.
_LINES_STYLE = "width: calc({{BoxWidth}} * var(--ankipasuk-width-scale, 1))"

_FRONT_TEMPLATE = f"""\
{_SIZE_CONTROLS_HTML}

<div class="title">{{{{Title}}}} {{{{Sequence}}}}</div>
{{{{#Author}}}}<div class="author">{{{{Author}}}}</div>{{{{/Author}}}}

<br>

{{{{#FrontRows}}}}
<div class="lines" style="{_LINES_STYLE}">{{{{FrontRows}}}}</div>
{{{{/FrontRows}}}}
{{{{^FrontRows}}}}
<div class="lines" style="{_LINES_STYLE}">
    {{{{Context}}}}
    <div class="line cloze">
        {{{{#Prompt}}}}{{{{Prompt}}}}{{{{/Prompt}}}}
        {{{{^Prompt}}}}[...]{{{{/Prompt}}}}
    </div>
</div>
{{{{/FrontRows}}}}"""

_BACK_TEMPLATE = f"""\
{_SIZE_CONTROLS_HTML}

<div class="title">{{{{Title}}}} {{{{Sequence}}}}</div>
{{{{#Author}}}}<div class="author">{{{{Author}}}}</div>{{{{/Author}}}}

<br>

{{{{#BackRows}}}}
<div class="lines" style="{_LINES_STYLE}">{{{{BackRows}}}}</div>
{{{{/BackRows}}}}
{{{{^BackRows}}}}
<div class="lines" style="{_LINES_STYLE}">
    {{{{Context}}}}
    {{{{Line}}}}
</div>
{{{{/BackRows}}}}"""

CARD_TEMPLATES = [{"Name": "Recite", "Front": _FRONT_TEMPLATE, "Back": _BACK_TEMPLATE}]

# Adapted from tikkun.io's own page.css (github.com/akivajgordon/
# tikkun.io) -- same class names, same fragment/column/setuma mechanism,
# since that's the visual technique a scroll-accurate tiqqun card
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
#    The box width itself is computed once in Python from the 'aliyya's
#    actual longest line (see build_lpcg_fields's BoxWidth field) and set
#    as an explicit inline style on that parent -- a predetermined box,
#    not a discovered one.
#  - "text-align: justify" + "text-align-last: justify" stretches a
#    single (non-wrapping) line to fill that fixed width edge-to-edge.
#  - A setuma (more than one ".fragment" in a ".column") gets
#    "justify-content: space-between" real gap between the two fragments,
#    each sized to its own content -- a visibly distinct gap, not just
#    another wide word-spacing stretch.
# The core scroll-layout rules -- box/line/setuma structure only, no
# Anki-specific bits (night mode, card-only font-size/line-height
# controls, cloze styling) -- factored out so
# :mod:`ankipasuk.webgui.api` can reuse the exact same rendering outside
# Anki too (the source section's own tikkun-style display, via
# :func:`render_scroll_html`), rather than maintaining a second,
# possibly-drifting copy. CSS below interpolates this in and then layers
# its own Anki-only additions/overrides on top (see the comment blocks
# there for why each addition exists).
SCROLL_CSS = """\
.lines {
    direction: rtl;
    margin: 0 auto;
    /* The ", 16px"/", 1" fallbacks make these safe to use even before a
       caller ever sets the variable (e.g. the webgui's own source
       section, on first render before its own width/size controls have
       touched it) -- an Anki card always sets both explicitly (see
       CSS's own :root block below), so the fallback never applies
       there. */
    font-size: var(--ankipasuk-font-size, 16px);
}

.lines .line {
    text-align: justify;
    text-align-last: justify;
    line-height: calc(130% * var(--ankipasuk-line-height-scale, 1));
}

/* A petuḥa ends its paragraph partway through the line on purpose -- the
   rest of the line is blank on the actual scroll, so unlike an ordinary
   line it must NOT be stretched to fill the box's width. */
.lines .line.petucha {
    text-align: start;
    text-align-last: start;
}

.column {
    display: flex;
    justify-content: space-between;
}

.fragment {
    width: 100%;
}

/* A setuma -- more than one fragment in a column -- gets real space
   between its two halves, each sized to its own content. */
.fragment.setuma {
    width: auto;
}
"""

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
    --ankipasuk-width-scale: 1;
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

{SCROLL_CSS}
/* Anki-only addition on top of SCROLL_CSS above: the synthetic
   "[Beginning]" marker (not real scroll text, so also unjustified like a
   petuḥa) only exists on a card, never in the plain webgui display
   SCROLL_CSS is shared with. */
.lines .line.petucha,
.lines .line.beginning-marker {{
    text-align: start;
    text-align-last: start;
}}

/* ankipasuk.verse_cards's own marker for a real transition to a new
   physical scroll column, e.g. when a verse's own tail crosses an 'ammud
   boundary -- a clear divider, not just another line of scroll text, so
   it's set off with its own rule on either side rather than folded into
   the justified/unjustified text flow above. */
.lines .amud-break {{
    direction: ltr;
    display: flex;
    align-items: center;
    gap: 0.6em;
    margin: 0.5em 0;
    font-size: small;
    color: #888;
}}

.lines .amud-break::before,
.lines .amud-break::after {{
    content: "";
    flex: 1;
    border-top: 1px solid #ccc;
}}

.nightMode .lines .amud-break {{
    filter: invert(85%);
}}

.lines .line.cloze {{
    font-weight: bold;
    color: blue;
}}

.nightMode .lines .line.cloze {{
    filter: invert(85%);
}}

/* ankipasuk.verse_cards's own inline cloze span, nested INSIDE a
   .fragment above (not a replacement for it) -- a fragment can be split
   between this verse's own tested words and a neighboring verse's
   context words, so it needs its own span-level class distinct from the
   row-level .line.cloze above, where the whole row is tested at once. */
.cloze-inline {{
    font-weight: bold;
    color: blue;
}}

/* The Front side's hidden state: same literal words as .cloze-inline
   alone (see verse_cards._render_split_fragment for why), just painted
   over with a solid bar instead of shown -- so the row's
   text-align: justify has identical text to work with on both sides of
   the card, and stretches identically either way. */
.cloze-inline.redacted {{
    color: transparent;
    background-color: #e0e0e0;
    border-radius: 2px;
}}

/* The NEXT verse's own opening words, sharing a row with this verse's
   own last row -- masked on BOTH sides, always (see
   verse_cards._render_split_fragment for why "own" reveals on the Back
   but this never does): showing it here would spoil that verse's own
   card before the reader gets to it. A visibly darker grey than
   .redacted's, so the two are easy to tell apart at a glance -- .redacted
   marks "you'll see this in a moment, on THIS card's own Back", this
   marks "not on this card at all". */
.cloze-inline.masked {{
    color: transparent;
    background-color: #c0c0c0;
    border-radius: 2px;
}}

.nightMode .cloze-inline {{
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
# text without the longest line actually wrapping. Public (not
# underscore-prefixed) since :mod:`ankipasuk.verse_cards` reuses it too,
# for the exact same reason on the exact same font.
BOX_WIDTH_FACTOR = 0.9

# A short 'aliyya's longest line can compute to a noticeably narrower box
# than a typical one -- narrow enough to feel cramped rather than
# scroll-accurate. 40ch is comfortable even for a short one; anything
# whose own content genuinely needs more still gets it, since this is
# only a floor.
MIN_BOX_WIDTH_CH = 40


def box_width_from_char_counts(char_counts) -> str:
    """One shared box width, in CSS "ch" units, from the single longest
    ``char_counts`` value (or :data:`MIN_BOX_WIDTH_CH`, whichever is
    larger) -- see the module-level CSS comment for why this is computed
    here in Python rather than left to the browser to guess from HTML
    content. Shared by :func:`_box_width` (row-mode, counting each
    rendered line's own letters) and :mod:`ankipasuk.verse_cards`
    (verse-mode, counting each row's words joined with spaces the same
    way)."""
    max_chars = max(char_counts, default=0)
    return f"{max(MIN_BOX_WIDTH_CH, round(max_chars * BOX_WIDTH_FACTOR))}ch"


def _box_width(lines: list) -> str:
    """One shared box width for every card built from ``lines``, in CSS
    "ch" units, from the single longest line's own visible letter count --
    see the module-level CSS comment for why this is computed here in
    Python rather than left to the browser to guess from HTML content."""
    return box_width_from_char_counts(_normalize_line(line)["char_count"] for line in lines)


def render_scroll_html(lines: list, *, scalable: bool = True) -> str:
    """Render ``lines`` (:func:`ankipasuk.tikkun.get_scroll_lines_for_range`'s
    own shape, or plain strings) into one self-contained
    ``<div class="lines" style="width: ...">`` block -- the exact same
    ``.line``/``.column``/``.fragment`` markup and box-width computation
    an Anki card uses (see :data:`SCROLL_CSS`), for display OUTSIDE Anki
    too -- :mod:`ankipasuk.webgui.api` uses this for the source section's
    own tikkun-style display. Empty string if ``lines`` is empty (no
    range to show, rather than an empty box).

    The width is ``calc(<box_width> * var(--ankipasuk-width-scale, 1))``,
    the same pattern the Anki card templates use (see ``_LINES_STYLE``)
    -- lets the caller wire up its own live ↔-/↔+ control (a CSS custom
    property on the document root) without needing to re-render this
    HTML on every click; the ``, 1`` fallback keeps the box at its
    computed width if nothing ever sets that variable. With ``scalable``
    off the width is the plain box width, for renderers without CSS
    variables (the PDF export, see :mod:`ankipasuk.ammud_pages`).
    """
    if not lines:
        return ""
    box_width = _box_width(lines)
    rows_html = _as_rows(group_lines(lines, 1))
    width = f"calc({box_width} * var(--ankipasuk-width-scale, 1))" if scalable else box_width
    style = f"width: {width}"
    return f'<div class="lines" style="{style}">{rows_html}</div>'


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
    reciting through the same 'aliyya. Font size and line spacing are
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
