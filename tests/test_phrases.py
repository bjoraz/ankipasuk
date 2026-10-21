"""Tests for ankipasuk.phrases: the finder and its rules on small made-up
texts, then known phrases of the bundled Tanakh (docs/phrases.md)."""

import pytest

from ankipasuk import phrases as ph
from ankipasuk import shorashim as sh
from ankipasuk.shorashim_build import CONSTRUCT, PROPER, QERE

# A made-up dictionary: words a..h, fillers x1..x9, and a few real ones by
# their Strong's numbers (אֵת, לֹא, אָמַר, a preposition, a name, God's names).
NAMES = ["a", "b", "c", "d", "e", "f", "g", "h", *(f"x{i}" for i in range(1, 10)),
         "et", "not", "say", "in", "moshe", "aharon", "miryam", "yhwh", "elohim", "tsevaot"]
LEMMAS = [[f"90{i:02d}", "w"] for i in range(17)] + [
    ["853", "p"], ["3808", "p"], ["559", "w"], [None, "p"], ["4872", "n"], ["175", "n"], ["4813", "n"],
    ["3068", "n"], ["430", "w"], ["6635", "w"],
]
L = {name: i for i, name in enumerate(NAMES)}


def w(*names, flags=None):
    flags = flags or {}
    return [[L[n], flags.get(n, 0)] for n in names]


def made_up(*verses):
    return ph.Corpus(LEMMAS, [("Genesis", {f"1:{i + 1}": v for i, v in enumerate(verses)})])


def keys(c, *verse_numbers):
    spans = [c.verses[("Genesis", f"1:{v}")] for v in verse_numbers]
    found = ph._find(c, ph._segments(c, [{"book": "Genesis", "ch": 1, "vs": v} for v in verse_numbers]))
    assert spans
    return {tuple(NAMES[x] for x in key): len(occ) for key, (_s, _n, occ) in found.items()}


def test_a_phrase_is_as_long_as_its_occurrences_allow():
    c = made_up(w("a", "b", "c", "d", "e"), w("a", "b", "c", "d", "e"), w("c", "a", "b"))
    # "a b" occurs three times, "a b c d e" twice; "c d" only ever inside it.
    assert keys(c, 1) == {("a", "b"): 3, ("a", "b", "c", "d", "e"): 2}


def test_the_object_marker_is_left_out_and_a_qere_read_for_its_ketiv():
    c = made_up(w("a", "et", "b", "x1"), w("x2", "a", "b"),
                w("a", "c", "b", flags={"b": QERE}))  # c, the ketiv; b, its qere
    assert keys(c, 1) == {("a", "b"): 3}


def test_a_sof_pasuq_is_crossed_only_by_a_phrase_holding_a_whole_pasuq():
    # The end of one pasuq and the start of the next: cut there.
    c = made_up(w("x1", "a", "b"), w("c", "d", "x2"), w("x3", "a", "b"), w("c", "d", "x4"))
    assert keys(c, 1, 2) == {("a", "b"): 2, ("c", "d"): 2}
    # With a whole pasuq in it, one phrase.
    c = made_up(w("x1", "a", "b"), w("c", "d"), w("e", "x2"), w("x3", "a", "b"), w("c", "d"), w("e", "x4"))
    assert ("a", "b", "c", "d", "e") in keys(c, 1, 2, 3)


def test_particles_and_a_final_verb_of_saying_come_off_the_ends():
    c = made_up(w("in", "a", "b", "say", "x1"), w("x2", "in", "a", "b", "say", "x3"))
    assert keys(c, 1) == {("a", "b"): 2}


def test_formula_classes():
    proper = {"moshe": PROPER, "aharon": PROPER, "miryam": PROPER}
    c = made_up(w("say", "moshe", flags=proper), w("yhwh", "elohim"),
                w("moshe", "aharon", "miryam", flags=proper), w("yhwh", "tsevaot"), w("tsevaot", "a"),
                w("elohim", "moshe", flags={"elohim": CONSTRUCT, **proper}))

    def cls(v):
        a, b = c.verses[("Genesis", f"1:{v}")]
        return ph.formula_class(c, a, b - a)
    assert cls(1) == "speech"
    assert cls(2) == cls(4) == cls(6) == ph.TITLES  # יהוה אלהים, יהוה צבאות, אלהי משה
    assert cls(3) is None  # a list of names
    assert cls(5) is None  # צבאות alone is an army


def test_chance():
    assert ph._chance(2, 0.001) == pytest.approx(0.001 ** 2 / 2, rel=1e-3)
    assert ph._chance(3, 5.0) == 1.0


def test_thresholds_from_settings_stay_within_their_limits():
    t = ph.Thresholds.from_settings({"echo_places": 5.4, "refrain_chance": 7, "idiom_bound": "x",
                                     "rare_wording": True, "content_words": float("nan"), "other": 1})
    assert (t.echo_places, t.refrain_chance) == (5, 0.05)  # rounded; at most its limit
    assert (t.idiom_bound, t.rare_wording, t.content_words) == (0.1, 10, 2)  # not numbers: the defaults
    assert ph.Thresholds.from_settings(None) == ph.DEFAULTS
    assert ph.DEFAULTS.idiom_g2 == pytest.approx(10.83, abs=0.005)


