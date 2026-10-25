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
  roots (אֵת from אות, אַבְרָהָם from אבה), which would only be noise here.
  A name is one group by its spelling, however many people or places BDB
  tells apart under it, and its gloss is the name in the app's spelling
  (מֹשֶׁה: Moshe; see :mod:`ankipasuk.transliterate`);
- a people (חִתִּי, כְּנַעֲנִי, מוֹאָבִי) likewise, as a name, marked
  ``people``: a word the lexicon calls one (``Ag``, ``Ng``), or one OSHB's
  morphology calls one in most of its places -- the lexicon calls
  כְּנַעֲנִי a noun and מוֹאָבִי an adjective, and OSHB, word by word, is
  no steadier (:func:`peoples`);
- a word with no root in BDB: also itself.

Where BDB has two roots, or two words, with the same letters (לחם I
"bread", לחם II "battle"), they stay apart, numbered in BDB's order.

Each group also has its count in the whole Tanakh -- the books the app
reads from, and the rest of the Ketuvim (REFERENCE_BOOKS), which are only
counted -- so that a passage's key words can be told: the roots it uses
far more than the Tanakh does (:func:`ankipasuk.shorashim.keyness`).

For the phrases (:mod:`ankipasuk.phrases`), every word of the whole
Tanakh also gets its dictionary entry, numbered (:class:`Lemmas`), and a
few things OSHB's morphology and accents tell about it (:func:`book_lemmas`).

This runs once, when the data is made (``scripts/build_shorashim.py``);
the app only reads what it writes.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field

from .config import TROPE_UNICODE
from .transliterate import transliterate

# Lexicon parts of speech: particles and names are their own group.
PARTICLE_POS = {
    "R", "C", "D", "T", "Tj", "Tm", "Ti", "Td", "To", "P", "Pp", "Pd", "Pi", "Pf", "Pr", "R C", "C?",
}
NAME_POS = {"Np", "Ag", "Ng"}
PEOPLE_POS = {"Ag", "Ng"}  # of the names, peoples (gentilics)

# A prefix written as a word of its own (לָהֶם, בָּם, מִמֶּנּוּ): its lemma
# is just the prefix's code.
PREFIX_WORDS = {
    "b": ("בְּ", "in"), "l": ("לְ", "to"), "k": ("כְּ", "like"), "m": ("מִן", "from"),
    "c": ("וְ", "and"), "d": ("הַ", "the"), "i": ("הֲ", "interrogative"), "s": ("שֶׁ", "who"),
}

# The Name's gloss, in place of the lexicon's "Jehovah".
NAME_GLOSS = {"3068": "the Name", "3069": "the Name"}

# A plain meaning, shown with BDB's gloss, for common words whose BDB gloss
# is more its etymology than its meaning (הָיָה "fall out": "be"; קֹדֶשׁ
# "apartness": "holiness"; אַחַר "the hinder": "after"). Each is given with
# the gloss it goes with, so an entry sharing the number (עָשָׂה "press",
# beside עָשָׂה "do") isn't given it.
MEANINGS = {
    ("310", "the hinder"): "after",
    ("369", "nothing"): "there is not",
    ("389", "surely"): "only, surely",
    ("413", "motion to"): "to",
    ("430", "gods"): "God, gods",
    ("520", "ell"): "cubit",
    ("559", "utter"): "say",
    ("681", "conjunction"): "beside",
    ("834", "who"): "who, which, that",
    ("853", "mark of the accusative"): "(marks the object)",
    ("935", "come in"): "come",
    ("996", "interval"): "between",
    ("1107", "not unto"): "apart from",
    ("1115", "failure"): "not, except",
    ("1157", "separation"): "behind, for",
    ("1288", "kneel"): "bless",
    ("1289", "kneel"): "bless",
    ("1697", "speech"): "word, thing",
    ("1961", "fall out"): "be",
    ("2233", "sowing"): "seed",
    ("2320", "newness"): "month",
    ("2416", "alive"): "living, alive",
    ("2896", "pleasant"): "good",
    ("2896", "a good thing"): "good",
    ("3205", "bear"): "give birth",
    ("3282", "purpose"): "because",
    ("3426", "being"): "there is",
    ("3427", "sit"): "sit, dwell",
    ("3519", "abundance"): "glory",
    ("3605", "the whole"): "all",
    ("3606", "the whole"): "all",
    ("3627", "article"): "vessel",
    ("3820", "inner man"): "heart",
    ("3824", "inner man"): "heart",
    ("3966", "muchness"): "very",
    ("4069", "wherefore?"): "why?",
    ("4397", "messenger"): "messenger, angel",
    ("4605", "higher part"): "above",
    ("4672", "attain to"): "find",
    ("4725", "standing-place"): "place",
    ("5030", "spokesman"): "prophet",
    ("5046", "be conspicuous"): "tell",
    ("5048", "what is conspicuous"): "in front of",
    ("5612", "missive"): "book",
    ("5649", "slave"): "servant",
    ("5650", "slave"): "servant",
    ("5750", "a going round"): "still, again",
    ("5769", "long duration"): "forever, world",
    ("5921", "above"): "on, over",
    ("5975", "take one’s stand"): "stand",
    ("5980", "juxtaposition"): "beside",
    ("6213", "do"): "do, make",
    ("6680", "lay charge"): "command",
    ("6944", "apartness"): "holiness",
    ("7307", "breath"): "spirit, wind",
    ("7535", "leanness"): "only",
    ("7725", "turn back"): "return",
    ("7965", "completeness"): "peace",
    ("7969", "a three"): "three",
    ("8478", "the under part"): "under, instead of",
}

