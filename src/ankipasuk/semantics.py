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

A passage's *fields* (:func:`passage`) are its words' domains, all brought
to one level of the tree (4 unless the settings say 3 or 5): a deeper
domain is cut back to it, a shallower one stands for itself, its last
level repeated (People › People at level 4). A word has a field for each
of its domains, so some have two. Reference (names, pronouns, pointing
words) and particles are left out unless asked for.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from functools import cache, lru_cache
from pathlib import Path

from .shorashim import _book as _shorashim_book
from .shorashim import groups, keyness, lined_up
from .shorashim_build import OSIS_BOOKS, REFERENCE_BOOKS

DATA_DIR = Path(__file__).parent / "data" / "semantics"
LEVEL = 3  # digits a level of a domain's code
LEVELS = (3, 4, 5)  # the levels fields can be compared at
DEFAULT_LEVEL = 4
REFERENCE = "003"  # the top domain of names, pronouns and pointing words


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


def _senses_at(book: str, key: str, k: int) -> list[int]:
    found = _book(book).get(key, [])
    s = found[k] if k < len(found) else -1
    return s if isinstance(s, list) else [] if s < 0 else [s]


def field_path(field: str, level: int) -> list[str]:
    """A field's labels from the top down, ``level`` of them: a shallower
    domain's last one repeated ("001001003" at level 4: Objects, Beings,
    People, People)."""
    path = domain_path(field)
    return path + [path[-1]] * (level - len(path))


def fields_of(senses_here: list[int], level: int, reference: bool = False) -> list[str]:
    """A word's fields (its senses' domains, brought to ``level``), each
    once, in SDBH's order; Reference's only if ``reference``."""
    out: list[str] = []
    table = senses()
    for s in senses_here:
        for code in table[s][3]:
            field = code[:LEVEL * level]
            if (reference or not code.startswith(REFERENCE)) and field not in out:
                out.append(field)
    return out


def _particle(book: str, key: str, k: int) -> bool:
    words = _shorashim_book(book).get(key, [])
    g = words[k][1] if k < len(words) else None
    return g is not None and g >= 0 and groups()[g]["kind"] == "particle"


@lru_cache(maxsize=8)
def totals(level: int, reference: bool, particles: bool) -> tuple[Counter, int]:
    """Each field's words in the whole Tanakh, and the Tanakh's words
    with a field, as :func:`passage` counts them."""
    counts: Counter = Counter()
    words = 0
    for book in [*OSIS_BOOKS, *REFERENCE_BOOKS]:
        for key, found in _book(book).items():
            for k, s in enumerate(found):
                if s == -1 or (not particles and _particle(book, key, k)):
                    continue
                fields = fields_of(s if isinstance(s, list) else [s], level, reference)
                words += bool(fields)
                counts.update(fields)
    return counts, words


@cache
def levels() -> dict[int, float]:
    """How deep SDBH files the Tanakh's words: level -> the share of words
    with a sense whose (first) domain is at that level."""
    count: Counter = Counter()
    for _lemma, _gloss, _definition, codes, places in senses():
        if codes:
            count[len(codes[0]) // LEVEL] += places
    total = sum(count.values())
    return {n: round(count[n] / total, 4) for n in sorted(count)}


def passage(verse_data: list[dict], level: int = DEFAULT_LEVEL, reference: bool = False,
            particles: bool = False) -> dict:
    """The fields of every pasuq in ``verse_data`` (the app's fetched
    pesuqim), word by word as the shorashim's ``passage`` has them, and the
    fields that occur::

        {"level": 4,
         "verses": [[[[field, ...], [sense, ...]], ...], ...],
         "senses": {sense: [lemma, glosses, definition, [domain path, ...]]},
         "fields": {field: {"label", "path", "count", "verses", "words",
                            "total", "keyness", "ratio"}}}

    A word's senses are all SDBH gives it; its fields leave out what isn't
    asked for. A field's ``words`` are its commonest senses here, ``[lemma,
    glosses, times]``; ``verses`` the pesuqim it's in (by the verse
    lookup's labels); ``ratio`` how many times as often as in the whole
    Tanakh.
    """
    level = level if level in LEVELS else DEFAULT_LEVEL
    table = senses()
    verses, used = [], set()
    counts: Counter = Counter()
    where: dict[str, list[str]] = {}
    lemmas: dict[str, Counter] = {}
    for item, words in zip(verse_data, lined_up(verse_data)):
        label = f"{item['book']} {item['ch']}:{item['vs']}"
        row = []
        for _t, _s, at in words:
            here = [] if at is None else _senses_at(item["book"], *at)
            kept = here if particles or at is None or not _particle(item["book"], *at) else []
            fields = fields_of(kept, level, reference)
            row.append([fields, here])
            used.update(here)
            for field in fields:
                counts[field] += 1
                refs = where.setdefault(field, [])
                if not refs or refs[-1] != label:
                    refs.append(label)
                for s in kept:
                    if field in fields_of([s], level, reference):
                        lemmas.setdefault(field, Counter())[(table[s][0], table[s][1])] += 1
        verses.append(row)
    total, tanakh = totals(level, reference, particles)
    words = sum(1 for row in verses for fields, _s in row if fields)

    def info(field: str, n: int) -> dict:
        path = field_path(field, level)
        t = total.get(field, 0)
        return {"label": path[-1], "path": path, "count": n, "verses": where[field],
                "words": [[lemma, gloss, times] for (lemma, gloss), times in lemmas[field].most_common(6)],
                "total": t, "keyness": round(keyness(n, words, t, tanakh), 2),
                "ratio": round(n / words / (t / tanakh), 2) if t and words else 0}

    return {
        "level": level,
        "verses": verses,
        "senses": {s: [*table[s][:3], [" › ".join(domain_path(c)) for c in table[s][3]]]
                   for s in sorted(used)},
        "fields": {field: info(field, n) for field, n in counts.items()},
    }
