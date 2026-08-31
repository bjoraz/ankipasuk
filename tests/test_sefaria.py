"""Tests for the new (non-Torah) book-structure discovery and fetch
functions in sefaria.py -- discover_book_structure, get_book_structure,
and fetch_verse_range.

fetch_torah_range and get_chapter_lengths (the pre-existing, Torah-only
functions) are deliberately left untouched by the Nevi'im/Megillot work,
so they aren't retested here.
"""

import pytest

import ankipasuk.sefaria as sefaria_module
from ankipasuk.cache import SefariaCache


class FakeBook:
    """A fake Sefaria backend for one book: chapter_lengths[i] is the
    verse count of chapter i+1. Any chapter beyond the end of the list
    raises requests.HTTPError, simulating Sefaria's real behavior for a
    ref naming a chapter that doesn't exist."""

    def __init__(self, chapter_lengths):
        self.chapter_lengths = chapter_lengths
        self.call_count = 0

    def fake_get(self, url, params=None, timeout=None):
        self.call_count += 1
        # ref is the last two path segments URL-quoted together, e.g.
        # ".../texts/Isaiah%201" -- pull the chapter number back out.
        import re

        m = re.search(r"%20(\d+)$|[ /](\d+)$", url)
        ch = int(next(g for g in m.groups() if g)) if m else None

        class FakeResponse:
            def __init__(self, chapter_lengths=self.chapter_lengths, ch=ch):
                self._chapter_lengths = chapter_lengths
                self._ch = ch

            def raise_for_status(self):
                if self._ch is None or self._ch > len(self._chapter_lengths) or self._ch < 1:
                    import requests

                    raise requests.HTTPError("404")

            def json(self):
                n = self._chapter_lengths[self._ch - 1]
                return {"versions": [{"text": [f"verse {i + 1}" for i in range(n)]}]}

        return FakeResponse()


@pytest.fixture
def fake_isaiah(monkeypatch):
    """A fake 3-chapter "Isaiah" with lengths [26, 22, 26] -- small
    enough to probe quickly in tests, standing in for the real (66
    chapter) book."""
    book = FakeBook([26, 22, 26])
    monkeypatch.setattr(sefaria_module.requests, "get", book.fake_get)
    return book


def test_discover_book_structure_probes_until_failure(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.discover_book_structure("Isaiah", cache)
    assert lengths == [26, 22, 26]


def test_discover_book_structure_is_cached_after_first_call(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    sefaria_module.discover_book_structure("Isaiah", cache)
    calls_after_first = fake_isaiah.call_count

    # A second call (even chapter 4, the one-past-the-end probe) should
    # not hit the network again -- it's served entirely from cache.
    lengths = sefaria_module.discover_book_structure("Isaiah", cache)
    assert lengths == [26, 22, 26]
    assert fake_isaiah.call_count == calls_after_first


def test_discover_book_structure_persists_across_cache_instances(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    sefaria_module.discover_book_structure("Isaiah", cache)
    calls_after_first = fake_isaiah.call_count

    fresh_cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.discover_book_structure("Isaiah", fresh_cache)
    assert lengths == [26, 22, 26]
    assert fake_isaiah.call_count == calls_after_first  # no new network calls


def test_get_book_structure_uses_static_table_for_torah(tmp_path):
    """Torah books must never hit the network -- config.TORAH_VERSE_COUNTS
    is authoritative and free."""
    cache = SefariaCache(cache_dir=tmp_path)

    def fail_if_called(*a, **kw):
        raise AssertionError("should not make a network call for a Torah book")

    import ankipasuk.sefaria as sm
    original = sm.requests.get
    sm.requests.get = fail_if_called
    try:
        lengths = sefaria_module.get_book_structure("Genesis", cache)
    finally:
        sm.requests.get = original
    assert lengths[0] == 31  # Genesis 1 has 31 verses


def test_get_book_structure_discovers_live_for_non_torah(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.get_book_structure("Isaiah", cache)
    assert lengths == [26, 22, 26]


def test_get_book_structure_rejects_unknown_book(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError):
        sefaria_module.get_book_structure("Not A Real Book", cache)


def test_fetch_verse_range_stamps_each_verse_with_its_book(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    data = sefaria_module.fetch_verse_range("Isaiah", 1, 1, 1, 3, cache, "source")
    assert all(item["book"] == "Isaiah" for item in data)
    assert [item["vs"] for item in data] == [1, 2, 3]


def test_fetch_verse_range_works_for_torah_too(tmp_path):
    """fetch_verse_range is the general-purpose replacement used by the
    web GUI -- it must still handle Torah books correctly, not just the
    new ones."""
    cache = SefariaCache(cache_dir=tmp_path)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"versions": [{"text": ["verse one", "verse two"]}]}

    import ankipasuk.sefaria as sm
    original = sm.requests.get
    sm.requests.get = lambda url, params=None, timeout=None: FakeResponse()
    try:
        data = sefaria_module.fetch_verse_range("Genesis", 1, 1, 1, 2, cache, "source")
    finally:
        sm.requests.get = original
    assert [item["book"] for item in data] == ["Genesis", "Genesis"]


def test_fetch_verse_range_rejects_chapter_out_of_range(tmp_path, fake_isaiah):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="out of range"):
        sefaria_module.fetch_verse_range("Isaiah", 1, 1, 10, 1, cache, "source")


def test_fetch_verse_range_rejects_unknown_book(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Unknown book"):
        sefaria_module.fetch_verse_range("Not A Real Book", 1, 1, 1, 1, cache, "source")
