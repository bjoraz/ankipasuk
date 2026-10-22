"""Tests for ankipasuk.shorashim_build (OSHB -> groups) and
ankipasuk.shorashim (lining OSHB's words up with Sefaria's text)."""

import pytest

from ankipasuk import shorashim as sh
from ankipasuk.shorashim_build import Grouper, book_words, parse_lexicon, verb_form

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
  <w lemma="b/7225">בְּ/רֵאשִׁ֖ית</w> <w lemma="1254 a" morph="HVqp3ms">בָּרָ֣א</w> <w lemma="853">אֵ֥ת</w>
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


def test_a_verb_carries_its_form(built):
    _grouper, verses = built
    assert verses["1:1"][1][2:] == [0, "p"]  # בָּרָא: not a qere, a qatal
    assert len(verses["1:1"][0]) == 2  # בְּרֵאשִׁית: no verb
    assert [verb_form(m) for m in ("HC/Vqw3ms", "HVqp3ms", "AVqp3ms", "HNcmpa", "HVhv2ms/Sp1cs", "")] == \
        ["w", "p", "p", None, "v", None]


def test_a_qere_follows_its_ketiv_marked(built):
    _grouper, verses = built
    assert [w[0] for w in verses["1:2"]] == ["מימ", "מים", "אברהם", "ראש"]
    assert len(verses["1:2"][0]) == 2 and verses["1:2"][1][2] == 1


def test_a_roots_gloss_is_its_commonest_words(built):
    grouper, _verses = built
    root = next(g for g in grouper.table() if g["label"] == "ראשׁ")
    assert root["gloss"] in ("beginning", "head")
    assert {w for w, _gloss, _meaning in root["words"]} == {"רֵאשִׁית", "רֹאשׁ"}


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
    assert sh.verse_words("Sirach", 1, 1, "אַשְׁרֵי הָאִישׁ") == [["אַשְׁרֵי", " ", None], ["הָאִישׁ", "", None]]


def test_a_lemma_without_its_letter_is_the_numbers_first_sense():
    grouper = Grouper(parse_lexicon(LEXICON))
    # 1254 has "a" (shape) and "b" (be fat); a bare 1254 is "a".
    g = grouper.group_of("1254")
    assert grouper.groups[g].lemmas == {("בָּרָא", "shape", ""): 1}


def test_a_plain_meaning_goes_beside_bdbs_gloss_only_where_it_is_the_one_named():
    from ankipasuk.shorashim_build import MEANINGS

    lexicon = f"""<index {NS}><part>
    <entry id="a"><w>עָשָׂה</w><pos>V</pos><def>do</def><xref strong="6213" aug="a"/>
      <etym root="עשׂה" type="main"/></entry>
    <entry id="b"><w>עָשָׂה</w><pos>V</pos><def>press</def><xref strong="6213" aug="b"/>
      <etym root="עשׂה" type="main"/></entry>
    <entry id="c"><w>יהוה</w><pos>Np</pos><def>Jehovah</def><xref strong="3068"/></entry>
    </part></index>"""
    entries = parse_lexicon(lexicon)
    # BDB's gloss is kept; the plain meaning goes beside it.
    assert MEANINGS[("6213", "do")] == "do, make"
    assert (entries["a"].gloss, entries["a"].meaning) == ("do", "do, make")
    assert (entries["b"].gloss, entries["b"].meaning) == ("press", "")
    assert (entries["c"].gloss, entries["c"].meaning) == ("the Name", "")


def test_homonymous_roots_are_numbered_in_bdbs_order_and_names_merge_by_spelling():
    lexicon = f"""<index {NS}><part>
    <entry id="b"><w>לחם</w><xref bdb="l.ab.aa"/><etym root="לחם" type="main">b2</etym></entry>
    <entry id="b2"><w>מִלְחָמָה</w><pos>N</pos><def>battle</def><xref strong="4421"/>
      <etym type="sub">b</etym></entry>
    <entry id="a"><w>לחם</w><xref bdb="l.aa.aa"/><etym root="לחם" type="main">a2</etym></entry>
    <entry id="a2"><w>לֶחֶם</w><pos>N</pos><def>bread</def><xref strong="3899"/>
      <etym type="sub">a</etym></entry>
    <entry id="p1"><w>עֲזַרְיָה</w><pos>Np</pos><def>Azariah</def><xref strong="5838" aug="a"/></entry>
    <entry id="p2"><w>עֲזַרְיָה</w><pos>Np</pos><def>Azariah</def><xref strong="5838" aug="b"/></entry>
    </part></index>"""
    grouper = Grouper(parse_lexicon(lexicon))
    battle, bread = grouper.group_of("4421"), grouper.group_of("3899")
    one, other = grouper.group_of("5838 a"), grouper.group_of("5838 b")
    table = grouper.table()
    # Listed second, but first in BDB (l.aa before l.ab): bread is לחם I.
    assert (table[bread]["number"], table[battle]["number"]) == (1, 2)
    assert one == other and table[one]["number"] == 0
    assert table[one]["gloss"] == "'Azarya"  # the app's spelling, not "Azariah"


