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

from ..cache import SefariaCache
from ..cloze import verse_to_nested_cloze
from ..config import BOOK_HEBREW_NAMES, CSV_FLAGS, POINTED_VERSION, TORAH_BOOKS, TORAH_VERSE_COUNTS
from ..sefaria import (
    fetch_torah_range,
    get_aliyah_ref,
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
    """Holds the mutable state a session needs (cache, last-fetched verse
    data) -- one instance is created per app run and shared by every JS
    call, mirroring how ``AnkiPasukApp`` held this as instance state."""

    def __init__(self) -> None:
        self.cache = SefariaCache()
        self.current_verse_data: list[dict] = []
        self.current_book: str = "Genesis"
        self.window: webview.Window | None = None

    # =============================================================
    #  Static reference data (no network)
    # =============================================================
    def get_books(self) -> list[str]:
        return list(TORAH_BOOKS.keys())

    def get_chapter_count(self, book: str) -> int:
        return len(TORAH_VERSE_COUNTS[book])

    def get_verse_count(self, book: str, chapter: int) -> int:
        counts = TORAH_VERSE_COUNTS[book]
        if 1 <= chapter <= len(counts):
            return counts[chapter - 1]
        return 1

    # =============================================================
    #  Live Sefaria data (network on first call per book, cached after)
    # =============================================================
    def get_parashot(self, book: str) -> dict:
        """{"ok": True, "names": [...]} or {"ok": False, "error": "..."}."""
        try:
            parashot = get_parasha_structure(book, self.cache)
            return {"ok": True, "names": [p["name"] for p in parashot]}
        except Exception as e:  # noqa: BLE001 - reported to the JS side
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def get_aliyah_count(self, book: str, parasha_name: str) -> dict:
        try:
            parashot = get_parasha_structure(book, self.cache)
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
        try:
            data = fetch_torah_range(book, start_ch, start_vs, end_ch, end_vs, self.cache, POINTED_VERSION)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        self.current_verse_data = data
        self.current_book = book
        return {"ok": True, "verses": data, "cache_status": self._cache_status_text()}

    def fetch_parashah_aliyah(self, book: str, parasha_name: str, aliyah_num: int) -> dict:
        try:
            ref_str = get_aliyah_ref(book, parasha_name, aliyah_num, self.cache)
            pointed_verses = get_text_for_ref(ref_str, POINTED_VERSION, self.cache)
            start_ch, start_vs = parse_start_ref(ref_str)

            data = []
            ch, vs = start_ch, start_vs
            for pointed in pointed_verses:
                plain = strip_vowels_and_trope(pointed)
                data.append({"ch": ch, "vs": vs, "pointed": pointed, "plain": plain})
                vs += 1
                if ch <= self.get_chapter_count(book) and vs > self.get_verse_count(book, ch):
                    vs = 1
                    ch += 1
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e)}
        self.current_verse_data = data
        self.current_book = book
        return {"ok": True, "verses": data, "cache_status": self._cache_status_text()}

    def _cache_status_text(self) -> str:
        s = self.cache.stats()
        return f"Cache: {s['cached_refs']} ref(s), {s['cached_books']} book structure(s)"

    def get_cache_status(self) -> str:
        return self._cache_status_text()

    def clear_cache(self) -> dict:
        self.cache.clear()
        return {"ok": True, "cache_status": self._cache_status_text()}

    # =============================================================
    #  Cloze generation
    # =============================================================
    def generate_cloze(self, max_leaf_disj: int, reset_per_line: bool) -> dict:
        if not self.current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}

        max_leaf_disj = max(1, max_leaf_disj)
        lines = []
        unit_debug_lines = []
        viz_html_blocks = []
        next_start = 1

        for item in self.current_verse_data:
            v = item["pointed"].strip()
            if not v:
                continue

            start_counter = 1 if reset_per_line else next_start
            cl, last, tree, _tok, units = verse_to_nested_cloze(
                v, start_counter=start_counter, max_leaf_disj=max_leaf_disj
            )
            lines.append(cl)
            unit_debug_lines.append(format_units(units))
            viz_html_blocks.append(tree_to_html(tree))

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
        if not self.current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}

        max_leaf_disj = max(1, max_leaf_disj)
        hebrew_book = BOOK_HEBREW_NAMES.get(self.current_book, self.current_book)
        rows = []
        next_start = 1
        total = len(self.current_verse_data)

        for i, item in enumerate(self.current_verse_data):
            pointed = item["pointed"].strip()
            start_counter = 1 if reset_per_line else next_start
            cl, last, _tree, _tok, _units = verse_to_nested_cloze(
                pointed, start_counter=start_counter, max_leaf_disj=max_leaf_disj
            )
            if not reset_per_line:
                next_start = last + 1

            plain = item["plain"]
            prev_plain = self.current_verse_data[i - 1]["plain"] if i > 0 else ""
            next_plain = self.current_verse_data[i + 1]["plain"] if i + 1 < total else ""
            verse_label = f"{hebrew_book} {item['ch']}:{item['vs']}"

            rows.append([str(i + 1), verse_label, cl, plain, prev_plain, next_plain, "", CSV_FLAGS])

        if not rows:
            return {"ok": False, "error": "No verse lines were found to export."}

        if self.window is None:
            return {"ok": False, "error": "Window not ready."}

        path = self.window.create_file_dialog(
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
        )
        anki_api.window = window
        return {"ok": True}

    def open_stats_window(self, max_leaf_disj: int) -> dict:
        if not self.current_verse_data:
            return {"ok": False, "error": "Fetch a range of verses first."}
        stats_api = StatsApi(self.current_verse_data, max_leaf_disj)
        window = webview.create_window(
            "Corpus statistics",
            str(_STATIC_DIR / "stats.html"),
            js_api=stats_api,
            width=1000,
            height=760,
        )
        stats_api.window = window
        return {"ok": True}
