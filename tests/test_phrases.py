"""Tests for ankipasuk.phrases: the finder and its rules on small made-up
texts, then known phrases of the bundled Tanakh (docs/phrases.md)."""

import pytest

from ankipasuk import phrases as ph
from ankipasuk import shorashim as sh
from ankipasuk.shorashim_build import CONSTRUCT, DUKE, ETNAHTA, KING, PROPER, QERE

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


def test_a_phrase_crosses_a_break_only_from_and_to_breaks_at_most_a_step_weaker():
    # The end of one pasuq and the start of the next: cut at the sof pasuq.
    c = made_up(w("x1", "a", "b"), w("c", "d", "x2"), w("x3", "a", "b"), w("c", "d", "x4"))
    assert keys(c, 1, 2) == {("a", "b"): 2, ("c", "d"): 2}
    # A whole pasuq with part of the next (or the last word of the one
    # before): only the whole pasuq.
    c = made_up(w("x1", "a", "b"), w("c", "d"), w("e", "x2"), w("x3", "a", "b"), w("c", "d"), w("e", "x4"))
    assert keys(c, 1, 2, 3) == {("a", "b"): 2, ("c", "d"): 2}
    # Whole pesuqim, one phrase.
    c = made_up(w("x1"), w("a", "b"), w("c", "d"), w("x2"), w("a", "b"), w("c", "d"))
    assert ("a", "b", "c", "d") in keys(c, 2, 3)
    # An etnaḥta: a whole half, or nothing across it.
    half = {"b": ETNAHTA}
    c = made_up(w("x1", "a", "b", "c", "d", flags=half), w("x2", "a", "b", "c", "d", flags=half))
    assert keys(c, 1) == {("a", "b"): 2, ("c", "d"): 2}
    c = made_up(w("a", "b", "c", "d", flags=half), w("a", "b", "c", "d", flags=half))
    assert keys(c, 1) == {("a", "b", "c", "d"): 2}
    # A king (zaqef, tifḥa...) the same; particles at the edges don't count.
    king = {"x1": KING, "x2": KING, "b": KING}
    c = made_up(w("x1", "in", "a", "b", "c", "d", flags=king), w("x2", "in", "a", "b", "c", "d", flags=king))
    assert keys(c, 1) == {("a", "b", "c", "d"): 2}
    king = {"b": KING}
    c = made_up(w("x1", "a", "b", "c", "d", flags=king), w("x2", "a", "b", "c", "d", flags=king))
    assert keys(c, 1) == {("a", "b"): 2, ("c", "d"): 2}


def test_one_step_weaker_is_enough():
    def both(*names, flags):
        first = {("x1" if n == "x" else n): f for n, f in flags.items()}
        second = {("x2" if n == "x" else n): f for n, f in flags.items()}
        return made_up(w("x1", *names, flags=first), w("x2", *names, flags=second))
    # Across a king from a duke, across an etnaḥta from a king: one phrase.
    assert keys(both("a", "b", "c", "d", flags={"x": DUKE, "b": KING}), 1) == {("a", "b", "c", "d"): 2}
    assert keys(both("a", "b", "c", "d", flags={"x": KING, "b": ETNAHTA}), 1) == {("a", "b", "c", "d"): 2}
    # Two steps weaker: cut.
    split = {("a", "b"): 2, ("c", "d"): 2}
    assert keys(both("a", "b", "c", "d", flags={"x": DUKE, "b": ETNAHTA}), 1) == split
    # Across a sof pasuq from an etnaḥta to an etnaḥta: one phrase; from a king, cut.
    half = {"x1": ETNAHTA, "x2": ETNAHTA, "d": ETNAHTA}
    c = made_up(w("x1", "a", "b", flags=half), w("c", "d", "x3", flags=half),
                w("x2", "a", "b", flags=half), w("c", "d", "x4", flags=half))
    assert keys(c, 1, 2) == {("a", "b", "c", "d"): 2}
    unit = {"x1": KING, "x2": KING, "d": ETNAHTA}
    c = made_up(w("x1", "a", "b", flags=unit), w("c", "d", "x3", flags=unit),
                w("x2", "a", "b", flags=unit), w("c", "d", "x4", flags=unit))
    assert keys(c, 1, 2) == {("a", "b"): 2, ("c", "d"): 2}


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
                                     "rare_title": True, "content_words": float("nan"), "other": 1})
    assert (t.echo_places, t.refrain_chance) == (5, 0.05)  # rounded; at most its limit
    assert (t.idiom_bound, t.rare_title, t.content_words) == (0.1, 10, 2)  # not numbers: the defaults
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
    evening = find(tanakh, found, "ויהי ערב ויהי בקר")  # not יום: יום אחד is the next unit
    assert evening["kinds"] == ["refrain"] and len(evening["here"]) == 6 and not evening["formula"]
    tohu = find(tanakh, found, "תהו ובהו")
    assert "echo" in tohu["kinds"] and tohu["places"] == [("Jeremiah", "4:23")]
    assert find(tanakh, found, "ויאמר אלהים")["formula"] == "speech"


