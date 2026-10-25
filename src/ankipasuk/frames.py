"""Frames (inclusio): a unit of the text that opens and closes with the
same words (docs/phrases.md, Frames).

The units are the Masoretic sections of a whole book (ankipasuk.sections),
alone or in runs of up to MAX_SECTIONS, and each petuḥa section (from a
petuḥa to the next, however many setumot it holds); a book without that
data (the Ketuvim but the Megillot) has no frames. A frame is either

- a *phrase*, one the phrase tests list in the book (not a formula), in the
  unit's first pasuq and its last; or
- a rare *word* (a dictionary word, few times in the book) found only near
  the unit's two ends: in its first and its last stretch (EDGE_SHARE of its
  pesuqim, at most EDGE_MAX), at least once in each, nowhere between; or
- a rare *field* (a semantic field, ankipasuk.semantics, in few of the
  book's pesuqim) found only near the unit's ends, as a word is, in other
  words at one end than at the other: the same meaning, said differently
  (וַיִּקַּח and וַיִּתֵּן, Marry, around Shemot 2:1-22). A field's frame
  in the same word at both ends is a word's frame.

Each has its chance: how likely its occurrences in the unit would fall so,
placed at random among the unit's pesuqim. A frame is kept if that chance,
times the units the phrase or word was tested in, is below STRENGTH; for
each, its strongest unit. The *sections* come first: a single section
(a setuma section) or a petuḥa section. A phrase or word is tested on them
first, against how many of them it could frame, and only if it frames none
on the other runs, against them all; and they're listed first. Words and
fields are the less sure: some are the same rare word in two neighbouring
stories, so they're listed as candidates.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from math import comb

from . import phrases as ph
from . import semantics as se
from .sections import _table as _sections

MAX_SECTIONS = 8
EDGE_SHARE, EDGE_MAX = 0.1, 5
RARE_IN_BOOK, RARE_IN_FRAME = 15, 4
FIELD_RARE_IN_BOOK = 25  # (pesuqim: a field is many words)
STRENGTH = 0.05


def _key(k: str) -> tuple[int, int]:
    ch, vs = k.split(":")
    return int(ch), int(vs)


def units(book: str, keys: list[str]) -> list[tuple[int, int, int, str]]:
    """The units of ``book`` (its pesuqim ``keys``, in order): ``(first,
    last, sections, kind)``, indices into ``keys``: every run of up to
    MAX_SECTIONS sections, and every petuḥa section. ``kind`` is "petuha"
    for a run from a petuḥa to the next (the book's start and end count as
    petuḥot) with only setumot between, "setuma" for another single
    section, "run" for the rest. A break inside a pasuq doesn't end a
    unit."""
    breaks = _sections().get(book, {})
    sections, start = [], 0  # (first, last, the break after it)
    for i, k in enumerate(keys):
        end = next((b for b in reversed(breaks.get(k, [])) if isinstance(b, str)), None)
        if end or i == len(keys) - 1:
            sections.append((start, i, end or "P"))
            start = i + 1
    out = []
    for a in range(len(sections)):
        petuha = a == 0 or sections[a - 1][2] == "P"  # (while it can still be a petuḥa section)
        for b in range(a, len(sections)):
            n = b - a + 1
            closes = sections[b][2] == "P"
            kind = "petuha" if petuha and closes else "setuma" if n == 1 else "run"
            if n <= MAX_SECTIONS or kind == "petuha":
                out.append((sections[a][0], sections[b][1], n, kind))
            if closes:
                petuha = False
            if n >= MAX_SECTIONS and not petuha:
                break
    return out


class _Best:
    """A phrase's or word's best unit: among the sections, and among them
    all (see the module's docstring)."""

    def __init__(self):
        self.best: dict[bool, tuple | None] = {True: None, False: None}
        self.tried = {True: 0, False: 0}

    def add(self, chance: float, unit: tuple, *more) -> None:
        for family in (True, False) if unit[3] != "run" else (False,):
            self.tried[family] += 1
            if self.best[family] is None or chance < self.best[family][0]:
                self.best[family] = (chance, unit, *more)

    def kept(self) -> tuple | None:
        """``(score, chance, unit, ...)``, or None if it frames nothing."""
        for family in (True, False):
            found = self.best[family]
            if found and found[0] * self.tried[family] < STRENGTH:
                return (found[0] * self.tried[family], *found)
        return None


def _only_at_the_ends(in_pasuq: list[dict], runs: list[tuple], rare: int) -> dict:
    """The things (words, fields) found only near a unit's two ends, each
    with its best unit (``_Best.kept``: score, chance, unit, and the
    pesuqim it's in there). ``in_pasuq`` has each pasuq's things, each with
    its tokens there; ``rare``, in how many of the book's pesuqim a thing
    may be."""
    where: dict = defaultdict(list)
    for i, things in enumerate(in_pasuq):
        for w in things:
            where[w].append(i)
    best: dict = defaultdict(_Best)
    for unit in runs:
        a, b = unit[:2]
        p = b - a + 1
        if p < 6:
            continue
        e = max(1, min(EDGE_MAX, round(p * EDGE_SHARE)))
        first = set().union(*(in_pasuq[x] for x in range(a, a + e)))
        last = set().union(*(in_pasuq[x] for x in range(b - e + 1, b + 1)))
        for w in first & last:
            if len(where[w]) > rare:
                continue
            occ = [x for x in where[w] if a <= x <= b]
            if len(occ) > RARE_IN_FRAME:
                continue
            m = len(occ)
            framed = all(x < a + e or x > b - e for x in occ)  # (else tried, and failed)
            best[w].add((comb(2 * e, m) - 2 * comb(e, m)) / comb(p, m) if framed else 1, unit, occ)
    return {w: kept for w, b in best.items() if (kept := b.kept())}


@lru_cache(maxsize=8)
def book_frames(book: str, level: int = se.DEFAULT_LEVEL) -> tuple:
    """The frames of a whole book, each ``{"word", "field", "key",
    "length", "first", "last", "sections", "unit", "ends", "chance",
    "score"}``: whether a word, its field (a field's frame, at ``level``),
    its lemmas, its length in tokens, its unit (first and last pasuq, as
    "ch:vs", how many sections, and its kind: see :func:`units`), the
    tokens it starts at in the unit's ends, and its chance (times the units
    tried: score). The sections' frames first."""
    c = ph.corpus()
    keys = sorted((k for (b, k) in c.verses if b == book), key=_key)
    if not keys or book not in _sections():
        return ()
    pos = {k: i for i, k in enumerate(keys)}
    runs = units(book, keys)
    out = []

    # Phrases: in the unit's first pasuq and its last.
    data = [{"book": book, "ch": _key(k)[0], "vs": _key(k)[1]} for k in keys]
    for r in ph._classify(c, ph._segments(c, data)):
        if r["formula"]:
            continue
        at: dict[int, list[int]] = defaultdict(list)
        for j in r["here"]:
            at[pos[c.where[j][1]]].append(j)
        best = _Best()
        for unit in runs:
            a, b = unit[:2]
            if b - a < 2 or a not in at or b not in at:
                continue
            p, m = b - a + 1, sum(1 for x in at if a <= x <= b)
            best.add(m * (m - 1) / (p * (p - 1)), unit)
        if kept := best.kept():
            score, chance, (a, b, n_sec, kind) = kept
            out.append({"word": False, "field": None, "key": r["key"], "length": r["length"],
                        "first": keys[a], "last": keys[b], "sections": n_sec, "unit": kind,
                        "ends": sorted(at[a] + at[b]), "chance": chance, "score": score})

    # Rare words, and rare fields, only near the unit's two ends: each
    # pasuq's content words (God's names aside), by lemma and by field.
    words: list[dict[int, list[int]]] = []
    fields: list[dict[str, list[int]]] = []
    for k in keys:
        a, z = c.verses[(book, k)]
        words.append(defaultdict(list))
        fields.append(defaultdict(list))
        for t in range(a, z):
            if c.lem[t] >= 0 and c.bits[t] & ph._CONTENT and c.strong[t] not in ph.GOD_NAMES:
                words[-1][c.lem[t]].append(t)
                senses = [s for w in range(c.first[t], c.last[t] + 1) for s in se._senses_at(book, k, w)]
                for f in se.fields_of(senses, level):
                    fields[-1][f].append(t)
    for w, (score, chance, (a, b, n_sec, kind), occ) in _only_at_the_ends(words, runs, RARE_IN_BOOK).items():
        ends = sorted(t for x in occ for t in words[x][w])
        out.append({"word": True, "field": None, "key": (w,), "length": 1, "first": keys[a], "last": keys[b],
                    "sections": n_sec, "unit": kind, "ends": ends, "chance": chance, "score": score})
    rare_fields = _only_at_the_ends(fields, runs, FIELD_RARE_IN_BOOK)
    for f, (score, chance, (a, b, n_sec, kind), occ) in rare_fields.items():
        e = max(1, min(EDGE_MAX, round((b - a + 1) * EDGE_SHARE)))
        opening = {c.lem[t] for x in occ if x < a + e for t in fields[x][f]}
        closing = {c.lem[t] for x in occ if x > b - e for t in fields[x][f]}
        if opening == closing:
            continue  # the same word: a word's frame
        ends = sorted(t for x in occ for t in fields[x][f])
        out.append({"word": False, "field": f, "key": (f,), "length": 1, "first": keys[a], "last": keys[b],
                    "sections": n_sec, "unit": kind, "ends": ends, "chance": chance, "score": score})
    return tuple(sorted(out, key=lambda f: (f["unit"] == "run", f["score"])))


def add_to(result: dict, verse_data: list[dict], level: int = se.DEFAULT_LEVEL) -> dict:
    """``result`` (:func:`ankipasuk.phrases.passage`) with the frames whose
    unit overlaps the loaded pesuqim, as phrase entries of the section
    "frame": ``[["sections", ids], ["runs", ids], ["words", ids],
    ["fields", ids]]``, the phrases framing a section, those framing a run
    of them, the words and the fields (at ``level``). Each has ``kinds``
    ["frame"], a ``key`` ("frame", its book and its words or field: one a
    book) and a ``frame`` ``{"word", "field", "first", "last", "sections",
    "unit", "chance"}`` (the unit's first and last pasuq as references; a
    field's path); its ``text`` is a field's words at the ends, its
    ``marks``, ``spans`` and ``verses`` its ends' words that are loaded,
    its ``places`` the ends that aren't."""
    c = ph.corpus()
    loaded: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for item in verse_data:
        loaded[item["book"]].add((item["ch"], item["vs"]))
    place = ph.Placer(c, verse_data) if verse_data else None
    entries, groups = result["phrases"], {"sections": [], "runs": [], "words": [], "fields": []}
    for book in loaded:
        for f in book_frames(book, level):
            lo, hi = _key(f["first"]), _key(f["last"])
            if not any(lo <= at <= hi for at in loaded[book]):
                continue
            n = f["length"]
            occ_marks = [m for m in (place.marks(j, n) for j in f["ends"]) if m]
            outside = [j for j in f["ends"] if not place.marks(j, n)]
            places, seen = [], set()  # one a pasuq
            for j in outside:
                if c.where[j] not in seen:
                    seen.add(c.where[j])
                    places.append({"ref": ph.ref(c, j, n), "at": j, "length": n})
            def text_at(j):
                marks = place.marks(j, n)
                return place.text(marks) if marks else " ".join(ph.letters(c, j, n))

            if f["field"]:  # its words at either end, each once
                text = " · ".join(dict.fromkeys(text_at(j) for j in f["ends"]))
            else:
                text = place.text(occ_marks[0]) if occ_marks else text_at(f["ends"][0])
            eid = len(entries)
            entries.append({
                "id": eid, "kinds": ["frame"],
                "key": f"frame {book} "
                       + (f"field {f['field']}" if f["field"] else ph.phrase_key(c, f["ends"][0], n)),
                "formula": None, "exceptional": None, "text": text,
                "here": len(occ_marks), "total": len(f["ends"]), "elsewhere": len(places), "places": places,
                "chapters": 0, "books": 1,
                "marks": sorted({m for ms in occ_marks for m in ms}), "spans": ph.Placer.spans(occ_marks),
                "verses": sorted({v for ms in occ_marks for v, _k in ms}), "children": {},
                "frame": {"word": f["word"], "first": f"{ph._name(book)} {f['first']}",
                          "field": " › ".join(se.field_path(f["field"], level)) if f["field"] else None,
                          "last": f"{ph._name(book)} {f['last']}", "sections": f["sections"],
                          "unit": f["unit"], "chance": f["chance"]},
            })
            group = ("fields" if f["field"] else "words" if f["word"]
                     else "runs" if f["unit"] == "run" else "sections")
            groups[group].append(eid)
    result["sections"]["frame"] = [[name, ids] for name, ids in groups.items() if ids]
    return result
