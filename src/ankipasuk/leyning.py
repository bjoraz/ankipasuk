"""Computes parasha/aliyah/Maftir/holiday tags for individual verses.

Two data sources feed this, deliberately kept separate:

- The weekly aliyah 1-7 boundaries come **live from Sefaria** (see
  :func:`ankipasuk.sefaria.get_parasha_structure`), the same source the rest
  of the app already uses -- so they're guaranteed to use the exact same
  chapter/verse numbering as the fetched verse text, with zero risk of a
  numbering mismatch between data sources.
- Maftir length (how many verses) and holiday/fast-day reading ranges come
  from a small bundled table (``data/parashot.json``, ``data/holiday_readings.json``),
  derived from the ``@hebcal/leyning`` package -- see ``THIRD_PARTY_NOTICES.md``.
  Maftir is expressed as a **verse count**, not an absolute reference,
  specifically so it's immune to the one well-known chapter-numbering
  discrepancy in the Torah (Genesis 31/32, "Vayetzei" -- Sefaria's Jewish/
  Masoretic numbering has Genesis 31:55 where some other numbering
  conventions have Genesis 32:1, shifting the rest of the chapter by one).
  Combining a *relative* verse count with the *live* aliyah-7 boundary
  sidesteps that entirely.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

from .config import BOOK_HEBREW_NAMES, TORAH_VERSE_COUNTS

_DATA_PACKAGE = "ankipasuk.data"


@lru_cache(maxsize=1)
def _load_json(filename: str):
    with resources.files(_DATA_PACKAGE).joinpath(filename).open("r", encoding="utf-8") as f:
        return json.load(f)


def parasha_table(book: str) -> list[dict]:
    """The bundled per-book parasha table: slug, maftir verse count, etc.,
    in canonical reading order (index 0 = first parasha of the book)."""
    data = _load_json("parashot.json")
    return data.get(book, [])


def holiday_readings() -> list[dict]:
    """The bundled holiday/fast-day reading table (Torah portions only)."""
    return _load_json("holiday_readings.json")


# =============================================================
#  LINEAR VERSE INDEXING (within one book)
# =============================================================
def _chapter_verse_counts(book: str) -> list[int]:
    return TORAH_VERSE_COUNTS[book]


def verse_index(book: str, ch: int, vs: int) -> int:
    """A 0-based index of (ch, vs) within the whole book, counting verses in
    reading order. Used to walk backward/forward across chapter boundaries
    and to test range containment without special-casing chapter edges."""
    counts = _chapter_verse_counts(book)
    return sum(counts[: ch - 1]) + (vs - 1)


def verse_from_index(book: str, idx: int) -> tuple[int, int]:
    """Inverse of :func:`verse_index`."""
    counts = _chapter_verse_counts(book)
    remaining = idx
    for ch, n in enumerate(counts, start=1):
        if remaining < n:
            return ch, remaining + 1
        remaining -= n
    raise ValueError(f"Verse index {idx} out of range for {book}.")


# =============================================================
#  SEFARIA REF-RANGE PARSING
# =============================================================
_REF_RANGE_RE = re.compile(
    r"^(?P<book>.+?)\s+"
    r"(?P<sch>\d+):(?P<svs>\d+)"
    r"(?:-(?:(?P<ech>\d+):)?(?P<evs>\d+))?$"
)


def parse_ref_range(ref: str) -> tuple[str, int, int, int, int]:
    """Parse a Sefaria-style ref string into (book, start_ch, start_vs,
    end_ch, end_vs). Handles all three shapes Sefaria emits:
    ``"Genesis 1:1"`` (single verse), ``"Genesis 1:1-5"`` (same-chapter
    range), and ``"Genesis 1:1-2:3"`` (cross-chapter range)."""
    m = _REF_RANGE_RE.match(ref.strip())
    if not m:
        raise ValueError(f"Could not parse ref range: {ref!r}")

    book = m.group("book")
    sch, svs = int(m.group("sch")), int(m.group("svs"))

    if m.group("evs") is None:
        ech, evs = sch, svs
    elif m.group("ech") is not None:
        ech, evs = int(m.group("ech")), int(m.group("evs"))
    else:
        ech, evs = sch, int(m.group("evs"))

    return book, sch, svs, ech, evs


# =============================================================
#  MAFTIR COMPUTATION
# =============================================================
def compute_maftir_range(book: str, aliyah7_end: tuple[int, int], n_verses: int) -> tuple[int, int, int, int]:
    """Given the live-fetched end of aliyah 7 and the bundled Maftir verse
    count, return (start_ch, start_vs, end_ch, end_vs) for Maftir -- the
    last ``n_verses`` verses of the parasha, correctly walking backward
    across a chapter boundary if needed."""
    ech, evs = aliyah7_end
    end_idx = verse_index(book, ech, evs)
    start_idx = end_idx - (n_verses - 1)
    if start_idx < 0:
        raise ValueError(f"Maftir verse count {n_verses} runs before the start of {book}.")
    sch, svs = verse_from_index(book, start_idx)
    return sch, svs, ech, evs


# =============================================================
#  INTERVAL TABLES
# =============================================================
def build_parasha_intervals(book: str, sefaria_parashot: list[dict]) -> list[tuple[int, int, str]]:
    """Build (start_idx, end_idx, tag) intervals for every aliyah and
    Maftir in ``book``, by pairing Sefaria's live per-parasha aliyah refs
    (``sefaria_parashot``, as returned by
    :func:`ankipasuk.sefaria.get_parasha_structure`, in canonical order)
    with the bundled slug/Maftir-count table, matched by position."""
    hebrew_book = BOOK_HEBREW_NAMES.get(book, book).lower()
    table = parasha_table(book)
    intervals = []

    for i, entry in enumerate(table):
        if i >= len(sefaria_parashot):
            break  # bundled table has more parshiot than Sefaria returned (shouldn't happen)

        refs = sefaria_parashot[i].get("refs", [])
        slug = entry["slug"]
        rel = entry["rel"]
        prefix = f"aliyah::{hebrew_book}::{rel:02d}-{slug}"

        aliyah7_end = None
        for aliyah_num, ref in enumerate(refs, start=1):
            _b, sch, svs, ech, evs = parse_ref_range(ref)
            start_idx = verse_index(book, sch, svs)
            end_idx = verse_index(book, ech, evs)
            intervals.append((start_idx, end_idx, f"{prefix}::{aliyah_num}"))
            if aliyah_num == 7:
                aliyah7_end = (ech, evs)

        if aliyah7_end is not None and entry.get("maftir_verses"):
            msch, msvs, mech, mevs = compute_maftir_range(book, aliyah7_end, entry["maftir_verses"])
            start_idx = verse_index(book, msch, msvs)
            end_idx = verse_index(book, mech, mevs)
            intervals.append((start_idx, end_idx, f"{prefix}::maftir"))

    return intervals


def build_holiday_intervals() -> list[tuple[str, int, int, str]]:
    """Build (book, start_idx, end_idx, tag) intervals for every bundled
    holiday/fast-day reading. Independent of any live data."""
    intervals = []
    for entry in holiday_readings():
        slug = entry["slug"]
        for aliyah in entry["aliyot"]:
            book = aliyah["book"]
            _b, sch, svs, ech, evs = parse_ref_range(f"{book} {aliyah['start']}-{aliyah['end']}")
            intervals.append((
                book, verse_index(book, sch, svs), verse_index(book, ech, evs),
                f"holiday::{slug}::{aliyah['num']}",
            ))
        maftir = entry.get("maftir")
        if maftir:
            book = maftir["book"]
            _b, sch, svs, ech, evs = parse_ref_range(f"{book} {maftir['start']}-{maftir['end']}")
            intervals.append((
                book, verse_index(book, sch, svs), verse_index(book, ech, evs),
                f"holiday::{slug}::maftir",
            ))
    return intervals


def tags_for_verse(
    book: str, ch: int, vs: int,
    parasha_intervals: list[tuple[int, int, str]],
    holiday_intervals: list[tuple[str, int, int, str]],
) -> list[str]:
    """All tags applicable to (book, ch, vs), given precomputed interval
    tables (see :func:`build_parasha_intervals` / :func:`build_holiday_intervals`)."""
    idx = verse_index(book, ch, vs)
    tags = [tag for start, end, tag in parasha_intervals if start <= idx <= end]
    tags += [tag for b, start, end, tag in holiday_intervals if b == book and start <= idx <= end]
    return tags
