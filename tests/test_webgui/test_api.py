"""Tests for ankipasuk.webgui.api.Api.

Every method is a thin wrapper around already-tested core logic
(cloze.py, sefaria.py) -- these tests focus on the wrapping itself: does
the JSON-serializable shape returned to JS match what the frontend
expects, are errors reported as {"ok": False, "error": ...} rather than
raised, and is state (_current_verse_data, accumulated across fetches
and stamped per-verse with "book" rather than tracked as a single
Api-wide _current_book) threaded through correctly between calls.
"""

from ankipasuk.cache import SefariaCache
from ankipasuk.config import POINTED_VERSION
from ankipasuk.lpcg import MODEL_NAME as LPCG_MODEL_NAME
from ankipasuk.settings import Settings
from ankipasuk.webgui.api import Api


def test_get_books_returns_categorized_dict():
    api = Api()
    books = api.get_books()
    assert "Genesis" in books["Torah"]
    assert "Deuteronomy" in books["Torah"]
    assert "Isaiah" in books["Nevi'im"]
    assert "I Samuel" in books["Nevi'im"]
    assert "Esther" in books["Megillot"]


def test_get_chapter_count_and_verse_count():
    api = Api()
    assert api.get_chapter_count("Genesis") == {"ok": True, "count": 50}
    assert api.get_verse_count("Genesis", 1) == {"ok": True, "count": 31}


def test_get_verse_count_out_of_range_chapter_is_safe():
    api = Api()
    # Doesn't raise -- returns a harmless default for an invalid chapter.
    assert api.get_verse_count("Genesis", 999) == {"ok": True, "count": 1}


def test_get_chapter_count_reports_error_for_unknown_book():
    api = Api()
    result = api.get_chapter_count("Not A Real Book")
    assert result["ok"] is False
    assert "error" in result


def test_generate_cloze_without_fetched_verses_reports_error():
    api = Api()
    result = api.generate_cloze(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_generate_cloze_matches_verse_to_nested_cloze(genesis_1_1):
    from ankipasuk.cloze import verse_to_nested_cloze

    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]

    result = api.generate_cloze(2, True)
    assert result["ok"] is True

    expected_cloze, _last, _tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=2)
    assert result["output"] == expected_cloze
    assert "viz-line" in result["viz_html"]


def test_generate_cloze_wraps_each_verse_for_spacing(genesis_1_1, genesis_1_2):
    """Each verse's rows must be wrapped in its own container so CSS can
    put a gap between verses without affecting the (smaller) gap between
    rows within the same verse."""
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_2, "plain": genesis_1_2},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert result["viz_html"].count('class="viz-verse"') == 2


def test_generate_cloze_skips_blank_lines(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": "   ", "plain": ""},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert result["output"].count("\n") == 0  # only one non-blank verse -> one line


def test_generate_cloze_reset_per_line_vs_continuous(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_1, "plain": genesis_1_1},
    ]
    reset = api.generate_cloze(2, True)
    continuous = api.generate_cloze(2, False)
    # With reset, both lines' cloze numbering starts at c1; without reset,
    # the second line continues from where the first left off.
    assert reset["output"].split("\n")[1].startswith("{{c1::") or "{{c1::" in reset["output"].split("\n")[1]
    assert "{{c1::" not in continuous["output"].split("\n")[1]


def test_fetch_chapter_verse_accumulates_across_calls_and_books(genesis_1_1, monkeypatch):
    """The core of the new multi-range feature: calling fetch_chapter_verse
    more than once appends rather than replaces, and different calls can
    name different books -- each verse keeps track of its own book."""
    api = Api()

    def fake_fetch(book, start_ch, start_vs, end_ch, end_vs, cache, version_param):
        return [{"book": book, "ch": start_ch, "vs": start_vs, "pointed": genesis_1_1, "plain": genesis_1_1}]

    monkeypatch.setattr("ankipasuk.webgui.api.fetch_verse_range", fake_fetch)

    first = api.fetch_chapter_verse("Genesis", 1, 1, 1, 1)
    assert first["ok"] is True
    assert len(first["verses"]) == 1

    second = api.fetch_chapter_verse("Isaiah", 6, 1, 6, 1)
    assert second["ok"] is True
    assert len(second["verses"]) == 2
    assert [v["book"] for v in second["verses"]] == ["Genesis", "Isaiah"]


