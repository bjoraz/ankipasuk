"""Tests for ankipasuk.qeriya.

The regression tests at the bottom replay the exact validation done during
development: reconstructing "Sefaria-shaped" 'aliyya refs from the user's
own hand-applied tags (bereshit.apkg) and confirming every single one of
the 568 tagged (verse, tag) pairs is reproduced exactly. That data isn't
shipped with the repo (it's someone's personal Anki deck), so these tests
use small, hand-built stand-ins that exercise the same code paths and edge
cases (in particular, the Genesis 31/32 maftir chapter-boundary case).
"""

from ankipasuk import qeriya as qr


def test_parse_ref_range_single_verse():
    assert qr.parse_ref_range("Genesis 1:1") == ("Genesis", 1, 1, 1, 1)


def test_parse_ref_range_same_chapter_short_form():
    assert qr.parse_ref_range("Genesis 1:1-5") == ("Genesis", 1, 1, 1, 5)


def test_parse_ref_range_accepts_en_dash():
    """Regression test for a real bug: Sefaria's API doesn't consistently
    use a plain ASCII hyphen for ranges -- an en-dash (U+2013) was observed
    in the wild for a live-fetched 'aliyya ref, which broke tagging with
    ValueError: Could not parse ref range. Same-chapter short form and full
    cross-chapter form should both work with any common dash variant."""
    assert qr.parse_ref_range("Deuteronomy 33:1\u20137") == ("Deuteronomy", 33, 1, 33, 7)
    assert qr.parse_ref_range("Genesis 1:1\u20132:3") == ("Genesis", 1, 1, 2, 3)
    assert qr.parse_ref_range("Genesis 1:1\u20145") == ("Genesis", 1, 1, 1, 5)  # em-dash too


def test_parse_ref_range_cross_chapter():
    assert qr.parse_ref_range("Genesis 1:1-2:3") == ("Genesis", 1, 1, 2, 3)


def test_verse_index_round_trips():
    for ch, vs in [(1, 1), (1, 31), (2, 1), (6, 8), (50, 26)]:
        idx = qr.verse_index("Genesis", ch, vs)
        assert qr.verse_from_index("Genesis", idx) == (ch, vs)


def test_verse_index_is_monotonic_across_chapter_boundary():
    end_of_ch1 = qr.verse_index("Genesis", 1, 31)  # Genesis 1 has 31 verses
    start_of_ch2 = qr.verse_index("Genesis", 2, 1)
    assert start_of_ch2 == end_of_ch1 + 1


def test_compute_maftir_range_same_chapter():
    # Bereshit: 'aliyya 7 ends 6:8, maftir is 4 verses -> 6:5-6:8
    assert qr.compute_maftir_range("Genesis", (6, 8), 4) == (6, 5, 6, 8)


def test_compute_maftir_range_crosses_chapter_boundary():
    # Vayyetse: 'aliyya 7 ends 32:2 (Jewish/Sefaria numbering), maftir is 3
    # verses -> crosses back into chapter 31 -> 31:55-32:2.
    assert qr.compute_maftir_range("Genesis", (32, 2), 3) == (31, 55, 32, 2)


def test_chapter_counts_override_changes_verse_index():
    """Regression test: verse_index/verse_from_index must actually use a
    passed-in chapter_counts override rather than silently falling back to
    the static table, since production tagging relies on this to stay
    correct if Sefaria's live chapter structure ever differs from the
    static snapshot (this is exactly what happened at Genesis 31/32)."""
    static_idx = qr.verse_index("Genesis", 32, 1)  # uses the static table (31 has 55 verses)

    # A live count where chapter 31 has only 54 verses instead of 55.
    live_counts = list(qr.TORAH_VERSE_COUNTS["Genesis"])
    live_counts[30] = 54  # chapter 31 (0-indexed)
    live_idx = qr.verse_index("Genesis", 32, 1, chapter_counts=live_counts)

    assert live_idx == static_idx - 1
    # And the round trip works with the override too.
    assert qr.verse_from_index("Genesis", live_idx, chapter_counts=live_counts) == (32, 1)


