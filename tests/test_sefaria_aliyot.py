"""Tests for ankipasuk.sefaria.fetch_aliyot_in_range.

Uses a cache pre-seeded with a fake parasha structure and per-chapter
text (same approach as tests/test_anki_connect/test_tagging.py's
_cache_with_genesis), so these exercise the real range-walking/
chapter-rollover logic with zero network access.
"""

import pytest

from ankipasuk.cache import SefariaCache
from ankipasuk.sefaria import fetch_aliyot_in_range

BOOK = "Genesis"


def _seed(tmp_path, parashot, ref_texts):
    """``parashot``: list of {"name": ..., "refs": [...]}.
    ``ref_texts``: {ref_str: [pointed_verse, ...]} -- fetch_aliyot_in_range
    (like webgui.api.Api.fetch_parashah_aliyah) fetches text keyed by the
    *aliyah's own ref string* (e.g. "Genesis 1:1-1:2"), not per chapter,
    so that's what needs to be pre-seeded here."""
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_parasha_structure(BOOK, parashot)
    for ref, verses in ref_texts.items():
        cache.set_text(ref, "source", verses)
    return cache


def _three_parashot():
    """Bereshit (2 aliyot), Noach (2 aliyot), Lech Lecha (2 aliyot), all
    within chapters 1-3 (3 verses each) for simplicity."""
    return [
        {"name": "Bereshit", "refs": ["Genesis 1:1-1:2", "Genesis 1:3-1:3"]},
        {"name": "Noach", "refs": ["Genesis 2:1-2:2", "Genesis 2:3-2:3"]},
        {"name": "Lech Lecha", "refs": ["Genesis 3:1-3:2", "Genesis 3:3-3:3"]},
    ]


def _chapter_texts():
    return {
        "Genesis 1:1-1:2": ["v1:1", "v1:2"],
        "Genesis 1:3-1:3": ["v1:3"],
        "Genesis 2:1-2:2": ["v2:1", "v2:2"],
        "Genesis 2:3-2:3": ["v2:3"],
        "Genesis 3:1-3:2": ["v3:1", "v3:2"],
        "Genesis 3:3-3:3": ["v3:3"],
    }


def test_single_aliyah_within_one_parasha(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    aliyot = fetch_aliyot_in_range(BOOK, "Bereshit", 1, "Bereshit", 1, cache, "source")

    assert len(aliyot) == 1
    assert aliyot[0]["parasha"] == "Bereshit"
    assert aliyot[0]["aliyah_num"] == 1
    assert [v["pointed"] for v in aliyot[0]["verses"]] == ["v1:1", "v1:2"]
    assert [v["ch"] for v in aliyot[0]["verses"]] == [1, 1]
    assert [v["vs"] for v in aliyot[0]["verses"]] == [1, 2]


def test_range_spans_multiple_parashot_in_order(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    aliyot = fetch_aliyot_in_range(BOOK, "Bereshit", 2, "Noach", 1, cache, "source")

    assert [(a["parasha"], a["aliyah_num"]) for a in aliyot] == [
        ("Bereshit", 2), ("Noach", 1),
    ]
    assert [v["pointed"] for v in aliyot[0]["verses"]] == ["v1:3"]
    assert [v["pointed"] for v in aliyot[1]["verses"]] == ["v2:1", "v2:2"]


def test_full_parashot_in_the_middle_of_the_range_include_all_their_aliyot(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    aliyot = fetch_aliyot_in_range(BOOK, "Bereshit", 1, "Lech Lecha", 2, cache, "source")

    assert [(a["parasha"], a["aliyah_num"]) for a in aliyot] == [
        ("Bereshit", 1), ("Bereshit", 2),
        ("Noach", 1), ("Noach", 2),
        ("Lech Lecha", 1), ("Lech Lecha", 2),
    ]


def test_each_verse_stamps_its_own_book(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    aliyot = fetch_aliyot_in_range(BOOK, "Bereshit", 1, "Bereshit", 1, cache, "source")
    assert all(v["book"] == BOOK for v in aliyot[0]["verses"])


def test_unknown_start_parasha_raises(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    with pytest.raises(ValueError, match="Not A Parasha"):
        fetch_aliyot_in_range(BOOK, "Not A Parasha", 1, "Noach", 1, cache, "source")


def test_end_before_start_raises(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    with pytest.raises(ValueError, match="must not come before"):
        fetch_aliyot_in_range(BOOK, "Noach", 1, "Bereshit", 1, cache, "source")


def test_aliyah_number_out_of_range_raises(tmp_path):
    cache = _seed(tmp_path, _three_parashot(), _chapter_texts())
    with pytest.raises(ValueError, match="does not have 'aliyyot"):
        fetch_aliyot_in_range(BOOK, "Bereshit", 1, "Bereshit", 5, cache, "source")
