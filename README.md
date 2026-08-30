# AnkiPasuk

Generate nested [Anki](https://apps.ankiweb.net/) cloze cards from Torah
verses, split according to their cantillation (trope) structure — plus a
built-in statistics viewer for exploring the corpus you've fetched.

Verse text and cantillation marks are pulled from the [Sefaria
API](https://www.sefaria.org/), stripped down to their disjunctive
("minimum disjunctive group") structure, and recursively split into a
binary tree of clauses. Each clause becomes a nested `{{c1::...}}` cloze,
so studying the card progressively reveals the verse from its coarsest
grammatical break down to individual words.

## Features

- **Fetch by chapter/verse range or by Parashah/Aliyah**, Torah-wide.
- **Nested cloze generation** based on cantillation-mark disjunctive rank,
  including correct handling of Munach Legarmeh.
- **CSV export** formatted for Anki import (with previous/next verse context
  columns for extra context on each card).
- **Corpus statistics window**: distributions of words per verse, minimum
  disjunctive groups per verse, split-tree depth, words-per-disjunctive-group,
  a length-vs-depth correlation scatter plot, per-chapter averages, and
  trope-frequency counts — every chart is clickable and shows the actual
  verse text behind any bar, point, or row.
- **Persistent local cache**: verse text and parashah structure fetched from
  Sefaria are cached to disk, so re-running the app (or re-fetching an
  overlapping range) never re-downloads the same data.
- **Anki scheduling automation** (optional, via AnkiConnect): once a note's
  full-verse cloze is well-memorized, automatically suspend its easier
  partial-clue clozes, and bring them back if the full verse later lapses.
  See [`docs/anki-scheduling.md`](docs/anki-scheduling.md).
- **Automatic parasha/aliyah/Maftir/holiday tagging** (optional, via
  AnkiConnect): tag every note with where its verse falls in the annual
  Torah reading cycle. See [`docs/anki-tagging.md`](docs/anki-tagging.md).

## Installation

Requires Python 3.10+. Tkinter must be available (it ships with most Python
installers; on Debian/Ubuntu you may need `sudo apt install python3-tk`).

```bash
git clone https://github.com/bjoraz/ankipasuk.git
cd ankipasuk
pip install -e .
```

## Usage

```bash
ankipasuk
# or:
python -m ankipasuk
```

1. Choose **Chapter / Verse** or **Parashah / Aliyah** mode, pick a range,
   and click **Fetch range from Sefaria**.
2. Set **Max disjunctive groups per leaf** (how granular the nested cloze
   splitting should be) and click **Generate cloze cards**.
3. **Export to CSV** for import into Anki, or **Copy cloze output** directly.
4. Click **Show Stats** to open the corpus statistics window for the
   currently loaded range.

### The local cache

The app never re-fetches a verse or parashah structure it has already seen.
Cached data lives at:

- Linux/macOS: `~/.cache/ankipasuk/`
- Windows: `%APPDATA%\AnkiPasuk\`
- Overridable via the `ANKIPASUK_CACHE_DIR` environment variable.

A **Clear cache** button next to the fetch controls deletes it if you ever
need a clean re-fetch.

## Architecture

The codebase is split into a GUI-free core and a thin tkinter GUI on top of
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
├── anki_connect/            # Optional: AnkiConnect scheduling automation
│   ├── client.py             #   raw JSON-RPC client
│   ├── notes.py               #   pure stem/leaf identification (no network)
│   ├── operations.py           #   AnkiConnect-backed card & note operations
│   ├── scheduling.py            #   promotion / lapse-recovery policy
│   ├── tagging.py                #   parasha/aliyah/Maftir/holiday tagging
│   └── cli.py                     #   console-friendly wrappers
├── leyning.py               # Parasha/aliyah/Maftir/holiday tag computation (no network)
├── data/                    # Bundled parasha & holiday-reading tables (see THIRD_PARTY_NOTICES.md)
└── gui/
    ├── app.py            # Main window (AnkiPasukApp)
    ├── stats_window.py   # "Corpus statistics" window
    └── charts.py         # Clickable canvas bar/scatter charts + verse popup

scripts/                  # Double-click-friendly wrappers around anki_connect
├── test_anki_connect.py
├── flag_stem_cards.py
├── update_mature_cards.py
└── tag_deck.py

docs/
├── anki-scheduling.md    # Anki scheduling automation: how it works, how to run it
└── anki-tagging.md       # Automatic tagging: how it works, how to run it
```

Only `gui/` depends on `tkinter`; everything else is pure Python + `requests`,
which is what makes the test suite able to run headless / in CI. `anki_connect/`
depends on nothing but the standard library (`urllib`, `json`) plus a running
Anki + AnkiConnect instance, and is entirely optional -- the cloze generator
works without it.

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
Genesis 31/32 Maftir chapter-boundary edge case.

## Acknowledgments

Verse text and cantillation marks courtesy of the
[Sefaria API](https://www.sefaria.org/). This project is not affiliated with
Sefaria.

Maftir verse counts and the holiday/fast-day reading table are derived from
[`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning) (BSD-2-Clause).
See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for details. This
project is not affiliated with Hebcal.

## License

[MIT](LICENSE)
