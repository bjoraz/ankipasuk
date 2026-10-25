"""Tests for ankipasuk.sections: reading Sefaria's section marks, the spans
that are one section, and the bundled data."""

from ankipasuk import sections as sc

PASUQ = "וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר יוֹם אֶחָד׃"


def test_a_break_after_a_pasuq_or_inside_one():
    assert sc.breaks_in(PASUQ + "&nbsp;{פ}") == ["P"]
    assert sc.breaks_in(PASUQ + "&nbsp;{ס}&nbsp;&nbsp;&nbsp;") == ["S"]
    assert sc.breaks_in(PASUQ) == []
    # Inside: after how many words, maqaf splitting them as the Text view does.
    assert sc.breaks_in("וַיְהִי־עֶרֶב {ס} וַיְהִי־בֹקֶר׃ {פ}") == [["S", 2], "P"]


def test_the_decalogue_and_eikhas_acrostics_are_one_section():
    found = {"20:1": ["S"], "20:6": ["S"], "20:13": [["S", 2], "S"], "20:14": [["S", 4], "P"], "20:18": ["S"]}
    assert sc.one_section("Exodus", found) == {"20:1": ["S"], "20:14": ["P"], "20:18": ["S"]}
    assert sc.one_section("Genesis", found) == found


def test_the_bundled_sections():
    assert sc.breaks("Genesis", 1, 5) == ["P"]  # the first day
    assert sc.breaks("Genesis", 10, 14) == ["S"]
    assert any(isinstance(b, list) and b[0] == "P" for b in sc.breaks("Genesis", 35, 22))  # inside the pasuq
    assert sc.breaks("Exodus", 20, 7) == [] and sc.breaks("Exodus", 20, 14) == ["P"]  # the Decalogue, one
    assert sc.breaks("Lamentations", 1, 1) == [] and sc.breaks("Lamentations", 1, 22) == ["P"]
    assert sc.breaks("Ruth", 4, 17) == ["P"] and sc.breaks("Ruth", 4, 22) == []
    assert sc.breaks("Psalms", 1, 6) == []  # a book the app doesn't read
