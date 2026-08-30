"""Quick check that AnkiConnect is reachable. Double-click to run, or:

    python test_anki_connect.py
"""

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.anki_connect.cli import check_connection

# ============================================================
# CONFIGURATION
# ============================================================
ANKI_CONNECT_URL = "http://127.0.0.1:8765"

if __name__ == "__main__":
    check_connection(url=ANKI_CONNECT_URL)
