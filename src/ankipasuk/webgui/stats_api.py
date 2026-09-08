"""API bridge for the Corpus Statistics window.

Computes everything once via the existing GUI-agnostic ``stats.py``
(``compute_corpus_stats``) and ``structure.py`` on window creation, then
serves it to the JS frontend as plain JSON-serializable data -- no new
statistics logic lives here, only adaptation for the JS side.
"""

from __future__ import annotations

import webview

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


class StatsApi:
    def __init__(self, verse_data: list[dict], max_leaf_disj: int) -> None:
        self._window: webview.Window | None = None
        self.verse_data = verse_data
        self.max_leaf_disj = max_leaf_disj
        self.stats = compute_corpus_stats(verse_data, max_leaf_disj)

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
            "ratio": _dist_to_bars(s["ratio_dist"], s["ratio_bins"], value_formatter=lambda k: f"{k:g}"),
            "max_leaf_disj": self.max_leaf_disj,
        }

    def get_chapter_data(self) -> dict:
        if self.stats is None:
            return {"chapters": []}
        s = self.stats
        return {
            "chapters": [
                {
                    "book": book,
                    "chapter": ch,
                    "avg_words": s["chapter_avg_words"][(book, ch)],
                    "avg_disj": s["chapter_avg_disj"][(book, ch)],
                    "verses": s["chapter_bins"][(book, ch)],
                }
                for (book, ch) in s["chapters"]
            ]
        }

    def get_trope_frequency(self) -> list:
        if self.stats is None:
            return []
        s = self.stats
        return [
            {"name": name, "count": count, "verses": s["trope_bins"][name]}
            for name, count in sorted(s["trope_freq"].items(), key=lambda kv: -kv[1])
        ]

    def get_structure_by_word_count(self) -> list:
        grouped = group_verses_by_word_count_and_structure(self.verse_data)
        return [
            {
                "axis_value": wc,
                "structures": [
                    {"label": format_structure(sig), "count": len(labels), "verses": labels}
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
                    {"label": format_structure(sig), "count": len(labels), "verses": labels}
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
        return [
            {"label": format_structure(sig), "count": len(labels), "verses": labels}
            for sig, labels in summary
        ]

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
