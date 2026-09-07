"""Tests for ankipasuk.anki_connect.operations.ensure_model / add_notes."""

from ankipasuk.anki_connect.client import DEFAULT_URL
from ankipasuk.anki_connect.operations import add_notes, ensure_model

CARD_TEMPLATES = [{"Name": "Card 1", "Front": "{{Front}}", "Back": "{{Back}}"}]


def test_ensure_model_creates_missing_model(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    assert "MyModel" in fake_anki.models
    assert fake_anki.models["MyModel"]["fields"] == ["Front", "Back"]


def test_ensure_model_is_idempotent(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    # Second call must not attempt to recreate it (FakeAnki asserts on that).
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    assert list(fake_anki.models.keys()) == ["MyModel"]


def test_add_notes_returns_new_note_ids(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    notes = [
        {"deckName": "Deck", "modelName": "MyModel", "fields": {"Front": "a", "Back": "1"}, "tags": []},
        {"deckName": "Deck", "modelName": "MyModel", "fields": {"Front": "b", "Back": "2"}, "tags": []},
    ]
    result = add_notes(notes, url=DEFAULT_URL, dry_run=False)
    assert len(result) == 2
    assert all(isinstance(nid, int) for nid in result)
    assert len(fake_anki.notes) == 2


def test_add_notes_dedup_rejects_matching_first_field_in_same_deck_and_model(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    notes = [
        {"deckName": "Deck", "modelName": "MyModel", "fields": {"Front": "dup", "Back": "1"}, "tags": []},
        {"deckName": "Deck", "modelName": "MyModel", "fields": {"Front": "dup", "Back": "2"}, "tags": []},
    ]
    result = add_notes(notes, url=DEFAULT_URL, dry_run=False)
    assert result[0] is not None
    assert result[1] is None  # rejected as a duplicate of the first


def test_add_notes_allow_duplicate_bypasses_dedup(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    notes = [
        {
            "deckName": "Deck", "modelName": "MyModel",
            "fields": {"Front": "dup", "Back": "1"}, "tags": [],
            "options": {"allowDuplicate": True},
        },
        {
            "deckName": "Deck", "modelName": "MyModel",
            "fields": {"Front": "dup", "Back": "2"}, "tags": [],
            "options": {"allowDuplicate": True},
        },
    ]
    result = add_notes(notes, url=DEFAULT_URL, dry_run=False)
    assert all(nid is not None for nid in result)


def test_add_notes_dry_run_makes_no_changes(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    notes = [{"deckName": "Deck", "modelName": "MyModel", "fields": {"Front": "a", "Back": "1"}, "tags": []}]
    result = add_notes(notes, url=DEFAULT_URL, dry_run=True)
    assert result == [None]
    assert fake_anki.notes == {}


def test_add_notes_empty_list_is_a_noop(fake_anki):
    assert add_notes([], url=DEFAULT_URL, dry_run=False) == []
    assert fake_anki.calls == []
