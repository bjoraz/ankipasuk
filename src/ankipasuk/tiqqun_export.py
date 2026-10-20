"""What makes two tiqqun notes the same card, and the tiqqun CSV.

Tiqqun notes (note type :data:`ankipasuk.lpcg.MODEL_NAME`) don't store
which pasuq they're for, so a duplicate check has to work it out:

- **Pasuq mode** (one card per pasuq): the card is that pasuq's, key
  ``pasuq:<book> <ch>:<vs>``. For a new note it's known; for an existing
  one it's recovered from its tags and ``Sequence`` -- an 'ammud export's
  cards are the pesuqim starting on that 'ammud, in order, and an 'aliyya
  export's are the pesuqim of the range in its title.
- **Row mode** (a sliding window over the sefer's lines): the card is the
  lines it asks you to recite, key ``row:<their text>``.

Keys survive changes to the card's HTML and title between versions of the
app, which comparing the fields wouldn't. A note whose key can't be
recovered still counts as a duplicate of a new note with identical lines.
"""

from __future__ import annotations

import csv
import io
import re

from .anki_connect.tagging import HEBREW_TO_BOOK
from .cache import SefariaCache
from .config import BOOK_HEBREW_NAMES, TORAH_VERSE_COUNTS
from .lpcg import FIELD_NAMES, MODEL_NAME
from .qeriya import parse_range_ref
from .sefaria import get_chapter_lengths
from .tikkun import get_book_verses_on_amud

_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RANGE_RE = re.compile(r"\(([^()]+)\)\s*$")


def pasuq_key(book: str, ch: int, vs: int) -> str:
    return f"pasuq:{book} {ch}:{vs}"


def _text(html: str) -> str:
    return " ".join(_TAG_RE.sub(" ", html).replace("&nbsp;", " ").split())


def row_key(line_html: str) -> str:
    return f"row:{_text(line_html)}"


def content_key(fields: dict[str, str]) -> str:
    """The card's own lines, for notes whose pasuq can't be recovered."""
    return "lines:" + _text(fields.get("FrontRows", "") + " | " + fields.get("Line", ""))


def _range_pesuqim(book: str, start: tuple[int, int], end: tuple[int, int], cache: SefariaCache):
    counts = get_chapter_lengths(book, cache)
    ch, vs = start
    while (ch, vs) <= end:
        yield ch, vs
        vs += 1
        if vs > counts[ch - 1]:
            ch, vs = ch + 1, 1


def existing_note_key(fields: dict[str, str], tags: list[str], cache: SefariaCache) -> str | None:
    """The key of a tiqqun note already in Anki (see the module docstring),
    or ``None`` if it can't be worked out."""
    if fields.get("Line"):
        return row_key(fields["Line"])
    try:
        seq = int(fields.get("Sequence") or 0)
    except ValueError:
        return None
    if seq < 1:
        return None

    ammud = next((t.split("::", 1)[1] for t in tags if t.lower().startswith(("ammud::", "amud::"))), None)
    if ammud and ammud.isdigit():
        refs = get_book_verses_on_amud(int(ammud), cache)  # an 'ammud can hold two books
        if seq <= len(refs):
            return pasuq_key(*refs[seq - 1])
        return None

    m = _TITLE_RANGE_RE.search(fields.get("Title", ""))
    if not m:
        return None
    try:
        name, start, end = parse_range_ref(m.group(1))
    except ValueError:
        return None
    book = HEBREW_TO_BOOK.get(name) or (name if name in TORAH_VERSE_COUNTS else None)
    if book is None:
        return None
    for i, (ch, vs) in enumerate(_range_pesuqim(book, start, end, cache), 1):
        if i == seq:
            return pasuq_key(book, ch, vs)
    return None


def existing_keys(notes_info: list[dict], cache: SefariaCache) -> set[str]:
    """Every key (recovered and by content) of the tiqqun notes in Anki."""
    keys = set()
    for note in notes_info:
        fields = {name: f["value"] for name, f in note["fields"].items()}
        key = existing_note_key(fields, note.get("tags", []), cache)
        if key:
            keys.add(key)
        keys.add(content_key(fields))
    return keys


def pasuq_label(key: str) -> str | None:
    """A pasuq key as the card shows it: "pasuq:Genesis 1:3" -> "Bereshit
    1:3". ``None`` for any other key (a line-mode card's)."""
    if not key.startswith("pasuq:"):
        return None
    book, _space, ref = key[len("pasuq:"):].rpartition(" ")
    return f"{BOOK_HEBREW_NAMES.get(book, book)} {ref}"


def missing_pasuq_fields(notes_info: list[dict], cache: SefariaCache) -> list[tuple[int, str]]:
    """``(note id, "Bereshit 1:3")`` for each pasuq-mode tiqqun note in
    ``notes_info`` (AnkiConnect's ``notesInfo``) whose "Pasuq" field is
    empty -- notes made before the field existed -- with the pasuq worked
    out as for the duplicate check (see :func:`existing_note_key`). Notes
    whose pasuq can't be recovered, and line-mode notes, are left out."""
    found = []
    for note in notes_info:
        fields = {name: f["value"] for name, f in note["fields"].items()}
        if fields.get("Pasuq", "").strip():
            continue
        key = existing_note_key(fields, note.get("tags", []), cache)
        label = pasuq_label(key) if key else None
        if label:
            found.append((note["noteId"], label))
    return found


def is_duplicate(note: dict, keys: set[str]) -> bool:
    return note["key"] in keys or content_key(note["fields"]) in keys


def csv_text(notes: list[dict]) -> str:
    """The notes as an Anki CSV, its header naming the note type; the last
    two columns are each note's tags and deck. Fields hold HTML (and may
    span lines), so they're quoted as needed."""
    buf = io.StringIO()
    n = len(FIELD_NAMES)
    buf.write(
        f"#separator:tab\n#html:true\n#notetype:{MODEL_NAME}\n"
        f"#tags column:{n + 1}\n#deck column:{n + 2}\n"
    )
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
    for note in notes:
        writer.writerow(
            [note["fields"].get(name, "") for name in FIELD_NAMES] + [" ".join(note["tags"]), note["deck"]]
        )
    return buf.getvalue()
