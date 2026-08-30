"""AnkiConnect-based scheduling automation for the stem/leaf card structure
produced by :mod:`ankipasuk.cloze`.

- :mod:`ankipasuk.anki_connect.client` -- the raw JSON-RPC client.
- :mod:`ankipasuk.anki_connect.notes` -- pure stem/leaf identification
  (no network).
- :mod:`ankipasuk.anki_connect.operations` -- AnkiConnect-backed card
  operations (search, flag, suspend, answer).
- :mod:`ankipasuk.anki_connect.scheduling` -- the promotion / lapse-recovery
  policy built on top of the above.
"""

from .client import AnkiConnectError, invoke
from .scheduling import initialize_stems, process_lapses, process_promotions, run_scheduling_cycle

__all__ = [
    "AnkiConnectError",
    "invoke",
    "initialize_stems",
    "process_promotions",
    "process_lapses",
    "run_scheduling_cycle",
]