def test_clear_ranges_empties_accumulated_verse_data(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]
    result = api.clear_ranges()
    assert result == {"ok": True, "verses": []}
    assert api._current_verse_data == []


def _seed_tikkun_source(api, tmp_path, monkeypatch):
    """A tiny 2-verse fake Genesis chapter with real nikud/trope in its
    tikkun.io row text, for exercising fetch_tikkun_chapter_verse /
    fetch_tikkun_parashah_aliyah with zero network access."""
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [2]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_tikkun_toc({
        "1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}}},
    })
    api._cache.set_tikkun_page(1, [
        {"text": [["בְּרֵאשִׁ֖ית"]], "verses": [{"chapter": 1, "verse": 1}],
         "aliyot": [{"standard": 1}], "isPetucha": False},
        {"text": [["בָּרָ֣א"]], "verses": [{"chapter": 1, "verse": 2}], "aliyot": [], "isPetucha": False},
    ])
    # For fetch_parashah_aliyah/fetch_tikkun_parashah_aliyah's own range resolution.
    api._cache.set_parasha_structure(
        "Genesis", [{"name": "Bereshit", "refs": ["Genesis 1:1-1:2"]}],
    )
    api._cache.set_text("Genesis 1:1-1:2", POINTED_VERSION, ["v1", "v2"])


def test_fetch_tikkun_chapter_verse_renders_plain_and_pointed_html(tmp_path, monkeypatch):
    api = Api()
    _seed_tikkun_source(api, tmp_path, monkeypatch)

    result = api.fetch_tikkun_chapter_verse("Genesis", 1, 1, 1, 2)

    assert result["ok"] is True
    assert '<div class="lines"' in result["plain_html"]
    assert "בראשית" in result["plain_html"]
    assert "בְּרֵאשִׁ֖ית" in result["pointed_html"]
    assert "בראשית" not in result["pointed_html"]  # the unpointed form never appears there


def test_fetch_tikkun_chapter_verse_is_a_noop_for_non_torah_books(tmp_path, monkeypatch):
    api = Api()
    _seed_tikkun_source(api, tmp_path, monkeypatch)

    result = api.fetch_tikkun_chapter_verse("Isaiah", 6, 1, 6, 1)

    assert result["ok"] is True
    assert result["plain_html"] == ""
    assert result["pointed_html"] == ""


def test_fetch_tikkun_chapter_verse_accumulates_across_calls(tmp_path, monkeypatch):
    api = Api()
    _seed_tikkun_source(api, tmp_path, monkeypatch)

    first = api.fetch_tikkun_chapter_verse("Genesis", 1, 1, 1, 1)
    second = api.fetch_tikkun_chapter_verse("Genesis", 1, 2, 1, 2)

    assert second["plain_html"].startswith(first["plain_html"])
    assert second["plain_html"] != first["plain_html"]
    assert "בראשית" in second["plain_html"]
    assert "ברא" in second["plain_html"]


def test_fetch_tikkun_parashah_aliyah_renders_the_resolved_range(tmp_path, monkeypatch):
    api = Api()
    _seed_tikkun_source(api, tmp_path, monkeypatch)

    result = api.fetch_tikkun_parashah_aliyah("Genesis", "Bereshit", 1)

    assert result["ok"] is True
    assert "בראשית" in result["plain_html"]
    assert "ברא" in result["plain_html"]


def test_get_tikkun_scroll_css_contains_the_shared_selectors():
    api = Api()
    css = api.get_tikkun_scroll_css()
    assert ".lines" in css
    assert ".fragment" in css


