"""``ankipasuk --serve``: the app in a browser instead of a window.

pywebview only opens windows on Windows, macOS and Linux, and can't be
installed at all where there's no desktop to open them on -- an iPhone
or iPad running a-Shell, say. The window only ever shows the pages in
``static/``, though, talking to the bridges (api.py and the others)
through ``window.pywebview.api``. This serves the same pages over HTTP to
any browser, with ``static/bridge.js`` standing in for pywebview's bridge:
each call is a POST to ``/api/<session>/<method>``, answered by the same
bridge objects the window uses, unchanged.

What the bridges ask of their window is done here by :class:`BrowserWindow`:

- ``evaluate_js``: the script is queued, and the page fetches the queue
  (``/api/<session>/_poll``, held open until there is something) and
  runs it -- the Anki tools' log lines, the statistics finding their
  phrases again.
- ``create_file_dialog``: a browser can't be asked where to save a file,
  so files are saved to one folder (``~/Documents/AnkiPasuk`` by default:
  in a-Shell that's the folder the Files app shows), and the page offers
  each one as a download as well.
- A second window (Statistics, Anki tools) opens over the page, in a
  frame with its own session, rather than as a window of its own:
  browsers block windows opened from a script, and a-Shell's own browser
  has only the one.
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import sys
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .. import phrases
from .api import Api

_STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770  # AnkiConnect has 8765
_POLL_SECONDS = 25.0  # how long a _poll waits for a script before answering with none

#  What the bridge call running on this thread saved and opened, for its
#  answer to report (see _App.call): the bridges run each call on the
#  request's own thread, as pywebview runs them on one of its own.
_current = threading.local()


def default_exports_dir() -> Path:
    """``~/Documents/AnkiPasuk``, or ``~/AnkiPasuk`` without a Documents
    folder. In a-Shell ``~/Documents`` is what the Files app shows."""
    documents = Path.home() / "Documents"
    return (documents if documents.is_dir() else Path.home()) / "AnkiPasuk"


class _Event:
    """pywebview's window event, as far as the bridges use it: handlers
    added with ``+=``, called when it fires."""

    def __init__(self) -> None:
        self._handlers: list = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def fire(self) -> None:
        for handler in self._handlers:
            try:
                handler()
            except Exception:  # noqa: BLE001 -- one handler's failure doesn't stop the rest
                traceback.print_exc()


class _Events:
    def __init__(self) -> None:
        self.closed = _Event()


class BrowserWindow:
    """Stands in for pywebview's ``Window`` for one page open in a browser."""

    def __init__(self, exports_dir: Path) -> None:
        self.events = _Events()
        self._exports_dir = exports_dir
        self._scripts: list[str] = []
        self._ready = threading.Condition()

    def evaluate_js(self, script: str) -> None:
        with self._ready:
            self._scripts.append(script)
            self._ready.notify_all()

    def take_scripts(self, timeout: float) -> list[str]:
        """The scripts queued for the page, once there are any or after
        ``timeout`` seconds (then none)."""
        with self._ready:
            self._ready.wait_for(lambda: self._scripts, timeout)
            scripts, self._scripts = self._scripts, []
        return scripts

    def create_file_dialog(self, dialog_type=None, directory="", allow_multiple=False,
                           save_filename="", file_types=()) -> str:
        """Where to save ``save_filename``: in the exports folder, under a
        name no file there has yet."""
        self._exports_dir.mkdir(parents=True, exist_ok=True)
        name = Path(save_filename).name or "export"
        stem, suffix = Path(name).stem, Path(name).suffix
        target = self._exports_dir / name
        n = 2
        while target.exists():
            target = self._exports_dir / f"{stem} ({n}){suffix}"
            n += 1
        target.touch()  # claimed, so a second save before this one is written can't pick it too
        saved = getattr(_current, "saved", None)
        if saved is not None:
            saved.append(target.name)
        return str(target)


class _App:
    """The open pages: each a session, with its bridge and its window."""

    def __init__(self, exports_dir: Path) -> None:
        self.exports_dir = exports_dir
        self._sessions: dict[str, tuple[object, BrowserWindow]] = {}
        self._lock = threading.Lock()

    def _add(self, js_api) -> tuple[str, BrowserWindow]:
        window = BrowserWindow(self.exports_dir)
        sid = secrets.token_urlsafe(12)
        with self._lock:
            self._sessions[sid] = (js_api, window)
        return sid, window

    def new_main(self) -> str:
        """A session for a newly loaded main page, with a bridge of its
        own: reloading the page starts the app afresh, as relaunching it
        does."""
        api = Api()
        sid, window = self._add(api)
        api._window = window
        api._create_window = self._open_page
        return sid

    def _open_page(self, title: str, page: str, js_api, width: int, height: int) -> BrowserWindow:
        """Api._create_window's stand-in: a session for ``js_api``, whose
        page the main page opens over itself once the call answers."""
        sid, window = self._add(js_api)
        opened = getattr(_current, "opened", None)
        if opened is not None:
            opened.append({"title": title, "url": f"{page}?session={sid}"})
        return window

    def get(self, sid: str):
        with self._lock:
            return self._sessions.get(sid)

    def close(self, sid: str) -> None:
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session is not None:
            session[1].events.closed.fire()

    def call(self, sid: str, method: str, args: list) -> dict:
        """``method`` of the session's bridge, as ``window.pywebview.api``
        would call it: its result, or the error it raised; and the files
        it saved and pages it opened."""
        session = self.get(sid)
        if session is None:
            return {"error": "This page's session has ended. Reload the page."}
        js_api = session[0]
        fn = getattr(js_api, method, None) if not method.startswith("_") else None
        if not callable(fn):
            return {"error": f"No such call: {method}"}
        _current.saved, _current.opened = [], []
        try:
            return {"result": fn(*args), "saved": _current.saved, "opened": _current.opened}
        except Exception as e:  # noqa: BLE001 -- rejects the call's promise, as pywebview does
            traceback.print_exc()
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            del _current.saved, _current.opened


