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
from .config import POINTED_VERSION, REQUEST_TIMEOUT, SEFARIA_API_BASE, SEFARIA_INDEX_BASE, TORAH_BOOKS
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
    if book not in TORAH_BOOKS:
        raise ValueError("Invalid Torah book.")

    if start_ch < 1 or end_ch < 1 or start_ch > TORAH_BOOKS[book] or end_ch > TORAH_BOOKS[book]:
        raise ValueError("Chapter out of range for selected book.")

    if (end_ch, end_vs) < (start_ch, start_vs):
        raise ValueError("End reference must not come before start reference.")

    verse_data = []

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
        raise RuntimeError(f"Could not load parashah structure for {book}: {e}") from e
    except ValueError as e:
        raise RuntimeError(f"Invalid JSON in parashah structure for {book}.") from e

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
        raise RuntimeError(f"No parashah nodes found for {book}.")

    cache.set_parasha_structure(book, out)
    return out


def get_aliyah_ref(book: str, parasha_name: str, aliyah_num: int, cache: SefariaCache) -> str:
    parashot = get_parasha_structure(book, cache)

    for p in parashot:
        if p["name"] == parasha_name:
            refs = p["refs"]
            if 1 <= aliyah_num <= len(refs):
                return refs[aliyah_num - 1]
            raise ValueError(f"{parasha_name} does not have aliyah {aliyah_num}.")
    raise ValueError(f"Parashah {parasha_name} not found in {book}.")


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
    for ch in range(1, TORAH_BOOKS[book] + 1):
        chapter_text = get_text_for_ref(f"{book} {ch}", version_param, cache)
        lengths.append(len(chapter_text))
    return lengths
