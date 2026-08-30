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
    webview.start()


if __name__ == "__main__":
    main()
