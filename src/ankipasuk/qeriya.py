"""Computes parasha/'aliyya/maftir/holiday tags for individual verses.

Two data sources feed this, deliberately kept separate:

- The weekly 'aliyya 1-7 boundaries come **live from Sefaria** (see
  :func:`ankipasuk.sefaria.get_parasha_structure`), the same source the rest
  of the app already uses -- so they're guaranteed to use the exact same
  chapter/verse numbering as the fetched verse text, with zero risk of a
  numbering mismatch between data sources.
- The maftir's length (how many verses) and holiday/fast-day reading ranges come
  from a small bundled table (``data/parashot.json``, ``data/holiday_readings.json``),
  derived from the ``@hebcal/leyning`` package -- see ``THIRD_PARTY_NOTICES.md``.
  The maftir is expressed as a **verse count**, not an absolute reference,
  specifically so it's immune to the one well-known chapter-numbering
  discrepancy in the Tora (Genesis 31/32, Vayyetse -- different textual
  traditions place the chapter break a verse apart).

That immunity only holds if the per-chapter verse *counts* used to walk
that verse count backward are themselves correct for the current text --
which is why every function here takes an optional ``chapter_counts``
(or ``chapter_counts_by_book``) override. Passed a live-fetched value (see
:func:`ankipasuk.sefaria.get_chapter_lengths`), it's used instead of the
static ``config.TORAH_VERSE_COUNTS`` snapshot, which can otherwise drift
out of sync with what Sefaria's API currently returns for a given chapter
and silently shift every subsequent chapter's indexing. This module itself
still does no I/O -- the caller (:mod:`ankipasuk.anki_connect.tagging`)
fetches the live data and passes it in as plain data.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

from .config import BOOK_HEBREW_NAMES, LEGACY_BOOK_HEBREW_NAMES, TORAH_VERSE_COUNTS

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
    """The bundled holiday/fast-day reading table (Tora readings only)."""
    return _load_json("holiday_readings.json")


# =============================================================
#  NAMES AND TAGS (see docs/transliteration.md)
# =============================================================
ALIYYA_TAG_NAMESPACE = "aliyya::"
HOLIDAY_TAG_NAMESPACE = "holiday::"
# What the weekly-reading tags were called before docs/transliteration.md;
# anki_connect.tagging.migrate_legacy_tags renames them.
LEGACY_ALIYAH_TAG_NAMESPACE = "aliyah::"

# Tags the tiqqun-card export puts on its notes (see webgui.api).
TIQQUN_ALIYYA_TAG = "ankipasuk-aliyya"
LEGACY_TIQQUN_ALIYAH_TAG = "ankipasuk-aliyah"


def tiqqun_parasha_tag(slug: str) -> str:
    return f"parasha::{slug}"


def tiqqun_ammud_tag(ammud_num: int) -> str:
    return f"ammud::{ammud_num:03d}"


def to_slug(name: str) -> str:
    """The ASCII form of a transliterated name, used in tags: lowercase, ḥ
    as h, apostrophes dropped, spaces as ``_`` (``"Ḥayye Sara"`` ->
    ``"hayye_sara"``)."""
    return name.lower().replace("ḥ", "h").replace("'", "").replace(" ", "_")


def parasha_names(book: str, sefaria_parashot: list[dict]) -> dict[str, dict]:
    """Map each of Sefaria's parasha names for ``book`` to its entry in the
    bundled table (with our ``name`` and ``slug``), pairing the two lists by
    position -- the same pairing :func:`build_parasha_intervals` relies on.
    Returns ``{}`` if the lists differ in length, so callers fall back to
    Sefaria's own names rather than risk pairing the wrong parasha."""
    table = parasha_table(book)
    if len(table) != len(sefaria_parashot):
        return {}
    return {p["name"]: entry for p, entry in zip(sefaria_parashot, table)}


