"""Building the semantic data (see :mod:`ankipasuk.semantics`) from the UBS
Dictionary of Biblical Hebrew: the open release of the Semantic Dictionary
of Biblical Hebrew (SDBH, https://github.com/ubsicap/ubs-open-license,
CC BY-SA 4.0), on the words of the Open Scriptures Hebrew Bible.

SDBH gives each sense of a word (a *meaning*, ``LEXMeanings``) its lexical
semantic domains, a tree with three digits a level ("001001001": Objects ›
Beings › Deities), and every place where the word has that sense, as
``BBBCCCVVVSSWWW``: the book (in an English Bible's order), the chapter,
the verse (the Hebrew's numbering), a segment (unused for Hebrew), and the
word, numbered in even numbers. Its words are OSHB's *segments*, counted
the way OSHB writes them: a prefix is a word of its own (וְהָאָרֶץ, OSHB's
``c/d/776``, is three), and so is an article hidden in a preposition (בָּאָרֶץ,
``b/776`` with the morphology ``Rd``, is three too), but a suffix isn't. A
ketiv and its qere are two words.

So each pasuq's places are lined up with OSHB's segments in order
(:func:`line_up`): a place goes where its number says, unless a word
before it was split one way here and another there (SDBH keeps לָמָּה
whole; OSHB writes ``l/4100``), which moves the rest. A place matches
its segment if the segment's Strong's number is one of the entry's, or a
prefix is the entry's letter. Some places go where their number and their
neighbours put them although their Strong's numbers differ: the two
dictionaries file a few words apart (טוֹב, "good", 2895 or 2896; מִצְרַיִם
and מִצְרִי).

Each OSHB word then has the senses of its last segment, the word itself
(not its prefixes). This runs once, when the data is made
(``scripts/build_semantics.py``); the app only reads what it writes.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .shorashim_build import LETTER, _verse_words

# OSHB's books, by SDBH's numbers (an English Bible's order).
SDBH_BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr",
    "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer", "Lam", "Ezek", "Dan",
    "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal",
]
# OSHB's prefixes, as the letter SDBH's entry for them begins with: and,
# the article, the interrogative, the prepositions, the relative.
PREFIXES = {"c": "ו", "d": "ה", "i": "ה", "b": "ב", "k": "כ", "l": "ל", "m": "מ", "s": "ש"}
ARTICLE = "ה*"  # the article hidden in a preposition (Rd)
WINDOW = 4  # how far from its number a place may go
_DIGITS = re.compile(r"\d+")


@dataclass
class Segment:
    word: int  # its OSHB word, in the pasuq (as the shorashim data counts them)
    key: str  # its Strong's number ("0776"), a prefix's letter, or ARTICLE
    last: bool  # the word's own segment, after its prefixes


def strong(code: str) -> str:
    """A Strong's number as both are compared: four digits ("H0430",
    "430", "1254 a" -> "0430", "1254")."""
    m = _DIGITS.search(code)
    return m.group().zfill(4) if m else ""


def segments(words: list[tuple[str, str]]) -> list[Segment]:
    """A pasuq's OSHB words (``(lemma, morph)``, every ``<w>``, a ketiv
    and its qere both) as SDBH counts them."""
    out = []
    for k, (lemma, morph) in enumerate(words):
        parts = [p.strip() for p in lemma.split("/") if p.strip()]
        morphs = morph[1:].split("/") if morph else []  # (after the language)
        for i, part in enumerate(parts):
            key = strong(part) if part[:1].isdigit() else PREFIXES.get(part, part)
            out.append(Segment(k, key, i == len(parts) - 1))
            if i < len(morphs) and morphs[i] == "Rd":
                out.append(Segment(k, ARTICLE, False))
    return out


def oshb_verses(xml_text: str, osis: str) -> dict[str, list[tuple[str, str]]]:
    """A book's pesuqim, each its words' ``(lemma, morph)``, in the order
    and with the words the shorashim data has (see
    ankipasuk.shorashim_build._verse_words)."""
    out: dict[str, list[tuple[str, str]]] = {}
    for key, _v, el, _letters in _verse_words(xml_text, osis):
        words = out.setdefault(key, [])
        if el is not None:
            words.append((el.get("lemma", ""), el.get("morph", "")))
    return out


@dataclass
class Place:
    """The senses SDBH gives one of a pasuq's words (its number ``n``: the
    first word is 1), and what it can match: Strong's numbers, letters."""
    n: int
    senses: list[int] = field(default_factory=list)
    codes: set[str] = field(default_factory=set)
    letters: set[str] = field(default_factory=set)

    def matches(self, seg: Segment) -> bool:
        return (seg.key in self.codes or seg.key in self.letters
                or (seg.key == ARTICLE and "ה" in self.letters))


