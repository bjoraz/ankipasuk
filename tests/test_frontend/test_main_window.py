"""The main window, offline, on Bereshit 1-3 made from the bundled data
(see conftest)."""

import json

from ankipasuk.settings import Settings

from .conftest import in_view, load, show_phrases


def test_a_range_loads_and_each_pasuq_is_drawn(main_window):
    load(main_window, 1, 5, 5)
    page = main_window.page
    page.wait_for_function("document.querySelectorAll('#viz-box .dg-pasuq').length === 5")
    assert main_window.texts("#viz-box .dg-ref")[:2] == ["Bereshit 1:1", "Bereshit 1:2"]
    assert page.locator("#btn-export-cloze-anki").inner_text() == "Send 5 pesuqim to Anki"


def test_the_diagrams_letters_only_have_no_pointing_and_no_labels(main_window):
    load(main_window, 1, 5, 5)
    page = main_window.page
    page.wait_for_selector("#viz-box .dg-label")
    marks = ("[...document.querySelectorAll('#viz-box .dg-word')]"
             ".some(w => /[\\u0591-\\u05c7]/.test(w.textContent))")
    assert page.evaluate(marks)  # (the seeded text has ta'amim)
    page.click('#diagram-kind [data-kind="plain"]')
    page.wait_for_selector("#viz-box .dg-line")
    assert not page.evaluate(marks) and page.locator("#viz-box .dg-label").count() == 0
    assert page.locator("#viz-box .dg-word").first.inner_text() == "בראשית"
    # Saving starts as the view shows them, the labels' choice set aside.
    page.click("#btn-save-diagrams")
    assert page.locator('[data-opt="plain"]').is_checked()
    assert page.locator('[data-opt="labels"]').is_disabled()
    page.click("#pd-cancel")
    page.click('#diagram-kind [data-kind="pointed"]')
    page.wait_for_selector("#viz-box .dg-label")


def test_a_range_that_cant_be_fetched_says_why(main_window):
    load(main_window, 3, 24, 80)
    main_window.page.select_option(".range-end-ch", "4")  # not in the cache, and offline
    main_window.page.wait_for_function("document.getElementById('toast').textContent.includes('Sefaria')")
    toast = main_window.page.locator("#toast").inner_text()
    assert "Couldn't reach Sefaria. Check the internet connection" in toast
    assert "HTTPSConnectionPool" not in toast


def test_a_clicked_word_colours_its_shoresh_and_tops_the_list(main_window):
    load(main_window, 1, 5, 5)
    page = main_window.page
    page.click('[data-view="text"]')
    word = page.locator("#text-box .tv-line .w").nth(1)  # ברא
    word.click()
    group = word.get_attribute("data-g")
    assert "hl-0" in (word.get_attribute("class") or "")
    assert page.locator("#roots-list li").first.get_attribute("data-root") == group


def test_phrases_are_listed_by_section_and_a_picked_one_steps_through_the_text(main_window):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    tabs = main_window.texts("#ph-tabs button")
    assert [t.split("\n")[0] for t in tabs] == ["Refrains", "Echoes", "Idioms", "Formulas", "Frames"]
    first = page.locator("#phrases-list li.ph").first
    assert first.locator(".ph-n").inner_text() == "6×"  # ויהי ערב ויהי בקר יום
    first.locator(".ph-text").click()
    assert "picked" in first.get_attribute("class")
    assert first.locator(".ph-pos").inner_text() == "1/6"
    first.locator('[data-jump="1"]').click()
    assert first.locator(".ph-pos").inner_text() == "2/6"
    page.wait_for_function("document.querySelectorAll('#text-box .ph-flash[data-k]').length > 0")
    assert in_view(main_window, "#text-box .ph-flash[data-k]", "#text-box")
    first.locator('[data-jump="-1"]').click()
    first.locator('[data-jump="-1"]').click()
    assert first.locator(".ph-pos").inner_text() == "6/6"  # round from the first to the last
    # Underlined in the text: its words have the line.
    underlined = page.evaluate(
        "[...document.querySelectorAll('#text-box [data-k]')].filter(e => e.style.boxShadow).length")
    assert underlined >= 6 * 4  # ויהי ערב ויהי בקר, six times


