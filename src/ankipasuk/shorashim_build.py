"""Building the shorashim data (see :mod:`ankipasuk.shorashim`) from the
Open Scriptures Hebrew Bible.

OSHB (https://github.com/openscriptures/morphhb, CC BY 4.0, on the
Westminster Leningrad Codex, public domain) gives every word of the Tanakh
its lemma: a Strong's number, with a letter where two words share one
(``1254 a``, "create"; ``1254 b``, "be fat"), after any prefixes
(``c/d/776``: and-the-earth). Its lexicon (HebrewLexicon's
``LexicalIndex.xml``) gives each lemma its part of speech, a short gloss,
and its place in Brown-Driver-Briggs: a root's own entry (``etym
type="main" root="אבד"``), or a word filed under one (``etym type="sub"``,
naming the root's entry).

Every word gets a *group*, the thing the app counts and colours:

- a word filed under a root: the root (רֵאשִׁית, רִאשׁוֹן -> ראשׁ);
- a particle (prepositions, conjunctions, pronouns, אֵת, אֲשֶׁר, ...) or a
  name: just that word, in all its forms -- BDB derives some of them from
  roots (אֵת from אות, אַבְרָהָם from אבה), which would only be noise here;
- a word with no root in BDB: also itself.

This runs once, when the data is made (``scripts/build_shorashim.py``);
the app only reads what it writes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field

# Lexicon parts of speech: particles and names are their own group.
PARTICLE_POS = {
    "R", "C", "D", "T", "Tj", "Tm", "Ti", "Td", "To", "P", "Pp", "Pd", "Pi", "Pf", "Pr", "R C", "C?",
}
NAME_POS = {"Np", "Ag", "Ng"}

# A prefix written as a word of its own (לָהֶם, בָּם, מִמֶּנּוּ): its lemma
# is just the prefix's code.
PREFIX_WORDS = {
    "b": ("בְּ", "in"), "l": ("לְ", "to"), "k": ("כְּ", "like"), "m": ("מִן", "from"),
    "c": ("וְ", "and"), "d": ("הַ", "the"), "i": ("הֲ", "interrogative"), "s": ("שֶׁ", "who"),
}

# Glosses the lexicon gives that don't belong in this app.
GLOSS_OVERRIDES = {"3068": "the Name", "3069": "the Name"}  # not "Jehovah"

LETTER = re.compile(r"[\u05d0-\u05ea]")
_LEMMA = re.compile(r"(\d+)\s*([a-z])?")
_STRESS = "\u05ab"  # BDB's stress mark on headwords (אֶ֫רֶץ)

# OSHB's file and osisID for each book, by the name the app uses.
OSIS_BOOKS = {
    "Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut",
    "Joshua": "Josh", "Judges": "Judg", "I Samuel": "1Sam", "II Samuel": "2Sam", "I Kings": "1Kgs",
    "II Kings": "2Kgs", "Isaiah": "Isa", "Jeremiah": "Jer", "Ezekiel": "Ezek", "Hosea": "Hos",
    "Joel": "Joel", "Amos": "Amos", "Obadiah": "Obad", "Jonah": "Jonah", "Micah": "Mic", "Nahum": "Nah",
    "Habakkuk": "Hab", "Zephaniah": "Zeph", "Haggai": "Hag", "Zechariah": "Zech", "Malachi": "Mal",
    "Song of Songs": "Song", "Ruth": "Ruth", "Lamentations": "Lam", "Ecclesiastes": "Eccl", "Esther": "Esth",
}


def consonants(text: str) -> str:
    """Just the letters: what OSHB's words and Sefaria's are compared by."""
    return "".join(LETTER.findall(text))


@dataclass
class Entry:
    id: str
    word: str
    pos: str
    gloss: str
    strong: str | None
    aug: str | None
    etym_type: str | None
    etym_root: str | None
    etym_ref: str | None


@dataclass
class Group:
    key: str
    label: str
    kind: str  # "root", "word", "name" or "particle"
    gloss: str
    lemmas: Counter = field(default_factory=Counter)  # (headword, gloss) -> occurrences


def parse_lexicon(xml_text: str) -> dict[str, Entry]:
    """LexicalIndex.xml's entries, by id."""
    root = ET.fromstring(xml_text)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    entries = {}
    for e in root.iter(ns + "entry"):
        def text(tag, e=e):
            el = e.find(ns + tag)
            return (el.text or "").strip() if el is not None else ""
        xref = e.find(ns + "xref")
        etym = e.find(ns + "etym")
        strong = xref.get("strong") if xref is not None else None
        entries[e.get("id")] = Entry(
            id=e.get("id"), word=text("w").replace(_STRESS, ""), pos=text("pos"),
            gloss=GLOSS_OVERRIDES.get(strong, text("def")), strong=strong,
            aug=xref.get("aug") if xref is not None else None,
            etym_type=etym.get("type") if etym is not None else None,
            etym_root=etym.get("root") if etym is not None else None,
            etym_ref=(etym.text or "").strip() if etym is not None else None,
        )
    return entries


