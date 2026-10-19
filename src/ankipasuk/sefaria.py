"""Thin wrapper around the Sefaria REST API.

All network calls go through a :class:`~ankipasuk.cache.SefariaCache`
instance passed in by the caller, so a given (ref, version) pair or book's
parashah structure is only ever fetched from the network once, ever.
"""

from __future__ import annotations

import html
import re

import requests

from .cache import SefariaCache
from .config import (
    ALL_BOOKS,
    POINTED_VERSION,
    REQUEST_TIMEOUT,
    SEFARIA_API_BASE,
    SEFARIA_INDEX_BASE,
    TORAH_VERSE_COUNTS,
)
from .text_processing import strip_vowels_and_trope


# =============================================================
#  TEXT CLEANING
# =============================================================
def sanitize_sefaria_verse(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s*\{[^}]*[פס][^}]*\}\s*", " ", text)
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    text = re.sub(r"[\ufeff\u200b\u200c\u200d]", "", text)
    text = " ".join(text.split())
    return text.strip()


def flatten_and_clean_text(raw_text):
    out = []

    def walk(x):
        if isinstance(x, str):
            cleaned = sanitize_sefaria_verse(x)
            if cleaned:
                out.append(cleaned)
        elif isinstance(x, list):
            for item in x:
                walk(item)
        else:
            cleaned = sanitize_sefaria_verse(str(x))
            if cleaned:
                out.append(cleaned)

    walk(raw_text)
    return out


# =============================================================
#  API CALLS
# =============================================================
def get_text_for_ref(ref_str: str, version_param: str, cache: SefariaCache):
    """Return the cleaned verse list for ``ref_str``, using the on-disk
    cache when available and only hitting the network on a miss."""
    cached = cache.get_text(ref_str, version_param)
    if cached is not None:
        return cached

    url = f"{SEFARIA_API_BASE}/{requests.utils.quote(ref_str, safe='')}"
    params = {
        "version": version_param,
        "return_format": "text_only",
    }

    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Network/API error while fetching {ref_str}: {e}") from e
    except ValueError as e:
        raise RuntimeError(f"Invalid JSON returned for {ref_str}.") from e

    versions = data.get("versions", [])
    text = None

    for version in versions:
        candidate = version.get("text")
        if candidate:
            text = candidate
            break

    if text is None:
        raise RuntimeError(f"No text returned for {ref_str} ({version_param}).")

    cleaned = flatten_and_clean_text(text)
    cache.set_text(ref_str, version_param, cleaned)
    return cleaned


def fetch_torah_range(book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int,
                       cache: SefariaCache, version_param: str):
    if book not in TORAH_VERSE_COUNTS:
        raise ValueError("Invalid Torah book.")

    book_chapter_count = len(TORAH_VERSE_COUNTS[book])
    if start_ch < 1 or end_ch < 1 or start_ch > book_chapter_count or end_ch > book_chapter_count:
        raise ValueError("Chapter out of range for selected book.")

    if (end_ch, end_vs) < (start_ch, start_vs):
        raise ValueError("End reference must not come before start reference.")

    verse_data = []

    with cache.defer_saves():
        for ch in range(start_ch, end_ch + 1):
            chapter_pointed = get_text_for_ref(f"{book} {ch}", version_param, cache)
            max_verse = len(chapter_pointed)

            from_v = start_vs if ch == start_ch else 1
            to_v = end_vs if ch == end_ch else max_verse

            if from_v < 1 or to_v < 1 or from_v > max_verse or to_v > max_verse:
                raise ValueError(
                    f"Verse out of range in {book} {ch}. "
                    f"That chapter has {max_verse} verses."
                )

            for vs_idx in range(from_v - 1, to_v):
                pointed = chapter_pointed[vs_idx]
                plain = strip_vowels_and_trope(pointed)
                verse_data.append({
                    "ch": ch,
                    "vs": vs_idx + 1,
                    "pointed": pointed,
                    "plain": plain
                })

    return verse_data


def discover_book_structure(
    book: str, cache: SefariaCache, version_param: str = POINTED_VERSION
) -> list[int]:
    """The number of verses in each chapter of ``book``, discovered live by
    probing Sefaria chapter by chapter until a fetch fails (no such
    chapter) -- for books without a hardcoded per-chapter table (all of
    Nevi'im and the Megillot; Torah uses config.TORAH_VERSE_COUNTS
    instead, no network needed). Cached via
    :meth:`SefariaCache.set_book_structure`, so this probing cost is paid
    at most once per book ever, even across app restarts.
    """
    cached = cache.get_book_structure(book)
    if cached is not None:
        return cached

    lengths = []
    ch = 1
    with cache.defer_saves():
        while True:
            try:
                chapter_text = get_text_for_ref(f"{book} {ch}", version_param, cache)
            except RuntimeError:
                break
            if not chapter_text:
                break
            lengths.append(len(chapter_text))
            ch += 1

    if not lengths:
        raise RuntimeError(f"Could not find any chapters for {book}.")

    cache.set_book_structure(book, lengths)
    return lengths


