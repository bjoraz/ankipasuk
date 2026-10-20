"""Turning fetched pesuqim into cloze notes, for both ways of exporting
them: a CSV file to import into Anki, or straight into Anki through
AnkiConnect. Both go through :func:`build_cloze_notes`, so a pasuq gets the
same fields and tags either way.

One note per pasuq. The fields, in order, are the ones the CSV has always
had (``FIELD_NAMES``); a note type receiving them directly must start with
those fields in that order. The tags are the qeriya tags the tagger would
compute (Tora pesuqim, see :mod:`ankipasuk.qeriya`) plus a
``haftara::<slug>`` tag for every haftara the pasuq belongs to.
"""

from __future__ import annotations

from .cache import SefariaCache
from .cloze import verse_to_nested_cloze
from .config import BOOK_HEBREW_NAMES, CSV_FLAGS, TORAH_VERSE_COUNTS
from .qeriya import (
    build_holiday_intervals,
    build_parasha_intervals,
    haftara_tags_for_verse,
    tags_for_verse,
    verse_index,
)
from .sefaria import get_chapter_lengths, get_parasha_structure

# The first six must match a note type's first six fields by name (see
# check_note_type_fields); the last two are filled by position, since the
# note type's own name for the settings field varies.
FIELD_NAMES = ["Number", "Source", "Text", "Verse", "Previous", "Next", "Back Extra", "Settings"]
NAMED_FIELDS = FIELD_NAMES[:6]


def source_label(item: dict) -> str:
    """The Source field: book as AnkiPasuk writes it, then chapter:verse."""
    return f"{BOOK_HEBREW_NAMES.get(item['book'], item['book'])} {item['ch']}:{item['vs']}"


def qeriya_context(books: set[str], cache: SefariaCache) -> dict:
    """Per Tora book: live chapter lengths and the interval tables the
    tagger uses, so exported tags match what ankipasuk-tag-deck computes.
    Shared with the tiqqun export (see :func:`qeriya_tags`)."""
    context = {}
    for book in books & set(TORAH_VERSE_COUNTS):
        counts = get_chapter_lengths(book, cache)
        context[book] = {
            "counts": counts,
            "parashot": build_parasha_intervals(book, get_parasha_structure(book, cache), counts),
            "holidays": build_holiday_intervals({book: counts}),
        }
    return context


def qeriya_tags(context: dict, book: str, ch: int, vs: int) -> list[str]:
    """The parasha/'aliyya/holiday tags of a Tora pasuq, from a
    :func:`qeriya_context` covering its book; ``[]`` for any other book."""
    c = context.get(book)
    if c is None:
        return []
    return tags_for_verse(book, ch, vs, c["parashot"], c["holidays"], c["counts"])


def build_cloze_notes(
    verse_data: list[dict], max_leaf_disj: int, reset_per_line: bool, cache: SefariaCache,
) -> list[dict]:
    """``{"key", "fields", "tags"}`` for each non-blank pasuq in
    ``verse_data`` (the fetched ranges, in order). ``key`` is
    ``(book, ch, vs)``; ``fields`` follows ``FIELD_NAMES``.

    ``Number`` is the pasuq's position in its book for the Tora (Bereshit
    1:1 is 1), its position in the haftara for a haftara, and its position
    in the export otherwise. ``Previous``/``Next`` are the neighbouring
    pesuqim as fetched, but a haftara's never reach outside it."""
    max_leaf_disj = max(1, max_leaf_disj)
    context = qeriya_context({item["book"] for item in verse_data}, cache)
    items = [item for item in verse_data if item["pointed"].strip()]

    def neighbour(i: int, j: int) -> str:
        """Pasuq j's plain text if it's read together with pasuq i."""
        if 0 <= j < len(items) and items[j].get("haftara") == items[i].get("haftara"):
            return items[j]["plain"]
        return ""

    notes = []
    next_start = 1
    for i, item in enumerate(items):
        book, ch, vs = item["book"], item["ch"], item["vs"]
        start = 1 if reset_per_line else next_start
        cloze, last, *_ = verse_to_nested_cloze(item["pointed"].strip(), start, max_leaf_disj)
        if not reset_per_line:
            next_start = last + 1

        tags = []
        if book in context:
            c = context[book]
            number = verse_index(book, ch, vs, c["counts"]) + 1
            tags += qeriya_tags(context, book, ch, vs)
        elif "haftara_pos" in item:
            number = item["haftara_pos"]
        else:
            number = i + 1
        tags += [t for t in haftara_tags_for_verse(book, ch, vs) if t not in tags]

        notes.append({
            "key": (book, ch, vs),
            "fields": [
                str(number), source_label(item), cloze, item["plain"],
                neighbour(i, i - 1), neighbour(i, i + 1), "", CSV_FLAGS,
            ],
            "tags": tags,
        })
    return notes


def csv_rows(notes: list[dict]) -> list[list[str]]:
    """One row per note: the fields, then the tags space-separated (the
    column Anki's ``#tags column`` header points at)."""
    return [note["fields"] + [" ".join(note["tags"])] for note in notes]


CSV_HEADER = f"#separator:tab\n#tags column:{len(FIELD_NAMES) + 1}\n"


def check_note_type_fields(field_names: list[str]) -> str | None:
    """``None`` if a note type with these fields can take the notes, else
    why not."""
    if field_names[: len(NAMED_FIELDS)] != NAMED_FIELDS or len(field_names) < len(FIELD_NAMES):
        return (
            f"The note type's fields must start with {', '.join(NAMED_FIELDS)}, then two more "
            f"(back extra and settings); it has: {', '.join(field_names) or 'none'}."
        )
    return None


def anki_fields(note: dict, field_names: list[str]) -> dict[str, str]:
    """``note``'s fields keyed by the note type's own field names, by
    position. Fields past the eighth (e.g. a Sound field) are left out,
    so Anki leaves them empty."""
    return dict(zip(field_names[: len(FIELD_NAMES)], note["fields"]))
