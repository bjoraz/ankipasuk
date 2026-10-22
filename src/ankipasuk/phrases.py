"""Phrases: the word sequences of a passage that recur in the Tanakh,
sorted into refrains, echoes and idioms, with formulas set apart.

docs/phrases.md describes the choices, the tests and their thresholds;
this follows it section by section. In short:

- The Tanakh is one sequence of dictionary words (*tokens*), from the
  data :func:`ankipasuk.shorashim_build.book_lemmas` made: prefixes and
  suffixes don't count, the object marker אֵת is left out, the qere is
  read, a two-word name is one token, and no phrase runs from one book
  into the next.
- From each token of the passage, a phrase is followed through all its
  occurrences in the Tanakh while two or more remain, and kept where it
  can't be extended without losing one (*closed*); then cut where the
  ta'amim divide it and trimmed (:func:`_find`).
- Each is then tested (:func:`_classify`): a refrain, an echo, an idiom,
  any or all of them, unless it's a formula (:func:`formula_class`).
"""

from __future__ import annotations

import gzip
import json
import math
import threading
from array import array
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, fields
from functools import cache
from pathlib import Path
from statistics import NormalDist

from .config import BOOK_HEBREW_NAMES, OTHER_BOOK_HEBREW_NAMES
from .shorashim import _book, line_up, lined_up, pieces
from .shorashim_build import (
    CONSTRUCT,
    DUKE,
    ETNAHTA,
    GENTILIC,
    GOD_NAMES,
    KING,
    NUMERAL,
    OSIS_BOOKS,
    PROPER,
    QERE,
    REFERENCE_BOOKS,
    consonants,
)

DATA_DIR = Path(__file__).parent / "data" / "phrases"
BOOKS = {**OSIS_BOOKS, **REFERENCE_BOOKS}  # Sefaria's name -> OSHB's


