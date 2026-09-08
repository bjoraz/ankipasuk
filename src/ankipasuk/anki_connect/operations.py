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


def ensure_model(
    model_name: str, fields: list[str], css: str, card_templates: list[dict], *, url: str,
) -> None:
    """Make sure an Anki note type named ``model_name`` exists, creating it
    via AnkiConnect's ``createModel`` if it doesn't. Idempotent: does
    nothing (no request beyond the existence check) if the model is
    already there, so it's safe to call before every export.

    Does not itself reconcile an existing model's fields/templates with
    what's passed in, matching AnkiConnect's own ``createModel``
    semantics -- see :func:`ensure_model_fields` and
    :func:`sync_model_templates` (and :func:`sync_model_css`) for that.
    """
    existing = invoke("modelNames", url=url)
    if model_name in existing:
        return
    invoke(
        "createModel", url=url,
        modelName=model_name,
        inOrderFields=fields,
        css=css,
        isCloze=False,
        cardTemplates=card_templates,
    )


def ensure_model_fields(model_name: str, fields: list[str], *, url: str) -> None:
    """Make sure ``model_name`` has exactly the fields in ``fields``, in
    this exact order -- via AnkiConnect's ``modelFieldAdd``, called once
    per field with its target index: that action both creates a field
    that doesn't exist yet AND repositions one that already does (real
    AnkiConnect's own implementation applies the ``index`` unconditionally
    whenever it's given, whether or not the field is new), so a single
    pass fixes both a missing field and one sitting in the wrong slot.

    Order matters because Anki refuses to create a note whose FIRST field
    (by the note type's own field order, not by name) is empty -- see
    :data:`ankipasuk.lpcg.FIELD_NAMES`'s own comment on why "Title" is
    listed first. Content in any field beyond that isn't touched.

    The field-list equivalent of :func:`sync_model_css`: a field added
    (or reordered) in this project's own note-type definition in a later
    version must still reach a note type an older version already
    created, not be silently invisible -- or, worse, leave the wrong
    field first -- on it forever.
    """
    for index, field in enumerate(fields):
        invoke("modelFieldAdd", url=url, modelName=model_name, fieldName=field, index=index)


def sync_model_templates(model_name: str, card_templates: list[dict], *, url: str) -> None:
    """Push each card template's Front/Back HTML unconditionally, whether
    the model already existed or :func:`ensure_model` just created it --
    the template equivalent of :func:`sync_model_css`, for the same
    reason: a later template fix must not be silently ignored forever by
    a note type an older version of this project already created.
    """
    templates = {t["Name"]: {"Front": t["Front"], "Back": t["Back"]} for t in card_templates}
    invoke("updateModelTemplates", url=url, model={"name": model_name, "templates": templates})


def sync_model_css(model_name: str, css: str, *, url: str) -> None:
    """Push ``css`` as ``model_name``'s note-type styling unconditionally,
    whether the model already existed or :func:`ensure_model` just created
    it. ``ensure_model`` (like AnkiConnect's own ``createModel``)
    deliberately never touches an existing model's styling, which means a
    styling change shipped in a later version of this project -- a font, a
    layout fix -- would otherwise be silently ignored forever by anyone
    whose note type was created by an older version. CSS-only, unlike a
    fields/templates change, can never corrupt existing card data, so it's
    always safe to push again on every export.
    """
    invoke("updateModelStyling", url=url, model={"name": model_name, "css": css})


def add_notes(
    notes: list[dict], *, url: str, dry_run: bool, log: Logger = _noop,
) -> list[int | None]:
    """Add a batch of full Anki notes (each a dict with ``deckName``,
    ``modelName``, ``fields``, and optionally ``tags``/``options``) via
    AnkiConnect's ``addNotes``. Returns one entry per input note: the new
    note ID, or ``None`` for any note AnkiConnect rejected (e.g. a
    duplicate) -- same shape ``addNotes`` itself returns, just batched.
    """
    if not notes:
        return []
    if dry_run:
        return [None] * len(notes)

    added: list[int | None] = []
    for batch in _batched(notes):
        result = invoke("addNotes", url=url, notes=batch)
        added.extend(result)
        _log_batch_progress(log, "Added", len(added), len(notes))
    return added


def ensure_media_file(filename: str, data_base64: str, *, url: str) -> None:
    """Make sure ``filename`` exists in Anki's media collection with this
    exact content, uploading it via AnkiConnect's ``storeMediaFile`` if it
    doesn't already. Idempotent: does nothing (no upload request) if the
    file is already there -- safe to call before every export even for a
    large font file.

    Does not attempt to reconcile a same-named file with *different*
    content already in the collection (e.g. hand-replaced by the user) --
    it's left as-is, matching :func:`ensure_model`'s own semantics for a
    same-named model.
    """
    existing = invoke("retrieveMediaFile", url=url, filename=filename)
    if existing:
        return
    invoke("storeMediaFile", url=url, filename=filename, data=data_base64)


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
