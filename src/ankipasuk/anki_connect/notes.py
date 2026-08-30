"""Stem/leaf identification.

Each note produced by the cloze generator has multiple cloze cards, nested
from innermost clause (lowest ``c`` number / ``ord``) out to the full verse
(highest ``c`` number / ``ord``). The card with the highest ``ord`` is the
"stem" -- the full-verse recall card -- and every other card on the note is
a "leaf" -- a partial, easier hint card.

This module is pure logic (dict-in, dict-out): no network calls, so it's
directly unit-testable with hand-built card dicts shaped like AnkiConnect's
``cardsInfo`` results.
"""

from __future__ import annotations


def group_cards_by_note(cards: list[dict]) -> dict[int, list[dict]]:
    """Group a flat list of AnkiConnect card-info dicts by their note id."""
    notes: dict[int, list[dict]] = {}
    for card in cards:
        notes.setdefault(card["note"], []).append(card)
    return notes


def pick_stem_and_leaves(note_cards: list[dict]) -> tuple[dict, list[dict]]:
    """Given every card on one note, return (stem, leaves).

    The stem is the card with the highest ``ord`` (the outermost, full-verse
    cloze); every other card is a leaf.
    """
    if not note_cards:
        raise ValueError("A note has no cards.")

    stem = max(note_cards, key=lambda c: c["ord"])
    leaves = [c for c in note_cards if c["cardId"] != stem["cardId"]]
    return stem, leaves
