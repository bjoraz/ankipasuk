import json
import urllib.error

import pytest

from ankipasuk.anki_connect.client import AnkiConnectError, invoke


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_invoke_returns_result_on_success(monkeypatch):
    import ankipasuk.anki_connect.client as client_module

    def fake_urlopen(request, timeout):
        body = json.dumps({"result": 6, "error": None}).encode("utf-8")
        return _FakeResponse(body)

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)
    assert invoke("version") == 6


def test_invoke_raises_on_connection_error(monkeypatch):
    import ankipasuk.anki_connect.client as client_module

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AnkiConnectError, match="Could not connect"):
        invoke("version")


def test_invoke_raises_friendly_error_on_bare_timeout(monkeypatch):
    """Regression test: on a large response (e.g. cardsInfo for a big
    deck), a timeout while reading the body can surface as a bare
    TimeoutError rather than urllib.error.URLError -- this must still be
    caught and wrapped in AnkiConnectError, not leak out raw."""
    import ankipasuk.anki_connect.client as client_module

    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AnkiConnectError, match="Could not connect"):
        invoke("cardsInfo", cards=[1, 2, 3])


def test_invoke_raises_on_anki_reported_error(monkeypatch):
    import ankipasuk.anki_connect.client as client_module

    def fake_urlopen(request, timeout):
        body = json.dumps({"result": None, "error": "deck was not found"}).encode("utf-8")
        return _FakeResponse(body)

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AnkiConnectError, match="deck was not found"):
        invoke("findCards", query="deck:Nonexistent")


def test_invoke_raises_on_malformed_json(monkeypatch):
    import ankipasuk.anki_connect.client as client_module

    def fake_urlopen(request, timeout):
        return _FakeResponse(b"not json{{{")

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AnkiConnectError, match="unreadable response"):
        invoke("version")
