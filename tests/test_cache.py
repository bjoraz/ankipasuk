import os

import pytest

from ankipasuk.cache import SefariaCache


def test_text_cache_round_trips_through_disk(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    assert cache.get_text("Genesis 1", "source") is None

    cache.set_text("Genesis 1", "source", ["verse one", "verse two"])

    # A brand-new instance pointed at the same directory should see it
    # without any network access -- this is the whole point of a
    # persistent, on-disk cache.
    reloaded = SefariaCache(cache_dir=tmp_path)
    assert reloaded.get_text("Genesis 1", "source") == ["verse one", "verse two"]


def test_text_cache_is_keyed_by_version_too(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_text("Genesis 1", "source", ["pointed"])
    cache.set_text("Genesis 1", "plain", ["unpointed"])

    assert cache.get_text("Genesis 1", "source") == ["pointed"]
    assert cache.get_text("Genesis 1", "plain") == ["unpointed"]


def test_parasha_structure_cache_round_trips(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    structure = [{"name": "Bereshit", "refs": ["Genesis 1:1-6:8"]}]
    cache.set_parasha_structure("Genesis", structure)

    reloaded = SefariaCache(cache_dir=tmp_path)
    assert reloaded.get_parasha_structure("Genesis") == structure


def test_clear_removes_memory_and_disk_state(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_text("Genesis 1", "source", ["verse one"])
    assert cache.text_path.exists()

    cache.clear()
    assert cache.get_text("Genesis 1", "source") is None
    assert not cache.text_path.exists()

    reloaded = SefariaCache(cache_dir=tmp_path)
    assert reloaded.get_text("Genesis 1", "source") is None


def test_corrupted_cache_file_is_ignored_not_fatal(tmp_path):
    cache_dir = tmp_path
    cache_dir.mkdir(exist_ok=True)
    (cache_dir / "text_cache.json").write_text("not valid json{{{", encoding="utf-8")

    cache = SefariaCache(cache_dir=cache_dir)  # must not raise
    assert cache.get_text("Genesis 1", "source") is None


def test_get_text_for_ref_only_hits_network_once(tmp_path, monkeypatch):
    """End-to-end check that a repeat fetch of the same ref is served from
    the cache instead of calling requests.get again."""
    import ankipasuk.sefaria as sefaria_module

    call_count = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"versions": [{"text": ["cached verse text"]}]}

    def fake_get(url, params=None, timeout=None):
        call_count["n"] += 1
        return FakeResponse()

    monkeypatch.setattr(sefaria_module.requests, "get", fake_get)

    cache = SefariaCache(cache_dir=tmp_path)
    first = sefaria_module.get_text_for_ref("Genesis 1", "source", cache)
    second = sefaria_module.get_text_for_ref("Genesis 1", "source", cache)

    assert first == second == ["cached verse text"]
    assert call_count["n"] == 1  # not fetched twice

    # And a fresh cache instance backed by the same directory also avoids
    # the network entirely.
    fresh_cache = SefariaCache(cache_dir=tmp_path)
    third = sefaria_module.get_text_for_ref("Genesis 1", "source", fresh_cache)
    assert third == ["cached verse text"]
    assert call_count["n"] == 1


def test_book_structure_cache_round_trips(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    assert cache.get_book_structure("Isaiah") is None

    cache.set_book_structure("Isaiah", [26, 22, 26])
    assert cache.get_book_structure("Isaiah") == [26, 22, 26]

    # A fresh instance backed by the same directory sees it too.
    fresh_cache = SefariaCache(cache_dir=tmp_path)
    assert fresh_cache.get_book_structure("Isaiah") == [26, 22, 26]


def test_book_structure_cache_included_in_clear_and_stats(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_book_structure("Ruth", [22, 23, 18, 22])
    assert cache.stats()["cached_book_structures"] == 1

    cache.clear()
    assert cache.get_book_structure("Ruth") is None
    assert cache.stats()["cached_book_structures"] == 0


# =============================================================
#  defer_saves() -- batches many small writes into one flush at the
#  end, instead of writing the whole cache file to disk on every
#  single set_text() call. This is the actual fix for a real crash
#  report: probing ~66 chapters of Isaiah one at a time triggered ~66
#  rapid full-file rewrites, which on Windows collided with something
#  (commonly antivirus real-time scanning) transiently holding a
#  handle on the just-written file, surfacing as a repeated
#  PermissionError ("being used by another process") that crashed the
#  whole app.
# =============================================================
def test_defer_saves_suppresses_writes_until_the_block_exits(tmp_path, monkeypatch):
    cache = SefariaCache(cache_dir=tmp_path)
    write_count = {"n": 0}
    original = SefariaCache._write_json_atomic

    def counting_write(path, entries):
        write_count["n"] += 1
        original(path, entries)

    monkeypatch.setattr(SefariaCache, "_write_json_atomic", staticmethod(counting_write))

    with cache.defer_saves():
        cache.set_text("Genesis 1", "source", ["v1"])
        cache.set_text("Genesis 2", "source", ["v2"])
        cache.set_text("Genesis 3", "source", ["v3"])
        # Still zero writes to disk -- everything so far is in-memory only.
        assert write_count["n"] == 0
        assert not cache.text_path.exists()

    # Exactly one write for all three set_text calls combined, once the
    # block exits -- not three.
    assert write_count["n"] == 1
    assert cache.text_path.exists()

    # And the data itself is genuinely all there, not just the last entry.
    fresh = SefariaCache(cache_dir=tmp_path)
    assert fresh.get_text("Genesis 1", "source") == ["v1"]
    assert fresh.get_text("Genesis 2", "source") == ["v2"]
    assert fresh.get_text("Genesis 3", "source") == ["v3"]


def test_defer_saves_flushes_even_if_the_block_raises(tmp_path):
    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(ValueError):
        with cache.defer_saves():
            cache.set_text("Genesis 1", "source", ["v1"])
            raise ValueError("simulated failure partway through a probing loop")

    # Whatever was fetched before the failure is still persisted -- a
    # probing loop that dies partway through (e.g. a network error on
    # chapter 40 of a 50-chapter book) doesn't lose chapters 1-39.
    fresh = SefariaCache(cache_dir=tmp_path)
    assert fresh.get_text("Genesis 1", "source") == ["v1"]


def test_defer_saves_nested_blocks_flush_only_once(tmp_path, monkeypatch):
    cache = SefariaCache(cache_dir=tmp_path)
    write_count = {"n": 0}
    original = SefariaCache._write_json_atomic

    def counting_write(path, entries):
        write_count["n"] += 1
        original(path, entries)

    monkeypatch.setattr(SefariaCache, "_write_json_atomic", staticmethod(counting_write))

    with cache.defer_saves():
        cache.set_text("Genesis 1", "source", ["v1"])
        with cache.defer_saves():  # a function called from within another defer_saves() block
            cache.set_text("Genesis 2", "source", ["v2"])
        # Inner block exited but the outer one hasn't -- still deferred.
        assert write_count["n"] == 0

    assert write_count["n"] == 1  # only the outermost exit actually flushes


# =============================================================
#  _write_json_atomic retry-with-backoff -- the second line of defense
#  against the same transient-Windows-file-lock issue, for callers
#  that aren't (or can't be) wrapped in defer_saves().
# =============================================================
def test_write_json_atomic_retries_past_a_transient_os_error(tmp_path, monkeypatch):
    monkeypatch.setattr("ankipasuk.cache.time.sleep", lambda _: None)  # don't actually wait in tests

    real_replace = os.replace
    call_count = {"n": 0}

    def flaky_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise PermissionError("simulated transient Windows file lock")
        real_replace(src, dst)

    monkeypatch.setattr("ankipasuk.cache.os.replace", flaky_replace)

    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_text("Genesis 1", "source", ["v1"])  # must not raise

    assert call_count["n"] == 3  # failed twice, succeeded on the third try
    assert cache.get_text("Genesis 1", "source") == ["v1"]


def test_write_json_atomic_gives_up_after_max_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr("ankipasuk.cache.time.sleep", lambda _: None)

    def always_fails(src, dst):
        raise PermissionError("simulated permanently locked file")

    monkeypatch.setattr("ankipasuk.cache.os.replace", always_fails)

    cache = SefariaCache(cache_dir=tmp_path)
    with pytest.raises(PermissionError):
        cache.set_text("Genesis 1", "source", ["v1"])


def test_concurrent_writes_use_independent_temp_files(tmp_path):
    """Two SefariaCache instances (simulating two nearly-simultaneous
    writes) writing to the same path must not share a temp filename --
    otherwise one's os.replace could consume the temp file the other is
    still writing to, surfacing as a confusing FileNotFoundError rather
    than a clean success or an honest retry-able PermissionError."""
    cache_a = SefariaCache(cache_dir=tmp_path)
    cache_b = SefariaCache(cache_dir=tmp_path)

    tmp_names = set()
    real_open = open

    def spying_open(path, *a, **kw):
        s = str(path)
        if s.endswith(".tmp") and "text_cache" in s:
            tmp_names.add(s)
        return real_open(path, *a, **kw)

    import builtins
    original_open = builtins.open
    builtins.open = spying_open
    try:
        cache_a.set_text("Genesis 1", "source", ["from a"])
        cache_b.set_text("Genesis 2", "source", ["from b"])
    finally:
        builtins.open = original_open

    assert len(tmp_names) == 2  # two writes, two distinct temp filenames
