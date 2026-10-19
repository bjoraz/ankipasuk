"""Rename the tags AnkiPasuk made with the old spelling (aliyah::...,
holiday::simchat_torah, amud::..., ...) to the new spelling described in
docs/transliteration.md.

Only touches tags AnkiPasuk itself generates, and adds each new tag before
removing the old one. Safe to run repeatedly.

Double-click to run, or:

    python migrate_tags.py
"""

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.anki_connect.cli import migrate_tags_cli

# ============================================================
# CONFIGURATION
# ============================================================
ANKI_CONNECT_URL = "http://127.0.0.1:8765"

# The whole deck (or a sub-deck) -- every note in it gets checked.
DECK = "Qeriya"

# First run with True.
# Once the output looks correct, change to False.
DRY_RUN = True

if __name__ == "__main__":
    migrate_tags_cli(DECK, url=ANKI_CONNECT_URL, dry_run=DRY_RUN)
