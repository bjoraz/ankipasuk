"""Which pywebview rendering backend to use, and what to tell the user
when there isn't one.

pywebview doesn't ship a web engine -- it drives whatever the OS already
has. On Windows that's WebView2 (reached through ``pythonnet``, pulled in
by pywebview itself) and on macOS WKWebView (through ``pyobjc``, likewise
a pywebview dependency), so on both there is nothing extra to install and
nothing for this module to decide.

Linux is the one platform where neither is true. There the engine is
either WebKitGTK -- reached through PyGObject (``gi``), which is a
*system* package on every distro rather than something pip puts in a
virtualenv -- or Qt WebEngine, which is pip-installable but a ~100 MB
download. Installing AnkiPasuk into a virtualenv therefore succeeds on
Linux and then fails at launch, and pywebview's own diagnostic for that
("You must have either QT or GTK with Python extensions installed")
arrives after two stderr tracebacks and doesn't say what to install. This
module probes for the backends up front so :func:`ankipasuk.webgui.main`
can name the one it found -- avoiding pywebview's noisy
try-GTK-then-fall-back-to-Qt sequence -- or, when neither works, fail
with instructions.
"""

from __future__ import annotations

import os
import platform
import sys
from importlib.util import find_spec

#  The names pywebview's own ``webview.start(gui=...)`` accepts for the
#  two backends that exist on Linux.
GTK = "gtk"
QT = "qt"


class NoWebViewBackendError(RuntimeError):
    """No usable pywebview backend is installed. The message is written
    for the person running the app, not for a traceback reader."""


def _gtk_available() -> bool:
    """Whether ``webview.platforms.gtk`` would import.

    Mirrors that module's own preamble: PyGObject, GTK 3, and WebKit2 at
    either 4.1 (current) or 4.0 (older distros). ``require_version`` only
    resolves typelib files -- it doesn't load GTK or touch the display --
    so this stays cheap and safe to call headless.
    """
    if find_spec("gi") is None:
        return False
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
    except (ImportError, ValueError):
        return False
    return True


def _qt_installed() -> bool:
    """Whether a Qt binding with its WebEngine module is installed at all.

    ``webview.platforms.qt`` goes through ``qtpy``, which abstracts over
    the four bindings below; any one of them with its WebEngine companion
    module present is enough. A cheap ``find_spec`` check, which says
    nothing about whether the binding's native libraries will load -- see
    :func:`_qt_load_error` for that.
    """
    if find_spec("qtpy") is None:
        return False
    for binding, webengine in (
        ("PyQt6", "PyQt6.QtWebEngineWidgets"),
        ("PySide6", "PySide6.QtWebEngineWidgets"),
        ("PyQt5", "PyQt5.QtWebEngineWidgets"),
        ("PySide2", "PySide2.QtWebEngineWidgets"),
    ):
        try:
            if find_spec(binding) is not None and find_spec(webengine) is not None:
                return True
        except (ImportError, ValueError):
            continue  # a half-installed binding -- treat as absent, try the next
    return False


def _qt_load_error() -> str | None:
    """``None`` if the Qt modules ``webview.platforms.qt`` needs import,
    otherwise the error they fail with.

    Having the Python packages isn't enough: PyQt6 and PySide6 wheels link
    against the system's EGL and OpenGL libraries (and WebEngine against a
    few more), which a minimal install or container may not have. Then
    the import fails with e.g. ``libEGL.so.1: cannot open shared object
    file``, and a ``find_spec`` check alone would have picked Qt anyway --
    leaving pywebview to fail with its own tracebacks. So this really
    imports the same modules pywebview does. Importing doesn't create a
    ``QApplication`` or touch the display, and pywebview would import them
    next anyway, so the cost is only paid once.
    """
    try:
        from qtpy import (  # noqa: F401
            QtCore,
            QtGui,
            QtNetwork,
            QtWebChannel,
            QtWebEngineCore,
            QtWebEngineWidgets,
            QtWidgets,
        )
    except (ImportError, RuntimeError, OSError) as exc:  # qtpy's own errors are RuntimeErrors
        return f"{type(exc).__name__}: {exc}"
    return None


def _qt_available() -> bool:
    """Whether ``webview.platforms.qt`` would import: Qt is installed and
    its modules (with their native libraries) actually load."""
    return _qt_installed() and _qt_load_error() is None


