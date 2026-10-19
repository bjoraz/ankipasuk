"""Tests for the ankipasuk-tk-legacy entry point's tkinter preflight.

Most Linux distributions ship tkinter as a separate package rather than
as part of the standard library, so the retired Tk interface has to cope
with it being absent -- and say which package to install instead of
dying on an import.
"""

import ankipasuk.gui as gui


def test_main_reports_the_missing_package_instead_of_raising(monkeypatch, capsys):
    monkeypatch.setattr(gui, "find_spec", lambda name: None)
    assert gui.main() == 1
    message = capsys.readouterr().err
    assert "sudo apt install python3-tk" in message


def test_main_does_not_import_the_tk_app_when_tkinter_is_absent(monkeypatch):
    # The failure has to be caught *before* ankipasuk.gui.app is reached:
    # that module imports tkinter at module scope, which is exactly the
    # bare ModuleNotFoundError this preflight exists to replace.
    monkeypatch.setattr(gui, "find_spec", lambda name: None)
    imported = []
    monkeypatch.setattr(
        gui, "_missing_tkinter_message", lambda: imported.append("message") or "no tkinter"
    )
    gui.main()
    assert imported == ["message"]


def test_main_launches_the_tk_app_when_tkinter_is_available(monkeypatch):
    import sys
    import types

    monkeypatch.setattr(gui, "find_spec", lambda name: object())
    launched = []
    fake_app = types.ModuleType("ankipasuk.gui.app")
    fake_app.main = lambda: launched.append("launched")
    monkeypatch.setitem(sys.modules, "ankipasuk.gui.app", fake_app)

    assert gui.main() == 0
    assert launched == ["launched"]


def test_missing_message_covers_every_distro_and_points_at_the_current_gui():
    message = gui._missing_tkinter_message()
    for expected in (
        "sudo apt install python3-tk",
        "sudo dnf install python3-tkinter",
        "sudo pacman -S tk",
        "sudo zypper install python3-tk",
        "python -m ankipasuk",
    ):
        assert expected in message, f"missing {expected!r}"


def test_missing_message_is_plain_text_not_rst():
    # It goes to a terminal, not to a docs build.
    assert "``" not in gui._missing_tkinter_message()
