"""Clickable canvas charts for the stats window.

Pure tkinter (no external plotting dependency). Every chart function takes
a ``verse_lookup`` dict so that clicking a bar/point/row can show the
verses -- reference and Hebrew text -- behind it.
"""

from __future__ import annotations

import tkinter as tk
from collections import Counter

from ..config import PDF, RLE
from .fonts import pick_hebrew_font


def show_verse_list_popup(parent: tk.Misc, title: str, labels, verse_lookup: dict) -> None:
    """Window listing the verses (reference + Hebrew text) behind a clicked
    bar/point/trope."""
    from ..stats import _label_sort_key

    labels = sorted(set(labels), key=_label_sort_key)
    hebrew_font = pick_hebrew_font()

    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("560x480")

    tk.Label(win, text=title, anchor="w", font=("Arial", 10, "bold")).pack(fill="x", padx=8, pady=(8, 0))
    tk.Label(win, text=f"{len(labels)} verse(s)", anchor="w", fg="gray30").pack(fill="x", padx=8)

    text_frame = tk.Frame(win)
    text_frame.pack(fill="both", expand=True, padx=8, pady=8)
    text_frame.grid_rowconfigure(0, weight=1)
    text_frame.grid_columnconfigure(0, weight=1)

    # wrap=NONE + horizontal scroll, not wrap=WORD: Tk's word-wrap can
    # visibly scramble word order within a Hebrew line when it splits that
    # line across multiple display lines -- it applies bidi reordering to
    # the logical line as a whole and then chops the result for display,
    # rather than reordering per visual line.
    text = tk.Text(text_frame, wrap=tk.NONE, font=(hebrew_font, 12))
    text.grid(row=0, column=0, sticky="nsew")

    scroll_y = tk.Scrollbar(text_frame, orient="vertical", command=text.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    text.configure(yscrollcommand=scroll_y.set)

    scroll_x = tk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
    scroll_x.grid(row=1, column=0, sticky="ew")
    text.configure(xscrollcommand=scroll_x.set)

    text.tag_configure("ref", font=("Arial", 10, "bold"), foreground="#37474f", spacing1=10, spacing3=2)
    text.tag_configure("verse", font=(hebrew_font, 13), spacing3=4, justify="right")

    for label in labels:
        entry = verse_lookup.get(label)
        text.insert(tk.END, f"{label}\n", ("ref",))
        if entry and entry.get("pointed"):
            text.insert(tk.END, RLE + entry["pointed"] + PDF + "\n", ("verse",))
        else:
            text.insert(tk.END, "(text unavailable)\n", ("verse",))

    text.config(state="disabled")


def _bind_clickable(canvas: tk.Canvas, item, title: str, labels, verse_lookup: dict) -> None:
    canvas.tag_bind(
        item, "<Button-1>",
        lambda e, t=title, lbls=labels, vl=verse_lookup: show_verse_list_popup(canvas, t, lbls, vl)
    )
    canvas.tag_bind(item, "<Enter>", lambda e: canvas.config(cursor="hand2"))
    canvas.tag_bind(item, "<Leave>", lambda e: canvas.config(cursor=""))


def draw_bar_chart(canvas: tk.Canvas, dist: Counter, bins: dict, x_label: str, verse_lookup: dict,
                    bar_color: str = "#64b5f6", value_formatter=str) -> None:
    """Draw a clickable bar chart of {value: count}. Clicking a bar opens a
    popup listing the verses in that bin."""
    canvas.delete("all")
    if not dist:
        canvas.create_text(20, 20, anchor="w", text="No data.")
        return

    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 400)
    height = max(canvas.winfo_height(), 260)

    margin_left, margin_right = 45, 20
    margin_top, margin_bottom = 20, 40

    keys = sorted(dist.keys())
    values = [dist[k] for k in keys]
    max_val = max(values) if values else 1

    plot_w = max(width - margin_left - margin_right, 10)
    plot_h = max(height - margin_top - margin_bottom, 10)
    n = len(keys)
    bar_w = plot_w / n

    canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom)
    canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom)
    canvas.create_text(margin_left - 8, margin_top, text=str(max_val), anchor="e", font=("Arial", 8))

    for i, (k, v) in enumerate(zip(keys, values)):
        bar_h = (v / max_val) * plot_h if max_val else 0
        x0 = margin_left + i * bar_w + 2
        x1 = margin_left + (i + 1) * bar_w - 2
        y1 = height - margin_bottom
        y0 = y1 - bar_h
        rect = canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline="")
        canvas.create_text((x0 + x1) / 2, y1 + 12, text=value_formatter(k), font=("Arial", 8))
        if v:
            canvas.create_text((x0 + x1) / 2, y0 - 8, text=str(v), font=("Arial", 8))

        labels_here = bins.get(k, [])
        if labels_here:
            _bind_clickable(canvas, rect, f"{x_label} = {value_formatter(k)}", labels_here, verse_lookup)

    canvas.create_text(width / 2, height - 10, text=x_label, font=("Arial", 9, "bold"))