# --- the tests' thresholds (docs/phrases.md, "Thresholds") -------------------
@dataclass(frozen=True)
class Thresholds:
    """What a phrase needs to be listed; the app's settings can change
    them (:meth:`from_settings`)."""

    content_words: int = 2
    refrain_here: int = 2
    refrain_chance: float = 1e-3
    echo_places: int = 3
    echo_chance: float = 1e-3
    idiom_occurrences: int = 4
    idiom_chapters: int = 3
    idiom_chance: float = 1e-3  # of the G² at each split
    idiom_bound: float = 0.1
    rare_title: int = 10  # places in the Tanakh
    concentrated: float = 1 / 3  # of a wording's places, in the passage

    @property
    def idiom_g2(self) -> float:
        """The G² whose chance is ``idiom_chance`` (one degree of freedom:
        10.83 for 1/1000)."""
        return NormalDist().inv_cdf(1 - self.idiom_chance / 2) ** 2

    @classmethod
    def from_settings(cls, values: dict | None) -> Thresholds:
        """From saved settings: each within its LIMITS, the default for
        what's missing or not a number."""
        out = {}
        for f in fields(cls):
            value, (low, high) = (values or {}).get(f.name), LIMITS[f.name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
                continue
            value = min(max(value, low), high)
            out[f.name] = round(value) if f.type == "int" else float(value)
        return cls(**out)


# How far each threshold may be set.
LIMITS = {
    "content_words": (2, 6), "refrain_here": (2, 10), "refrain_chance": (1e-9, 0.05),
    "echo_places": (1, 10), "echo_chance": (1e-9, 0.05), "idiom_occurrences": (3, 50),
    "idiom_chapters": (2, 30), "idiom_chance": (1e-9, 0.05), "idiom_bound": (0.01, 1.0),
    "rare_title": (0, 100), "concentrated": (0.05, 1.0),
}
DEFAULTS = Thresholds()

# --- words, by Strong's number ----------------------------------------------
OBJECT_MARKER = "853"
NOT_CONTENT = {"3605", "3606"}  # כֹּל
NEGATIONS = {"3808", "408"}  # לֹא, אַל
SPEECH_VERBS = {"559", "1696", "6030"}  # אָמַר, דָּבַר, עָנָה: trimmed off a phrase's end
TITLE_BEFORE = {"6440", "5869"}  # פְּנֵי, עֵינֵי, before a name of God
FATHER = "1"
TSEVAOT = "6635"  # צְבָאוֹת: a name of God only after one

# Family words: son, daughter, father, brother, wife, house, land, king,
# people, tribe (two words), clan, city, beyond.
KIN = {"1121", "1323", "1", "251", "802", "1004", "776", "4428", "5971", "4294", "7626", "4940", "5892",
       "5676"}
# Year, month, day, cubit, sheqel, length, breadth, height, weight, beqa,
# kikkar; son (בן שנה).
MEASURE = {"8141", "2320", "3117", "520", "8255", "753", "7341", "6967", "4948", "1235", "3603", "1121"}

# The formula classes after God's names and titles (docs/phrases.md, the
# table): name -> (core words, other words allowed, names allowed,
# numerals allowed, needs a name or numeral).
CLASSES = {
    "names and their families": (set(), KIN | GOD_NAMES, True, False, True),
    # say, speak, word, utterance, answer; with be, people
    "speech": ({"559", "1696", "1697", "5002", "6030"}, GOD_NAMES | KIN | {"1961", "5971"},
               True, False, False),
    "numbers, dates and measures": (set(), MEASURE, False, True, True),
    # beget, live, die, count, generations, number, head; with male, name, go out, host
    "genealogies and censuses": ({"3205", "2421", "4191", "6485", "8435", "4557", "1538"},
                                 KIN | MEASURE | {"2145", "8034", "3318", "6635"}, True, True, True),
    "time": ({"1961"}, {"3117", "6256"}, True, True, False),  # be; day, time
}
TITLES = "God's names and titles"
FORMULA_CLASSES = [TITLES, *CLASSES]

# A token's own bits.
_CONTENT, _NEG, _LIGHT, _AFTER_ET = 1, 2, 4, 8
# The break after a token, by strength: a duke (revia', zarqa, pashta,
# yetiv, tevir), a king (segolta, shalshelet, zaqef, tifḥa), an etnaḥta, a
# sof pasuq. A phrase is cut at kings and stronger; a duke can only end one.
_DUKE, _KING, _ETNAHTA, _SOF = 1, 2, 3, 4


class Corpus:
    """The Tanakh as tokens, in parallel arrays, from ``lemmas`` (the
    dictionary words, ``[strong, kind]``) and ``books`` (``[(name,
    {"ch:vs": [[lemma, flags], ...]})]``, as the data has them).
    A token of -1 is a barrier: a word without a dictionary word, or the
    end of a book."""

    def __init__(self, lemmas: list[list], books: Iterable[tuple[str, dict]]):
        assert len(lemmas) < 1 << 14, "pairs are keyed by two lemmas in 28 bits"
        self.lem = array("i")
        self.bits = bytearray()
        self.flags = bytearray()  # the data's (shorashim_build: PROPER, ...)
        self.brk = bytearray()
        self.strong: list[str | None] = []
        self.where: list[tuple[str, str]] = []  # (book, ch:vs)
        self.first, self.last = array("h"), array("h")  # its OSHB words in the pasuq
        self.verses: dict[tuple[str, str], tuple[int, int]] = {}
        for book, verses in books:
            for key, words in verses.items():
                start = len(self.lem)
                self._add_verse(lemmas, (book, key), words)
                self.verses[(book, key)] = (start, len(self.lem))
            self._add(-1, None, None, 0, (book, ""), 0, 0, False, _SOF)
        self.n = sum(1 for x in self.lem if x >= 0)
        self.freq = Counter(x for x in self.lem if x >= 0)
        self.pairs: dict[int, list[int]] = defaultdict(list)
        lem = self.lem
        for j in range(len(lem) - 1):
            if lem[j] >= 0 and lem[j + 1] >= 0:
                self.pairs[lem[j] << 14 | lem[j + 1]].append(j)
        self._counts: dict[tuple, int] = {}

    def _add_verse(self, lemmas, where, words) -> None:
        toks: list[list] = []  # [lemma, strong, kind, flags, first, last, after_et]
        after_et = False
        for k, w in enumerate(words):
            n, flags = w
            first = k
            if flags & QERE and toks and toks[-1][5] == k - 1:
                first = toks.pop()[4]  # the qere is read, its ketiv not
            strong, kind = lemmas[n] if n >= 0 else (None, None)
            if strong == OBJECT_MARKER:
                after_et = True
                continue
            if toks and kind == "m" and toks[-1][0] == n:  # בֵּית לֶחֶם, one name
                breaks = ETNAHTA | KING | DUKE  # the break after it is its last word's
                toks[-1][5], toks[-1][3] = k, toks[-1][3] & ~breaks | flags & breaks
                continue
            toks.append([n, strong, kind, flags, first, k, after_et])
            after_et = False
        last_x = len(toks) - 1
        for x, (n, strong, kind, flags, first, last, et) in enumerate(toks):
            brk = (_SOF if x == last_x else _ETNAHTA if flags & ETNAHTA else _KING if flags & KING
                   else _DUKE if flags & DUKE else 0)
            self._add(n, strong, kind, flags, where, first, last, et, brk)

    def _add(self, n, strong, kind, flags, where, first, last, after_et, brk) -> None:
        bits = _AFTER_ET if after_et else 0
        if n >= 0:
            bits |= _LIGHT if strong in NOT_CONTENT else _CONTENT if kind != "p" else 0
            if strong in NEGATIONS:
                bits |= _NEG
        else:
            n = -1
        self.lem.append(n)
        self.bits.append(bits)
        self.flags.append(flags)
        self.brk.append(brk)
        self.strong.append(strong)
        self.where.append(where)
        self.first.append(first)
        self.last.append(last)

    def occurrences(self, i: int, n: int) -> list[int]:
        """Every start of tokens ``[i, i + n)``'s sequence in the Tanakh."""
        lem = self.lem
        occ = self.pairs.get(lem[i] << 14 | lem[i + 1], [])
        for k in range(2, n):
            t = lem[i + k]
            occ = [j for j in occ if lem[j + k] == t]
        return occ

    def count(self, key: tuple[int, ...]) -> int:
        """How often the lemma sequence ``key`` occurs in the Tanakh."""
        if len(key) == 1:
            return self.freq[key[0]]
        if key not in self._counts:
            lem = self.lem
            occ = self.pairs.get(key[0] << 14 | key[1], [])
            for k in range(2, len(key)):
                occ = [j for j in occ if lem[j + k] == key[k]]
            self._counts[key] = len(occ)
        return self._counts[key]


_loading = threading.Lock()


def corpus() -> Corpus:
    """The bundled Tanakh: a second or two the first time (the app starts
    on it in the background, see :func:`warm`)."""
    with _loading:
        return _corpus()


@cache
def _corpus() -> Corpus:
    def read(name):
        return json.loads(gzip.decompress((DATA_DIR / name).read_bytes()))
    books = ((book, read(f"{osis}.json.gz")) for book, osis in BOOKS.items()
             if (DATA_DIR / f"{osis}.json.gz").exists())
    return Corpus(read("lemmas.json.gz"), books)


def warm() -> None:
    """Load the corpus in the background, so the first passage's phrases
    don't wait for it."""
    threading.Thread(target=corpus, name="phrases", daemon=True).start()


# --- finding a passage's phrases --------------------------------------------
def _particle(c: Corpus, j: int) -> bool:
    return 0 <= j < len(c.lem) and c.lem[j] >= 0 and not c.bits[j] & _CONTENT


def _edge(c: Corpus, j: int, step: int) -> int:
    """How strong a break the phrase edge at token ``j`` can stand on: the
    break before it (``step`` -1) or after it (+1), or one beyond the
    particles there, whichever is stronger (they can be taken in or left
    out). A book's ends are a sof pasuq."""
    if step < 0:
        best, k = (c.brk[j - 1] if j else _SOF), j - 1
        while _particle(c, k):
            best, k = max(best, c.brk[k - 1] if k else _SOF), k - 1
    else:
        best, k = c.brk[j], j + 1
        while _particle(c, k):
            best, k = max(best, c.brk[k]), k + 1
    return best


def _cut(c: Corpus, i: int, n: int) -> list[tuple[int, int]]:
    """Tokens ``[i, i + n)`` as the ta'amim divide them: a phrase may cross a
    sof pasuq, an etnaḥta or a king only if it starts and ends on breaks
    at most one step weaker than the strongest it crosses (an etnaḥta for
    a sof pasuq, a king for an etnaḥta, a duke for a king). Otherwise a
    part-unit at either end is cut off at that break, and each piece is
    divided the same way."""
    end = i + n - 1
    inside = [k for k in range(i, end) if c.brk[k] >= _KING]
    if not inside:
        return [(i, n)]
    top = max(c.brk[k] for k in inside)
    tops = [k for k in inside if c.brk[k] == top]
    start_ok, end_ok = _edge(c, i, -1) >= top - 1, _edge(c, end, 1) >= top - 1
    if start_ok and end_ok:
        return [(i, n)]
    head, tail, lo, hi = [], [], i, end
    if not start_ok:
        head = _cut(c, i, tops[0] - i + 1)
        lo = tops[0] + 1
    if not end_ok and tops[-1] >= lo:
        tail = _cut(c, tops[-1] + 1, end - tops[-1])
        hi = tops[-1]
    return head + (_cut(c, lo, hi - lo + 1) if lo <= hi else []) + tail


def _trim(c: Corpus, s: int, n: int) -> tuple[int, int]:
    """Particles off both ends (not לֹא, אַל); off the end, כֹּל and a verb
    of saying too."""
    while n and not c.bits[s] & (_CONTENT | _LIGHT | _NEG):
        s, n = s + 1, n - 1
    while n and (not c.bits[s + n - 1] & (_CONTENT | _NEG) or c.strong[s + n - 1] in SPEECH_VERBS):
        n -= 1
    return s, n


def _content_words(c: Corpus, s: int, n: int) -> int:
    return sum(1 for j in range(s, s + n) if c.bits[j] & _CONTENT)


def _pieces(c: Corpus, i: int, n: int) -> list[tuple[int, int]]:
    """Tokens ``[i, i + n)`` cut at the ta'amim and trimmed; a trimmed piece
    is cut again if its new ends no longer stand on its breaks."""
    out, todo = [], _cut(c, i, n)
    while todo:
        s, m = _trim(c, *todo.pop())
        if m < 2:
            continue
        again = _cut(c, s, m)
        if len(again) > 1:
            todo.extend(again)
        else:
            out.append((s, m))
    return out


def _find(c: Corpus, segments: list[tuple[int, int]], content_words: int = DEFAULTS.content_words,
          ) -> dict[tuple, tuple[int, int, list[int]]]:
    """The phrases with an occurrence in the passage's ``segments`` (runs
    of tokens ``[a, b)``) and at least ``content_words`` content words:
    ``{lemmas: (start, length, occurrences)}``."""
    lem = c.lem
    raw = []
    for a, b in segments:
        for i in range(a, b - 1):
            if lem[i] < 0 or lem[i + 1] < 0:
                continue
            occ, n = c.pairs.get(lem[i] << 14 | lem[i + 1], []), 2
            if len(occ) < 2:
                continue  # once in the Tanakh: no phrase
            while True:
                nxt: list[int] = []
                if i + n < b and lem[i + n] >= 0:
                    t = lem[i + n]
                    nxt = [j for j in occ if lem[j + n] == t]
                if len(nxt) < len(occ):  # closed on the right; on the left?
                    left = lem[i - 1] if i > a else -1
                    if left < 0 or any(j == 0 or lem[j - 1] != left for j in occ):
                        raw.append((i, n, occ))
                if len(nxt) < 2:
                    break
                occ, n = nxt, n + 1
    out: dict[tuple, tuple[int, int, list[int]]] = {}
    for i, n, occ in raw:
        for s, m in _pieces(c, i, n):
            if _content_words(c, s, m) < content_words:
                continue
            key = tuple(lem[s:s + m])
            shifted = [j + s - i for j in occ]
            if key not in out or len(out[key][2]) < len(shifted):
                out[key] = (s, m, shifted)
    return out


# --- formulas ---------------------------------------------------------------
def is_title(c: Corpus, s: int, n: int) -> bool:
    """God's names side by side (יהוה צבאות, אל שדי, יהוה אלהיך); after a
    construct form of one without a suffix, a name, a people or fathers
    (אלהי אברהם, אלהי העברים, אלהי אבתיכם); פני / עיני before one (לפני
    יהוה). Nothing else: no particle, no אֵת left out inside."""
    toks = [j for j in range(s, s + n) if not c.bits[j] & _LIGHT]
    if not any(c.strong[j] in GOD_NAMES for j in toks) or any(c.bits[j] & _AFTER_ET for j in toks[1:]):
        return False
    for x, j in enumerate(toks):
        prev = toks[x - 1] if x else None
        nxt = toks[x + 1] if x + 1 < len(toks) else None
        after_god = prev is not None and c.strong[prev] in GOD_NAMES
        if c.strong[j] in GOD_NAMES and (c.strong[j] != TSEVAOT or after_god):
            continue
        named = c.flags[j] & (PROPER | GENTILIC) or c.strong[j] == FATHER
        if named and after_god and c.flags[prev] & CONSTRUCT:
            continue
        before_god = nxt is not None and c.strong[nxt] in GOD_NAMES
        if c.strong[j] in TITLE_BEFORE and c.flags[j] & CONSTRUCT and before_god:
            continue
        return False
    return True


def formula_class(c: Corpus, s: int, n: int) -> str | None:
    """The formula class of tokens ``[s, s + n)``, or None (docs/phrases.md,
    Formulas). A list -- three or more names or peoples -- is no formula.
    A name here is someone's or somewhere's: יהוה is a name in the lexicon,
    but only the classes that allow God's names take it."""
    toks = [j for j in range(s, s + n) if c.bits[j] & _CONTENT]
    named = [j for j in toks if c.flags[j] & (PROPER | GENTILIC) and c.strong[j] not in GOD_NAMES]
    if len(named) >= 3:
        return None
    if is_title(c, s, n):
        return TITLES
    for name, (core, allowed, names, numerals, needs) in CLASSES.items():
        def fits(j, names=names, numerals=numerals):
            return ((names and c.flags[j] & PROPER and c.strong[j] not in GOD_NAMES)
                    or (numerals and c.flags[j] & NUMERAL))
        if core and not any(c.strong[j] in core for j in toks):
            continue
        if needs and not any(fits(j) for j in toks):
            continue
        if all(c.strong[j] in core or c.strong[j] in allowed or fits(j) for j in toks):
            return name
    return None


def _exceptional(total: int, here: int, t: Thresholds = DEFAULTS) -> str | None:
    """Why a title of God, ``total`` times in the Tanakh and ``here`` times
    in the passage, is no formula: it's "rare" in the Tanakh, or "here",
    mostly in the passage; or None."""
    if total <= t.rare_title:
        return "rare"
    if here >= 2 and here >= t.concentrated * total:
        return "here"
    return None


# --- the tests --------------------------------------------------------------
def _chance(k: int, mu: float) -> float:
    """P(X >= k) for X ~ Poisson(mu): how likely ``k`` or more by chance."""
    if mu <= 0:
        return 0.0
    if k <= mu:
        return 1.0  # at least about a half: as good as certain here
    # The tail directly, term by term: exact for the tiny values that matter.
    log_term = -mu + k * math.log(mu) - math.lgamma(k + 1)
    total, i = 0.0, k
    while True:
        term = math.exp(log_term)
        total += term
        if term < total * 1e-12 or i > k + 500:
            return min(total, 1.0)
        i += 1
        log_term += math.log(mu / i)


def _g2(a: int, c1: int, c2: int, n: int) -> float:
    """Log-likelihood of two parts occurring together ``a`` times, ``c1``
    and ``c2`` times in all, in ``n`` words (the 2×2 table)."""
    cells = [(a, c1 * c2 / n), (c1 - a, c1 * (n - c2) / n), (c2 - a, (n - c1) * c2 / n),
             (n - c1 - c2 + a, (n - c1) * (n - c2) / n)]
    return 2 * sum(o * math.log(o / e) for o, e in cells if o > 0 and e > 0)


def _classify(c: Corpus, segments: list[tuple[int, int]], t: Thresholds = DEFAULTS) -> list[dict]:
    """The passage's phrases that are a refrain, an echo, an idiom, or a
    formula that would be one: each as a dict (see :func:`passage`)."""
    end_of: dict[int, int] = {}
    for a, b in segments:
        for j in range(a, b):
            end_of[j] = b
    words = len(end_of)
    here_freq = Counter(c.lem[j] for j in end_of if c.lem[j] >= 0)

    def inside(j, n):
        return end_of.get(j, -1) >= j + n

    rows = []
    idiom_g2 = t.idiom_g2
    for key, (s, n, occ) in _find(c, segments, t.content_words).items():
        here = [j for j in occ if inside(j, n)]
        if not here:
            continue
        elsewhere = [j for j in occ if not inside(j, n)]
        formula = formula_class(c, s, n)
        exceptional = _exceptional(len(occ), len(here), t) if formula == TITLES else None
        if exceptional:
            formula = None
        kinds = []
        chance_here = _chance(len(here), words * math.prod(here_freq[x] / words for x in key))
        if len(here) >= t.refrain_here and chance_here < t.refrain_chance:
            kinds.append("refrain")
        chance = _chance(len(occ), c.n * math.prod(c.freq[x] / c.n for x in key))
        places = sorted({c.where[j] for j in elsewhere}, key=_canonical)
        if 1 <= len(places) <= t.echo_places and chance < t.echo_chance:
            kinds.append("echo")
        chapters = {(c.where[j][0], c.where[j][1].split(":")[0]) for j in occ}
        bound = 0.0
        if len(occ) >= t.idiom_occurrences and len(chapters) >= t.idiom_chapters:
            parts = [(c.count(key[:k]), c.count(key[k:])) for k in range(1, len(key))]
            bound = min(len(occ) / min(left, right) for left, right in parts)
            strong = all(_g2(len(occ), left, right, c.n) >= idiom_g2 for left, right in parts)
            if bound >= t.idiom_bound and strong:
                kinds.append("idiom")
        if kinds:
            rows.append({"key": key, "start": s, "length": n, "occurrences": occ, "here": here,
                         "elsewhere": elsewhere, "places": places, "chapters": len(chapters),
                         "books": len({b for b, _ch in chapters}), "kinds": kinds, "formula": formula,
                         "exceptional": exceptional, "chance_here": chance_here, "chance": chance,
                         "bound": bound})
    return rows


def _canonical(where: tuple[str, str]) -> tuple[int, int, int]:
    book, key = where
    ch, _colon, vs = key.partition(":")
    return list(BOOKS).index(book) if book in BOOKS else 99, int(ch or 0), int(vs or 0)


def _offsets(big: tuple, small: tuple) -> list[int]:
    """Where ``small`` is inside ``big``."""
    return [k for k in range(len(big) - len(small) + 1) if big[k:k + len(small)] == small]


def _fold(rows: list[dict], positions: str, keep: int) -> list[dict]:
    """``rows`` with a phrase folded under a longer one holding it (in its
    ``children``) when fewer than ``keep`` of its ``positions`` lie outside
    the longer ones; the rest, longest first."""
    shown: list[dict] = []
    having: dict[int, list[dict]] = defaultdict(list)  # a lemma -> the shown phrases with it
    for r in sorted(rows, key=lambda r: -r["length"]):
        holders, covered = [], set()
        for o in having[r["key"][0]]:
            offsets = _offsets(o["key"], r["key"])
            if offsets:
                holders.append(o)
                covered.update(k + d for k in o[positions] for d in offsets)
        own = [j for j in r[positions] if j not in covered]
        if holders and len(own) < keep:
            holders[0].setdefault("children", []).append(r)
        else:
            shown.append(r)
            for lemma in set(r["key"]):
                having[lemma].append(r)
    return shown


# --- the passage --------------------------------------------------------------
def _segments(c: Corpus, verse_data: list[dict]) -> list[tuple[int, int]]:
    """The passage's tokens as runs ``[a, b)`` (a pasuq loaded twice counts
    once)."""
    segments: list[list[int]] = []
    seen = set()
    for item in verse_data:
        span = c.verses.get((item["book"], f"{item['ch']}:{item['vs']}"))
        if span is None or span in seen:
            continue
        seen.add(span)
        if segments and segments[-1][1] == span[0]:
            segments[-1][1] = span[1]
        else:
            segments.append(list(span))
    return [(a, b) for a, b in segments if b > a]


def letters(c: Corpus, j: int, n: int) -> list[str]:
    """Tokens ``[j, j + n)`` as OSHB's letters, a word each (for words that
    aren't loaded, so have no pointed text here)."""
    out = []
    for t in range(j, j + n):
        book, key = c.where[t]
        out.extend(w[0] for w in _book(book)[key][c.first[t]:c.last[t] + 1])
    return out


def phrase_key(c: Corpus, j: int, n: int) -> str:
    """Tokens ``[j, j + n)`` as their dictionary words, the same wherever
    and however they're written, and from one build of the data to the
    next: their Strong's numbers ("1254 430"), or for a preposition with a
    suffix, which has none, its letter (לָהֶם, "ל")."""
    return " ".join(c.strong[t] or letters(c, t, 1)[0][:1] for t in range(j, j + n))


def ref(c: Corpus, j: int, n: int) -> str:
    """Where tokens ``[j, j + n)`` are, in the app's spelling: "Yirmeyahu
    4:23", "Shemot 20:2-6"."""
    (book, key), (_b2, end) = c.where[j], c.where[j + n - 1]
    name = _name(book)
    if end == key:
        return f"{name} {key}"
    ch, vs = key.split(":")
    ch2, vs2 = end.split(":")
    return f"{name} {key}–{vs2}" if ch2 == ch else f"{name} {key}–{end}"


def _covered(c: Corpus, j: int, n: int) -> dict[tuple[str, str], set[int]]:
    """The OSHB words (by pasuq) of tokens ``[j, j + n)``, the אֵת between
    them included."""
    out: dict[tuple[str, str], set[int]] = defaultdict(set)
    for t in range(j, j + n):
        out[c.where[t]].update(range(c.first[t], c.last[t] + 1))
        if t + 1 < j + n and c.where[t + 1] == c.where[t]:
            out[c.where[t]].update(range(c.last[t] + 1, c.first[t + 1]))
    return out


class Placer:
    """Where the Tanakh's tokens are in the loaded pesuqim (``verse_data``,
    the app's fetched pesuqim): an occurrence's words, as ``[pasuq, word]``
    (indices into the loaded pesuqim and their words, as
    :func:`ankipasuk.shorashim.passage` has them)."""

    def __init__(self, c: Corpus, verse_data: list[dict]):
        self.c = c
        self.lined = lined_up(verse_data)
        self.words_at: dict[tuple[str, str, int], list[tuple[int, int]]] = defaultdict(list)
        for v, (item, words) in enumerate(zip(verse_data, self.lined)):
            for k, (_t, _s, at) in enumerate(words):
                if at is not None:
                    self.words_at[(item["book"], at[0], at[1])].append((v, k))

    def marks(self, j: int, n: int) -> list[tuple[int, int]]:
        """The loaded words of tokens ``[j, j + n)``: in each pasuq, from
        their first to their last, those between too (a paseq, a word that
        didn't line up), so an underline runs unbroken. None if they aren't
        loaded."""
        found: dict[int, set[int]] = defaultdict(set)
        for (book, key), idx in _covered(self.c, j, n).items():
            for x in idx:
                for v, k in self.words_at.get((book, key, x), ()):
                    found[v].add(k)
        return [(v, k) for v, ks in sorted(found.items()) for k in range(min(ks), max(ks) + 1)]

    def text(self, marks: list[tuple[int, int]]) -> str:
        """The loaded words ``marks`` as they read, with their separators."""
        return "".join(self.lined[v][k][0] + ("" if x == len(marks) - 1 else self.lined[v][k][1] or " ")
                       for x, (v, k) in enumerate(marks))

    @staticmethod
    def spans(occ_marks: list[list[tuple[int, int]]]) -> list[list[int]]:
        """Each occurrence's first and last word, ``[pasuq, word, pasuq,
        word]``, in the text's order; a pasuq loaded twice gives one in
        each."""
        out = set()
        for ms in occ_marks:
            runs: list[list[tuple[int, int]]] = []
            for m in ms:
                if runs and m[0] - runs[-1][-1][0] <= 1:
                    runs[-1].append(m)
                else:
                    runs.append([m])
            out.update((*run[0], *run[-1]) for run in runs)
        return [list(x) for x in sorted(out)]


def passage(verse_data: list[dict], thresholds: Thresholds = DEFAULTS) -> dict:
    """The loaded pesuqim's phrases, for the Text view and Statistics::

        {"phrases": [{"id", "key", "kinds", "formula", "exceptional", "text",
                      "here", "total", "elsewhere", "places", "chapters",
                      "books", "marks", "spans", "verses", "children"}, ...],
         "sections": {"refrain": [id, ...], "echo": [...], "idiom": [...],
                      "formula": [[class, [id, ...]], ...]}}

    ``key`` is its dictionary words (:func:`phrase_key`); ``kinds`` are
    the sections a phrase is in (none for a formula,
    ``formula`` naming its class); ``exceptional``, why a title of God
    isn't one ("rare", "here": :func:`_exceptional`). ``text`` is its first occurrence here, in the loaded
    text; ``marks`` every word of its occurrences here, as ``[pasuq,
    word]`` (indices into the loaded pesuqim and their words, as
    :func:`ankipasuk.shorashim.passage` has them); ``spans`` each
    occurrence's first and last word, ``[pasuq, word, pasuq, word]``, in
    the text's order; ``verses`` the pesuqim it's in. ``places`` are the
    other pesuqim it's in, ``elsewhere`` of them (``{"ref", "at",
    "length"}``, the first 30). ``children`` are
    the phrases folded under it, by section. ``thresholds`` are the
    tests'."""
    c = corpus()
    segments = _segments(c, verse_data)
    if not segments:
        return {"phrases": [], "sections": {"refrain": [], "echo": [], "idiom": [], "formula": []}}
    rows = _classify(c, segments, thresholds)
    place = Placer(c, verse_data)

    entries = []
    for i, r in enumerate(rows):
        r["id"] = i
        occ_marks = [place.marks(j, r["length"]) for j in r["here"]]
        text = place.text(occ_marks[0] if occ_marks else [])
        n = r["length"]
        places, seen = [], set()  # one a pasuq
        for j in sorted(r["elsewhere"], key=lambda j: _canonical(c.where[j])):
            if c.where[j] not in seen:
                seen.add(c.where[j])
                places.append({"ref": ref(c, j, n), "at": j, "length": n})
        entries.append({
            "id": i, "key": phrase_key(c, r["start"], n),
            "kinds": r["kinds"] if not r["formula"] else [], "formula": r["formula"],
            "exceptional": r["exceptional"], "text": text, "here": len(r["here"]),
            "total": len(r["occurrences"]),
            "elsewhere": len(places), "places": places[:30],
            "chapters": r["chapters"], "books": r["books"],
            "marks": sorted({m for ms in occ_marks for m in ms}), "spans": place.spans(occ_marks),
            "verses": sorted({v for ms in occ_marks for v, _k in ms}), "children": {},
        })
    sections: dict = {}
    order = {"refrain": lambda r: (r["chance_here"], -len(r["here"])),
             "echo": lambda r: (r["chance"], -r["length"]),
             "idiom": lambda r: (-r["bound"], -len(r["occurrences"]))}
    keep = {"refrain": ("here", thresholds.refrain_here), "echo": ("elsewhere", 1),
            "idiom": ("occurrences", 2)}
    for kind in ("refrain", "echo", "idiom"):
        mine = [r for r in rows if kind in r["kinds"] and not r["formula"]]
        for r in mine:
            r.pop("children", None)
        shown = sorted(_fold(mine, *keep[kind]), key=order[kind])
        for r in shown:
            kids = sorted(r.get("children", []), key=order[kind])
            if kids:
                entries[r["id"]]["children"][kind] = [k["id"] for k in kids]
        sections[kind] = [r["id"] for r in shown]
    formulas = [r for r in rows if r["formula"]]
    for r in formulas:
        r.pop("children", None)
    shown = _fold(formulas, "here", 1)
    for r in shown:
        if r.get("children"):
            kids = sorted(r["children"], key=lambda r: -len(r["here"]))
            entries[r["id"]]["children"]["formula"] = [k["id"] for k in kids]
    sections["formula"] = [[name, [r["id"] for r in sorted(shown, key=lambda r: (-len(r["here"]), r["start"]))
                                   if r["formula"] == name]] for name in FORMULA_CLASSES]
    sections["formula"] = [s for s in sections["formula"] if s[1]]
    return {"phrases": entries, "sections": sections}


def _name(book: str) -> str:
    return BOOK_HEBREW_NAMES.get(book) or OTHER_BOOK_HEBREW_NAMES.get(book, book)


def _marked(words: list, keep) -> list[list]:
    """``[text, separator, marked]`` for each word, marked from the first
    word ``keep`` takes to the last, those between too."""
    hits = [k for k, w in enumerate(words) if keep(k, w)]
    span = range(min(hits), max(hits) + 1) if hits else range(0)
    return [[w[0], w[1], int(k in span)] for k, w in enumerate(words)]


def here_verses(entry: dict, verse_data: list[dict], words: list[list]) -> list[dict]:
    """The loaded pesuqim a phrase (an entry of :func:`passage`) is in, for
    its viewer: ``[{"ref", "words": [[text, separator, marked]]}]``;
    ``words`` are the loaded pesuqim's words, as :func:`lined_up` or
    :func:`ankipasuk.shorashim.passage` has them."""
    marked = {(v, k) for v, k in entry["marks"]}
    out = []
    for v in entry["verses"]:
        item = verse_data[v]
        out.append({"ref": f"{_name(item['book'])} {item['ch']}:{item['vs']}",
                    "words": [[w[0], w[1], int((v, k) in marked)] for k, w in enumerate(words[v])]})
    return out


def context(at: int, length: int, chapter_of) -> dict:
    """One of a phrase's places (``at``, ``length`` as its ``places`` have
    them) in its chapter, for its viewer::

        {"ref", "title", "ch", "verses": [{"vs", "words": [[text, sep, marked]],
                                           "hit"}]}

    ``hit`` marks the pesuqim the phrase is in, its words ``marked``.
    ``chapter_of(book, ch)`` gives a chapter's pesuqim, pointed."""
    c = corpus()
    covered = _covered(c, at, length)
    book, key = c.where[at]
    ch = int(key.split(":")[0])
    verses = []
    for vs, text in enumerate(chapter_of(book, ch), 1):
        ps = pieces(text)
        idx = covered.get((book, f"{ch}:{vs}"))
        if idx:
            oshb = _book(book).get(f"{ch}:{vs}") or []
            ks = line_up([consonants(t) for t, _s in ps], oshb) if oshb else [None] * len(ps)
            words = _marked(ps, lambda k, _w, ks=ks, idx=idx: ks[k] is not None and ks[k] in idx)
        else:
            words = [[t, s, 0] for t, s in ps]
        verses.append({"vs": vs, "words": words, "hit": bool(idx)})
    return {"ref": ref(c, at, length), "title": f"{_name(book)} {ch}", "ch": ch, "verses": verses}