def test_compute_maftir_range_uses_chapter_counts_override():
    """Regression test: if the live chapter-31 count differs from the
    static table, the maftir backward-walk must reflect the live value,
    not silently compute an off-by-one range."""
    live_counts = list(qr.TORAH_VERSE_COUNTS["Genesis"])
    live_counts[30] = 54  # chapter 31 has 54 verses in this (hypothetical) live count

    # With the override, verse_index for (32, 2) is one less than with the
    # static table, so walking back the same 3 verses lands one verse
    # earlier throughout -- but still correctly straddles the boundary.
    result = qr.compute_maftir_range("Genesis", (32, 2), 3, chapter_counts=live_counts)
    static_result = qr.compute_maftir_range("Genesis", (32, 2), 3)
    assert result != static_result
    assert result == (31, 54, 32, 2)  # one verse earlier than the static-table answer


def test_parasha_table_genesis_matches_known_slugs():
    table = qr.parasha_table("Genesis")
    assert len(table) == 12
    slugs = [e["slug"] for e in table]
    assert slugs[:4] == ["bereshit", "noah", "lekh_lekha", "vayyera"]
    assert all(e["rel"] == i + 1 for i, e in enumerate(table))


def test_holiday_readings_are_all_torah_only():
    for entry in qr.holiday_readings():
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
    qr.parasha_table('Genesis') positionally), with real refs only for the
    parashiyyot named in ``overrides`` (by slug) and harmless placeholders
    everywhere else. The placeholder is Genesis 1:31 (not 1:1) so there's
    room to subtract any parasha's maftir verse count without going
    negative -- these placeholder parashiyyot are never queried in the tests
    below, but build_parasha_intervals still computes a maftir range for
    every entry in the table, so the placeholder must be valid."""
    table = qr.parasha_table("Genesis")
    out = []
    for entry in table:
        refs = overrides.get(entry["slug"], ["Genesis 1:31"] * entry["n_aliyot"])
        out.append({"name": entry["slug"], "refs": refs})
    return out


def test_tags_for_verse_full_aliyah_and_maftir_for_bereshit():
    # Real 'aliyya boundaries for Parashat Bereshit, as Sefaria would return them.
    refs = [
        "Genesis 1:1-2:3", "Genesis 2:4-2:19", "Genesis 2:20-3:21",
        "Genesis 3:22-4:18", "Genesis 4:19-4:22", "Genesis 4:23-5:24",
        "Genesis 5:25-6:8",
    ]
    sefaria_parashot = _fake_sefaria_parashot({"bereshit": refs})
    intervals = qr.build_parasha_intervals("Genesis", sefaria_parashot)

    assert "aliyya::bereshit::01-bereshit::1" in qr.tags_for_verse(
        "Genesis", 1, 1, intervals, []
    )
    assert "aliyya::bereshit::01-bereshit::7" in qr.tags_for_verse(
        "Genesis", 6, 8, intervals, []
    )
    # The maftir: last 4 verses of the parasha (validated against the real deck).
    for ch, vs in [(6, 5), (6, 6), (6, 7), (6, 8)]:
        assert "aliyya::bereshit::01-bereshit::maftir" in qr.tags_for_verse(
            "Genesis", ch, vs, intervals, []
        )
    assert "aliyya::bereshit::01-bereshit::maftir" not in qr.tags_for_verse(
        "Genesis", 6, 4, intervals, []
    )


def test_tags_for_verse_vayetzei_maftir_crosses_chapter_boundary():
    # Vayyetse is the 7th parasha of Genesis (rel=7). 'Aliyya 7 real end is
    # 32:2 in Jewish/Sefaria numbering; maftir is 3 verses -> 31:55-32:2.
    refs = ["Genesis 1:1"] * 6 + ["Genesis 31:43-32:2"]
    sefaria_parashot = _fake_sefaria_parashot({"vayyetse": refs})
    intervals = qr.build_parasha_intervals("Genesis", sefaria_parashot)

    for ch, vs in [(31, 55), (32, 1), (32, 2)]:
        assert "aliyya::bereshit::07-vayyetse::maftir" in qr.tags_for_verse(
            "Genesis", ch, vs, intervals, []
        )
    assert "aliyya::bereshit::07-vayyetse::maftir" not in qr.tags_for_verse(
        "Genesis", 31, 54, intervals, []
    )


def test_tags_for_verse_holiday_reading_independent_of_parasha():
    intervals = qr.build_parasha_intervals("Genesis", _fake_sefaria_parashot({}))
    holiday_intervals = qr.build_holiday_intervals()

    # Rosh haShana I reads Genesis 21:1-21:4 as 'aliyya 1.
    tags = qr.tags_for_verse("Genesis", 21, 2, intervals, holiday_intervals)
    assert "holiday::rosh_hashana_i::1" in tags


def test_tags_for_verse_returns_multiple_tags_when_applicable():
    # Genesis 22:1 is simultaneously part of Vayyera's weekly 'aliyya 7 *and*
    # the Rosh haShana II holiday reading's 'aliyya 1 -- both should be
    # returned together.
    refs = ["Genesis 1:1"] * 6 + ["Genesis 22:1-22:24"]
    sefaria_parashot = _fake_sefaria_parashot({"vayyera": refs})
    intervals = qr.build_parasha_intervals("Genesis", sefaria_parashot)
    holiday_intervals = qr.build_holiday_intervals()

    tags = qr.tags_for_verse("Genesis", 22, 1, intervals, holiday_intervals)
    assert "aliyya::bereshit::04-vayyera::7" in tags
    assert "holiday::rosh_hashana_ii::1" in tags


# =============================================================
#  NAMES AND TAGS (docs/transliteration.md)
# =============================================================
def test_to_slug():
    assert qr.to_slug("Ḥayye Sara") == "hayye_sara"
    assert qr.to_slug("Shemini 'Atseret") == "shemini_atseret"
    assert qr.to_slug("Vezot haBerakha") == "vezot_haberakha"


def test_every_slug_is_the_ascii_form_of_its_name():
    for book in ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"):
        for entry in qr.parasha_table(book):
            assert entry["slug"] == qr.to_slug(entry["name"])
    for entry in qr.holiday_readings():
        assert entry["slug"] == qr.to_slug(entry["display_name"])


def test_parasha_names_pairs_by_position_and_refuses_a_length_mismatch():
    sefaria = [{"name": f"Sefaria {i}"} for i in range(12)]
    mapping = qr.parasha_names("Genesis", sefaria)
    assert mapping["Sefaria 4"]["name"] == "Ḥayye Sara"
    assert mapping["Sefaria 4"]["slug"] == "hayye_sara"
    assert qr.parasha_names("Genesis", sefaria[:11]) == {}


def test_legacy_tag_renames_weekly_holiday_and_tiqqun_tags():
    renames = qr.legacy_tag_renames(
        {"Genesis": ["Bereshit", "Noach", "Lech Lecha", "Vayera", "Chayei Sara", "Toldot",
                     "Vayetzei", "Vayishlach", "Vayeshev", "Miketz", "Vayigash", "Vayechi"]}
    )
    assert renames["aliyah::bereshit::05-haye_sara::3"] == "aliyya::bereshit::05-hayye_sara::3"
    assert renames["aliyah::bamidbar::04-shlach::maftir"] == "aliyya::bemidbar::04-shelah_lekha::maftir"
    assert renames["aliyah::bereshit::01-bereshit::1"] == "aliyya::bereshit::01-bereshit::1"
    assert renames["holiday::simchat_torah::1"] == "holiday::simhat_tora::1"
    assert "holiday::purim::1" not in renames  # unchanged slug
    assert renames["ankipasuk-aliyah"] == "ankipasuk-aliyya"
    assert renames["amud::012"] == "ammud::012"
    assert renames["parasha::chayei-sara"] == "parasha::hayye_sara"
    # Keys are lowercase, so lookups must lowercase the tag first.
    assert all(k == k.lower() for k in renames)


def test_legacy_tag_renames_without_sefaria_names_skips_parasha_tags():
    renames = qr.legacy_tag_renames()
    assert not any(k.startswith("parasha::") for k in renames)


def test_every_weekly_and_holiday_rename_targets_a_tag_the_tagger_generates():
    generated = set()
    for book in ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"):
        fake = [{"name": e["slug"], "refs": [f"{book} 5:5"] * e["n_aliyot"]} for e in qr.parasha_table(book)]
        generated |= {tag for _s, _e, tag in qr.build_parasha_intervals(book, fake)}
    generated |= {tag for _b, _s, _e, tag in qr.build_holiday_intervals()}

    renames = qr.legacy_tag_renames()
    targets = {v for k, v in renames.items() if k.startswith(("aliyah::", "holiday::"))}
    assert targets <= generated
    assert "aliyah::devarim::11-vezot_haberakhah::maftir" not in renames  # no maftir in the table
