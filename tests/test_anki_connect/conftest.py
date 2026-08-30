"""A small in-memory fake of the AnkiConnect actions that
ankipasuk.anki_connect.operations relies on, so scheduling.py's actual
promotion/lapse-recovery logic can be exercised without a running Anki
instance or any network access.
"""

from __future__ import annotations

import pytest


class FakeAnki:
    """Holds a tiny fake collection of notes/cards and answers the subset
    of AnkiConnect actions this project uses."""

    def __init__(self):
        self._next_card_id = 1
        self.cards: dict[int, dict] = {}   # cardId -> card dict
        self.calls: list[tuple[str, dict]] = []

    def add_note(self, note_id: int, deck: str, ords_and_intervals: list[tuple[int, int]]) -> None:
        """Add a note with cards at the given (ord, interval_days) pairs."""
        for ord_, interval in ords_and_intervals:
            card_id = self._next_card_id
            self._next_card_id += 1
            self.cards[card_id] = {
                "cardId": card_id,
                "note": note_id,
                "ord": ord_,
                "interval": interval,
                "flags": 0,
                "deck": deck,
                "suspended": False,
            }

    # --- the AnkiConnect-shaped API surface used by operations.py --------
    def invoke(self, action: str, **params):
        self.calls.append((action, params))
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            raise AssertionError(f"FakeAnki has no handler for action {action!r}")
        return handler(**params)

    def _do_version(self):
        return 6

    def _do_findCards(self, query: str):
        # Supports the small subset of query syntax this project emits:
        # "deck:X", "nid:N", "deck:X flag:F", "deck:X flag:F prop:ivl>=N",
        # "deck:X flag:F prop:ivl<N".
        parts = query.split()
        matches = list(self.cards.values())

        for part in parts:
            if part.startswith("deck:"):
                deck = part[len("deck:"):]
                matches = [c for c in matches if c["deck"] == deck]
            elif part.startswith("nid:"):
                note_id = int(part[len("nid:"):])
                matches = [c for c in matches if c["note"] == note_id]
            elif part.startswith("flag:"):
                flag = int(part[len("flag:"):])
                matches = [c for c in matches if c["flags"] == flag]
            elif part.startswith("prop:ivl>="):
                threshold = int(part[len("prop:ivl>="):])
                matches = [c for c in matches if c["interval"] >= threshold]
            elif part.startswith("prop:ivl<"):
                threshold = int(part[len("prop:ivl<"):])
                matches = [c for c in matches if c["interval"] < threshold]
            else:
                raise AssertionError(f"FakeAnki findCards: unsupported query term {part!r}")

        return [c["cardId"] for c in matches]

    def _do_cardsInfo(self, cards: list[int]):
        return [dict(self.cards[cid]) for cid in cards]

    def _do_setSpecificValueOfCard(self, card: int, keys: list[str], newValues: list, warning_check: bool):
        assert keys == ["flags"]
        self.cards[card]["flags"] = newValues[0]
        return [True]

    def _do_suspend(self, cards: list[int]):
        for cid in cards:
            self.cards[cid]["suspended"] = True
        return True

    def _do_unsuspend(self, cards: list[int]):
        for cid in cards:
            self.cards[cid]["suspended"] = False
        return True

    def _do_answerCards(self, answers: list[dict]):
        return [True for _ in answers]


@pytest.fixture
def fake_anki(monkeypatch):
    """Patch ankipasuk.anki_connect.client.invoke to route through a
    FakeAnki instance instead of the network, and hand the test the
    FakeAnki so it can set up cards and inspect state afterward."""
    import ankipasuk.anki_connect.client as client_module

    backend = FakeAnki()

    def fake_invoke(
        action, *, url=client_module.DEFAULT_URL, timeout=client_module.DEFAULT_TIMEOUT, **params
    ):
        return backend.invoke(action, **params)

    monkeypatch.setattr(client_module, "invoke", fake_invoke)
    # operations.py imported `invoke` by name, so it must be patched there too.
    import ankipasuk.anki_connect.operations as operations_module
    monkeypatch.setattr(operations_module, "invoke", fake_invoke)

    import ankipasuk.anki_connect.cli as cli_module
    monkeypatch.setattr(cli_module, "invoke", fake_invoke)

    return backend
