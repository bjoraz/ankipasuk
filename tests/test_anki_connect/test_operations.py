"""Tests for ankipasuk.anki_connect.operations.ensure_model / add_notes /
ensure_media_file / ensure_model_fields / sync_model_css /
sync_model_templates."""

from ankipasuk.anki_connect.client import DEFAULT_URL
from ankipasuk.anki_connect.operations import (
    add_notes,
    ensure_media_file,
    ensure_model,
    ensure_model_fields,
    sync_model_css,
    sync_model_templates,
)

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


def test_sync_model_css_updates_an_existing_models_styling(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "old css", CARD_TEMPLATES, url=DEFAULT_URL)
    sync_model_css("MyModel", "new css", url=DEFAULT_URL)
    assert fake_anki.models["MyModel"]["css"] == "new css"


def test_ensure_model_fields_appends_a_missing_field(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    ensure_model_fields("MyModel", ["Front", "Back", "Extra"], url=DEFAULT_URL)
    assert fake_anki.models["MyModel"]["fields"] == ["Front", "Back", "Extra"]


def test_ensure_model_fields_is_a_noop_when_order_already_matches(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    ensure_model_fields("MyModel", ["Front", "Back"], url=DEFAULT_URL)
    assert fake_anki.models["MyModel"]["fields"] == ["Front", "Back"]


def test_ensure_model_fields_reorders_an_existing_field_to_match(fake_anki):
    """A field that already exists but isn't first -- e.g. a note type an
    older version of this code created with a different field order --
    must be moved, not just left alone (Anki treats a note as empty based
    on its FIRST field, regardless of field name)."""
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    ensure_model_fields("MyModel", ["Back", "Front"], url=DEFAULT_URL)
    assert fake_anki.models["MyModel"]["fields"] == ["Back", "Front"]


def test_sync_model_templates_updates_an_existing_models_templates(fake_anki):
    ensure_model("MyModel", ["Front", "Back"], "css", CARD_TEMPLATES, url=DEFAULT_URL)
    new_templates = [{"Name": "Card 1", "Front": "new front", "Back": "new back"}]
    sync_model_templates("MyModel", new_templates, url=DEFAULT_URL)
    assert fake_anki.models["MyModel"]["cardTemplates"] == {
        "Card 1": {"Front": "new front", "Back": "new back"},
    }


def test_ensure_media_file_uploads_missing_file(fake_anki):
    ensure_media_file("_stam.ttf", "YmFzZTY0", url=DEFAULT_URL)
    assert fake_anki.media["_stam.ttf"] == "YmFzZTY0"


def test_ensure_media_file_is_idempotent(fake_anki):
    ensure_media_file("_stam.ttf", "YmFzZTY0", url=DEFAULT_URL)
    calls_after_first = len(fake_anki.calls)
    ensure_media_file("_stam.ttf", "YmFzZTY0", url=DEFAULT_URL)
    # Second call should only check (retrieveMediaFile), never re-upload.
    assert len(fake_anki.calls) == calls_after_first + 1
    assert fake_anki.calls[-1][0] == "retrieveMediaFile"