def test_the_thresholds_change_what_is_listed(tanakh):
    def texts(**changed):
        found = rows(tanakh, "Genesis", (1, 1), (2, 3), ph.Thresholds(**changed))
        return {letters(tanakh, r): r["kinds"] for r in found}
    assert "refrain" in texts()["ויהי ערב ויהי בקר"]  # six times
    assert "refrain" not in texts(refrain_here=7).get("ויהי ערב ויהי בקר", [])
    assert "תהו ובהו" not in texts(content_words=3)
    echoes = sum("echo" in kinds for kinds in texts().values())
    assert sum("echo" in kinds for kinds in texts(echo_places=6).values()) > echoes


def test_gods_name_is_no_persons_name_in_the_formula_classes(tanakh):
    temple = find(tanakh, rows(tanakh, "I Samuel", (3, 1), (3, 21)), "בית יהוה")
    assert temple["formula"] is None  # not a name formula, as בית משה would be
    joseph = find(tanakh, rows(tanakh, "Genesis", (39, 1), (39, 23)), "ויהי יהוה את יוסף")
    assert joseph["formula"] is None  # not a time formula
    # Nor one of a list's three names: this is speech.
    speech = find(tanakh, rows(tanakh, "Numbers", (19, 1), (19, 22)), "וידבר יהוה אל משה ואל אהרן")
    assert speech["formula"] == "speech"


def test_idioms_and_lists(tanakh):
    found = rows(tanakh, "Exodus", (3, 1), (4, 31))
    assert "idiom" in find(tanakh, found, "ארץ זבת חלב ודבש")["kinds"]
    nations = find(tanakh, found, "והאמרי והפרזי והחוי והיבוסי")  # after מקום הכנעני והחתי's zaqef
    assert nations["formula"] is None  # a list, not a formula


def test_gods_names_are_formulas_unless_rare_or_mostly_here(tanakh):
    # Counted as dictionary words, like every phrase: in all their forms.
    shaddai = find(tanakh, rows(tanakh, "Genesis", (17, 1), (17, 27)), "אל שדי")
    assert shaddai["exceptional"] == "rare" and shaddai["formula"] is None  # 8 times in the Tanakh
    eden = find(tanakh, rows(tanakh, "Genesis", (2, 4), (3, 24)), "יהוה אלהים")
    assert eden["formula"] == ph.TITLES and not eden["exceptional"]  # 20 of its 903 times here
    devarim = rows(tanakh, "Deuteronomy", (5, 1), (6, 25))
    ours = find(tanakh, devarim, "יהוה אלהינו", "יהוה אלהיך", "יהוה אלהיכם")
    assert ours["formula"] == ph.TITLES and not ours["exceptional"]
    ezekiel = find(tanakh, rows(tanakh, "Ezekiel", (1, 1), (48, 35)), "אדני יהוה")
    assert ezekiel["exceptional"] == "here" and ezekiel["formula"] is None  # 217 of its 301
    assert (ph._exceptional(10, 0), ph._exceptional(30, 10), ph._exceptional(30, 9)) == ("rare", "here", None)


