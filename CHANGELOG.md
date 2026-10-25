# Changelog

## Unreleased

More ways of studying the text: where things are in the passage, its
Masoretic sections, its verb forms, the frames of a book's sections, and
each word's meaning.

### Added

- **Semantic fields**, a new pane in the Text view: each word's sense and
  domain in the Semantic Dictionary of Biblical Hebrew (the UBS open
  release, CC BY-SA 4.0, bundled and lined up with OSHB's words; see
  `docs/semantics.md`). The passage's fields, the most used or the key
  ones first; click one, or a word, to colour its words, a word in two
  coloured fields striped. All words are compared at one level of the
  tree, 4 by default or 3 or 5 in **Field settings**. Names and particles
  only when ticked. A word's tooltip gives its senses.
- **Verb forms**, a new pane: the passage's verbs by form (wayyiqtol,
  qatal, yiqtol, weqatal, …), in seven groups or all eleven, counted,
  drawn as a strip of the passage, and coloured in the text; each form
  explained on hover.
- **Frames** (*inclusio*), a fifth tab in Phrases: the book's Masoretic
  sections that open and close with the same phrase, a single section or
  a petuḥa section first, then runs of sections (ברא אלהים, Bereshit
  1:1–2:3). Rare words found only at a unit's two ends, and rare semantic
  fields said in other words at either end, are listed as candidates,
  folded. Each frame has its chance.
- **Masoretic sections** in the Text view: פ or ס after a pasuq that ends
  a petuḥa or a setuma, and a gap; inside a pasuq where the break is
  there. From Sefaria's *Miqra according to the Masorah*, bundled; the
  Decalogue and Eikha 1–4 count as one section each.
- **An archive for phrases**: archive a phrase or frame that's wrong or
  not needed now, and it's left out of every passage until you restore it
  from **Archive**, below the list. The statistics window shares it.
- **Where it is**: a coloured shoresh or field, or a picked phrase, shows
  a strip of where it is in the passage; click it to go there.
- **Verse numbers** before each pasuq in the Text view and in the phrase
  viewer's chapter.
- **Letters only** in the Diagram view, and in its PDF/HTML export: the
  bare letters, and the brackets without their ta'amim's names.

### Changed

- The Text view's side panel has four panes: Shorashim, Phrases, Verbs
  and Fields.
- A picked phrase moves to the top of its section, as a coloured shoresh
  does. A section's groups (the formula classes, the frames' kinds) fold
  by their header, and stay folded or open.

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