LETTER = re.compile(r"[\u05d0-\u05ea]")
_LEMMA = re.compile(r"(\d+)\s*([a-z])?")
_STRESS = "\u05ab"  # BDB's stress mark on headwords (אֶ֫רֶץ)
_FINALS = str.maketrans("ךםןףץ", "כמנפצ")

# OSHB's file and osisID for each book, by the name the app uses.
OSIS_BOOKS = {
    "Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut",
    "Joshua": "Josh", "Judges": "Judg", "I Samuel": "1Sam", "II Samuel": "2Sam", "I Kings": "1Kgs",
    "II Kings": "2Kgs", "Isaiah": "Isa", "Jeremiah": "Jer", "Ezekiel": "Ezek", "Hosea": "Hos",
    "Joel": "Joel", "Amos": "Amos", "Obadiah": "Obad", "Jonah": "Jonah", "Micah": "Mic", "Nahum": "Nah",
    "Habakkuk": "Hab", "Zephaniah": "Zeph", "Haggai": "Hag", "Zechariah": "Zech", "Malachi": "Mal",
    "Song of Songs": "Song", "Ruth": "Ruth", "Lamentations": "Lam", "Ecclesiastes": "Eccl", "Esther": "Esth",
}
# The rest of the Tanakh, which the app has no readings from: counted, for
# each group's count in the whole Tanakh, and searched for the phrases'
# other places. By Sefaria's name, as OSIS_BOOKS.
REFERENCE_BOOKS = {
    "Psalms": "Ps", "Proverbs": "Prov", "Job": "Job", "Daniel": "Dan", "Ezra": "Ezra", "Nehemiah": "Neh",
    "I Chronicles": "1Chr", "II Chronicles": "2Chr",
}

# Names of God (Strong's numbers): יהוה, אֱלֹהִים, אֲדֹנָי, אֵל, אֱלוֹהַּ, שַׁדַּי,
# עֶלְיוֹן, and צְבָאוֹת.
GOD_NAMES = {"3068", "3069", "430", "136", "410", "433", "7706", "5945", "6635"}

# A word's flags in the phrase data (book_lemmas).
QERE, PROPER, GENTILIC, NUMERAL, CONSTRUCT, ETNAHTA, KING, DUKE = (1 << i for i in range(8))
# The ta'amim by their rank in the app's table (config.TROPE_UNICODE): the
# kings (segolta, shalshelet, zaqef qatan and gadol, tifḥa) and the dukes
# (revia', zarqa, pashta, yetiv, tevir). OSHB writes a few zarqas in prose
# as U+0598, which in the poetic books is tsinnorit (never cut at).
_KINGS = {ch for ch, (_name, rank) in TROPE_UNICODE.items() if rank == 2}
_DUKES = {ch for ch, (_name, rank) in TROPE_UNICODE.items() if rank == 3} | {"\u0598"}


def _verse_words(xml_text: str, osis: str):
    """OSHB's words, as ``(chapter:verse, verse, word, letters)``: every
    ``<w>`` with letters, a qere included (it follows its ketiv)."""
    root = ET.fromstring(xml_text)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    for v in root.iter(ns + "verse"):
        book, ch, vs = v.get("osisID").split(".")
        if book != osis:
            continue
        key = f"{ch}:{vs}"
        yield key, None, None, ""  # the pasuq, even with no words
        for el in v.iter():
            if el.tag != ns + "w":
                continue
            letters = consonants("".join(el.itertext()))
            if letters:
                yield key, v, el, letters


