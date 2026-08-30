import pytest

from ankipasuk.anki_connect.notes import group_cards_by_note, pick_stem_and_leaves


def _card(card_id, note, ord_):
    return {"cardId": card_id, "note": note, "ord": ord_}


def test_group_cards_by_note_groups_correctly():
    cards = [_card(1, 100, 0), _card(2, 100, 1), _card(3, 200, 0)]
    notes = group_cards_by_note(cards)
    assert set(notes.keys()) == {100, 200}
    assert {c["cardId"] for c in notes[100]} == {1, 2}
    assert {c["cardId"] for c in notes[200]} == {3}


def test_pick_stem_and_leaves_picks_highest_ord():
    cards = [_card(1, 100, 0), _card(2, 100, 2), _card(3, 100, 1)]
    stem, leaves = pick_stem_and_leaves(cards)
    assert stem["cardId"] == 2  # ord 2 is highest
    assert {c["cardId"] for c in leaves} == {1, 3}


def test_pick_stem_and_leaves_single_card_note():
    cards = [_card(1, 100, 0)]
    stem, leaves = pick_stem_and_leaves(cards)
    assert stem["cardId"] == 1
    assert leaves == []


def test_pick_stem_and_leaves_empty_raises():
    with pytest.raises(ValueError):
        pick_stem_and_leaves([])
