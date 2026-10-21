"""Pointed Hebrew in the app's spelling (docs/transliteration.md): the
Sephardi rules the app writes every book, parasha and holiday name by,
applied to any pointed word -- used for the names in the shorashim data.

In short:

- consonants: בּ/ב b/v, כּ/כ k/kh, פּ/פ p/f, ח ḥ, צ ts, ק q, שׁ sh, שׂ s,
  ט ת t; ע is always ', א is ' only where it starts a syllable inside a
  word, and a silent final ה isn't written;
- vowels: qamats and pataḥ a, qamats qatan o, tsere and segol e, ḥiriq i,
  ḥolam o, shuruq and qubbuts u (ḥataf: a, e, o); pataḥ before a yod is
  ai, tsere or ḥiriq before one is just e or i;
- a sheva na is e, a sheva naḥ nothing: na at the start of a word, as the
  second of two, under a doubled letter, or after a long vowel;
- a dagesh ḥazaq doubles the letter, except sh and ts, and except after
  the article, which is written "ha" and joined to the capitalized word
  that follows;
- names are capitalized, each word of them.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

SHEVA, HATAF_SEGOL, HATAF_PATAH, HATAF_QAMATS = "ְ", "ֱ", "ֲ", "ֳ"
HIRIQ, TSERE, SEGOL, PATAH, QAMATS = "ִ", "ֵ", "ֶ", "ַ", "ָ"
HOLAM, HOLAM_HASER_VAV, QUBBUTS, DAGESH = "ֹ", "ֺ", "ֻ", "ּ"
SHIN_DOT, SIN_DOT, QAMATS_QATAN = "ׁ", "ׂ", "ׇ"
MAQAF = "־"

VOWELS = {
    QAMATS: "a", PATAH: "a", QAMATS_QATAN: "o", TSERE: "e", SEGOL: "e", HIRIQ: "i",
    HOLAM: "o", HOLAM_HASER_VAV: "o", QUBBUTS: "u", HATAF_PATAH: "a", HATAF_SEGOL: "e", HATAF_QAMATS: "o",
}
LONG = {QAMATS, TSERE, HOLAM, HOLAM_HASER_VAV}  # with ḥiriq male and shuruq, which are vowel letters
CONSONANTS = {
    "א": "", "ב": "v", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ḥ", "ט": "t", "י": "y",
    "כ": "kh", "ך": "kh", "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "'",
    "פ": "f", "ף": "f", "צ": "ts", "ץ": "ts", "ק": "q", "ר": "r", "ש": "sh", "ת": "t",
}
HARD = {"ב": "b", "כ": "k", "ך": "k", "פ": "p", "ף": "p"}
NOT_DOUBLED = {"sh", "ts", "kh", "ḥ", "'", ""}


@dataclass
class _Letter:
    letter: str
    marks: set[str] = field(default_factory=set)
    vowel: str = ""      # what's written for its vowel
    long: bool = False   # its vowel is long (for a following sheva)
    mater: bool = False  # a vowel letter (ḥolam male, shuruq, ḥiriq male...), not written itself
    initial_u: bool = False  # a word starting with shuruq (וּ)

    @property
    def dagesh(self) -> bool:
        return DAGESH in self.marks

    def has(self, *marks: str) -> bool:
        return any(m in self.marks for m in marks)

    @property
    def pointed(self) -> bool:
        """Has a vowel (or sheva) of its own."""
        return bool(self.marks & (set(VOWELS) | {SHEVA}))


def _letters(word: str) -> list[_Letter]:
    out: list[_Letter] = []
    for ch in unicodedata.normalize("NFD", word):
        if "א" <= ch <= "ת":
            out.append(_Letter(ch))
        elif out and ("ְ" <= ch <= "ׇ"):
            out[-1].marks.add(ch)
        # ta'amim, meteg, CGJ and the like are left out
    return out


def _word(word: str) -> str:
    ls = _letters(word)
    if not ls:
        return ""
    # Vowel letters first: ḥolam male, shuruq, and a yod or vav after a
    # vowel, which give the letter before them their vowel.
    for i, c in enumerate(ls):
        prev = ls[i - 1] if i else None
        if c.letter == "ו" and c.has(HOLAM, HOLAM_HASER_VAV) and not (c.marks - {HOLAM, HOLAM_HASER_VAV}) \
                and prev is not None and not prev.pointed:
            prev.vowel, prev.long, c.mater = "o", True, True  # ḥolam male
            continue
        if c.letter == "ו" and c.marks == {DAGESH} and (prev is None or not prev.pointed):
            if prev is None:
                c.vowel, c.long, c.initial_u = "u", True, True  # a word starting with shuruq
            else:
                prev.vowel, prev.long, c.mater = "u", True, True
            continue
    for c in ls:
        if c.mater or c.initial_u:
            continue
        for v, written in VOWELS.items():
            if v in c.marks and not c.vowel:
                c.vowel, c.long = written, v in LONG
        if PATAH in c.marks and HIRIQ in c.marks:
            c.vowel = "ayi"  # יְרוּשָׁלִַם
    for i, c in enumerate(ls):
        prev = ls[i - 1] if i else None
        if c.letter == "י" and not c.pointed and not c.dagesh and prev is not None and prev.vowel \
                and not c.mater:
            nxt = ls[i + 1] if i + 1 < len(ls) else None
            if prev.has(HIRIQ) and not prev.has(PATAH):
                prev.long, c.mater = True, True  # ḥiriq male
            elif prev.has(TSERE, SEGOL):
                c.mater = True
            elif prev.has(PATAH, QAMATS) and (nxt is None or nxt.letter != "ו"):
                prev.vowel, c.mater = prev.vowel + "i", True  # Ḥaggai, Sinai
    # Then the consonants.
    out = []
    article = len(ls) > 2 and ls[0].letter == "ה" and ls[0].has(PATAH, QAMATS) and ls[1].dagesh \
        and ls[1].letter not in "אהחער"
    for i, c in enumerate(ls):
        # The letter before, skipping vowel letters: what carries the vowel
        # (יְהוֹשׁוּעַ: the shin's u, before the ayin's furtive pataḥ).
        prev = next((ls[j] for j in range(i - 1, -1, -1) if not ls[j].mater), None)
        last = i == len(ls) - 1
        if c.mater:
            continue
        if c.initial_u:
            out.append("u")
            continue
        sound = CONSONANTS[c.letter]
        if c.letter == "ש":
            sound = "s" if c.has(SIN_DOT) else "sh" if c.has(SHIN_DOT) or c.pointed else ""
        if c.dagesh and c.letter in HARD:
            sound = HARD[c.letter]
        if c.letter == "ה" and last and not c.dagesh and not c.pointed:
            sound = ""  # a silent final he
        if c.letter == "א":
            sound = "'" if i and (c.vowel or c.has(SHEVA)) and not (article and i == 1) else ""
        if c.letter == "ו" and last and not c.pointed and prev is not None and prev.vowel:
            sound = "v"  # עֵשָׂו
        doubled = (c.dagesh and i > 0 and c.letter not in "הו" and prev is not None and prev.vowel != ""
                   and not (article and i == 1) and sound not in NOT_DOUBLED)
        if c.letter == "ו" and c.dagesh and c.pointed and i:
            doubled = True  # חַוָּה
        # Sheva: na or naḥ.
        vowel = c.vowel
        if c.has(SHEVA) and not vowel:
            second = prev is not None and prev.has(SHEVA) and not prev.vowel
            # (After the article, the dagesh isn't written but still doubles:
            # הַמְּדָתָא, haMedata.)
            na = i == 0 or doubled or (article and i == 1) or (second and not last) \
                or (prev is not None and prev.long and not last) \
                or (i + 1 < len(ls) and ls[i + 1].letter == c.letter)
            vowel = "e" if na and not last else ""
        furtive = last and c.letter in "חעה" and c.has(PATAH) and prev is not None and prev.vowel != ""
        if furtive:
            out.append("a" + sound)
        else:
            out.append((sound * 2 if doubled else sound) + vowel)
        if article and i == 0:
            out.append("|")  # the article, joined to a capitalized word
    text = "".join(out)
    if article:
        head, _bar, rest = text.partition("|")
        return head + _capitalize(rest)
    return text


def _capitalize(word: str) -> str:
    for i, ch in enumerate(word):
        if ch.isalpha():
            return word[:i] + ch.upper() + word[i + 1:]
    return word


def transliterate(pointed: str, *, name: bool = True) -> str:
    """``pointed`` in the app's spelling; a name capitalized, each of its
    words (words split at spaces and maqaf)."""
    words = [w for w in pointed.replace(MAQAF, " ").split() if w]
    out = [_word(w) for w in words]
    if name:
        out = [w if w.startswith("ha") and any(ch.isupper() for ch in w) else _capitalize(w) for w in out]
    return " ".join(w for w in out if w)