def _parse_lemma(lemma: str) -> tuple[re.Match | None, str, int]:
    """A lemma (``c/d/776``) as its Strong's number (a match of _LEMMA, or
    None for a prefix written as a word), the prefix code, and how many
    prefixes come before it."""
    parts = [p.strip() for p in lemma.split("/") if p.strip()]
    for k, part in enumerate(parts):
        m = _LEMMA.match(part)
        if m:
            return m, "", k
    return None, parts[-1] if parts else "", len(parts)


def consonants(text: str) -> str:
    """Just the letters: what OSHB's words and Sefaria's are compared by."""
    return "".join(LETTER.findall(text))


@dataclass
class Entry:
    id: str
    word: str
    pos: str
    gloss: str  # BDB's, as the lexicon has it
    strong: str | None
    aug: str | None
    etym_type: str | None
    etym_root: str | None
    etym_ref: str | None
    meaning: str = ""  # a plain meaning beside it, for some (MEANINGS)
    bdb: str = ""  # its place in BDB ("v.dv.ab"), which sorts in BDB's order


@dataclass
class Group:
    key: str
    label: str
    kind: str  # "root", "word", "name" or "particle"
    gloss: str
    meaning: str = ""
    lemmas: Counter = field(default_factory=Counter)  # (headword, gloss, meaning) -> occurrences
    total: int = 0  # its words in the whole Tanakh
    people: bool = False  # a name of a people (kind "name")


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
        bdb = text("def")
        entries[e.get("id")] = Entry(
            id=e.get("id"), word=text("w").replace(_STRESS, ""), pos=text("pos"),
            gloss=NAME_GLOSS.get(strong, bdb), meaning=MEANINGS.get((strong, bdb), ""), strong=strong,
            bdb=xref.get("bdb", "") if xref is not None else "",
            aug=xref.get("aug") if xref is not None else None,
            etym_type=etym.get("type") if etym is not None else None,
            etym_root=etym.get("root") if etym is not None else None,
            etym_ref=(etym.text or "").strip() if etym is not None else None,
        )
    return entries