def line_up(segs: list[Segment], places: list[Place]) -> list[int | None]:
    """Each place's segment (an index into ``segs``), or None where it has
    none: in order, each within WINDOW of its number, the most matches,
    then the fewest shifts (one shift a word split differently)."""
    # The best way to place the places so far, by the last segment used:
    # (score, shift, segments).
    best: dict[int, tuple[int, int | None, list]] = {-1: (0, None, [])}
    for place in places:
        at = place.n - 1
        now: dict[int, tuple[int, int | None, list]] = {}

        def keep(last, option):
            if last not in now or option[0] > now[last][0]:
                now[last] = option

        for last, (score, shift, path) in best.items():
            keep(last, (score - 3, shift, [*path, None]))  # left out
            for j in range(max(last + 1, at - WINDOW), min(len(segs), at + WINDOW + 1)):
                gain = 10 if place.matches(segs[j]) else 0
                moved = 0 if shift is None else abs(j - at - shift)
                keep(j, (score + gain - moved, j - at, [*path, j]))
        best = now
    return max(best.values(), key=lambda option: option[0])[2]


@dataclass
class Senses:
    """SDBH's senses that have places, numbered, each ``[lemma (NFC), gloss,
    definition, [domain codes], places]``, and the places by pasuq:
    ``(book number, chapter, verse) -> [Place]``, in order."""
    table: list[list] = field(default_factory=list)
    places: dict[tuple[int, int, int], list[Place]] = field(default_factory=dict)


def _english(localized: list[dict] | None) -> dict:
    return next((x for x in localized or [] if x.get("LanguageCode") == "en"), {})


def read_sdbh(entries: list[dict]) -> Senses:
    out = Senses()
    by_verse: dict[tuple[int, int, int], dict[int, Place]] = defaultdict(dict)
    for entry in entries:
        codes = {c for c in map(strong, entry.get("StrongCodes") or []) if c}
        letters = set(LETTER.findall(entry.get("Lemma") or "")[:1])
        for base in entry.get("BaseForms") or []:
            for meaning in base.get("LEXMeanings") or []:
                refs = [r[:14] for r in meaning.get("LEXReferences") or [] if r[:14].isdigit()]
                if not refs:
                    continue
                sense = len(out.table)
                english = _english(meaning.get("LEXSenses"))
                domains = [d["DomainCode"] for d in meaning.get("LEXDomains") or [] if d.get("DomainCode")]
                out.table.append([unicodedata.normalize("NFC", entry.get("Lemma", "")),
                                  ", ".join(english.get("Glosses") or []),
                                  english.get("DefinitionShort") or "", domains, 0])
                for r in refs:
                    where, n = (int(r[:3]), int(r[3:6]), int(r[6:9])), int(r[11:14]) // 2
                    place = by_verse[where].setdefault(n, Place(n))
                    if sense not in place.senses:
                        place.senses.append(sense)
                    place.codes |= codes
                    place.letters |= letters
    out.places = {where: [ps[n] for n in sorted(ps)] for where, ps in by_verse.items()}
    return out


@dataclass
class Report:
    places: Counter = field(default_factory=Counter)  # matched, placed (numbers differ), left out
    words: Counter = field(default_factory=Counter)  # OSHB words: with a sense, without
    unmatched: Counter = field(default_factory=Counter)  # (SDBH's number, OSHB's) where they differ

    def lines(self) -> list[str]:
        def share(counter, key):
            return f"{counter[key]:,} ({100 * counter[key] / max(sum(counter.values()), 1):.2f}%)"
        return [f"SDBH's places: {sum(self.places.values()):,}; "
                + ", ".join(f"{k} {share(self.places, k)}" for k in ("matched", "placed", "left out")),
                f"OSHB's words: {sum(self.words.values()):,}; "
                + ", ".join(f"{k} {share(self.words, k)}" for k in ("with a sense", "without")),
                "the commonest Strong's numbers that differ (SDBH, OSHB): "
                + ", ".join(f"{a}/{b} {n}" for (a, b), n in self.unmatched.most_common(8))]


def book_senses(xml_text: str, osis: str, senses: Senses, report: Report) -> dict[str, list]:
    """A book's pesuqim, each its words' senses, as the shorashim data has
    its words: a sense's number, a list of them (a word SDBH gives two
    senses in one place), or -1. Counts each sense's places
    (``senses.table[i][4]``) and what was lined up (``report``)."""
    number = SDBH_BOOKS.index(osis) + 1
    out = {}
    for key, words in oshb_verses(xml_text, osis).items():
        ch, vs = map(int, key.split(":"))
        segs = segments(words)
        found: list[list[int]] = [[] for _ in words]
        places = senses.places.get((number, ch, vs), [])
        for place, j in zip(places, line_up(segs, places)):
            if j is None:
                report.places["left out"] += 1
                continue
            seg = segs[j]
            if place.matches(seg):
                report.places["matched"] += 1
            elif seg.key[:1].isdigit():
                report.places["placed"] += 1
                report.unmatched[(min(place.codes, default="?"), seg.key)] += 1
            else:
                report.places["left out"] += 1  # (a word's sense on a prefix)
                continue
            if seg.last:
                found[seg.word].extend(s for s in place.senses if s not in found[seg.word])
        for s in found:
            report.words["with a sense" if s else "without"] += 1
            for i in s:
                senses.table[i][4] += 1
        out[key] = [s[0] if len(s) == 1 else s if s else -1 for s in found]
    return out


def domain_table(domains: list[dict]) -> dict[str, list[str]]:
    """SDBH's lexical domains: code -> [label, description], in English."""
    out = {}
    for d in domains:
        english = _english(d.get("SemanticDomainLocalizations"))
        out[d["Code"]] = [english.get("Label", ""), english.get("Description", "")]
    return out