class Grouper:
    """Each lemma's group (see the module docstring), built as the books
    are read, so the table holds only groups that occur."""

    def __init__(self, entries: dict[str, Entry]):
        self.entries = entries
        self.by_strong: dict[tuple[str, str | None], str] = {}
        for e in entries.values():
            if e.strong:
                self.by_strong.setdefault((e.strong, e.aug), e.id)
                self.by_strong.setdefault((e.strong, None), e.id)
        self.groups: list[Group] = []
        self._index: dict[str, int] = {}

    def _group(self, key: str, label: str, kind: str, gloss: str) -> int:
        if key not in self._index:
            self._index[key] = len(self.groups)
            self.groups.append(Group(key, label, kind, gloss))
        return self._index[key]

    def _root(self, entry: Entry) -> Entry | None:
        """The root entry ``entry`` is filed under (itself, for a root)."""
        seen = set()
        e = entry
        while e is not None and e.id not in seen:
            seen.add(e.id)
            if e.etym_type == "main":
                return e
            if e.etym_type == "sub" and e.etym_ref:
                e = self.entries.get(e.etym_ref.split(",")[0].strip())
                continue
            return None
        return None

    def group_of(self, lemma: str) -> int | None:
        """The group index for an OSHB lemma (``c/d/776``), or None if it
        can't be read."""
        parts = [p.strip() for p in lemma.split("/") if p.strip()]
        main = next((p for p in reversed(parts) if _LEMMA.match(p)), None)
        if main is None:
            code = parts[-1] if parts else ""
            if code in PREFIX_WORDS:
                word, gloss = PREFIX_WORDS[code]
                return self._count(self._group(f"p:{code}", word, "particle", gloss), word, gloss)
            return None
        m = _LEMMA.match(main)
        entry_id = self.by_strong.get((m.group(1), m.group(2))) or self.by_strong.get((m.group(1), None))
        if entry_id is None:
            return None
        entry = self.entries[entry_id]
        if entry.pos in PARTICLE_POS:
            g = self._group(f"w:{entry.id}", entry.word, "particle", entry.gloss)
        elif entry.pos in NAME_POS:
            g = self._group(f"w:{entry.id}", entry.word, "name", entry.gloss)
        else:
            root = self._root(entry)
            if root is None:
                g = self._group(f"w:{entry.id}", entry.word, "word", entry.gloss)
            else:
                letters = root.etym_root or consonants(root.word)
                g = self._group(f"r:{root.id}", letters, "root", root.gloss)
        return self._count(g, entry.word, entry.gloss)

    def _count(self, g: int, word: str, gloss: str) -> int:
        self.groups[g].lemmas[(word, gloss)] += 1
        return g

    def table(self) -> list[dict]:
        """The groups, for the app: label, kind, gloss, and the words in
        each, most used first. A group's gloss is its commonest word's
        (כלל: "all", for כֹּל, not the root's "complete"), or the root's
        own where that's all there is."""
        out = []
        for g in self.groups:
            words = [[w, gl] for (w, gl), _n in g.lemmas.most_common()]
            gloss = next((gl for _w, gl in words if gl), g.gloss)
            out.append({"label": g.label, "kind": g.kind, "gloss": gloss, "words": words[:8]})
        return out


def book_words(xml_text: str, osis: str, grouper: Grouper) -> dict[str, list[list]]:
    """Each pasuq's words, in order, as ``[letters, group]``, or ``[letters,
    group, 1]`` for a qere (which follows its ketiv, as in Sefaria's
    "(ketiv) [qere]"), keyed "chapter:verse"."""
    root = ET.fromstring(xml_text)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    verses = {}
    for v in root.iter(ns + "verse"):
        book, ch, vs = v.get("osisID").split(".")
        if book != osis:
            continue
        words = []
        for el in v.iter():
            if el.tag != ns + "w":
                continue
            letters = consonants("".join(el.itertext()))
            if not letters:
                continue
            g = grouper.group_of(el.get("lemma", ""))
            words.append([letters, g, 1] if _is_qere(v, el, ns) else [letters, g])
        verses[f"{ch}:{vs}"] = words
    return verses


def _is_qere(verse: ET.Element, word: ET.Element, ns: str) -> bool:
    for rdg in verse.iter(ns + "rdg"):
        if rdg.get("type") == "x-qere" and any(w is word for w in rdg.iter(ns + "w")):
            return True
    return False
