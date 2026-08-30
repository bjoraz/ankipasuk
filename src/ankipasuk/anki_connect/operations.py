"""AnkiConnect-backed operations: searching, flagging, suspending, and
answering cards. Thin wrappers around :func:`ankipasuk.anki_connect.client.invoke`,
kept separate from the scheduling policy in :mod:`ankipasuk.anki_connect.scheduling`
so each can be tested independently.
"""

from __future__ import annotations

from .client import AnkiConnectError, invoke
from .notes import pick_stem_and_leaves


def find_cards(query: str, *, url: str) -> list[int]:
    return invoke("findCards", url=url, query=query)


def cards_info(card_ids: list[int], *, url: str) -> list[dict]:
    if not card_ids:
        return []
    return invoke("cardsInfo", url=url, cards=card_ids)


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


def suspend(card_ids: list[int], *, url: str, dry_run: bool) -> None:
    if not card_ids or dry_run:
        return
    invoke("suspend", url=url, cards=card_ids)


def unsuspend(card_ids: list[int], *, url: str, dry_run: bool) -> None:
    if not card_ids or dry_run:
        return
    invoke("unsuspend", url=url, cards=card_ids)


def answer_again(card_ids: list[int], *, url: str, dry_run: bool) -> None:
    """Answer every card in ``card_ids`` as 'Again' (ease 1)."""
    if not card_ids or dry_run:
        return

    answers = [{"cardId": card_id, "ease": 1} for card_id in card_ids]
    result = invoke("answerCards", url=url, answers=answers)

    if result is None:
        raise AnkiConnectError("answerCards returned no result.")

    failed = [
        (card_id, answer_result)
        for card_id, answer_result in zip(card_ids, result)
        if answer_result is not True
    ]
    if failed:
        raise AnkiConnectError(f"Some cards could not be answered: {failed}")
