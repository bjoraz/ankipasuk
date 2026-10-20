# Tagging notes by where they're read

This tool tags every note in a deck with where its pasuq falls in the
yearly qeriya cycle: its parasha and 'aliyya (1 to 7), whether it's part of
that week's maftir, and any holiday or fast-day reading it belongs to. A
pasuq from the Nevi'im is tagged with the haftarot it's read in.

## The tags

```
aliyya::<book>::<NN-parasha>::<1-7|maftir>
holiday::<occasion>::<1-N|maftir>
haftara::<parasha or occasion>
```

For example `aliyya::bereshit::01-bereshit::1`,
`aliyya::shemot::01-shemot::maftir` or `holiday::rosh_hashana_i::1`. The
number before the parasha is its position within its book. A pasuq can
have more than one tag: Bereshit 22:1 gets `aliyya::bereshit::04-vayyera::7`
from the weekly reading and `holiday::rosh_hashana_ii::1` because it's
also read on the second day of Rosh haShana. Yirmeyahu 1:5 gets both
`haftara::shemot` and `haftara::mattot`; the haftarot follow the Spanish
and Portuguese custom (`src/ankipasuk/data/haftarot.json`).

Book, parasha and occasion names are written the ASCII way described in
[`transliteration.md`](transliteration.md), which also lists every one of
them. If you'd rather name the occasions differently, edit the `slug`
fields in `src/ankipasuk/data/holiday_readings.json` before your first
run; it's much easier than renaming tags afterwards.

## Tags in the old spelling

Earlier versions wrote these tags differently (`aliyah::bereshit::05-haye_sara::3`,
`holiday::simchat_torah::1`, and so on). If your deck has them, rename them
before tagging:

- **From the app:** **Anki tools → Migrate Tags**.
- **As a script:** `python .\scripts\migrate_tags.py`
- **As a command:**
  ```bash
  ankipasuk-migrate-tags "Qeriya" --dry-run   # preview
  ankipasuk-migrate-tags "Qeriya"             # apply
  ```

It only renames tags AnkiPasuk itself made, adds each new tag before
removing the old one, and changes nothing else. It also renames the tags
on tiqqun cards (`ankipasuk-aliyah`, `amud::012`, `parasha::...`). If you
tag before migrating, nothing breaks: the old tags show up as conflicts,
with a reminder to migrate, and the new ones are added next to them.

Notes keep working either way: the tagger reads the book name in a note's
**Source** field in either spelling (`Bamidbar 3:5` or `Bemidbar 3:5`).

## What you need

- Anki running on the same machine, with the
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
  (`http://127.0.0.1:8765` by default).
- A **Source** field on each note holding the reference, like
  `Bereshit 1:1`. The cloze CSV export already writes it that way.
- Network access to Sefaria, for the 'aliyya divisions and the number of
  pesuqim in each chapter. Both are cached after the first fetch. The
  first time you tag a book you haven't fetched from before, that means
  downloading each of its chapters once.

## Running it

- **From the app:** **Anki tools → Tag Deck**.
- **As a script:**
  ```powershell
  python .\scripts\tag_deck.py
  ```
- **As a command:**
  ```bash
  ankipasuk-tag-deck "Qeriya" --dry-run   # preview
  ankipasuk-tag-deck "Qeriya"             # apply
  ```

Point it at the whole deck or any sub-deck; every note in it is checked,
whatever book or parasha it's from. Do a dry run first. It lists exactly
which tags would go on which notes and changes nothing.

**It only ever adds tags.** It never removes or edits one. If a note
already has an `aliyah::` or `holiday::` tag that doesn't match what was
worked out, you get a `CONFLICT` line in the log and the note is left as it
is for you to look at. Everything else about the note (other tags,
scheduling, flags) is untouched. That makes it safe to run again and again,
and safe on a deck you've partly tagged by hand.

## Where the divisions come from

The weekly 'aliyyot come live from Sefaria's parasha divisions, the same
source the rest of the app uses for the text (and cached the same way).
That way the 'aliyya boundaries and the pesuqim are always numbered the same
way, with no second source to fall out of step.

Two things Sefaria doesn't give come from a small bundled table taken from
[`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning) (see
`THIRD_PARTY_NOTICES.md`): how many pesuqim each maftir has, and the
holiday and fast-day readings.

The maftir is stored as a count ("the last 4 pesuqim"), not a fixed
reference, and is counted back from the end of the seventh 'aliyya. The
count-back uses the number of pesuqim in each chapter as Sefaria has them
right now, not a table built into the code. This matters at Bereshit 31/32,
where editions disagree on whether וַיַּשְׁכֵּם לָבָן closes chapter 31 or
opens chapter 32. A fixed table that disagreed with Sefaria on that one
pasuq once shifted the maftir of Vayyetse, and everything after it in the
book, by one pasuq. Reading the counts from Sefaria removes that whole kind
of mismatch.

All of this was checked against a real, partly hand-tagged deck: rebuilding
the 'aliyya ranges from the tags already in it reproduced all 568 tagged
(pasuq, tag) pairs exactly, including the Bereshit 31/32 case.
`tests/test_qeriya.py` covers the same logic on its own, and
`test_chapter_counts_override_changes_verse_index` and
`test_compute_maftir_range_uses_chapter_counts_override` cover the live
chapter counts in particular.

## Holidays and fasts

Holiday readings don't depend on the year (the same pesuqim are read every
time, just on different dates), so like the weekly 'aliyyot they're tagged
per pasuq with no calendar involved.

The table has one standard reading for each of these: Rosh haShana (both
days), Yom Kippur (morning and Minḥa), Sukkot (the first two days, the five
days of Ḥol haMo'ed, and Hosha'na Rabba), Shemini 'Atseret, Simḥat Tora,
Pesaḥ (the first two days, the four days of Ḥol haMo'ed, and the seventh
and eighth days), Shavu'ot (both days), the eight days of Ḥanukka, Rosh
Ḥodesh, Purim, Shushan Purim, Ta'anit Ester, the four parashiyyot (Sheqalim,
Zakhor, Para, haḤodesh), Tsom Gedalya, 'Asara beTevet, Shiv'a 'Asar
beTammuz, Tish'a beAv (morning and Minḥa), and Yom ha'Atsma'ut.

What's left out on purpose are the variants for when an occasion falls on
Shabbat, on a different day of Ḥol haMo'ed, or together with another
occasion (Ḥanukka on Rosh Ḥodesh, for instance). Those divide the same
pesuqim into 'aliyyot differently but don't add any new pesuqim, so leaving
them out costs no coverage and keeps the tags simple.

Unlike the weekly 'aliyyot, the holiday table hasn't been checked against
Sefaria or an existing deck, since there were no holiday tags to compare
with. It comes straight from Hebcal's table. If it matters to you, spot
check a few holiday tags after running.