def get_book_structure(book: str, cache: SefariaCache, version_param: str = POINTED_VERSION) -> list[int]:
    """The number of verses in each chapter of ``book`` -- the static,
    zero-network TORAH_VERSE_COUNTS table for Torah books, or live
    discovery (see discover_book_structure) for anything else."""
    if book in TORAH_VERSE_COUNTS:
        return TORAH_VERSE_COUNTS[book]
    if book not in ALL_BOOKS:
        raise ValueError(f"Unknown book: {book}")
    return discover_book_structure(book, cache, version_param)


def fetch_verse_range(book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int,
                       cache: SefariaCache, version_param: str):
    """Like fetch_torah_range, but works for any book in config.ALL_BOOKS
    (Torah, Nevi'im, or the Megillot) rather than Torah alone, and stamps
    each returned verse with its own "book" field -- needed once ranges
    from different books can be fetched independently and concatenated
    together (see webgui.api.Api.fetch_chapter_verse), since "ch:vs"
    alone stops uniquely identifying a verse the moment more than one
    book is involved."""
    if book not in ALL_BOOKS:
        raise ValueError(f"Unknown book: {book}")

    chapter_lengths = get_book_structure(book, cache, version_param)
    book_chapter_count = len(chapter_lengths)

    if start_ch < 1 or end_ch < 1 or start_ch > book_chapter_count or end_ch > book_chapter_count:
        raise ValueError("Chapter out of range for selected book.")

    if (end_ch, end_vs) < (start_ch, start_vs):
        raise ValueError("End reference must not come before start reference.")

    verse_data = []

    with cache.defer_saves():
        for ch in range(start_ch, end_ch + 1):
            chapter_pointed = get_text_for_ref(f"{book} {ch}", version_param, cache)
            max_verse = len(chapter_pointed)

            from_v = start_vs if ch == start_ch else 1
            to_v = end_vs if ch == end_ch else max_verse

            if from_v < 1 or to_v < 1 or from_v > max_verse or to_v > max_verse:
                raise ValueError(
                    f"Verse out of range in {book} {ch}. "
                    f"That chapter has {max_verse} verses."
                )

            for vs_idx in range(from_v - 1, to_v):
                pointed = chapter_pointed[vs_idx]
                plain = strip_vowels_and_trope(pointed)
                verse_data.append({
                    "book": book,
                    "ch": ch,
                    "vs": vs_idx + 1,
                    "pointed": pointed,
                    "plain": plain
                })

    return verse_data


def parse_start_ref(ref_str: str):
    m = re.search(r"(\d+):(\d+)", ref_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"(\d+)\s*$", ref_str.split("-")[0])
    if m2:
        return int(m2.group(1)), 1
    return 1, 1


def get_parasha_structure(book: str, cache: SefariaCache):
    cached = cache.get_parasha_structure(book)
    if cached is not None:
        return cached

    url = f"{SEFARIA_INDEX_BASE}/{requests.utils.quote(book, safe='')}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not load parasha structure for {book}: {e}") from e
    except ValueError as e:
        raise RuntimeError(f"Invalid JSON in parasha structure for {book}.") from e

    alt_structs = data.get("alt_structs", {})
    parasha_struct = alt_structs.get("Parasha")
    if not parasha_struct:
        raise RuntimeError(f"No Parasha alternate structure found for {book}.")

    nodes = parasha_struct.get("nodes", [])
    out = []

    for node in nodes:
        name = node.get("sharedTitle") or node.get("title")
        refs = node.get("refs", [])
        whole_ref = node.get("wholeRef")

        if name and refs:
            out.append({
                "name": str(name),
                "wholeRef": whole_ref,
                "refs": refs,
            })

    if not out:
        raise RuntimeError(f"No parasha nodes found for {book}.")

    cache.set_parasha_structure(book, out)
    return out


def get_aliyah_ref(book: str, parasha_name: str, aliyah_num: int, cache: SefariaCache) -> str:
    parashot = get_parasha_structure(book, cache)

    for p in parashot:
        if p["name"] == parasha_name:
            refs = p["refs"]
            if 1 <= aliyah_num <= len(refs):
                return refs[aliyah_num - 1]
            raise ValueError(f"{parasha_name} does not have 'aliya {aliyah_num}.")
    raise ValueError(f"Parasha {parasha_name} not found in {book}.")


