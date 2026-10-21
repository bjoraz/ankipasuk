"""Tests for ankipasuk.transliterate: pointed Hebrew in the app's spelling
(docs/transliteration.md)."""

import pytest

from ankipasuk.transliterate import transliterate

# docs/transliteration.md's parashiyyot, made by hand by the same rules.
PARASHOT = {
    "בְּרֵאשִׁית": "Bereshit", "נֹחַ": "Noaḥ", "וַיֵּרָא": "Vayyera", "תּוֹלְדֹת": "Toledot", "וַיֵּצֵא": "Vayyetse",
    "וַיִּשְׁלַח": "Vayyishlaḥ", "מִקֵּץ": "Miqqets", "וַיְחִי": "Vayḥi", "שְׁמוֹת": "Shemot", "וָאֵרָא": "Va'era",
    "בְּשַׁלַּח": "Beshallaḥ", "יִתְרוֹ": "Yitro", "תְּרוּמָה": "Teruma", "תְּצַוֶּה": "Tetsavve", "וַיִּקְרָא": "Vayyiqra",
    "צַו": "Tsav", "תַזְרִיעַ": "Tazria'", "אַחֲרֵי מוֹת": "Aḥare Mot", "בְּחֻקֹּתַי": "Beḥuqqotai",
    "בְּמִדְבַּר": "Bemidbar", "נָשֹׂא": "Naso", "בְּהַעֲלֹתְךָ": "Beha'alotekha", "חֻקַּת": "Ḥuqqat",
    "פִּינְחָס": "Pineḥas", "מַטּוֹת": "Mattot", "מַסְעֵי": "Mas'e", "וָאֶתְחַנַּן": "Va'etḥannan", "עֵקֶב": "'Eqev",
    "רְאֵה": "Re'e", "שֹׁפְטִים": "Shofetim", "כִּי תֵצֵא": "Ki Tetse", "נִצָּבִים": "Nitsavim",
    "הַאֲזִינוּ": "Ha'azinu", "וְזֹאת הַבְּרָכָה": "Vezot haBerakha",
}

NAMES = {
    "מֹשֶׁה": "Moshe", "יַעֲקֹב": "Ya'aqov", "יִשְׂרָאֵל": "Yisra'el", "אַהֲרֹן": "Aharon",
    "יְהוֹשֻׁעַ": "Yehoshua'",  # furtive pataḥ
    "מִצְרַיִם": "Mitsrayim", "יִשָּׂשכָר": "Yissakhar",  # the unpointed shin isn't read
    "שָׁאוּל": "Sha'ul", "עֵשָׂו": "'Esav", "חַוָּה": "Ḥavva", "אֵלִיָּה": "Eliyya",
    "מׇרְדֳּכַי": "Mordokhai",  # qamats qatan
    "הַמְּדָתָא": "haMedata",  # the article, joined
    "מַחֲנֵה־דָן": "Maḥane Dan",  # maqaf: two words
    "מְנַשֶּׁה": "Menashe",  # sh isn't doubled
    "אֶסְתֵּר": "Ester",  # a dagesh after a sheva naḥ isn't doubling
    "יִרְמְיָהוּ": "Yirmeyahu",  # the second of two shevas is na
    "חֲבַקּוּק": "Ḥavaqquq",
}


@pytest.mark.parametrize("pointed, written", list(PARASHOT.items()))
def test_the_docs_parashiyyot(pointed, written):
    assert transliterate(pointed) == written


@pytest.mark.parametrize("pointed, written", list(NAMES.items()))
def test_names(pointed, written):
    assert transliterate(pointed) == written


def test_an_ordinary_word_isnt_capitalized():
    assert transliterate("תּוֹלְדֹת", name=False) == "toledot"
