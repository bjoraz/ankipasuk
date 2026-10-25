"""Tests for ankipasuk.frames: the units, known frames of the bundled
Tanakh, and the frames as the phrase views get them (docs/phrases.md,
Frames)."""

from math import comb

from ankipasuk import frames as fr
from ankipasuk import phrases as ph
from ankipasuk import semantics as se
from ankipasuk import shorashim as sh

# Strong's numbers: בָּרָא, אֱלֹהִים, יֶלֶד, רוּחַ.
CREATE, GOD, CHILD, WIND = "1254", "430", "3206", "7307"


def keys_of(book):
    return sorted((k for (b, k) in ph.corpus().verses if b == book), key=fr._key)


def words(f):
    """A frame's dictionary words, by Strong's number."""
    c = ph.corpus()
    return [c.strong[t] for t in range(f["ends"][0], f["ends"][0] + f["length"])]


def frame(book, first, last, *strong):
    return next(f for f in fr.book_frames(book)
                if (f["first"], f["last"]) == (first, last) and words(f) == list(strong))


def named(book):
    keys = keys_of(book)
    return [(keys[a], keys[b], n, kind) for a, b, n, kind in fr.units(book, keys)]


def test_units_are_sections_petuha_sections_and_runs():
    units = named("Genesis")
    days = [u for u in units if u[0] == "1:1"]
    # Bereshit 1:1 starts the first day; each day ends with a petuḥa, the seventh at 2:3.
    assert days[:2] == [("1:1", "1:5", 1, "petuha"), ("1:1", "1:8", 2, "run")]
    assert ("1:1", "2:3", 7, "run") in days and len(days) == fr.MAX_SECTIONS
    # 2:4 to the petuḥa at 3:21, with setumot after 3:15 and 3:16.
    assert ("2:4", "3:21", 3, "petuha") in units and ("2:4", "3:15", 1, "setuma") in units
    assert ("3:16", "3:16", 1, "setuma") in units and ("2:4", "3:16", 2, "run") in units
    # A petuḥa section is one however many setumot it holds: Devarim's laws.
    assert ("22:6", "25:16", 36, "petuha") in named("Deuteronomy")


def test_bereshit_1_is_framed_by_bara_elohim():
    f = frame("Genesis", "1:1", "2:3", CREATE, GOD)
    assert f["word"] is False and (f["sections"], f["unit"]) == (7, "run")
    # In 4 of the unit's 34 pesuqim (1:1, 1:21, 1:27, 2:3): by chance, the
    # first and the last both among them in 4·3 of the 34·33 ways.
    assert f["chance"] == 4 * 3 / (34 * 33)


def test_the_phrase_frames_follow_the_phrase_settings():
    # ברא אלהים has two content words: with three needed, it isn't a phrase.
    strict = ph.Thresholds(**{**ph.DEFAULTS.__dict__, "content_words": 3})
    assert not [f for f in fr.book_frames("Genesis", thresholds=strict)
                if (f["first"], f["last"]) == ("1:1", "2:3") and words(f) == [CREATE, GOD]]


def test_the_sections_frames_come_first():
    # Eikha 2 opens and closes with בְּיוֹם אַפּוֹ (2:1, 2:22); each camp of
    # Bemidbar 2 with its מַחֲנֵה; Bemidbar 30's vows with what YHWH commanded.
    assert frame("Lamentations", "2:1", "2:22", "3117", "639")["unit"] == "petuha"
    assert frame("Numbers", "2:10", "2:16", "4264", "7205")["unit"] == "setuma"
    assert frame("Numbers", "30:2", "30:17", "6680", "3068")["unit"] == "petuha"
    for book in ("Genesis", "Numbers"):
        units = [f["unit"] for f in fr.book_frames(book)]
        first_run = units.index("run")
        assert first_run > 0 and all(u == "run" for u in units[first_run:])


def test_rare_words_framing_a_unit():
    child = frame("Ruth", "1:1", "4:17", CHILD)  # Naomi's children lost (1:5), then a child (4:16)
    assert child["word"] is True and child["sections"] == 1  # Ruth's first petuḥa is at 4:17
    wind = next(f for f in fr.book_frames("Jonah") if f["word"] and words(f) == [WIND])  # 1:4, 4:8
    assert wind["first"] == "1:1" and wind["last"].startswith("4:")