#  Per-distro install lines for the WebKitGTK route. Kept as data so the
#  help text below stays readable.
_GTK_SYSTEM_PACKAGES = (
    ("Debian/Ubuntu", "sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0"),
    ("Fedora", "sudo dnf install python3-gobject webkit2gtk4.1"),
    ("Arch", "sudo pacman -S python-gobject webkit2gtk-4.1"),
    ("openSUSE", "sudo zypper install python3-gobject typelib-1_0-WebKit2-4_1"),
)


def missing_backend_message(qt_error: str | None = None) -> str:
    """What to print when no backend is usable.

    Both routes are offered rather than just the recommended one: the
    WebKitGTK packages need root, which someone installing into their own
    virtualenv may not have, and the pip-only Qt route is the answer in
    that case.

    ``qt_error`` is the error Qt fails to load with when it *is*
    installed (see :func:`_qt_load_error`); it's shown, since in that case
    the fix is a missing system library, not another install.
    """
    qt_note = "" if qt_error is None else f"""
     Qt is installed in this environment, but it can't load:

         {qt_error}

     That usually means the system's graphics libraries (EGL, OpenGL)
     are missing, which is common on minimal installs and in containers.
     On Debian/Ubuntu:

         sudo apt install libegl1 libgl1

     If the error names another library, install the package that
     provides it.
"""
    distro_lines = "\n".join(f"         # {name}\n         {cmd}" for name, cmd in _GTK_SYSTEM_PACKAGES)
    return f"""AnkiPasuk's window needs a web engine, and this Python environment can't
reach one. pywebview renders through the system's own engine rather than
bundling a browser, and on Linux that means one of two backends:

  1. WebKitGTK -- recommended, uses the engine your desktop already has.
     Install the system packages:

{distro_lines}

     They live outside the virtualenv, so the environment AnkiPasuk runs
     in has to be allowed to see them:

         python3 -m venv --system-site-packages .venv    # venv
         pipx install --editable --system-site-packages .  # pipx, from the checkout

     (An existing venv can't be opened up after the fact -- recreate it,
     or set include-system-site-packages = true in its pyvenv.cfg.)

  2. Qt WebEngine -- no system packages and no root, but a ~100 MB
     download:

         pip install "pywebview[qt]"
{qt_note}
Already installed one of these? Then it isn't visible from this
interpreter ({platform.python_version()} at {sys.executable}) -- check you're
installing into the same environment you're launching from."""


def opens_windows() -> bool:
    """Whether pywebview can open a window here at all: not on iOS (in
    a-Shell, say), where it installs but ``platform.system()`` is none of
    the systems it knows. ankipasuk then serves the app to a browser
    (see .serve) instead."""
    return platform.system() in ("Windows", "Darwin", "Linux", "OpenBSD")


def choose_backend() -> str | None:
    """The backend to hand ``webview.start(gui=...)``, or ``None`` to let
    pywebview decide for itself.

    ``None`` on Windows and macOS, where pywebview's own choice is the
    only one and naming it would just be noise. ``None`` too when
    ``PYWEBVIEW_GUI`` is set, so that pywebview's documented override
    keeps working and stays the way to escape a bad guess here.

    :raises NoWebViewBackendError: on Linux with no usable backend --
        raised here, before any window is created, so the user gets
        :func:`missing_backend_message` instead of pywebview's two
        tracebacks and a one-line exception.
    """
    if platform.system() not in ("Linux", "OpenBSD"):
        return None
    if os.environ.get("PYWEBVIEW_GUI"):
        return None

    #  GTK first: it renders through the WebKitGTK the desktop already has
    #  -- native window decorations, the system's own fonts and scaling --
    #  where Qt WebEngine ships a second, separate Chromium. Except under
    #  KDE, which pywebview itself keys off KDE_FULL_SESSION: there a Qt
    #  window matches the rest of the desktop. Probed in that order and
    #  stopped at the first that works, so a machine that gets GTK never
    #  pays for importing Qt (see _qt_load_error).
    probes = {GTK: _gtk_available, QT: _qt_available}
    order = (QT, GTK) if os.environ.get("KDE_FULL_SESSION") else (GTK, QT)
    for name in order:
        if probes[name]():
            return name

    qt_error = _qt_load_error() if _qt_installed() else None
    raise NoWebViewBackendError(missing_backend_message(qt_error))
