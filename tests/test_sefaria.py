"""Tests for the new (non-Tora) book-structure discovery and fetch
functions in sefaria.py -- discover_book_structure, get_book_structure,
and fetch_verse_range.

fetch_torah_range and get_chapter_lengths (the pre-existing, Tora-only
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
                    import types

                    import requests

                    raise requests.HTTPError("404", response=types.SimpleNamespace(status_code=404))

            def json(self):
                n = self._chapter_lengths[self._ch - 1]
                return {"versions": [{"text": [f"verse {i + 1}" for i in range(n)]}]}

        return FakeResponse()


@pytest.fixture
def fake_malachi(monkeypatch):
    """A fake 3-chapter "Malachi" with lengths [14, 17, 24] -- small
    enough to probe quickly in tests, standing in for the real book's real verse counts."""
    book = FakeBook([14, 17, 24])
    monkeypatch.setattr(sefaria_module.requests, "get", book.fake_get)
    return book


def test_discover_book_structure_probes_until_failure(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.discover_book_structure("Malachi", cache)
    assert lengths == [14, 17, 24]


def test_discover_book_structure_is_cached_after_first_call(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    sefaria_module.discover_book_structure("Malachi", cache)
    calls_after_first = fake_malachi.call_count

    # A second call (even chapter 4, the one-past-the-end probe) should
    # not hit the network again -- it's served entirely from cache.
    lengths = sefaria_module.discover_book_structure("Malachi", cache)
    assert lengths == [14, 17, 24]
    assert fake_malachi.call_count == calls_after_first


def test_discover_book_structure_persists_across_cache_instances(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    sefaria_module.discover_book_structure("Malachi", cache)
    calls_after_first = fake_malachi.call_count

    fresh_cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.discover_book_structure("Malachi", fresh_cache)
    assert lengths == [14, 17, 24]
    assert fake_malachi.call_count == calls_after_first  # no new network calls


def test_get_book_structure_uses_static_table_for_torah(tmp_path):
    """Tora books must never hit the network -- config.TORAH_VERSE_COUNTS
    is authoritative and free."""
    cache = SefariaCache(cache_dir=tmp_path)

    def fail_if_called(*a, **kw):
        raise AssertionError("should not make a network call for a Tora book")

    import ankipasuk.sefaria as sm
    original = sm.requests.get
    sm.requests.get = fail_if_called
    try:
        lengths = sefaria_module.get_book_structure("Genesis", cache)
    finally:
        sm.requests.get = original
    assert lengths[0] == 31  # Genesis 1 has 31 verses


def test_get_book_structure_discovers_live_for_non_torah(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    lengths = sefaria_module.get_book_structure("Malachi", cache)
    assert lengths == [14, 17, 24]


def test_get_book_structure_rejects_unknown_book(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError):
        sefaria_module.get_book_structure("Not A Real Book", cache)


def test_fetch_verse_range_stamps_each_verse_with_its_book(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    data = sefaria_module.fetch_verse_range("Malachi", 1, 1, 1, 3, cache, "source")
    assert all(item["book"] == "Malachi" for item in data)
    assert [item["vs"] for item in data] == [1, 2, 3]


def test_fetch_verse_range_works_for_torah_too(tmp_path):
    """fetch_verse_range is the general-purpose replacement used by the
    web GUI -- it must still handle Tora books correctly, not just the
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


def test_fetch_verse_range_rejects_chapter_out_of_range(tmp_path, fake_malachi):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="out of range"):
        sefaria_module.fetch_verse_range("Malachi", 1, 1, 10, 1, cache, "source")


def test_fetch_verse_range_rejects_unknown_book(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Unknown book"):
        sefaria_module.fetch_verse_range("Not A Real Book", 1, 1, 1, 1, cache, "source")


def test_a_network_error_does_not_truncate_a_book(tmp_path, monkeypatch):
    # The bug that left Ezekiel at 42 chapters: a failed request mid-way
    # was taken for "no more chapters", and the short book was cached.
    import requests

    book = FakeBook([14, 17, 24])
    real_get = book.fake_get

    def flaky_get(url, params=None, timeout=None):
        if url.endswith("%203"):
            raise requests.ConnectionError("connection reset")
        return real_get(url, params=params, timeout=timeout)

    monkeypatch.setattr(sefaria_module.requests, "get", flaky_get)
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(RuntimeError):
        sefaria_module.discover_book_structure("Malachi", cache)
    assert cache.get_book_structure("Malachi") is None  # nothing cached

    monkeypatch.setattr(sefaria_module.requests, "get", real_get)
    assert sefaria_module.discover_book_structure("Malachi", cache) == [14, 17, 24]


def test_a_truncated_cached_book_is_rediscovered(tmp_path, monkeypatch):
    book = FakeBook([14, 17, 24])
    monkeypatch.setattr(sefaria_module.requests, "get", book.fake_get)
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_book_structure("Malachi", [14, 17])  # cut short by an old failure
    assert sefaria_module.discover_book_structure("Malachi", cache) == [14, 17, 24]


def test_every_listed_book_has_a_chapter_count():
    from ankipasuk.config import MEGILLOT_BOOKS, NEVIIM_BOOKS, NON_TORAH_CHAPTER_COUNTS

    assert set(NON_TORAH_CHAPTER_COUNTS) == set(NEVIIM_BOOKS) | set(MEGILLOT_BOOKS)


def test_a_failed_fetch_says_what_went_wrong_in_words(tmp_path, monkeypatch):
    import requests

    def offline(*_args, **_kwargs):
        raise requests.exceptions.ProxyError("Unable to connect to proxy")  # a ConnectionError too

    monkeypatch.setattr(sefaria_module.requests, "get", offline)
    with pytest.raises(RuntimeError) as failed:
        sefaria_module.get_text_for_ref("Genesis 1", "source", SefariaCache(cache_dir=tmp_path))
    assert str(failed.value).startswith("Couldn't reach Sefaria. Check the internet connection")
    assert "HTTPSConnectionPool" not in str(failed.value)
    late = sefaria_module.fetch_error("Sefaria", "Genesis 1", requests.Timeout())
    assert late == "Sefaria didn't answer in time when fetching Genesis 1. Try again in a moment."