def _inject_bridge(html: str) -> str:
    """The page with bridge.js loaded first thing, before its own scripts."""
    tag = '<script src="bridge.js"></script>\n'
    head = html.find("</head>")
    return html[:head] + tag + html[head:] if head != -1 else tag + html


def _make_handler(app: _App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AnkiPasuk"

        def log_message(self, format, *args):  # noqa: A002 -- the base class's name
            pass  # a line per request would bury the app's own output

        def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")  # an update is never hidden behind a cached page
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page left while its call (most often a _poll) was waiting

        def _send_json(self, value, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _not_found(self) -> None:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 -- the base class's name
            path = unquote(urlsplit(self.path).path)
            if path == "/":
                self._send(HTTPStatus.FOUND, b"", "text/plain", {"Location": "/index.html"})
                return
            if path == "/favicon.ico":
                self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")  # none, rather than a 404 in the console
                return
            if path.startswith("/exports/"):
                self._send_file(app.exports_dir, path.removeprefix("/exports/"), download=True)
                return
            self._send_file(_STATIC_DIR, path.lstrip("/"))

        def _send_file(self, folder: Path, name: str, download: bool = False) -> None:
            #  Only a file directly in ``folder``: no subfolders, no "..".
            if not name or "/" in name or "\\" in name or name.startswith("."):
                return self._not_found()
            target = folder / name
            if not target.is_file():
                return self._not_found()
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type.endswith("javascript"):
                content_type += "; charset=utf-8"
            body = target.read_bytes()
            if name.endswith(".html") and folder == _STATIC_DIR:
                body = _inject_bridge(body.decode("utf-8")).encode("utf-8")
            extra = None
            if download:
                extra = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}
            self._send(HTTPStatus.OK, body, content_type, extra)

        def do_POST(self) -> None:  # noqa: N802 -- the base class's name
            parts = urlsplit(self.path).path.strip("/").split("/")
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if parts == ["api", "new"]:
                self._send_json({"session": app.new_main()})
                return
            if len(parts) != 3 or parts[0] != "api":
                return self._not_found()
            sid, method = parts[1], parts[2]
            if method == "_poll":
                session = app.get(sid)
                if session is None:
                    self._send_json({"error": "ended"}, HTTPStatus.GONE)
                else:
                    self._send_json({"scripts": session[1].take_scripts(_POLL_SECONDS)})
                return
            if method == "_close":
                app.close(sid)
                self._send_json({})
                return
            try:
                args = json.loads(raw or b"[]")
            except ValueError:
                return self._send_json({"error": "Bad request"}, HTTPStatus.BAD_REQUEST)
            if not isinstance(args, list):
                return self._send_json({"error": "Bad request"}, HTTPStatus.BAD_REQUEST)
            self._send_json(app.call(sid, method, args))

    return Handler


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                exports_dir: Path | None = None) -> ThreadingHTTPServer:
    """The app's server, bound but not yet serving."""
    app = _App(exports_dir or default_exports_dir())
    server = ThreadingHTTPServer((host, port), _make_handler(app))
    server.daemon_threads = True  # a page's held-open _poll doesn't keep the process alive
    server.app = app
    return server


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True,
          exports_dir: Path | None = None) -> int:
    """Serve the app until interrupted (Ctrl-C)."""
    try:
        server = make_server(host, port, exports_dir)
    except OSError as e:
        print(f"Couldn't listen on {host}:{port}: {e}. Try another --port.", file=sys.stderr)
        return 1
    phrases.warm()
    shown_host = "localhost" if host in ("127.0.0.1", "0.0.0.0", "") else host
    url = f"http://{shown_host}:{server.server_address[1]}/"
    print(f"AnkiPasuk is running at {url}")
    print(f"Saved files go to {server.app.exports_dir}")
    print("Press Ctrl-C to stop.")
    sys.stdout.flush()
    if open_browser:
        #  On a thread: on some systems opening the browser waits for it.
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
