"""The 'Corpus statistics' window, opened from the main app."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..stats import compute_corpus_stats, format_stats_summary, write_stats_csv
from ..structure import (
    format_structure,
    group_verses_by_disj_count_and_structure,
    group_verses_by_word_count_and_structure,
)
from .charts import draw_bar_chart, draw_chapter_bar_chart, draw_scatter_chart, show_verse_list_popup


def build_trope_frequency_widget(parent: tk.Misc, stats: dict) -> tk.Text:
    """Text widget listing disjunctive trope frequency; click a line to see
    which verses contain that trope."""
    text = tk.Text(parent, wrap=tk.WORD, font=("Courier", 10), cursor="arrow")
    text.pack(fill="both", expand=True)

    if not stats["trope_freq"]:
        text.insert("1.0", "No disjunctive tropes found.")
        text.config(state="disabled")
        return text

    text.insert(tk.END, "Click a trope to see which verses contain it.\n\n")
    for name, cnt in stats["trope_freq"].most_common():
        tag = f"trope_{name}"
        text.insert(tk.END, f"{name}: {cnt}\n", (tag,))
        text.tag_configure(tag, foreground="#1565c0")
        labels = stats["trope_bins"].get(name, [])
        text.tag_bind(
            tag, "<Button-1>",
            lambda e, n=name, lbls=labels: show_verse_list_popup(
                text, f"Trope: {n}", lbls, stats["verse_lookup"]
            )
        )
        text.tag_bind(tag, "<Enter>", lambda e: text.config(cursor="hand2"))
        text.tag_bind(tag, "<Leave>", lambda e: text.config(cursor="arrow"))

    text.config(state="disabled")
    return text


def build_structure_breakdown_widget(
    parent: tk.Misc, axis_label: str, grouped: dict, verse_lookup: dict
) -> tk.Text:
    """Text widget listing, for each value of some axis (word count or
    disjunctive-group count), every distinct verse nesting-structure that
    occurs at that value and how many verses share it. Click a structure
    line to see its verses.

    ``grouped`` is ``{axis_value: {structure_signature: [verse_labels]}}``
    -- see :func:`ankipasuk.structure.group_verses_by_word_count_and_structure`
    / :func:`ankipasuk.structure.group_verses_by_disj_count_and_structure`.
    """
    text = tk.Text(parent, wrap=tk.WORD, font=("Courier", 10), cursor="arrow")
    text.pack(fill="both", expand=True)

    if not grouped:
        text.insert("1.0", "No data.")
        text.config(state="disabled")
        return text

    text.insert(tk.END, "Click a structure to see its verses.\n\n")
    tag_counter = 0
    for axis_value in sorted(grouped):
        structs = grouped[axis_value]
        total = sum(len(labels) for labels in structs.values())
        text.insert(tk.END, f"{axis_label} = {axis_value}  ({total} verse{'s' if total != 1 else ''})\n")

        for sig, labels in sorted(structs.items(), key=lambda kv: (-len(kv[1]), format_structure(kv[0]))):
            tag_counter += 1
            tag = f"struct_{tag_counter}"
            text.insert(tk.END, f"    {format_structure(sig)}   x{len(labels)}\n", (tag,))
            text.tag_configure(tag, foreground="#1565c0")
            text.tag_bind(
                tag, "<Button-1>",
                lambda e, s=sig, lbls=labels, av=axis_value: show_verse_list_popup(
                    text, f"{axis_label} = {av}, structure {format_structure(s)}", lbls, verse_lookup
                )
            )
            text.tag_bind(tag, "<Enter>", lambda e: text.config(cursor="hand2"))
            text.tag_bind(tag, "<Leave>", lambda e: text.config(cursor="arrow"))

        text.insert(tk.END, "\n")

    text.config(state="disabled")
    return text


def _export_stats_to_csv(parent: tk.Misc, stats: dict, max_leaf_disj: int) -> None:
    if stats is None:
        messagebox.showerror("Nothing to export", "No stats to export.", parent=parent)
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="Export per-verse stats to CSV",
        parent=parent,
    )
    if not path:
        return

    try:
        write_stats_csv(path, stats, max_leaf_disj)
    except OSError as e:
        messagebox.showerror("Export failed", str(e), parent=parent)
        return

    messagebox.showinfo("Export complete", f"Exported per-verse stats to:\n{path}", parent=parent)


def show_stats_window(parent: tk.Misc, verse_data, max_leaf_disj: int) -> None:
    """Open the corpus-statistics window for the given verse range."""
    if not verse_data:
        messagebox.showerror("Nothing to analyze", "Fetch a range of verses first.", parent=parent)
        return

    stats = compute_corpus_stats(verse_data, max_leaf_disj)
    if stats is None:
        messagebox.showerror("Nothing to analyze", "No verse lines were found to analyze.", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title("Corpus statistics")
    win.geometry("960x720")

    tk.Label(
        win, text="Click any bar, point, or trope to see the verses behind it.",
        anchor="w", fg="gray30"
    ).pack(fill="x", padx=8, pady=(8, 0))

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # --- Summary tab ---
    summary_frame = tk.Frame(notebook)
    notebook.add(summary_frame, text="Summary")
    summary_text = tk.Text(summary_frame, wrap=tk.WORD, font=("Courier", 10))
    summary_text.pack(fill="both", expand=True)
    summary_text.insert("1.0", format_stats_summary(stats, max_leaf_disj))
    summary_text.config(state="disabled")

    # --- Words / verse distribution ---
    wc_frame = tk.Frame(notebook)
    notebook.add(wc_frame, text="Words / verse")
    wc_canvas = tk.Canvas(wc_frame, bg="white")
    wc_canvas.pack(fill="both", expand=True)
    wc_frame.bind(
        "<Configure>",
        lambda e: draw_bar_chart(wc_canvas, stats["word_count_dist"], stats["word_count_bins"],
                                  "Words in verse", stats["verse_lookup"])
    )

    # --- Minimum disjunctive groups / verse distribution ---
    dc_frame = tk.Frame(notebook)
    notebook.add(dc_frame, text="Disjunctive groups / verse")
    dc_canvas = tk.Canvas(dc_frame, bg="white")
    dc_canvas.pack(fill="both", expand=True)
    dc_frame.bind(
        "<Configure>",
        lambda e: draw_bar_chart(dc_canvas, stats["disj_count_dist"], stats["disj_count_bins"],
                                  "Minimum disjunctive groups in verse", stats["verse_lookup"],
                                  bar_color="#81c784")
    )

    # --- Clauses after splitting (depends on max_leaf_disj) ---
    cc_frame = tk.Frame(notebook)
    notebook.add(cc_frame, text=f"Clauses / verse (max {max_leaf_disj}/leaf)")
    cc_canvas = tk.Canvas(cc_frame, bg="white")
    cc_canvas.pack(fill="both", expand=True)
    cc_frame.bind(
        "<Configure>",
        lambda e: draw_bar_chart(cc_canvas, stats["clause_count_dist"], stats["clause_count_bins"],
                                  "Cloze clauses after splitting", stats["verse_lookup"],
                                  bar_color="#ffb74d")
    )

    # --- Split-tree depth (depends on max_leaf_disj) ---
    depth_frame = tk.Frame(notebook)
    notebook.add(depth_frame, text=f"Split depth (max {max_leaf_disj}/leaf)")
    depth_canvas = tk.Canvas(depth_frame, bg="white")
    depth_canvas.pack(fill="both", expand=True)
    depth_frame.bind(
        "<Configure>",
        lambda e: draw_bar_chart(depth_canvas, stats["depth_dist"], stats["depth_bins"],
                                  "Split-tree depth", stats["verse_lookup"], bar_color="#e57373")
    )

    # --- Words per disjunctive group ---
    ratio_frame = tk.Frame(notebook)
    notebook.add(ratio_frame, text="Words / disjunctive group")
    ratio_canvas = tk.Canvas(ratio_frame, bg="white")
    ratio_canvas.pack(fill="both", expand=True)
    ratio_frame.bind(
        "<Configure>",
        lambda e: draw_bar_chart(ratio_canvas, stats["ratio_dist"], stats["ratio_bins"],
                                  "Words per disjunctive group", stats["verse_lookup"],
                                  bar_color="#4db6ac", value_formatter=lambda k: f"{k:g}")
    )

    # --- By chapter (avg words & avg disjunctive groups) ---
    chapter_frame = tk.Frame(notebook)
    notebook.add(chapter_frame, text="By chapter")
    chapter_canvas = tk.Canvas(chapter_frame, bg="white")
    chapter_canvas.pack(fill="both", expand=True)
    chapter_series = [
        ("Avg words", "#64b5f6", stats["chapter_avg_words"]),
        ("Avg disjunctive groups", "#81c784", stats["chapter_avg_disj"]),
    ]
    chapter_frame.bind(
        "<Configure>",
        lambda e: draw_chapter_bar_chart(chapter_canvas, stats["chapters"], chapter_series,
                                          stats["chapter_bins"], stats["verse_lookup"])
    )

    # --- Verse length vs. split-tree depth correlation ---
    corr_frame = tk.Frame(notebook)
    notebook.add(corr_frame, text="Length vs. depth")
    corr_canvas = tk.Canvas(corr_frame, bg="white")
    corr_canvas.pack(fill="both", expand=True)
    corr_frame.bind(
        "<Configure>",
        lambda e: draw_scatter_chart(corr_canvas, stats["scatter_points"],
                                      "Words in verse", "Split-tree depth", stats["verse_lookup"])
    )

    # --- Trope frequency ---
    trope_frame = tk.Frame(notebook)
    notebook.add(trope_frame, text="Trope frequency")
    build_trope_frequency_widget(trope_frame, stats)

    # --- Verse structure by word count ---
    struct_wc_frame = tk.Frame(notebook)
    notebook.add(struct_wc_frame, text="Structure by word count")
    struct_by_wc = group_verses_by_word_count_and_structure(verse_data)
    build_structure_breakdown_widget(struct_wc_frame, "Words in verse", struct_by_wc, stats["verse_lookup"])

    # --- Verse structure by disjunctive group count ---
    struct_dc_frame = tk.Frame(notebook)
    notebook.add(struct_dc_frame, text="Structure by disjunctive groups")
    struct_by_dc = group_verses_by_disj_count_and_structure(verse_data)
    build_structure_breakdown_widget(
        struct_dc_frame, "Disjunctive groups in verse", struct_by_dc, stats["verse_lookup"]
    )

    tk.Button(
        win, text="Export per-verse stats to CSV",
        command=lambda: _export_stats_to_csv(win, stats, max_leaf_disj)
    ).pack(pady=(0, 8))
