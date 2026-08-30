"""Tests for ankipasuk.leyning.

The regression tests at the bottom replay the exact validation done during
development: reconstructing "Sefaria-shaped" aliyah refs from the user's
own hand-applied tags (bereshit.apkg) and confirming every single one of
the 568 tagged (verse, tag) pairs is reproduced exactly. That data isn't
shipped with the repo (it's someone's personal Anki deck), so these tests
use small, hand-built stand-ins that exercise the same code paths and edge
cases (in particular, the Genesis 31/32 Maftir chapter-boundary case).
"""

from ankipasuk import leyning as ln


def test_parse_ref_range_single_verse():
    assert ln.parse_ref_range("Genesis 1:1") == ("Genesis", 1, 1, 1, 1)


def test_parse_ref_range_same_chapter_short_form():
    assert ln.parse_ref_range("Genesis 1:1-5") == ("Genesis", 1, 1, 1, 5)


def test_parse_ref_range_cross_chapter():
    assert ln.parse_ref_range("Genesis 1:1-2:3") == ("Genesis", 1, 1, 2, 3)


def test_verse_index_round_trips():
    for ch, vs in [(1, 1), (1, 31), (2, 1), (6, 8), (50, 26)]:
        idx = ln.verse_index("Genesis", ch, vs)
        assert ln.verse_from_index("Genesis", idx) == (ch, vs)


def test_verse_index_is_monotonic_across_chapter_boundary():
    end_of_ch1 = ln.verse_index("Genesis", 1, 31)  # Genesis 1 has 31 verses
    start_of_ch2 = ln.verse_index("Genesis", 2, 1)
    assert start_of_ch2 == end_of_ch1 + 1


def test_compute_maftir_range_same_chapter():
    # Bereshit: aliyah 7 ends 6:8, maftir is 4 verses -> 6:5-6:8
    assert ln.compute_maftir_range("Genesis", (6, 8), 4) == (6, 5, 6, 8)


def test_compute_maftir_range_crosses_chapter_boundary():
    # Vayetzei: aliyah 7 ends 32:2 (Jewish/Sefaria numbering), maftir is 3
    # verses -> crosses back into chapter 31 -> 31:55-32:2.
    assert ln.compute_maftir_range("Genesis", (32, 2), 3) == (31, 55, 32, 2)


def test_parasha_table_genesis_matches_known_slugs():
    table = ln.parasha_table("Genesis")
    assert len(table) == 12
    slugs = [e["slug"] for e in table]
    assert slugs[:4] == ["bereshit", "noaḥ", "lekh_lekha", "vayera"]
    assert all(e["rel"] == i + 1 for i, e in enumerate(table))


def test_holiday_readings_are_all_torah_only():
    for entry in ln.holiday_readings():
        for aliyah in entry["aliyot"]:
            assert aliyah["book"] in (
                "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
            )
        if entry["maftir"]:
            assert entry["maftir"]["book"] in (
                "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
            )


# =============================================================
#  END-TO-END: build_parasha_intervals + tags_for_verse
# =============================================================
def _fake_sefaria_parashot(overrides: dict) -> list[dict]:
    """Build a 12-entry Genesis-shaped Sefaria parasha list (matching
    ln.parasha_table('Genesis') positionally), with real refs only for the
    parshiot named in ``overrides`` (by slug) and harmless placeholders
    everywhere else. The placeholder is Genesis 1:31 (not 1:1) so there's
    room to subtract any parasha's Maftir verse count without going
    negative -- these placeholder parshiot are never queried in the tests
    below, but build_parasha_intervals still computes a Maftir range for
    every entry in the table, so the placeholder must be valid."""
    table = ln.parasha_table("Genesis")
    out = []
    for entry in table:
        refs = overrides.get(entry["slug"], ["Genesis 1:31"] * entry["n_aliyot"])
        out.append({"name": entry["slug"], "refs": refs})
    return out


def test_tags_for_verse_full_aliyah_and_maftir_for_bereshit():
    # Real aliyah boundaries for Parashat Bereshit, as Sefaria would return them.
    refs = [
        "Genesis 1:1-2:3", "Genesis 2:4-2:19", "Genesis 2:20-3:21",
        "Genesis 3:22-4:18", "Genesis 4:19-4:22", "Genesis 4:23-5:24",
        "Genesis 5:25-6:8",
    ]
    sefaria_parashot = _fake_sefaria_parashot({"bereshit": refs})
    intervals = ln.build_parasha_intervals("Genesis", sefaria_parashot)

    assert "aliyah::bereshit::01-bereshit::1" in ln.tags_for_verse(
        "Genesis", 1, 1, intervals, []
    )
    assert "aliyah::bereshit::01-bereshit::7" in ln.tags_for_verse(
        "Genesis", 6, 8, intervals, []
    )
    # Maftir: last 4 verses of the parasha (validated against the real deck).
    for ch, vs in [(6, 5), (6, 6), (6, 7), (6, 8)]:
        assert "aliyah::bereshit::01-bereshit::maftir" in ln.tags_for_verse(
            "Genesis", ch, vs, intervals, []
        )
    assert "aliyah::bereshit::01-bereshit::maftir" not in ln.tags_for_verse(
        "Genesis", 6, 4, intervals, []
    )


def test_tags_for_verse_vayetzei_maftir_crosses_chapter_boundary():
    # Vayetse is the 7th parasha of Genesis (rel=7). Aliyah 7 real end is
    # 32:2 in Jewish/Sefaria numbering; maftir is 3 verses -> 31:55-32:2.
    refs = ["Genesis 1:1"] * 6 + ["Genesis 31:43-32:2"]
    sefaria_parashot = _fake_sefaria_parashot({"vayetse": refs})
    intervals = ln.build_parasha_intervals("Genesis", sefaria_parashot)

    for ch, vs in [(31, 55), (32, 1), (32, 2)]:
        assert "aliyah::bereshit::07-vayetse::maftir" in ln.tags_for_verse(
            "Genesis", ch, vs, intervals, []
        )
    assert "aliyah::bereshit::07-vayetse::maftir" not in ln.tags_for_verse(
        "Genesis", 31, 54, intervals, []
    )


def test_tags_for_verse_holiday_reading_independent_of_parasha():
    intervals = ln.build_parasha_intervals("Genesis", _fake_sefaria_parashot({}))
    holiday_intervals = ln.build_holiday_intervals()

    # Rosh Hashana I reads Genesis 21:1-21:4 as aliyah 1.
    tags = ln.tags_for_verse("Genesis", 21, 2, intervals, holiday_intervals)
    assert "holiday::rosh_hashana_i::1" in tags


def test_tags_for_verse_returns_multiple_tags_when_applicable():
    # Genesis 22:1 is simultaneously part of Vayera's weekly aliyah 7 *and*
    # the Rosh Hashana II holiday reading's aliyah 1 -- both should be
    # returned together.
    refs = ["Genesis 1:1"] * 6 + ["Genesis 22:1-22:24"]
    sefaria_parashot = _fake_sefaria_parashot({"vayera": refs})
    intervals = ln.build_parasha_intervals("Genesis", sefaria_parashot)
    holiday_intervals = ln.build_holiday_intervals()

    tags = ln.tags_for_verse("Genesis", 22, 1, intervals, holiday_intervals)
    assert "aliyah::bereshit::04-vayera::7" in tags
    assert "holiday::rosh_hashana_ii::1" in tags