def test_spans_are_each_occurrence_in_the_texts_order(tanakh):
    genesis = sh._book("Genesis")
    pesuqim = [{"book": "Genesis", "ch": 1, "vs": v, "pointed": " ".join(w for w, *_ in genesis[f"1:{v}"])}
               for v in range(1, 32)]
    out = ph.passage(pesuqim)
    evening = next(p for p in out["phrases"] if "refrain" in p["kinds"] and p["here"] == 6
                   and sh.consonants(p["text"]).startswith("ויהיערב"))
    assert [v for v, *_ in evening["spans"]] == [4, 7, 12, 18, 22, 30]  # 1:5, 1:8, ... 1:31
    assert all(v == v2 and k < k2 for v, k, v2, k2 in evening["spans"])


def test_long_phrases_whole(tanakh):
    # The princes' offering, twelve times: its four whole pesuqim (the
    # fifth ends with each prince's name); the Decalogue, as in Shemot 20.
    offering = max(rows(tanakh, "Numbers", (7, 1), (7, 89)), key=lambda r: r["length"])
    assert offering["length"] >= 40 and len(offering["here"]) == 12 and "refrain" in offering["kinds"]
    assert letters(tanakh, offering).startswith("וקרבנו") and letters(tanakh, offering).endswith("לחטאת")
    decalogue = max(rows(tanakh, "Deuteronomy", (5, 1), (6, 25)), key=lambda r: r["length"])
    assert decalogue["length"] >= 70 and decalogue["places"][0] == ("Exodus", "20:2")


def test_no_phrase_crosses_a_break_from_or_to_a_weaker_one(tanakh):
    passages = [("Genesis", (1, 1), (3, 24)), ("Numbers", (22, 2), (25, 9)), ("Deuteronomy", (5, 1), (6, 25)),
                ("Ezekiel", (6, 1), (7, 27)), ("Ruth", (1, 1), (4, 22))]
    for book, first, last in passages:
        for r in rows(tanakh, book, first, last):
            assert ph._cut(tanakh, r["start"], r["length"]) == [(r["start"], r["length"])], letters(tanakh, r)
    # Yeḥezqel's ויהי דבר יהוה אלי לאמר runs on into the next pasuq no more.
    texts = {letters(tanakh, r) for r in rows(tanakh, "Ezekiel", (6, 1), (7, 27))}
    assert not any("לאמר בן אדם" in t for t in texts) and "בן אדם" in texts
    # Nor ויהי ערב ויהי בקר into יום אחד (יום has no disjunctive); but מארץ
    # מצרים starts on the tevir of הוצאתיך, a step below the tifḥa it crosses.
    texts = {letters(tanakh, r) for r in rows(tanakh, "Genesis", (1, 1), (2, 3))}
    assert "ויהי ערב ויהי בקר" in texts and "ויהי ערב ויהי בקר יום" not in texts
    devarim = rows(tanakh, "Deuteronomy", (5, 1), (6, 25))
    assert "idiom" in find(tanakh, devarim, "מארץ מצרים מבית עבדים")["kinds"]


def test_passage_marks_the_loaded_words(genesis_1_1, genesis_1_2):
    data = [{"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1},
            {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_2}]
    out = ph.passage(data)
    entry = next(p for p in out["phrases"] if sh.consonants(p["text"]) == "תהוובהו")
    assert entry["id"] in out["sections"]["echo"]
    words = sh.pieces(genesis_1_2)
    assert [sh.consonants(words[k][0]) for _v, k in entry["marks"]] == ["תהו", "ובהו"]
    assert entry["verses"] == [1] and entry["places"][0]["ref"] == "Yirmeyahu 4:23"
    assert entry["spans"] == [[*entry["marks"][0], *entry["marks"][-1]]]  # its first word and last
    empty = {"refrain": [], "echo": [], "idiom": [], "formula": []}
    assert ph.passage([]) == {"phrases": [], "sections": empty}