def test_get_tikkun_font_css_embeds_the_cached_font(tmp_path):
    api = Api()
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._cache.set_tikkun_font("ZmFrZS1mb250")

    result = api.get_tikkun_font_css()

    assert result["ok"] is True
    assert "ZmFrZS1mb250" in result["css"]
    assert "@font-face" in result["css"]


def test_export_csv_without_fetched_verses_reports_error():
    api = Api()
    result = api.export_csv(2, True)
    assert result["ok"] is False
    assert "error" in result


def test_export_csv_without_window_reports_error(genesis_1_1):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1}
    ]
    api._window = None
    result = api.export_csv(2, True)
    assert result["ok"] is False


def test_export_csv_uses_each_verses_own_book_for_the_label(genesis_1_1, tmp_path):
    """A CSV built from a concatenated multi-book range must label each
    row with ITS OWN book, not one book for the whole export -- this is
    the specific regression the removal of a single Api-wide
    _current_book was meant to fix."""
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Isaiah", "ch": 6, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
    ]

    out_path = tmp_path / "cloze_cards.csv"

    class FakeWindow:
        def create_file_dialog(self, *a, **kw):
            return str(out_path)

    api._window = FakeWindow()
    result = api.export_csv(2, True)
    assert result["ok"] is True

    content = out_path.read_text(encoding="utf-8-sig")
    assert "Bereshit 1:1" in content
    assert "Yeshayahu 6:1" in content



