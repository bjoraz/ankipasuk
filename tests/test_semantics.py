"""Tests for ankipasuk.semantics_build (OSHB's segments, lining SDBH's places
up with them) and ankipasuk.semantics (the bundled data)."""

import unicodedata

from ankipasuk import semantics as se
from ankipasuk import semantics_build as sb
from ankipasuk.shorashim import _book


def keys(segs):
    return [(s.word, s.key, s.last) for s in segs]


def test_segments_are_counted_as_sdbh_counts_words():
    # וְהָאָרֶץ is three; בָּאָרֶץ too, its article hidden in the preposition;
    # a suffix (אִתָּךְ) is none; a word that's only a preposition is its own.
    segs = sb.segments([("c/d/776", "HC/Td/Ncbsa"), ("b/776", "HRd/Ncbsa"), ("854", "HR/Sp2fs"),
                        ("l", "HR/Sp2ms")])
    assert keys(segs) == [(0, "ו", False), (0, "ה", False), (0, "0776", True),
                          (1, "ב", False), (1, sb.ARTICLE, False), (1, "0776", True),
                          (2, "0854", True), (3, "ל", True)]
    assert sb.strong("H0430") == sb.strong("430") == "0430" and sb.strong("1254 a") == "1254"


def place(n, *codes, letters=()):
    return sb.Place(n, [n], set(codes), set(letters))


def test_places_follow_a_word_split_one_way_here_and_another_there():
    # וַיֹּאמֶר ... לָמָּה חָרָה: OSHB writes ל/מה, SDBH counts לָמָּה as one, so
    # what follows it is a word earlier in SDBH's numbers.
    segs = sb.segments([("c/559", "HC/Vqw3ms"), ("l/4100", "HR/Pi"), ("2734", "HVqp3ms"),
                        ("c/4100", "HC/Pi")])
    places = [place(2, "0559"), place(3, "4100"), place(4, "2734"), place(6, "4100")]
    assert sb.line_up(segs, places) == [1, 3, 4, 6]
    # A place whose number differs (טוֹב, 2895 or 2896) still goes where its
    # neighbours put it; one with no room is left out.
    segs = sb.segments([("7200", "HVqw3ms"), ("2896", "HAamsa"), ("430", "HNcmpa")])
    assert sb.line_up(segs, [place(1, "7200"), place(2, "2895"), place(3, "0430")]) == [0, 1, 2]
    assert sb.line_up(segs, [place(1, "7200"), place(2, "0430"), place(3, "0430")])[0] == 0


def test_reading_sdbh():
    entry = {"Lemma": "רוּחַ", "StrongCodes": ["H7307", "A7308"], "BaseForms": [{"LEXMeanings": [
        {"LEXDomains": [{"DomainCode": "001001001"}], "LEXReferences": ["00100100200028"],
         "LEXSenses": [{"LanguageCode": "en", "Glosses": ["Spirit"],
                        "DefinitionShort": "the spirit of God"}]},
        {"LEXDomains": [{"DomainCode": "001002006001"}], "LEXReferences": ["00100100200028{N:001}"],
         "LEXSenses": [{"LanguageCode": "en", "Glosses": ["breeze", "wind"]}]},
    ]}]}
    out = sb.read_sdbh([entry])
    assert out.table == [["רוּחַ", "Spirit", "the spirit of God", ["001001001"], 0],
                         ["רוּחַ", "breeze, wind", "", ["001002006001"], 0]]
    (p,) = out.places[(1, 1, 2)]
    assert (p.n, p.senses, p.codes, p.letters) == (14, [0, 1], {"7307", "7308"}, {"ר"})


