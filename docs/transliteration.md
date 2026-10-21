# Transliteration

AnkiPasuk writes every Hebrew word the same way: in the docs, in the app,
on cards, and in the names it generates (the book name in a note's
`Source` field, tags). This page is the rule set, and the full list of
names it produces.

## Rules

**Consonants**

| Letter | Written | Notes |
|---|---|---|
| א | nothing, or `'` | `'` only where it starts a syllable inside a word: Nevi'im, Va'era, Yo'el, Mal'akhi |
| בּ / ב | b / v | |
| ג, ד | g, d | |
| ה | h | a silent final he isn't written (Tora, Teruma); with a mappiq it is (legarmeh) |
| ו | v | as a consonant |
| ז | z | |
| ח | ḥ | |
| ט, ת | t | tav is t with or without a dagesh |
| י | y | |
| כּ / כ | k / kh | |
| ל, מ, נ | l, m, n | |
| ס, שׂ | s | |
| ע | `'` | always, also at the start of a word: 'aliyya, 'Amos, 'Eqev |
| פּ / פ | p / f | |
| צ | ts | |
| ק | q | |
| ר | r | |
| שׁ | sh | |

**Vowels.** Qamats and pataḥ are a; tsere and segol are e; ḥiriq is i;
ḥolam is o; shuruq and qubbuts are u. Tsere followed by yod is still e
(Shene gerishin, Mishle, Pequde). Pataḥ followed by yod is ai
(Beḥuqqotai, Ḥaggai).

**Sheva.** A sheva na is written e; a sheva naḥ isn't written. So pesuqim,
mesharetim, Bemidbar, Shofetim, Beha'alotekha, Toledot, but mafsiq,
Segolta, Yitro. Typical signs of a sheva na: the start of a word, the
second of two shevas, after a long vowel, and under a letter with a dagesh
ḥazaq.

**Dagesh ḥazaq** doubles the letter: Shabbat, Sukkot, Vayyiqra, Miqqets,
'aliyya, 'ammud, niqqud, tiqqun. Three exceptions, for readability:

