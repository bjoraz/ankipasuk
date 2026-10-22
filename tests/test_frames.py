"""Tests for ankipasuk.frames: the units, known frames of the bundled
Tanakh, and the frames as the phrase views get them (docs/phrases.md,
Frames)."""

from math import comb

from ankipasuk import frames as fr
from ankipasuk import phrases as ph
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


def test_units_are_runs_of_sections():
    keys = keys_of("Genesis")
    units = fr.units("Genesis", keys)
    days = [(keys[a], keys[b], n) for a, b, n in units if a == 0]
    # Bereshit 1:1 starts the first day; each day ends with a petuḥa, the seventh at 2:3.
    assert days[:2] == [("1:1", "1:5", 1), ("1:1", "1:8", 2)]
    assert ("1:1", "2:3", 7) in days and len(days) == fr.MAX_SECTIONS
    assert all(b >= a for a, b, _n in units)


def test_bereshit_1_is_framed_by_bara_elohim():
    f = frame("Genesis", "1:1", "2:3", CREATE, GOD)
    assert f["word"] is False and f["sections"] == 7
    # In 4 of the unit's 34 pesuqim (1:1, 1:21, 1:27, 2:3): by chance, the
    # first and the last both among them in 4·3 of the 34·33 ways.
    assert f["chance"] == 4 * 3 / (34 * 33)


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
    assert set(groups) == {"phrases", "words"}
    bara = next(out["phrases"][i] for i in groups["phrases"]
                if out["phrases"][i]["frame"]["first"] == "Bereshit 1:1")
    assert bara["kinds"] == ["frame"] and bara["frame"]["last"] == "Bereshit 2:3"
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
