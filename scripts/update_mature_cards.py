"""Run regularly to manage the stem/leaf scheduling cycle:

    Flag 1 + interval >= PROMOTION_INTERVAL
        -> flag stem 1 -> 2, suspend leaves

    Flag 2 + interval < PROMOTION_INTERVAL
        -> unsuspend leaves, answer leaves Again, flag stem 2 -> 1

Double-click to run, or:

    python update_mature_cards.py
"""

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.anki_connect.cli import sync_scheduling_cli

# ============================================================
# CONFIGURATION
# ============================================================
ANKI_CONNECT_URL = "http://127.0.0.1:8765"

DECK = "Leyning::1-Bereshit"

# True  = show what would happen, make NO changes
# False = actually modify Anki
DRY_RUN = True

# For a test deck, use something smaller (e.g. 10).
# For the real deck, use 21.
PROMOTION_INTERVAL = 21

if __name__ == "__main__":
    sync_scheduling_cli(DECK, PROMOTION_INTERVAL, url=ANKI_CONNECT_URL, dry_run=DRY_RUN)
