"""Automatic parasha/aliyah/Maftir/holiday tagging.

Reads each note's "Source" field (e.g. ``"Bereshit 1:1"``, as produced by
the CSV export), computes the tags that verse should have (see
:mod:`ankipasuk.leyning`), and adds any that are missing.

Existing tags are **never removed or overwritten**. If a note already has
a tag that looks like one this tool would generate (``aliyah::...`` or
``holiday::...``) but it doesn't match what was just computed, that's
reported as a conflict for you to review by hand -- it is not silently
changed. This makes the tool safe to run repeatedly and safe to run on a
deck (like this one) that already has some tags applied by hand.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from ..cache import SefariaCache
from ..config import BOOK_HEBREW_NAMES
from ..leyning import build_holiday_intervals, build_parasha_intervals, tags_for_verse
from ..sefaria import get_chapter_lengths, get_parasha_structure
from .operations import add_tags, find_notes, notes_info

HEBREW_TO_BOOK = {v: k for k, v in BOOK_HEBREW_NAMES.items()}

_SOURCE_RE = re.compile(r"^(?P<book>.+?)\s+(?P<ch>\d+):(?P<vs>\d+)$")

# Any existing tag starting with one of these prefixes is treated as "ours"
# for conflict detection -- i.e. it's meaningful to compare it against what
# we'd compute, rather than just leaving it alone as an unrelated tag.
_OWNED_PREFIXES = ("aliyah::", "holiday::")


def parse_source_field(source: str):
    """Parse a "Source" field like "Bereshit 1:1" into (book, ch, vs), using
    English book names. Returns None if it doesn't look like a Torah verse
    reference (e.g. blank, or a non-Torah book)."""
    m = _SOURCE_RE.match(source.strip())
    if not m:
        return None
    book = HEBREW_TO_BOOK.get(m.group("book"))
    if book is None:
        return None
    return book, int(m.group("ch")), int(m.group("vs"))


@dataclass
class NotePlan:
    note_id: int
    source: str
    book: str
    ch: int
    vs: int
    computed_tags: list[str]
    existing_tags: list[str]
    missing_tags: list[str] = field(default_factory=list)
    conflicting_tags: list[str] = field(default_factory=list)


@dataclass
class TaggingPlan:
    notes: list[NotePlan]
    unparsed_note_ids: list[int]

    @property
    def notes_needing_tags(self) -> list[NotePlan]:
        return [n for n in self.notes if n.missing_tags]

    @property
    def notes_with_conflicts(self) -> list[NotePlan]:
        return [n for n in self.notes if n.conflicting_tags]

    def summary(self) -> dict:
        return {
            "total_notes": len(self.notes),
            "unparsed_notes": len(self.unparsed_note_ids),
            "notes_needing_tags": len(self.notes_needing_tags),
            "total_tags_to_add": sum(len(n.missing_tags) for n in self.notes),
            "notes_with_conflicts": len(self.notes_with_conflicts),
        }


def _books_present(plans: list[tuple]) -> set[str]:
    return {book for _nid, _source, book, _ch, _vs in plans}


def compute_tagging_plan(deck: str, *, url: str, cache: SefariaCache, log=lambda _msg: None) -> TaggingPlan:
    """Fetch every note in ``deck``, compute its tags, and diff against
    what's already there. Makes no changes -- see :func:`apply_tagging_plan`."""
    note_ids = find_notes(f"deck:{deck}", url=url)
    log(f"Found {len(note_ids)} note(s) in {deck}.")
    infos = notes_info(note_ids, url=url, log=log)

    parsed = []
    unparsed = []
    for info in infos:
        fields = info.get("fields", {})
        source_field = fields.get("Source", {}).get("value", "")
        parsed_ref = parse_source_field(source_field)
        if parsed_ref is None:
            unparsed.append(info["noteId"])
            continue
        book, ch, vs = parsed_ref
        parsed.append((info["noteId"], source_field, book, ch, vs, info.get("tags", [])))

    books_needed = {book for _nid, _src, book, _ch, _vs, _tags in parsed}
    parasha_intervals_by_book = {}
    chapter_counts_by_book = {}
    for book in books_needed:
        log(f"Fetching current chapter structure for {book} (cached after first run)...")
        chapter_counts_by_book[book] = get_chapter_lengths(book, cache)
        sefaria_parashot = get_parasha_structure(book, cache)
        parasha_intervals_by_book[book] = build_parasha_intervals(
            book, sefaria_parashot, chapter_counts_by_book[book]
        )
    holiday_intervals = build_holiday_intervals(chapter_counts_by_book)

    plans = []
    for note_id, source, book, ch, vs, existing_tags in parsed:
        computed = tags_for_verse(
            book, ch, vs, parasha_intervals_by_book[book], holiday_intervals,
            chapter_counts_by_book[book],
        )
        existing_set = set(existing_tags)
        missing = [t for t in computed if t not in existing_set]

        owned_existing = {t for t in existing_tags if t.startswith(_OWNED_PREFIXES)}
        conflicting = sorted(owned_existing - set(computed))

        plans.append(NotePlan(
            note_id=note_id, source=source, book=book, ch=ch, vs=vs,
            computed_tags=computed, existing_tags=existing_tags,
            missing_tags=missing, conflicting_tags=conflicting,
        ))

    return TaggingPlan(notes=plans, unparsed_note_ids=unparsed)


def apply_tagging_plan(plan: TaggingPlan, *, url: str, dry_run: bool, log=lambda _msg: None) -> dict:
    """Add every missing tag from ``plan``. Groups notes by their exact set
    of missing tags so each distinct combination is a single ``addTags``
    call rather than one call per note."""
    by_tagset: dict[str, list[int]] = defaultdict(list)
    for note in plan.notes_needing_tags:
        tagset = " ".join(sorted(note.missing_tags))
        by_tagset[tagset].append(note.note_id)

    for tagset, note_ids in by_tagset.items():
        log(f"TAG   {len(note_ids)} note(s) -> {tagset}")
        add_tags(note_ids, tagset, url=url, dry_run=dry_run, log=log)

    for note in plan.notes_with_conflicts:
        log(
            f"CONFLICT  note {note.note_id} ({note.source}): existing "
            f"{note.conflicting_tags} not in computed {note.computed_tags} -- left untouched"
        )

    return plan.summary()