def test_a_long_section_shows_its_first_twelve_then_all(main_window):
    load(main_window, 3, 24, 80)
    show_phrases(main_window)
    page = main_window.page
    total = int(page.locator('#ph-tabs [data-kind="refrain"] .ph-tab-n').inner_text())
    assert total > 12 and page.locator("#phrases-list li.ph").count() == 12
    page.click(".ph-more button")
    assert page.locator("#phrases-list li.ph").count() == total
    assert page.locator(".ph-more").inner_text() == "Show the first 12"


def test_phrase_settings_find_the_phrases_again_and_keep_only_whats_changed(main_window, offline):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    count = "Number(document.querySelector('#ph-tabs [data-kind=\"echo\"] .ph-tab-n')?.textContent)"
    before = page.evaluate(count)
    page.click("#btn-settings")
    assert page.locator('[data-setting="echo_places"]').input_value() == "3"
    page.fill('[data-setting="echo_places"]', "6")
    assert page.locator(".changed").count() == 1
    page.click("#settings-form button[type=submit]")
    page.wait_for_function(f"{count} > {before}")
    page.click('#ph-tabs [data-kind="echo"]')
    assert "one to six other pesuqim" in page.locator("#ph-about").inner_text()
    saved = json.loads((offline / "settings.json").read_text())
    assert saved["phrases"] == {"echo_places": 6}
    # Out of its limits, it isn't saved.
    page.click("#btn-settings")
    page.fill('[data-setting="content_words"]', "99")
    page.click("#settings-form button[type=submit]")
    assert page.locator("#settings-dialog").is_visible()
    page.click("#st-reset")
    page.click("#settings-form button[type=submit]")
    page.wait_for_function(f"{count} === {before}")
    assert json.loads((offline / "settings.json").read_text())["phrases"] == {}


def test_an_echo_opens_in_its_chapter(main_window):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    page.click('#ph-tabs [data-kind="echo"]')
    if page.locator(".ph-more").count() and "all" in page.locator(".ph-more").inner_text():
        page.click(".ph-more button")  # תהו ובהו may be further down
    page.locator("#phrases-list .ph-place", has_text="Yirmeyahu 4:23").first.click()
    page.wait_for_selector(".ph-vs.hit")
    assert page.locator(".ph-chapter-title").inner_text() == "Yirmeyahu 4"
    assert page.locator(".ph-vs.hit .ph-vs-n").inner_text() == "4:23"
    assert in_view(main_window, ".ph-vs.hit", ".ph-chapter")  # scrolled to it
    assert page.locator(".ph-there .ph-hit").count() >= 1 and page.locator(".ph-here .ph-hit").count() >= 1
    page.keyboard.press("Escape")
    assert page.locator(".ph-viewer").count() == 0


def test_a_coloured_shoresh_shows_where_it_is_and_goes_there(main_window):
    load(main_window, 2, 3, 34)
    page = main_window.page
    page.click('[data-view="text"]')
    page.locator("#text-box .tv-line .w").nth(1).click()  # ברא: 1:1, 1:21, 1:27 (three times), 2:3
    spark = page.locator("#roots-list .spark")
    assert spark.count() == 1 and spark.locator("rect").count() == 4
    assert spark.get_attribute("data-at") == "0,20,26,33"
    box = spark.bounding_box()
    page.mouse.click(box["x"] + 2, box["y"] + 4)  # the left end: the passage's last pasuq
    page.wait_for_function("document.querySelectorAll('#text-box .ph-flash').length > 0")
    lines = page.evaluate(
        "[...document.querySelectorAll('#text-box .ph-flash')].map(e => e.closest('.tv-line').dataset.i)")
    assert set(lines) == {"33"}


