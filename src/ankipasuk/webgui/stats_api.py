"""API bridge for the Corpus Statistics window.

Computes everything once via the existing GUI-agnostic ``stats.py``
(``compute_corpus_stats``) and ``structure.py`` on window creation, then
serves it to the JS frontend as plain JSON-serializable data -- no new
statistics logic lives here, only adaptation for the JS side.
"""

from __future__ import annotations

import webview

from ..config import BOOK_HEBREW_NAMES, LEGARMEH_NAME, TROPE_HEBREW_NAMES, TROPE_UNICODE
from ..diagram import pasuq_diagram
from ..stats import compute_corpus_stats, format_stats_summary, write_stats_csv
from ..structure import (
    format_structure,
    group_verses_by_disj_count_and_structure,
    group_verses_by_structure,
    group_verses_by_word_count_and_structure,
)


def _dist_to_bars(dist, bins, value_formatter=str):
    """Counter + bins dict -> a JS-friendly sorted list of
    {key, count, verses}, ready to render as bars."""
    return [{"key": value_formatter(k), "count": dist[k], "verses": bins[k]} for k in sorted(dist.keys())]


def _ratio_bars(dist, bins):
    """Words per disjunctive group, every 0.1 bin from the lowest to the
    highest -- the empty ones too, so the bars read as a histogram."""
    if not dist:
        return []
    lo, hi = round(min(dist) * 10), round(max(dist) * 10)
    return [
        {"key": f"{t / 10:.1f}", "count": dist.get(t / 10, 0), "verses": bins.get(t / 10, [])}
        for t in range(lo, hi + 1)
    ]


# Each mafsiq's rank, by name (the paseq's comes from the legarmeh rule).
_RANKS = {name: rank for name, rank in TROPE_UNICODE.values() if rank} | {LEGARMEH_NAME: 4}


def _our_spelling(label: str) -> str:
    """ "Genesis 1:1" -> "Bereshit 1:1", as the rest of the app writes it."""
    book, _space, ref = label.rpartition(" ")
    return f"{BOOK_HEBREW_NAMES.get(book, book)} {ref}"


class StatsApi:
    def __init__(self, verse_data: list[dict], max_leaf_disj: int, font_css: str = "") -> None:
        self._window: webview.Window | None = None
        self.verse_data = verse_data
        self.max_leaf_disj = max_leaf_disj
        self.font_css = font_css  # the STAM font's @font-face, from the main window's Api
        self.stats = compute_corpus_stats(verse_data, max_leaf_disj)
        self._diagrams: dict[str, dict] = {}

    def get_font_css(self) -> str:
        return self.font_css

    def get_diagrams(self, labels: list[str]) -> list[dict]:
        """``[{"ref", "diagram"}]`` for the pesuqim labelled ``labels`` (as
        in the verse lookup), in that order, greyed for this window's
        max_leaf_disj -- see ankipasuk.diagram."""
        lookup = self.get_verse_lookup()
        return [
            self._diagram(label) for label in labels if label in lookup and lookup[label]["pointed"].strip()
        ]

    def _diagram(self, label: str) -> dict:
        # Each structure tab shows its pesuqim again, so they're made once.
        if label not in self._diagrams:
            pointed = self.get_verse_lookup()[label]["pointed"]
            self._diagrams[label] = {
                "ref": _our_spelling(label), "diagram": pasuq_diagram(pointed, self.max_leaf_disj)
            }
        return self._diagrams[label]

    def get_summary(self) -> str:
        return format_stats_summary(self.stats, self.max_leaf_disj)

    def get_verse_lookup(self) -> dict:
        return self.stats["verse_lookup"] if self.stats else {}

    def get_distributions(self) -> dict:
        if self.stats is None:
            return {}
        s = self.stats
        return {
            "word_count": _dist_to_bars(s["word_count_dist"], s["word_count_bins"]),
            "disj_count": _dist_to_bars(s["disj_count_dist"], s["disj_count_bins"]),
            "clause_count": _dist_to_bars(s["clause_count_dist"], s["clause_count_bins"]),
            "depth": _dist_to_bars(s["depth_dist"], s["depth_bins"]),
            "ratio": _ratio_bars(s["ratio_dist"], s["ratio_bins"]),
            "max_leaf_disj": self.max_leaf_disj,
        }

    def get_trope_frequency(self) -> list:
        if self.stats is None:
            return []
        s = self.stats
        # Rank first (1 to 4), then the most frequent, as the diagram labels them.
        return [
            {"name": name, "hebrew": TROPE_HEBREW_NAMES.get(name, name), "rank": _RANKS.get(name, 0),
             "count": count, "verses": s["trope_bins"][name]}
            for name, count in sorted(s["trope_freq"].items(), key=lambda kv: (_RANKS.get(kv[0], 9), -kv[1]))
        ]

    def _structure(self, sig, labels: list[str]) -> dict:
        """One structure: its signature, how many pesuqim share it, which,
        and the diagram of the first of them as its example."""
        return {
            "label": format_structure(sig), "count": len(labels), "verses": labels,
            "example": self._diagram(labels[0]),
        }

    def get_structure_by_word_count(self) -> list:
        grouped = group_verses_by_word_count_and_structure(self.verse_data)
        return [
            {
                "axis_value": wc,
                "structures": [
                    self._structure(sig, labels)
                    for sig, labels in sorted(
                        structs.items(), key=lambda kv: (-len(kv[1]), format_structure(kv[0]))
                    )
                ],
            }
            for wc, structs in sorted(grouped.items())
        ]

    def get_structure_by_disj_count(self) -> list:
        grouped = group_verses_by_disj_count_and_structure(self.verse_data)
        return [
            {
                "axis_value": dc,
                "structures": [
                    self._structure(sig, labels)
                    for sig, labels in sorted(
                        structs.items(), key=lambda kv: (-len(kv[1]), format_structure(kv[0]))
                    )
                ],
            }
            for dc, structs in sorted(grouped.items())
        ]

    def get_structure_summary(self) -> list:
        summary = sorted(
            group_verses_by_structure(self.verse_data).items(),
            key=lambda kv: (-len(kv[1]), format_structure(kv[0])),
        )
        return [self._structure(sig, labels) for sig, labels in summary]

    def export_csv(self) -> dict:
        if self.stats is None:
            return {"ok": False, "error": "No verses to export."}
        if self._window is None:
            return {"ok": False, "error": "Window not ready."}

        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="verse_stats.csv",
            file_types=("CSV files (*.csv)", "All files (*.*)"),
        )
        if not path:
            return {"ok": False, "error": None}
        target = path if isinstance(path, str) else path[0]

        try:
            write_stats_csv(target, self.stats, self.max_leaf_disj)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": target}
