"""One-time setup: flag the stem (last/outermost cloze) of every note in a
deck with flag 1. Run this once when initializing a freshly-imported deck.

Double-click to run, or:

    python flag_stem_cards.py
"""

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.anki_connect.cli import initialize_stems_cli

# ============================================================
# CONFIGURATION
# ============================================================
ANKI_CONNECT_URL = "http://127.0.0.1:8765"

DECK = "Leyning::5-Devarim"

# First run with True.
# Once the output looks correct, change to False.
DRY_RUN = True

if __name__ == "__main__":
    initialize_stems_cli(DECK, url=ANKI_CONNECT_URL, dry_run=DRY_RUN)
