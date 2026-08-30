"""API bridge for the AnkiConnect Tools window.

Mirrors ``gui/anki_connect_window.py``'s logic exactly (same underlying
calls: ``invoke``, ``initialize_stems``, ``run_scheduling_cycle``,
``compute_tagging_plan`` + ``apply_tagging_plan``), adapted from
Tk's background-thread + queue + polling pattern to background-thread +
``window.evaluate_js`` push updates -- the JS-side equivalent, since a
web view has no polling loop to hook into the way Tk's ``root.after`` did.
"""

from __future__ import annotations

import json
import threading

import webview

from ..anki_connect.client import DEFAULT_URL, invoke
from ..anki_connect.scheduling import initialize_stems as scheduling_initialize_stems
from ..anki_connect.scheduling import run_scheduling_cycle
from ..anki_connect.tagging import apply_tagging_plan, compute_tagging_plan
from ..cache import SefariaCache


class AnkiConnectApi:
    def __init__(self) -> None:
        self.window: webview.Window | None = None

    def get_default_url(self) -> str:
        return DEFAULT_URL

    def _log(self, tab_id: str, msg: str) -> None:
        if self.window is None:
            return
        self.window.evaluate_js(f"appendLog({json.dumps(tab_id)}, {json.dumps(msg)})")

    def _done(self, tab_id: str) -> None:
        if self.window is not None:
            self.window.evaluate_js(f"operationDone({json.dumps(tab_id)})")

    # =============================================================
    #  Connection
    # =============================================================
    def check_connection(self, url: str) -> None:
        threading.Thread(target=self._check_connection_worker, args=(url,), daemon=True).start()

    def _check_connection_worker(self, url: str) -> None:
        try:
            version = invoke("version", url=url)
            self._log("conn", f"Connected. AnkiConnect version: {version}")
        except Exception as e:  # noqa: BLE001 - reported to the user via log
            self._log("conn", f"ERROR: {e}")
        self._done("conn")

    # =============================================================
    #  Initialize Stems
    # =============================================================
    def initialize_stems(self, url: str, deck: str, dry_run: bool) -> None:
        threading.Thread(target=self._initialize_stems_worker, args=(url, deck, dry_run), daemon=True).start()

    def _initialize_stems_worker(self, url: str, deck: str, dry_run: bool) -> None:
        try:
            result = scheduling_initialize_stems(
                deck, url=url, dry_run=dry_run, log=lambda m: self._log("stems", m)
            )
            self._log("stems", "")
            self._log(
                "stems",
                f"Flagged: {result['flagged']}  Already flagged: {result['skipped']}  "
                f"Total notes: {result['notes']}",
            )
            if dry_run:
                self._log("stems", "DRY RUN -- no changes were made.")
        except Exception as e:  # noqa: BLE001
            self._log("stems", f"ERROR: {e}")
        self._done("stems")

    # =============================================================
    #  Sync Scheduling
    # =============================================================
    def sync_scheduling(self, url: str, deck: str, interval: int, dry_run: bool) -> None:
        threading.Thread(
            target=self._sync_scheduling_worker, args=(url, deck, interval, dry_run), daemon=True
        ).start()

    def _sync_scheduling_worker(self, url: str, deck: str, interval: int, dry_run: bool) -> None:
        try:
            result = run_scheduling_cycle(
                deck, interval, url=url, dry_run=dry_run, log=lambda m: self._log("sched", m)
            )
            self._log("sched", "")
            self._log("sched", f"Promoted: {result['promoted']}  Recovered: {result['recovered']}")
            if dry_run:
                self._log("sched", "DRY RUN -- no changes were made.")
        except Exception as e:  # noqa: BLE001
            self._log("sched", f"ERROR: {e}")
        self._done("sched")

    # =============================================================
    #  Tag Deck
    # =============================================================
    def tag_deck(self, url: str, deck: str, dry_run: bool) -> None:
        threading.Thread(target=self._tag_deck_worker, args=(url, deck, dry_run), daemon=True).start()

    def _tag_deck_worker(self, url: str, deck: str, dry_run: bool) -> None:
        try:
            self._log("tag", "Fetching notes and computing tags...")
            cache = SefariaCache()
            plan = compute_tagging_plan(deck, url=url, cache=cache, log=lambda m: self._log("tag", m))
            summary = apply_tagging_plan(plan, url=url, dry_run=dry_run, log=lambda m: self._log("tag", m))
            self._log("tag", "")
            self._log(
                "tag",
                f"Total notes: {summary['total_notes']}  "
                f"Not a Torah ref: {summary['unparsed_notes']}  "
                f"Notes tagged: {summary['notes_needing_tags']}  "
                f"Tags added: {summary['total_tags_to_add']}  "
                f"Conflicts: {summary['notes_with_conflicts']}",
            )
            if dry_run:
                self._log("tag", "DRY RUN -- no changes were made.")
        except Exception as e:  # noqa: BLE001
            self._log("tag", f"ERROR: {e}")
        self._done("tag")