def test_a_words_chance_is_all_its_places_in_the_ends():
    # Among p pesuqim, m places at random, all in the two ends of e each,
    # some in each: C(2e, m) - 2 C(e, m) of the C(p, m) ways.
    for f in fr.book_frames("Ruth"):
        if f["word"]:
            assert 0 < f["chance"] < 1 and f["score"] < fr.STRENGTH
    p, e, m = 85, 5, 3
    assert (comb(2 * e, m) - 2 * comb(e, m)) / comb(p, m) < comb(2 * e, m) / comb(p, m)


def test_a_book_without_sections_has_no_frames():
    assert fr.book_frames("Psalms") == ()


def pesuqim(book, ch, first, last):
    words = sh._book(book)
    return [{"book": book, "ch": ch, "vs": vs, "pointed": " ".join(w for w, *_ in words[f"{ch}:{vs}"])}
            for vs in range(first, last + 1)]


def test_frames_where_the_passage_touches_their_unit():
    loaded = pesuqim("Genesis", 1, 1, 31) + pesuqim("Genesis", 2, 1, 3)
    out = fr.add_to(ph.passage(loaded), loaded)
    groups = dict(out["sections"]["frame"])
    assert set(groups) == {"runs", "words"}  # (no section here has a phrase's frame)
    bara = next(out["phrases"][i] for i in groups["runs"]
                if out["phrases"][i]["frame"]["first"] == "Bereshit 1:1")
    assert bara["kinds"] == ["frame"] and bara["frame"]["last"] == "Bereshit 2:3"
    assert bara["key"] == f"frame Genesis {CREATE} {GOD}" and bara["frame"]["unit"] == "run"
    assert sorted(v for v, *_ in bara["spans"]) == [0, 33] and bara["places"] == []  # both ends here

    # Only its first day loaded: its other end is a place, to read in its chapter.
    loaded = pesuqim("Genesis", 1, 1, 5)
    out = fr.add_to(ph.passage(loaded), loaded)
    bara = next(p for p in out["phrases"] if "frame" in p["kinds"] and p["frame"]["last"] == "Bereshit 2:3"
                and not p["frame"]["word"])
    assert [v for v, *_ in bara["spans"]] == [0] and [x["ref"] for x in bara["places"]] == ["Bereshit 2:3"]
    # A passage the unit doesn't reach has none of its frames.
    loaded = pesuqim("Genesis", 12, 1, 9)
    out = fr.add_to(ph.passage(loaded), loaded)
    assert all(p["frame"]["first"] != "Bereshit 1:1" for p in out["phrases"] if "frame" in p["kinds"])


def test_a_field_frames_a_unit_in_other_words():
    # Shemot 2:1-22: a marriage opens it and one closes it, in other words
    # (וַיִּקַּח, 2:1; וַיִּתֵּן, 2:21). Its births are one word (וַתֵּלֶד) at
    # both ends: that's a word's frame, not a field's.
    c = ph.corpus()
    found = {f["field"]: f for f in fr.book_frames("Exodus") if f["field"] and f["first"] == "2:1"}
    marry = next(f for code, f in found.items() if se.field_path(code, 4)[-1] == "Marry")
    assert (marry["last"], marry["unit"]) == ("2:22", "petuha") and marry["word"] is False
    opening = {c.lem[t] for t in marry["ends"] if c.where[t][1] == "2:1"}
    closing = {c.lem[t] for t in marry["ends"] if c.where[t][1] == "2:21"}
    assert opening and closing and not opening & closing  # no word at both ends
    assert all(se.field_path(code, 4)[-1] != "Birth" for code in found)


def test_field_frames_are_listed_with_the_words():
    loaded = pesuqim("Exodus", 2, 1, 22)
    out = fr.add_to(ph.passage(loaded), loaded)
    groups = dict(out["sections"]["frame"])
    marry = next(p for p in (out["phrases"][i] for i in groups["fields"]) if "Marry" in p["frame"]["field"])
    assert marry["frame"]["field"].endswith("Association › Marry") and " · " in marry["text"]
    assert len(marry["spans"]) == 2
    # Archived by its words, which a level doesn't change (its field's code does).
    c = ph.corpus()
    ends = [t for t in range(*c.verses[("Exodus", "2:1")]) if c.strong[t] == "3947"]  # וַיִּקַּח
    assert marry["key"].startswith("frame Exodus field ") and "3947" in marry["key"].split() and ends
    assert "001" not in marry["key"].split()[3:]
