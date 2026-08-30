"""A minimal AnkiConnect JSON-RPC client.

This is the one place that talks to the AnkiConnect HTTP API. Everything
else in :mod:`ankipasuk.anki_connect` calls :func:`invoke` (directly or via
a thin wrapper) rather than building requests itself, so there is exactly
one implementation of the request/response/error handling to get right.
"""

from __future__ import annotations

import json
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765"
DEFAULT_TIMEOUT = 60


class AnkiConnectError(RuntimeError):
    """Raised for anything that goes wrong talking to AnkiConnect: the
    connection failing (Anki not running, AnkiConnect not installed), a
    malformed response, or an error reported by AnkiConnect itself."""


def invoke(action: str, *, url: str = DEFAULT_URL, timeout: int = DEFAULT_TIMEOUT, **params):
    """Call one AnkiConnect action and return its ``result``.

    Raises :class:`AnkiConnectError` on any connection problem, malformed
    response, or AnkiConnect-reported error -- callers don't need to know
    anything about ``urllib`` or AnkiConnect's JSON envelope.
    """
    request_data = {"action": action, "version": 6, "params": params}
    data = json.dumps(request_data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except OSError as e:
        # Covers urllib.error.URLError (connection failures) as well as a
        # bare TimeoutError/socket.timeout, which urllib can raise directly
        # -- unwrapped -- if the timeout happens while reading a large
        # response body (e.g. cardsInfo/notesInfo on a big deck) rather
        # than while connecting. Both are OSError subclasses, so one
        # except clause catches both and gives a consistent message.
        raise AnkiConnectError(
            f"Could not connect to AnkiConnect at {url}, or it stopped responding "
            f"(possibly a slow/large request timing out). Make sure Anki is running "
            f"and the AnkiConnect add-on is installed.\n"
            f"Technical error: {e}"
        ) from e

    try:
        result = json.loads(payload)
    except json.JSONDecodeError as e:
        raise AnkiConnectError(f"AnkiConnect returned an unreadable response: {e}") from e

    if result.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect error during '{action}': {result['error']}")

    return result.get("result")