def test_a_picked_phrase_moves_to_the_top_with_where_it_is(main_window):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    ids = lambda: [r.get_attribute("data-id") for r in page.locator("#phrases-list li.ph").all()]  # noqa: E731
    before = ids()
    page.locator("#phrases-list li.ph").nth(3).locator(".ph-text").click()
    assert ids()[0] == before[3] and ids()[1:4] == before[:3]
    assert page.locator("#phrases-list li.last-picked").count() == 1
    assert page.locator("#phrases-list li.ph").first.locator(".spark").count() == 1
    page.locator("#phrases-list li.ph").first.locator(".ph-text").click()  # unpicked: back in its place
    assert ids()[:4] == before[:4] and page.locator("#phrases-list .spark").count() == 0


def test_frames_are_listed_and_a_picked_one_goes_from_one_end_to_the_other(main_window):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    page.click('#ph-tabs [data-kind="frame"]')
    groups = page.locator("#phrases-list .ph-fold")
    assert [g.get_attribute("data-group") for g in groups.all()] == ["runs", "words"]
    # The words' frames are folded: shown when their header is clicked, and remembered.
    assert page.locator("#phrases-list li.ph").count() == 1
    page.click('#phrases-list .ph-fold[data-group="words"]')
    words = int(page.locator('#phrases-list .ph-fold[data-group="words"] .ph-class-n').inner_text())
    assert page.locator("#phrases-list li.ph").count() == 1 + words
    page.click('#phrases-list .ph-fold[data-group="words"]')
    assert page.locator("#phrases-list li.ph").count() == 1
    bara = page.locator("#phrases-list li.ph", has=page.locator('.ph-n:text-is("1:1–2:3")')).first
    assert "7 sections" in bara.locator(".ph-meta").inner_text()
    bara.locator(".ph-text").click()
    assert bara.locator(".ph-pos").inner_text() == "1/2"  # its two ends, 1:1 and 2:3
    bara.locator('[data-jump="1"]').click()
    assert bara.locator(".ph-pos").inner_text() == "2/2"
    page.wait_for_selector('#text-box .tv-line[data-i="33"] .ph-flash[data-k]')  # 2:3, its last pasuq
    assert in_view(main_window, '#text-box .tv-line[data-i="33"]', "#text-box")


def test_a_frames_other_end_opens_in_its_chapter(main_window):
    load(main_window, 1, 5, 5)
    show_phrases(main_window)
    page = main_window.page
    page.click('#ph-tabs [data-kind="frame"]')
    bara = page.locator("#phrases-list li.ph", has=page.locator('.ph-n:text-is("1:1–2:3")')).first
    bara.locator(".ph-place").click()
    page.wait_for_selector(".ph-viewer .ph-there h4")
    assert page.locator(".ph-viewer .ph-there h4").text_content().startswith("Outside the passage")
    assert "A frame: Bereshit 1:1–2:3" in page.locator(".ph-viewer-sub").inner_text()
    page.wait_for_selector(".ph-vs.hit")
    assert page.locator(".ph-vs.hit .ph-vs-n").inner_text() == "2:3"


def test_a_frame_of_a_section_says_which(main_window):
    load(main_window, 3, 24, 80)  # Bereshit 2:4-3:21, a petuḥa section with two setumot
    show_phrases(main_window)
    page = main_window.page
    page.click('#ph-tabs [data-kind="frame"]')
    assert page.locator("#phrases-list .ph-fold").first.get_attribute("data-group") == "sections"
    row = page.locator("#phrases-list li.ph").first
    assert row.locator(".ph-n").inner_text() == "2:4–3:21"
    assert "a petuḥa section with 2 setumot" in row.locator(".ph-meta").inner_text()


