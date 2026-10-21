"""Tests for ankipasuk.shorashim_build (OSHB -> groups) and
ankipasuk.shorashim (lining OSHB's words up with Sefaria's text)."""

import pytest

from ankipasuk import shorashim as sh
from ankipasuk.shorashim_build import Grouper, book_words, parse_lexicon

NS = 'xmlns="http://openscriptures.github.com/morphhb/namespace"'

# A lexicon in LexicalIndex.xml's shape: a root (ראשׁ) with a word filed
# under it, a verb that is its own root, homographs told apart by letter,
# a particle, a name derived from a root, and a noun with no root.
LEXICON = f"""<index {NS}><part>
<entry id="r1"><w>ראשׁ</w><xref bdb="x"/><etym root="ראשׁ" type="main">r2, r3</etym></entry>
<entry id="r2"><w>רֹאשׁ</w><pos>N</pos><def>head</def><xref strong="7218"/><etym type="sub">r1</etym></entry>
<entry id="r3"><w>רֵאשִׁית</w><pos>N</pos><def>beginning</def><xref strong="7225"/>
  <etym type="sub">r1</etym></entry>
<entry id="v1"><w>בָּרָא</w><pos>V</pos><def>shape</def><xref strong="1254" aug="a"/>
  <etym root="ברא" type="main"/></entry>
<entry id="v2"><w>בָּרָא</w><pos>V</pos><def>be fat</def><xref strong="1254" aug="b"/>
  <etym root="ברא" type="main"/></entry>
<entry id="p1"><w>אֵת</w><pos>T</pos><def>mark of the accusative</def><xref strong="853"/>
  <etym type="sub">r1</etym></entry>
<entry id="n1"><w>אַבְרָהָם</w><pos>Np</pos><def>Abraham</def><xref strong="85"/>
  <etym type="sub">r1</etym></entry>
<entry id="w1"><w>מַיִם</w><pos>N</pos><def>water</def><xref strong="4325"/></entry>
</part></index>"""

BOOK = f"""<osis {NS}><osisText><div type="book" osisID="Gen"><chapter osisID="Gen.1">
<verse osisID="Gen.1.1">
  <w lemma="b/7225">בְּ/רֵאשִׁ֖ית</w> <w lemma="1254 a">בָּרָ֣א</w> <w lemma="853">אֵ֥ת</w>
  <w lemma="l">לָ֑/כֶם</w>
</verse>
<verse osisID="Gen.1.2">
  <w type="x-ketiv" lemma="4325">מימ</w><note type="variant"><catchWord>מימ</catchWord>
  <rdg type="x-qere"><w lemma="4325">מַ֣יִם</w></rdg></note> <w lemma="85">אַבְרָהָ֔ם</w> <w lemma="7218">רֹ֖אשׁ</w>
</verse>
</chapter></div></osisText></osis>"""


@pytest.fixture
def built():
    grouper = Grouper(parse_lexicon(LEXICON))
    verses = book_words(BOOK, "Gen", grouper)
    return grouper, verses


def test_words_under_a_root_share_it_and_particles_names_and_rootless_words_stay_themselves(built):
    grouper, verses = built
    table = grouper.table()
    first, second = verses["1:1"], verses["1:2"]
    by_letters = {w[0]: table[w[1]] for w in first + second}
    assert by_letters["בראשית"]["label"] == "ראשׁ" and by_letters["בראשית"]["kind"] == "root"
    assert by_letters["ראש"] is by_letters["בראשית"]  # רֹאשׁ, filed under the same root
    assert by_letters["ברא"]["gloss"] == "shape"  # 1254 a, not b
    assert by_letters["את"]["kind"] == "particle"  # not BDB's אות
    assert by_letters["אברהם"]["kind"] == "name" and by_letters["אברהם"]["label"] == "אַבְרָהָם"
    assert by_letters["מים"]["kind"] == "word" and by_letters["מים"]["gloss"] == "water"
    assert by_letters["לכם"]["kind"] == "particle" and by_letters["לכם"]["label"] == "לְ"


def test_a_qere_follows_its_ketiv_marked(built):
    _grouper, verses = built
    assert [w[0] for w in verses["1:2"]] == ["מימ", "מים", "אברהם", "ראש"]
    assert len(verses["1:2"][0]) == 2 and verses["1:2"][1][2] == 1


def test_a_roots_gloss_is_its_commonest_words(built):
    grouper, _verses = built
    root = next(g for g in grouper.table() if g["label"] == "ראשׁ")
    assert root["gloss"] in ("beginning", "head")
    assert {w for w, _gloss in root["words"]} == {"רֵאשִׁית", "רֹאשׁ"}