def test_the_bundled_senses_of_bereshit_1():
    words = [w[0] for w in _book("Genesis")["1:1"]]
    senses = se.verse_senses("Genesis", 1, 1)
    assert len(senses) == len(words) == 7
    table = se.senses()
    lemma = {w: [table[s][0] for s in ss] for w, ss in zip(words, senses)}
    nfc = [unicodedata.normalize("NFC", w) for w in ("רֵאשִׁית", "אֶרֶץ")]
    assert lemma["בראשית"] == nfc[:1] and lemma["ברא"] == ["ברא"] and lemma["הארץ"] == nfc[1:]
    (earth,) = senses[6]
    assert [se.domain_path(d) for d in table[earth][3]] == [["Objects", "Natural World", "Land"]]
    assert table[earth][4] > 2000  # its places in the Tanakh
    # 1:2: עַל has none (SDBH hasn't done it); רוּחַ אֱלֹהִים two senses each,
    # the Spirit of God or a mighty wind.
    words = [w[0] for w in _book("Genesis")["1:2"]]
    senses = dict(zip(words, se.verse_senses("Genesis", 1, 2)))
    assert senses["על"] == [] and len(senses["ורוח"]) == 2 and len(senses["אלהים"]) == 2


def test_a_ketiv_and_its_qere_both_have_their_sense():
    words = [w[0] for w in _book("Genesis")["8:17"]]
    senses = se.verse_senses("Genesis", 8, 17)
    assert senses[words.index("הוצא")] == senses[words.index("היצא")] != []


def test_most_words_have_a_sense():
    have = total = 0
    for book in ("Genesis", "Isaiah", "Ruth", "Psalms"):
        for key in _book(book):
            ch, vs = map(int, key.split(":"))
            senses = se.verse_senses(book, ch, vs)
            assert len(senses) == len(_book(book)[key])  # a word each, as the shorashim's
            have += sum(1 for s in senses if s)
            total += len(senses)
    assert have / total > 0.85


def bereshit_1():
    words = _book("Genesis")
    return [{"book": "Genesis", "ch": ch, "vs": vs, "pointed": " ".join(w[0] for w in words[f"{ch}:{vs}"])}
            for ch, last in ((1, 31), (2, 3)) for vs in range(1, last + 1)]


HEAVEN, SHINE, LIQUIDS, WATERBODIES = "001002002", "002001001056", "001002006007", "001002009"


def test_a_passages_fields_at_level_4():
    out = se.passage(bereshit_1())
    heaven = out["fields"][HEAVEN]
    # Heaven is filed at level 3, so at level 4 it stands for itself.
    assert heaven["path"] == ["Objects", "Natural World", "Heaven", "Heaven"] and heaven["label"] == "Heaven"
    assert heaven["count"] == 20 and [w[0] for w in heaven["words"][:2]] == ["שָׁמַיִם", "רָקִיעַ"]
    key = sorted(out["fields"], key=lambda f: -out["fields"][f]["keyness"])
    assert key[:2] == [HEAVEN, SHINE] and out["fields"][SHINE]["ratio"] > 10
    # מַיִם has two domains, so two fields. In 1:1, אֱלֹהִים (Reference) has
    # none, nor אֵת (a particle), unless asked for; in 1:2 it has its other
    # sense's, "mighty" (a mighty wind).
    row = dict(zip([w[0] for w in _book("Genesis")["1:2"]], out["verses"][1]))
    assert row["המים"][0] == [LIQUIDS, WATERBODIES] and row["אלהים"][0] == ["002001003010"]
    words = [w[0] for w in _book("Genesis")["1:1"]]
    first = dict(zip(words, out["verses"][0]))
    assert first["אלהים"][0] == [] and first["אלהים"][1]  # (its senses are still given, for its tooltip)
    assert first["את"][0] == []
    out = se.passage(bereshit_1(), reference=True, particles=True)
    first = dict(zip(words, out["verses"][0]))
    assert first["אלהים"][0] and first["את"][0] == ["002001001023"]  # אֵת: Identify


def test_other_levels_cut_back_or_repeat():
    at3 = se.passage(bereshit_1(), level=3)
    assert at3["level"] == 3 and SHINE[:9] in at3["fields"] and SHINE not in at3["fields"]
    at5 = se.passage(bereshit_1(), level=5)
    assert at5["fields"][HEAVEN]["path"] == ["Objects", "Natural World", "Heaven", "Heaven", "Heaven"]
    assert se.passage(bereshit_1(), level=7)["level"] == se.DEFAULT_LEVEL


def test_how_deep_words_are_filed():
    depth = se.levels()
    assert abs(sum(depth.values()) - 1) < 0.001 and max(depth, key=depth.get) == 4
