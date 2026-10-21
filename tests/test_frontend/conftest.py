"""The app's pages in a headless browser, driven like a user would.

Each page gets a stand-in for pywebview's bridge that calls a real Api
(or StatsApi) in this process. Nothing reaches the network or Anki: the
verse cache is seeded with chapters made from the bundled OSHB data (its
letters, an etnaḥta and a tifḥa where OSHB has one of those breaks, and a
sof pasuq), and every request is refused.

Needs Playwright (``pip install -e ".[ui-test]"``) and a Chromium: the one
``python -m playwright install chromium`` installs, or a system one
(``ANKIPASUK_CHROMIUM``, or the usual paths). Without them these tests
are skipped.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import urllib.request
from pathlib import Path

import pytest
import requests

from ankipasuk.cache import SefariaCache
from ankipasuk.config import POINTED_VERSION
from ankipasuk.phrases import BOOKS
from ankipasuk.phrases import DATA_DIR as PHRASE_DATA
from ankipasuk.settings import Settings
from ankipasuk.shorashim import _book
from ankipasuk.shorashim_build import ETNAHTA, KING

STATIC = Path(__file__).resolve().parents[2] / "src" / "ankipasuk" / "webgui" / "static"
SEEDED = [("Genesis", 1), ("Genesis", 2), ("Genesis", 3), ("Jeremiah", 4)]

# The bridge as pywebview gives it (window.pywebview.api.<method>(...) ->
# a promise), each call going to __call; and pywebviewready once loaded.
BRIDGE = """
window.pywebview = {api: new Proxy({}, {get: (_, name) => async (...args) =>
    JSON.parse(await window.__call(name, JSON.stringify(args)))})};
window.addEventListener("load", () => window.dispatchEvent(new Event("pywebviewready")));
"""


def bundled_chapter(book: str, ch: int) -> list[str]:
    """A chapter's pesuqim from the bundled data, as Sefaria's text would
    come: OSHB's words, with OSHB's etnaḥta and its other breaks (as
    tifḥa), and a sof pasuq."""
    words = _book(book)
    breaks = json.loads(gzip.decompress((PHRASE_DATA / f"{BOOKS[book]}.json.gz").read_bytes()))
    verses = []
    vs = 1
    while f"{ch}:{vs}" in words:
        key = f"{ch}:{vs}"
        marked = [w[0] + ("֑" if b[1] & ETNAHTA else "֖" if b[1] & KING else "")
                  for w, b in zip(words[key], breaks[key])]
        verses.append(" ".join(marked) + "׃")
        vs += 1
    return verses


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    found = (os.environ.get("ANKIPASUK_CHROMIUM"), shutil.which("chromium"),
             shutil.which("chromium-browser"), shutil.which("google-chrome"))
    with sync_api.sync_playwright() as p:
        for path in (None, *filter(None, found)):  # Playwright's own Chromium first
            try:
                b = p.chromium.launch(executable_path=path)
            except Exception:  # noqa: BLE001 -- not installed; the next one
                continue
            yield b
            b.close()
            return
        pytest.skip("no Chromium for Playwright (python -m playwright install chromium)")


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """No network, no Anki, the cache and settings in ``tmp_path``, the
    seeded chapters in the cache."""
    monkeypatch.setenv("ANKIPASUK_CACHE_DIR", str(tmp_path))

    def refuse(*_args, **_kwargs):
        raise requests.ConnectionError("offline (tests)")

    def refuse_anki(*_args, **_kwargs):
        raise OSError("Anki is not running (tests)")

    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse_anki)
    cache = SefariaCache(cache_dir=tmp_path)
    for book, ch in SEEDED:
        cache.set_text(f"{book} {ch}", POINTED_VERSION, bundled_chapter(book, ch))
    return tmp_path


class Page:
    """A page of the app with its bridge, the errors it logged, and a few
    helpers."""

    def __init__(self, browser, html: str, bridge):
        self.bridge = bridge
        self.errors: list[str] = []
        self.page = browser.new_page(viewport={"width": 1366, "height": 860})
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        self.page.expose_function("__call", self._call)
        self.page.add_init_script(BRIDGE)
        self.page.goto((STATIC / html).as_uri())

    def _call(self, name: str, args: str) -> str:
        return json.dumps(getattr(self.bridge, name)(*json.loads(args)))

    def texts(self, selector: str) -> list[str]:
        return self.page.locator(selector).all_inner_texts()


@pytest.fixture
def main_window(browser, offline):
    from ankipasuk.webgui.api import Api

    api = Api()
    api._settings = Settings(cache_dir=offline)
    page = Page(browser, "index.html", api)
    page.page.wait_for_function("document.getElementById('line-count').textContent.includes('loaded')")
    yield page
    page.page.close()
    assert page.errors == []


def load(page: Page, end_ch: int, end_vs: int, pesuqim: int) -> None:
    """Bereshit 1:1 to end_ch:end_vs, in the first range row."""
    page.page.select_option(".range-end-ch", str(end_ch))
    page.page.select_option(".range-end-vs", str(end_vs))
    page.page.wait_for_function(
        f"document.getElementById('line-count').textContent === '{pesuqim} pesuqim loaded'")


def show_phrases(page: Page) -> None:
    page.page.click('[data-view="text"]')
    page.page.click('#panel-kind [data-pane="phrases"]')
    page.page.wait_for_selector("#ph-tabs button")
