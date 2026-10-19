# AnkiPasuk

Generate nested [Anki](https://apps.ankiweb.net/) cloze cards from Torah
verses, split according to their cantillation (trope) structure, or
scroll-accurate recitation flashcards for memorizing an aliyah line by
line the way a Torah reader actually learns it — plus a built-in
statistics viewer for exploring the corpus you've fetched.

Verse text and cantillation marks are pulled from the [Sefaria
API](https://www.sefaria.org/), stripped down to their disjunctive
("minimum disjunctive group") structure, and recursively split into a
binary tree of clauses. Each clause becomes a nested `{{c1::...}}` cloze,
so studying the card progressively reveals the verse from its coarsest
grammatical break down to individual words.

For recitation practice, line-layout data from the
[tikkun.io](https://github.com/akivajgordon/tikkun.io) project renders
each card exactly as it appears on a real Torah scroll column (justified
lines, petuchot/setumot as real gaps, the same STAM-style font) — see
"LPCG recitation cards" below.

## Features

- **Fetch by chapter/verse range or by Parashah/Aliyah**, Torah-wide.
- **Nested cloze generation** based on cantillation-mark disjunctive rank,
  including correct handling of Munach Legarmeh.
- **CSV export** formatted for Anki import (with previous/next verse context
  columns for extra context on each card).
- **LPCG recitation cards** (pushed directly to Anki via AnkiConnect, an
  independent reimplementation of the
  [AnkiLPCG](https://github.com/sobjornstad/AnkiLPCG) overlapping-context
  technique): export a whole aliyah range or a single amud (scroll column)
  as flashcards for memorizing the Torah reading line by line.
  - **Verse mode** (default): one card per verse, word-precise even where
    a physical scroll row is shared with the verse just before/after, or
    where a verse's own tail crosses into the next amud (shown with a
    visible "amud" break) -- only that verse's own words are ever tested;
    a neighboring verse's words on the same row show as plain (front) or
    masked (never shown) context depending on which side they're on.
  - **Row mode**: the classic AnkiLPCG sliding window over physical scroll
    rows, with configurable context/recite line counts and grouping.
  - Every card is rendered scroll-accurate (`ankipasuk.tikkun`): justified
    lines broken exactly where a kosher Sefer Torah's column would break,
    petuchot and setumot (including poetic "brick" layouts like Az
    Yashir/Shirat HaYam or the Aseret HaDibrot) shown as real gaps, in the
    same STAM-style font tikkun.io itself uses. Font size, line spacing,
    and box width are all adjustable live, directly on the card.
- **Tikkun.io scroll-style display** in the source section: view any
  fetched Torah range (plain or pointed/nikud) laid out exactly as it
  would appear on the physical scroll, with the same live font-size/
  line-height/width controls -- useful for browsing without exporting.
- **Corpus statistics window**: distributions of words per verse, minimum
  disjunctive groups per verse, split-tree depth, words-per-disjunctive-group,
  a length-vs-depth correlation scatter plot, per-chapter averages, and
  trope-frequency counts — every chart is clickable and shows the actual
  verse text behind any bar, point, or row.
- **Verse nesting-structure analysis** (`ankipasuk.structure`, not yet
  exposed in the GUI): group every verse in a range by its cantillation
  nesting shape (the traditional disjunctive-accent hierarchy -- strongest
  mark divides first, then the next-strongest present mark within each
  half, and so on), find every other verse sharing a given verse's exact
  shape, or see which shapes recur most.
- **Persistent local cache**: verse text and parashah structure fetched from
  Sefaria are cached to disk, so re-running the app (or re-fetching an
  overlapping range) never re-downloads the same data.
- **Anki scheduling automation** (optional, via AnkiConnect): once a note's
  full-verse cloze is well-memorized, automatically suspend its easier
  partial-clue clozes, and bring them back if the full verse later lapses.
  Available from the GUI (**AnkiConnect Tools** link) or as standalone
  scripts. See [`docs/anki-scheduling.md`](docs/anki-scheduling.md).
- **Automatic parasha/aliyah/Maftir/holiday tagging** (optional, via
  AnkiConnect): tag every note with where its verse falls in the annual
  Torah reading cycle. Also available from the **AnkiConnect Tools** link.
  See [`docs/anki-tagging.md`](docs/anki-tagging.md).

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/bjoraz/ankipasuk.git
cd ankipasuk
pip install -e .
```

On **Windows** and **macOS** that's everything: the window is rendered by
WebView2 and WKWebView respectively, and the bindings for both come in as
pywebview dependencies.

### Linux: one extra step

pywebview drives the web engine the system already has rather than
bundling one, and on Linux that engine isn't reachable from a fresh
virtualenv by default. Pick either backend -- the app detects which one is
present and uses it, preferring WebKitGTK when both are.

**WebKitGTK** (recommended -- the engine your desktop already uses, so the
window matches the rest of the system and nothing extra is downloaded):

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0  # Debian/Ubuntu
sudo dnf install python3-gobject webkit2gtk4.1                      # Fedora
sudo pacman -S python-gobject webkit2gtk-4.1                        # Arch
sudo zypper install python3-gobject typelib-1_0-WebKit2-4_1         # openSUSE
```

These are system packages, so a virtualenv has to be allowed to see them:

```bash
python3 -m venv --system-site-packages .venv    # venv
pipx install --system-site-packages ankipasuk   # pipx
```

An existing virtualenv can't be opened up after the fact -- recreate it,
or set `include-system-site-packages = true` in its `pyvenv.cfg`.

**Qt WebEngine** (no system packages and no root, but a ~100 MB download):

```bash
pip install -e ".[qt]"
```

Running `ankipasuk` with neither installed prints these instructions
rather than failing on an import. `PYWEBVIEW_GUI=gtk` or `PYWEBVIEW_GUI=qt`
forces a particular backend if the automatic choice ever picks wrong.

The retired Tk interface (`ankipasuk-tk-legacy`) additionally needs
tkinter, which most distributions package separately -- `python3-tk` on
Debian/Ubuntu, `python3-tkinter` on Fedora. The current GUI doesn't use
tkinter at all.

## Usage

```bash
ankipasuk
# or:
python -m ankipasuk
```

(The original tkinter GUI is still available via `ankipasuk-tk-legacy` if
ever needed, but isn't actively developed -- see "Why webgui, not gui"
below.)

1. Choose **Chapter / Verse** or **Parashah / Aliyah** mode, pick a range
   (add more ranges to concatenate them), and click **Fetch all ranges**.
   Check **Tikkun.io scroll layout** above the text boxes to see it laid
   out scroll-accurate instead of as flat verse text (Torah ranges only);
   its own **A-/A+**, **≡-/≡+**, and **↔-/↔+** controls adjust text size,
   line spacing, and box width live, and persist across app restarts.
2. Set **Max disjunctive groups per leaf** (how granular the nested cloze
   splitting should be) and click **Generate cloze cards**.
3. **Export to CSV** for import into Anki, or **Copy cloze output** directly.
4. Click **Corpus statistics** to open the statistics window for the
   currently loaded range.
5. **Export aliyah range to Anki** (further down the page) pushes LPCG-style
   recitation cards straight to Anki via AnkiConnect for a parashah/aliyah
   range or a single amud -- pick **Verse** or **Row** card division and a
   deck name. Requires Anki running with the AnkiConnect add-on; the note
   type is created automatically on first use.
6. **AnkiConnect Tools** opens a window for the optional
   AnkiConnect-backed features (connection check, stem initialization,
   scheduling sync, tagging) -- see
   [`docs/anki-scheduling.md`](docs/anki-scheduling.md) and
   [`docs/anki-tagging.md`](docs/anki-tagging.md).

### The local cache

The app never re-fetches a verse or parashah structure it has already seen,
nor a tikkun.io page/table-of-contents/font it's already downloaded for a
recitation-card export or the scroll-style display. Cached data lives at:

- Linux/macOS: `~/.cache/ankipasuk/`
- Windows: `%APPDATA%\AnkiPasuk\`
- Overridable via the `ANKIPASUK_CACHE_DIR` environment variable.

A **Clear cache** button next to the fetch controls deletes it if you ever
need a clean re-fetch. (The GUI window's own settings -- last-used deck
name, and the tikkun display's text-size/line-height/width controls --
live separately, in a `webview_storage` subfolder of the same directory,
so they persist across restarts too.)

## Architecture

The codebase is split into a GUI-free core and a web-based GUI on top of
it, so the actual cantillation-parsing logic can be tested, scripted, or
reused independently of the desktop app:

```
src/ankipasuk/
├── config.py           # Static constants (Torah structure, trope unicode table, ...)
├── cache.py             # Persistent, on-disk cache for Sefaria lookups
├── sefaria.py           # Sefaria API wrapper (uses cache.py)
├── text_processing.py   # Trope tokenization, disjunctive grouping, tree splitting
├── cloze.py              # Nested cloze markup generation from the split tree
├── stats.py               # Corpus statistics computation (no GUI dependency)
├── structure.py           # Verse nesting-structure analysis/grouping (no GUI dependency)
├── tikkun.py               # Scroll-accurate line/page layout from tikkun.io (uses cache.py)
├── verse_cards.py           # Word-precise verse-anchored LPCG card builder (uses tikkun.py)
├── lpcg.py                   # LPCG note type/CSS/templates + row-anchored card builder
├── anki_connect/            # Optional: AnkiConnect scheduling automation, and note push
│   ├── client.py             #   raw JSON-RPC client
│   ├── notes.py               #   pure stem/leaf identification (no network)
│   ├── operations.py           #   AnkiConnect-backed card & note operations
│   ├── scheduling.py            #   promotion / lapse-recovery policy
│   ├── tagging.py                #   parasha/aliyah/Maftir/holiday tagging
│   └── cli.py                     #   console-friendly wrappers
├── leyning.py               # Parasha/aliyah/Maftir/holiday tag computation (no network)
├── data/                    # Bundled parasha & holiday-reading tables (see THIRD_PARTY_NOTICES.md)
├── webgui/                  # The GUI: a pywebview window rendering local HTML/CSS/JS
│   ├── api.py                 #   main window's Python<->JS bridge (fetch, cloze, CSV, LPCG export)
│   ├── anki_connect_api.py    #   AnkiConnect Tools window's bridge
│   ├── stats_api.py           #   Corpus statistics window's bridge
│   ├── tree_html.py           #   renders the cloze split-tree as RTL-correct HTML
│   └── static/                 #   index.html/anki_connect.html/stats.html + .js/.css
└── gui/                     # Legacy: the original tkinter GUI, kept for reference
    ├── app.py                  #   (see "Why webgui, not gui" below)
    ├── stats_window.py
    ├── anki_connect_window.py
    └── charts.py

scripts/                  # Double-click-friendly wrappers around anki_connect
├── test_anki_connect.py
├── flag_stem_cards.py
├── update_mature_cards.py
└── tag_deck.py

docs/
├── anki-scheduling.md    # Anki scheduling automation: how it works, how to run it
└── anki-tagging.md       # Automatic tagging: how it works, how to run it
```

Only `webgui/` and (legacy) `gui/` depend on anything GUI-related;
everything else is pure Python + `requests`, which is what makes the test
suite able to run headless / in CI. `anki_connect/` depends on nothing but
the standard library (`urllib`, `json`) plus a running Anki + AnkiConnect
instance, and is entirely optional -- the cloze generator works without it.

### Why `webgui`, not `gui`

The original GUI was built with tkinter. Tkinter's `Text` widget has no
real implementation of the Unicode Bidirectional Algorithm, which caused
persistent, hard-to-fully-fix bugs with Hebrew (niqud/teamim-heavy RTL
text): word order and spacing corruption on long lines, and text visibly
rearranging when the user selected it with the mouse -- both confirmed
present on the actual target platform (Windows), and both traced to
documented, long-standing tkinter/Tk limitations rather than anything
fixable with more workarounds.

`webgui/` renders the same UI as plain HTML with `dir="rtl"`, using the
OS's native web engine (WebView2 on Windows, the same Chromium family used
by every mainstream browser) via [`pywebview`](https://pywebview.flowrl.com/).
Browsers implement bidi text correctly, including selection -- this isn't
a workaround, it eliminates the underlying bug class. `gui/` is kept in
the repository for reference and is still runnable via the
`ankipasuk-tk-legacy` command, but is no longer the default and isn't
being developed further.

Everything below `gui/`/`webgui/` in the module list above -- all the
actual cantillation-parsing, statistics, and tagging logic -- is
completely unaffected by this and required no changes.

## Development

```bash
pip install -e ".[dev]"
pytest            # run the test suite (headless, no display needed)
ruff check src tests   # lint
```

Tests focus on the core logic (`text_processing`, `cloze`, `stats`, `cache`)
using small, hand-built verses with real trope Unicode combining marks, so
they don't depend on network access to Sefaria. `tests/test_cache.py`
specifically verifies that a repeat fetch of the same reference is served
from disk instead of hitting the network again. `tests/test_anki_connect/`
exercises the promotion/lapse-recovery scheduling logic, and the tagging
logic, end-to-end against an in-memory fake AnkiConnect backend, so it
runs without Anki installed. `tests/test_leyning.py` covers the
parasha/aliyah/Maftir/holiday tag computation itself, including the
Genesis 31/32 Maftir chapter-boundary edge case. `tests/test_tikkun.py`,
`tests/test_verse_cards.py`, and `tests/test_lpcg.py` exercise the
scroll-layout/recitation-card logic against hand-built fake tikkun.io
table-of-contents/page data (zero network access, same as everything
else), including the word-level alignment at shared row and amud
boundaries described above.

## Acknowledgments

Verse text and cantillation marks courtesy of the
[Sefaria API](https://www.sefaria.org/). This project is not affiliated with
Sefaria.

Scroll-accurate line/page layout data and the STAM-style font used for
recitation cards and the tikkun-style display are fetched live (and cached
locally) from the [tikkun.io project](https://github.com/akivajgordon/tikkun.io)
(MIT licensed). This project is not affiliated with tikkun.io.

Maftir verse counts and the holiday/fast-day reading table are derived from
[`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning) (BSD-2-Clause).
See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for details. This
project is not affiliated with Hebcal.

## License

[MIT](LICENSE)
