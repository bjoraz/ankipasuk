from ankipasuk.anki_connect.operations import _BATCH_SIZE
from ankipasuk.anki_connect.tagging import (
    apply_tagging_plan,
    compute_tagging_plan,
    parse_source_field,
)
from ankipasuk.cache import SefariaCache
from ankipasuk.leyning import parasha_table

DECK = "Leyning"


def _placeholder_genesis_parashot(overrides: dict | None = None) -> list[dict]:
    """Sefaria-shaped parasha list for Genesis: real refs for parshiot named
    in ``overrides`` (by slug), harmless placeholders elsewhere -- same
    approach as tests/test_leyning.py."""
    overrides = overrides or {}
    table = parasha_table("Genesis")
    out = []
    for entry in table:
        refs = overrides.get(entry["slug"], ["Genesis 1:31"] * entry["n_aliyot"])
        out.append({"name": entry["slug"], "refs": refs})
    return out


def _cache_with_genesis(tmp_path, overrides=None) -> SefariaCache:
    cache = SefariaCache(cache_dir=tmp_path)
    cache.set_parasha_structure("Genesis", _placeholder_genesis_parashot(overrides))
    return cache


def test_parse_source_field_valid():
    assert parse_source_field("Bereshit 1:1") == ("Genesis", 1, 1)
    assert parse_source_field("Devarim 34:12") == ("Deuteronomy", 34, 12)


def test_parse_source_field_invalid():
    assert parse_source_field("") is None
    assert parse_source_field("not a ref") is None
    assert parse_source_field("Narnia 1:1") is None


def test_compute_tagging_plan_computes_missing_tags(tmp_path, fake_anki):
    bereshit_refs = [
        "Genesis 1:1-2:3", "Genesis 2:4-2:19", "Genesis 2:20-3:21",
        "Genesis 3:22-4:18", "Genesis 4:19-4:22", "Genesis 4:23-5:24",
        "Genesis 5:25-6:8",
    ]
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})

    fake_anki.add_note_with_fields(1, DECK, {"Source": "Bereshit 1:1"}, tags=[])
    fake_anki.add_note_with_fields(2, DECK, {"Source": "Bereshit 6:8"}, tags=[])

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)

    assert len(plan.notes) == 2
    note1 = next(n for n in plan.notes if n.note_id == 1)
    note2 = next(n for n in plan.notes if n.note_id == 2)

    assert "aliyah::bereshit::01-bereshit::1" in note1.missing_tags
    assert "aliyah::bereshit::01-bereshit::7" in note2.missing_tags
    assert "aliyah::bereshit::01-bereshit::maftir" in note2.missing_tags
    assert not note1.conflicting_tags
    assert not note2.conflicting_tags


def test_compute_tagging_plan_flags_conflicting_tags(tmp_path, fake_anki):
    bereshit_refs = ["Genesis 1:1-2:3"] + ["Genesis 1:31"] * 6
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})

    # This note already has an "aliyah::..." tag, but the WRONG one.
    fake_anki.add_note_with_fields(
        1, DECK, {"Source": "Bereshit 1:1"},
        tags=["aliyah::bereshit::01-bereshit::99"],
    )

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    note = plan.notes[0]

    assert "aliyah::bereshit::01-bereshit::99" in note.conflicting_tags
    assert "aliyah::bereshit::01-bereshit::1" in note.missing_tags


def test_compute_tagging_plan_ignores_unrelated_existing_tags(tmp_path, fake_anki):
    bereshit_refs = ["Genesis 1:1-2:3"] + ["Genesis 1:31"] * 6
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})

    fake_anki.add_note_with_fields(
        1, DECK, {"Source": "Bereshit 1:1"}, tags=["leech", "marked"],
    )

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    note = plan.notes[0]

    assert not note.conflicting_tags  # unrelated tags aren't flagged
    assert "aliyah::bereshit::01-bereshit::1" in note.missing_tags


def test_compute_tagging_plan_collects_unparsed_notes(tmp_path, fake_anki):
    cache = _cache_with_genesis(tmp_path)
    fake_anki.add_note_with_fields(1, DECK, {"Source": "not a torah ref"}, tags=[])

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)

    assert plan.unparsed_note_ids == [1]
    assert plan.notes == []


