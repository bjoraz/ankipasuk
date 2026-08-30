# Sephardic transliteration convention

Every Hebrew proper noun the app generates -- book names, parasha/aliyah/
Maftir tag slugs, and holiday-reading names -- follows a strict Sephardic
transliteration convention, applied consistently everywhere. This document
records the exact rule set and the full resulting table, so it's auditable
and correctable rather than buried in code.

## The rules

**Consonants**

| Letter | Value | Notes |
|---|---|---|
| Alef | (no symbol) | Silent; contributes no letter, only its vowel. |
| Bet | b / v | Depending on dagesh. |
| Gimel | g | |
| Dalet | d | |
| He | h | Final He is dropped unless it carries a mappiq. |
| Vav | v | (as a consonant) |
| Zayin | z | |
| Het | ḥ | |
| Tet | t | |
| Yod | y | |
| Kaf | k | (with dagesh) |
| Khaf | kh | (without dagesh) |
| Lamed | l | |
| Mem | m | |
| Nun | n | |
| Samekh | s | |
| Ayin | ’ | e.g. Shema’, ma’ariv |
| Pe | p / f | Depending on pronunciation. |
| Tsadi | ts | |
| Qof | q | |
| Resh | r | |
| Shin/Sin | sh / s | By the dot's position. |
| Tav | t | (th only if a community keeps that distinction -- not used here) |

Dagesh hazak (gemination) is written as a doubled letter (e.g. Shabbat,
Kippur, Sukkot). This is applied where it's clearly, unambiguously marked
and well attested (the examples above) but not exhaustively re-derived
for every prefix consonant across all 54 parasha names -- see "Scope and
judgment calls" below.

**Vowels**

| Niqud | Value |
|---|---|
| Patach | a |
| Kamats | a |
| Tsere | e |
| Segol | e |
| Hiriq | i |
| Holam | o |
| Shuruk | u |
| Kubuts | u |
| Sheva na (vocal) | e (e.g. Berakhah) |
| Sheva nah (silent) | (not transliterated) |
| Diphthong | ai |

## Where this applies

- `ankipasuk.config.BOOK_HEBREW_NAMES` -- the 5 Torah book names, used in
  CSV export verse labels and as the tag prefix's second segment
  (`aliyah::<book>::...`).
- `ankipasuk/data/parashot.json` -- every parasha's `slug` and
  `display_name`.
- `ankipasuk/data/holiday_readings.json` -- every holiday/fast-day
  reading's `slug` and `display_name`.

Everything downstream (tag construction in `leyning.py`, the GUI's CSV
export) reads these as data, so there's no separate transliteration logic
to keep in sync elsewhere.

## Backward compatibility with this deck

Your deck already has notes whose Source field (e.g. "Bamidbar 3:5") was
written with the previous spelling and is fixed as static text -- changing
the convention going forward can't rewrite that. So:

- `ankipasuk.config.LEGACY_BOOK_HEBREW_NAMES` keeps the old book-name
  spellings, and `ankipasuk.anki_connect.tagging.HEBREW_TO_BOOK` accepts
  either spelling when parsing a note's Source field -- old notes still
  get read and tagged correctly.
- Every entry in `parashot.json` and `holiday_readings.json` keeps a
  `legacy_slug` field recording its previous slug, purely for reference/
  traceability -- it isn't read by any code path.
- New output (CSV export labels, computed tag strings) always uses the
  current Sephardic spelling.

This means re-running the tagging tool on notes that already have your
hand-applied `aliyah::...` tags (which used the old spelling) will report
them all as conflicts, since the old tag text no longer matches what's
computed. That's the tool behaving correctly (see
[`docs/anki-tagging.md`](anki-tagging.md)) -- it won't silently rewrite
them. You'll want to either bulk-delete the old-spelling tags first (Anki's
Find & Replace on tags, or the browser's tag list) or accept the conflict
list and reconcile by hand.

## Scope and judgment calls

A few things worth knowing about how this was derived:

- Gemination (dagesh hazak) is not exhaustively doubled. Distinguishing a
  "strengthening" dagesh from a true gemination dagesh requires
  morphological analysis word-by-word (e.g. is the dagesh in Vayigash's
  Gimel, from an assimilated Nun, meant to be audible?). This was applied
  for the clear, canonical cases (Shabbat, Kippur, Sukkot, Tammuz) but not
  re-litigated for every parasha name, to avoid guessing at gemination
  that would look unusual without a specific source to check it against.
- Sheva na/nah requires knowing syllable structure, not just the niqud
  mark itself. This was determined per-word from the standard
  pronunciation, but a few are genuinely closer calls than others --
  flagged individually below.
- Two specific words are worth double-checking against your own practice:
  - **Beha'alotkha** (Numbers): the sheva under Tav (the letter before the
    final -kha) was treated as silent. Some traditions vocalize it as
    "Beha'alotekha".
  - **Ree** (Deuteronomy, Re'eh): Alef takes no symbol and the final He
    has no mappiq, so the literal result of the rules is "Ree" (both
    letters vanish, leaving the vowels to run together). Many
    transliteration conventions write "Re'e" or "Reeh" here for
    readability even when otherwise following similar rules.
- Holiday/fast-day names got the same substitution rules but weren't
  individually cross-checked against a second source the way the weekly
  parasha names were (see `docs/anki-tagging.md` for the corresponding
  scope note on that data).

If anything here doesn't match your own practice, both data files are
plain, readable JSON -- edit the `slug` and `display_name` fields directly.

## Full table

"Legacy" is the spelling used before this change (and still recognized
when reading existing notes -- see above). "New" is what the app generates
going forward.

### Parashot

| # | Legacy | New slug | Display |
|---|---|---|---|
| **Genesis** | | | |
| 01 | `bereshit` | `bereshit` | Bereshit |
| 02 | `noah` | `noaḥ` | Noaḥ ⟵ *changed* |
| 03 | `lekh_lekha` | `lekh_lekha` | Lekh Lekha |
| 04 | `vayera` | `vayera` | Vayera |
| 05 | `haye_sara` | `ḥayei_sara` | Ḥayei Sara ⟵ *changed* |
| 06 | `toledot` | `toledot` | Toledot |
| 07 | `vayetze` | `vayetse` | Vayetse ⟵ *changed* |
| 08 | `vayishlah` | `vayishlaḥ` | Vayishlaḥ ⟵ *changed* |
| 09 | `vayeshev` | `vayeshev` | Vayeshev |
| 10 | `miketz` | `miqets` | Miqets ⟵ *changed* |
| 11 | `vayigash` | `vayigash` | Vayigash |
| 12 | `vayhi` | `vayḥi` | Vayḥi ⟵ *changed* |
| **Exodus** | | | |
| 01 | `shemot` | `shemot` | Shemot |
| 02 | `vaera` | `vaera` | Vaera |
| 03 | `bo` | `bo` | Bo |
| 04 | `beshalach` | `beshalaḥ` | Beshalaḥ ⟵ *changed* |
| 05 | `yitro` | `yitro` | Yitro |
| 06 | `mishpatim` | `mishpatim` | Mishpatim |
| 07 | `terumah` | `teruma` | Teruma ⟵ *changed* |
| 08 | `tetzaveh` | `tetsave` | Tetsave ⟵ *changed* |
| 09 | `ki_tisa` | `ki_tisa` | Ki Tisa |
| 10 | `vayakhel` | `vayaqhel` | Vayaqhel ⟵ *changed* |
| 11 | `pekudei` | `pequdei` | Pequdei ⟵ *changed* |
| **Leviticus** | | | |
| 01 | `vayikra` | `vayiqra` | Vayiqra ⟵ *changed* |
| 02 | `tzav` | `tsav` | Tsav ⟵ *changed* |
| 03 | `shmini` | `shemini` | Shemini ⟵ *changed* |
| 04 | `tazria` | `tazria’` | Tazria’ ⟵ *changed* |
| 05 | `metzora` | `metsora’` | Metsora’ ⟵ *changed* |
| 06 | `achrei_mot` | `aḥarei_mot` | Aḥarei Mot ⟵ *changed* |
| 07 | `kedoshim` | `qedoshim` | Qedoshim ⟵ *changed* |
| 08 | `emor` | `emor` | Emor |
| 09 | `behar` | `behar` | Behar |
| 10 | `bechukotai` | `beḥuqotai` | Beḥuqotai ⟵ *changed* |
| **Numbers** | | | |
| 01 | `bamidbar` | `bemidbar` | Bemidbar ⟵ *changed* |
| 02 | `nasso` | `naso` | Naso ⟵ *changed* |
| 03 | `behaalotcha` | `beha’alotkha` | Beha’alotkha ⟵ *changed* |
| 04 | `shlach` | `shelaḥ` | Shelaḥ ⟵ *changed* |
| 05 | `korach` | `qoraḥ` | Qoraḥ ⟵ *changed* |
| 06 | `chukat` | `ḥuqat` | Ḥuqat ⟵ *changed* |
| 07 | `balak` | `balaq` | Balaq ⟵ *changed* |
| 08 | `pinchas` | `pinḥas` | Pinḥas ⟵ *changed* |
| 09 | `matot` | `matot` | Matot |
| 10 | `masei` | `mas’ei` | Mas’ei ⟵ *changed* |
| **Deuteronomy** | | | |
| 01 | `devarim` | `devarim` | Devarim |
| 02 | `vaetchanan` | `vaetḥanan` | Vaetḥanan ⟵ *changed* |
| 03 | `eikev` | `’eqev` | ’Eqev ⟵ *changed* |
| 04 | `reeh` | `ree` | Ree ⟵ *changed* |
| 05 | `shoftim` | `shoftim` | Shoftim |
| 06 | `ki_teitzei` | `ki_tetse` | Ki Tetse ⟵ *changed* |
| 07 | `ki_tavo` | `ki_tavo` | Ki Tavo |
| 08 | `nitzavim` | `nitsavim` | Nitsavim ⟵ *changed* |
| 09 | `vayeilech` | `vayelekh` | Vayelekh ⟵ *changed* |
| 10 | `haazinu` | `haazinu` | Haazinu |
| 11 | `vezot_haberakhah` | `vezot_haberakha` | Vezot Haberakha ⟵ *changed* |

### Holiday / fast-day readings

| Legacy | New slug | Display |
|---|---|---|
| `rosh_hashana_i` | `rosh_hashana_i` | Rosh Hashana I |
| `rosh_hashana_ii` | `rosh_hashana_ii` | Rosh Hashana II |
| `yom_kippur` | `yom_kippur` | Yom Kippur |
| `yom_kippur_mincha` | `yom_kippur_minḥa` | Yom Kippur (Minḥa) ⟵ *changed* |
| `sukkot_i` | `sukkot_i` | Sukkot I |
| `sukkot_ii` | `sukkot_ii` | Sukkot II |
| `sukkot_chol_ha_moed_day_1` | `sukkot_ḥol_hamoed_day_1` | Sukkot Ḥol HaMoed Day 1 ⟵ *changed* |
| `sukkot_chol_ha_moed_day_2` | `sukkot_ḥol_hamoed_day_2` | Sukkot Ḥol HaMoed Day 2 ⟵ *changed* |
| `sukkot_chol_ha_moed_day_3` | `sukkot_ḥol_hamoed_day_3` | Sukkot Ḥol HaMoed Day 3 ⟵ *changed* |
| `sukkot_chol_ha_moed_day_4` | `sukkot_ḥol_hamoed_day_4` | Sukkot Ḥol HaMoed Day 4 ⟵ *changed* |
| `sukkot_chol_ha_moed_day_5` | `sukkot_ḥol_hamoed_day_5` | Sukkot Ḥol HaMoed Day 5 ⟵ *changed* |
| `sukkot_final_day_hoshana_raba` | `sukkot_final_day_hoshana_raba` | Sukkot Final Day (Hoshana Raba) |
| `shmini_atzeret` | `shemini_atseret` | Shemini ’Atseret ⟵ *changed* |
| `simchat_torah` | `simḥat_tora` | Simḥat Tora ⟵ *changed* |
| `pesach_i` | `pesaḥ_i` | Pesaḥ I ⟵ *changed* |
| `pesach_ii` | `pesaḥ_ii` | Pesaḥ II ⟵ *changed* |
| `pesach_chol_ha_moed_day_1` | `pesaḥ_ḥol_hamoed_day_1` | Pesaḥ Ḥol HaMoed Day 1 ⟵ *changed* |
| `pesach_chol_ha_moed_day_2` | `pesaḥ_ḥol_hamoed_day_2` | Pesaḥ Ḥol HaMoed Day 2 ⟵ *changed* |
| `pesach_chol_ha_moed_day_3` | `pesaḥ_ḥol_hamoed_day_3` | Pesaḥ Ḥol HaMoed Day 3 ⟵ *changed* |
| `pesach_chol_ha_moed_day_4` | `pesaḥ_ḥol_hamoed_day_4` | Pesaḥ Ḥol HaMoed Day 4 ⟵ *changed* |
| `pesach_vii` | `pesaḥ_vii` | Pesaḥ VII ⟵ *changed* |
| `pesach_viii` | `pesaḥ_viii` | Pesaḥ VIII ⟵ *changed* |
| `shavuot_i` | `shavu’ot_i` | Shavu’ot I ⟵ *changed* |
| `shavuot_ii` | `shavu’ot_ii` | Shavu’ot II ⟵ *changed* |
| `chanukah_day_1` | `ḥanukka_day_1` | Ḥanukka Day 1 ⟵ *changed* |
| `chanukah_day_2` | `ḥanukka_day_2` | Ḥanukka Day 2 ⟵ *changed* |
| `chanukah_day_3` | `ḥanukka_day_3` | Ḥanukka Day 3 ⟵ *changed* |
| `chanukah_day_4` | `ḥanukka_day_4` | Ḥanukka Day 4 ⟵ *changed* |
| `chanukah_day_5` | `ḥanukka_day_5` | Ḥanukka Day 5 ⟵ *changed* |
| `chanukah_day_6` | `ḥanukka_day_6` | Ḥanukka Day 6 ⟵ *changed* |
| `chanukah_day_7` | `ḥanukka_day_7` | Ḥanukka Day 7 ⟵ *changed* |
| `chanukah_day_8` | `ḥanukka_day_8` | Ḥanukka Day 8 ⟵ *changed* |
| `rosh_chodesh` | `rosh_ḥodesh` | Rosh Ḥodesh ⟵ *changed* |
| `purim` | `purim` | Purim |
| `shushan_purim` | `shushan_purim` | Shushan Purim |
| `taanit_esther` | `ta’anit_ester` | Ta’anit Ester ⟵ *changed* |
| `shabbat_shekalim` | `shabbat_sheqalim` | Shabbat Sheqalim ⟵ *changed* |
| `shabbat_zachor` | `shabbat_zakhor` | Shabbat Zakhor ⟵ *changed* |
| `shabbat_parah` | `shabbat_para` | Shabbat Para ⟵ *changed* |
| `shabbat_hachodesh` | `shabbat_haḥodesh` | Shabbat Haḥodesh ⟵ *changed* |
| `tzom_gedaliah` | `tsom_gedalya` | Tsom Gedalya ⟵ *changed* |
| `asara_btevet` | `’asara_betevet` | ’Asara BeTevet ⟵ *changed* |
| `tzom_tammuz` | `tsom_tammuz` | Tsom Tammuz ⟵ *changed* |
| `tisha_bav` | `tish’a_beav` | Tish’a BeAv ⟵ *changed* |
| `tisha_bav_mincha` | `tish’a_beav_minḥa` | Tish’a BeAv (Minḥa) ⟵ *changed* |
| `yom_haatzmaut` | `yom_ha’atsmaut` | Yom Ha’atsmaut ⟵ *changed* |

