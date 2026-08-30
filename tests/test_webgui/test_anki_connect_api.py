"""Tests for ankipasuk.webgui.anki_connect_api.AnkiConnectApi.

Each operation runs on a background thread and streams progress via
window.evaluate_js -- these tests use a fake window that just records the
JS calls, then wait for the background thread to finish (bounded with a
generous timeout) and assert on the recorded log sequence, mirroring
exactly what the real JS-side appendLog/operationDone functions receive.
"""

import time

from ankipasuk.webgui.anki_connect_api import AnkiConnectApi

DECK = "Leyning::1-Bereshit"


class _FakeWindow:
    def __init__(self):
        self.calls: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.calls.append(script)


def _wait_for_done(window: _FakeWindow, tab_id: str, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(f'operationDone("{tab_id}")' in c for c in window.calls):
            return
        time.sleep(0.01)
    raise TimeoutError(f"operationDone(\"{tab_id}\") was never called; calls so far: {window.calls}")


def _log_lines(window: _FakeWindow, tab_id: str) -> list[str]:
    import json
    import re

    lines = []
    for call in window.calls:
        m = re.match(r'appendLog\("' + tab_id + r'", (.*)\)$', call)
        if m:
            lines.append(json.loads(m.group(1)))
    return lines


def test_get_default_url():
    from ankipasuk.anki_connect.client import DEFAULT_URL

    api = AnkiConnectApi()
    assert api.get_default_url() == DEFAULT_URL


def test_check_connection_success(fake_anki):
    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    api.check_connection("http://fake")
    _wait_for_done(window, "conn")

    logs = _log_lines(window, "conn")
    assert any("Connected" in line for line in logs)


def test_initialize_stems_streams_progress_and_flags(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5), (2, 5)])

    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    api.initialize_stems("http://fake", DECK, False)
    _wait_for_done(window, "stems")

    logs = _log_lines(window, "stems")
    assert any("Flagged: 1" in line for line in logs)
    assert not any("DRY RUN" in line for line in logs)

    flags = {c["ord"]: c["flags"] for c in fake_anki.cards.values()}
    assert flags[2] == 1  # highest-ord card flagged


def test_initialize_stems_dry_run_makes_no_changes(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 5)])

    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    api.initialize_stems("http://fake", DECK, True)
    _wait_for_done(window, "stems")

    logs = _log_lines(window, "stems")
    assert any("DRY RUN" in line for line in logs)
    assert all(c["flags"] == 0 for c in fake_anki.cards.values())


def test_sync_scheduling_reports_promoted_and_recovered(fake_anki):
    fake_anki.add_note(1, DECK, [(0, 5), (1, 30)])
    fake_anki.cards[2]["flags"] = 1  # stem already flagged, interval past threshold

    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    api.sync_scheduling("http://fake", DECK, 21, False)
    _wait_for_done(window, "sched")

    logs = _log_lines(window, "sched")
    assert any("Promoted:" in line and "Recovered:" in line for line in logs)


def test_tag_deck_reports_summary(fake_anki, tmp_path, monkeypatch):
    from ankipasuk.cache import SefariaCache

    monkeypatch.setattr(
        "ankipasuk.webgui.anki_connect_api.SefariaCache",
        lambda: SefariaCache(cache_dir=tmp_path),
    )
    fake_anki.add_note_with_fields(1, DECK, {"Source": "not a torah ref"}, tags=[])

    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    api.tag_deck("http://fake", DECK, True)
    _wait_for_done(window, "tag")

    logs = _log_lines(window, "tag")
    assert any("Not a Torah ref: 1" in line for line in logs)
    assert any("DRY RUN" in line for line in logs)


def test_errors_are_logged_not_raised(fake_anki):
    """An operation on a nonexistent/misbehaving setup must report via
    appendLog + operationDone, never raise out of the background thread
    (which would just silently vanish with no user-visible feedback)."""
    api = AnkiConnectApi()
    window = _FakeWindow()
    api._window = window

    # No deck notes added -- initialize_stems should complete cleanly
    # with zero notes, not error; use a real failure mode instead: an
    # invalid interval type would raise inside run_scheduling_cycle.
    api.sync_scheduling("http://fake", DECK, "not-a-number", False)
    _wait_for_done(window, "sched")

    logs = _log_lines(window, "sched")
    assert any("ERROR" in line for line in logs)
