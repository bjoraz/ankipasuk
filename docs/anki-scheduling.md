# Retiring clause cards once you know the pasuq

Every note from the cloze export has one card for the whole pasuq (the
last, highest-numbered cloze, called the **stem** here) and one card for
each clause in it (the **leaves**). The leaves are how you learn the pasuq,
but once you can read the whole thing reliably they're just extra reviews.
This tool suspends a note's leaves when its stem matures, and brings them
back if the stem lapses.

It keeps track with Anki's flags:

| Flag | Meaning |
|---|---|
| 1 (red) | Active: the leaves are reviewed as usual. |
| 2 (orange) | Mature: the leaves are suspended. |

Each sync does two things:

- **Promotion.** A stem with flag 1 whose interval has reached the
  promotion interval (21 days unless you change it) gets flag 2, and its
  leaves are suspended.
- **Lapse recovery.** A stem with flag 2 whose interval has dropped back
  below that (because you forgot it) gets flag 1 again. Its leaves are
  unsuspended and answered Again, so you drill them alongside the stem
  until it's solid.

## What you need

- Anki running on the same machine, with the
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
  (it listens on `http://127.0.0.1:8765` by default).
- A deck of notes imported from the cloze CSV export. Any deck name works;
  you pass it to each tool. The scripts in `scripts/` come preset with
  names like `Qeriya::1-Bereshit`, so change the `DECK` line at the top of
  the file to match yours.

## Running it

Each step can be run three ways:

- **From the app.** Launch `ankipasuk`, click **Anki tools** in the top bar, and
  use the tab for that step. Each tab has a deck field, a dry-run checkbox
  and a log.
- **As a script.** Double-click the file in `scripts/` (handy on Windows).
  Its settings are at the top of the file.
- **As a command**, with the settings as arguments.

### 1. Once per deck: flag the stems

```powershell
python .\scripts\flag_stem_cards.py
```
or
```bash
ankipasuk-init-stems "Qeriya::1-Bereshit" --dry-run   # preview
ankipasuk-init-stems "Qeriya::1-Bereshit"             # apply
```

Do this right after importing a deck. It finds the highest-numbered card
on every note and gives it flag 1. Notes that already have a flag are left
alone, so it's safe to run again after importing more pesuqim.

### 2. Regularly: sync

```powershell
python .\scripts\update_mature_cards.py
```
or
```bash
ankipasuk-sync-scheduling "Qeriya::1-Bereshit" --promotion-interval 21 --dry-run
ankipasuk-sync-scheduling "Qeriya::1-Bereshit" --promotion-interval 21
```

Run it as often as you like. Once a day, or after each study session, is
plenty. The command is the easiest to put in a scheduled task.

### Checking that Anki is reachable

```powershell
python .\scripts\test_anki_connect.py
```
or
```bash
ankipasuk-check-connection
```

## Dry-run first

Every way of running these has a dry run: `DRY_RUN = True` at the top of
the script, the **Dry run** checkbox in the app, or `--dry-run` on the
command line. It prints exactly what would change and changes nothing. To
try the whole cycle out, use a test deck and a short promotion interval
(say 10 days).

## Safety

- On every sync, each note's stem and leaves are worked out again, and the
  tool checks that the card it found really is that note's stem before
  touching anything. If a note's cards were edited by hand and no longer
  fit, that note is skipped with a warning.
- Flags 1 and 2 are reserved for this. Flagging stems never touches a
  stem card that already has a flag of any color.

## How it's put together

```
src/ankipasuk/anki_connect/
├── client.py       AnkiConnect requests (standard library only)
├── notes.py        which card is the stem, which are leaves (no network)
├── operations.py   search, flag, suspend, answer
├── scheduling.py   promotion and lapse recovery
└── cli.py          the commands and the scripts' entry points
```

The only thing this relies on from the cloze export is that the whole
pasuq is always the highest-numbered cloze on its note. `notes.py` is
tested on its own, and `scheduling.py` is tested end to end against an
in-memory stand-in for AnkiConnect, so none of it needs Anki to test.
