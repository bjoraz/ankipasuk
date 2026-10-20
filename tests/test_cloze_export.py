"""Tests for ankipasuk.cloze_export: the notes both cloze exports (CSV and
straight to Anki) are built from."""

from ankipasuk.cache import SefariaCache
from ankipasuk.cloze_export import (
    CSV_HEADER,
    FIELD_NAMES,
    anki_fields,
    build_cloze_notes,
    check_note_type_fields,
    csv_rows,
)
from tests.test_anki_connect.test_tagging import _cache_with_genesis


def _verse(book, ch, vs, text, **extra):
    return {"book": book, "ch": ch, "vs": vs, "pointed": text, "plain": text, **extra}


def test_tora_notes_are_numbered_by_book_and_tagged(tmp_path, genesis_1_1):
    bereshit = ["Genesis 1:1-2:3", "Genesis 2:4-2:19", "Genesis 2:20-3:21", "Genesis 3:22-4:18",
                "Genesis 4:19-4:22", "Genesis 4:23-5:24", "Genesis 5:25-6:8"]
    cache = _cache_with_genesis(tmp_path, {"bereshit": bereshit})
    notes = build_cloze_notes([_verse("Genesis", 2, 4, genesis_1_1)], 2, True, cache)
    (note,) = notes
    assert note["key"] == ("Genesis", 2, 4)
    assert note["fields"][:2] == ["35", "Bereshit 2:4"]  # Genesis 1 has 31 pesuqim
    assert "aliyya::bereshit::01-bereshit::2" in note["tags"]


def test_haftara_notes_are_numbered_within_the_haftara_and_tagged(tmp_path, genesis_1_1):
    verses = [
        _verse("Isaiah", 42, 5, genesis_1_1, haftara="bereshit", haftara_pos=1),
        _verse("Isaiah", 42, 6, genesis_1_1 + " ב", haftara="bereshit", haftara_pos=2),
    ]
    notes = build_cloze_notes(verses, 2, True, SefariaCache(cache_dir=tmp_path))
    assert [n["fields"][:2] for n in notes] == [["1", "Yesha'yahu 42:5"], ["2", "Yesha'yahu 42:6"]]
    assert all(n["tags"] == ["haftara::bereshit"] for n in notes)
    assert notes[0]["fields"][5] == genesis_1_1 + " ב"  # Next
    assert notes[1]["fields"][4] == genesis_1_1  # Previous


def test_neighbours_never_reach_outside_a_haftara(tmp_path, genesis_1_1):
    # Two haftarot fetched one after the other: Bereshit's last pasuq
    # must not show Noaḥ's first as its Next.
    verses = [
        _verse("Isaiah", 42, 21, "סוף", haftara="bereshit", haftara_pos=17),
        _verse("Isaiah", 54, 1, "רני", haftara="noah", haftara_pos=1),
    ]
    first, second = build_cloze_notes(verses, 2, True, SefariaCache(cache_dir=tmp_path))
    assert first["fields"][5] == "" and second["fields"][4] == ""


def test_blank_pesuqim_are_skipped(tmp_path, genesis_1_1):
    verses = [_verse("Isaiah", 6, 1, "  "), _verse("Isaiah", 6, 2, genesis_1_1)]
    (note,) = build_cloze_notes(verses, 2, True, SefariaCache(cache_dir=tmp_path))
    assert note["fields"][1] == "Yesha'yahu 6:2"


def test_csv_rows_end_with_the_tags_column_the_header_names():
    note = {"key": None, "fields": [str(i) for i in range(len(FIELD_NAMES))], "tags": ["a::b", "c"]}
    (row,) = csv_rows([note])
    assert row[-1] == "a::b c"
    assert f"#tags column:{len(row)}" in CSV_HEADER


def test_note_type_check_needs_the_named_fields_in_order():
    good = ["Number", "Source", "Text", "Verse", "Previous", "Next", "Back Extra", "Opts", "Sound"]
    assert check_note_type_fields(good) is None
    assert check_note_type_fields(["Source", "Number"] + good[2:]) is not None
    assert check_note_type_fields(good[:7]) is not None  # no settings field


def test_anki_fields_leave_extra_fields_alone():
    names = ["Number", "Source", "Text", "Verse", "Previous", "Next", "Back Extra", "Opts", "Sound"]
    note = {"fields": [str(i) for i in range(8)], "tags": []}
    mapped = anki_fields(note, names)
    assert mapped["Opts"] == "7"
    assert "Sound" not in mapped  # a recording field is never written
