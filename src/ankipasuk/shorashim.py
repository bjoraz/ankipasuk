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

A passage's *key words* (Buber's Leitwörter) are the groups it uses far
more than the Tanakh as a whole: see :func:`keyness`.
"""

from __future__ import annotations

import gzip
import json
import math
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import cache, lru_cache
from pathlib import Path

from .shorashim_build import OSIS_BOOKS, REFERENCE_BOOKS, consonants

DATA_DIR = Path(__file__).parent / "data" / "shorashim"
MAQAF = "\u05be"
_FINALS = str.maketrans("ךםןףץ", "כמנפצ")


@cache
def _table() -> dict:
    return json.loads(gzip.decompress((DATA_DIR / "groups.json.gz").read_bytes()))


def groups() -> list[dict]:
    """Every group: ``{"label", "kind", "gloss", "meaning", "number",
    "words", "total"}`` -- see
    :meth:`ankipasuk.shorashim_build.Grouper.table`."""
    return _table()["groups"]


def tanakh_words() -> int:
    """The Tanakh's words that have a group: what each group's ``total``
    is out of."""
    return _table()["words"]


def keyness(count: int, words: int, total: int, tanakh: int) -> float:
    """How much more a passage of ``words`` words uses a group, ``count``
    times, than the rest of the Tanakh does (the group ``total`` times in
    ``tanakh`` words, the passage's among them); below 0, how much less.

    Dunning's log-likelihood (G²), as corpus linguists rank key words by:
    it weighs how much more often against how sure that is, so a root used
    twelve times where the Tanakh's rate would give two ranks above a rare
    word that's there once."""
    rest, rest_words = max(total - count, 0), max(tanakh - words, 0)
    if not count or not words or not rest_words:
        return 0.0
    expected = words * (count + rest) / (words + rest_words)
    g2 = count * math.log(count / expected)
    if rest:
        g2 += rest * math.log(rest / (rest_words * (count + rest) / (words + rest_words)))
    return 2 * g2 if count / words > rest / rest_words else -2 * g2


@cache
def _book(book: str) -> dict[str, list[list]]:
    osis = OSIS_BOOKS.get(book) or REFERENCE_BOOKS.get(book)
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
    spelling, word for word. Each word's index in ``oshb_words``."""
    result: list[int | None] = [None] * len(letters)
    matcher = SequenceMatcher(None, letters, [w[0] for w in oshb_words], autojunk=False)
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op == "equal" or (op == "replace" and a2 - a1 == b2 - b1):
            for k in range(a2 - a1):
                result[a1 + k] = b1 + k
    return result


def line_up(sefaria_letters: list[str], oshb_words: list[list]) -> list[int | None]:
    """The OSHB word (its index in ``oshb_words``, ``[letters, group(,
    1)]``) of each of Sefaria's words, given by their letters ("" for a
    token with none, like paseq)."""
    targets = [i for i, s in enumerate(sefaria_letters) if s]
    result: list[int | None] = [None] * len(sefaria_letters)
    letters = [sefaria_letters[i] for i in targets]
    for with_qere in (True, False):
        words = list(range(len(oshb_words))) if with_qere \
            else [k for k, w in enumerate(oshb_words) if not (len(w) > 2 and w[2])]  # not a qere
        if len(words) == len(letters):
            for i, k in zip(targets, words):
                result[i] = k
            return result
    for i, k in zip(targets, _match(letters, oshb_words)):
        result[i] = k
    return result


def align(sefaria_letters: list[str], oshb_words: list[list]) -> list[int | None]:
    """The group of each of Sefaria's words (see :func:`line_up`)."""
    return [None if k is None else oshb_words[k][1] for k in line_up(sefaria_letters, oshb_words)]


def verse_words(book: str, ch: int, vs: int, pointed: str) -> list[list]:
    """One pasuq's words as ``[text, separator, group]`` (group None where
    there's none: no data for the book, or a word that didn't line up)."""
    return [[t, s, _group_at(book, at)] for t, s, at in _verse_places(book, ch, vs, pointed)]


def _verse_places(book: str, ch: int, vs: int, pointed: str) -> list[list]:
    """One pasuq's words as ``[text, separator, (chapter:verse, index)]``:
    each with the OSHB word it is, or None."""
    ps = pieces(pointed)
    key = f"{ch}:{vs}"
    oshb = _book(book).get(key)
    if not oshb:
        return [[t, s, None] for t, s in ps]
    ks = line_up([consonants(t) for t, _s in ps], oshb)
    return [[t, s, None if k is None else (key, k)] for (t, s), k in zip(ps, ks)]


def _group_at(book: str, at: tuple[str, int] | None) -> int | None:
    return None if at is None else _book(book)[at[0]][at[1]][1]


def _form_at(book: str, at: tuple[str, int] | None) -> str | None:
    """The verb form of the OSHB word ``at`` (see
    :func:`ankipasuk.shorashim_build.verb_form`), or None."""
    word = None if at is None else _book(book)[at[0]][at[1]]
    return word[3] if word is not None and len(word) > 3 else None


def _unmatched(words: list[list]) -> int:
    return sum(1 for t, _s, at in words if at is None and consonants(t))


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
        keys = sorted((k for k in data if k.split(":")[0] == str(ch)), key=lambda k: int(k.split(":")[1]))
        theirs = [(k, n) for k in keys for n in range(len(data[k]))]
        ours = [(i, j) for i in indices for j, (t, _s, _at) in enumerate(verses[i]) if consonants(t)]
        found = _match([consonants(verses[i][j][0]) for i, j in ours], [data[k][n] for k, n in theirs])
        if sum(f is None for f in found) < before:
            for (i, j), f in zip(ours, found):
                verses[i][j][2] = None if f is None else theirs[f]


def lined_up(verse_data: list[dict]) -> list[list[list]]:
    """Every loaded pasuq's words as ``[text, separator, (chapter:verse,
    index)]``: each Sefaria word with the OSHB word (of the same book) it
    is, or None -- what :func:`passage` and :mod:`ankipasuk.phrases`
    both start from. The last few are kept."""
    key = tuple((item["book"], item["ch"], item["vs"], item["pointed"]) for item in verse_data)
    return [[list(w) for w in verse] for verse in _lined_up(key)]


@lru_cache(maxsize=4)
def _lined_up(key: tuple) -> tuple:
    verse_data = [{"book": b, "ch": c, "vs": v, "pointed": p} for b, c, v, p in key]
    verses = [_verse_places(item["book"], item["ch"], item["vs"], item["pointed"]) for item in verse_data]
    _realign_chapters(verse_data, verses)
    return tuple(tuple(tuple(w) for w in verse) for verse in verses)


def passage(verse_data: list[dict]) -> dict:
    """The words of every pasuq in ``verse_data`` (the app's fetched
    pesuqim) with their groups, and the groups that occur, each with how
    often, and in which pesuqim (by the verse lookup's labels)::

        {"verses": [[[text, sep, group, form], ...], ...],
         "groups": {group: {"label", "display", "kind", "gloss", "words",
                            "count", "verses", "keyness", "ratio"}}}

    ``ratio`` is how many times as often as in the whole Tanakh.
    """
    table = groups()
    counts: Counter = Counter()
    where: dict[int, list[str]] = {}
    verses = [[[t, s, _group_at(item["book"], at), _form_at(item["book"], at)] for t, s, at in words]
              for item, words in zip(verse_data, lined_up(verse_data))]
    for item, words in zip(verse_data, verses):
        label = f"{item['book']} {item['ch']}:{item['vs']}"
        for _t, _s, g, _f in words:
            if g is None:
                continue
            counts[g] += 1
            refs = where.setdefault(g, [])
            if not refs or refs[-1] != label:
                refs.append(label)
    words = sum(counts.values())
    tanakh = tanakh_words()

    def key(g: int, n: int) -> dict:
        total = table[g].get("total", 0)
        return {"keyness": round(keyness(n, words, total, tanakh), 2),
                "ratio": round(n / words / (total / tanakh), 2) if total else 0}

    return {
        "verses": verses,
        "groups": {
            g: {**table[g], "display": display(table[g]), "count": n, "verses": where[g], **key(g, n)}
            for g, n in counts.items()
        },
    }
