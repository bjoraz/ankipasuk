"""Shorashim: each word of a passage with its root, and how often each root
occurs.

The roots come from the Open Scriptures Hebrew Bible and its lexicon (see
:mod:`ankipasuk.shorashim_build`, which made the data in
``data/shorashim/``): every word belongs to a *group* -- its root, or, for
a particle, a name, or a word with no root, the word itself in all its
forms. OSHB's text is the Leningrad Codex; the app's is Sefaria's, so each
pasuq's words are lined up with OSHB's here:

- word by word, when the two have the same words (nearly every pasuq --
  a spelling difference here and there, הטהרה / הטהורה, doesn't matter);
- Sefaria writes a ketiv and its qere as two words, "(הוצא) [הַיְצֵא]",
  and so does OSHB's data (the qere marked), so those line up too;
- otherwise by their letters, and a word that matches nothing has no
  group;
- where the two divide a chapter into pesuqim differently (the Ten
  Commandments, Shemot 20 and Devarim 5), a pasuq lines up badly on its
  own, so its whole chapter is lined up at once instead.

A word joined by maqaf is two words here, as in OSHB.
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

from .shorashim_build import OSIS_BOOKS, consonants

DATA_DIR = Path(__file__).parent / "data" / "shorashim"
MAQAF = "\u05be"
_FINALS = str.maketrans("ךםןףץ", "כמנפצ")


@cache
def groups() -> list[dict]:
    """Every group: ``{"label", "kind", "gloss", "words"}`` -- see
    :meth:`ankipasuk.shorashim_build.Grouper.table`."""
    return json.loads(gzip.decompress((DATA_DIR / "groups.json.gz").read_bytes()))


@cache
def _book(book: str) -> dict[str, list[list]]:
    osis = OSIS_BOOKS.get(book)
    path = DATA_DIR / f"{osis}.json.gz"
    if osis is None or not path.exists():
        return {}
    return json.loads(gzip.decompress(path.read_bytes()))


def display(group: dict) -> str:
    """A group as the app shows it: a root letter by letter (א־מ־ר, no
    final forms between the letters), any other word as it's written."""
    if group["kind"] != "root":
        return group["label"]
    letters = re.findall(r"[\u05d0-\u05ea][\u05c1\u05c2]?", group["label"])
    return MAQAF.join(letter.translate(_FINALS) for letter in letters)


def pieces(pointed: str) -> list[list[str]]:
    """A pasuq's words as ``[text, separator]``: split at spaces and at
    maqaf, the separator being what follows the word (" ", "־" or "")."""
    out = []
    for token in pointed.split():
        parts = token.split(MAQAF)
        for i, part in enumerate(parts):
            out.append([part, MAQAF if i < len(parts) - 1 else " "])
    if out:
        out[-1][1] = ""
    return out


def _match(letters: list[str], oshb_words: list[list]) -> list[int | None]:
    """Line up by letters: runs that match, and runs that differ only in
    spelling, word for word."""
    result: list[int | None] = [None] * len(letters)
    matcher = SequenceMatcher(None, letters, [w[0] for w in oshb_words], autojunk=False)
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op == "equal" or (op == "replace" and a2 - a1 == b2 - b1):
            for k in range(a2 - a1):
                result[a1 + k] = oshb_words[b1 + k][1]
    return result


def align(sefaria_letters: list[str], oshb_words: list[list]) -> list[int | None]:
    """The group of each of Sefaria's words (given by their letters, "" for
    a token with none, like paseq), from OSHB's ``[letters, group(, 1)]``."""
    targets = [i for i, s in enumerate(sefaria_letters) if s]
    result: list[int | None] = [None] * len(sefaria_letters)
    letters = [sefaria_letters[i] for i in targets]
    for with_qere in (True, False):
        words = oshb_words if with_qere else [w for w in oshb_words if len(w) < 3]
        if len(words) == len(letters):
            for i, w in zip(targets, words):
                result[i] = w[1]
            return result
    for i, g in zip(targets, _match(letters, oshb_words)):
        result[i] = g
    return result


def verse_words(book: str, ch: int, vs: int, pointed: str) -> list[list]:
    """One pasuq's words as ``[text, separator, group]`` (group None where
    there's none: no data for the book, or a word that didn't line up)."""
    ps = pieces(pointed)
    oshb = _book(book).get(f"{ch}:{vs}")
    if not oshb:
        return [[t, s, None] for t, s in ps]
    gs = align([consonants(t) for t, _s in ps], oshb)
    return [[t, s, g] for (t, s), g in zip(ps, gs)]


def _unmatched(words: list[list]) -> int:
    return sum(1 for t, _s, g in words if g is None and consonants(t))


def _realign_chapters(verse_data: list[dict], verses: list[list[list]]) -> None:
    """Line up, chapter by chapter, where some pasuq didn't line up on its
    own: all of the chapter's loaded pesuqim against all of OSHB's
    chapter, kept (in place) only if that matches more words."""
    chapters: dict[tuple[str, int], list[int]] = {}
    for i, item in enumerate(verse_data):
        chapters.setdefault((item["book"], item["ch"]), []).append(i)
    for (book, ch), indices in chapters.items():
        before = sum(_unmatched(verses[i]) for i in indices)
        if not before:
            continue
        data = _book(book)
        theirs = [w for key, ws in sorted(
            ((k, v) for k, v in data.items() if k.split(":")[0] == str(ch)),
            key=lambda kv: int(kv[0].split(":")[1])) for w in ws]
        ours = [(i, j) for i in indices for j, (t, _s, _g) in enumerate(verses[i]) if consonants(t)]
        groups_found = _match([consonants(verses[i][j][0]) for i, j in ours], theirs)
        if sum(g is None for g in groups_found) < before:
            for (i, j), g in zip(ours, groups_found):
                verses[i][j][2] = g


def passage(verse_data: list[dict]) -> dict:
    """The words of every pasuq in ``verse_data`` (the app's fetched
    pesuqim) with their groups, and the groups that occur, each with how
    often, and in which pesuqim (by the verse lookup's labels)::

        {"verses": [[[text, sep, group], ...], ...],
         "groups": {group: {"label", "display", "kind", "gloss", "words",
                            "count", "verses"}}}
    """
    table = groups()
    counts: Counter = Counter()
    where: dict[int, list[str]] = {}
    verses = [verse_words(item["book"], item["ch"], item["vs"], item["pointed"]) for item in verse_data]
    _realign_chapters(verse_data, verses)
    for item, words in zip(verse_data, verses):
        label = f"{item['book']} {item['ch']}:{item['vs']}"
        for _t, _s, g in words:
            if g is None:
                continue
            counts[g] += 1
            refs = where.setdefault(g, [])
            if not refs or refs[-1] != label:
                refs.append(label)
    return {
        "verses": verses,
        "groups": {
            g: {**table[g], "display": display(table[g]), "count": n, "verses": where[g]}
            for g, n in counts.items()
        },
    }
