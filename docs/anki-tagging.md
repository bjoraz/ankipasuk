# Automatic parasha / aliyah / Maftir / holiday tagging

Tags every note in a deck with where its verse falls in the annual Torah
reading cycle: which parasha and aliyah (1-7), whether it's part of the
weekly Maftir, and whether it's also read on a holiday or fast day.

## Tag scheme

```
aliyah::<hebrew-book>::<NN-parasha-slug>::<1-7|maftir>
holiday::<holiday-slug>::<1-N|maftir>
```

For example: `aliyah::bereshit::01-bereshit::1`, `aliyah::shemot::01-shemot::maftir`,
`holiday::rosh_hashana_i::1`. A verse can carry more than one tag -- e.g.
Genesis 22:1 is both `aliyah::bereshit::04-vayera::7` (the regular weekly
reading) and `holiday::rosh_hashana_ii::1` (also read on Rosh Hashana II).

The `aliyah::` scheme matches what was already being applied by hand to
this deck before this tool existed. The `holiday::` scheme is new,
introduced by this tool (there was no existing precedent to match) --
edit the `slug` field in `ankipasuk/data/holiday_readings.json` before
running if you'd prefer different names, since it's simplest to change
before the tags exist.

## Requirements

- [Anki](https://apps.ankiweb.net/) running locally, with the
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
  installed (default: `http://127.0.0.1:8765`).
- Each note's **Source** field must look like `"Bereshit 1:1"` (Hebrew book
  name + chapter:verse), which is what the main app's CSV export already
  produces.
- Network access to Sefaria for the aliyah 1-7 boundaries and per-chapter
  verse counts (see below) -- cached locally after the first fetch, same
  as the rest of the app. The first time you tag a book you haven't
  already fetched verses from (via the main app's Chapter/Verse or
  Parashah/Aliyah modes), this means fetching every chapter of that book
  once to get accurate verse counts -- a one-time cost per book, not per
  run.

## Running it

- **From the GUI** -- launch `ankipasuk` (or `python -m ankipasuk`), then
  **AnkiConnect Tools → Tag Deck**.
- **Double-click the script**:
  ```powershell
  python .\scripts\tag_deck.py
  ```
- **The installed console command**:
  ```bash
  ankipasuk-tag-deck "Leyning" --dry-run   # preview
  ankipasuk-tag-deck "Leyning"             # apply
  ```

Point it at the whole `Leyning` deck (or a sub-deck) -- every note in it is
checked regardless of which book/parasha it's in. **Always dry-run first**;
the dry-run shows exactly which tags would be added to which notes, with
no changes made.

**This tool only ever adds tags. It never removes or changes an existing
one.** If a note already has an `aliyah::...` or `holiday::...` tag that
doesn't match what was just computed, that's reported as a `CONFLICT` line
instead of being silently changed -- review those by hand. Everything else
about the note (unrelated tags, scheduling, flags) is left untouched. This
makes it safe to run repeatedly (re-running adds nothing new) and safe to
run on a deck that already has some tags applied by hand, like this one.

## Why aliyah boundaries come from Sefaria, not a bundled table

The weekly aliyah 1-7 verse ranges are fetched live from the same Sefaria
`Parasha` structure the rest of the app already uses (and caches locally --
see `ankipasuk.cache.SefariaCache`). This guarantees they use the *exact
same* chapter/verse numbering as the verse text itself, with zero risk of
a mismatch between data sources.

Maftir length (a verse *count*, e.g. "4") and the holiday/fast-day reading
table come from a small bundled data file instead, derived from the
[`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning) package --
see `THIRD_PARTY_NOTICES.md`. Maftir is deliberately expressed as a count
rather than an absolute reference, then walked backward from the live
aliyah-7 boundary to get the actual range -- and that backward walk itself
uses **live-fetched per-chapter verse counts**
(`ankipasuk.sefaria.get_chapter_lengths`), not a static table, specifically
because Genesis 31/32 has a well-known chapter-numbering discrepancy
between different textual traditions (which verse is the last of chapter
31 versus the first of chapter 32), and a hardcoded verse-count table can
drift out of sync with what Sefaria's text currently has at exactly that
kind of boundary -- which happened in practice and silently shifted
Maftir (and everything downstream in the book, e.g. Vayishlach) by one
verse. Deriving the counts live, cached afterward the same as everything
else, eliminates that entire class of bug rather than requiring the count
to be manually kept in sync.

This was all validated during development against a real, partially
hand-tagged deck: reconstructing "Sefaria-shaped" aliyah refs from the
existing hand-applied tags and confirming all 568 tagged (verse, tag)
pairs -- including the Genesis 31/32 case -- were reproduced exactly. See
`tests/test_leyning.py` for the same logic in a self-contained form, and
its `test_chapter_counts_override_changes_verse_index` /
`test_compute_maftir_range_uses_chapter_counts_override` tests
specifically for the live-vs-static-table behavior.

## Scope and limitations of the holiday/fast-day table

Torah readings for holidays and fast days aren't tied to a specific
calendar year -- the same verses are read every year, just on different
dates -- so, like the weekly aliyot, this is tagged on a static, per-verse
basis rather than requiring any calendar computation.

The bundled table covers one representative, non-year-dependent reading
per occasion: Rosh Hashana (2 days), Yom Kippur (+ Mincha), Sukkot (2 days,
5 days Chol HaMoed, Hoshana Raba), Shmini Atzeret, Simchat Torah, Pesach
(2 days, 4 days Chol HaMoed, VII, VIII), Shavuot (2 days), Chanukah (8
days), Rosh Chodesh, Purim, Shushan Purim, Ta'anit Esther, the 4 special
Shabbatot (Shekalim, Zachor, Parah, HaChodesh), the minor fasts (Tzom
Gedaliah, Asara B'Tevet, Tzom Tammuz) and Tisha B'Av (+ Mincha), and Yom
HaAtzma'ut.

Deliberately **not** included: the many liturgical variants for how a
reading changes when it coincides with Shabbat, a different Chol HaMoed
day of the week, or another holiday (e.g. "Chanukah Day 7 (on Rosh
Chodesh)"). These represent alternate *aliyah splits* of the same
underlying verses, not new verse coverage, so skipping them doesn't lose
any tagging -- they'd just make the tag scheme more elaborate for little
benefit in a personal study deck.

Unlike the weekly aliyot, this portion is **not** cross-validated against
live Sefaria data (there's no existing precedent in the deck to check it
against, since no holiday tags existed before this tool). It comes
directly from Hebcal's static table. If precision matters to you, spot
check a few holiday tags against Sefaria after running.