def test_pieces_split_at_spaces_and_maqaf():
    assert sh.pieces("עַל־פְּנֵי תְהוֹם׃") == [["עַל", "־"], ["פְּנֵי", " "], ["תְהוֹם׃", ""]]


def test_same_words_line_up_one_to_one_even_spelled_differently():
    oshb = [["הבהמה", 1], ["הטהורה", 2]]
    assert sh.align(["הבהמה", "הטהרה"], oshb) == [1, 2]


def test_ketiv_and_qere_line_up_with_sefarias_two_words():
    oshb = [["על", 1], ["הוצא", 2], ["היצא", 2, 1], ["אתך", 3]]
    assert sh.align(["על", "הוצא", "היצא", "אתך"], oshb) == [1, 2, 2, 3]
    # A text with only the ketiv drops OSHB's qere.
    assert sh.align(["על", "הוצא", "אתך"], oshb) == [1, 2, 3]


def test_a_token_without_letters_gets_nothing_and_unmatched_words_get_nothing():
    assert sh.align(["ויקרא", "", "אלהים"], [["ויקרא", 5], ["אלהים", 6]]) == [5, None, 6]
    assert sh.align(["אב", "גד", "הו"], [["אב", 1], ["זח", 2]]) == [1, None, None]


def test_a_chapter_divided_differently_is_lined_up_as_a_whole(monkeypatch):
    # OSHB puts the third word in pasuq 1; Sefaria in pasuq 2.
    monkeypatch.setattr(sh, "_book", lambda book: {
        "20:1": [["אנכי", 1], ["יהוה", 2], ["אלהיך", 3]], "20:2": [["לא", 4], ["יהיה", 5]],
    })
    monkeypatch.setattr(sh, "groups", lambda: [{"label": str(i), "kind": "word", "gloss": "", "words": []}
                                               for i in range(6)])
    data = [{"book": "Exodus", "ch": 20, "vs": 1, "pointed": "אָנֹכִי יְהוָה"},
            {"book": "Exodus", "ch": 20, "vs": 2, "pointed": "אֱלֹהֶיךָ לֹא יִהְיֶה"}]
    out = sh.passage(data)
    assert [[w[2] for w in v] for v in out["verses"]] == [[1, 2], [3, 4, 5]]
    assert out["groups"][3]["verses"] == ["Exodus 20:2"]


def test_a_root_is_shown_letter_by_letter_without_final_forms():
    assert sh.display({"kind": "root", "label": "שׁנה"}) == "שׁ־נ־ה"
    assert sh.display({"kind": "root", "label": "בן"}) == "ב־נ"
    assert sh.display({"kind": "name", "label": "אַבְרָהָם"}) == "אַבְרָהָם"


def test_the_bundled_data_knows_bereshit_1_1():
    pointed = "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"
    words = sh.verse_words("Genesis", 1, 1, pointed)
    table = sh.groups()
    shown = [sh.display(table[g]) for _t, _s, g in words]
    assert shown == ["ר־א־שׁ", "ב־ר־א", "א־ל־ה", "אֵת", "שׁ־מ־ה", "אֵת", "א־ר־צ"]
    assert table[words[3][2]]["kind"] == "particle"


def test_a_book_without_data_just_has_its_words():
    assert sh.verse_words("Psalms", 1, 1, "אַשְׁרֵי הָאִישׁ") == [["אַשְׁרֵי", " ", None], ["הָאִישׁ", "", None]]


def test_a_lemma_without_its_letter_is_the_numbers_first_sense():
    grouper = Grouper(parse_lexicon(LEXICON))
    # 1254 has "a" (shape) and "b" (be fat); a bare 1254 is "a".
    g = grouper.group_of("1254")
    assert grouper.groups[g].lemmas == {("בָּרָא", "shape"): 1}


def test_misleading_glosses_are_replaced_only_where_they_are_the_one_named():
    from ankipasuk.shorashim_build import GLOSS_FIXES

    lexicon = f"""<index {NS}><part>
    <entry id="a"><w>עָשָׂה</w><pos>V</pos><def>do</def><xref strong="6213" aug="a"/>
      <etym root="עשׂה" type="main"/></entry>
    <entry id="b"><w>עָשָׂה</w><pos>V</pos><def>press</def><xref strong="6213" aug="b"/>
      <etym root="עשׂה" type="main"/></entry>
    <entry id="c"><w>יהוה</w><pos>Np</pos><def>Jehovah</def><xref strong="3068"/></entry>
    </part></index>"""
    entries = parse_lexicon(lexicon)
    assert GLOSS_FIXES[("6213", "do")] == entries["a"].gloss == "do, make"
    assert entries["b"].gloss == "press"
    assert entries["c"].gloss == "the Name"