def test_a_phrase_archived_is_gone_until_restored(main_window):
    load(main_window, 2, 3, 34)
    show_phrases(main_window)
    page = main_window.page
    count = lambda: int(page.locator('#ph-tabs [data-kind="refrain"] .ph-tab-n').inner_text())  # noqa: E731
    before = count()
    first = page.locator("#phrases-list li.ph").first
    pid = first.get_attribute("data-id")
    underlined = "[...document.querySelectorAll('#text-box [data-k]')].some(e => e.style.boxShadow)"
    first.locator(".ph-text").click()  # picked: underlined
    assert page.evaluate(underlined)
    first.hover()
    first.locator(".ph-archive").click()
    page.wait_for_selector(".ph-archive-open")
    assert page.locator(f'#phrases-list li.ph[data-id="{pid}"]').count() == 0 and count() == before - 1
    assert page.locator(".ph-archive-open").inner_text() == "Archive (1)"
    assert not page.evaluate(underlined)  # and no longer picked
    # Gone from every section it was in, and kept in the archive.
    page.click(".ph-archive-open")
    entry = page.locator(".ph-archive-list li.ph")
    assert entry.count() == 1 and "a refrain" in entry.inner_text() and "here" in entry.inner_text()
    entry.locator(".ph-restore").click()
    page.wait_for_selector(".ph-archive-list .ph-none")
    page.keyboard.press("Escape")
    assert count() == before and page.locator(f'#phrases-list li.ph[data-id="{pid}"]').count() == 1
    assert page.locator(".ph-archive-open").count() == 0


def test_the_text_marks_the_masoretic_breaks(main_window):
    load(main_window, 1, 8, 8)
    page = main_window.page
    page.click('[data-view="text"]')
    page.wait_for_selector('#text-box .tv-line[data-i="4"]')
    line = page.locator('#text-box .tv-line[data-i="4"]')  # 1:5, the first day's petuḥa
    assert "tv-end-p" in line.get_attribute("class") and line.locator(".tv-break").inner_text() == "פ"
    assert page.locator('#text-box .tv-line[data-i="3"] .tv-break').count() == 0


def test_each_pasuq_in_the_text_has_its_chapter_and_verse(main_window):
    load(main_window, 1, 8, 8)
    page = main_window.page
    page.click('[data-view="text"]')
    page.wait_for_selector('#text-box .tv-line[data-i="4"] .w')
    number = page.locator('#text-box .tv-line[data-i="4"] .tv-n')
    assert number.inner_text() == "1:5" and number.get_attribute("title") == "Bereshit 1:5"
    # One a pasuq, left out when the text is copied.
    assert page.locator("#text-box .tv-line .tv-n").count() == 8
    assert page.evaluate("getComputedStyle(document.querySelector('#text-box .tv-n')).userSelect") == "none"


def test_the_fields_pane_colours_the_words_of_a_field(main_window):
    load(main_window, 2, 3, 34)
    page = main_window.page
    page.click('[data-view="text"]')
    page.wait_for_selector("#text-box .tv-line .w")
    page.click('#panel-kind [data-pane="fields"]')
    page.wait_for_selector("#fields-list li[data-field]")
    assert page.locator("#text-hint").inner_text() == "Click a word to colour its fields"
    page.click('#fields-sort [data-sort="key"]')
    assert page.locator("#fields-list li").first.get_attribute("data-field") == "001002002"  # Heaven
    background = "(el) => getComputedStyle(el).backgroundImage + getComputedStyle(el).backgroundColor"
    # מַיִם, in two fields
    water = page.locator('#text-box .tv-line[data-i="1"] [data-d="001002006007 001002009"]')
    plain = water.evaluate(background)
    page.click('#fields-list li[data-field="001002006007"]')  # Liquids
    one = water.evaluate(background)
    assert one != plain and "gradient" not in one
    page.click('#fields-list li[data-field="001002009"]')  # Waterbodies: now striped
    assert "repeating-linear-gradient" in water.evaluate(background)
    assert page.locator("#fields-list li").first.locator(".spark").count() == 1  # coloured ones first
    # A word's click colours its fields, and again takes them off.
    heaven = page.locator('#text-box .tv-line[data-i="0"] [data-d="001002002"]')
    heaven.click()
    label = page.locator('#fields-list li[data-field="001002002"] .fd-label')
    assert "hl-" in (label.get_attribute("class") or "")
    heaven.click()
    assert page.locator('#fields-list li[data-field="001002002"] .spark').count() == 0
    heaven.hover()  # its tooltip: its shoresh, then its sense
    title = heaven.get_attribute("title")
    assert "heaven, sky" in title and "Objects › Natural World › Heaven" in title
    # Names come in when asked for: אֱלֹהִים gets a field.
    god = page.locator('#text-box .tv-line[data-i="0"] [data-k="2"]')
    assert god.get_attribute("data-d") is None
    page.check("#fields-reference")
    page.wait_for_function(
        "document.querySelector('#text-box .tv-line[data-i=\"0\"] [data-k=\"2\"]').dataset.d")
    # Back to the shorashim: their colours, not the fields'.
    page.click('#panel-kind [data-pane="roots"]')
    assert "fields-mode" not in (page.locator("#text-box").get_attribute("class") or "")