def draw_chapter_bar_chart(canvas: tk.Canvas, chapters, series, bins: dict, verse_lookup: dict) -> None:
    """Grouped bar chart, one group per chapter. ``series`` is a list of
    (name, color, {chapter: value}) tuples. Clicking any bar in a chapter's
    group opens the verse list for that chapter."""
    canvas.delete("all")
    if not chapters:
        canvas.create_text(20, 20, anchor="w", text="No data.")
        return

    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 400)
    height = max(canvas.winfo_height(), 260)

    margin_left, margin_right = 45, 20
    margin_top, margin_bottom = 40, 40

    all_vals = [v for _, _, vals in series for v in vals.values()]
    max_val = max(all_vals) if all_vals else 1

    plot_w = max(width - margin_left - margin_right, 10)
    plot_h = max(height - margin_top - margin_bottom, 10)
    n = len(chapters)
    group_w = plot_w / n
    bar_w = group_w / (len(series) + 1)

    canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom)
    canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom)
    canvas.create_text(margin_left - 8, margin_top, text=f"{max_val:.1f}", anchor="e", font=("Arial", 8))

    for s_idx, (name, color, _vals) in enumerate(series):
        lx = margin_left + s_idx * 140
        canvas.create_rectangle(lx, 4, lx + 10, 14, fill=color, outline="")
        canvas.create_text(lx + 14, 9, text=name, anchor="w", font=("Arial", 8))

    for i, ch in enumerate(chapters):
        group_x0 = margin_left + i * group_w
        labels_here = bins.get(ch, [])
        for s_idx, (_name, color, vals) in enumerate(series):
            v = vals.get(ch, 0)
            bar_h = (v / max_val) * plot_h if max_val else 0
            x0 = group_x0 + s_idx * bar_w + 2
            x1 = x0 + bar_w - 2
            y1 = height - margin_bottom
            y0 = y1 - bar_h
            rect = canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            if labels_here:
                _bind_clickable(canvas, rect, f"Chapter {ch}", labels_here, verse_lookup)
        canvas.create_text(group_x0 + group_w / 2, height - margin_bottom + 12,
                            text=str(ch), font=("Arial", 8))

    canvas.create_text(width / 2, height - 10, text="Chapter", font=("Arial", 9, "bold"))


def draw_scatter_chart(canvas: tk.Canvas, points: dict, x_label: str, y_label: str,
                        verse_lookup: dict) -> None:
    """Scatter plot of verse length vs. split-tree depth (or any other x/y
    pair). ``points`` maps (x, y) -> [verse labels]; dot size reflects how
    many verses share that exact (x, y). Clicking a dot lists those verses."""
    canvas.delete("all")
    if not points:
        canvas.create_text(20, 20, anchor="w", text="No data.")
        return

    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 400)
    height = max(canvas.winfo_height(), 300)

    margin_left, margin_right = 50, 20
    margin_top, margin_bottom = 20, 45

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    plot_w = max(width - margin_left - margin_right, 10)
    plot_h = max(height - margin_top - margin_bottom, 10)

    def to_px(x, y):
        px = margin_left + (x - x_min) / (x_max - x_min) * plot_w
        py = height - margin_bottom - (y - y_min) / (y_max - y_min) * plot_h
        return px, py

    canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom)
    canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom)
    canvas.create_text(
        margin_left - 8, height - margin_bottom, text=str(y_min), anchor="e", font=("Arial", 8)
    )
    canvas.create_text(margin_left - 8, margin_top, text=str(y_max), anchor="e", font=("Arial", 8))
    canvas.create_text(margin_left, height - margin_bottom + 16, text=str(x_min), font=("Arial", 8))
    canvas.create_text(width - margin_right, height - margin_bottom + 16, text=str(x_max), font=("Arial", 8))

    max_count = max(len(v) for v in points.values())

    for (x, y), labels in points.items():
        px, py = to_px(x, y)
        r = 4 + 6 * (len(labels) / max_count)
        dot = canvas.create_oval(px - r, py - r, px + r, py + r, fill="#7e57c2", outline="")
        _bind_clickable(canvas, dot, f"{x_label} = {x}, {y_label} = {y}", labels, verse_lookup)

    canvas.create_text(width / 2, height - 10, text=x_label, font=("Arial", 9, "bold"))
    canvas.create_text(15, height / 2, text=y_label, angle=90, font=("Arial", 9, "bold"))
