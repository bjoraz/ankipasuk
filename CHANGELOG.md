# Changelog

## Unreleased

### Changed

- Phrases follow the ta'amim's division: a phrase that crosses a sof
  pasuq, an etnaḥta or a king (segolta, shalshelet, zaqef, tifḥa) starts
  and ends on breaks at most one step weaker (an etnaḥta, a king, a
  duke). Before, it only had to contain one whole unit, and could begin
  or end anywhere in the next: ויהי ערב ויהי בקר יום is now ויהי ערב ויהי
  בקר, and ויהי דבר יהוה אלי לאמר no longer runs on into בן אדם, while
  מארץ מצרים מבית עבדים stays whole. The phrase data now records the
  dukes.
- A picked phrase's underline takes the palette's colours in click order
  again, as the shorashim do, without skipping theirs (0.2.0's change).

### Fixed

- Trimming a phrase's end could leave it crossing a break it no longer
  stood on.
- A two-word name (בית לחם) took the break after it from its first word,
  not its last.

## 0.2.0 — 2026-10-21

The app now studies the text as well as making cards: the shorashim and
the recurring phrases of whatever is loaded.

### Added

- **Shorashim** in the Text view: click a word to colour every word of its
  root, with the passage's roots listed beside the text, their glosses,
  and a **Key words** order (the roots the passage uses far more than the
  Tanakh does). Homonymous roots are numbered; names and peoples are told
  apart. Data from the Open Scriptures Hebrew Bible, bundled.
- **Phrases**: the passage's refrains, echoes of other places in the
  Tanakh, and idioms, with formulas set apart (`docs/phrases.md`). Pick a
  phrase to underline it and step through its occurrences (‹ 2/6 ›); open
  an echo's other place in its whole chapter. Each section shows its 12
  strongest, with Show all. **Settings…** in the pane sets the tests'
  thresholds.
- **Diagrams** in Joshua Jacobson's style for every pasuq, and the diagram
  view saved as PDF or HTML pages, with a preview.
- **Tiqqun cards** laid out as in the sefer (tikkun.io), by 'ammud, as CSV
  or straight to Anki, and 'ammudim as HTML or PDF pages; hovering a word
  on the answer side shows its pointing.
- **Haftarot**, ranges from one 'aliyya to another, the Nevi'im and the
  five Megillot, and several ranges at once.
- **Cloze cards straight to Anki** through AnkiConnect, adding only
  pesuqim that have no note yet.
- **Statistics**: diagrams for the most common structures, and Shorashim
  and Phrases tabs.
- **Linux support**: the web view's backend is detected, and the README
  says what to install.
- One transliteration throughout (`docs/transliteration.md`), and **Migrate
  Tags** to rename tags in the old spelling.
- Browser tests of the app's pages, in Chromium and WebKit, in CI.

### Changed

- The main window: tabs for the two kinds of card, numbered steps beside a
  live preview, and a settings column that folds away.
- A failed fetch says what went wrong in words (couldn't reach Sefaria,
  check the connection), not the network library's error.
- The tkinter interface, replaced by the web view since August, is
  removed.

### Fixed

- God's name counted as a person's name in the phrase formulas, hiding
  phrases like בית יהוה.
- The window didn't start where the web view has no storage.
- The maftir could be cut short by a stale verse count; rapid cache writes
  crashed on Windows; large decks timed out in the Anki tools.

## 0.1.0 — 2026-08-30

The first version: nested cloze cards split along the ta'amim, from
Sefaria's text, in a tkinter window.