class Grouper:
    """Each lemma's group (see the module docstring), built as the books
    are read, so the table holds only groups that occur.

    With ``reference`` set, a book is only counted: its words add to their
    groups' totals, and to :attr:`words`, but make no new groups and
    don't count towards a group's words and gloss."""

    def __init__(self, entries: dict[str, Entry], peoples: set[str] = frozenset()):
        self.entries = entries
        self.peoples = set(peoples) | {e.id for e in entries.values() if e.pos in PEOPLE_POS}
        self.by_strong: dict[tuple[str, str | None], str] = {}
        for e in entries.values():
            if e.strong:
                self.by_strong.setdefault((e.strong, e.aug), e.id)
        # A lemma without its letter, where the number has several entries,
        # is the one without a letter, or else OSHB's first, "a" (עַיִן:
        # "eye", not "spring").
        for e in entries.values():
            if e.strong and (e.strong, None) not in self.by_strong:
                self.by_strong[(e.strong, None)] = self.by_strong.get((e.strong, "a"), e.id)
        self.groups: list[Group] = []
        self._index: dict[str, int] = {}
        self.reference = False
        self.words = 0  # words with a group, in the whole Tanakh

    def _group(self, key: str, label: str, kind: str, gloss: str, meaning: str = "") -> int | None:
        if key not in self._index:
            if self.reference:
                self.words += 1  # a word of the Tanakh, just not of the app's books
                return None
            self._index[key] = len(self.groups)
            self.groups.append(Group(key, label, kind, gloss, meaning))
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

    def entry_of(self, lemma: str) -> Entry | str | None:
        """An OSHB lemma's (``c/d/776``) lexicon entry; the prefix code for a
        prefix written as a word (``l``, for לָכֶם); None if it can't be read."""
        m, code, _k = _parse_lemma(lemma)
        if m is None:
            return code if code in PREFIX_WORDS else None
        entry_id = self.by_strong.get((m.group(1), m.group(2))) or self.by_strong.get((m.group(1), None))
        return self.entries[entry_id] if entry_id is not None else None

    def group_of(self, lemma: str) -> int | None:
        """The group index for an OSHB lemma (``c/d/776``), or None if it
        can't be read."""
        entry = self.entry_of(lemma)
        if entry is None:
            return None
        if isinstance(entry, str):
            word, gloss = PREFIX_WORDS[entry]
            g = self._group(f"p:{entry}", word, "particle", gloss)
            return None if g is None else self._count(g, word, gloss)
        if entry.pos in PARTICLE_POS:
            g = self._group(f"w:{entry.id}", entry.word, "particle", entry.gloss, entry.meaning)
        elif entry.pos in NAME_POS or entry.id in self.peoples:
            spelling = unicodedata.normalize("NFC", entry.word)
            gloss = entry.gloss if entry.strong in NAME_GLOSS else transliterate(entry.word)
            people = entry.id in self.peoples
            g = self._group(f"{'g' if people else 'n'}:{spelling}", entry.word, "name", gloss)
            if g is not None:
                self.groups[g].people = people
        else:
            root = self._root(entry)
            if root is None:
                g = self._group(f"w:{entry.id}", entry.word, "word", entry.gloss, entry.meaning)
            else:
                letters = root.etym_root or consonants(root.word)
                g = self._group(f"r:{root.id}", letters, "root", root.gloss, root.meaning)
        return None if g is None else self._count(g, entry.word, entry.gloss, entry.meaning)

    def _count(self, g: int, word: str, gloss: str, meaning: str = "") -> int:
        self.groups[g].total += 1
        self.words += 1
        if self.reference:
            return g
        if self.groups[g].kind == "name":
            gloss, meaning = self.groups[g].gloss, ""  # the name as the app spells it, not OSHB's English
        self.groups[g].lemmas[(word, gloss, meaning)] += 1
        return g

    def _numbers(self) -> list[int]:
        """Each group's number among the groups of its kind written the
        same (BDB's homonyms: לחם I, לחם II; shin and sin told apart), in
        BDB's order; 0 for a group that's the only one."""
        def place(g: Group) -> str:
            entry = self.entries.get(g.key.split(":", 1)[1])
            return entry.bdb if entry is not None else ""

        same: dict[tuple[str, str], list[int]] = {}
        for i, g in enumerate(self.groups):
            if g.kind == "name":
                continue  # one group per spelling already
            if g.kind == "root":
                written = "".join(re.findall("[\u05d0-\u05ea][\u05c1\u05c2]?", g.label)).translate(_FINALS)
            else:
                written = unicodedata.normalize("NFC", g.label)
            same.setdefault((g.kind, written), []).append(i)
        numbers = [0] * len(self.groups)
        for members in same.values():
            if len(members) > 1:
                members.sort(key=lambda i: place(self.groups[i]))
                for n, i in enumerate(members, 1):
                    numbers[i] = n
        return numbers

    def table(self) -> list[dict]:
        """The groups, for the app: label, kind, gloss (BDB's) and plain
        meaning (where there's one), the words in each, most used first,
        as ``[word, gloss, meaning]``, and its count in the Tanakh
        (``total``). A group's gloss is its commonest word's (כלל: "the
        whole", for כֹּל, not the root's "complete"), or the root's own
        where that's all there is."""
        out = []
        for g, number in zip(self.groups, self._numbers()):
            words = [[w, gl, mn] for (w, gl, mn), _n in g.lemmas.most_common()]
            gloss, meaning = next(((gl, mn) for _w, gl, mn in words if gl), (g.gloss, g.meaning))
            row = {"label": g.label, "kind": g.kind, "gloss": gloss, "meaning": meaning,
                   "number": number, "words": words[:8], "total": g.total}
            if g.people:
                row["people"] = True
            out.append(row)
        return out


def peoples(grouper: Grouper, xml_texts) -> set[str]:
    """The lexicon entries OSHB's morphology calls a people (``Ng``,
    ``Ag``) in most of their places, over all the books ``xml_texts``:
    כְּנַעֲנִי and יְבוּסִי, which the lexicon calls nouns, מוֹאָבִי and
    עַמּוֹנִי, adjectives -- but not בֵּן, a people twice in its 4,940."""
    tagged: Counter = Counter()
    seen: Counter = Counter()
    for xml_text in xml_texts:
        root = ET.fromstring(xml_text)
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        for el in root.iter(ns + "w"):
            entry = grouper.entry_of(el.get("lemma", ""))
            if isinstance(entry, Entry):
                seen[entry.id] += 1
                if _morph(el.get("morph", ""))[0][:2] in ("Ng", "Ag"):
                    tagged[entry.id] += 1
    return {e for e, n in tagged.items() if 2 * n > seen[e]}


def verb_form(morph: str) -> str | None:
    """A verb's form, as OSHB's morphology codes its conjugation: w
    wayyiqtol, p qatal, i yiqtol, q weqatal, v imperative, j jussive, h
    cohortative, r / s active / passive participle, a / c infinitive
    absolute / construct; None for any other word."""
    main, _suffix = _morph(morph)
    return main[2] if main.startswith("V") and len(main) >= 3 else None


