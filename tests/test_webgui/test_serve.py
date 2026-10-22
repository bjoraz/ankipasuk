"""Tests for ankipasuk.webgui.serve: the app served to a browser, over
plain HTTP (tests/test_frontend/test_served.py drives it in one)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from ankipasuk.webgui.serve import BrowserWindow, make_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ANKIPASUK_CACHE_DIR", str(tmp_path))
    server = make_server("127.0.0.1", 0, exports_dir=tmp_path / "exports")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield server
    server.shutdown()
    server.server_close()


def get(server, path):
    with urllib.request.urlopen(server.url + path) as response:
        return response.read().decode("utf-8")


def post(server, path, body=None):
    data = b"" if body is None else json.dumps(body).encode()
    request = urllib.request.Request(server.url + path, data=data, method="POST")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def test_pages_load_the_bridge_before_their_own_scripts(server):
    html = get(server, "/index.html")
    assert html.index('<script src="bridge.js">') < html.index('<script src="app.js">')
    assert "pywebviewready" in get(server, "/bridge.js")


def test_only_the_static_folders_own_files_are_served(server):
    for path in ("/..%2fapi.py", "/../api.py", "/nothing.js", "/exports/..%2f..%2fsettings.json"):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(server, path)
        assert e.value.code == 404


def test_a_call_answers_with_the_bridges_result(server):
    sid = post(server, "/api/new")["session"]
    assert post(server, f"/api/{sid}/get_chapter_count", ["Genesis"])["result"] == {"ok": True, "count": 50}
    assert "error" in post(server, f"/api/{sid}/_cache_status_text", [])
    assert "error" in post(server, f"/api/{sid}/no_such_method", [])
    assert "error" in post(server, "/api/unknown/get_books", [])


def test_a_second_window_is_a_session_of_its_own_and_scripts_reach_it(server):
    sid = post(server, "/api/new")["session"]
    answer = post(server, f"/api/{sid}/open_anki_connect_window", [])
    (opened,) = answer["opened"]
    assert opened["title"] == "Anki tools" and opened["url"].startswith("anki_connect.html?session=")
    tools = opened["url"].split("=", 1)[1]
    assert post(server, f"/api/{tools}/get_default_url", [])["result"].startswith("http://")
    server.app.get(tools)[1].evaluate_js("appendLog('conn', 'hi')")
    assert post(server, f"/api/{tools}/_poll")["scripts"] == ["appendLog('conn', 'hi')"]
    post(server, f"/api/{tools}/_close")
    assert server.app.get(tools) is None


def test_the_save_dialog_picks_a_free_name_in_the_exports_folder(tmp_path):
    window = BrowserWindow(tmp_path / "exports")
    first = window.create_file_dialog(save_filename="cards.csv")
    second = window.create_file_dialog(save_filename="../cards.csv")
    assert first == str(tmp_path / "exports" / "cards.csv")
    assert second == str(tmp_path / "exports" / "cards (2).csv")


def test_where_pywebview_cant_open_a_window_the_app_is_served(monkeypatch):
    import ankipasuk.webgui as webgui

    served = []
    monkeypatch.setattr(webgui, "opens_windows", lambda: False)
    monkeypatch.setattr(webgui, "serve", lambda *args: served.append(args) or 0)
    assert webgui.main([]) == 0
    assert served and served[0][:2] == ("127.0.0.1", 8770)
