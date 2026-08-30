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
