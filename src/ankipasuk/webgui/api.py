"""The Python side of the web GUI: a thin API surface exposed to the
JavaScript frontend via pywebview's JS-to-Python bridge
(``window.pywebview.api.<method>(...)`` in JS calls the method of the same
name here).

Every method here is a thin wrapper around the same core logic the
original Tk GUI used (``sefaria.py``, ``cloze.py``, ``text_processing.py``,
``stats.py``, ``structure.py``, ``qeriya.py``, ``anki_connect/*``) --
nothing here reimplements any business logic, it only adapts calling
conventions (Python objects in, JSON-serializable dicts/lists out) for the
JS side to consume.
"""

from __future__ import annotations

import csv
import io
import traceback
from pathlib import Path

import webview

from ..ammud_pages import ammud_pages_html
from ..ammud_pages import write_pdf as write_ammud_pages_pdf
from ..anki_connect import client as anki_client
from ..anki_connect.client import DEFAULT_URL, AnkiConnectError
from ..anki_connect.operations import add_notes as anki_add_notes
from ..anki_connect.operations import ensure_deck as anki_ensure_deck
from ..anki_connect.operations import ensure_media_file as anki_ensure_media_file
from ..anki_connect.operations import ensure_model as anki_ensure_model
from ..anki_connect.operations import ensure_model_fields as anki_ensure_model_fields
from ..anki_connect.operations import find_notes as anki_find_notes
from ..anki_connect.operations import notes_info as anki_notes_info
from ..anki_connect.operations import sync_model_css as anki_sync_model_css
from ..anki_connect.operations import sync_model_templates as anki_sync_model_templates
from ..anki_connect.tagging import parse_source_field
from ..cache import SefariaCache
from ..cloze import verse_to_nested_cloze
from ..cloze_export import (
    CSV_HEADER,
    anki_fields,
    build_cloze_notes,
    check_note_type_fields,
    csv_rows,
    qeriya_context,
    qeriya_tags,
    source_label,
)
from ..config import (
    BOOK_CATEGORIES,
    BOOK_HEBREW_NAMES,
    BOOK_HEBREW_SCRIPT_NAMES,
    POINTED_VERSION,
    QERIYA_DECK_NAMES,
)
from ..diagram import pasuq_diagram
from ..lpcg import CARD_TEMPLATES, build_lpcg_fields, render_scroll_html
from ..lpcg import CSS as LPCG_CSS
from ..lpcg import FIELD_NAMES as LPCG_FIELD_NAMES
from ..lpcg import MODEL_NAME as LPCG_MODEL_NAME
from ..lpcg import SCROLL_CSS as LPCG_SCROLL_CSS
from ..qeriya import (
    haftara_label,
    haftara_table,
    parasha_names,
    parse_range_ref,
    tiqqun_ammud_deck,
    tiqqun_ammud_tag,
)
from ..sefaria import (
    fetch_verse_range,
    get_aliyah_ref,
    get_book_structure,
    get_parasha_structure,
    get_text_for_ref,
    parse_start_ref,
)
from ..settings import Settings
from ..text_processing import strip_vowels_and_trope
from ..tikkun import (
    FONT_ANKI_FILENAME,
    get_amud_lines,
    get_book_for_page,
    get_book_verses_on_amud,
    get_font_base64,
    get_scroll_lines_for_range,
)
from ..tiqqun_export import content_key as tiqqun_content_key
from ..tiqqun_export import csv_text as tiqqun_csv_text
from ..tiqqun_export import existing_keys as tiqqun_existing_keys
from ..tiqqun_export import is_duplicate as tiqqun_is_duplicate
from ..tiqqun_export import pasuq_key as tiqqun_pasuq_key
from ..tiqqun_export import row_key as tiqqun_row_key
from ..verse_cards import build_amud_verse_cards
from .anki_connect_api import AnkiConnectApi
from .stats_api import StatsApi

_STATIC_DIR = Path(__file__).parent / "static"