def _seed_two_aliyah_parasha(api, tmp_path):
    """Pre-seed api._cache with a single parashah ("Bereshit") of two
    one-verse aliyot, entirely within Genesis chapter 1 -- enough for
    export_aliyot_to_anki to run with zero network access.

    Card content comes from tikkun.io's scroll-line data (see
    ankipasuk.tikkun), not Sefaria's per-verse text, so both a fake
    parasha structure/text AND a fake tikkun table-of-contents/page are
    seeded here -- each of the two verses given its own scroll line, so
    each aliyah still produces exactly one card in these tests.

    verse-mode (the default) additionally needs a Sefaria word count per
    verse (see ankipasuk.verse_cards), fetched by chapter ref
    ("Genesis 1") rather than aliyah ref -- seeded here too (one word per
    verse, matching each verse's own one-word tikkun row below), so that
    lookup doesn't fall back to a real network fetch.
    """
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_parasha_structure(
        "Genesis",
        [{"name": "Bereshit", "refs": ["Genesis 1:1", "Genesis 1:2"]}],
    )
    # fetch_aliyot_in_range fetches text keyed by each aliyah's own ref
    # string (single verses here), not per chapter.
    api._cache.set_text("Genesis 1:1", POINTED_VERSION, ["v1"])
    api._cache.set_text("Genesis 1:2", POINTED_VERSION, ["v2"])
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["א", "ב"])

    api._cache.set_tikkun_toc({
        "1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 2}, "3": {"p": 1, "l": 3}}},
    })
    api._cache.set_tikkun_page(1, [
        {"text": [["אאא"]], "verses": [{"chapter": 1, "verse": 1}],
         "aliyot": [{"standard": 1}], "isPetucha": False},
        {"text": [["בבב"]], "verses": [{"chapter": 1, "verse": 2}], "aliyot": [], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")  # avoid a real network fetch


def test_export_aliyot_to_anki_pushes_one_note_type_and_notes_per_aliyah(tmp_path, fake_anki):
    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)

    result = api.export_aliyot_to_anki(
        "Genesis", "Bereshit", 1, "Bereshit", 2, "Leyning::Recitation",
    )

    assert result["ok"] is True
    assert result["aliyot"] == 2
    assert result["notes_added"] == 2  # one scroll line per aliyah -> one card per aliyah
    assert LPCG_MODEL_NAME in fake_anki.models
    assert all(n["deck"] == "Leyning::Recitation" for n in fake_anki.notes.values())


def _seed_two_verses_sharing_a_row(api, tmp_path, monkeypatch):
    """A single aliyah covering two verses that share a physical scroll
    row: verse 1 is one word ("אאא") and verse 2 (three words: "בבב",
    "גגג", "דדד") starts on that same row, then continues across two more
    rows on its own. Exercises the "tail ends cohabiting a shared row"
    case verse-mode cards must handle -- row0 ("אאא בבב") holds verse 1's
    whole content AND the first word of verse 2's.

    verse-mode's word-alignment (ankipasuk.verse_cards) needs each verse's
    own Sefaria word count too, fetched (like ankipasuk.sefaria elsewhere)
    by chapter ref ("Genesis 1"), not by aliyah ref -- unrelated to (and a
    different cache key than) the aliyah-ref text fetch_aliyot_in_range
    itself uses to discover aliyah boundaries.
    """
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [2]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_parasha_structure(
        "Genesis",
        [{"name": "Bereshit", "refs": ["Genesis 1:1-1:2"]}],
    )
    api._cache.set_text("Genesis 1:1-1:2", POINTED_VERSION, ["v1", "v2"])
    # Chapter-keyed text, for verse_cards' own per-verse word counts.
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["א", "ב ג ד"])

    api._cache.set_tikkun_toc({
        "1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 1}}},
    })
    api._cache.set_tikkun_page(1, [
        {"text": [["אאא בבב"]], "verses": [{"chapter": 1, "verse": 1}, {"chapter": 1, "verse": 2}],
         "aliyot": [{"standard": 1}], "isPetucha": False},
        {"text": [["גגג"]], "verses": [], "aliyot": [], "isPetucha": False},
        {"text": [["דדד"]], "verses": [], "aliyot": [], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")  # avoid a real network fetch


def test_export_aliyot_to_anki_verse_mode_shares_a_boundary_row(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_two_verses_sharing_a_row(api, tmp_path, monkeypatch)

    result = api.export_aliyot_to_anki("Genesis", "Bereshit", 1, "Bereshit", 1, "Deck")

    assert result["ok"] is True
    assert result["notes_added"] == 2  # one card per verse, not per row
    back_rows = sorted(n["fields"]["BackRows"] for n in fake_anki.notes.values())
    # Verse 1's card tests only its own word ("אאא") -- verse 2's word on
    # that same row ("בבב") still occupies the row (a real Torah scroll
    # doesn't blank out the next verse's opening word), but must be
    # masked rather than shown, so verse 2's own card isn't spoiled.
    short_card, long_card = back_rows
    assert '<span class="cloze-inline">אאא</span>' in short_card
    assert '<span class="cloze-inline">בבב</span>' not in short_card
    assert '<span class="cloze-inline masked">בבב</span>' in short_card

    # Verse 2's card tests its own 3 words across all 3 rows, with verse
    # 1's word ("אאא") showing as plain (untested) context on the shared row.
    assert '<span class="cloze-inline">בבב</span>' in long_card
    assert '<span class="cloze-inline">גגג</span>' in long_card
    assert '<span class="cloze-inline">דדד</span>' in long_card
    assert '<span class="cloze-inline">אאא</span>' not in long_card
    # verse 1's word as plain context, sharing one (non-setuma) fragment
    # with verse 2's own cloze span -- see verse_cards._render_row_html.
    assert '<div class="line"><div class="column"><span class="fragment">אאא ' in long_card


def _seed_aliyah_starting_mid_row(api, tmp_path, monkeypatch):
    """Two one-verse aliyot sharing a physical scroll row -- but unlike
    _seed_two_verses_sharing_a_row, the EXPORT only covers the SECOND
    aliyah (verse 2), excluding verse 1 entirely. Verse 1's own word
    ("קקק") still shares row 0 with verse 2's own first word ("בבב"),
    exactly as Exodus 20:1's row also carries the last word of 19:25 --
    the regression this fixture targets: without accounting for the
    excluded verse just before the range, its word would get silently
    counted as part of verse 2's OWN tested content (see
    ankipasuk.verse_cards's module docstring on "leading bleed").
    """
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [2]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_parasha_structure(
        "Genesis",
        [{"name": "Bereshit", "refs": ["Genesis 1:1", "Genesis 1:2"]}],
    )
    api._cache.set_text("Genesis 1:1", POINTED_VERSION, ["v1"])
    api._cache.set_text("Genesis 1:2", POINTED_VERSION, ["v2"])
    # Chapter-keyed text, for verse_cards' own per-verse word counts.
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["קקק", "בבב גגג"])

    api._cache.set_tikkun_toc({
        "1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 1, "l": 1}}},
    })
    api._cache.set_tikkun_page(1, [
        {"text": [["קקק בבב"]], "verses": [{"chapter": 1, "verse": 1}, {"chapter": 1, "verse": 2}],
         "aliyot": [{"standard": 1}, {"standard": 2}], "isPetucha": False},
        {"text": [["גגג"]], "verses": [], "aliyot": [], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")  # avoid a real network fetch


def test_export_aliyot_to_anki_excludes_a_prior_verses_bleed_from_the_first_card(
    tmp_path, fake_anki, monkeypatch,
):
    api = Api()
    _seed_aliyah_starting_mid_row(api, tmp_path, monkeypatch)

    result = api.export_aliyot_to_anki("Genesis", "Bereshit", 2, "Bereshit", 2, "Deck")

    assert result["ok"] is True
    assert result["notes_added"] == 1  # only verse 2's own card -- verse 1 isn't in range
    (note,) = fake_anki.notes.values()
    back_rows = note["fields"]["BackRows"]

    # Verse 2's own tested content is ONLY its own 2 words -- verse 1's
    # word, sharing the same row, must show as plain context, never as
    # part of what's tested.
    assert '<span class="cloze-inline">בבב</span>' in back_rows
    assert '<span class="cloze-inline">גגג</span>' in back_rows
    assert '<span class="cloze-inline">קקק</span>' not in back_rows
    # "[Beginning]" still applies -- verse 1's own row has nothing before
    # it either in this fixture (it's the chapter's first verse).
    assert back_rows.startswith(
        '<div class="line beginning-marker">[Beginning]</div>'
        '<div class="line"><div class="column"><span class="fragment">קקק '
    )


def test_export_aliyot_to_anki_row_mode_still_available(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_two_verses_sharing_a_row(api, tmp_path, monkeypatch)

    result = api.export_aliyot_to_anki(
        "Genesis", "Bereshit", 1, "Bereshit", 1, "Deck", card_division="row",
    )

    assert result["ok"] is True
    assert result["notes_added"] == 3  # one card per physical row, the old behavior


def test_get_lpcg_deck_name_defaults_when_nothing_saved_yet(tmp_path):
    api = Api()
    api._settings = Settings(cache_dir=tmp_path)
    assert api.get_lpcg_deck_name() == Api.DEFAULT_LPCG_DECK_NAME


def test_export_aliyot_to_anki_remembers_the_deck_name_for_next_time(tmp_path, fake_anki):
    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)

    api.export_aliyot_to_anki("Genesis", "Bereshit", 1, "Bereshit", 1, "Master::Leyning::Aliyot")
    assert api.get_lpcg_deck_name() == "Master::Leyning::Aliyot"

    # Simulates a fresh app launch reading the same on-disk settings.
    api2 = Api()
    api2._settings = Settings(cache_dir=tmp_path)
    assert api2.get_lpcg_deck_name() == "Master::Leyning::Aliyot"


def test_export_aliyot_to_anki_sets_a_box_width_from_the_verse_text(tmp_path, fake_anki):
    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)

    api.export_aliyot_to_anki("Genesis", "Bereshit", 1, "Bereshit", 1, "Deck")

    (note,) = fake_anki.notes.values()
    # "אאא" alone is far short of MIN_BOX_WIDTH_CH, so the floor -- not
    # the verse-text-derived factor -- is what actually sets this field
    # here; see test_lpcg.py for the content-driven case.
    assert note["fields"]["BoxWidth"] == "40ch"


def test_export_aliyot_to_anki_refreshes_css_on_an_already_existing_model(tmp_path, fake_anki):
    """A note type created by an older version of this code (before a CSS
    change, e.g. adding the STAM font or setumah-gap styling) must not be
    stuck with stale styling forever -- ensure_model alone never updates
    an existing model, so export_aliyot_to_anki must also refresh it."""
    from ankipasuk.anki_connect.operations import ensure_model
    from ankipasuk.lpcg import CARD_TEMPLATES, FIELD_NAMES

    ensure_model(LPCG_MODEL_NAME, FIELD_NAMES, "stale old css", CARD_TEMPLATES, url="http://localhost:8765")

    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)
    api.export_aliyot_to_anki("Genesis", "Bereshit", 1, "Bereshit", 1, "Deck")

    assert fake_anki.models[LPCG_MODEL_NAME]["css"] != "stale old css"


def test_export_aliyot_to_anki_tags_notes_with_the_parasha(tmp_path, fake_anki):
    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)

    api.export_aliyot_to_anki("Genesis", "Bereshit", 1, "Bereshit", 1, "Deck")

    (note,) = fake_anki.notes.values()
    assert "ankipasuk-aliyah" in note["tags"]
    assert "parasha::Bereshit" in note["tags"]


def test_export_aliyot_to_anki_reports_sefaria_errors(tmp_path, fake_anki):
    api = Api()
    _seed_two_aliyah_parasha(api, tmp_path)

    result = api.export_aliyot_to_anki(
        "Genesis", "Not A Parasha", 1, "Bereshit", 1, "Deck",
    )
    assert result["ok"] is False
    assert "error" in result


def _seed_one_amud(api, tmp_path, monkeypatch):
    """Pre-seed api._cache with a single one-line amud (amud 1, wholly
    within a fake single-chapter Genesis) -- enough for export_amud_to_anki
    to run with zero network access.

    verse-mode (the default) needs a Sefaria word count per verse too
    (see ankipasuk.verse_cards), fetched by chapter ref ("Genesis 1") --
    seeded here to match the tikkun row's own single word ("אאא"), so the
    word-alignment doesn't fall back to a real network fetch.
    """
    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [1]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["א"])
    api._cache.set_tikkun_toc({"1": {"1": {"1": {"p": 1, "l": 1}}}})
    api._cache.set_tikkun_page(1, [
        {"text": [["אאא"]], "verses": [{"chapter": 1, "verse": 1}],
         "aliyot": [{"standard": 1}], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")  # avoid a real network fetch


def test_export_amud_to_anki_pushes_notes_for_the_whole_amud(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)

    result = api.export_amud_to_anki(1, "Deck")

    assert result["ok"] is True
    assert result["amud"] == 1
    assert result["book"] == "Genesis"
    assert result["notes_added"] == 1
    assert all(n["deck"] == "Deck" for n in fake_anki.notes.values())


def test_export_amud_to_anki_tags_notes_as_an_amud(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)

    api.export_amud_to_anki(1, "Deck")

    (note,) = fake_anki.notes.values()
    assert note["tags"] == ["amud::001"]


def test_export_amud_to_anki_remembers_the_deck_name(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)

    api.export_amud_to_anki(1, "Master::Leyning::Aliyot")
    assert api.get_lpcg_deck_name() == "Master::Leyning::Aliyot"


def test_export_amud_to_anki_rejects_out_of_range_amud(tmp_path, fake_anki):
    api = Api()
    result = api.export_amud_to_anki(0, "Deck")
    assert result["ok"] is False
    assert "error" in result


def test_cache_status_text_reflects_stats():
    api = Api()
    status = api.get_cache_status()
    assert "Cache:" in status
    assert "ref(s)" in status
    assert "book structure(s)" in status

