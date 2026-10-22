"""pywebview, when it is installed.

The desktop window needs it, but ``ankipasuk --serve`` (see .serve) does
not: it shows the same pages in a browser, so it also runs where
pywebview can't be installed at all, such as a-Shell on iOS. The bridges
import pywebview from here so that they still import there; ``webview``
is then ``None``.
"""

from __future__ import annotations

try:
    import webview
except ImportError:
    webview = None

#  What create_file_dialog takes for a save dialog. pywebview 5 deprecates
#  SAVE_DIALOG in favour of FileDialog.SAVE, which older 5.x lack. The
#  browser's stand-in window (.serve) ignores it.
if webview is None:
    SAVE_DIALOG = "save"
elif hasattr(webview, "FileDialog"):
    SAVE_DIALOG = webview.FileDialog.SAVE
else:
    SAVE_DIALOG = webview.SAVE_DIALOG