def test_the_field_level_is_a_setting(main_window, offline):
    load(main_window, 1, 5, 5)
    page = main_window.page
    page.click('[data-view="text"]')
    page.click('#panel-kind [data-pane="fields"]')
    page.wait_for_selector("#fields-list li[data-field]")
    page.click("#btn-field-settings")
    levels = page.locator("#fs-levels label")
    assert levels.count() == 3 and "Level 4 (the default)" in levels.nth(1).inner_text()
    assert "% of the words are filed at it" in levels.nth(0).inner_text()
    assert page.locator("#fs-depths").inner_text().startswith("How deep SDBH files")
    page.check('[name="fs-level"][value="3"]')
    page.click('#field-settings-form button[type="submit"]')
    page.wait_for_function("document.getElementById('fields-level').textContent === 'Level 3'")
    assert Settings(cache_dir=offline).get("fields") == {"level": 3}


def test_the_verbs_pane_counts_the_forms_and_colours_them(main_window):
    load(main_window, 2, 3, 34)
    page = main_window.page
    page.click('[data-view="text"]')
    page.wait_for_selector("#text-box .tv-line .w")
    colour = "getComputedStyle(document.querySelector('#text-box [data-f=\"w\"]')).color"
    plain = page.evaluate(colour)
    page.click('#panel-kind [data-pane="verbs"]')
    page.wait_for_selector("#verbs-list li")
    kinds = page.locator("#verbs-list li")
    assert kinds.count() == 7 and kinds.first.locator(".vf-name").inner_text() == "wayyiqtol"
    assert kinds.first.get_attribute("title").startswith("Wayyiqtol (vav-consecutive imperfect)")
    assert "Imperative: a command" in kinds.nth(4).get_attribute("title")  # each of a group's forms
    total = int(page.locator("#verbs-count").inner_text().strip("()"))
    counted = sum(int(kinds.nth(i).locator(".vf-n").inner_text()) for i in range(7))
    assert total == counted == page.locator('#verbs-strip rect[y="0"]').count()  # a block a verb
    assert page.locator('#verbs-strip rect[y="1.08"]').count() == 7  # a tick a petuḥa: each day
    assert page.evaluate(colour) != plain  # wayyiqtol coloured in the text
    kinds.first.click()  # hidden
    assert page.evaluate(colour) == plain and "off" in kinds.first.get_attribute("class")
    page.check("#verbs-all")
    assert page.locator("#verbs-list li").count() == 11
    page.click('#panel-kind [data-pane="roots"]')  # leaving the pane takes the colours off
    qatal = "getComputedStyle(document.querySelector('#text-box [data-f=\"p\"]')).color"
    assert page.evaluate(qatal) == plain
