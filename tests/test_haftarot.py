"""Tests for the bundled haftara table and the tags derived from it
(ankipasuk.qeriya, data/haftarot.json)."""

import pytest

from ankipasuk.config import NEVIIM_BOOKS, NON_TORAH_CHAPTER_COUNTS
from ankipasuk.qeriya import (
    haftara_label,
    haftara_table,
    haftara_tags_for_verse,
    holiday_readings,
    parasha_table,
    parse_range_ref,
)

TORAH = ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy")


def test_every_parasha_has_one_haftara_in_reading_order():
    parashot = [(book, e["slug"]) for book in TORAH for e in parasha_table(book)]
    listed = [(e["parasha_book"], e["slug"]) for e in haftara_table() if e["kind"] == "parasha"]
    assert listed == parashot
    assert len(listed) == 54


def test_special_shabbatot_use_the_holiday_tables_slugs():
    specials = {e["slug"] for e in haftara_table() if e["kind"] == "special"}
    assert specials == {
        "shabbat_hol_hamoed_sukkot", "shabbat_sheqalim", "shabbat_zakhor", "shabbat_para",
        "shabbat_hahodesh", "shabbat_hol_hamoed_pesah", "shabbat_hagadol",
    }
    # The four parashiyyot are already in the holiday reading table (for
    # their Tora reading); the haftara must be filed under the same slug.
    holiday_slugs = {e["slug"] for e in holiday_readings()}
    assert {"shabbat_sheqalim", "shabbat_zakhor", "shabbat_para", "shabbat_hahodesh"} <= holiday_slugs


def test_every_range_is_a_real_range_in_the_neviim():
    slugs = [e["slug"] for e in haftara_table()]
    assert len(slugs) == len(set(slugs))
    for entry in haftara_table():
        assert entry["refs"], entry["slug"]
        for ref in entry["refs"]:
            book, start, end = parse_range_ref(ref)
            assert book in NEVIIM_BOOKS, ref
            assert start <= end, ref
            assert end[0] <= NON_TORAH_CHAPTER_COUNTS[book], ref


@pytest.mark.parametrize("ref, expected", [
    ("Isaiah 42:5-21", ("Isaiah", (42, 5), (42, 21))),
    ("Jeremiah 7:21-8:3", ("Jeremiah", (7, 21), (8, 3))),
    ("I Kings 18:46-19:21", ("I Kings", (18, 46), (19, 21))),
])
def test_parse_range_ref(ref, expected):
    assert parse_range_ref(ref) == expected


def test_parse_range_ref_rejects_a_single_verse():
    with pytest.raises(ValueError):
        parse_range_ref("Isaiah 42:5")


def test_toledot_starts_at_malachi_1_1():
    # The printed S&P list has 1:7, a misprint; see data/haftarot.json.
    toledot = next(e for e in haftara_table() if e["slug"] == "toledot")
    assert toledot["refs"] == ["Malachi 1:1-2:7"]


def test_a_pasuq_in_two_haftarot_gets_both_tags():
    assert haftara_tags_for_verse("Jeremiah", 1, 5) == ["haftara::shemot", "haftara::mattot"]
    assert haftara_tags_for_verse("Isaiah", 54, 10) == ["haftara::noah", "haftara::ki_tetse"]
    # Re'eh starts just after: 54:11.
    assert haftara_tags_for_verse("Isaiah", 54, 11) == ["haftara::ree"]


def test_ranges_are_inclusive_and_multi_part():
    # Mishpatim: Jeremiah 34:8-22, then 33:25-26.
    assert haftara_tags_for_verse("Jeremiah", 34, 8) == ["haftara::mishpatim"]
    assert haftara_tags_for_verse("Jeremiah", 34, 22) == ["haftara::mishpatim"]
    assert haftara_tags_for_verse("Jeremiah", 33, 25) == ["haftara::mishpatim"]
    assert haftara_tags_for_verse("Jeremiah", 33, 24) == []
    # Shabbat Shuva spans two books: Hosea, then Micah.
    assert haftara_tags_for_verse("Micah", 7, 20) == ["haftara::vayyelekh"]


def test_tora_pesuqim_get_no_haftara_tags():
    assert haftara_tags_for_verse("Genesis", 1, 1) == []


def test_labels_use_our_book_names():
    mishpatim = next(e for e in haftara_table() if e["slug"] == "mishpatim")
    assert haftara_label(mishpatim) == "Mishpatim — Yirmeyahu 34:8–22; Yirmeyahu 33:25–26"
