"""Entry point for the web-based GUI: a pywebview window (native window
chrome, but rendered by the OS's own web engine -- WebView2 on Windows,
WebKitGTK on Linux, WKWebView on macOS) showing the HTML/CSS/JS frontend
in ``static/``, backed by :class:`ankipasuk.webgui.api.Api`.

Runs fully offline except for the same Sefaria network calls the app
always needed (cached locally afterward, same as before) -- nothing about
using a web view for the UI itself requires or uses the internet.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

import webview

from ..cache import default_cache_dir
from .api import Api
from .backend import NoWebViewBackendError, choose_backend

_STATIC_DIR = Path(__file__).parent / "static"


def _clear_http_cache(storage_path: Path) -> None:
    """Drop WebKitGTK's HTTP cache (``<storage_path>/cache``) before the
    window opens.

    With private_mode off, pywebview serves the frontend from a fixed port,
    so every launch loads the same URL. Older pywebview versions sent no
    cache headers, and WebKit kept serving the HTML/JS it had cached from
    them even after an update -- the window showed an old version of the
    app. The cache only ever holds copies of the files in ``static/``, so
    clearing it costs nothing; saved settings (localStorage) live in a
    separate directory and are kept.
    """
    shutil.rmtree(storage_path / "cache", ignore_errors=True)


def _exit_even_if_threads_linger(status: int) -> int:
    """Leave the process, whether or not pywebview's leftovers let us.

    Loading the frontend from ``static/index.html`` makes pywebview start
    its own bottle HTTP server to serve the page and its assets (it does
    this for any local URL, on every platform). That server is a
    ``ThreadingMixIn`` + ``WSGIServer``, and pywebview never sets
    ``daemon_threads`` on it -- so, unlike ``http.server``'s own threading
    server, it inherits ``socketserver``'s ``daemon_threads = False``
    default and spawns a *non-daemon* thread per request. Under WebKitGTK
    the page is still holding a keep-alive connection when the window
    closes, which leaves one such thread parked in a socket read forever:
    ``webview.start()`` returns, ``main()`` returns, and then the
    interpreter refuses to shut down because it is waiting on a thread
    that will never finish. Closing the window leaves a live process
    behind every single time.

    There is no handle to shut that server down with -- the ``WSGIServer``
    instance is a local inside pywebview's own adapter -- so the fix is to
    stop waiting. Once the window is gone the app is over and nothing is
    left to clean up: cached verses and saved settings are written through
    synchronously as they change, and the web view's own storage belongs
    to WebKit's separate process, which persisted it when the window was
    destroyed. Flushing our own streams is the only cleanup that is ours.

    The leftover thread is checked for rather than assumed, so this is a
    plain return on any platform or pywebview version that doesn't strand
    one, and only the stuck case gets the blunt instrument.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    stuck = [
        t
        for t in threading.enumerate()
        if t.is_alive() and not t.daemon and t is not threading.main_thread()
    ]
    if stuck:
        os._exit(status)
    return status


def main() -> int:
    #  Checked before building anything: on Linux the rendering backend is
    #  a separate install (see .backend), and finding that out only once
    #  webview.start() is reached buries the one actionable line under
    #  pywebview's own import tracebacks.
    try:
        gui = choose_backend()
    except NoWebViewBackendError as exc:
        print(exc, file=sys.stderr)
        return 1

    api = Api()
    window = webview.create_window(
        "Nested Anki Cloze Generator",
        str(_STATIC_DIR / "index.html"),
        js_api=api,
        width=1280,
        height=920,
        min_size=(900, 650),
        text_select=True,
    )
    api._window = window

    # pywebview's own default is private_mode=True (an incognito-style
    # profile, thrown away on exit) -- without this, the source section's
    # own text-size/line-height/width controls (app.js's own
    # localStorage-backed settings) would silently reset every time the
    # app is relaunched, unlike an Anki card's own equivalent controls
    # (persisted in Anki's own, already-persistent profile). storage_path
    # reuses this project's own existing per-OS data directory (see
    # ankipasuk.cache.default_cache_dir) rather than pywebview's own
    # default location, so it lives alongside everything else this
    # project already stores and is easy to find/clear together.
    storage_path = default_cache_dir() / "webview_storage"
    storage_path.mkdir(parents=True, exist_ok=True)
    _clear_http_cache(storage_path)
    webview.start(gui=gui, private_mode=False, storage_path=str(storage_path))
    return _exit_even_if_threads_linger(0)


if __name__ == "__main__":
    sys.exit(main())
