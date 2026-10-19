"""Hebrew text and trope-mark processing.

Everything here is pure logic: no network calls, no GUI. That makes it the
most important part of the codebase to unit test, since it's where the
actual cantillation-parsing rules live.
"""

from __future__ import annotations

import unicodedata

from .config import LEGARMEH_NAME, MAKEF, MUNACH, PASEQ, TROPE_UNICODE


# =============================================================
#  VOWEL / TROPE STRIPPING
# =============================================================
def strip_vowels_and_trope(text: str) -> str:
    """Strip Nikud and Trope from pointed Hebrew text to guarantee matching
    plain text."""
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    stripped = stripped.replace(MAKEF, " ").replace("׃", "").replace("׀", "")
    stripped = " ".join(stripped.split())
    return unicodedata.normalize("NFC", stripped)


# =============================================================
#  TOKENIZATION + PASEQ (MUNACH LEGARMEH)
# =============================================================
def contains_char(token: str, ch: str) -> bool:
    return ch in unicodedata.normalize("NFD", token)


def extract_trope_char(token: str):
    """Return the single trope character that determines this token's
    disjunctive level, preferring a disjunctive mark over any conjunctive
    ones present on the same word."""
    norm = unicodedata.normalize("NFD", token)
    chars = [ch for ch in norm if ch in TROPE_UNICODE]

    if not chars:
        return None

    disjunctives = [ch for ch in chars if 1 <= TROPE_UNICODE[ch][1] <= 4]
    if disjunctives:
        return min(disjunctives, key=lambda ch: TROPE_UNICODE[ch][1])

    return chars[0]


def tokenize_pasuk(pasuk: str):
    """Split a pointed verse into word tokens, each annotated with its
    ta'am's rank/name and whether it could be part of a paseq (shofar
    holekh + pesiq, Unicode's MUNAH + PASEQ)."""
    tokens = []
    for w in pasuk.split():
        ch = extract_trope_char(w)
        lvl = TROPE_UNICODE[ch][1] if ch else 0
        name = TROPE_UNICODE[ch][0] if ch else None
        tokens.append({
            "text": w,
            "level": lvl,
            "trope_name": name,
            "has_munach": contains_char(w, MUNACH),
            "has_paseq": contains_char(w, PASEQ),
            "is_legarmeh": False,
        })
    adjust_for_munach_legarmeh(tokens)
    return tokens


def adjust_for_munach_legarmeh(tokens) -> None:
    """A shofar holekh (Unicode MUNAH) immediately followed by the vertical
    stroke (Unicode PASEQ) is read as Paseq -- Ashkenazi munach legarmeh --
    a mafsiq at the same rank as Gerish (level 4), if and only if the next
    mafsiq, skipping over any number of mesharetim in between, is level 3.
    Otherwise the stroke is only a pause (Ashkenazi pasek) and the word
    stays a mesharet at level 0. See the note above
    :data:`ankipasuk.config.TROPE_UNICODE` for the names, including why the
    plain stroke is labeled "Pesiq".

    The condition deliberately accepts any level-3 mafsiq, not only a
    ravia' (the usual case). This follows Joshua Jacobson's *Chanting the
    Hebrew Bible*: there are rare cases of it before the other level-3
    te'amim. Don't narrow it to ravia' alone.

    The stroke's own token gets the new level and the name
    :data:`ankipasuk.config.LEGARMEH_NAME`. Mutates ``tokens`` in place."""
    n = len(tokens)
    for i in range(n - 1):
        if tokens[i]["has_munach"] and tokens[i + 1]["has_paseq"]:
            j = i + 2
            while j < n and tokens[j]["level"] == 0:
                j += 1
            if j < n and tokens[j]["level"] == 3:
                tokens[i + 1]["level"] = 4
                tokens[i + 1]["trope_name"] = LEGARMEH_NAME
                tokens[i + 1]["is_legarmeh"] = True


# =============================================================
#  GROUPING (minimum disjunctive groups)
# =============================================================
def group_into_units(tokens):
    """Group tokens into disjunctive units: each unit is a run of
    conjunctive words followed by one disjunctive word."""
    units = []
    conj_buf = []

    for tok in tokens:
        lvl = tok["level"]
        if lvl == 0:
            conj_buf.append({"text": tok["text"], "level": 0})
        else:
            subs = list(conj_buf)
            subs.append({"text": tok["text"], "level": lvl})
            units.append({"level": lvl, "subs": subs})
            conj_buf = []

    if conj_buf:
        if units:
            units[-1]["subs"].extend(conj_buf)
        else:
            units.append({"level": 0, "subs": conj_buf})

    for k, u in enumerate(units, 1):
        u["uid"] = k

    return units


def disj_count(units) -> int:
    """The number of *minimum disjunctive groups* in a verse -- the count
    used both for cloze splitting and for the stats window."""
    return sum(1 for u in units if 1 <= u["level"] <= 4)


def format_units(units) -> str:
    out = []
    for i, u in enumerate(units):
        text = " ".join(sub["text"] for sub in u["subs"])
        out.append(f"{i}: L{u['level']} | {text}")
    return "\n".join(out)


# =============================================================
#  SPLITTING
# =============================================================
def choose_split_index(units):
    if not units:
        return None

    candidates = [
        (i, u["level"])
        for i, u in enumerate(units)
        if i < len(units) - 1 and 1 <= u["level"] <= 4
    ]
    if not candidates:
        return None

    min_level = min(lvl for _, lvl in candidates)
    return min(i for i, lvl in candidates if lvl == min_level)


def split_segment(units, max_leaf_disj: int = 2):
    """Recursively split a verse's units into a binary tree of clauses, each
    leaf having at most ``max_leaf_disj`` disjunctive groups."""
    if disj_count(units) <= max_leaf_disj:
        return units

    idx = choose_split_index(units)
    if idx is None:
        return units

    left = split_segment(units[:idx + 1], max_leaf_disj)
    right = split_segment(units[idx + 1:], max_leaf_disj)
    return {"left": left, "right": right}
