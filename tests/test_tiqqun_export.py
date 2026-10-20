"""Tests for ankipasuk.tiqqun_export: telling which pasuq (or lines) a
tiqqun note is for, so an export never adds the same card twice."""

import csv
import io

import ankipasuk.tiqqun_export as te
from ankipasuk.cache import SefariaCache


def test_an_ammud_notes_pasuq_comes_from_its_tag_and_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(te, "get_verses_starting_on_amud", lambda n, cache: [(8, 21), (8, 22), (9, 1)])
    monkeypatch.setattr(te, "get_book_for_page", lambda n, cache: "Genesis")
    fields = {"Title": "Bereshit Amud 9", "Sequence": "3", "FrontRows": "<div>old html</div>", "Line": ""}
    key = te.existing_note_key(fields, ["ammud::009"], SefariaCache(cache_dir=tmp_path))
    assert key == te.pasuq_key("Genesis", 9, 1)


def test_the_old_amud_tag_works_too(tmp_path, monkeypatch):
    monkeypatch.setattr(te, "get_verses_starting_on_amud", lambda n, cache: [(1, 1)])
    monkeypatch.setattr(te, "get_book_for_page", lambda n, cache: "Genesis")
    fields = {"Title": "x", "Sequence": "1", "Line": ""}
    key = te.existing_note_key(fields, ["amud::001"], SefariaCache(cache_dir=tmp_path))
    assert key == "pasuq:Genesis 1:1"


def test_an_aliyya_notes_pasuq_comes_from_the_range_in_its_title(tmp_path, monkeypatch):
    # Genesis 18 has 33 pesuqim, so card 35 of "18:1-19:5" is 19:2.
    monkeypatch.setattr(te, "get_chapter_lengths", lambda book, cache: [31] * 17 + [33, 38])
    fields = {"Title": "Bereshit Vayyera 1 (Bereshit 18:1-19:5)", "Sequence": "35", "Line": ""}
    tags = ["ankipasuk-aliyya", "parasha::vayyera"]
    assert te.existing_note_key(fields, tags, SefariaCache(cache_dir=tmp_path)) == "pasuq:Genesis 19:2"


def test_an_old_spelling_in_the_title_is_understood(tmp_path, monkeypatch):
    monkeypatch.setattr(te, "get_chapter_lengths", lambda book, cache: [10] * 30)
    fields = {"Title": "Vayikra Tzav 1 (Vayikra 6:1-6:11)", "Sequence": "2", "Line": ""}
    assert te.existing_note_key(fields, [], SefariaCache(cache_dir=tmp_path)) == "pasuq:Leviticus 6:2"


def test_a_row_card_is_its_recited_lines(tmp_path):
    fields = {"Line": '<div class="line">בראשית ברא</div>', "Sequence": "4"}
    assert te.existing_note_key(fields, [], SefariaCache(cache_dir=tmp_path)) == "row:בראשית ברא"


def test_an_unrecognisable_note_still_matches_identical_lines(tmp_path):
    existing = [{"fields": {"Title": {"value": "?"}, "FrontRows": {"value": "<b>אאא</b>"}}, "tags": []}]
    keys = te.existing_keys(existing, SefariaCache(cache_dir=tmp_path))
    same = {"fields": {"FrontRows": "<i>אאא</i>"}, "key": "pasuq:Genesis 1:1"}
    other = {"fields": {"FrontRows": "<i>בבב</i>"}, "key": "pasuq:Genesis 1:2"}
    assert te.is_duplicate(same, keys) and not te.is_duplicate(other, keys)


def test_csv_names_the_note_type_and_deck_and_quotes_multi_line_html():
    notes = [{"fields": {"Title": "T", "FrontRows": "<div>a</div>\n<div>b</div>"}, "tags": ["ammud::001"]}]
    text = te.csv_text(notes, "Ammudim::001")
    header, body = text.split("#tags column:10\n")
    assert "#notetype:Ankipasuk Aliyah" in header and "#deck:Ammudim::001" in header
    (row,) = list(csv.reader(io.StringIO(body), delimiter="\t"))
    assert row[0] == "T" and row[4] == "<div>a</div>\n<div>b</div>" and row[-1] == "ammud::001"