def legacy_tag_renames(
    sefaria_parasha_names: dict[str, list[str]] | None = None, *, total_ammudim: int = 245,
) -> dict[str, str]:
    """Every tag AnkiPasuk used to generate, mapped to what it generates
    now, keyed by the old tag in lowercase (Anki compares tags without
    regard to case). Covers the weekly-reading and holiday tags, and the
    tiqqun-card tags.

    The old tiqqun-card ``parasha::`` tags were made from Sefaria's
    parasha names, so mapping them needs those names:
    ``sefaria_parasha_names`` is ``{book: [name, ...]}`` in Sefaria's
    order, e.g. from :func:`ankipasuk.sefaria.get_parasha_structure`.
    Without it, those tags are left out of the map."""
    renames: dict[str, str] = {}

    for book in TORAH_VERSE_COUNTS:
        old_book = to_slug(LEGACY_BOOK_HEBREW_NAMES.get(book, BOOK_HEBREW_NAMES[book]))
        new_book = to_slug(BOOK_HEBREW_NAMES[book])
        for entry in parasha_table(book):
            old = f"{LEGACY_ALIYAH_TAG_NAMESPACE}{old_book}::{entry['rel']:02d}-{entry['legacy_slug']}"
            new = f"{ALIYYA_TAG_NAMESPACE}{new_book}::{entry['rel']:02d}-{entry['slug']}"
            # Mirrors build_parasha_intervals: a maftir tag only where the
            # table has a maftir (Vezot haBerakha has none).
            suffixes = [str(n) for n in range(1, entry["n_aliyot"] + 1)]
            if entry.get("maftir_verses"):
                suffixes.append("maftir")
            for suffix in suffixes:
                renames[f"{old}::{suffix}"] = f"{new}::{suffix}"

    for entry in holiday_readings():
        suffixes = [a["num"] for a in entry["aliyot"]] + (["maftir"] if entry.get("maftir") else [])
        for suffix in suffixes:
            new = f"{HOLIDAY_TAG_NAMESPACE}{entry['slug']}::{suffix}"
            renames[f"{HOLIDAY_TAG_NAMESPACE}{entry['legacy_slug']}::{suffix}"] = new
            # Holiday tags applied by hand before the tagger existed sat
            # under the 'aliyah' namespace, with the same old slugs.
            renames[f"{LEGACY_ALIYAH_TAG_NAMESPACE}holiday::{entry['legacy_slug']}::{suffix}"] = new

    renames[LEGACY_TIQQUN_ALIYAH_TAG] = TIQQUN_ALIYYA_TAG
    for n in range(1, total_ammudim + 1):
        renames[f"amud::{n:03d}"] = tiqqun_ammud_tag(n)
    for book, names in (sefaria_parasha_names or {}).items():
        mapping = parasha_names(book, [{"name": name} for name in names])
        for sefaria_name, entry in mapping.items():
            renames[tiqqun_parasha_tag(sefaria_name.replace(" ", "-"))] = tiqqun_parasha_tag(entry["slug"])

    return {old.lower(): new for old, new in renames.items() if old.lower() != new.lower()}


# =============================================================
#  LINEAR VERSE INDEXING (within one book)
# =============================================================
def _chapter_verse_counts(book: str, chapter_counts: list[int] | None) -> list[int]:
    """``chapter_counts`` wins if given (e.g. live-fetched data); otherwise
    falls back to the static ``config.TORAH_VERSE_COUNTS`` snapshot."""
    return chapter_counts if chapter_counts is not None else TORAH_VERSE_COUNTS[book]


def verse_index(book: str, ch: int, vs: int, chapter_counts: list[int] | None = None) -> int:
    """A 0-based index of (ch, vs) within the whole book, counting verses in
    reading order. Used to walk backward/forward across chapter boundaries
    and to test range containment without special-casing chapter edges."""
    counts = _chapter_verse_counts(book, chapter_counts)
    return sum(counts[: ch - 1]) + (vs - 1)


def verse_from_index(book: str, idx: int, chapter_counts: list[int] | None = None) -> tuple[int, int]:
    """Inverse of :func:`verse_index`."""
    counts = _chapter_verse_counts(book, chapter_counts)
    remaining = idx
    for ch, n in enumerate(counts, start=1):
        if remaining < n:
            return ch, remaining + 1
        remaining -= n
    raise ValueError(f"Verse index {idx} out of range for {book}.")


# =============================================================
#  SEFARIA REF-RANGE PARSING
# =============================================================
# Sefaria's API doesn't consistently use a plain ASCII hyphen for ranges --
# an en-dash has been observed in the wild (e.g. "Deuteronomy 33:1-7" is
# sometimes rendered with U+2013 instead of U+002D). Accept the common
# dash/hyphen variants so a data-formatting quirk on Sefaria's end doesn't
# break tagging.
_DASH_CHARS = "\u002D\u2010\u2011\u2012\u2013\u2014\u2212"  # -‐‑‒–—−

_REF_RANGE_RE = re.compile(
    r"^(?P<book>.+?)\s+"
    r"(?P<sch>\d+):(?P<svs>\d+)"
    rf"(?:[{_DASH_CHARS}](?:(?P<ech>\d+):)?(?P<evs>\d+))?$"
)


def parse_ref_range(ref: str) -> tuple[str, int, int, int, int]:
    """Parse a Sefaria-style ref string into (book, start_ch, start_vs,
    end_ch, end_vs). Handles all three shapes Sefaria emits:
    ``"Genesis 1:1"`` (single verse), ``"Genesis 1:1-5"`` (same-chapter
    range), and ``"Genesis 1:1-2:3"`` (cross-chapter range) -- with any of
    the dash variants in ``_DASH_CHARS`` as the range separator."""
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
def compute_maftir_range(
    book: str, aliyah7_end: tuple[int, int], n_verses: int, chapter_counts: list[int] | None = None
) -> tuple[int, int, int, int]:
    """Given the live-fetched end of 'aliyya 7 and the bundled maftir verse
    count, return (start_ch, start_vs, end_ch, end_vs) for the maftir -- the
    last ``n_verses`` verses of the parasha, correctly walking backward
    across a chapter boundary if needed."""
    ech, evs = aliyah7_end
    end_idx = verse_index(book, ech, evs, chapter_counts)
    start_idx = end_idx - (n_verses - 1)
    if start_idx < 0:
        raise ValueError(f"Maftir verse count {n_verses} runs before the start of {book}.")
    sch, svs = verse_from_index(book, start_idx, chapter_counts)
    return sch, svs, ech, evs


