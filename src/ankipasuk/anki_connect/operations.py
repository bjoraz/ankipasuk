"""AnkiConnect-backed operations: searching, flagging, suspending, and
answering cards. Thin wrappers around :func:`ankipasuk.anki_connect.client.invoke`,
kept separate from the scheduling policy in :mod:`ankipasuk.anki_connect.scheduling`
so each can be tested independently.
"""

from __future__ import annotations

from collections.abc import Callable

from .client import AnkiConnectError, invoke
from .notes import pick_stem_and_leaves

Logger = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


# AnkiConnect can time out or become very slow on a single request covering
# a whole large deck (e.g. cardsInfo/notesInfo/addTags for 10,000+ cards or
# notes at once). Batching keeps each request small and lets progress be
# reported as it goes, instead of one huge, fragile, silent request.
_BATCH_SIZE = 500


def _batched(items: list, size: int = _BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _log_batch_progress(log: Logger, label: str, done: int, total: int) -> None:
    if total > _BATCH_SIZE:
        log(f"  {label} {done}/{total}...")


def find_cards(query: str, *, url: str) -> list[int]:
    return invoke("findCards", url=url, query=query)


def find_notes(query: str, *, url: str) -> list[int]:
    return invoke("findNotes", url=url, query=query)


def notes_info(note_ids: list[int], *, url: str, log: Logger = _noop) -> list[dict]:
    if not note_ids:
        return []
    out = []
    for batch in _batched(note_ids):
        out.extend(invoke("notesInfo", url=url, notes=batch))
        _log_batch_progress(log, "Fetched note info for", len(out), len(note_ids))
    return out


def add_tags(note_ids: list[int], tags: str, *, url: str, dry_run: bool, log: Logger = _noop) -> None:
    """Add one or more space-separated tags to every note in ``note_ids``."""
    if not note_ids or dry_run:
        return
    done = 0
    for batch in _batched(note_ids):
        invoke("addTags", url=url, notes=batch, tags=tags)
        done += len(batch)
        _log_batch_progress(log, "Tagged", done, len(note_ids))


def cards_info(card_ids: list[int], *, url: str, log: Logger = _noop) -> list[dict]:
    if not card_ids:
        return []
    out = []
    for batch in _batched(card_ids):
        out.extend(invoke("cardsInfo", url=url, cards=batch))
        _log_batch_progress(log, "Fetched card info for", len(out), len(card_ids))
    return out


def cards_for_note(note_id: int, *, url: str) -> list[int]:
    return find_cards(f"nid:{note_id}", url=url)


def get_stem_and_leaves(note_id: int, *, url: str) -> tuple[dict, list[dict]]:
    """Fetch every card on ``note_id`` and split it into (stem, leaves)."""
    card_ids = cards_for_note(note_id, url=url)
    if not card_ids:
        raise AnkiConnectError(f"Note {note_id} has no cards.")
    cards = cards_info(card_ids, url=url)
    return pick_stem_and_leaves(cards)


def set_flag(card_id: int, flag: int, *, url: str, dry_run: bool) -> None:
    if dry_run:
        return
    result = invoke(
        "setSpecificValueOfCard", url=url,
        card=card_id, keys=["flags"], newValues=[int(flag)], warning_check=True,
    )
    if result != [True]:
        raise AnkiConnectError(f"Could not set flag on card {card_id}: {result}")


def suspend(card_ids: list[int], *, url: str, dry_run: bool, log: Logger = _noop) -> None:
    if not card_ids or dry_run:
        return
    done = 0
    for batch in _batched(card_ids):
        invoke("suspend", url=url, cards=batch)
        done += len(batch)
        _log_batch_progress(log, "Suspended", done, len(card_ids))


def unsuspend(card_ids: list[int], *, url: str, dry_run: bool, log: Logger = _noop) -> None:
    if not card_ids or dry_run:
        return
    done = 0
    for batch in _batched(card_ids):
        invoke("unsuspend", url=url, cards=batch)
        done += len(batch)
        _log_batch_progress(log, "Un-suspended", done, len(card_ids))


def answer_again(card_ids: list[int], *, url: str, dry_run: bool, log: Logger = _noop) -> None:
    """Answer every card in ``card_ids`` as 'Again' (ease 1)."""
    if not card_ids or dry_run:
        return

    done = 0
    for batch in _batched(card_ids):
        answers = [{"cardId": card_id, "ease": 1} for card_id in batch]
        result = invoke("answerCards", url=url, answers=answers)

        if result is None:
            raise AnkiConnectError("answerCards returned no result.")

        failed = [
            (card_id, answer_result)
            for card_id, answer_result in zip(batch, result)
            if answer_result is not True
        ]
        if failed:
            raise AnkiConnectError(f"Some cards could not be answered: {failed}")

        done += len(batch)
        _log_batch_progress(log, "Answered", done, len(card_ids))
