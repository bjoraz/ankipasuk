"""Tests for ankipasuk.diagram: a pasuq's division as Jacobson-style
brackets."""

from ankipasuk.diagram import pasuq_diagram

# Bereshit 31:33, the example from Jacobson's book (2.14.11).
GENESIS_31_33 = (
    "וַיָּבֹ֨א לָבָ֜ן בְּאֹ֥הֶל יַעֲקֹ֣ב ׀ וּבְאֹ֣הֶל לֵאָ֗ה וּבְאֹ֛הֶל שְׁתֵּ֥י הָאֲמָהֹ֖ת וְלֹ֣א מָצָ֑א "
    "וַיֵּצֵא֙ מֵאֹ֣הֶל לֵאָ֔ה וַיָּבֹ֖א בְּאֹ֥הֶל רָחֵֽל׃"
)


def _boxes(unit):
    return [(b["from"], b["to"], b["rank"], b["name"]) for b in unit["boxes"]]


def test_jacobsons_example_has_his_brackets():
    first, second = pasuq_diagram(GENESIS_31_33)["units"]
    # His 1-ETN, 2-TIP, 3-REV, 3-TVR, 4-GER, 4-LEG -- in Sephardi Hebrew.
    assert _boxes(first) == [
        (0, 5, 1, "אתנח"), (0, 4, 2, "טרחא"), (0, 2, 3, "רביע"),
        (0, 0, 4, "גריש"), (1, 1, 4, "פסק"), (3, 3, 3, "תביר"),
    ]
    assert _boxes(second) == [
        (6, 9, 1, "סוף פסוק"), (6, 7, 2, "זקף קטן"), (6, 6, 3, "קדמא"), (8, 8, 2, "טרחא"),
    ]


def _rows(unit):
    """Each bracket's row from the top (0 = the unit's own bracket)."""
    top = max(b["h"] for b in unit["boxes"])
    return {b["name"]: top - b["h"] for b in unit["boxes"]}


def test_rows_follow_how_deep_each_division_is_as_in_jacobsons_figure():
    first, _second = pasuq_diagram(GENESIS_31_33)["units"]
    # His figure: 1-ETN, 2-TIP, 3-REV on successive rows; 4-GER and the
    # downgraded 3-TVR one lower; 4-LEG lowest.
    assert _rows(first) == {"אתנח": 0, "טרחא": 1, "רביע": 2, "גריש": 3, "תביר": 3, "פסק": 4}


def test_a_downgraded_taam_sits_below_the_earlier_one_of_its_rank():
    # The tevir divides only what's left after the ravia' (both rank 3), so
    # its bracket is lower -- even with nothing inside the ravia's bracket.
    first, _second = pasuq_diagram(GENESIS_31_33)["units"]
    rows = _rows(first)
    assert rows["תביר"] > rows["רביע"]
    assert rows["פסק"] > rows["גריש"]  # the same for the two rank-4 brackets


def test_divisions_the_cards_dont_make_are_greyed():
    def grey(n):
        units = pasuq_diagram(GENESIS_31_33, card_n=n)["units"]
        return {b["name"] for u in units for b in u["boxes"] if b["grey"]}

    assert grey(1) == set()
    assert {"פסק", "תביר", "קדמא"} <= grey(2)
    assert "אתנח" not in grey(99) and "סוף פסוק" not in grey(99)  # a unit's own bracket always shows


def test_each_unit_holds_its_own_words():
    first, second = pasuq_diagram(GENESIS_31_33)["units"]
    assert first["words"][0]["text"] == "וַיָּבֹ֨א" and first["words"][-1]["text"] == "מָצָ֑א"
    assert second["words"][0]["g"] == 6 and second["words"][-1]["text"] == "רָחֵֽל׃"


def test_a_pasuq_without_an_atnah_is_one_unit(genesis_1_1):
    # A short pasuq whose strongest division is below atnaḥ.
    short = "וַיֹּ֥אמֶר יְהֹוָ֖ה אֶל־מֹשֶׁ֥ה לֵּאמֹֽר׃"
    (unit,) = pasuq_diagram(short)["units"]
    assert unit["boxes"][0]["name"] == "סוף פסוק"


def test_an_empty_pasuq():
    assert pasuq_diagram("") == {"units": []}
