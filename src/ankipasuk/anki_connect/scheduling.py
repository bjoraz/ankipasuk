"""Scheduling policy for the stem/leaf promotion cycle.

Card structure produced by the cloze generator: every note has one "stem"
(the full-verse, highest-``ord`` cloze) and one or more "leaves" (partial,
easier clozes). Flags track which phase a stem is in:

- **Flag 1** = active stem -- leaves are live, being studied normally.
- **Flag 2** = mature stem -- leaves are suspended once the stem's own
  interval has grown past ``promotion_interval`` days, since drilling the
  easier partial hints is no longer useful once the full verse is well
  known.

Promotion (1 -> 2) fires once the stem is mature enough; lapse recovery
(2 -> 1) fires if the stem's interval later drops back below the
threshold (e.g. after a lapse), which un-suspends the leaves and answers
them "Again" so they resume being drilled alongside the stem.
"""

from __future__ import annotations

from collections.abc import Callable

from .client import AnkiConnectError
from .notes import group_cards_by_note, pick_stem_and_leaves
from .operations import answer_again, cards_info, find_cards, set_flag, suspend, unsuspend

Logger = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


def initialize_stems(deck: str, *, url: str, dry_run: bool, log: Logger = _noop) -> dict:
    """One-time setup: flag the stem (highest-``ord`` card) of every note
    in ``deck`` with flag 1, leaving any note that already has a flag
    untouched. Returns a summary dict with counts."""
    card_ids = find_cards(f"deck:{deck}", url=url)
    log(f"Found {len(card_ids)} card(s) in {deck}.")

    if not card_ids:
        return {"flagged": 0, "skipped": 0, "notes": 0}

    cards = cards_info(card_ids, url=url, log=log)
    notes = group_cards_by_note(cards)
    log(f"Found {len(notes)} note(s).")

    flagged = 0
    skipped = 0

    for note_cards in notes.values():
        stem, _leaves = pick_stem_and_leaves(note_cards)
        stem_id = stem["cardId"]
        current_flags = stem.get("flags", 0)

        if current_flags != 0:
            log(f"SKIP   {stem_id} (already flag {current_flags})")
            skipped += 1
            continue

        log(f"FLAG   {stem_id} (ord {stem['ord']}) -> 1")
        set_flag(stem_id, 1, url=url, dry_run=dry_run)
        flagged += 1

    return {"flagged": flagged, "skipped": skipped, "notes": len(notes)}


def _resolve_stem_for_matched_card(matched_card: dict, *, url: str, log: Logger):
    """Re-derive the stem/leaves for the note behind ``matched_card``, and
    make sure the card the search matched really is the stem (a defensive
    check in case the deck's card structure was ever edited)."""
    note_id = matched_card["note"]
    card_ids = find_cards(f"nid:{note_id}", url=url)
    cards = cards_info(card_ids, url=url)
    stem, leaves = pick_stem_and_leaves(cards)

    if stem["cardId"] != matched_card["cardId"]:
        log(
            f"WARNING -- SKIPPING: matched card {matched_card['cardId']} is not "
            f"the note's actual stem ({stem['cardId']})."
        )
        return None, None

    return stem, leaves


def process_promotions(
    deck: str, promotion_interval: int, *, url: str, dry_run: bool, log: Logger = _noop
) -> dict:
    """Promote every flag-1 stem whose interval has reached
    ``promotion_interval`` days: flag it 2 and suspend its leaves."""
    query = f"deck:{deck} flag:1 prop:ivl>={promotion_interval}"
    log(f"Promotion search: {query}")

    matching_ids = find_cards(query, url=url)
    log(f"Found {len(matching_ids)} candidate stem(s).")
    if not matching_ids:
        return {"promoted": 0}

    matching_cards = cards_info(matching_ids, url=url, log=log)
    promoted = 0

    for matched_card in matching_cards:
        stem, leaves = _resolve_stem_for_matched_card(matched_card, url=url, log=log)
        if stem is None:
            continue

        log(
            f"PROMOTE stem {stem['cardId']} (interval {stem.get('interval', '?')}d) "
            f"flag 1 -> 2, suspending {len(leaves)} leaf/leaves"
        )

        set_flag(stem["cardId"], 2, url=url, dry_run=dry_run)
        suspend([leaf["cardId"] for leaf in leaves], url=url, dry_run=dry_run, log=log)
        promoted += 1

    return {"promoted": promoted}


def process_lapses(
    deck: str, promotion_interval: int, *, url: str, dry_run: bool, log: Logger = _noop
) -> dict:
    """Recover every flag-2 stem whose interval has dropped back below
    ``promotion_interval`` days (i.e. it lapsed): un-suspend its leaves,
    answer them all 'Again', and flag the stem back to 1."""
    query = f"deck:{deck} flag:2 prop:ivl<{promotion_interval}"
    log(f"Lapse-recovery search: {query}")

    matching_ids = find_cards(query, url=url)
    log(f"Found {len(matching_ids)} candidate stem(s).")
    if not matching_ids:
        return {"recovered": 0}

    matching_cards = cards_info(matching_ids, url=url, log=log)
    recovered = 0

    for matched_card in matching_cards:
        stem, leaves = _resolve_stem_for_matched_card(matched_card, url=url, log=log)
        if stem is None:
            continue

        log(
            f"RECOVER stem {stem['cardId']} (interval {stem.get('interval', '?')}d) "
            f"flag 2 -> 1, un-suspending + re-queuing {len(leaves)} leaf/leaves"
        )

        leaf_ids = [leaf["cardId"] for leaf in leaves]
        unsuspend(leaf_ids, url=url, dry_run=dry_run, log=log)
        answer_again(leaf_ids, url=url, dry_run=dry_run, log=log)
        set_flag(stem["cardId"], 1, url=url, dry_run=dry_run)
        recovered += 1

    return {"recovered": recovered}


def run_scheduling_cycle(
    deck: str, promotion_interval: int, *, url: str, dry_run: bool, log: Logger = _noop
) -> dict:
    """Run one full promotion + lapse-recovery cycle for ``deck``."""
    promo_result = process_promotions(deck, promotion_interval, url=url, dry_run=dry_run, log=log)
    lapse_result = process_lapses(deck, promotion_interval, url=url, dry_run=dry_run, log=log)
    return {**promo_result, **lapse_result}


__all__ = [
    "AnkiConnectError",
    "initialize_stems",
    "process_promotions",
    "process_lapses",
    "run_scheduling_cycle",
]