# =============================================================
#  INTERVAL TABLES
# =============================================================
def build_parasha_intervals(
    book: str, sefaria_parashot: list[dict], chapter_counts: list[int] | None = None
) -> list[tuple[int, int, str]]:
    """Build (start_idx, end_idx, tag) intervals for every 'aliyya and
    the maftir in ``book``, by pairing Sefaria's live per-parasha 'aliyya refs
    (``sefaria_parashot``, as returned by
    :func:`ankipasuk.sefaria.get_parasha_structure`, in canonical order)
    with the bundled slug/maftir-count table, matched by position. Pass a
    live-fetched ``chapter_counts`` (see
    :func:`ankipasuk.sefaria.get_chapter_lengths`) to avoid relying on the
    static verse-count table for the maftir backward-walk."""
    book_slug = to_slug(BOOK_HEBREW_NAMES.get(book, book))
    table = parasha_table(book)
    intervals = []

    for i, entry in enumerate(table):
        if i >= len(sefaria_parashot):
            break  # bundled table has more parashiyyot than Sefaria returned (shouldn't happen)

        refs = sefaria_parashot[i].get("refs", [])
        slug = entry["slug"]
        rel = entry["rel"]
        prefix = f"{ALIYYA_TAG_NAMESPACE}{book_slug}::{rel:02d}-{slug}"

        aliyah7_end = None
        for aliyah_num, ref in enumerate(refs, start=1):
            _b, sch, svs, ech, evs = parse_ref_range(ref)
            start_idx = verse_index(book, sch, svs, chapter_counts)
            end_idx = verse_index(book, ech, evs, chapter_counts)
            intervals.append((start_idx, end_idx, f"{prefix}::{aliyah_num}"))
            if aliyah_num == 7:
                aliyah7_end = (ech, evs)

        if aliyah7_end is not None and entry.get("maftir_verses"):
            msch, msvs, mech, mevs = compute_maftir_range(
                book, aliyah7_end, entry["maftir_verses"], chapter_counts
            )
            start_idx = verse_index(book, msch, msvs, chapter_counts)
            end_idx = verse_index(book, mech, mevs, chapter_counts)
            intervals.append((start_idx, end_idx, f"{prefix}::maftir"))

    return intervals


def build_holiday_intervals(
    chapter_counts_by_book: dict[str, list[int]] | None = None,
) -> list[tuple[str, int, int, str]]:
    """Build (book, start_idx, end_idx, tag) intervals for every bundled
    holiday/fast-day reading. Doesn't depend on live parasha data, but does
    accept live-fetched per-book chapter counts (see
    :func:`ankipasuk.sefaria.get_chapter_lengths`) for the same reason
    :func:`build_parasha_intervals` does; any book not present in
    ``chapter_counts_by_book`` falls back to the static table."""
    chapter_counts_by_book = chapter_counts_by_book or {}
    intervals = []
    for entry in holiday_readings():
        slug = entry["slug"]
        for aliyah in entry["aliyot"]:
            book = aliyah["book"]
            counts = chapter_counts_by_book.get(book)
            _b, sch, svs, ech, evs = parse_ref_range(f"{book} {aliyah['start']}-{aliyah['end']}")
            intervals.append((
                book, verse_index(book, sch, svs, counts), verse_index(book, ech, evs, counts),
                f"{HOLIDAY_TAG_NAMESPACE}{slug}::{aliyah['num']}",
            ))
        maftir = entry.get("maftir")
        if maftir:
            book = maftir["book"]
            counts = chapter_counts_by_book.get(book)
            _b, sch, svs, ech, evs = parse_ref_range(f"{book} {maftir['start']}-{maftir['end']}")
            intervals.append((
                book, verse_index(book, sch, svs, counts), verse_index(book, ech, evs, counts),
                f"{HOLIDAY_TAG_NAMESPACE}{slug}::maftir",
            ))
    return intervals


def tags_for_verse(
    book: str, ch: int, vs: int,
    parasha_intervals: list[tuple[int, int, str]],
    holiday_intervals: list[tuple[str, int, int, str]],
    chapter_counts: list[int] | None = None,
) -> list[str]:
    """All tags applicable to (book, ch, vs), given precomputed interval
    tables (see :func:`build_parasha_intervals` / :func:`build_holiday_intervals`).
    ``chapter_counts`` should be the same live-fetched data (if any) used to
    build those interval tables, so the index computed here lines up with
    theirs exactly."""
    idx = verse_index(book, ch, vs, chapter_counts)
    tags = [tag for start, end, tag in parasha_intervals if start <= idx <= end]
    tags += [tag for b, start, end, tag in holiday_intervals if b == book and start <= idx <= end]
    return tags
