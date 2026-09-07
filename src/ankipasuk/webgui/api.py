"""The Python side of the web GUI: a thin API surface exposed to the
JavaScript frontend via pywebview's JS-to-Python bridge
(``window.pywebview.api.<method>(...)`` in JS calls the method of the same
name here).

Every method here is a thin wrapper around the same core logic the
original Tk GUI used (``sefaria.py``, ``cloze.py``, ``text_processing.py``,
``stats.py``, ``structure.py``, ``leyning.py``, ``anki_connect/*``) --
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

from ..anki_connect.client import DEFAULT_URL, AnkiConnectError
from ..anki_connect.operations import add_notes as anki_add_notes
from ..anki_connect.operations import ensure_model as anki_ensure_model
from ..cache import SefariaCache
from ..cloze import verse_to_nested_cloze
from ..config import BOOK_CATEGORIES, BOOK_HEBREW_NAMES, CSV_FLAGS, POINTED_VERSION
from ..lpcg import CARD_TEMPLATES, build_lpcg_fields
from ..lpcg import CSS as LPCG_CSS
from ..lpcg import FIELD_NAMES as LPCG_FIELD_NAMES
from ..lpcg import MODEL_NAME as LPCG_MODEL_NAME
from ..sefaria import (
    fetch_aliyot_in_range,
    fetch_verse_range,
    get_aliyah_ref,
    get_book_structure,
    get_parasha_structure,
    get_text_for_ref,
    parse_start_ref,
)
from ..text_processing import format_units, strip_vowels_and_trope
from .anki_connect_api import AnkiConnectApi
from .stats_api import StatsApi
from .tree_html import tree_to_html

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
    """

    def __init__(self) -> None:
        self._cache = SefariaCache()
        self._current_verse_data: list[dict] = []
        self._window: webview.Window | None = None

    # =============================================================
    #  Static reference data (no network)
    # =============================================================
    def get_books(self) -> dict[str, list[str]]:
        """{"Torah": [...], "Nevi'im": [...], "Megillot": [...]} -- the
        frontend uses this to build a book <select> with one <optgroup>
        per category."""
        return BOOK_CATEGORIES

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
        """{"ok": True, "names": [...]} or {"ok": False, "error": "..."}."""
        try:
            parashot = get_parasha_structure(book, self._cache)
            return {"ok": True, "names": [p["name"] for p in parashot]}
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
        """Like fetch_chapter_verse, but for a named parashah/aliyah
        (Torah only -- parashot don't exist for Nevi'im or the
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

    def clear_ranges(self) -> dict:
        """Discard all accumulated verse data, starting a fresh session."""
        self._current_verse_data = []
        return {"ok": True, "verses": self._current_verse_data}

    def _cache_status_text(self) -> str:
        s = self._cache.stats()
        return f"Cache: {s['cached_refs']} ref(s), {s['cached_books']} book structure(s)"

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
            viz_html_blocks.append(f'<div class="viz-verse">{tree_to_html(tree)}</div>')

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

        max_leaf_disj = max(1, max_leaf_disj)
        rows = []
        next_start = 1
        total = len(self._current_verse_data)

        for i, item in enumerate(self._current_verse_data):
            pointed = item["pointed"].strip()
            start_counter = 1 if reset_per_line else next_start
            cl, last, _tree, _tok, _units = verse_to_nested_cloze(
                pointed, start_counter=start_counter, max_leaf_disj=max_leaf_disj
            )
            if not reset_per_line:
                next_start = last + 1

            plain = item["plain"]
            prev_plain = self._current_verse_data[i - 1]["plain"] if i > 0 else ""
            next_plain = self._current_verse_data[i + 1]["plain"] if i + 1 < total else ""
            hebrew_book = BOOK_HEBREW_NAMES.get(item["book"], item["book"])
            verse_label = f"{hebrew_book} {item['ch']}:{item['vs']}"

            rows.append([str(i + 1), verse_label, cl, plain, prev_plain, next_plain, "", CSV_FLAGS])

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
            writer = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
            writer.writerows(rows)
            with open(target, "w", encoding="utf-8-sig", newline="") as f:
                f.write(buf.getvalue())
        except OSError as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "count": len(rows), "path": target}

    # =============================================================
    #  Aliyah recitation export (overlapping-context notes, pushed
    #  directly to Anki via AnkiConnect)
    # =============================================================
    def export_aliyot_to_anki(
        self,
        book: str,
        start_parasha: str,
        start_aliyah: int,
        end_parasha: str,
        end_aliyah: int,
        deck_name: str,
        context_lines: int = 2,
        recite_lines: int = 1,
        group_size: int = 1,
    ) -> dict:
        """Fetch every aliyah from (start_parasha, start_aliyah) through
        (end_parasha, end_aliyah) and push one Anki note per recitation
        card to ``deck_name`` via AnkiConnect, using the overlapping-context
        windowing in :mod:`ankipasuk.lpcg` -- one aliyah = one "poem" (its
        own Title, so cards from different aliyot never overlap each
        other's context window).

        Anki must be running with the AnkiConnect add-on installed. Does
        not require the AnkiLPCG add-on itself -- the note type
        (:data:`ankipasuk.lpcg.MODEL_NAME`) is created automatically on
        first use if missing.
        """
        try:
            aliyot = fetch_aliyot_in_range(
                book, start_parasha, start_aliyah, end_parasha, end_aliyah,
                self._cache, POINTED_VERSION,
            )
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

        hebrew_book = BOOK_HEBREW_NAMES.get(book, book)
        notes = []
        for aliyah in aliyot:
            lines = [v["pointed"] for v in aliyah["verses"] if v["pointed"].strip()]
            if not lines:
                continue
            title = f"{hebrew_book} {aliyah['parasha']} {aliyah['aliyah_num']} ({aliyah['ref']})"
            tags = [
                "ankipasuk-aliyah",
                f"parasha::{aliyah['parasha'].replace(' ', '-')}",
            ]
            for fields in build_lpcg_fields(
                lines, title=title, context_lines=context_lines,
                recite_lines=recite_lines, group_size=group_size,
            ):
                notes.append({
                    "deckName": deck_name,
                    "modelName": LPCG_MODEL_NAME,
                    "fields": fields,
                    "tags": tags,
                    "options": {"allowDuplicate": True},
                })

        if not notes:
            return {"ok": False, "error": "No aliyot with text were found in that range."}

        try:
            anki_ensure_model(LPCG_MODEL_NAME, LPCG_FIELD_NAMES, LPCG_CSS, CARD_TEMPLATES, url=DEFAULT_URL)
            result_ids = anki_add_notes(notes, url=DEFAULT_URL, dry_run=False)
        except AnkiConnectError as e:
            return {"ok": False, "error": str(e)}

        added = sum(1 for r in result_ids if r is not None)
        skipped = len(result_ids) - added
        return {"ok": True, "aliyot": len(aliyot), "notes_added": added, "notes_skipped": skipped}

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
