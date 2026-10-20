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

from ..analysis import cloze_breakdown
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
)
from ..config import (
    BOOK_CATEGORIES,
    BOOK_HEBREW_NAMES,
    BOOK_HEBREW_SCRIPT_NAMES,
    POINTED_VERSION,
    QERIYA_DECK_NAMES,
)
from ..lpcg import CARD_TEMPLATES, build_lpcg_fields, render_scroll_html
from ..lpcg import CSS as LPCG_CSS
from ..lpcg import FIELD_NAMES as LPCG_FIELD_NAMES
from ..lpcg import MODEL_NAME as LPCG_MODEL_NAME
from ..lpcg import SCROLL_CSS as LPCG_SCROLL_CSS
from ..qeriya import (
    ALIYYA_TAG_NAMESPACE,
    TIQQUN_ALIYYA_TAG,
    haftara_label,
    haftara_table,
    parasha_names,
    parse_range_ref,
    tiqqun_ammud_tag,
    tiqqun_parasha_tag,
    to_slug,
)
from ..sefaria import (
    fetch_aliyot_in_range,
    fetch_verse_range,
    get_aliyah_ref,
    get_book_structure,
    get_parasha_structure,
    get_text_for_ref,
    parse_start_ref,
)
from ..settings import Settings
from ..structure import format_structure, verse_structure_signature
from ..text_processing import format_units, strip_vowels_and_trope
from ..tikkun import (
    FONT_ANKI_FILENAME,
    get_amud_lines,
    get_book_for_page,
    get_font_base64,
    get_scroll_lines_for_range,
    get_verses_starting_on_amud,
)
from ..tiqqun_export import content_key as tiqqun_content_key
from ..tiqqun_export import csv_text as tiqqun_csv_text
from ..tiqqun_export import existing_keys as tiqqun_existing_keys
from ..tiqqun_export import is_duplicate as tiqqun_is_duplicate
from ..tiqqun_export import pasuq_key as tiqqun_pasuq_key
from ..tiqqun_export import row_key as tiqqun_row_key
from ..verse_cards import build_amud_verse_cards, build_verse_cards
from .anki_connect_api import AnkiConnectApi
from .stats_api import StatsApi
from .tree_html import analysis_to_html, leaf_chips, tree_to_html

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
        unit_debug_lines = []
        viz_html_blocks = []
        next_start = 1

        for item in self._current_verse_data:
            v = item["pointed"].strip()
            if not v:
                continue

            start_counter = 1 if reset_per_line else next_start
            cl, last, tree, _tok, units = verse_to_nested_cloze(
                v, start_counter=start_counter, max_leaf_disj=max_leaf_disj
            )
            lines.append(cl)
            unit_debug_lines.append(format_units(units))
            breakdown = cloze_breakdown(tree, start_counter)
            label = f"{BOOK_HEBREW_NAMES.get(item['book'], item['book'])} {item['ch']}:{item['vs']}"
            signature = format_structure(verse_structure_signature(v))
            viz_html_blocks.append(
                '<div class="viz-verse">'
                f"{tree_to_html(tree, chips=leaf_chips(breakdown))}"
                f"{analysis_to_html(label, signature, breakdown)}"
                "</div>"
            )

            if not reset_per_line:
                next_start = last + 1

        return {
            "ok": True,
            "output": "\n".join(lines),
            "tokens": "\n\n".join(unit_debug_lines),
            "viz_html": "".join(viz_html_blocks),
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
    DEFAULT_LPCG_DECK_NAME = "Master::Qeriya::Aliyyot"

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

    def get_lpcg_deck_name(self) -> str:
        """The deck name to prefill the export form with: whatever was
        last used (see export_aliyot_to_anki / export_amud_to_anki), or
        DEFAULT_LPCG_DECK_NAME the first time the app is ever run."""
        return self._settings.get("lpcg_deck_name", self.DEFAULT_LPCG_DECK_NAME)

    def _push_lpcg_notes(self, notes: list[dict], deck_name: str) -> dict:
        """Send tiqqun notes (see _tiqqun_aliyot_notes / _tiqqun_amud_notes)
        to ``deck_name``, creating the deck if needed and making sure the
        font, note type, CSS and templates are in place (and refreshed if
        stale) first.

        A note that's already in Anki -- the same pasuq's card, or the same
        lines in row mode, anywhere in the collection (see
        ankipasuk.tiqqun_export) -- is skipped; existing notes are never
        changed. Returns ``{"ok": True, "notes_added", "already_in_anki",
        "failed"}`` or ``{"ok": False, "error"}``."""
        self._settings.set("lpcg_deck_name", deck_name)
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
            anki_ensure_deck(deck_name, url=DEFAULT_URL)
            payload = [{
                "deckName": deck_name, "modelName": LPCG_MODEL_NAME,
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

    def _write_tiqqun_csv(self, notes: list[dict], deck_name: str, default_name: str) -> dict:
        """Save tiqqun notes as an Anki CSV. Importing it needs the
        tiqqun note type already in Anki (any export to Anki creates it)."""
        self._settings.set("lpcg_deck_name", deck_name)
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
                f.write(tiqqun_csv_text(notes, deck_name))
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "count": len(notes), "path": target}

    def _tiqqun_notes(
        self, book: str, fields_list: list[dict], verse_refs: list[tuple[int, int]] | None,
        tags: list[str], context: dict,
    ) -> list[dict]:
        """``{"fields", "tags", "key"}`` per card. In pasuq mode
        (``verse_refs`` given, one per card) each card also gets its
        pasuq's qeriya tags, as the cloze export does."""
        notes = []
        for i, fields in enumerate(fields_list):
            if verse_refs is not None and len(verse_refs) == len(fields_list):
                ch, vs = verse_refs[i]
                key = tiqqun_pasuq_key(book, ch, vs)
                note_tags = tags + [t for t in qeriya_tags(context, book, ch, vs) if t not in tags]
            elif fields.get("Line"):
                key, note_tags = tiqqun_row_key(fields["Line"]), list(tags)
            else:
                key, note_tags = tiqqun_content_key(fields), list(tags)
            notes.append({"fields": fields, "tags": note_tags, "key": key})
        return notes

    def _tiqqun_aliyot_notes(
        self, book: str, start_parasha: str, start_aliyah: int, end_parasha: str, end_aliyah: int,
        card_division: str, context_lines: int, recite_lines: int, group_size: int,
    ) -> tuple[list[dict], int]:
        """The tiqqun notes for a range of 'aliyyot, and how many 'aliyyot
        that was. One 'aliyya is one LPCG "poem", so a card's context never
        reaches into the next 'aliyya. Raises RuntimeError/ValueError."""
        aliyot = fetch_aliyot_in_range(
            book, start_parasha, start_aliyah, end_parasha, end_aliyah, self._cache, POINTED_VERSION,
        )
        ours = parasha_names(book, get_parasha_structure(book, self._cache))
        context = qeriya_context({book}, self._cache)
        hebrew_book = BOOK_HEBREW_NAMES.get(book, book)
        notes = []
        for aliyah in aliyot:
            verses = aliyah["verses"]
            if not verses:
                continue
            # Our name and slug for the parasha (falling back to Sefaria's
            # if the pairing doesn't hold), and the ref with our book name.
            entry = ours.get(aliyah["parasha"])
            parasha_name = entry["name"] if entry else aliyah["parasha"]
            parasha_slug = entry["slug"] if entry else to_slug(aliyah["parasha"])
            ref = aliyah["ref"]
            if ref.startswith(book + " "):
                ref = hebrew_book + ref[len(book):]
            title = f"{hebrew_book} {parasha_name} {aliyah['aliyah_num']} ({ref})"
            tags = [TIQQUN_ALIYYA_TAG, tiqqun_parasha_tag(parasha_slug)]
            if card_division == "verse":
                verse_refs = [(v["ch"], v["vs"]) for v in verses]
                fields_list = build_verse_cards(book, verse_refs, self._cache, title=title)
            else:
                verse_refs = None
                if entry:  # a row card spans lines, so it carries its 'aliyya's tag
                    tags.append(
                        f"{ALIYYA_TAG_NAMESPACE}{to_slug(hebrew_book)}::{entry['rel']:02d}-{entry['slug']}"
                        f"::{aliyah['aliyah_num']}"
                    )
                lines = get_scroll_lines_for_range(
                    book, verses[0]["ch"], verses[0]["vs"], verses[-1]["ch"], verses[-1]["vs"], self._cache,
                )
                fields_list = build_lpcg_fields(
                    lines, title=title, context_lines=context_lines,
                    recite_lines=recite_lines, group_size=group_size,
                )
            notes += self._tiqqun_notes(book, fields_list, verse_refs, tags, context)
        return notes, len(aliyot)

    def _tiqqun_amud_notes(
        self, amud_num: int, card_division: str, context_lines: int, recite_lines: int, group_size: int,
    ) -> tuple[list[dict], str]:
        """The tiqqun notes for one 'ammud (sefer column), and its book. A
        sefer starts each book on a fresh column, so an 'ammud is always
        within one book. Raises RuntimeError/ValueError."""
        book = get_book_for_page(amud_num, self._cache)
        title = f"{BOOK_HEBREW_NAMES.get(book, book)} 'Ammud {amud_num}"
        tags = [tiqqun_ammud_tag(amud_num)]
        if card_division == "verse":
            verse_refs = get_verses_starting_on_amud(amud_num, self._cache)
            fields_list = build_amud_verse_cards(book, amud_num, self._cache, title=title)
        else:
            verse_refs = None
            fields_list = build_lpcg_fields(
                get_amud_lines(amud_num, self._cache), title=title, context_lines=context_lines,
                recite_lines=recite_lines, group_size=group_size,
            )
        context = qeriya_context({book}, self._cache)
        return self._tiqqun_notes(book, fields_list, verse_refs, tags, context), book

    def export_aliyot_to_anki(
        self,
        book: str,
        start_parasha: str,
        start_aliyah: int,
        end_parasha: str,
        end_aliyah: int,
        deck_name: str,
        card_division: str = "verse",
        context_lines: int = 2,
        recite_lines: int = 1,
        group_size: int = 1,
    ) -> dict:
        """Send the tiqqun cards for a range of 'aliyyot to ``deck_name``
        through AnkiConnect (see _push_lpcg_notes for duplicates and the
        deck).

        ``card_division`` picks how each 'aliyya's lines become cards:

        - "verse" (default, recommended): one card per pasuq, word-precise
          at any line it shares with the pasuq just before/after (see
          :mod:`ankipasuk.verse_cards`) -- only that pasuq's own words are
          tested; a neighbour's words on the same line show as plain
          context. Exactly one extra line before as context.
          ``context_lines``/``recite_lines``/``group_size`` are ignored.
        - "row": the AnkiLPCG-style sliding window over the sefer's lines,
          tuned by ``context_lines``/``recite_lines``/``group_size`` (see
          :func:`ankipasuk.lpcg.build_lpcg_fields`).

        Either way each card's text is laid out as in a sefer (see
        :mod:`ankipasuk.tikkun`), in the STAM-style font tikkun.io uses,
        which is put into Anki as a media file on first use. The note type
        (:data:`ankipasuk.lpcg.MODEL_NAME`) is created if missing.
        """
        try:
            notes, n_aliyot = self._tiqqun_aliyot_notes(
                book, start_parasha, start_aliyah, end_parasha, end_aliyah,
                card_division, context_lines, recite_lines, group_size,
            )
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        result = self._push_lpcg_notes(notes, deck_name)
        if result["ok"]:
            result["aliyot"] = n_aliyot
        elif result["error"] == "No text was found to export.":
            result["error"] = "No 'aliyyot with text were found in that range."
        return result

    def export_aliyot_csv(
        self, book: str, start_parasha: str, start_aliyah: int, end_parasha: str, end_aliyah: int,
        deck_name: str, card_division: str = "verse", context_lines: int = 2,
        recite_lines: int = 1, group_size: int = 1,
    ) -> dict:
        """Like export_aliyot_to_anki, but saved as a CSV to import."""
        try:
            notes, _n = self._tiqqun_aliyot_notes(
                book, start_parasha, start_aliyah, end_parasha, end_aliyah,
                card_division, context_lines, recite_lines, group_size,
            )
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        return self._write_tiqqun_csv(notes, deck_name, "tiqqun_aliyyot.csv")

    def export_amud_to_anki(
        self,
        amud_num: int,
        deck_name: str,
        card_division: str = "verse",
        context_lines: int = 2,
        recite_lines: int = 1,
        group_size: int = 1,
    ) -> dict:
        """Send the tiqqun cards for 'ammud ``amud_num`` (1-245, see
        :data:`ankipasuk.tikkun.TOTAL_AMUDIM`) to ``deck_name``: in pasuq
        mode one card per pasuq starting on it (via
        :func:`ankipasuk.verse_cards.build_amud_verse_cards`), in row mode
        the whole 'ammud as one sliding window. See export_aliyot_to_anki.
        """
        try:
            notes, book = self._tiqqun_amud_notes(
                amud_num, card_division, context_lines, recite_lines, group_size,
            )
        except (RuntimeError, ValueError) as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        result = self._push_lpcg_notes(notes, deck_name)
        if result["ok"]:
            result["amud"] = amud_num
            result["book"] = book
        elif result["error"] == "No text was found to export.":
            result["error"] = f"'Ammud {amud_num} has no text."
        return result

    def export_amud_csv(
        self, amud_num: int, deck_name: str, card_division: str = "verse", context_lines: int = 2,
        recite_lines: int = 1, group_size: int = 1,
    ) -> dict:
        """Like export_amud_to_anki, but saved as a CSV to import."""
        try:
            notes, _book = self._tiqqun_amud_notes(
                amud_num, card_division, context_lines, recite_lines, group_size,
            )
        except (RuntimeError, ValueError) as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        return self._write_tiqqun_csv(notes, deck_name, f"tiqqun_ammud_{amud_num:03d}.csv")

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
        stats_api = StatsApi(self._current_verse_data, max_leaf_disj)
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
