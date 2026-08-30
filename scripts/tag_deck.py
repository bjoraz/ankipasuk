"""Tag every note in a deck with its parasha/aliyah/Maftir/holiday tags,
computed from Sefaria (live, cached locally) + a small bundled data table.

Never removes or overwrites existing tags -- only adds missing ones, and
reports any conflicts (an existing "aliyah::..."/"holiday::..." tag that
doesn't match what was computed) for you to review by hand. Safe to run
repeatedly.

Double-click to run, or:

    python tag_deck.py
"""

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.anki_connect.cli import tag_deck_cli

# ============================================================
# CONFIGURATION
# ============================================================
ANKI_CONNECT_URL = "http://127.0.0.1:8765"

# The whole "Leyning" deck (or a sub-deck, e.g. "Leyning::1-Bereshit") --
# every note in it gets checked, regardless of which book/parasha it's in.
DECK = "Leyning"

# First run with True.
# Once the output looks correct, change to False.
DRY_RUN = True

if __name__ == "__main__":
    tag_deck_cli(DECK, url=ANKI_CONNECT_URL, dry_run=DRY_RUN)
