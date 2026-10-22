"""Frames (inclusio): a unit of the text that opens and closes with the
same words (docs/phrases.md, Frames).

The units are the Masoretic sections of a whole book (ankipasuk.sections),
alone or in runs of up to MAX_SECTIONS; a book without that data (the
Ketuvim but the Megillot) has no frames. A frame is either

- a *phrase*, one the phrase tests list in the book (not a formula), in the
  unit's first pasuq and its last; or
- a rare *word* (a dictionary word, few times in the book) found only near
  the unit's two ends: in its first and its last stretch (EDGE_SHARE of its
  pesuqim, at most EDGE_MAX), at least once in each, nowhere between.

Each has its chance: how likely its occurrences in the unit would fall so,
placed at random among the unit's pesuqim. A frame is kept if that chance,
times the units the phrase or word was tested in, is below STRENGTH; for
each, its strongest unit. Words are the less sure: some are the same rare
word in two neighbouring stories, so they're listed as candidates.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from math import comb

from . import phrases as ph
from .sections import _table as _sections

MAX_SECTIONS = 8
EDGE_SHARE, EDGE_MAX = 0.1, 5
RARE_IN_BOOK, RARE_IN_FRAME = 15, 4
STRENGTH = 0.05


def _key(k: str) -> tuple[int, int]:
    ch, vs = k.split(":")
    return int(ch), int(vs)


def units(book: str, keys: list[str]) -> list[tuple[int, int, int]]:
    """The units of ``book`` (its pesuqim ``keys``, in order): ``(first,
    last, sections)``, indices into ``keys``, every run of up to
    MAX_SECTIONS sections. A break inside a pasuq doesn't end a unit."""
    breaks = _sections().get(book, {})
    sections, start = [], 0
    for i, k in enumerate(keys):
        if any(isinstance(b, str) for b in breaks.get(k, [])) or i == len(keys) - 1:
            sections.append((start, i))
            start = i + 1
    return [(sections[a][0], sections[b][1], b - a + 1)
            for a in range(len(sections)) for b in range(a, min(len(sections), a + MAX_SECTIONS))]


@lru_cache(maxsize=8)
def book_frames(book: str) -> tuple:
    """The frames of a whole book, each ``{"word", "key", "length",
    "first", "last", "sections", "ends", "chance", "score"}``: whether a
    word, its lemmas, its length in tokens, its unit (first and last
    pasuq, as "ch:vs", and how many sections), the tokens it starts at in
    the unit's ends, and its chance (times the units tried: score)."""
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
        best, tried = None, 0
        for a, b, n_sec in runs:
            if b - a < 2 or a not in at or b not in at:
                continue
            tried += 1
            p, m = b - a + 1, sum(1 for x in at if a <= x <= b)
            chance = m * (m - 1) / (p * (p - 1))
            if best is None or chance < best[0]:
                best = (chance, a, b, n_sec)
        if best and best[0] * tried < STRENGTH:
            chance, a, b, n_sec = best
            out.append({"word": False, "key": r["key"], "length": r["length"], "first": keys[a],
                        "last": keys[b], "sections": n_sec, "ends": sorted(at[a] + at[b]), "chance": chance,
                        "score": chance * tried})

    # Rare words: only near the unit's two ends.
    in_pasuq: list[dict[int, list[int]]] = []
    for k in keys:
        a, z = c.verses[(book, k)]
        words: dict[int, list[int]] = defaultdict(list)
        for t in range(a, z):
            if c.lem[t] >= 0 and c.bits[t] & ph._CONTENT and c.strong[t] not in ph.GOD_NAMES:
                words[c.lem[t]].append(t)
        in_pasuq.append(words)
    where: dict[int, list[int]] = defaultdict(list)
    for i, words in enumerate(in_pasuq):
        for w in words:
            where[w].append(i)
    best_w: dict[int, tuple] = {}
    tried_w: dict[int, int] = defaultdict(int)
    for a, b, n_sec in runs:
        p = b - a + 1
        if p < 6:
            continue
        e = max(1, min(EDGE_MAX, round(p * EDGE_SHARE)))
        first = set().union(*(in_pasuq[x] for x in range(a, a + e)))
        last = set().union(*(in_pasuq[x] for x in range(b - e + 1, b + 1)))
        for w in first & last:
            if len(where[w]) > RARE_IN_BOOK:
                continue
            occ = [x for x in where[w] if a <= x <= b]
            if len(occ) > RARE_IN_FRAME:
                continue
            tried_w[w] += 1
            if all(x < a + e or x > b - e for x in occ):
                m = len(occ)
                chance = (comb(2 * e, m) - 2 * comb(e, m)) / comb(p, m)
                if w not in best_w or chance < best_w[w][0]:
                    best_w[w] = (chance, a, b, n_sec, occ)
    for w, (chance, a, b, n_sec, occ) in best_w.items():
        if chance * tried_w[w] < STRENGTH:
            ends = sorted(t for x in occ for t in in_pasuq[x][w])
            out.append({"word": True, "key": (w,), "length": 1, "first": keys[a], "last": keys[b],
                        "sections": n_sec, "ends": ends, "chance": chance, "score": chance * tried_w[w]})
    return tuple(sorted(out, key=lambda f: f["score"]))


def add_to(result: dict, verse_data: list[dict]) -> dict:
    """``result`` (:func:`ankipasuk.phrases.passage`) with the frames whose
    unit overlaps the loaded pesuqim, as phrase entries of the section
    "frame" (``[["phrases", ids], ["words", ids]]``). Each has ``kinds``
    ["frame"] and a ``frame`` ``{"word", "first", "last", "sections",
    "chance"}`` (the unit's first and last pasuq as references); its
    ``marks``, ``spans`` and ``verses`` are its ends' words that are
    loaded, its ``places`` the ends that aren't."""
    c = ph.corpus()
    loaded: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for item in verse_data:
        loaded[item["book"]].add((item["ch"], item["vs"]))
    place = ph.Placer(c, verse_data) if verse_data else None
    entries, groups = result["phrases"], {"phrases": [], "words": []}
    for book in loaded:
        for f in book_frames(book):
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
            text = place.text(occ_marks[0]) if occ_marks else " ".join(ph.letters(c, f["ends"][0], n))
            eid = len(entries)
            entries.append({
                "id": eid, "kinds": ["frame"], "formula": None, "exceptional": None, "text": text,
                "here": len(occ_marks), "total": len(f["ends"]), "elsewhere": len(places), "places": places,
                "chapters": 0, "books": 1,
                "marks": sorted({m for ms in occ_marks for m in ms}), "spans": ph.Placer.spans(occ_marks),
                "verses": sorted({v for ms in occ_marks for v, _k in ms}), "children": {},
                "frame": {"word": f["word"], "first": f"{ph._name(book)} {f['first']}",
                          "last": f"{ph._name(book)} {f['last']}", "sections": f["sections"],
                          "chance": f["chance"]},
            })
            groups["words" if f["word"] else "phrases"].append(eid)
    result["sections"]["frame"] = [[name, ids] for name, ids in groups.items() if ids]
    return result
