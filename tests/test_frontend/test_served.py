"""The app served to a browser (ankipasuk --serve, see webgui/serve.py),
offline: its bridge.js in place of pywebview's, the Anki tools and the
statistics opened over the page, and a saved file offered for download."""

import threading

import pytest

from ankipasuk.webgui.serve import make_server


@pytest.fixture
def served(browser, offline):
    server = make_server("127.0.0.1", 0, exports_dir=offline / "exports")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    page = browser.new_page(viewport={"width": 1366, "height": 860})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
    page.wait_for_function("document.getElementById('line-count').textContent.includes('loaded')")
    yield page, server
    page.close()
    server.shutdown()
    server.server_close()
    assert errors == []


def test_the_anki_tools_open_over_the_page_and_stream_their_log(served):
    page, _server = served
    page.click("#btn-anki-tools")
    tools = page.frame_locator("iframe[src^='anki_connect.html']")
    tools.locator("#run-conn").click()
    # Anki is refused (see conftest); the error comes through evaluate_js.
    tools.locator("#log-conn", has_text="ERROR").wait_for()
    assert tools.locator("#run-conn").inner_text() == "Run"
    page.get_by_role("button", name="Close", exact=True).click()
    assert page.locator("iframe[src^='anki_connect.html']").count() == 0


def test_the_statistics_open_over_the_page_and_close_with_it(served):
    page, server = served
    page.click("#btn-stats")
    stats = page.frame_locator("iframe[src^='stats.html']")
    stats.locator("#summary-text", has_text="Verses analyzed").wait_for()
    sessions = server.app._sessions.values()
    api = next(js_api for js_api, _window in sessions if hasattr(js_api, "_stats_windows"))
    assert len(api._stats_windows) == 1
    page.get_by_role("button", name="Close", exact=True).click()
    page.wait_for_function("document.querySelectorAll(\"iframe[src^='stats.html']\").length === 0")
    page.wait_for_timeout(300)  # the closing page's beacon
    assert api._stats_windows == []


def test_a_saved_file_lands_in_the_exports_folder_and_downloads(served, offline):
    page, _server = served
    page.click("#btn-stats")
    stats = page.frame_locator("iframe[src^='stats.html']")
    stats.locator("#summary-text", has_text="Verses analyzed").wait_for()
    stats.locator("#btn-export-stats-csv").click()  # its alert, saying where, is dismissed
    link = stats.get_by_role("link", name="Download verse_stats.csv")
    link.wait_for()
    assert (offline / "exports" / "verse_stats.csv").read_text(encoding="utf-8").strip()
    with page.expect_download() as download:
        link.click()
    assert download.value.suggested_filename == "verse_stats.csv"
