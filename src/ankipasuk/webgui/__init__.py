"""Entry point for the web-based GUI: a pywebview window (native window
chrome, but rendered by the OS's own web engine -- WebView2 on Windows,
WebKitGTK on Linux, WKWebView on macOS) showing the HTML/CSS/JS frontend
in ``static/``, backed by :class:`ankipasuk.webgui.api.Api`.

Runs fully offline except for the same Sefaria network calls the app
always needed (cached locally afterward, same as before) -- nothing about
using a web view for the UI itself requires or uses the internet.
"""

from __future__ import annotations

from pathlib import Path

import webview

from ..cache import default_cache_dir
from .api import Api

_STATIC_DIR = Path(__file__).parent / "static"


def main() -> None:
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
    webview.start(private_mode=False, storage_path=str(storage_path))


if __name__ == "__main__":
    main()