def book_words(xml_text: str, osis: str, grouper: Grouper) -> dict[str, list[list]]:
    """Each pasuq's words, in order, as ``[letters, group]``, or ``[letters,
    group, 1]`` for a qere (which follows its ketiv, as in Sefaria's
    "(ketiv) [qere]"); a verb as ``[letters, group, qere (0 or 1), form]``
    (:func:`verb_form`). Keyed "chapter:verse"."""
    verses: dict[str, list[list]] = {}
    for key, v, el, letters in _verse_words(xml_text, osis):
        words = verses.setdefault(key, [])
        if el is None:
            continue
        g = grouper.group_of(el.get("lemma", ""))
        ns = el.tag[:el.tag.index("}") + 1] if el.tag.startswith("{") else ""
        qere = _is_qere(v, el, ns)
        form = verb_form(el.get("morph", ""))
        words.append([letters, g, int(qere), form] if form else [letters, g, 1] if qere else [letters, g])
    return verses


class Lemmas:
    """Every dictionary entry the Tanakh's words have, numbered in the order
    they're met, each as ``[strong, kind]``: kind "p" a particle, "n" a
    name, "m" a name of two words (בֵּית לֶחֶם), "g" a people (as the
    shorashim have them, :func:`peoples`), "w" any other word."""

    def __init__(self, grouper: Grouper):
        self.grouper = grouper
        self.table: list[list] = []
        self._index: dict[str, int] = {}

    def of(self, lemma: str) -> int:
        """A lemma's number, or -1 if it can't be read."""
        entry = self.grouper.entry_of(lemma)
        if entry is None:
            return -1
        key = f"p:{entry}" if isinstance(entry, str) else entry.id
        if key not in self._index:
            if isinstance(entry, str):
                row = [None, "p"]
            elif entry.pos in PARTICLE_POS:
                row = [entry.strong, "p"]
            elif entry.id in self.grouper.peoples:
                row = [entry.strong, "g"]
            elif entry.pos in NAME_POS:
                row = [entry.strong, "m" if " " in entry.word.strip() else "n"]
            else:
                row = [entry.strong, "w"]
            self._index[key] = len(self.table)
            self.table.append(row)
        return self._index[key]


def _morph(morph: str) -> tuple[str, bool]:
    """OSHB's morphology code (``HC/Vqw3ms``) as its main word's part
    (``Vqw3ms``), and whether there's a suffix (``/Sp3ms``)."""
    segments = morph[1:].split("/") if morph else []
    main = [x for x in segments if not x.startswith("S")]
    return (main[-1] if main else ""), any(x.startswith("S") for x in segments)


def book_lemmas(xml_text: str, osis: str, lemmas: Lemmas) -> dict[str, list[list]]:
    """Each pasuq's words, as :func:`book_words` has them (the same words
    in the same order), for the phrases: ``[lemma, flags]``.

    flags: QERE; PROPER (a name) and GENTILIC (a people), as the word's
    entry is (:class:`Lemmas`), the same everywhere; NUMERAL and
    CONSTRUCT (without a suffix), from OSHB's morphology; ETNAHTA, KING (a
    segolta, shalshelet, zaqef or tifḥa on it) and DUKE (a revia', zarqa,
    pashta, yetiv or tevir), from its accents."""
    verses: dict[str, list[list]] = {}
    for key, v, el, _letters in _verse_words(xml_text, osis):
        words = verses.setdefault(key, [])
        if el is None:
            continue
        lemma = el.get("lemma", "")
        n = lemmas.of(lemma)
        main, suffix = _morph(el.get("morph", ""))
        text = "".join(el.itertext())
        accents = set(unicodedata.normalize("NFD", text))
        ns = el.tag[:el.tag.index("}") + 1] if el.tag.startswith("{") else ""
        kind = lemmas.table[n][1] if n >= 0 else None
        flags = ((QERE if _is_qere(v, el, ns) else 0) | (PROPER if kind in ("n", "m") else 0)
                 | (GENTILIC if kind == "g" else 0)
                 | (NUMERAL if main[:2] in ("Ac", "Ao") else 0)
                 | (CONSTRUCT if main[:1] in ("N", "A") and main.endswith("c") and not suffix else 0)
                 | (ETNAHTA if "\u0591" in accents else 0) | (KING if accents & _KINGS else 0)
                 | (DUKE if accents & _DUKES else 0))
        words.append([n, flags])
    return verses


def _is_qere(verse: ET.Element, word: ET.Element, ns: str) -> bool:
    for rdg in verse.iter(ns + "rdg"):
        if rdg.get("type") == "x-qere" and any(w is word for w in rdg.iter(ns + "w")):
            return True
    return False
