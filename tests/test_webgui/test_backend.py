"""Tests for ankipasuk.webgui.backend -- picking a pywebview rendering
backend, and failing usefully when there isn't one.

The probes genuinely inspect the machine the tests run on, so every test
here stubs them out: CI has no WebKitGTK and no Qt WebEngine, a Linux
desktop may have either or both, and a test that asserted on the real
answer would mean something different on each.
"""

import pytest

from ankipasuk.webgui import backend


@pytest.fixture
def probes(monkeypatch):
    """Pin both backend probes and the platform, so each test states the
    machine it's describing instead of inheriting the real one."""

    def configure(*, gtk=False, qt=False, system="Linux"):
        monkeypatch.setattr(backend, "_gtk_available", lambda: gtk)
        monkeypatch.setattr(backend, "_qt_available", lambda: qt)
        monkeypatch.setattr(backend.platform, "system", lambda: system)
        monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
        monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    return configure


# =============================================================
#  available_backends
# =============================================================
def test_available_backends_is_empty_when_neither_is_installed(probes):
    probes()
    assert backend.available_backends() == []


def test_available_backends_reports_each_one_present(probes):
    probes(gtk=True)
    assert backend.available_backends() == ["gtk"]
    probes(qt=True)
    assert backend.available_backends() == ["qt"]


def test_available_backends_prefers_gtk_when_both_are_present(probes):
    probes(gtk=True, qt=True)
    assert backend.available_backends() == ["gtk", "qt"]


# =============================================================
#  choose_backend
# =============================================================
def test_choose_backend_picks_gtk_over_qt(probes):
    probes(gtk=True, qt=True)
    assert backend.choose_backend() == "gtk"


def test_choose_backend_picks_qt_when_gtk_is_missing(probes):
    probes(qt=True)
    assert backend.choose_backend() == "qt"


def test_choose_backend_raises_with_install_instructions_when_nothing_is_installed(probes):
    probes()
    with pytest.raises(backend.NoWebViewBackendError) as excinfo:
        backend.choose_backend()
    message = str(excinfo.value)
    assert "apt install" in message
    assert "ankipasuk[qt]" in message


def test_choose_backend_defers_to_pywebview_on_windows_and_macos(probes):
    # Both ship their engine as a pywebview dependency, so there is no
    # choice to make and naming one would only be noise.
    for system in ("Windows", "Darwin"):
        probes(system=system)
        assert backend.choose_backend() is None


def test_choose_backend_does_not_raise_on_windows_or_macos_without_gtk_or_qt(probes):
    # The Linux-only diagnostic must not fire on platforms where the
    # absence of both backends is the normal, working state.
    probes(system="Windows")
    assert backend.choose_backend() is None


def test_choose_backend_defers_to_an_explicit_pywebview_gui_override(monkeypatch, probes):
    probes(gtk=True, qt=True)
    monkeypatch.setenv("PYWEBVIEW_GUI", "qt")
    # None, not "qt": pywebview reads the variable itself, and returning
    # None is what leaves it free to do so.
    assert backend.choose_backend() is None


def test_choose_backend_prefers_qt_under_kde_when_qt_is_installed(monkeypatch, probes):
    probes(gtk=True, qt=True)
    monkeypatch.setenv("KDE_FULL_SESSION", "true")
    assert backend.choose_backend() == "qt"


def test_choose_backend_falls_back_to_gtk_under_kde_without_qt(monkeypatch, probes):
    probes(gtk=True)
    monkeypatch.setenv("KDE_FULL_SESSION", "true")
    assert backend.choose_backend() == "gtk"


# =============================================================
#  missing_backend_message
# =============================================================
def test_missing_backend_message_covers_both_install_routes():
    message = backend.missing_backend_message()
    for expected in (
        "sudo apt install",
        "sudo dnf install",
        "sudo pacman -S",
        "sudo zypper install",
        "--system-site-packages",
        "pip install 'ankipasuk[qt]'",
    ):
        assert expected in message, f"missing {expected!r}"


def test_missing_backend_message_names_the_interpreter_in_use():
    import sys

    assert sys.executable in backend.missing_backend_message()


# =============================================================
#  The probes themselves
# =============================================================
def test_gtk_probe_is_false_without_pygobject(monkeypatch):
    monkeypatch.setattr(backend, "find_spec", lambda name: None)
    assert backend._gtk_available() is False


def test_qt_probe_is_false_without_qtpy(monkeypatch):
    monkeypatch.setattr(backend, "find_spec", lambda name: None)
    assert backend._qt_available() is False


def test_qt_probe_needs_a_webengine_module_not_just_a_binding(monkeypatch):
    # PyQt6 without PyQt6-WebEngine is a real and easy-to-hit state: the
    # WebEngine module is a separate distribution, and pywebview's Qt
    # backend is unusable without it.
    present = {"qtpy", "PyQt6"}
    monkeypatch.setattr(backend, "find_spec", lambda name: object() if name in present else None)
    assert backend._qt_available() is False
    present.add("PyQt6.QtWebEngineWidgets")
    assert backend._qt_available() is True


def test_probes_are_safe_to_call_for_real(probes):
    # Whatever this machine has, probing must not raise or need a display
    # -- choose_backend() runs before any window exists.
    assert isinstance(backend._gtk_available(), bool)
    assert isinstance(backend._qt_available(), bool)


# =============================================================
#  Process teardown
# =============================================================
#  pywebview serves the local frontend over its own bottle HTTP server,
#  whose per-request threads are non-daemon; under WebKitGTK one of them
#  survives the window close and would otherwise hang the interpreter
#  forever. See ankipasuk.webgui._exit_even_if_threads_linger.
def test_exit_returns_normally_when_no_thread_is_stranded(monkeypatch):
    import threading

    from ankipasuk import webgui

    hard_exits = []
    monkeypatch.setattr(webgui.os, "_exit", lambda status: hard_exits.append(status))
    monkeypatch.setattr(webgui.threading, "enumerate", lambda: [threading.main_thread()])

    assert webgui._exit_even_if_threads_linger(0) == 0
    assert hard_exits == []


def test_exit_is_forced_when_a_non_daemon_thread_is_stranded(monkeypatch):
    import threading

    from ankipasuk import webgui

    hard_exits = []
    monkeypatch.setattr(webgui.os, "_exit", lambda status: hard_exits.append(status))

    monkeypatch.setattr(
        webgui.threading,
        "enumerate",
        lambda: [threading.main_thread(), _FakeThread(daemon=False)],
    )

    webgui._exit_even_if_threads_linger(0)
    assert hard_exits == [0]


def test_a_stranded_daemon_thread_does_not_force_an_exit(monkeypatch):
    # Daemon threads never hold up interpreter shutdown, so they are not
    # a reason to reach for os._exit.
    import threading

    from ankipasuk import webgui

    hard_exits = []
    monkeypatch.setattr(webgui.os, "_exit", lambda status: hard_exits.append(status))
    monkeypatch.setattr(
        webgui.threading,
        "enumerate",
        lambda: [threading.main_thread(), _FakeThread(daemon=True)],
    )

    assert webgui._exit_even_if_threads_linger(0) == 0
    assert hard_exits == []


class _FakeThread:
    """Stands in for pywebview's parked request thread -- a real one would
    have to be genuinely stuck in a socket read to be realistic, which is
    not something a test should leave behind."""

    def __init__(self, *, daemon: bool):
        self.daemon = daemon
        self.name = "process_request_thread"

    def is_alive(self) -> bool:
        return True
