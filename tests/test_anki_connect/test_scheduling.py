from ankipasuk.anki_connect.operations import _BATCH_SIZE
from ankipasuk.anki_connect.scheduling import (
    initialize_stems,
    process_lapses,
    process_promotions,
)

DECK = "Leyning::1-Bereshit"


def test_initialize_stems_flags_only_the_highest_ord_card(fake_anki):
    # note 1: 3 cards, ord 0/1/2 -- ord 2 should be flagged.
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5), (2, 5)])
    result = initialize_stems(DECK, url="http://fake", dry_run=False)

    assert result == {"flagged": 1, "skipped": 0, "notes": 1}
    flags = {c["ord"]: c["flags"] for c in fake_anki.cards.values()}
    assert flags[2] == 1
    assert flags[0] == 0
    assert flags[1] == 0


def test_initialize_stems_batches_requests_on_a_large_deck(fake_anki):
    """Regression test for a real bug: cardsInfo/notesInfo used to be sent
    as one single request for the whole deck, which timed out on a deck
    with thousands of cards. This seeds more than one batch's worth of
    notes and checks both that cardsInfo was actually split into multiple
    calls, and that every note still ends up correctly flagged."""
    n_notes = (_BATCH_SIZE * 2) + 50  # 1 card/note -> guarantees 3 cardsInfo batches
    for note_id in range(1, n_notes + 1):
        fake_anki.add_note(note_id, DECK, [(0, 5)])

    result = initialize_stems(DECK, url="http://fake", dry_run=False)

    assert result == {"flagged": n_notes, "skipped": 0, "notes": n_notes}

    cards_info_calls = [params for action, params in fake_anki.calls if action == "cardsInfo"]
    assert len(cards_info_calls) == 3  # ceil((500*2+50) / 500) == 3
    assert all(len(call["cards"]) <= _BATCH_SIZE for call in cards_info_calls)

    # Every note's card should be flagged.
    for note_id in (1, n_notes // 2, n_notes):
        note_cards = [c for c in fake_anki.cards.values() if c["note"] == note_id]
        assert note_cards[0]["flags"] == 1


def test_initialize_stems_skips_already_flagged_notes(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5)])
    # Pre-flag the stem (highest ord) with something other than 0.
    stem_card_id = max(fake_anki.cards.values(), key=lambda c: c["ord"])["cardId"]
    fake_anki.cards[stem_card_id]["flags"] = 2

    result = initialize_stems(DECK, url="http://fake", dry_run=False)
    assert result == {"flagged": 0, "skipped": 1, "notes": 1}
    assert fake_anki.cards[stem_card_id]["flags"] == 2  # untouched


def test_initialize_stems_dry_run_makes_no_changes(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5)])
    result = initialize_stems(DECK, url="http://fake", dry_run=True)

    assert result["flagged"] == 1  # counted...
    # ...but nothing was actually written.
    assert all(c["flags"] == 0 for c in fake_anki.cards.values())


def test_process_promotions_flags_stem_and_suspends_leaves(fake_anki):
    # note 1: stem (ord 1, interval 30) already flag 1, one leaf (ord 0).
    fake_anki.add_note(1, DECK, [(0, 30), (1, 30)])
    for c in fake_anki.cards.values():
        if c["ord"] == 1:
            c["flags"] = 1

    result = process_promotions(DECK, promotion_interval=21, url="http://fake", dry_run=False)
    assert result == {"promoted": 1}

    stem = next(c for c in fake_anki.cards.values() if c["ord"] == 1)
    leaf = next(c for c in fake_anki.cards.values() if c["ord"] == 0)
    assert stem["flags"] == 2
    assert leaf["suspended"] is True


def test_process_promotions_ignores_stems_below_threshold(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5)])  # interval 5 < 21
    for c in fake_anki.cards.values():
        if c["ord"] == 1:
            c["flags"] = 1

    result = process_promotions(DECK, promotion_interval=21, url="http://fake", dry_run=False)
    assert result == {"promoted": 0}


def test_process_lapses_unsuspends_and_answers_again_and_reflags(fake_anki):
    # note 1: stem (ord 1, interval 5) is flag 2 (mature-but-lapsed), leaf suspended.
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5)])
    stem = next(c for c in fake_anki.cards.values() if c["ord"] == 1)
    leaf = next(c for c in fake_anki.cards.values() if c["ord"] == 0)
    stem["flags"] = 2
    leaf["suspended"] = True

    result = process_lapses(DECK, promotion_interval=21, url="http://fake", dry_run=False)
    assert result == {"recovered": 1}

    assert stem["flags"] == 1
    assert leaf["suspended"] is False
    # answerCards should have been called once, for the leaf.
    answer_calls = [params for action, params in fake_anki.calls if action == "answerCards"]
    assert len(answer_calls) == 1
    assert answer_calls[0]["answers"] == [{"cardId": leaf["cardId"], "ease": 1}]


def test_process_lapses_ignores_stems_at_or_above_threshold(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 30), (1, 30)])
    for c in fake_anki.cards.values():
        if c["ord"] == 1:
            c["flags"] = 2

    result = process_lapses(DECK, promotion_interval=21, url="http://fake", dry_run=False)
    assert result == {"recovered": 0}


def test_process_promotions_dry_run_makes_no_changes(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 30), (1, 30)])
    for c in fake_anki.cards.values():
        if c["ord"] == 1:
            c["flags"] = 1

    result = process_promotions(DECK, promotion_interval=21, url="http://fake", dry_run=True)
    assert result == {"promoted": 1}  # still counted/reported

    stem = next(c for c in fake_anki.cards.values() if c["ord"] == 1)
    leaf = next(c for c in fake_anki.cards.values() if c["ord"] == 0)
    assert stem["flags"] == 1  # untouched
    assert leaf["suspended"] is False  # untouched


def test_scheduling_only_touches_the_target_deck(fake_anki):
    other_deck = "Leyning::2-Shemot"
    fake_anki.add_note(1, DECK, [(0, 30), (1, 30)])
    fake_anki.add_note(2, other_deck, [(0, 30), (1, 30)])
    for c in fake_anki.cards.values():
        if c["ord"] == 1:
            c["flags"] = 1

    process_promotions(DECK, promotion_interval=21, url="http://fake", dry_run=False)

    deck1_stem = next(c for c in fake_anki.cards.values() if c["deck"] == DECK and c["ord"] == 1)
    deck2_stem = next(c for c in fake_anki.cards.values() if c["deck"] == other_deck and c["ord"] == 1)
    assert deck1_stem["flags"] == 2
    assert deck2_stem["flags"] == 1  # other deck untouched
