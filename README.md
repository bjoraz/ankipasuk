# AnkiPasuk

AnkiPasuk makes [Anki](https://apps.ankiweb.net/) cards for learning to read
from the Sefer Tora. It takes the text and te'amim from
[Sefaria](https://www.sefaria.org/) and gives you two kinds of cards:

- **Nested cloze cards** that take each pasuq apart along its own te'amim:
  first into its two halves, then each half into its clauses, down to the
  smallest phrases the mafsiqim allow. The hidden part shows only its bare
  letters, the way it's written in the scroll, and you supply the reading.
- **Recitation cards** laid out line for line as in a kasher Sefer Tora,
  so what you memorize has the same shape as the scroll you'll read from.

There's also a statistics window for whatever range you've loaded
(including a way to find pesuqim that share the same te'amim structure),
and a few optional tools that work on your Anki collection directly.

## The structure algorithm

This is what drives the cloze cards. Here it is step by step, with Bereshit
1:2 as the example.

### 1. Rank each word by its ta'am

Every mafsiq has a rank, following the usual four classes (keisarim,
melakhim, mishnim, shalishim):

| Rank | Te'amim |
|---|---|
| 1 | Sof pasuq, Atnaḥ |
| 2 | Segolta, Shalshelet, Zaqef qaton, Zaqef gadol, Tarḥa |
| 3 | Ravia', Qadma, Zarqa, Yetiv, Tevir |
| 4 | Gerish, Shene gerishin, Pazer gadol, Talsha, Paseq |
| 0 | the meshartim: Shofar holekh, Ma'arikh, Shofar mehuppakh, Azla, Darga, Tarsa |

A word takes the rank of the strongest ta'am on it. The vertical stroke
after a shofar holekh needs one extra rule, since the same sign can be
part of a mafsiq or just a pause:

| Shofar holekh + stroke | Read as | Rank | Ashkenazi name |
|---|---|---|---|
| next mafsiq is rank 3 | paseq, a mafsiq | 4 | munach legarmeh |
| anywhere else | a meshares with a pause | 0 | munach pasek |

The next mafsiq is usually a ravia', but any rank-3 mafsiq counts. That
follows Joshua Jacobson's *Chanting the Hebrew Bible*, which has rare cases
before the other rank-3 te'amim. In the code the plain stroke is labeled
"Pesiq" to keep it apart from paseq. That label is AnkiPasuk's own, not an
established Sephardi term, and it's never shown in the app.

The names follow the table in Wikipedia's
[Hebrew cantillation](https://en.wikipedia.org/wiki/Hebrew_cantillation)
article. If you work with the Unicode characters directly, go by the
codepoint rather than Unicode's character name, which often differs: Qadma
here is U+0599 (Unicode calls it PASHTA), Azla is U+05A8 (Unicode's QADMA),
Atnaḥ is U+0591 (ETNAHTA), and so on. Unicode also has the names of zarqa
and tsinnorit the wrong way round: zarqa is U+05AE (named ZINOR) and
tsinnorit is U+0598 (named ZARQA). Sefaria's text uses that encoding, and so
does AnkiPasuk. `TROPE_UNICODE` in `config.py` has the full mapping.

### 2. Group meshartim with the mafsiq they lead into

Each run of meshartim joins the mafsiq that ends it. These groups are the
smallest units the te'amim let you cut the pasuq into. Bereshit 1:2 has
eight:

| | Group | Ends with | Rank |
|---|---|---|---|
| 1 | וְהָאָ֗רֶץ | Ravia' | 3 |
| 2 | הָיְתָ֥ה תֹ֨הוּ֙ | Qadma | 3 |
| 3 | וָבֹ֔הוּ | Zaqef qaton | 2 |
| 4 | וְחֹ֖שֶׁךְ | Tarḥa | 2 |
| 5 | עַל־פְּנֵ֣י תְה֑וֹם | Atnaḥ | 1 |
| 6 | וְר֣וּחַ אֱלֹהִ֔ים | Zaqef qaton | 2 |
| 7 | מְרַחֶ֖פֶת | Tarḥa | 2 |
| 8 | עַל־פְּנֵ֥י הַמָּֽיִם׃ | Sof pasuq | 1 |

### 3. Split, then split again

Within any stretch of text, find the strongest mafsiq other than the one
that closes the stretch, and cut right after it. If that rank shows up more
than once, cut after the first one, since the earlier of two equal
mafsiqim is the bigger pause. Then do the same to each half.

You stop when a piece has at most *N* groups left. *N* is the **Max
disjunctive groups per leaf** setting in the app (default 2). With *N* = 1
you get the complete division, down to single groups. A higher *N* leaves
longer phrases intact and gives you fewer, harder cards.

For Bereshit 1:2 the atnaḥ on תְה֑וֹם splits the pasuq. In the first half,
the zaqef on וָבֹ֔הוּ outranks the tarḥa after it. In the piece before
that, ravia' and qadma are both rank 3, so the cut comes after the ravia'.
The second half splits at the zaqef on אֱלֹהִ֔ים.

### 4. Turn the tree into clozes

Every piece of the tree, at every level, becomes its own cloze. They're
numbered children first, so the smallest clauses get the low numbers and
the whole pasuq is always the last one. At the default setting Bereshit 1:2
gives nine cards:

```
c9  והארץ היתה תהו ובהו וחשך על פני תהום ורוח אלהים מרחפת על פני המים
c5  ├─ והארץ היתה תהו ובהו וחשך על פני תהום
c3  │  ├─ והארץ היתה תהו ובהו
c1  │  │  ├─ והארץ
c2  │  │  └─ היתה תהו ובהו
c4  │  └─ וחשך על פני תהום
c8  └─ ורוח אלהים מרחפת על פני המים
c6     ├─ ורוח אלהים
c7     └─ מרחפת על פני המים
```

Each cloze is written as `{{cN::pointed text::unpointed text}}`, so the
hint Anki shows in the gap is the same words without niqqud or te'amim,
just as they look in the scroll. On card c1 you see the rest of the pasuq
fully pointed and have to read וְהָאָ֗רֶץ from its letters. On c9 you get
the letters of the whole pasuq and nothing else. Nested clozes need Anki
2.1.56 or newer.

### Pesuqim with the same shape

Run the split with *N* = 1 and replace each leaf with the rank of the
mafsiq that closes it. What's left is a signature of the pasuq's structure
that can be compared across pesuqim:

- Bereshit 1:1: `((L2 L1) (L2 L1))`
- Bereshit 1:2: `(((L3 (L3 L2)) (L2 L1)) (L2 (L2 L1)))`

The **Structure** tab of the statistics window groups every pasuq you've
loaded by this signature (by word count, by number of groups, or just the
most common shapes first). Click a shape to see the pesuqim that have it.
It's a quick way to see which patterns keep coming back in a parasha you're
preparing, or to practice one awkward pattern across several pesuqim. The
signature is independent of whatever *N* you use for your cards.

### Built from separate pieces

Each step above is one small function with no knowledge of the GUI, Anki,
or the network, so you can use them directly:

```python
from ankipasuk.cloze import verse_to_nested_cloze
from ankipasuk.structure import format_structure, verse_structure_signature

markup, last_cloze, tree, words, groups = verse_to_nested_cloze(pasuq, max_leaf_disj=2)
format_structure(verse_structure_signature(pasuq))  # '(((L3 (L3 L2)) (L2 L1)) (L2 (L2 L1)))'
```

- The rank table is plain data (`TROPE_UNICODE` in `config.py`).
- Ranking and paseq, grouping, and splitting are separate functions in
  `text_processing.py` (`tokenize_pasuk`, `group_into_units`,
  `split_segment`). The choice of where to cut lives in a single function,
  `choose_split_index`, and the stopping point is the one `max_leaf_disj`
  parameter.
- The tree that comes out is reused everywhere: for the cloze markup
  (`cloze.py`), the indented, colored view in the main window, the clause
  and depth counts in the statistics, and the structure signatures
  (`structure.py`).
- The Anki scheduling tool (below) relies on exactly one property of the
  output, that the whole pasuq is always the highest-numbered cloze, and on
  nothing else.

Tehillim, Mishle and Iyov aren't supported, because the Sifrei Emet use a
different system of te'amim.

## Recitation cards

The second kind of card is for the qeriya itself. Choose a range of
'aliyot (or a single 'amud, 1 to 245) and AnkiPasuk sends the cards
straight to Anki through the AnkiConnect add-on.

Every card is drawn from [tikkun.io](https://github.com/akivajgordon/tikkun.io)'s
layout data. Lines break where they do in the standard 245-'amud layout
and are justified edge to edge, petuḥot and setumot appear as real gaps
(Az Yashir and the 'Aseret haDibberot included), and the font is the same
Shlomo semiStam that tikkun.io uses. The font is copied into Anki's media
folder, so the cards work offline.

You can divide the cards two ways:

**By pasuq** (the default). One card per pasuq, showing the line before it
for context and asking for the pasuq's own lines. Pesuqim rarely start and
end on a line break, and tikkun.io's data doesn't say where in a line one
pasuq stops and the next starts. AnkiPasuk works it out by lining up the
words on the scroll against Sefaria's word count for each pasuq, so every
card tests that pasuq's words and nothing more:

- On a line shared with the previous pasuq, its end is shown as ordinary
  text.
- On a line shared with the next pasuq, its opening words are covered by a
  gray bar on both sides of the card, so this card doesn't give away the
  next one.
- A pasuq that runs over onto the next 'amud gets a visible "['Amud N]"
  divider where the column changes.

The alignment also works backwards. If the first pasuq you asked for starts
in the middle of a line, it steps back to the last petuḥa (the last point
where nothing earlier can spill onto the line) and aligns from there, so a
stray word from before your range can't throw off every card after it.

**By line.** The overlapping-window method from the
[AnkiLPCG](https://github.com/sobjornstad/AnkiLPCG) add-on: a few lines of
context, then recite the next line (or lines). Context size, recite size
and grouping can all be set. This is an independent reimplementation; you
don't need AnkiLPCG installed.

Both kinds use the same note type, "Ankipasuk Aliyah", which is created the
first time you export. Each card has small controls in the corner for text
size, line spacing and width (A−/A+, ≡−/≡+, ↔−/↔+). Whatever you set there
applies to every card.

The same layout is in the main window too: tick **Tikkun.io scroll layout**
to see the range you fetched as it appears in the scroll, with or without
niqqud.

## Statistics

**Corpus statistics** opens a window on whatever is loaded: words per
pasuq, groups per pasuq, how many clauses and how deep the split goes at
your current *N*, words per group, averages by chapter, how often each
mafsiq occurs, and the structure groupings described above. Click any bar
or row to see the pesuqim behind it. There's also a per-pasuq CSV export.

## Tools that work on your Anki collection (optional)

These need Anki open with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on. Open them
from **AnkiConnect Tools** in the app, run them as commands
(`ankipasuk-check-connection`, `ankipasuk-init-stems`,
`ankipasuk-sync-scheduling`, `ankipasuk-tag-deck`), or double-click the
scripts in `scripts/`.

- **Retire clause cards once you know the pasuq.** After a one-time step
  that flags each note's full-pasuq card, a sync suspends the clause cards
  on any note whose full-pasuq interval has reached 21 days (you can change
  this). If the full pasuq lapses, they're unsuspended and marked Again,
  so you drill them alongside it until it's back up. Details in
  [`docs/anki-scheduling.md`](docs/anki-scheduling.md).
- **Tag notes by where they're read.** Each note is tagged with its parasha
  and 'aliya, whether it's in the maftir, and any holiday or fast-day
  reading it belongs to, for example `aliyah::bereshit::04-vayera::7` and
  `holiday::rosh_hashana_ii::1`. It only ever adds tags. If an existing tag
  disagrees with what it worked out, that's reported and left alone.
  Details in [`docs/anki-tagging.md`](docs/anki-tagging.md).

Every tool has a dry-run mode. Use it first.

## Installing

You need Python 3.10 or newer.

```bash
git clone https://github.com/bjoraz/ankipasuk.git
cd ankipasuk
pip install -e .
ankipasuk            # or: python -m ankipasuk
```

The app window uses [pywebview](https://pywebview.flowrl.com/), which
draws with the system's own web engine (WebView2 on Windows, WebKit on
macOS). On Linux it also needs GTK or Qt bindings; see pywebview's install
notes.

## Using the app

1. Add one or more ranges, by chapter and verse or by parasha and 'aliya,
   from the Tora, Nevi'im or the five Megillot, then click **Fetch all
   ranges**. Ranges are joined in the order you add them, so you can run
   the end of one book into the start of the next.
2. Set **Max disjunctive groups per leaf** and click **Generate cloze
   cards**. You'll see the cloze markup, the groups for each pasuq, and
   each pasuq's tree drawn as indented, colored rows.
3. Click **Export to CSV** and import the file into Anki. It's
   tab-separated with one row per pasuq: a running number, the reference
   (e.g. `Bereshit 1:1`), the cloze text, the unpointed pasuq, the
   unpointed pesuqim before and after it, then an empty column and a fixed
   settings string. The tagging tool looks for the reference in a field
   called `Source`.
4. For recitation cards, use the panel at the bottom: book, first and last
   parasha and 'aliya (or an 'amud number), deck name, and how to divide
   the cards.

**Reset cloze numbering for each line** is on by default, so each pasuq
starts again at c1 and becomes its own note. Turn it off if you'd rather
keep counting across the whole range.

### Cache

Nothing is downloaded twice. Sefaria text, parasha divisions, and
tikkun.io's pages and font are all kept on disk:

- Linux and macOS: `~/.cache/ankipasuk/` (or `$XDG_CACHE_HOME/ankipasuk/`)
- Windows: `%APPDATA%\AnkiPasuk\`
- Anywhere else, if you set `ANKIPASUK_CACHE_DIR`

**Clear cache** in the main window empties it. Your own settings (the last
deck name you used, in `settings.json`, and the layout controls, in
`webview_storage/`) live in the same folder and aren't touched by it.

## Code layout

```
src/ankipasuk/
├── config.py            rank table, book lists, Tora verse counts
├── text_processing.py   ranking, paseq, grouping, splitting
├── cloze.py             tree → nested cloze markup, structure signature
├── structure.py         grouping pesuqim by structure
├── stats.py             statistics for a loaded range
├── qeriya.py            parasha / 'aliya / maftir / holiday tag logic
├── sefaria.py           Sefaria API
├── tikkun.py            tikkun.io line layout and font
├── cache.py             on-disk cache used by both
├── lpcg.py              recitation note type, card templates, line-mode cards
├── verse_cards.py       pasuq-mode cards and the word alignment
├── anki_connect/        AnkiConnect client, scheduling, tagging, CLI
├── data/                bundled maftir lengths and holiday readings
├── webgui/              the app (pywebview + HTML/JS)
└── gui/                 the old tkinter app, no longer maintained
scripts/                 double-clickable wrappers for the Anki tools
docs/                    scheduling and tagging in detail
```

Only `webgui/` and `gui/` touch anything graphical. The AnkiConnect client
is plain standard library. Everything from `config.py` to `verse_cards.py`
can be used from a script or a notebook.

The first version of the app used tkinter, which doesn't handle
right-to-left text properly; long pointed pesuqim came out with words
scrambled, especially on Windows. The current app shows the same interface
in a web view, where Hebrew just works. The old one is still in `gui/` and
starts with `ankipasuk-tk-legacy`, but it isn't being developed.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests scripts
```

The tests don't touch the network. They use hand-built pesuqim with real
ta'am characters, fake tikkun.io pages (including lines shared between
pesuqim and across 'amudim), and an in-memory stand-in for AnkiConnect.

## Credits

- Text and te'amim from the [Sefaria API](https://www.sefaria.org/).
- Scroll layout and the Shlomo semiStam font from
  [tikkun.io](https://github.com/akivajgordon/tikkun.io) (MIT; the font is
  by Shlomo Orbach under the SIL Open Font License).
- Maftir lengths and the holiday reading table come from
  [`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning)
  (BSD-2-Clause); see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- The line-by-line recitation method comes from
  [AnkiLPCG](https://github.com/sobjornstad/AnkiLPCG) by Soren Bjornstad.
  No code was taken from it.

AnkiPasuk isn't affiliated with any of these projects.

## License

[MIT](LICENSE)