def fetch_aliyot_in_range(
    book: str,
    start_parasha: str,
    start_aliyah: int,
    end_parasha: str,
    end_aliyah: int,
    cache: SefariaCache,
    version_param: str = POINTED_VERSION,
) -> list[dict]:
    """Return an ordered list of aliyot from (start_parasha, start_aliyah)
    through (end_parasha, end_aliyah) inclusive, each as::

        {"parasha": name, "aliyah_num": n, "ref": ref_str, "verses": [...]}

    where ``verses`` is a list of per-verse dicts shaped exactly like
    :func:`fetch_verse_range`'s (``book``/``ch``/``vs``/``pointed``/``plain``).

    Aliyah boundaries come from the live Sefaria parasha structure (see
    :func:`get_parasha_structure`), so this always agrees with what
    fetching a single aliyah (e.g. ``webgui.api.Api.fetch_parashah_aliyah``)
    would return for any one aliyah inside the range -- there's no separate
    aliyah-boundary data source to drift out of sync with. Maftir is not
    included (Sefaria's Parasha alt_struct only carries aliyot 1-7); pass
    it as its own single-aliyah range if wanted.

    ``start_parasha`` and ``end_parasha`` may be the same parashah (a
    range entirely within one parashah); ``end_parasha`` must not come
    before ``start_parasha`` in the book's reading order.
    """
    parashot = get_parasha_structure(book, cache)
    names = [p["name"] for p in parashot]

    if start_parasha not in names:
        raise ValueError(f"Parasha {start_parasha!r} not found in {book}.")
    if end_parasha not in names:
        raise ValueError(f"Parasha {end_parasha!r} not found in {book}.")

    start_idx = names.index(start_parasha)
    end_idx = names.index(end_parasha)
    if end_idx < start_idx:
        raise ValueError("End parasha must not come before start parasha.")

    chapter_lengths = get_book_structure(book, cache, version_param)
    aliyot: list[dict] = []

    with cache.defer_saves():
        for p_idx in range(start_idx, end_idx + 1):
            parasha = parashot[p_idx]
            refs = parasha["refs"]
            first_num = start_aliyah if p_idx == start_idx else 1
            last_num = end_aliyah if p_idx == end_idx else len(refs)

            if first_num < 1 or last_num > len(refs) or first_num > last_num:
                raise ValueError(
                    f"{parasha['name']} does not have 'aliyot {first_num}-{last_num} "
                    f"(it has {len(refs)})."
                )

            for aliyah_num in range(first_num, last_num + 1):
                ref_str = refs[aliyah_num - 1]
                pointed_verses = get_text_for_ref(ref_str, version_param, cache)
                start_ch, start_vs = parse_start_ref(ref_str)

                verses = []
                ch, vs = start_ch, start_vs
                for pointed in pointed_verses:
                    plain = strip_vowels_and_trope(pointed)
                    verses.append({
                        "book": book, "ch": ch, "vs": vs,
                        "pointed": pointed, "plain": plain,
                    })
                    vs += 1
                    if ch <= len(chapter_lengths) and vs > chapter_lengths[ch - 1]:
                        vs = 1
                        ch += 1

                aliyot.append({
                    "parasha": parasha["name"],
                    "aliyah_num": aliyah_num,
                    "ref": ref_str,
                    "verses": verses,
                })

    return aliyot


def get_chapter_lengths(book: str, cache: SefariaCache, version_param: str = POINTED_VERSION) -> list[int]:
    """The number of verses in each chapter of ``book``, derived from
    Sefaria's actual current text (the same source used for cloze
    generation) rather than a static, hand-maintained table.

    ``config.TORAH_VERSE_COUNTS`` is a hardcoded snapshot that can drift
    out of sync with what Sefaria's API actually returns -- this has
    happened in practice at contested chapter boundaries (e.g. Genesis
    31/32, where different textual traditions place the boundary a verse
    apart). Since :mod:`ankipasuk.leyning`'s Maftir computation walks
    backward from a live-fetched aliyah-7 endpoint using per-chapter verse
    counts, a stale count anywhere silently shifts every subsequent
    chapter's indexing. Deriving the counts live -- cached afterward, same
    as everything else -- eliminates that entire class of bug rather than
    just correcting one hardcoded number.
    """
    lengths = []
    with cache.defer_saves():
        for ch in range(1, len(TORAH_VERSE_COUNTS[book]) + 1):
            chapter_text = get_text_for_ref(f"{book} {ch}", version_param, cache)
            lengths.append(len(chapter_text))
    return lengths