def test_the_rest_of_the_tanakh_is_only_counted(built):
    grouper, _verses = built
    before = len(grouper.groups)
    psalm = f"""<osis {NS}><osisText><div type="book" osisID="Ps"><chapter osisID="Ps.1">
    <verse osisID="Ps.1.1"><w lemma="7218">רֹאשׁ</w> <w lemma="4325">מַיִם</w> <w lemma="1254 b">בָּרָא</w></verse>
    </chapter></div></osisText></osis>"""
    grouper.reference = True
    book_words(psalm, "Ps", grouper)
    table = grouper.table()
    root = next(g for g in table if g["label"] == "ראשׁ")
    water = next(g for g in table if g["label"] == "מַיִם")
    # Totals go up; no new group for בָּרָא "be fat", and no word or gloss changes.
    assert (root["total"], water["total"]) == (3, 3)
    assert len(grouper.groups) == before
    assert {w for w, _gloss, _meaning in root["words"]} == {"רֵאשִׁית", "רֹאשׁ"}
    assert grouper.words == 8 + 3  # בָּרָא "be fat" a word of the Tanakh all the same


def test_key_words_are_those_used_far_more_than_in_the_tanakh():
    # Twelve times in 400 words, where the Tanakh's rate would give 2.
    often = sh.keyness(12, 400, 1500, 300_000)
    once_rare = sh.keyness(1, 400, 10, 300_000)
    as_usual = sh.keyness(2, 400, 1500, 300_000)
    assert often > once_rare > 0
    assert abs(as_usual) < 0.1
    assert sh.keyness(1, 400, 30_000, 300_000) < 0  # אֵת, once: far less than usual
    assert sh.keyness(0, 400, 10, 300_000) == 0 and sh.keyness(5, 400, 5, 400) == 0


def test_the_bundled_data_counts_the_whole_tanakh():
    table = sh.groups()
    assert 300_000 < sh.tanakh_words() < 310_000
    shalom = next(g for g in table if g["kind"] == "root" and g["meaning"] == "peace")
    assert shalom["total"] > 400  # Tehillim and Divre haYamim count too


def test_a_people_is_one_by_the_lexicon_or_by_most_of_its_places():
    from ankipasuk.shorashim_build import peoples

    lexicon = f"""<index {NS}><part>
    <entry id="k"><w>כְּנַעֲנִי</w><pos>N</pos><def>Kenaanite</def><xref strong="3669"/></entry>
    <entry id="h"><w>חִתִּי</w><pos>Ag</pos><def>Hittite</def><xref strong="2850"/></entry>
    <entry id="b"><w>בֵּן</w><pos>N</pos><def>son</def><xref strong="1121"/></entry>
    </part></index>"""
    book = f"""<osis {NS}><osisText><div type="book" osisID="Gen"><chapter osisID="Gen.1">
    <verse osisID="Gen.1.1"><w lemma="d/3669" morph="HTd/Ngmsa">הַ/כְּנַעֲנִי</w>
      <w lemma="3669" morph="HAgmsa">כְּנַעֲנִי</w> <w lemma="3669" morph="HNcmsa">כְּנַעֲנִי</w>
      <w lemma="2850" morph="HNpm">חִתִּי</w> <w lemma="1121" morph="HNgmsa">בֵּן</w>
      <w lemma="1121" morph="HNcmsc">בֶּן</w> <w lemma="1121" morph="HNcmsc">בֶּן</w></verse>
    </chapter></div></osisText></osis>"""
    entries = parse_lexicon(lexicon)
    found = peoples(Grouper(entries), [book])
    assert found == {"k"}  # two places of three; בֵּן only one of three
    grouper = Grouper(entries, found)
    table_of = {w[0]: grouper.table()[w[1]] for w in book_words(book, "Gen", grouper)["1:1"]}
    for word, gloss in (("כנעני", "Kena'ani"), ("חתי", "Ḥitti")):  # the lexicon's noun, and its gentilic
        assert table_of[word]["kind"] == "name" and table_of[word]["people"] is True
        assert table_of[word]["gloss"] == gloss
    assert table_of["בן"]["kind"] == "word" and "people" not in table_of["בן"]