- a dagesh qal at the start of a word isn't doubling and isn't written;
- the digraphs sh, ts and kh aren't doubled (Nitsavim, not Nittsavim);
- the dagesh that follows the definite article isn't written: the article
  is written `ha` and joined to the next word, which keeps its capital
  (Rosh haShana, 'Aseret haDibberot, Vezot haBerakha).

**Capitals.** Names are capitalized; ordinary words aren't (pasuq,
ta'amim, sefer, parasha, qeriya).

**ASCII form for tags.** Tags and other identifiers use the same spelling,
lowercased, with ḥ written h, apostrophes dropped, and spaces as `_`:
Ḥayye Sara becomes `hayye_sara`, Shemini 'Atseret becomes
`shemini_atseret`.

## Names in the shorashim data

The shorashim lists gloss every name (Moshe, Ya'aqov, Yisra'el, Mitsrayim)
by these rules, worked out from its pointed form by
`ankipasuk.transliterate` rather than written by hand. It spells the
parashiyyot below just as the table does, and its tests hold it to them.
Only the qamats qatan needs the pointing to say so (מׇרְדֳּכַי:
Mordokhai), which BDB's headwords do.

## What isn't transliterated

- English book names where the app uses them as keys and labels (the book
  picker, statistics labels like "Genesis 1:1").
- Names of the ta'amim follow the Sephardi column of the table in
  Wikipedia's [Hebrew cantillation](https://en.wikipedia.org/wiki/Hebrew_cantillation)
  article; see the ranking step in the [README](../README.md).
- Code identifiers (`aliyah_num`, `fetch_parashah_aliyah`, CSS classes,
  JSON keys), Unicode character names, and the names of other projects
  (tikkun.io, `@hebcal/leyning`, AnkiLPCG).
- The note type name "Ankipasuk Aliyah", because renaming it would create a
  second note type next to your existing cards.
- Ashkenazi names given for reference, such as munach legarmeh.

## Judgment calls

These follow the rules but could reasonably be written another way:

- **Pineḥas**: the sheva after the ḥiriq male is treated as na.
- **Shelaḥ Lekha**: the full name, where Sefaria has the short "Sh'lach".
- **Naso**: no dagesh in the sin (נָשֹׂא), so not "Nasso".
- **Pequde**: written as the name is said on its own, with p, although the
  pe is rafe in the verse (אֵלֶּה פְקוּדֵי).
- **Tsom Tammuz** keeps the name the data already used, rather than Shiv'a
  'Asar beTammuz.

## Old and new names

The app gets its parasha list from Sefaria and pairs it with the table
below by position (the same pairing it already uses for the maftir data),
so Sefaria's own spellings never reach the screen. Notes, tags and decks
made with the old names still work: the tagger reads both spellings of a
book name, and `ankipasuk-migrate-tags` (also under **Anki tools**)
renames old tags to the new ones.


### Books

The name written into a note's `Source` field and on card titles.

| Book | Old | New |
|---|---|---|
| Genesis | Bereshit | Bereshit |
| Exodus | Shemot | Shemot |
| Leviticus | Vayikra | Vayyiqra |
| Numbers | Bamidbar | Bemidbar |
| Deuteronomy | Devarim | Devarim |
| Joshua | Yehoshua | Yehoshua' |
| Judges | Shoftim | Shofetim |
| I Samuel | Shmuel Alef | Shemuel Alef |
| II Samuel | Shmuel Bet | Shemuel Bet |
| I Kings | Melachim Alef | Melakhim Alef |
| II Kings | Melachim Bet | Melakhim Bet |
| Isaiah | Yeshayahu | Yesha'yahu |
| Jeremiah | Yirmiyahu | Yirmeyahu |
| Ezekiel | Yechezkel | Yeḥezqel |
| Hosea | Hoshea | Hoshea' |
| Joel | Yoel | Yo'el |
| Amos | Amos | 'Amos |
| Obadiah | Ovadiah | 'Ovadya |
| Jonah | Yonah | Yona |
| Micah | Michah | Mikha |
| Nahum | Nachum | Naḥum |
| Habakkuk | Chavakuk | Ḥavaqquq |
| Zephaniah | Tzefaniah | Tsefanya |
| Haggai | Chaggai | Ḥaggai |
| Zechariah | Zechariah | Zekharya |
| Malachi | Malachi | Mal'akhi |
| Song of Songs | Shir HaShirim | Shir haShirim |
| Ruth | Rut | Rut |
| Lamentations | Eichah | Ekha |
| Ecclesiastes | Kohelet | Qohelet |
| Esther | Esther | Ester |

### Parashiyyot

Tags use the new slug, numbered by position in the book: `aliyya::<book>::<NN>-<slug>::<1-7|maftir>`.

| Book | # | Name | Slug | Old slug |
|---|---|---|---|---|
| Genesis | 01 | Bereshit | `bereshit` | same |
| Genesis | 02 | Noaḥ | `noah` | same |
| Genesis | 03 | Lekh Lekha | `lekh_lekha` | same |
| Genesis | 04 | Vayyera | `vayyera` | `vayera` |
| Genesis | 05 | Ḥayye Sara | `hayye_sara` | `haye_sara` |
| Genesis | 06 | Toledot | `toledot` | same |
| Genesis | 07 | Vayyetse | `vayyetse` | `vayetze` |
| Genesis | 08 | Vayyishlaḥ | `vayyishlah` | `vayishlah` |
| Genesis | 09 | Vayyeshev | `vayyeshev` | `vayeshev` |
| Genesis | 10 | Miqqets | `miqqets` | `miketz` |
| Genesis | 11 | Vayyiggash | `vayyiggash` | `vayigash` |
| Genesis | 12 | Vayḥi | `vayhi` | same |
| Exodus | 01 | Shemot | `shemot` | same |
| Exodus | 02 | Va'era | `vaera` | same |
| Exodus | 03 | Bo | `bo` | same |
| Exodus | 04 | Beshallaḥ | `beshallah` | `beshalach` |
| Exodus | 05 | Yitro | `yitro` | same |
| Exodus | 06 | Mishpatim | `mishpatim` | same |
| Exodus | 07 | Teruma | `teruma` | `terumah` |
| Exodus | 08 | Tetsavve | `tetsavve` | `tetzaveh` |
| Exodus | 09 | Ki Tissa | `ki_tissa` | `ki_tisa` |
| Exodus | 10 | Vayyaqhel | `vayyaqhel` | `vayakhel` |
| Exodus | 11 | Pequde | `pequde` | `pekudei` |
| Leviticus | 01 | Vayyiqra | `vayyiqra` | `vayikra` |
| Leviticus | 02 | Tsav | `tsav` | `tzav` |
| Leviticus | 03 | Shemini | `shemini` | `shmini` |
| Leviticus | 04 | Tazria' | `tazria` | same |
| Leviticus | 05 | Metsora' | `metsora` | `metzora` |
| Leviticus | 06 | Aḥare Mot | `ahare_mot` | `achrei_mot` |
| Leviticus | 07 | Qedoshim | `qedoshim` | `kedoshim` |
| Leviticus | 08 | Emor | `emor` | same |
| Leviticus | 09 | Behar | `behar` | same |
| Leviticus | 10 | Beḥuqqotai | `behuqqotai` | `bechukotai` |
| Numbers | 01 | Bemidbar | `bemidbar` | `bamidbar` |
| Numbers | 02 | Naso | `naso` | `nasso` |
| Numbers | 03 | Beha'alotekha | `behaalotekha` | `behaalotcha` |
| Numbers | 04 | Shelaḥ Lekha | `shelah_lekha` | `shlach` |
| Numbers | 05 | Qoraḥ | `qorah` | `korach` |
| Numbers | 06 | Ḥuqqat | `huqqat` | `chukat` |
| Numbers | 07 | Balaq | `balaq` | `balak` |
| Numbers | 08 | Pineḥas | `pinehas` | `pinchas` |
| Numbers | 09 | Mattot | `mattot` | `matot` |
| Numbers | 10 | Mas'e | `mase` | `masei` |
| Deuteronomy | 01 | Devarim | `devarim` | same |
| Deuteronomy | 02 | Va'etḥannan | `vaethannan` | `vaetchanan` |
| Deuteronomy | 03 | 'Eqev | `eqev` | `eikev` |
| Deuteronomy | 04 | Re'e | `ree` | `reeh` |
| Deuteronomy | 05 | Shofetim | `shofetim` | `shoftim` |
| Deuteronomy | 06 | Ki Tetse | `ki_tetse` | `ki_teitzei` |
| Deuteronomy | 07 | Ki Tavo | `ki_tavo` | same |
| Deuteronomy | 08 | Nitsavim | `nitsavim` | `nitzavim` |
| Deuteronomy | 09 | Vayyelekh | `vayyelekh` | `vayeilech` |
| Deuteronomy | 10 | Ha'azinu | `haazinu` | same |
| Deuteronomy | 11 | Vezot haBerakha | `vezot_haberakha` | `vezot_haberakhah` |

### Holiday and fast-day readings

Tags: `holiday::<slug>::<1-N|maftir>`.

| Name | Slug | Old slug |
|---|---|---|
| Rosh haShana I | `rosh_hashana_i` | same |
| Rosh haShana II | `rosh_hashana_ii` | same |
| Yom Kippur | `yom_kippur` | same |
| Yom Kippur Minḥa | `yom_kippur_minha` | `yom_kippur_mincha` |
| Sukkot I | `sukkot_i` | same |
| Sukkot II | `sukkot_ii` | same |
| Sukkot Ḥol haMo'ed Day 1 | `sukkot_hol_hamoed_day_1` | `sukkot_chol_ha_moed_day_1` |
| Sukkot Ḥol haMo'ed Day 2 | `sukkot_hol_hamoed_day_2` | `sukkot_chol_ha_moed_day_2` |
| Sukkot Ḥol haMo'ed Day 3 | `sukkot_hol_hamoed_day_3` | `sukkot_chol_ha_moed_day_3` |
| Sukkot Ḥol haMo'ed Day 4 | `sukkot_hol_hamoed_day_4` | `sukkot_chol_ha_moed_day_4` |
| Sukkot Ḥol haMo'ed Day 5 | `sukkot_hol_hamoed_day_5` | `sukkot_chol_ha_moed_day_5` |
| Hosha'na Rabba | `hoshana_rabba` | `sukkot_final_day_hoshana_raba` |
| Shemini 'Atseret | `shemini_atseret` | `shmini_atzeret` |
| Simḥat Tora | `simhat_tora` | `simchat_torah` |
| Pesaḥ I | `pesah_i` | `pesach_i` |
| Pesaḥ II | `pesah_ii` | `pesach_ii` |
| Pesaḥ Ḥol haMo'ed Day 1 | `pesah_hol_hamoed_day_1` | `pesach_chol_ha_moed_day_1` |
| Pesaḥ Ḥol haMo'ed Day 2 | `pesah_hol_hamoed_day_2` | `pesach_chol_ha_moed_day_2` |
| Pesaḥ Ḥol haMo'ed Day 3 | `pesah_hol_hamoed_day_3` | `pesach_chol_ha_moed_day_3` |
| Pesaḥ Ḥol haMo'ed Day 4 | `pesah_hol_hamoed_day_4` | `pesach_chol_ha_moed_day_4` |
| Pesaḥ VII | `pesah_vii` | `pesach_vii` |
| Pesaḥ VIII | `pesah_viii` | `pesach_viii` |
| Shavu'ot I | `shavuot_i` | same |
| Shavu'ot II | `shavuot_ii` | same |
| Ḥanukka Day 1 | `hanukka_day_1` | `chanukah_day_1` |
| Ḥanukka Day 2 | `hanukka_day_2` | `chanukah_day_2` |
| Ḥanukka Day 3 | `hanukka_day_3` | `chanukah_day_3` |
| Ḥanukka Day 4 | `hanukka_day_4` | `chanukah_day_4` |
| Ḥanukka Day 5 | `hanukka_day_5` | `chanukah_day_5` |
| Ḥanukka Day 6 | `hanukka_day_6` | `chanukah_day_6` |
| Ḥanukka Day 7 | `hanukka_day_7` | `chanukah_day_7` |
| Ḥanukka Day 8 | `hanukka_day_8` | `chanukah_day_8` |
| Rosh Ḥodesh | `rosh_hodesh` | `rosh_chodesh` |
| Purim | `purim` | same |
| Shushan Purim | `shushan_purim` | same |
| Ta'anit Ester | `taanit_ester` | `taanit_esther` |
| Shabbat Sheqalim | `shabbat_sheqalim` | `shabbat_shekalim` |
| Shabbat Zakhor | `shabbat_zakhor` | `shabbat_zachor` |
| Shabbat Para | `shabbat_para` | `shabbat_parah` |
| Shabbat haḤodesh | `shabbat_hahodesh` | `shabbat_hachodesh` |
| Tsom Gedalya | `tsom_gedalya` | `tzom_gedaliah` |
| 'Asara beTevet | `asara_betevet` | `asara_btevet` |
| Tsom Tammuz | `tsom_tammuz` | `tzom_tammuz` |
| Tish'a beAv | `tisha_beav` | `tisha_bav` |
| Tish'a beAv Minḥa | `tisha_beav_minha` | `tisha_bav_mincha` |
| Yom ha'Atsma'ut | `yom_haatsmaut` | `yom_haatzmaut` |

### Tags

| Tag | Old | New |
|---|---|---|
| weekly reading | `aliyah::bereshit::05-haye_sara::3` | `aliyya::bereshit::05-hayye_sara::3` |
| holiday reading | `holiday::simchat_torah::1` | `holiday::simhat_tora::1` |
| tiqqun cards, 'aliyya export | `ankipasuk-aliyah`, `parasha::Chayei-Sara` | `ankipasuk-aliyya`, `parasha::hayye_sara` |
| tiqqun cards, 'ammud export | `amud::012` | `ammud::012` |
