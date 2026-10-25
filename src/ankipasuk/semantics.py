"""Each word's sense and its semantic domains, from the UBS Dictionary of
Biblical Hebrew (the open Semantic Dictionary of Biblical Hebrew, SDBH),
lined up with OSHB's words (see :mod:`ankipasuk.semantics_build`,
docs/semantics.md).

A *sense* is one of a word's meanings in SDBH: its lemma, glosses, a short
definition and its lexical domains. A *domain* is a node of SDBH's tree,
three digits a level: "001" Objects, "001001" Beings, "001001001" Deities.
Each OSHB word (as the shorashim data has them: every ``<w>``, a ketiv and
its qere both) has the senses SDBH gives it there, usually one; the
function words SDBH hasn't done yet (עַל, אֶל, כִּי, כֹּל, ...) have none.
"""

from __future__ import annotations

import gzip
import json
from functools import cache
from pathlib import Path

from .shorashim_build import OSIS_BOOKS, REFERENCE_BOOKS

DATA_DIR = Path(__file__).parent / "data" / "semantics"
LEVEL = 3  # digits a level of a domain's code


@cache
def _table() -> dict:
    return json.loads(gzip.decompress((DATA_DIR / "senses.json.gz").read_bytes()))


def senses() -> list[list]:
    """Every sense: ``[lemma, glosses, definition, [domain codes],
    places]``, ``places`` its words in the whole Tanakh."""
    return _table()["senses"]


def domains() -> dict[str, list[str]]:
    """Every domain: code -> ``[label, description]``."""
    return _table()["domains"]


def domain_path(code: str) -> list[str]:
    """A domain's labels from the top down: "001001001" -> ["Objects",
    "Beings", "Deities"]."""
    table = domains()
    return [table.get(code[:i], ["?"])[0] for i in range(LEVEL, len(code) + 1, LEVEL)]


@cache
def _book(book: str) -> dict[str, list]:
    osis = OSIS_BOOKS.get(book) or REFERENCE_BOOKS.get(book)
    path = DATA_DIR / f"{osis}.json.gz"
    if osis is None or not path.exists():
        return {}
    return json.loads(gzip.decompress(path.read_bytes()))


def verse_senses(book: str, ch: int, vs: int) -> list[list[int]]:
    """Each OSHB word of the pasuq, its senses (numbers into
    :func:`senses`; none for a word SDBH doesn't give one)."""
    return [s if isinstance(s, list) else [] if s < 0 else [s] for s in _book(book).get(f"{ch}:{vs}", [])]
