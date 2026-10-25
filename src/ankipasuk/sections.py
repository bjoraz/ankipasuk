"""The Masoretic sections: where a petuḥa (an open section, the rest of the
line left blank) or a setuma (a closed one, a gap within the line) ends a
unit of the text, as Sefaria's Miqra according to the Masorah marks them
(``{פ}``, ``{ס}``), after the Aleppo Codex.

``scripts/build_sections.py`` collects them for every book the app reads
and bundles them (``data/sections.json.gz``); the app only looks them up,
offline. A break usually follows a pasuq. A few fall inside one (Bereshit
35:22, the short commandments of Shemot 20:13): those say after how many
of the pasuq's words, counted as :func:`ankipasuk.shorashim.pieces` splits
them, which is how the Text view counts its words.
"""

from __future__ import annotations

import gzip
import html
import json
import re
from functools import cache
from pathlib import Path

from .sefaria import sanitize_sefaria_verse
from .shorashim import pieces

DATA = Path(__file__).parent / "data" / "sections.json.gz"
PETUHA, SETUMA = "P", "S"
_MARK = re.compile(r"\{([פס])\}")

# Spans that are one section: their breaks are the layout, not the
# structure. The Decalogue's (a setuma or petuḥa after each commandment,
# some inside a pasuq), and Eikha 1-4's (a setuma after every pasuq of
# the acrostic). The break after the span stays. The songs (Az Yashir,
# Ha'azinu, Devora's, David's) need nothing: their layout has no breaks.
ONE_SECTION = [
    ("Exodus", (20, 2), (20, 14)), ("Deuteronomy", (5, 6), (5, 18)),
    *(("Lamentations", (ch, 1), (ch, 66 if ch == 3 else 22)) for ch in range(1, 5)),
]


def breaks_in(raw: str) -> list:
    """The breaks in one pasuq of Sefaria's text, in order: ``"P"`` or
    ``"S"`` for one after it, ``["P", n]`` for one after its first ``n``
    words."""
    text = html.unescape(raw)
    out: list = []
    for m in _MARK.finditer(text):
        kind = PETUHA if m.group(1) == "פ" else SETUMA
        if sanitize_sefaria_verse(text[m.end():]):  # words follow: inside the pasuq
            out.append([kind, len(pieces(sanitize_sefaria_verse(text[:m.start()])))])
        else:
            out.append(kind)
    return out


def one_section(book: str, found: dict[str, list]) -> dict[str, list]:
    """``found`` (a book's breaks, by ``"ch:vs"``) without those inside the
    spans of ONE_SECTION: only a span's last pasuq keeps its break after
    it."""
    out = dict(found)
    for name, first, last in ONE_SECTION:
        if name != book:
            continue
        for key in list(out):
            at = tuple(map(int, key.split(":")))
            if first <= at < last:
                del out[key]
            elif at == last:
                kept = [m for m in out[key] if isinstance(m, str)]
                if kept:
                    out[key] = kept
                else:
                    del out[key]
    return out


@cache
def _table() -> dict:
    return json.loads(gzip.decompress(DATA.read_bytes())) if DATA.exists() else {}


def breaks(book: str, ch: int, vs: int) -> list:
    """The breaks in or after a pasuq (see :func:`breaks_in`); none for a
    book that has no data."""
    return _table().get(book, {}).get(f"{ch}:{vs}", [])