# --- the bundled Tanakh ------------------------------------------------------
@pytest.fixture(scope="module")
def tanakh():
    return ph.corpus()


def rows(c, book, first, last, t=ph.DEFAULTS):
    data = [{"book": book, "ch": int(k.split(":")[0]), "vs": int(k.split(":")[1])}
            for (b, k) in c.verses if b == book]
    data = [d for d in data if first <= (d["ch"], d["vs"]) <= last]
    return ph._classify(c, ph._segments(c, data), t)


def letters(c, r):
    out = []
    for t in range(r["start"], r["start"] + r["length"]):
        book, key = c.where[t]
        out.extend(w[0] for w in sh._book(book)[key][c.first[t]:c.last[t] + 1])
    return " ".join(out)


def find(c, found, *texts):
    return next(r for r in found if letters(c, r) in texts)


def test_bereshit_1_has_its_refrains_an_echo_and_formulas(tanakh):
    found = rows(tanakh, "Genesis", (1, 1), (2, 3))
    evening = find(tanakh, found, "ויהי ערב ויהי בקר יום")
    assert evening["kinds"] == ["refrain"] and len(evening["here"]) == 6 and not evening["formula"]
    tohu = find(tanakh, found, "תהו ובהו")
    assert "echo" in tohu["kinds"] and tohu["places"] == [("Jeremiah", "4:23")]
    assert find(tanakh, found, "ויאמר אלהים")["formula"] == "speech"


def test_the_thresholds_change_what_is_listed(tanakh):
    def texts(**changed):
        found = rows(tanakh, "Genesis", (1, 1), (2, 3), ph.Thresholds(**changed))
        return {letters(tanakh, r): r["kinds"] for r in found}
    assert "refrain" in texts()["ויהי ערב ויהי בקר יום"]  # six times
    assert "refrain" not in texts(refrain_here=7).get("ויהי ערב ויהי בקר יום", [])
    assert "תהו ובהו" not in texts(content_words=3)
    echoes = sum("echo" in kinds for kinds in texts().values())
    assert sum("echo" in kinds for kinds in texts(echo_places=6).values()) > echoes


def test_idioms_and_lists(tanakh):
    found = rows(tanakh, "Exodus", (3, 1), (4, 31))
    assert "idiom" in find(tanakh, found, "זבת חלב ודבש")["kinds"]
    nations = find(tanakh, found, "הכנעני והחתי והאמרי והפרזי והחוי והיבוסי")
    assert nations["formula"] is None  # a list, not a formula


def test_gods_names_are_formulas_unless_their_wording_is_exceptional(tanakh):
    shaddai = find(tanakh, rows(tanakh, "Genesis", (17, 1), (17, 27)), "אל שדי")
    assert shaddai["variant"] and shaddai["formula"] is None  # 8 places in the Tanakh
    eden = find(tanakh, rows(tanakh, "Genesis", (2, 4), (3, 24)), "יהוה אלהים")
    assert eden["variant"]  # 20 of its 49 places here
    devarim = rows(tanakh, "Deuteronomy", (5, 1), (6, 25))
    ours = find(tanakh, devarim, "יהוה אלהינו", "יהוה אלהיך", "יהוה אלהיכם")
    assert ours["formula"] == ph.TITLES and not ours["variant"]


def test_long_phrases_whole(tanakh):
    # The princes' offering, twelve times; the Decalogue, as in Shemot 20.
    offering = max(rows(tanakh, "Numbers", (7, 1), (7, 89)), key=lambda r: r["length"])
    assert offering["length"] >= 50 and len(offering["here"]) == 12 and "refrain" in offering["kinds"]
    decalogue = max(rows(tanakh, "Deuteronomy", (5, 1), (6, 25)), key=lambda r: r["length"])
    assert decalogue["length"] >= 70 and decalogue["places"][0] == ("Exodus", "20:1")


def test_passage_marks_the_loaded_words(genesis_1_1, genesis_1_2):
    data = [{"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1},
            {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_2}]
    out = ph.passage(data)
    entry = next(p for p in out["phrases"] if sh.consonants(p["text"]) == "תהוובהו")
    assert entry["id"] in out["sections"]["echo"]
    words = sh.pieces(genesis_1_2)
    assert [sh.consonants(words[k][0]) for _v, k in entry["marks"]] == ["תהו", "ובהו"]
    assert entry["verses"] == [1] and entry["places"][0]["ref"] == "Yirmeyahu 4:23"
    empty = {"refrain": [], "echo": [], "idiom": [], "formula": []}
    assert ph.passage([]) == {"phrases": [], "sections": empty}
