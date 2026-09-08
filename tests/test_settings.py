"""Tests for ankipasuk.settings.Settings."""

from ankipasuk.settings import Settings


def test_get_returns_default_when_nothing_saved(tmp_path):
    settings = Settings(cache_dir=tmp_path)
    assert settings.get("missing_key", "fallback") == "fallback"


def test_get_returns_none_by_default_when_no_default_given(tmp_path):
    settings = Settings(cache_dir=tmp_path)
    assert settings.get("missing_key") is None


def test_set_then_get_round_trips(tmp_path):
    settings = Settings(cache_dir=tmp_path)
    settings.set("deck_name", "Master::Leyning::Aliyot")
    assert settings.get("deck_name") == "Master::Leyning::Aliyot"


def test_set_persists_to_disk_for_a_fresh_instance(tmp_path):
    Settings(cache_dir=tmp_path).set("deck_name", "Master::Leyning::Aliyot")
    fresh = Settings(cache_dir=tmp_path)
    assert fresh.get("deck_name") == "Master::Leyning::Aliyot"


def test_set_overwrites_a_previous_value(tmp_path):
    settings = Settings(cache_dir=tmp_path)
    settings.set("deck_name", "Old::Deck")
    settings.set("deck_name", "New::Deck")
    assert settings.get("deck_name") == "New::Deck"


def test_unrelated_keys_are_preserved_across_writes(tmp_path):
    settings = Settings(cache_dir=tmp_path)
    settings.set("a", 1)
    settings.set("b", 2)
    assert settings.get("a") == 1
    assert settings.get("b") == 2


def test_corrupted_settings_file_falls_back_to_empty(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("not valid json{{{", encoding="utf-8")
    settings = Settings(cache_dir=tmp_path)
    assert settings.get("anything", "fallback") == "fallback"
