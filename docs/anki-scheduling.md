# Anki scheduling automation

The cloze generator produces one note per verse, with the verse's full text
as the last (highest-`ord`) cloze -- the **stem** -- and each nested clause
as an earlier, easier cloze -- a **leaf**. Once a stem is well-memorized,
drilling its leaves separately stops being useful, so this module manages a
promotion cycle that suspends leaves once their stem matures, and brings
them back if the stem later lapses.

Flags track a stem's phase:

| Flag | Meaning |
|---|---|
| 1 | Active stem -- leaves are live and studied normally. |
| 2 | Mature stem -- leaves are suspended. |

```text
Flag 1 + stem interval >= PROMOTION_INTERVAL
        |
        v
    Flag stem 1 -> 2
    Suspend leaves

Flag 2 + stem interval < PROMOTION_INTERVAL   (i.e. the stem lapsed)
        |
        v
    Unsuspend leaves
    Answer leaves "Again"
    Flag stem 2 -> 1
```

## Requirements

- [Anki](https://apps.ankiweb.net/) running locally.
- The [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
  installed (default: listens on `http://127.0.0.1:8765`).
- Decks named `Leyning::1-Bereshit` through `Leyning::5-Devarim`, matching
  `ankipasuk.config.LEYNING_DECK_NAMES` -- one per Torah book, populated
  from the CSVs the main app exports.

## Running it

Two equivalent ways to run each step: double-click the script (Windows-
friendly, config at the top of the file), or use the installed console
command (any OS, flags on the command line).

### 1. One-time setup: flag every note's stem

```powershell
python .\scripts\flag_stem_cards.py
```
or
```bash
ankipasuk-init-stems "Leyning::1-Bereshit" --dry-run   # preview
ankipasuk-init-stems "Leyning::1-Bereshit"             # apply
```

Run this once per deck, right after importing its CSV. It finds the
highest-`ord` card on every note and flags it `1`; notes that already have
a flag are left untouched.

### 2. Recurring: run the scheduling cycle

```powershell
python .\scripts\update_mature_cards.py
```
or
```bash
ankipasuk-sync-scheduling "Leyning::1-Bereshit" --promotion-interval 21 --dry-run
ankipasuk-sync-scheduling "Leyning::1-Bereshit" --promotion-interval 21
```

Run this regularly (e.g. as a scheduled task). It promotes any flag-1 stem
whose interval has reached `PROMOTION_INTERVAL` days, and recovers any
flag-2 stem whose interval has since dropped back below it.

### 3. Just checking AnkiConnect is reachable

```powershell
python .\scripts\test_anki_connect.py
```
or
```bash
ankipasuk-check-connection
```

## Always dry-run first

Every script/command supports a dry run (`DRY_RUN = True` at the top of the
`.py` file, or `--dry-run` on the command line) that prints exactly what it
would change without touching Anki. Use a test deck and a low
`PROMOTION_INTERVAL` (e.g. 10) to sanity-check behavior before pointing at
a real deck.

## Library structure

```
src/ankipasuk/anki_connect/
├── client.py       # raw AnkiConnect JSON-RPC client (invoke())
├── notes.py        # pure stem/leaf identification, no network
├── operations.py   # AnkiConnect-backed card ops (search/flag/suspend/answer)
├── scheduling.py   # the promotion / lapse-recovery policy
└── cli.py          # console-friendly wrappers used by scripts/ and by
                     # the `ankipasuk-*` console_scripts entry points
```

`notes.py` has no network dependency and is unit tested directly.
`scheduling.py` is tested end-to-end against an in-memory fake AnkiConnect
backend (`tests/test_anki_connect/conftest.py`), so the promotion/recovery
logic itself is verified without needing Anki running.

## Safety notes

- Each scheduling pass re-derives the stem/leaves for every matched note
  and double-checks that the card the search matched actually is that
  note's stem before touching anything -- if the deck's card structure was
  ever edited by hand, the mismatched note is skipped with a warning rather
  than silently mishandled.
- Flags 1 and 2 are reserved for this workflow; `initialize_stems` never
  overwrites a note that already has *any* non-zero flag, so it's safe to
  re-run.
