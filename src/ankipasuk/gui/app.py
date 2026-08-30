"""The main application window."""

from __future__ import annotations

import csv
import threading
import tkinter as tk
import traceback
from functools import partial
from tkinter import filedialog, messagebox, ttk

from ..cache import SefariaCache
from ..cloze import verse_to_nested_cloze
from ..config import (
    BOOK_HEBREW_NAMES,
    CSV_FLAGS,
    GUIDE_BG,
    INDENT_SPACES_PER_LEVEL,
    INDENT_UNIT_PX,
    PDF,
    POINTED_VERSION,
    RLE,
    TORAH_BOOKS,
    TORAH_VERSE_COUNTS,
    UNIT_COLORS,
)
from ..sefaria import (
    fetch_torah_range,
    get_aliyah_ref,
    get_parasha_structure,
    get_text_for_ref,
    parse_start_ref,
)
from ..text_processing import format_units, strip_vowels_and_trope
from .anki_connect_window import show_anki_connect_tools
from .fonts import pick_hebrew_font
from .stats_window import show_stats_window


class AnkiPasukApp:
    """Builds and wires up the main Tk window.

    All mutable UI state (fetched verses, dropdown state, widget refs)
    lives on the instance rather than as module globals, which is what
    makes this safe to construct more than once (e.g. in tests).
    """

    PADX = 10
    PADY = 8

    def __init__(self, root: tk.Tk, cache: SefariaCache | None = None):
        self.root = root
        self.cache = cache if cache is not None else SefariaCache()

        # Synchronized verse dataset: list of dicts {"ch", "vs", "pointed", "plain"}
        self.current_verse_data: list[dict] = []
        self._updating_dropdowns = False

        self._build_vars()
        self._build_widgets()
        self._wire_traces()

        self.update_chapter_dropdowns()
        self.update_parasha_dropdowns()
        self.update_mode_visibility()
        self.update_line_count()
        self.update_cache_status()

    # =============================================================
    #  VARS
    # =============================================================
    def _build_vars(self) -> None:
        self.selection_mode_var = tk.StringVar(value="Chapter / Verse")
        self.book_var = tk.StringVar(value="Genesis")

        self.start_ch_var = tk.StringVar(value="1")
        self.start_vs_var = tk.StringVar(value="1")
        self.end_ch_var = tk.StringVar(value="1")
        self.end_vs_var = tk.StringVar(value="1")

        self.parasha_var = tk.StringVar(value="")
        self.aliyah_var = tk.StringVar(value="1")

        self.reset_per_line_var = tk.BooleanVar(value=True)
        self.line_count_var = tk.StringVar(value="Lines: 0")
        self.cache_status_var = tk.StringVar(value="")

    # =============================================================
    #  DROPDOWN HELPERS
    # =============================================================
    @staticmethod
    def chapter_count(book: str) -> int:
        return len(TORAH_VERSE_COUNTS[book])

    @staticmethod
    def verse_count(book: str, chapter: int) -> int:
        return TORAH_VERSE_COUNTS[book][chapter - 1]

    @staticmethod
    def set_combobox_values(combo: ttk.Combobox, values, current_var: tk.StringVar) -> None:
        str_values = [str(v) for v in values]
        combo["values"] = str_values
        if str_values and current_var.get() not in str_values:
            current_var.set(str_values[0])
        elif not str_values:
            current_var.set("")

    def is_cv_mode(self) -> bool:
        return self.selection_mode_var.get() == "Chapter / Verse"

    def update_chapter_dropdowns(self, *_args) -> None:
        if self._updating_dropdowns:
            return
        self._updating_dropdowns = True
        try:
            book = self.book_var.get()
            chapters = list(range(1, self.chapter_count(book) + 1))
            self.set_combobox_values(self.start_ch_combo, chapters, self.start_ch_var)
            self.set_combobox_values(self.end_ch_combo, chapters, self.end_ch_var)
            self.update_verse_dropdowns()
        finally:
            self._updating_dropdowns = False

    def update_verse_dropdowns(self, *_args) -> None:
        if self._updating_dropdowns:
            return
        self._updating_dropdowns = True
        try:
            book = self.book_var.get()

            try:
                start_ch = int(self.start_ch_var.get())
            except ValueError:
                start_ch = 1
                self.start_ch_var.set("1")

            try:
                end_ch = int(self.end_ch_var.get())
            except ValueError:
                end_ch = 1
                self.end_ch_var.set("1")

            if end_ch < start_ch:
                self.end_ch_var.set(str(start_ch))
                end_ch = start_ch

            start_verses = list(range(1, self.verse_count(book, start_ch) + 1))
            end_verses = list(range(1, self.verse_count(book, end_ch) + 1))

            self.set_combobox_values(self.start_vs_combo, start_verses, self.start_vs_var)
            self.set_combobox_values(self.end_vs_combo, end_verses, self.end_vs_var)

            try:
                sv = int(self.start_vs_var.get())
                ev = int(self.end_vs_var.get())
            except ValueError:
                return

            if end_ch == start_ch and ev < sv:
                self.end_vs_var.set(str(sv))
        finally:
            self._updating_dropdowns = False

    def update_parasha_dropdowns(self, *_args) -> None:
        book = self.book_var.get()
        try:
            parashot = get_parasha_structure(book, self.cache)
        except Exception:
            traceback.print_exc()
            self.parasha_combo["values"] = []
            self.aliyah_combo["values"] = []
            self.parasha_var.set("")
            self.aliyah_var.set("")
            return

        names = [p["name"] for p in parashot]
        self.set_combobox_values(self.parasha_combo, names, self.parasha_var)
        self.update_aliyah_dropdown()

    def update_aliyah_dropdown(self, *_args) -> None:
        book = self.book_var.get()
        parasha_name = self.parasha_var.get()

        if not parasha_name:
            self.aliyah_combo["values"] = []
            self.aliyah_var.set("")
            return

        try:
            parashot = get_parasha_structure(book, self.cache)
        except Exception:
            traceback.print_exc()
            self.aliyah_combo["values"] = []
            self.aliyah_var.set("")
            return

        for p in parashot:
            if p["name"] == parasha_name:
                aliyot = list(range(1, len(p["refs"]) + 1))
                self.set_combobox_values(self.aliyah_combo, aliyot, self.aliyah_var)
                return

        self.aliyah_combo["values"] = []
        self.aliyah_var.set("")

    def update_mode_visibility(self, *_args) -> None:
        if self.is_cv_mode():
            self.cv_frame.grid()
            self.pa_frame.grid_remove()
        else:
            self.pa_frame.grid()
            self.cv_frame.grid_remove()

    # =============================================================
    #  DISPLAY HELPERS
    # =============================================================
    @staticmethod
    def render_colored_tree(node, text_widget: tk.Text, depth=0, indent_level=0, extra_bias=0) -> None:
        eff_indent = indent_level + extra_bias

        depth_tag = f"depth{depth}"
        text_widget.tag_configure(
            depth_tag,
            background=UNIT_COLORS[depth % len(UNIT_COLORS)],
            justify="right",
        )

        # Nesting depth is shown as a margin on the right -- the side
        # Hebrew text actually starts from -- rather than the left, so
        # deeper clauses visually indent inward from where reading begins.
        indent_tag = f"indent{eff_indent}"
        text_widget.tag_configure(
            indent_tag,
            rmargin=INDENT_UNIT_PX * eff_indent,
            justify="right",
        )

        text_widget.tag_configure("guide", background=GUIDE_BG)
        text_widget.tag_configure("conj", foreground="gray40")

        if isinstance(node, dict):
            AnkiPasukApp.render_colored_tree(
                node["left"], text_widget, depth + 1, indent_level + 1, extra_bias
            )
            AnkiPasukApp.render_colored_tree(
                node["right"], text_widget, depth + 1, indent_level, extra_bias + 1
            )
            return

        # Words go in in their natural (logical) reading order -- Tk's own
        # bidi handling of the RLE-embedded Hebrew run displays this
        # correctly right-to-left; no manual reversal needed or wanted.
        first = True
        for u in node:
            for sub in u["subs"]:
                if not first:
                    text_widget.insert(tk.END, " ", (depth_tag, indent_tag))
                first = False
                tags = [depth_tag, indent_tag]
                if sub["level"] == 0:
                    tags.append("conj")
                text_widget.insert(tk.END, RLE + sub["text"] + PDF, tuple(tags))

        if eff_indent > 0:
            text_widget.insert(tk.END, " ", ("guide", indent_tag))
            for _ in range(eff_indent):
                text_widget.insert(tk.END, "\u00A0" * INDENT_SPACES_PER_LEVEL, ("guide", indent_tag))

        text_widget.insert(tk.END, "\n", ())

    @staticmethod
    def set_display_text(widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.tag_configure("rtl", justify="right")

        lines = text.splitlines()
        for i, line in enumerate(lines):
            widget.insert(tk.END, RLE + line + PDF, ("rtl",))
            if i < len(lines) - 1:
                widget.insert(tk.END, "\n")

        widget.config(state="disabled")

    def update_line_count(self) -> None:
        self.line_count_var.set(f"Lines: {len(self.current_verse_data)}")

    def update_cache_status(self) -> None:
        s = self.cache.stats()
        self.cache_status_var.set(
            f"Cache: {s['cached_refs']} ref(s), {s['cached_books']} book structure(s)"
        )

    # =============================================================
    #  GUI ACTIONS
    # =============================================================
    def _fetch_chapter_verse_range(self, book, start_ch, start_vs, end_ch, end_vs):
        return fetch_torah_range(book, start_ch, start_vs, end_ch, end_vs, self.cache, POINTED_VERSION)

    def _fetch_parasha_aliyah(self, book, parasha_name, aliyah_num):
        ref_str = get_aliyah_ref(book, parasha_name, aliyah_num, self.cache)
        pointed_verses = get_text_for_ref(ref_str, POINTED_VERSION, self.cache)
        start_ch, start_vs = parse_start_ref(ref_str)

        data = []
        ch, vs = start_ch, start_vs
        for pointed in pointed_verses:
            plain = strip_vowels_and_trope(pointed)
            data.append({"ch": ch, "vs": vs, "pointed": pointed, "plain": plain})
            vs += 1
            if ch <= self.chapter_count(book) and vs > self.verse_count(book, ch):
                vs = 1
                ch += 1
        return data

    def populate_input_from_api(self) -> None:
        mode = self.selection_mode_var.get()
        book = self.book_var.get()

        # Validate/collect inputs synchronously (fast, no network) so bad
        # input is reported immediately without spinning up a thread.
        if mode == "Chapter / Verse":
            try:
                start_ch = int(self.start_ch_var.get())
                start_vs = int(self.start_vs_var.get())
                end_ch = int(self.end_ch_var.get())
                end_vs = int(self.end_vs_var.get())
            except ValueError:
                messagebox.showerror("Invalid input", "Please make a valid selection.")
                return
            worker = partial(self._fetch_chapter_verse_range, book, start_ch, start_vs, end_ch, end_vs)

        elif mode == "Parashah / Aliyah":
            parasha_name = self.parasha_var.get()
            try:
                aliyah_num = int(self.aliyah_var.get())
            except ValueError:
                messagebox.showerror("Invalid input", "Please make a valid selection.")
                return
            worker = partial(self._fetch_parasha_aliyah, book, parasha_name, aliyah_num)

        else:
            messagebox.showerror("Invalid input", "Unknown selection mode.")
            return

        # Run the actual Sefaria network I/O on a background thread so the
        # GUI doesn't freeze during multi-chapter fetches (cache hits return
        # instantly, but a miss still has to wait on the network); results
        # are marshalled back onto the main thread via root.after.
        self.fetch_button.config(state="disabled", text="Fetching...")
        self.root.config(cursor="watch")

        def run():
            try:
                result, error = worker(), None
            except Exception as e:  # noqa: BLE001 - reported to the user below
                result, error = None, e
            self.root.after(0, lambda: self._on_fetch_complete(result, error))

        threading.Thread(target=run, daemon=True).start()

    def _on_fetch_complete(self, result, error) -> None:
        self.fetch_button.config(state="normal", text="Fetch range from Sefaria")
        self.root.config(cursor="")

        if error is not None:
            if isinstance(error, ValueError):
                messagebox.showerror("Invalid input", str(error))
            else:
                traceback.print_exc()
                messagebox.showerror("Sefaria fetch failed", str(error))
            return

        self.current_verse_data = result

        pointed_text = "\n".join(item["pointed"] for item in self.current_verse_data)
        plain_text = "\n".join(item["plain"] for item in self.current_verse_data)

        self.set_display_text(self.input_box, pointed_text)
        self.set_display_text(self.plain_box, plain_text)
        self.update_line_count()
        self.update_cache_status()

    def _get_max_leaf_disj(self) -> int:
        try:
            max_leaf_disj = int(self.max_leaf_entry.get())
            if max_leaf_disj < 1:
                return 2
            return max_leaf_disj
        except ValueError:
            return 2

    def generate_output(self) -> None:
        if not self.current_verse_data:
            return

        max_leaf_disj = self._get_max_leaf_disj()
        reset_per_line = self.reset_per_line_var.get()

        lines = []
        trees = []
        unit_debug_lines = []
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
            trees.append(tree)
            unit_debug_lines.append(format_units(units))

            if not reset_per_line:
                next_start = last + 1

        self.output_box.delete("1.0", tk.END)
        self.output_box.insert(tk.END, "\n".join(lines) if lines else "")

        self.tokens_box.delete("1.0", tk.END)
        self.tokens_box.insert(tk.END, "\n\n".join(unit_debug_lines))

        self.viz_output.delete("1.0", tk.END)
        for t in trees:
            self.render_colored_tree(t, self.viz_output, depth=0, indent_level=0, extra_bias=0)
            self.viz_output.insert(tk.END, "\n")

    def build_csv_rows(self):
        if not self.current_verse_data:
            return []

        max_leaf_disj = self._get_max_leaf_disj()
        reset_per_line = self.reset_per_line_var.get()
        book = self.book_var.get()
        hebrew_book = BOOK_HEBREW_NAMES.get(book, book)

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

            rows.append([
                str(i + 1),
                verse_label,
                cl,
                plain,
                prev_plain,
                next_plain,
                "",
                CSV_FLAGS,
            ])

        return rows

    def export_to_csv(self) -> None:
        if not self.current_verse_data:
            messagebox.showerror("Nothing to export", "Fetch a range of verses first.")
            return

        try:
            rows = self.build_csv_rows()
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
            return

        if not rows:
            messagebox.showerror("Nothing to export", "No verse lines were found to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export cloze cards to CSV",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
                writer.writerows(rows)
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return

        messagebox.showinfo("Export complete", f"Exported {len(rows)} card(s) to:\n{path}")

    def show_stats(self) -> None:
        show_stats_window(self.root, self.current_verse_data, self._get_max_leaf_disj())

    def open_anki_connect_tools(self) -> None:
        show_anki_connect_tools(self.root)

    def clear_cache(self) -> None:
        if not messagebox.askyesno(
            "Clear cache",
            "This deletes all locally cached Sefaria text and parashah data. "
            "It will be re-downloaded next time it's needed. Continue?",
        ):
            return
        self.cache.clear()
        self.update_cache_status()
        messagebox.showinfo("Cache cleared", "The local Sefaria cache has been cleared.")

    def copy_cloze_to_clipboard(self) -> None:
        text = self.output_box.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def copy_pointed_to_clipboard(self) -> None:
        text = "\n".join(item["pointed"] for item in self.current_verse_data)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def copy_plain_to_clipboard(self) -> None:
        text = "\n".join(item["plain"] for item in self.current_verse_data)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    # =============================================================
    #  WIDGET LAYOUT
    # =============================================================
    def _build_widgets(self) -> None:
        root = self.root
        PADX, PADY = self.PADX, self.PADY

        menubar = tk.Menu(root)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="AnkiConnect Tools...", command=self.open_anki_connect_tools)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        root.config(menu=menubar)

        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=2)
        root.grid_rowconfigure(4, weight=2)
        root.grid_rowconfigure(6, weight=3)

        # --- Source controls ---
        source_labelframe = ttk.LabelFrame(root, text="Source (Sefaria, Torah only)")
        source_labelframe.grid(
            row=0, column=0, rowspan=2, columnspan=2, sticky="ew", padx=PADX, pady=(PADY, 4)
        )

        source_frame = ttk.Frame(source_labelframe)
        source_frame.pack(fill="x", padx=8, pady=6)
        source_frame.grid_columnconfigure(99, weight=1)

        ttk.Label(source_frame, text="Mode:").grid(row=0, column=0, padx=(0, 4), sticky="w")
        mode_combo = ttk.Combobox(
            source_frame, textvariable=self.selection_mode_var,
            values=["Chapter / Verse", "Parashah / Aliyah"], state="readonly", width=18
        )
        mode_combo.grid(row=0, column=1, padx=(0, 12), sticky="w")

        ttk.Label(source_frame, text="Book:").grid(row=0, column=2, padx=(0, 4), sticky="w")
        book_combo = ttk.Combobox(
            source_frame, textvariable=self.book_var,
            values=list(TORAH_BOOKS.keys()), state="readonly", width=14
        )
        book_combo.grid(row=0, column=3, padx=(0, 12), sticky="w")

        cv_frame = ttk.Frame(source_frame)
        cv_frame.grid(row=0, column=4, columnspan=10, sticky="w")
        self.cv_frame = cv_frame

        ttk.Label(cv_frame, text="Start chapter:").grid(row=0, column=0, padx=(0, 4), sticky="w")
        self.start_ch_combo = ttk.Combobox(
            cv_frame, textvariable=self.start_ch_var, state="readonly", width=5
        )
        self.start_ch_combo.grid(row=0, column=1, padx=(0, 12), sticky="w")

        ttk.Label(cv_frame, text="Start verse:").grid(row=0, column=2, padx=(0, 4), sticky="w")
        self.start_vs_combo = ttk.Combobox(
            cv_frame, textvariable=self.start_vs_var, state="readonly", width=5
        )
        self.start_vs_combo.grid(row=0, column=3, padx=(0, 12), sticky="w")

        ttk.Label(cv_frame, text="End chapter:").grid(row=0, column=4, padx=(0, 4), sticky="w")
        self.end_ch_combo = ttk.Combobox(cv_frame, textvariable=self.end_ch_var, state="readonly", width=5)
        self.end_ch_combo.grid(row=0, column=5, padx=(0, 12), sticky="w")

        ttk.Label(cv_frame, text="End verse:").grid(row=0, column=6, padx=(0, 4), sticky="w")
        self.end_vs_combo = ttk.Combobox(cv_frame, textvariable=self.end_vs_var, state="readonly", width=5)
        self.end_vs_combo.grid(row=0, column=7, padx=(0, 12), sticky="w")

        pa_frame = ttk.Frame(source_frame)
        pa_frame.grid(row=0, column=4, columnspan=10, sticky="w")
        self.pa_frame = pa_frame

        ttk.Label(pa_frame, text="Parashah:").grid(row=0, column=0, padx=(0, 4), sticky="w")
        self.parasha_combo = ttk.Combobox(pa_frame, textvariable=self.parasha_var, state="readonly", width=18)
        self.parasha_combo.grid(row=0, column=1, padx=(0, 12), sticky="w")

        ttk.Label(pa_frame, text="Aliyah:").grid(row=0, column=2, padx=(0, 4), sticky="w")
        self.aliyah_combo = ttk.Combobox(pa_frame, textvariable=self.aliyah_var, state="readonly", width=5)
        self.aliyah_combo.grid(row=0, column=3, padx=(0, 12), sticky="w")

        self.fetch_button = ttk.Button(
            source_frame, text="Fetch range from Sefaria", command=self.populate_input_from_api
        )
        self.fetch_button.grid(row=0, column=20, padx=(8, 0), sticky="w")

        # --- Cache status row ---
        cache_frame = ttk.Frame(source_labelframe)
        cache_frame.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(cache_frame, textvariable=self.cache_status_var, foreground="gray30").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(cache_frame, text="Clear cache", command=self.clear_cache).pack(side="left")

        # --- Input panes ---
        input_frame = ttk.Frame(root)
        input_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=PADX, pady=(PADY, PADY))
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_rowconfigure(1, weight=1)

        left_header = ttk.Frame(input_frame)
        left_header.grid(row=0, column=0, sticky="ew")
        left_header.grid_columnconfigure(0, weight=1)

        right_header = ttk.Frame(input_frame)
        right_header.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        right_header.grid_columnconfigure(0, weight=1)

        ttk.Label(left_header, text="Pointed text (display only):", anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(left_header, text="Copy pointed text", command=self.copy_pointed_to_clipboard).grid(
            row=0, column=1, sticky="e"
        )

        ttk.Label(right_header, text="Text only (display only):", anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(right_header, text="Copy text-only", command=self.copy_plain_to_clipboard).grid(
            row=0, column=1, sticky="e"
        )

        pointed_pane = ttk.Frame(input_frame)
        pointed_pane.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        pointed_pane.grid_rowconfigure(0, weight=1)
        pointed_pane.grid_columnconfigure(0, weight=1)

        self.input_box = tk.Text(
            pointed_pane, wrap=tk.NONE, width=60, height=8, undo=False,
            font=(pick_hebrew_font(), 13), insertwidth=0,
        )
        self.input_box.grid(row=0, column=0, sticky="nsew")

        pointed_scroll_y = ttk.Scrollbar(pointed_pane, orient="vertical", command=self.input_box.yview)
        pointed_scroll_y.grid(row=0, column=1, sticky="ns")
        self.input_box.configure(yscrollcommand=pointed_scroll_y.set)

        pointed_scroll_x = ttk.Scrollbar(pointed_pane, orient="horizontal", command=self.input_box.xview)
        pointed_scroll_x.grid(row=1, column=0, sticky="ew")
        self.input_box.configure(xscrollcommand=pointed_scroll_x.set)

        plain_pane = ttk.Frame(input_frame)
        plain_pane.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(2, 0))
        plain_pane.grid_rowconfigure(0, weight=1)
        plain_pane.grid_columnconfigure(0, weight=1)

        self.plain_box = tk.Text(
            plain_pane, wrap=tk.NONE, width=60, height=8, undo=False,
            font=(pick_hebrew_font(), 13), insertwidth=0,
        )
        self.plain_box.grid(row=0, column=0, sticky="nsew")

        plain_scroll_y = ttk.Scrollbar(plain_pane, orient="vertical", command=self.plain_box.yview)
        plain_scroll_y.grid(row=0, column=1, sticky="ns")
        self.plain_box.configure(yscrollcommand=plain_scroll_y.set)

        plain_scroll_x = ttk.Scrollbar(plain_pane, orient="horizontal", command=self.plain_box.xview)
        plain_scroll_x.grid(row=1, column=0, sticky="ew")
        self.plain_box.configure(xscrollcommand=plain_scroll_x.set)

        self.input_box.config(state="disabled")
        self.plain_box.config(state="disabled")

        ttk.Label(input_frame, textvariable=self.line_count_var, anchor="e").grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )

        # --- Options + Buttons ---
        options_frame = ttk.Frame(root)
        options_frame.grid(row=3, column=0, sticky="w", padx=PADX, pady=(0, PADY))

        ttk.Label(options_frame, text="Max disjunctive groups per leaf:", anchor="w").grid(
            row=0, column=0, sticky="w"
        )

        self.max_leaf_entry = ttk.Entry(options_frame, width=5, justify="left")
        self.max_leaf_entry.insert(0, "2")
        self.max_leaf_entry.grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Checkbutton(
            options_frame, text="Reset cloze numbering for each line",
            variable=self.reset_per_line_var,
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        button_frame = ttk.Frame(root)
        button_frame.grid(row=3, column=1, sticky="e", padx=PADX, pady=(0, PADY))

        ttk.Button(button_frame, text="Generate cloze cards", command=self.generate_output).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(button_frame, text="Copy cloze output", command=self.copy_cloze_to_clipboard).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Button(button_frame, text="Export to CSV", command=self.export_to_csv).grid(
            row=0, column=2, padx=(0, 6)
        )
        ttk.Button(button_frame, text="Show Stats", command=self.show_stats).grid(row=0, column=3)

        # --- Output + Tokens ---
        output_frame = ttk.Frame(root)
        output_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=PADX, pady=(0, PADY))
        output_frame.grid_columnconfigure(0, weight=3)
        output_frame.grid_columnconfigure(1, weight=1)
        output_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(output_frame, text="Output:", anchor="w").grid(row=0, column=0, sticky="w")

        left_output_frame = ttk.Frame(output_frame)
        left_output_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        self.output_box = tk.Text(left_output_frame, wrap=tk.WORD, width=60, height=6)
        self.output_box.pack(fill="both", expand=True)

        right_tokens_frame = ttk.Frame(output_frame)
        right_tokens_frame.grid(row=1, column=1, sticky="nsew")

        ttk.Label(right_tokens_frame, text="Minimum disjunctive groups:", anchor="w").pack(anchor="w")

        self.tokens_box = tk.Text(right_tokens_frame, wrap=tk.WORD, width=32, height=6, font=("Courier", 10))
        self.tokens_box.pack(fill="both", expand=True)

        # --- Visualization ---
        ttk.Label(root, text="Visualization:", anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=PADX, pady=(0, 2)
        )

        self.viz_output = tk.Text(root, wrap=tk.WORD, width=100, height=14, font=(pick_hebrew_font(), 13))
        self.viz_output.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=PADX, pady=(0, PADY))

    def _wire_traces(self) -> None:
        self.selection_mode_var.trace_add("write", self.update_mode_visibility)
        self.book_var.trace_add("write", self.update_chapter_dropdowns)
        self.book_var.trace_add("write", self.update_parasha_dropdowns)
        self.start_ch_var.trace_add("write", self.update_verse_dropdowns)
        self.end_ch_var.trace_add("write", self.update_verse_dropdowns)
        self.parasha_var.trace_add("write", self.update_aliyah_dropdown)


def apply_best_theme(root: tk.Tk) -> None:
    """Switch to the most modern-looking ttk theme actually available,
    without changing any layout. Tk's default theme looks dated on every
    platform; 'vista' (Windows-native) is the best option where present,
    'clam' is a good flat cross-platform fallback everywhere else."""
    style = ttk.Style(root)
    available = set(style.theme_names())
    for candidate in ("vista", "xpnative", "clam", "aqua"):
        if candidate in available:
            style.theme_use(candidate)
            return


def main() -> None:
    root = tk.Tk()
    root.title("Nested Anki Cloze Generator")
    root.geometry("1280x920")
    root.minsize(980, 720)
    apply_best_theme(root)

    AnkiPasukApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()