def test_apply_tagging_plan_dry_run_makes_no_changes(tmp_path, fake_anki):
    # Genesis 2:4-2:19 (aliyah 2), verified to have zero overlap with any
    # curated holiday reading -- unlike aliyah 1 (Genesis 1:1-2:3), which
    # entirely coincides with Simchat Torah's reading (see
    # test_holiday_tag_applied_independent_of_parasha_data). This test is
    # only about dry-run behavior, so we want an unambiguous single tag.
    bereshit_refs = ["Genesis 1:1", "Genesis 2:4-2:19"] + ["Genesis 1:31"] * 5
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})
    fake_anki.add_note_with_fields(1, DECK, {"Source": "Bereshit 2:5"}, tags=[])

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    summary = apply_tagging_plan(plan, url="http://fake", dry_run=True)

    assert summary["total_tags_to_add"] == 1
    assert fake_anki.notes[1]["tags"] == []  # untouched


def test_apply_tagging_plan_is_idempotent(tmp_path, fake_anki):
    bereshit_refs = [
        "Genesis 1:1-2:3", "Genesis 2:4-2:19", "Genesis 2:20-3:21",
        "Genesis 3:22-4:18", "Genesis 4:19-4:22", "Genesis 4:23-5:24",
        "Genesis 5:25-6:8",
    ]
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})
    fake_anki.add_note_with_fields(1, DECK, {"Source": "Bereshit 6:8"}, tags=[])

    plan1 = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    apply_tagging_plan(plan1, url="http://fake", dry_run=False)

    tags_after_first_run = set(fake_anki.notes[1]["tags"])
    assert "aliyah::bereshit::01-bereshit::7" in tags_after_first_run
    assert "aliyah::bereshit::01-bereshit::maftir" in tags_after_first_run

    # Running it again should add nothing new and flag no conflicts.
    plan2 = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    summary2 = apply_tagging_plan(plan2, url="http://fake", dry_run=False)

    assert summary2["total_tags_to_add"] == 0
    assert summary2["notes_with_conflicts"] == 0
    assert set(fake_anki.notes[1]["tags"]) == tags_after_first_run


def test_apply_tagging_plan_never_removes_existing_tags(tmp_path, fake_anki):
    bereshit_refs = ["Genesis 1:1-2:3"] + ["Genesis 1:31"] * 6
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})
    fake_anki.add_note_with_fields(
        1, DECK, {"Source": "Bereshit 1:1"}, tags=["my_custom_tag"],
    )

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    apply_tagging_plan(plan, url="http://fake", dry_run=False)

    assert "my_custom_tag" in fake_anki.notes[1]["tags"]
    assert "aliyah::bereshit::01-bereshit::1" in fake_anki.notes[1]["tags"]


def test_holiday_tag_applied_independent_of_parasha_data(tmp_path, fake_anki):
    cache = _cache_with_genesis(tmp_path)  # no real parasha refs needed
    fake_anki.add_note_with_fields(1, DECK, {"Source": "Bereshit 21:2"}, tags=[])

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    note = plan.notes[0]

    assert "holiday::rosh_hashana_i::1" in note.missing_tags


def test_tagging_batches_requests_on_a_large_deck(tmp_path, fake_anki):
    """Regression test for a real bug: notesInfo/addTags used to be sent
    as one single request for the whole deck, which timed out on a deck
    with thousands of notes (the exact scenario a real user hit). This
    seeds more than one batch's worth of notes -- all referencing the same
    verse, so they all need the same single tag -- and checks that both
    notesInfo and addTags were split into multiple calls, and that every
    note still ends up correctly tagged."""
    bereshit_refs = ["Genesis 1:1-2:3", "Genesis 2:4-2:19"] + ["Genesis 1:31"] * 5
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit_refs})

    n_notes = (_BATCH_SIZE * 2) + 50
    for note_id in range(1, n_notes + 1):
        fake_anki.add_note_with_fields(note_id, DECK, {"Source": "Bereshit 2:5"}, tags=[])

    plan = compute_tagging_plan(DECK, url="http://fake", cache=cache)
    notes_info_calls = [params for action, params in fake_anki.calls if action == "notesInfo"]
    assert len(notes_info_calls) == 3  # ceil((500*2+50) / 500) == 3
    assert all(len(call["notes"]) <= _BATCH_SIZE for call in notes_info_calls)
    assert len(plan.notes) == n_notes

    summary = apply_tagging_plan(plan, url="http://fake", dry_run=False)
    assert summary["total_tags_to_add"] == n_notes  # one tag each

    add_tags_calls = [params for action, params in fake_anki.calls if action == "addTags"]
    assert len(add_tags_calls) == 3  # same n_notes worth of note_ids, one tagset group
    assert all(len(call["notes"]) <= _BATCH_SIZE for call in add_tags_calls)

    for note_id in (1, n_notes // 2, n_notes):
        assert "aliyah::bereshit::01-bereshit::2" in fake_anki.notes[note_id]["tags"]
