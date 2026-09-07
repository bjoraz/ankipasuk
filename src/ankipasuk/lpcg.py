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

Pipeline: a list of already-fully-rendered line strings (currently plain
pointed Hebrew verse text; eventually tikkun-styled HTML, see the project's
tikkun.io-calquing plan) goes in, a list of Anki-note field dicts comes
out. Callers are responsible for grouping those field dicts under
"deckName"/"modelName"/"tags" and pushing them via
:func:`ankipasuk.anki_connect.operations.add_notes`.
"""

from __future__ import annotations

MODEL_NAME = "Ankipasuk Aliyah"
FIELD_NAMES = ["Line", "Context", "Title", "Author", "Sequence", "Prompt"]
BEGINNING_MARKER = "[Beginning]"

_FRONT_TEMPLATE = """\
<div class="title">{{Title}} {{Sequence}}</div>
{{#Author}}<div class="author">{{Author}}</div>{{/Author}}

<br>

<div class="lines">
    {{Context}}
    <div class="cloze">
        {{#Prompt}}{{Prompt}}{{/Prompt}}
        {{^Prompt}}[...]{{/Prompt}}
    </div>
</div>"""

_BACK_TEMPLATE = """\
<div class="title">{{Title}} {{Sequence}}</div>
{{#Author}}<div class="author">{{Author}}</div>{{/Author}}

<br>

<div class="lines">
    {{Context}}
    <div class="cloze">{{Line}}</div>
</div>"""

CARD_TEMPLATES = [{"Name": "Recite", "Front": _FRONT_TEMPLATE, "Back": _BACK_TEMPLATE}]

CSS = """\
.card {
    font-family: "SBL Hebrew", "Ezra SIL", "Noto Serif Hebrew", arial;
    font-size: 22px;
    color: black;
    background-color: white;
}

.lines {
    text-align: right;
    direction: rtl;
    margin-left: 30px;
    margin-right: 30px;
}

.lines p {
    margin-top: 0px;
    margin-bottom: 0px;
}

.cloze {
    font-weight: bold;
    color: blue;
}

.nightMode .cloze {
    filter: invert(85%);
}

.title, .author {
    text-align: center;
    font-size: small;
    direction: ltr;
}
"""


def group_lines(lines: list[str], group_size: int) -> list[list[str]]:
    """Chunk ``lines`` into consecutive groups of ``group_size`` (the last
    group may be shorter). ``group_size=1`` -- the common case -- makes
    every physical line its own group, i.e. a no-op grouping."""
    if group_size < 1:
        raise ValueError("group_size must be at least 1.")
    return [lines[i:i + group_size] for i in range(0, len(lines), group_size)]


def _as_html(groups: list[list[str]]) -> str:
    return "".join(f"<p>{line}</p>" for group in groups for line in group)


def _prompt_for(n_lines: int) -> str:
    """AnkiLPCG shows a bare "[...]" cloze prompt (the template's own
    default, encoded here as an empty Prompt field) when exactly one line
    is being recited, and "[...N]" when reciting more than one -- e.g. at
    the end of a recitation window that runs past the end of the text."""
    return "" if n_lines == 1 else f"[...{n_lines}]"


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

    ``lines`` must already be fully rendered (HTML is fine -- each line is
    wrapped in its own ``<p>``, same as AnkiLPCG). No blank-line, comment,
    or indentation conventions are applied here: unlike AnkiLPCG's own
    poem-editor preprocessing, this deliberately does *no* text munging,
    so a tikkun-styled HTML line containing e.g. a "#" in a hex color
    can't be silently mistaken for a comment.
    """
    groups = group_lines(lines, group_size)
    fields: list[dict[str, str]] = []

    for seq, _group in enumerate(groups, start=1):
        context_start = max(0, seq - 1 - context_lines)
        context_groups = groups[context_start:seq - 1]
        context_html = _as_html(context_groups)
        if len(context_groups) < context_lines:
            context_html = f"<p>{BEGINNING_MARKER}</p>" + context_html

        recite_groups = groups[seq - 1:seq - 1 + recite_lines]
        n_recite_lines = sum(len(g) for g in recite_groups)

        fields.append({
            "Line": _as_html(recite_groups),
            "Context": context_html,
            "Title": title,
            "Author": author,
            "Sequence": str(seq),
            "Prompt": _prompt_for(n_recite_lines),
        })

    return fields