class Api:
    """Holds the mutable state a session needs (cache, accumulated verse
    data) -- one instance is created per app run and shared by every JS
    call, mirroring how ``AnkiPasukApp`` held this as instance state.

    Verse data accumulates across calls to fetch_chapter_verse /
    fetch_parashah_aliyah rather than being replaced -- each call appends
    its verses (each stamped with its own "book") to the same running
    list, so a session can concatenate ranges from different books (e.g.
    the end of Genesis plus the start of Exodus) simply by fetching each
    range in turn. clear_ranges() resets back to empty.

    The tikkun.io scroll-style HTML (see _tikkun_html_for_range)
    accumulates the same way, in _current_tikkun_html -- one growing
    HTML string per side (plain/pointed), rather than a per-verse list,
    since a single tikkun.io "line" doesn't correspond 1:1 with a verse.
    """

    def __init__(self) -> None:
        self._cache = SefariaCache()
        self._settings = Settings()
        self._current_verse_data: list[dict] = []
        self._current_tikkun_html: dict[str, str] = {"plain": "", "pointed": ""}
        self._window: webview.Window | None = None

    # =============================================================
    #  Static reference data (no network)
    # =============================================================
    def get_books(self) -> dict[str, list[str]]:
        """{"Tora": [...], "Nevi'im": [...], "Megillot": [...]} -- the
        frontend uses this to build a book <select> with one <optgroup>
        per category."""
        return BOOK_CATEGORIES

    def get_book_labels(self) -> dict[str, str]:
        """How each book is shown in the pickers, e.g. "Bereshit · בראשית".
        The option values stay the English names Sefaria uses."""
        return {
            book: f"{BOOK_HEBREW_NAMES[book]} · {BOOK_HEBREW_SCRIPT_NAMES[book]}"
            for books in BOOK_CATEGORIES.values() for book in books
        }

    def get_chapter_count(self, book: str) -> dict:
        try:
            return {"ok": True, "count": len(get_book_structure(book, self._cache))}
        except Exception as e:  # noqa: BLE001 - reported to the JS side
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def get_verse_count(self, book: str, chapter: int) -> dict:
        try:
            counts = get_book_structure(book, self._cache)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        count = counts[chapter - 1] if 1 <= chapter <= len(counts) else 1
        return {"ok": True, "count": count}

    # =============================================================
    #  Live Sefaria data (network on first call per book, cached after)
    # =============================================================
    def get_parashot(self, book: str) -> dict:
        """{"ok": True, "names": [...], "labels": [...]} or {"ok": False,
        "error": "..."}. ``names`` are Sefaria's, and are what the frontend
        sends back (they're the keys every other call looks parashiyyot up
        by); ``labels`` are the same parashiyyot as AnkiPasuk writes them
        (see docs/transliteration.md and :func:`ankipasuk.qeriya.parasha_names`),
        for display only."""
        try:
            parashot = get_parasha_structure(book, self._cache)
            names = [p["name"] for p in parashot]
            ours = parasha_names(book, parashot)
            labels = [ours[n]["name"] if n in ours else n for n in names]
            return {"ok": True, "names": names, "labels": labels}
        except Exception as e:  # noqa: BLE001 - reported to the JS side
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def get_aliyah_count(self, book: str, parasha_name: str) -> dict:
        try:
            parashot = get_parasha_structure(book, self._cache)
            for p in parashot:
                if p["name"] == parasha_name:
                    return {"ok": True, "count": len(p["refs"])}
            return {"ok": True, "count": 0}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    # =============================================================
    #  Fetching verse text
    # =============================================================
    def fetch_chapter_verse(
        self, book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int
    ) -> dict:
        """Fetch one range and APPEND it to the accumulated verse data
        (does not replace what's already there -- see clear_ranges to
        start over). Returns the full accumulated list so far, so the
        frontend can just replace its display with result["verses"]."""
        try:
            new_verses = fetch_verse_range(
                book, start_ch, start_vs, end_ch, end_vs, self._cache, POINTED_VERSION
            )
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        self._current_verse_data.extend(new_verses)
        return {"ok": True, "verses": self._current_verse_data, "cache_status": self._cache_status_text()}

    def fetch_parashah_aliyah(self, book: str, parasha_name: str, aliyah_num: int) -> dict:
        """Like fetch_chapter_verse, but for a named parasha/'aliyya
        (Tora only -- parashiyyot don't exist for Nevi'im or the
        Megillot). Also appends to the accumulated verse data."""
        try:
            ref_str = get_aliyah_ref(book, parasha_name, aliyah_num, self._cache)
            pointed_verses = get_text_for_ref(ref_str, POINTED_VERSION, self._cache)
            start_ch, start_vs = parse_start_ref(ref_str)
            chapter_lengths = get_book_structure(book, self._cache)

            new_verses = []
            ch, vs = start_ch, start_vs
            for pointed in pointed_verses:
                plain = strip_vowels_and_trope(pointed)
                new_verses.append({"book": book, "ch": ch, "vs": vs, "pointed": pointed, "plain": plain})
                vs += 1
                if ch <= len(chapter_lengths) and vs > chapter_lengths[ch - 1]:
                    vs = 1
                    ch += 1
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        self._current_verse_data.extend(new_verses)
        return {"ok": True, "verses": self._current_verse_data, "cache_status": self._cache_status_text()}

    def get_haftarot(self) -> dict:
        """The haftarot for the picker, grouped: each parasha's, then the
        special and intermediate Shabbatot (see data/haftarot.json)."""
        groups = {"parasha": [], "special": []}
        for entry in haftara_table():
            groups[entry["kind"]].append({"slug": entry["slug"], "label": haftara_label(entry)})
        return {"ok": True, "groups": [
            {"label": "Parashiyyot", "items": groups["parasha"]},
            {"label": "Special Shabbatot", "items": groups["special"]},
        ]}

    def fetch_haftara(self, slug: str) -> dict:
        """Fetch every range of one haftara, in order, and append it like
        fetch_chapter_verse does. Each pasuq is marked with the haftara and
        its position in it, which the exports use (see
        ankipasuk.cloze_export.build_cloze_notes)."""
        entry = next((e for e in haftara_table() if e["slug"] == slug), None)
        if entry is None:
            return {"ok": False, "error": f"Unknown haftara: {slug}"}
        try:
            new_verses = []
            for ref in entry["refs"]:
                book, (c1, v1), (c2, v2) = parse_range_ref(ref)
                new_verses += fetch_verse_range(book, c1, v1, c2, v2, self._cache, POINTED_VERSION)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        for pos, verse in enumerate(new_verses, 1):
            verse["haftara"] = slug
            verse["haftara_pos"] = pos
        self._current_verse_data.extend(new_verses)
        return {"ok": True, "verses": self._current_verse_data, "cache_status": self._cache_status_text()}

    # =============================================================
    #  Tikkun-style scroll display for the source section (Tora only --
    #  a deliberately SEPARATE call from fetch_chapter_verse /
    #  fetch_parashah_aliyah above, not folded into them: those two are
    #  the core verse-fetch path everything else (cloze generation, CSV
    #  export) depends on, and must stay usable -- and testable without
    #  a tikkun.io round-trip -- even when this display is never shown.
    # =============================================================
    def fetch_tikkun_chapter_verse(
        self, book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int,
    ) -> dict:
        """Like fetch_chapter_verse, but fetches and APPENDS this range's
        tikkun.io scroll-style HTML instead (see _tikkun_html_for_range)
        -- call alongside fetch_chapter_verse for the same range, not
        instead of it. A range outside the Tora is a harmless no-op
        (nothing appended, still "ok") -- tikkun.io simply has nothing to
        show there."""
        try:
            tikkun = self._tikkun_html_for_range(book, start_ch, start_vs, end_ch, end_vs)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        if tikkun is not None:
            plain_html, pointed_html = tikkun
            self._current_tikkun_html["plain"] += plain_html
            self._current_tikkun_html["pointed"] += pointed_html
        return self._tikkun_fetch_result()

    def fetch_tikkun_parashah_aliyah(self, book: str, parasha_name: str, aliyah_num: int) -> dict:
        """Like fetch_tikkun_chapter_verse, but for a named parasha/
        'aliyya -- call alongside fetch_parashah_aliyah for the same
        range."""
        try:
            ref_str = get_aliyah_ref(book, parasha_name, aliyah_num, self._cache)
            start_ch, start_vs = parse_start_ref(ref_str)
            verse_count = len(get_text_for_ref(ref_str, POINTED_VERSION, self._cache))
            chapter_lengths = get_book_structure(book, self._cache)

            end_ch, end_vs = start_ch, start_vs
            for _ in range(verse_count - 1):
                end_vs += 1
                if end_ch <= len(chapter_lengths) and end_vs > chapter_lengths[end_ch - 1]:
                    end_vs = 1
                    end_ch += 1

            tikkun = self._tikkun_html_for_range(book, start_ch, start_vs, end_ch, end_vs)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        if tikkun is not None:
            plain_html, pointed_html = tikkun
            self._current_tikkun_html["plain"] += plain_html
            self._current_tikkun_html["pointed"] += pointed_html
        return self._tikkun_fetch_result()

    def _tikkun_html_for_range(
        self, book: str, start_ch: int, start_vs: int, end_ch: int, end_vs: int,
    ) -> tuple[str, str] | None:
        """The tikkun.io scroll-style (plain, pointed) HTML for this
        range, or None if tikkun.io has no layout data for ``book``
        (Nevi'im and the Megillot aren't the Tora) -- the source
        section's own tikkun display simply has nothing to add for such
        a range, rather than erroring the whole fetch."""
        try:
            plain_lines = get_scroll_lines_for_range(book, start_ch, start_vs, end_ch, end_vs, self._cache)
            pointed_lines = get_scroll_lines_for_range(
                book, start_ch, start_vs, end_ch, end_vs, self._cache, pointed=True,
            )
        except ValueError:
            return None
        return render_scroll_html(plain_lines), render_scroll_html(pointed_lines)

    def _tikkun_fetch_result(self) -> dict:
        return {
            "ok": True,
            "plain_html": self._current_tikkun_html["plain"],
            "pointed_html": self._current_tikkun_html["pointed"],
        }

    def get_tikkun_scroll_css(self) -> str:
        """The tikkun-style scroll layout's own CSS (box/line/setuma
        structure -- see :data:`ankipasuk.lpcg.SCROLL_CSS`), for the
        frontend to inject once alongside the STAM font (see
        get_tikkun_font_css) so the HTML from fetch_chapter_verse /
        fetch_parashah_aliyah renders correctly outside Anki too."""
        return LPCG_SCROLL_CSS

    def get_tikkun_font_css(self) -> dict:
        """The STAM font as a ``@font-face`` rule with the font itself
        embedded as a base64 data URI (fetched live and cached forever
        after, like everything else in :mod:`ankipasuk.tikkun`) -- so the
        webgui can render tikkun-style text with the same font an Anki
        card does, without needing a font file checked into the repo or
        served as a separate static asset."""
        try:
            font_base64 = get_font_base64(self._cache)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        css = (
            '@font-face { font-family: "ShlomosemiStam"; '
            f'src: url(data:font/ttf;base64,{font_base64}); }} '
            '.lines { font-family: "ShlomosemiStam", "SBL Hebrew", '
            '"Ezra SIL", "Noto Serif Hebrew", arial; }'
        )
        return {"ok": True, "css": css}

    def clear_ranges(self) -> dict:
        """Discard all accumulated verse data (and any accumulated tikkun
        scroll HTML, see fetch_tikkun_chapter_verse), starting a fresh
        session."""
        self._current_verse_data = []
        self._current_tikkun_html = {"plain": "", "pointed": ""}
        return {"ok": True, "verses": self._current_verse_data}

    def _cache_status_text(self) -> str:
        s = self._cache.stats()
        return (
            f"Cache: {s['cached_refs']} ref(s), {s['cached_books']} book structure(s), "
            f"{s['cached_tikkun_pages']} tikkun.io page(s)"
        )

    def get_cache_status(self) -> str:
        return self._cache_status_text()

    def clear_cache(self) -> dict:
        self._cache.clear()
        return {"ok": True, "cache_status": self._cache_status_text()}

    # =============================================================
    #  Cloze generation
    # =============================================================
    def generate_cloze(self, max_leaf_disj: int, reset_per_line: bool) -> dict:
        if not self._current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}

        max_leaf_disj = max(1, max_leaf_disj)
        lines = []
        diagrams = []
        next_start = 1

        for item in self._current_verse_data:
            v = item["pointed"].strip()
            if not v:
                continue

            start_counter = 1 if reset_per_line else next_start
            cl, last, _tree, _tok, _units = verse_to_nested_cloze(
                v, start_counter=start_counter, max_leaf_disj=max_leaf_disj
            )
            lines.append(cl)
            diagrams.append({"ref": source_label(item), "diagram": pasuq_diagram(v, max_leaf_disj)})

            if not reset_per_line:
                next_start = last + 1

        return {
            "ok": True,
            "output": "\n".join(lines),
            # One entry per pasuq for the diagram and the list of groups
            # (static/diagram.js); greyed brackets mark the divisions the
            # cards don't make at this max_leaf_disj.
            "diagrams": diagrams,
        }

    # =============================================================
    #  CSV export
    # =============================================================
    def export_csv(self, max_leaf_disj: int, reset_per_line: bool) -> dict:
        if not self._current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}
        try:
            notes = build_cloze_notes(self._current_verse_data, max_leaf_disj, reset_per_line, self._cache)
        except Exception as e:  # noqa: BLE001 - e.g. Sefaria unreachable for the tags
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        rows = csv_rows(notes)

        if not rows:
            return {"ok": False, "error": "No verse lines were found to export."}

        if self._window is None:
            return {"ok": False, "error": "Window not ready."}

        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="cloze_cards.csv",
            file_types=("CSV files (*.csv)", "All files (*.*)"),
        )
        if not path:
            return {"ok": False, "error": None}  # user cancelled, not a real error

        target = path if isinstance(path, str) else path[0]
        try:
            buf = io.StringIO()
            buf.write(CSV_HEADER)  # tells Anki the separator and which column holds the tags
            writer = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
            writer.writerows(rows)
            with open(target, "w", encoding="utf-8-sig", newline="") as f:
                f.write(buf.getvalue())
        except OSError as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "count": len(rows), "path": target}

    # =============================================================
    #  'Aliyya recitation export (overlapping-context notes, pushed
    #  directly to Anki via AnkiConnect)
    # =============================================================


    # =============================================================
    #  Cloze export straight to Anki (AnkiConnect)
    # =============================================================
    def suggest_cloze_deck(self) -> str:
        """A deck for the fetched pesuqim: the book's Qeriya deck for the
        Tora, Qeriya::Haftarot for a haftara, else the last one used."""
        first = self._current_verse_data[0] if self._current_verse_data else None
        if first and "haftara" in first:
            return "Qeriya::Haftarot"
        if first and first["book"] in QERIYA_DECK_NAMES:
            return QERIYA_DECK_NAMES[first["book"]]
        return self._settings.get("cloze_deck_name", "Qeriya")

    def anki_status(self) -> dict:
        """Whether Anki is open with AnkiConnect -- a cheap check the main
        window repeats, to show it and to know when to load note types."""
        try:
            anki_client.invoke("version", url=DEFAULT_URL, timeout=3)
        except AnkiConnectError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def get_cloze_note_types(self) -> dict:
        """Note types in Anki that can take cloze notes (see
        cloze_export.check_note_type_fields), and the one to preselect:
        the last used, if it's still there."""
        try:
            names = anki_client.invoke("modelNames", url=DEFAULT_URL)
            usable = [n for n in names if check_note_type_fields(self._note_type_fields(n)) is None]
        except AnkiConnectError as e:
            return {"ok": False, "error": str(e)}
        last = self._settings.get("cloze_note_type")
        selected = last if last in usable else (usable[0] if usable else None)
        return {"ok": True, "names": usable, "selected": selected}

    @staticmethod
    def _note_type_fields(note_type: str) -> list[str]:
        return anki_client.invoke("modelFieldNames", url=DEFAULT_URL, modelName=note_type)

    def export_cloze_to_anki(
        self, max_leaf_disj: int, reset_per_line: bool, deck_name: str, note_type: str,
    ) -> dict:
        """Add the fetched pesuqim to Anki as cloze notes, with the same
        fields and tags as the CSV export.

        Only pesuqim with no note yet (of this note type, anywhere in the
        collection, matched on Source) are added. Existing notes are never
        changed, so their scheduling and anything added to them by hand --
        a recording in a Sound field, say -- are safe. Re-running an export
        only fills in what's missing."""
        if not self._current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}
        deck_name = deck_name.strip()
        if not deck_name or not note_type:
            return {"ok": False, "error": "Choose a deck and a note type first."}
        try:
            notes = build_cloze_notes(self._current_verse_data, max_leaf_disj, reset_per_line, self._cache)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        if not notes:
            return {"ok": False, "error": "No verse lines were found to export."}

        try:
            field_names = self._note_type_fields(note_type)
            problem = check_note_type_fields(field_names)
            if problem:
                return {"ok": False, "error": problem}
            existing_ids = anki_find_notes(f'"note:{note_type}"', url=DEFAULT_URL)
            existing = {
                parse_source_field(n["fields"].get("Source", {}).get("value", ""))
                for n in anki_notes_info(existing_ids, url=DEFAULT_URL)
            }
            new = [n for n in notes if n["key"] not in existing]
            anki_ensure_deck(deck_name, url=DEFAULT_URL)
            payload = [{
                "deckName": deck_name, "modelName": note_type,
                "fields": anki_fields(n, field_names), "tags": n["tags"],
                # Our own Source check above is the duplicate check; Anki's
                # (on the first field, Number) would wrongly match pesuqim
                # with the same number in different books.
                "options": {"allowDuplicate": True},
            } for n in new]
            result_ids = anki_add_notes(payload, url=DEFAULT_URL, dry_run=False) if payload else []
        except AnkiConnectError as e:
            return {"ok": False, "error": str(e)}

        self._settings.set("cloze_deck_name", deck_name)
        self._settings.set("cloze_note_type", note_type)
        added = sum(1 for r in result_ids if r is not None)
        return {
            "ok": True, "notes_added": added, "already_in_anki": len(notes) - len(new),
            "failed": len(result_ids) - added, "deck": deck_name,
        }

    def _push_lpcg_notes(self, notes: list[dict]) -> dict:
        """Send tiqqun notes (see _tiqqun_ammudim_notes), each to its own
        ``"deck"``, creating decks as needed and making sure the
        font, note type, CSS and templates are in place (and refreshed if
        stale) first.

        A note that's already in Anki -- the same pasuq's card, or the same
        lines in row mode, anywhere in the collection (see
        ankipasuk.tiqqun_export) -- is skipped; existing notes are never
        changed. Returns ``{"ok": True, "notes_added", "already_in_anki",
        "failed"}`` or ``{"ok": False, "error"}``."""
        if not notes:
            return {"ok": False, "error": "No text was found to export."}

        try:
            font_base64 = get_font_base64(self._cache)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

        try:
            anki_ensure_media_file(FONT_ANKI_FILENAME, font_base64, url=DEFAULT_URL)
            anki_ensure_model(LPCG_MODEL_NAME, LPCG_FIELD_NAMES, LPCG_CSS, CARD_TEMPLATES, url=DEFAULT_URL)
            anki_ensure_model_fields(LPCG_MODEL_NAME, LPCG_FIELD_NAMES, url=DEFAULT_URL)
            anki_sync_model_css(LPCG_MODEL_NAME, LPCG_CSS, url=DEFAULT_URL)
            anki_sync_model_templates(LPCG_MODEL_NAME, CARD_TEMPLATES, url=DEFAULT_URL)
            existing_ids = anki_find_notes(f'"note:{LPCG_MODEL_NAME}"', url=DEFAULT_URL)
            keys = tiqqun_existing_keys(anki_notes_info(existing_ids, url=DEFAULT_URL), self._cache)
            new = []
            for note in notes:
                if not tiqqun_is_duplicate(note, keys):
                    new.append(note)
                    keys.add(note["key"])  # nor twice within one export
            for deck in sorted({note["deck"] for note in new}):
                anki_ensure_deck(deck, url=DEFAULT_URL)
            payload = [{
                "deckName": note["deck"], "modelName": LPCG_MODEL_NAME,
                "fields": note["fields"], "tags": note["tags"],
                "options": {"allowDuplicate": True},  # the check above is the duplicate check
            } for note in new]
            result_ids = anki_add_notes(payload, url=DEFAULT_URL, dry_run=False) if payload else []
        except (AnkiConnectError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}

        added = sum(1 for r in result_ids if r is not None)
        return {
            "ok": True, "notes_added": added, "already_in_anki": len(notes) - len(new),
            "failed": len(result_ids) - added,
        }

    def _write_tiqqun_csv(self, notes: list[dict], default_name: str) -> dict:
        """Save tiqqun notes as an Anki CSV. Importing it needs the
        tiqqun note type already in Anki (any export to Anki creates it)."""
        if not notes:
            return {"ok": False, "error": "No text was found to export."}
        if self._window is None:
            return {"ok": False, "error": "Window not ready."}
        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=default_name,
            file_types=("CSV files (*.csv)", "All files (*.*)"),
        )
        if not path:
            return {"ok": False, "error": None}  # cancelled
        target = path if isinstance(path, str) else path[0]
        try:
            with open(target, "w", encoding="utf-8-sig", newline="") as f:
                f.write(tiqqun_csv_text(notes))
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "count": len(notes), "path": target}

    def _tiqqun_amud_notes(
        self, amud_num: int, card_division: str, context_lines: int, recite_lines: int, group_size: int,
    ) -> list[dict]:
        """The tiqqun notes for one 'ammud (sefer column). An 'ammud can hold
        the end of one book and the start of the next (111, 148, 200), so
        each pasuq card gets its own book's title, tags and identity.
        Raises RuntimeError/ValueError."""
        tags = [tiqqun_ammud_tag(amud_num)]

        def title(*books: str) -> str:
            return f"{'–'.join(BOOK_HEBREW_NAMES.get(b, b) for b in books)} 'Ammud {amud_num}"

        if card_division == "verse":
            cards = build_amud_verse_cards(amud_num, self._cache, title_for=title)
            context = qeriya_context({book for (book, _ch, _vs), _f in cards}, self._cache)
            return [{
                "fields": fields,
                "tags": tags + [t for t in qeriya_tags(context, book, ch, vs) if t not in tags],
                "key": tiqqun_pasuq_key(book, ch, vs),
            } for (book, ch, vs), fields in cards]
        # A row card spans lines, so it carries only the 'ammud's tag; one
        # straddling two books is titled with both.
        books = list(dict.fromkeys(book for book, _ch, _vs in get_book_verses_on_amud(amud_num, self._cache)))
        books = books or [get_book_for_page(amud_num, self._cache)]
        fields_list = build_lpcg_fields(
            get_amud_lines(amud_num, self._cache), title=title(*books), context_lines=context_lines,
            recite_lines=recite_lines, group_size=group_size,
        )
        return [{
            "fields": f, "tags": list(tags),
            "key": tiqqun_row_key(f["Line"]) if f.get("Line") else tiqqun_content_key(f),
        } for f in fields_list]

    def _tiqqun_ammudim_notes(
        self, ammudim: list[int], card_division: str, context_lines: int, recite_lines: int,
        group_size: int,
    ) -> tuple[list[int], list[dict]]:
        """The tiqqun notes for several 'ammudim, each marked with its
        'ammud's deck, ``Ammudim::NNN`` (see
        :func:`ankipasuk.qeriya.tiqqun_ammud_deck`). Each 'ammud counts
        once, in order, however the ranges overlap. Raises
        RuntimeError/ValueError, naming the 'ammud."""
        unique = sorted({int(n) for n in ammudim})
        if not unique:
            raise ValueError("Choose at least one 'ammud.")
        notes = []
        for n in unique:
            try:
                ammud_notes = self._tiqqun_amud_notes(
                    n, card_division, context_lines, recite_lines, group_size,
                )
            except (RuntimeError, ValueError) as e:
                raise type(e)(f"'Ammud {n}: {e}") from e
            if not ammud_notes:
                raise ValueError(f"'Ammud {n} has no text.")
            for note in ammud_notes:
                note["deck"] = tiqqun_ammud_deck(n)
            notes += ammud_notes
        return unique, notes

    def export_ammudim_to_anki(
        self, ammudim: list[int], card_division: str = "verse", context_lines: int = 2,
        recite_lines: int = 1, group_size: int = 1,
    ) -> dict:
        """Send the tiqqun cards for the 'ammudim in ``ammudim`` (each 1-245,
        see :data:`ankipasuk.tikkun.TOTAL_AMUDIM`) to Anki through
        AnkiConnect, each 'ammud to its own deck, ``Ammudim::NNN``; see
        _push_lpcg_notes for duplicates.

        ``card_division`` picks how an 'ammud's lines become cards:

        - "verse" (default, recommended): one card per pasuq starting on
          the 'ammud, word-precise at any line it shares with the pasuq
          just before/after (see :mod:`ankipasuk.verse_cards`) -- only that
          pasuq's own words are tested; a neighbour's words on the same
          line show as plain context. Exactly one extra line before as
          context. ``context_lines``/``recite_lines``/``group_size`` are
          ignored.
        - "row": the AnkiLPCG-style sliding window over the 'ammud's lines,
          tuned by ``context_lines``/``recite_lines``/``group_size`` (see
          :func:`ankipasuk.lpcg.build_lpcg_fields`).

        Either way each card's text is laid out as in a sefer (see
        :mod:`ankipasuk.tikkun`), in the STAM-style font tikkun.io uses,
        which is put into Anki as a media file on first use. The note type
        (:data:`ankipasuk.lpcg.MODEL_NAME`) is created if missing.
        """
        try:
            unique, notes = self._tiqqun_ammudim_notes(
                ammudim, card_division, context_lines, recite_lines, group_size,
            )
        except (RuntimeError, ValueError) as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        result = self._push_lpcg_notes(notes)
        if result["ok"]:
            result.update(ammudim=unique, decks=[tiqqun_ammud_deck(n) for n in unique])
        return result

    def export_ammudim_csv(
        self, ammudim: list[int], card_division: str = "verse", context_lines: int = 2,
        recite_lines: int = 1, group_size: int = 1,
    ) -> dict:
        """Like export_ammudim_to_anki, but saved as one CSV to import; a
        deck column keeps each 'ammud's cards in its own deck."""
        try:
            unique, notes = self._tiqqun_ammudim_notes(
                ammudim, card_division, context_lines, recite_lines, group_size,
            )
        except (RuntimeError, ValueError) as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        name = f"tiqqun_ammud_{unique[0]:03d}.csv" if len(unique) == 1 else (
            f"tiqqun_ammudim_{unique[0]:03d}-{unique[-1]:03d}.csv")
        return self._write_tiqqun_csv(notes, name)

    def preview_ammud(self, ammud: int) -> dict:
        """One 'ammud as the page export would save it (see
        ankipasuk.ammud_pages), as HTML for the Tiqqun tab's preview."""
        try:
            return {"ok": True, "html": ammud_pages_html([int(ammud)], self._cache)}
        except Exception as e:  # noqa: BLE001 -- a network failure is shown, not raised
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def export_ammud_pages(self, ammudim: list[int], fmt: str) -> dict:
        """Save the 'ammudim as pages -- each its sefer column, one per page
        (see ankipasuk.ammud_pages) -- as ``fmt`` "html" or "pdf"."""
        if fmt not in ("html", "pdf"):
            return {"ok": False, "error": f"Unknown format: {fmt}"}
        unique = sorted({int(n) for n in ammudim})
        if not unique:
            return {"ok": False, "error": "Choose at least one 'ammud."}
        if self._window is None:
            return {"ok": False, "error": "Window not ready."}
        name = f"ammud_{unique[0]:03d}" if len(unique) == 1 else f"ammudim_{unique[0]:03d}-{unique[-1]:03d}"
        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=f"{name}.{fmt}",
            file_types=(f"{fmt.upper()} files (*.{fmt})", "All files (*.*)"),
        )
        if not path:
            return {"ok": False, "error": None}  # cancelled
        target = path if isinstance(path, str) else path[0]
        try:
            if fmt == "pdf":
                write_ammud_pages_pdf(unique, self._cache, target)
            else:
                Path(target).write_text(ammud_pages_html(unique, self._cache), encoding="utf-8")
        except (RuntimeError, ValueError, OSError) as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        return {"ok": True, "count": len(unique), "path": target}

    # =============================================================
    #  Secondary windows
    # =============================================================
    def open_anki_connect_window(self) -> dict:
        anki_api = AnkiConnectApi()
        window = webview.create_window(
            "AnkiConnect Tools",
            str(_STATIC_DIR / "anki_connect.html"),
            js_api=anki_api,
            width=780,
            height=680,
            text_select=True,
        )
        anki_api._window = window
        return {"ok": True}

    def open_stats_window(self, max_leaf_disj: int) -> dict:
        if not self._current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}
        font = self.get_tikkun_font_css()
        stats_api = StatsApi(self._current_verse_data, max_leaf_disj, font["css"] if font["ok"] else "")
        window = webview.create_window(
            "Corpus statistics",
            str(_STATIC_DIR / "stats.html"),
            js_api=stats_api,
            width=1000,
            height=760,
            text_select=True,
        )
        stats_api._window = window
        return {"ok": True}
