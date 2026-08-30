"""The 'AnkiConnect Tools' window: connection check, stem initialization,
scheduling sync, and deck tagging, all driven from the GUI instead of the
console scripts / console_scripts commands.

Each operation runs on a background thread (they all do network I/O) and
streams its progress into a log pane via a thread-safe queue, polled
periodically on the main thread -- the standard, safe pattern for
combining a background worker with tkinter.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..anki_connect.client import DEFAULT_URL, AnkiConnectError, invoke
from ..anki_connect.scheduling import initialize_stems as scheduling_initialize_stems
from ..anki_connect.scheduling import run_scheduling_cycle
from ..anki_connect.tagging import apply_tagging_plan, compute_tagging_plan
from ..cache import SefariaCache


def _run_in_background(root: tk.Misc, worker, on_done) -> None:
    """Run ``worker()`` on a background thread; ``on_done(result, error)``
    is called back on the main thread via ``root.after`` once it finishes."""
    def run():
        try:
            result, error = worker(), None
        except Exception as e:  # noqa: BLE001 - reported to the user via on_done
            result, error = None, e
        root.after(0, lambda: on_done(result, error))

    threading.Thread(target=run, daemon=True).start()


def _start_log_pump(root: tk.Misc, log_queue: queue.Queue[str], text_widget: tk.Text) -> None:
    """Periodically drain ``log_queue`` into ``text_widget``. Runs for the
    lifetime of the window; safe to call once per window."""
    def poll():
        while True:
            try:
                msg = log_queue.get_nowait()
            except queue.Empty:
                break
            text_widget.config(state="normal")
            text_widget.insert(tk.END, msg + "\n")
            text_widget.see(tk.END)
            text_widget.config(state="disabled")
        root.after(100, poll)

    poll()


class _OperationTab:
    """Shared scaffolding for a tab: a log pane, a Run button that disables
    itself while running, and a background-thread + queue wiring so the
    operation's own ``log(msg)`` callback can push lines into the pane
    safely from the worker thread."""

    def __init__(self, notebook: ttk.Notebook, title: str, blurb: str):
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text=title)

        tk.Label(self.frame, text=blurb, anchor="w", justify="left", wraplength=640).pack(
            fill="x", padx=8, pady=(8, 4)
        )

        self.fields_frame = tk.Frame(self.frame)
        self.fields_frame.pack(fill="x", padx=8, pady=(0, 4))

        self.run_button = tk.Button(self.frame, text="Run")
        self.run_button.pack(anchor="w", padx=8, pady=(0, 4))

        self.log_text = tk.Text(self.frame, wrap=tk.WORD, height=14, font=("Courier", 10))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.config(state="disabled")

        self._log_queue: queue.Queue[str] = queue.Queue()

    def log(self, msg: str) -> None:
        """Thread-safe: safe to call from the background worker thread."""
        self._log_queue.put(msg)

    def clear_log(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def start_pump(self, root: tk.Misc) -> None:
        _start_log_pump(root, self._log_queue, self.log_text)

    def run(self, root: tk.Misc, worker, on_done) -> None:
        self.clear_log()
        self.run_button.config(state="disabled", text="Running...")

        def wrapped_done(result, error):
            self.run_button.config(state="normal", text="Run")
            on_done(result, error)

        _run_in_background(root, worker, wrapped_done)


def _labeled_entry(parent: tk.Misc, row: int, label: str, default: str, width: int = 30) -> tk.Entry:
    tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
    entry = tk.Entry(parent, width=width)
    entry.insert(0, default)
    entry.grid(row=row, column=1, sticky="w", pady=2)
    return entry


def show_anki_connect_tools(parent: tk.Misc) -> None:
    win = tk.Toplevel(parent)
    win.title("AnkiConnect Tools")
    win.geometry("760x620")

    url_frame = tk.Frame(win)
    url_frame.pack(fill="x", padx=8, pady=(8, 0))
    tk.Label(url_frame, text="AnkiConnect URL:").pack(side="left")
    url_entry = tk.Entry(url_frame, width=30)
    url_entry.insert(0, DEFAULT_URL)
    url_entry.pack(side="left", padx=(6, 0))

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    def get_url() -> str:
        return url_entry.get().strip() or DEFAULT_URL

    # =========================================================
    #  Connection tab
    # =========================================================
    conn_tab = _OperationTab(
        notebook, "Connection",
        "Check that Anki is running with the AnkiConnect add-on installed "
        "and reachable at the URL above.",
    )
    conn_status_var = tk.StringVar(value="")
    tk.Label(conn_tab.frame, textvariable=conn_status_var, anchor="w", fg="gray30").pack(
        fill="x", padx=8, pady=(0, 4)
    )

    def do_check_connection():
        def worker():
            return invoke("version", url=get_url())

        def on_done(version, error):
            if error is not None:
                conn_status_var.set(f"Connection failed: {error}")
                conn_tab.log(f"ERROR: {error}")
            else:
                conn_status_var.set(f"Connected. AnkiConnect version: {version}")
                conn_tab.log(f"Connected. AnkiConnect version: {version}")

        conn_tab.run(win, worker, on_done)

    conn_tab.run_button.config(command=do_check_connection)

    # =========================================================
    #  Initialize Stems tab
    # =========================================================
    stems_tab = _OperationTab(
        notebook, "Initialize Stems",
        "One-time setup: flag the stem (highest-ord cloze) of every note "
        "in a deck with flag 1, so the scheduling sync below knows which "
        "cards to track. Notes that already have any flag are left "
        "untouched -- safe to re-run.",
    )
    stems_deck_entry = _labeled_entry(stems_tab.fields_frame, 0, "Deck:", "Leyning")
    stems_dry_run_var = tk.BooleanVar(value=True)
    tk.Checkbutton(stems_tab.fields_frame, text="Dry run (preview only)", variable=stems_dry_run_var).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
    )

    def do_initialize_stems():
        deck = stems_deck_entry.get().strip()
        dry_run = stems_dry_run_var.get()
        if not deck:
            messagebox.showerror("Missing deck", "Enter a deck name.", parent=win)
            return

        def worker():
            return scheduling_initialize_stems(deck, url=get_url(), dry_run=dry_run, log=stems_tab.log)

        def on_done(result, error):
            if error is not None:
                stems_tab.log(f"ERROR: {error}")
                return
            stems_tab.log("")
            stems_tab.log(
                f"Flagged: {result['flagged']}  Already flagged: {result['skipped']}  "
                f"Total notes: {result['notes']}"
            )
            if dry_run:
                stems_tab.log("DRY RUN -- no changes were made.")

        stems_tab.run(win, worker, on_done)

    stems_tab.run_button.config(command=do_initialize_stems)

    # =========================================================
    #  Sync Scheduling tab
    # =========================================================
    sched_tab = _OperationTab(
        notebook, "Sync Scheduling",
        "Run one promotion + lapse-recovery cycle: matures (flag 1 -> 2, "
        "suspends leaves) any stem whose interval has reached the "
        "threshold, and recovers (flag 2 -> 1, un-suspends + re-queues "
        "leaves) any stem that has since lapsed.",
    )
    sched_deck_entry = _labeled_entry(sched_tab.fields_frame, 0, "Deck:", "Leyning")
    sched_interval_entry = _labeled_entry(
        sched_tab.fields_frame, 1, "Promotion interval (days):", "21", width=8
    )
    sched_dry_run_var = tk.BooleanVar(value=True)
    tk.Checkbutton(sched_tab.fields_frame, text="Dry run (preview only)", variable=sched_dry_run_var).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(4, 0)
    )

    def do_sync_scheduling():
        deck = sched_deck_entry.get().strip()
        dry_run = sched_dry_run_var.get()
        if not deck:
            messagebox.showerror("Missing deck", "Enter a deck name.", parent=win)
            return
        try:
            interval = int(sched_interval_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid interval", "Promotion interval must be a whole number.", parent=win)
            return

        def worker():
            return run_scheduling_cycle(deck, interval, url=get_url(), dry_run=dry_run, log=sched_tab.log)

        def on_done(result, error):
            if error is not None:
                sched_tab.log(f"ERROR: {error}")
                return
            sched_tab.log("")
            sched_tab.log(f"Promoted: {result['promoted']}  Recovered: {result['recovered']}")
            if dry_run:
                sched_tab.log("DRY RUN -- no changes were made.")

        sched_tab.run(win, worker, on_done)

    sched_tab.run_button.config(command=do_sync_scheduling)

    # =========================================================
    #  Tag Deck tab
    # =========================================================
    tag_tab = _OperationTab(
        notebook, "Tag Deck",
        "Compute and add parasha/aliyah/Maftir/holiday tags for every "
        "note in a deck. Never removes or changes an existing tag -- "
        "conflicts are reported in the log instead. See "
        "docs/anki-tagging.md for details.",
    )
    tag_deck_entry = _labeled_entry(tag_tab.fields_frame, 0, "Deck:", "Leyning")
    tag_dry_run_var = tk.BooleanVar(value=True)
    tk.Checkbutton(tag_tab.fields_frame, text="Dry run (preview only)", variable=tag_dry_run_var).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
    )

    def do_tag_deck():
        deck = tag_deck_entry.get().strip()
        dry_run = tag_dry_run_var.get()
        if not deck:
            messagebox.showerror("Missing deck", "Enter a deck name.", parent=win)
            return

        def worker():
            url = get_url()
            tag_tab.log("Fetching notes and computing tags...")
            cache = SefariaCache()
            plan = compute_tagging_plan(deck, url=url, cache=cache)
            return apply_tagging_plan(plan, url=url, dry_run=dry_run, log=tag_tab.log)

        def on_done(summary, error):
            if error is not None:
                if isinstance(error, AnkiConnectError):
                    tag_tab.log(f"ERROR: {error}")
                else:
                    tag_tab.log(f"ERROR: {error!r}")
                return
            tag_tab.log("")
            tag_tab.log(
                f"Total notes: {summary['total_notes']}  "
                f"Not a Torah ref: {summary['unparsed_notes']}  "
                f"Notes tagged: {summary['notes_needing_tags']}  "
                f"Tags added: {summary['total_tags_to_add']}  "
                f"Conflicts: {summary['notes_with_conflicts']}"
            )
            if dry_run:
                tag_tab.log("DRY RUN -- no changes were made.")

        tag_tab.run(win, worker, on_done)

    tag_tab.run_button.config(command=do_tag_deck)

    # Start each tab's log pump once the window (and its widgets) exist.
    for tab in (conn_tab, stems_tab, sched_tab, tag_tab):
        tab.start_pump(win)
