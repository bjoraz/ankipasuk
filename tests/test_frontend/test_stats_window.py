"""The statistics window, offline, on Bereshit 1:1-2:3 (see conftest)."""

import pytest

from ankipasuk.settings import Settings

from .conftest import Page, bundled_chapter


@pytest.fixture
def stats_window(browser, offline):
    from ankipasuk.cache import SefariaCache
    from ankipasuk.webgui.stats_api import StatsApi

    verses = [{"book": "Genesis", "ch": ch, "vs": vs, "pointed": text, "plain": text}
              for ch in (1, 2) for vs, text in enumerate(bundled_chapter("Genesis", ch), start=1)
              if (ch, vs) <= (2, 3)]
    api = StatsApi(verses, 2, "", cache=SefariaCache(cache_dir=offline), settings=Settings(cache_dir=offline))
    page = Page(browser, "stats.html", api)
    page.page.wait_for_selector("#ph-tabs button", state="attached")
    yield page
    page.page.close()
    assert page.errors == []


def test_the_statistics_window_lists_the_phrases_and_opens_one(stats_window):
    page = stats_window.page
    page.click('[data-tab="phrases"]')
    rows = page.locator("#phrases-list li.ph")
    assert rows.count() == 12 and page.locator(".ph-more").is_visible()
    rows.first.click()
    page.wait_for_selector(".ph-viewer .ph-here .ph-hit")
    assert "A refrain" in page.locator(".ph-viewer-sub").inner_text()
    page.keyboard.press("Escape")
    # A frame's viewer: both its ends here, so nothing elsewhere.
    page.click('#ph-tabs [data-kind="frame"]')
    bara = page.locator("#phrases-list li.ph", has=page.locator('.ph-n:text-is("1:1–2:3")')).first
    bara.locator(".ph-text").click()
    page.wait_for_selector(".ph-viewer .ph-here .ph-hit")
    assert page.locator(".ph-viewer-sub").inner_text().startswith("A frame: Bereshit 1:1–2:3 · 7 sections")
    assert page.locator(".ph-viewer .ph-here .ph-ref").all_inner_texts() == ["Bereshit 1:1", "Bereshit 2:3"]
    page.keyboard.press("Escape")
    # Archived here too, and kept in the main window's settings.
    bara.hover()
    bara.locator(".ph-archive").click()
    page.wait_for_selector(".ph-archive-open")
    assert page.locator("#phrases-list li.ph", has=page.locator('.ph-n:text-is("1:1–2:3")')).count() == 0
    assert stats_window.bridge._settings.get("phrase_archive")[0]["kind"] == "frame"
