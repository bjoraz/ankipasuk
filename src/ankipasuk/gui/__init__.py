"""Tkinter GUI for AnkiPasuk."""

from __future__ import annotations

import sys
from importlib.util import find_spec

#  Per-distro package names for tkinter. On Windows and macOS it comes
#  with the official Python installers, so the only platform that can be
#  missing it is Linux, where distros split it out of the standard
#  library into a separate package.
_TKINTER_PACKAGES = (
    ("Debian/Ubuntu", "sudo apt install python3-tk"),
    ("Fedora", "sudo dnf install python3-tkinter"),
    ("Arch", "sudo pacman -S tk"),
    ("openSUSE", "sudo zypper install python3-tk"),
)


def _missing_tkinter_message() -> str:
    distro_lines = "\n".join(f"    # {name}\n    {cmd}" for name, cmd in _TKINTER_PACKAGES)
    return f"""ankipasuk-tk-legacy needs tkinter, which isn't available to this Python
({sys.version.split()[0]} at {sys.executable}).

tkinter is part of the standard library, but most Linux distributions ship
it as a separate package that has to be installed alongside Python:

{distro_lines}

A virtualenv inherits tkinter from the interpreter it was created with, so
one created before installing the package above still won't see it --
recreate it afterwards.

This is the retired Tk interface, though. The current one
("ankipasuk", or "python -m ankipasuk") doesn't use tkinter at all,
and is almost certainly what you want instead."""


def main() -> int:
    """Entry point for ``ankipasuk-tk-legacy``.

    ``ankipasuk.gui.app`` imports tkinter at module scope, so on a Linux
    box without the distro's tkinter package the console script used to
    die with a bare ``ModuleNotFoundError`` before any of its own code
    ran. Importing it lazily here keeps that failure catchable, so it can
    be answered with the package to install.
    """
    if find_spec("tkinter") is None:
        print(_missing_tkinter_message(), file=sys.stderr)
        return 1

    from .app import main as _app_main

    _app_main()
    return 0
