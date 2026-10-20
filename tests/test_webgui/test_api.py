"""Tests for ankipasuk.webgui.api.Api.

Every method is a thin wrapper around already-tested core logic
(cloze.py, sefaria.py) -- these tests focus on the wrapping itself: does
the JSON-serializable shape returned to JS match what the frontend
expects, are errors reported as {"ok": False, "error": ...} rather than
raised, and is state (_current_verse_data, accumulated across fetches
and stamped per-verse with "book" rather than tracked as a single
Api-wide _current_book) threaded through correctly between calls.
"""

import re

from ankipasuk.cache import SefariaCache
from ankipasuk.config import POINTED_VERSION
from ankipasuk.lpcg import FIELD_NAMES as LPCG_FIELD_NAMES
from ankipasuk.lpcg import MODEL_NAME as LPCG_MODEL_NAME
from ankipasuk.settings import Settings
from ankipasuk.verse_cards import build_verse_cards
from ankipasuk.webgui.api import Api


def test_get_books_returns_categorized_dict():
    api = Api()
    books = api.get_books()
    assert "Genesis" in books["Tora"]
    assert "Deuteronomy" in books["Tora"]
    assert "Isaiah" in books["Nevi'im"]
    assert "I Samuel" in books["Nevi'im"]
    assert "Esther" in books["Megillot"]


def test_get_book_labels_covers_every_book_with_both_scripts():
    api = Api()
    labels = api.get_book_labels()
    assert set(labels) == {b for books in api.get_books().values() for b in books}
    assert labels["Genesis"] == "Bereshit · בראשית"
    assert labels["I Samuel"] == "Shemuel Alef · שמואל א׳"
    assert labels["Song of Songs"] == "Shir haShirim · שיר השירים"


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
    (entry,) = result["diagrams"]
    assert entry["ref"] == "Bereshit 1:1"
    assert entry["diagram"]["units"]


def test_generate_cloze_gives_one_diagram_per_verse_greyed_for_the_card_setting(genesis_1_1, genesis_1_2):
    api = Api()
    api._current_verse_data = [
        {"book": "Genesis", "ch": 1, "vs": 1, "pointed": genesis_1_1, "plain": genesis_1_1},
        {"book": "Genesis", "ch": 1, "vs": 2, "pointed": genesis_1_2, "plain": genesis_1_2},
    ]
    result = api.generate_cloze(2, True)
    assert result["ok"] is True
    assert [d["ref"] for d in result["diagrams"]] == ["Bereshit 1:1", "Bereshit 1:2"]
    # At N = 2 some divisions aren't made by the cards; at N = 1 all are.
    boxes = lambda r: [b for d in r["diagrams"] for u in d["diagram"]["units"] for b in u["boxes"]]  # noqa: E731
    assert any(b["grey"] for b in boxes(result))
    assert not any(b["grey"] for b in boxes(api.generate_cloze(1, True)))


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
    """A tiny 2-verse fake Genesis chapter with real niqqud/ta'amim in its
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
    from tests.test_anki_connect.test_tagging import _cache_with_genesis

    api = Api()
    api._cache = _cache_with_genesis(tmp_path)  # the export computes tags: no network
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
    assert "Yesha'yahu 6:1" in content



def _seed_two_aliyah_parasha(api, tmp_path):
    """Pre-seed api._cache with a single parasha ("Bereshit") of two
    one-verse 'aliyyot, entirely within Genesis chapter 1 -- enough for
    export_aliyot_to_anki to run with zero network access.

    Card content comes from tikkun.io's scroll-line data (see
    ankipasuk.tikkun), not Sefaria's per-verse text, so both a fake
    parasha structure/text AND a fake tikkun table-of-contents/page are
    seeded here -- each of the two verses given its own scroll line, so
    each 'aliyya still produces exactly one card in these tests.

    verse-mode (the default) additionally needs a Sefaria word count per
    verse (see ankipasuk.verse_cards), fetched by chapter ref
    ("Genesis 1") rather than 'aliyya ref -- seeded here too (one word per
    verse, matching each verse's own one-word tikkun row below), so that
    lookup doesn't fall back to a real network fetch.
    """
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    from tests.test_anki_connect.test_tagging import _placeholder_genesis_parashot

    # The other parashiyyot are placeholders: the export computes each
    # card's qeriya tags, which pairs Sefaria's list with our table.
    parashot = _placeholder_genesis_parashot()
    parashot[0] = {"name": "Bereshit", "refs": ["Genesis 1:1", "Genesis 1:2"]}
    api._cache.set_parasha_structure("Genesis", parashot)
    # fetch_aliyot_in_range fetches text keyed by each 'aliyya's own ref
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


_SEFARIA_GENESIS_NAMES = [
    "Bereshit", "Noach", "Lech Lecha", "Vayera", "Chayei Sara", "Toldot",
    "Vayetzei", "Vayishlach", "Vayeshev", "Miketz", "Vayigash", "Vayechi",
]



def _seed_full_genesis(api, tmp_path):
    """Like _seed_two_aliyah_parasha, but with all twelve of Genesis's
    parashiyyot in Sefaria's spelling (so they pair with the bundled table
    by position), the two one-verse 'aliyyot belonging to "Chayei Sara"."""
    _seed_two_aliyah_parasha(api, tmp_path)
    api._cache.set_parasha_structure("Genesis", [
        {"name": name, "refs": ["Genesis 1:1", "Genesis 1:2"] if name == "Chayei Sara" else ["Genesis 1:31"]}
        for name in _SEFARIA_GENESIS_NAMES
    ])


def test_get_parashot_labels_use_our_names_but_values_stay_sefarias(tmp_path):
    api = Api()
    _seed_full_genesis(api, tmp_path)
    result = api.get_parashot("Genesis")
    assert result["names"] == _SEFARIA_GENESIS_NAMES
    assert result["labels"][:5] == ["Bereshit", "Noaḥ", "Lekh Lekha", "Vayyera", "Ḥayye Sara"]


def _seed_two_verses_sharing_a_row(api, tmp_path, monkeypatch):
    """A single 'aliyya covering two verses that share a physical scroll
    row: verse 1 is one word ("אאא") and verse 2 (three words: "בבב",
    "גגג", "דדד") starts on that same row, then continues across two more
    rows on its own. Exercises the "tail ends cohabiting a shared row"
    case verse-mode cards must handle -- row0 ("אאא בבב") holds verse 1's
    whole content AND the first word of verse 2's.

    verse-mode's word-alignment (ankipasuk.verse_cards) needs each verse's
    own Sefaria word count too, fetched (like ankipasuk.sefaria elsewhere)
    by chapter ref ("Genesis 1"), not by 'aliyya ref -- unrelated to (and a
    different cache key than) the aliyah-ref text fetch_aliyot_in_range
    itself uses to discover 'aliyya boundaries.
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


def _without_hover(html):
    """The answer side minus its per-word hover spans (verse_cards._words_html)."""
    return re.sub(r'<span class="w" data-p="[^"]*">([^<]*)</span>', r"\1", html)


def test_verse_cards_share_a_boundary_row(tmp_path, monkeypatch):
    api = Api()
    _seed_two_verses_sharing_a_row(api, tmp_path, monkeypatch)

    # Through the cache, as the 'ammud export builds them.
    cards = build_verse_cards("Genesis", [(1, 1), (1, 2)], api._cache, title="t")
    assert len(cards) == 2  # one card per verse, not per row
    back_rows = sorted(_without_hover(c["BackRows"]) for c in cards)
    # Verse 1's card tests only its own word ("אאא") -- verse 2's word on
    # that same row ("בבב") still occupies the row (a real sefer
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
    """Two one-verse 'aliyyot sharing a physical scroll row -- but unlike
    _seed_two_verses_sharing_a_row, the EXPORT only covers the SECOND
    'aliyya (verse 2), excluding verse 1 entirely. Verse 1's own word
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


def test_verse_cards_exclude_a_prior_verses_bleed_from_the_first_card(
    tmp_path, monkeypatch,
):
    api = Api()
    _seed_aliyah_starting_mid_row(api, tmp_path, monkeypatch)

    # Only verse 2 is asked for; verse 1 shares its first line.
    (card,) = build_verse_cards("Genesis", [(1, 2)], api._cache, title="t")
    back_rows = _without_hover(card["BackRows"])

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


def _seed_one_amud(api, tmp_path, monkeypatch):
    """Pre-seed api._cache with a single one-line 'ammud ('ammud 1, wholly
    within a fake single-chapter Genesis) -- enough for export_ammudim_to_anki
    to run with zero network access.

    verse-mode (the default) needs a Sefaria word count per verse too
    (see ankipasuk.verse_cards), fetched by chapter ref ("Genesis 1") --
    seeded here to match the tikkun row's own single word ("אאא"), so the
    word-alignment doesn't fall back to a real network fetch.
    """
    from tests.test_anki_connect.test_tagging import _placeholder_genesis_parashot

    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [1]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_parasha_structure("Genesis", _placeholder_genesis_parashot())  # for the qeriya tags
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["א"])
    api._cache.set_tikkun_toc({"1": {"1": {"1": {"p": 1, "l": 1}}}})
    api._cache.set_tikkun_page(1, [
        {"text": [["אאא"]], "verses": [{"chapter": 1, "verse": 1}],
         "aliyot": [{"standard": 1}], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")  # avoid a real network fetch


def test_export_ammudim_to_anki_pushes_notes_for_the_whole_amud(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)

    result = api.export_ammudim_to_anki([1])

    assert result["ok"] is True
    assert result["ammudim"] == [1]
    assert result["notes_added"] == 1
    assert result["decks"] == ["Ammudim::001"]
    assert all(n["deck"] == "Ammudim::001" for n in fake_anki.notes.values())


def test_export_ammudim_to_anki_tags_notes_as_an_amud(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)

    api.export_ammudim_to_anki([1])

    (note,) = fake_anki.notes.values()
    # Plus the pasuq's own qeriya tags (Bereshit 1:1 is read on Simḥat
    # Tora; the fixture's parashiyyot are placeholders, so no 'aliyya tag).
    assert note["tags"] == ["ammud::001", "holiday::simhat_tora::7"]


def test_exporting_the_same_ammud_twice_adds_nothing_the_second_time(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)
    first, again = api.export_ammudim_to_anki([1]), api.export_ammudim_to_anki([1])
    assert (first["notes_added"], first["already_in_anki"]) == (1, 0)
    assert (again["notes_added"], again["already_in_anki"]) == (0, 1)
    assert len(fake_anki.notes) == 1


def test_export_ammudim_to_anki_refreshes_css_on_an_already_existing_model(tmp_path, fake_anki, monkeypatch):
    """A note type created by an older version of this code (before a CSS
    change, e.g. adding the STAM font or setuma-gap styling) must not be
    stuck with stale styling forever -- ensure_model alone never updates
    an existing model, so the export must also refresh it."""
    from ankipasuk.anki_connect.operations import ensure_model
    from ankipasuk.lpcg import CARD_TEMPLATES, FIELD_NAMES

    ensure_model(LPCG_MODEL_NAME, FIELD_NAMES, "stale old css", CARD_TEMPLATES, url="http://localhost:8765")
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)
    api.export_ammudim_to_anki([1])
    assert fake_anki.models[LPCG_MODEL_NAME]["css"] != "stale old css"


def test_export_ammudim_to_anki_rejects_out_of_range_amud(tmp_path, fake_anki):
    api = Api()
    result = api.export_ammudim_to_anki([0])
    assert result["ok"] is False
    assert "error" in result


def test_cache_status_text_reflects_stats():
    api = Api()
    status = api.get_cache_status()
    assert "Cache:" in status
    assert "ref(s)" in status
    assert "book structure(s)" in status



# =============================================================
#  Haftarot
# =============================================================
def test_get_haftarot_lists_parashiyyot_then_special_shabbatot():
    groups = Api().get_haftarot()["groups"]
    assert [g["label"] for g in groups] == ["Parashiyyot", "Special Shabbatot"]
    assert len(groups[0]["items"]) == 54
    assert groups[0]["items"][0] == {"slug": "bereshit", "label": "Bereshit — Yesha'yahu 42:5–21"}


def test_fetch_haftara_fetches_every_part_in_order_and_marks_each_pasuq(monkeypatch):
    import ankipasuk.webgui.api as api_module

    calls = []

    def fake_range(book, c1, v1, c2, v2, cache, version):
        calls.append((book, c1, v1, c2, v2))
        return [{"book": book, "ch": c1, "vs": v1, "pointed": "x", "plain": "x"}]

    monkeypatch.setattr(api_module, "fetch_verse_range", fake_range)
    api = Api()
    result = api.fetch_haftara("mishpatim")
    assert result["ok"] is True
    assert calls == [("Jeremiah", 34, 8, 34, 22), ("Jeremiah", 33, 25, 33, 26)]
    marks = [(v["haftara"], v["haftara_pos"]) for v in result["verses"]]
    assert marks == [("mishpatim", 1), ("mishpatim", 2)]


def test_fetch_haftara_rejects_an_unknown_slug():
    assert Api().fetch_haftara("no_such")["ok"] is False


def test_suggest_cloze_deck_follows_what_was_fetched():
    api = Api()
    api._current_verse_data = [{"book": "Leviticus", "ch": 1, "vs": 1}]
    assert api.suggest_cloze_deck() == "Qeriya::3-Vayyiqra"
    api._current_verse_data = [{"book": "Isaiah", "ch": 42, "vs": 5, "haftara": "bereshit"}]
    assert api.suggest_cloze_deck() == "Qeriya::Haftarot"


# =============================================================
#  Cloze export straight to Anki
# =============================================================
CLOZE_FIELDS = ["Number", "Source", "Text", "Verse", "Previous", "Next", "Back Extra", "Opts", "Sound"]


def _api_with_haftara(tmp_path, genesis_1_1):
    from ankipasuk.cache import SefariaCache

    api = Api()
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._current_verse_data = [
        {"book": "Isaiah", "ch": 42, "vs": vs, "pointed": genesis_1_1,
         "plain": f"p{vs}", "haftara": "bereshit", "haftara_pos": vs - 4}
        for vs in (5, 6, 7)
    ]
    return api


def test_export_cloze_to_anki_adds_tagged_notes(tmp_path, genesis_1_1, fake_anki):
    fake_anki.models["Leyning (by pasuk)"] = {"fields": CLOZE_FIELDS, "css": "", "cardTemplates": []}
    api = _api_with_haftara(tmp_path, genesis_1_1)

    result = api.export_cloze_to_anki(2, True, "Qeriya::Haftarot", "Leyning (by pasuk)")
    assert result == {
        "ok": True, "notes_added": 3, "already_in_anki": 0, "failed": 0, "deck": "Qeriya::Haftarot",
    }
    added = list(fake_anki.notes.values())
    assert [n["fields"]["Source"] for n in added] == ["Yesha'yahu 42:5", "Yesha'yahu 42:6", "Yesha'yahu 42:7"]
    assert all(n["tags"] == ["haftara::bereshit"] and n["deck"] == "Qeriya::Haftarot" for n in added)
    assert all("Sound" not in n["fields"] for n in added)


def test_export_cloze_to_anki_never_touches_existing_notes(tmp_path, genesis_1_1, fake_anki):
    # 42:6 already has a note, with a recording: it must be skipped, not
    # duplicated or overwritten; the other two are added.
    fake_anki.models["Leyning (by pasuk)"] = {"fields": CLOZE_FIELDS, "css": "", "cardTemplates": []}
    existing = {"Number": "2", "Source": "Yesha'yahu 42:6", "Text": "mine", "Sound": "[sound:me.mp3]"}
    before = {"deck": "Elsewhere", "model": "Leyning (by pasuk)", "tags": ["x"], "fields": dict(existing)}
    fake_anki.notes[99] = {**before, "fields": dict(existing)}
    api = _api_with_haftara(tmp_path, genesis_1_1)

    result = api.export_cloze_to_anki(2, True, "Qeriya::Haftarot", "Leyning (by pasuk)")
    assert (result["notes_added"], result["already_in_anki"]) == (2, 1)
    assert fake_anki.notes[99] == before
    assert not any(action in ("updateNoteFields", "addTags", "removeTags") for action, _ in fake_anki.calls)

    # Running it again adds nothing.
    again = api.export_cloze_to_anki(2, True, "Qeriya::Haftarot", "Leyning (by pasuk)")
    assert (again["notes_added"], again["already_in_anki"]) == (0, 3)


def test_export_cloze_to_anki_rejects_an_unsuitable_note_type(tmp_path, genesis_1_1, fake_anki):
    fake_anki.models["Basic"] = {"fields": ["Front", "Back"], "css": "", "cardTemplates": []}
    result = _api_with_haftara(tmp_path, genesis_1_1).export_cloze_to_anki(2, True, "D", "Basic")
    assert result["ok"] is False and "Number, Source" in result["error"]


def test_get_cloze_note_types_lists_only_suitable_ones(fake_anki):
    fake_anki.models["Basic"] = {"fields": ["Front", "Back"], "css": "", "cardTemplates": []}
    fake_anki.models["Leyning (by pasuk)"] = {"fields": CLOZE_FIELDS, "css": "", "cardTemplates": []}
    result = Api().get_cloze_note_types()
    assert result["names"] == ["Leyning (by pasuk)"]
    assert result["selected"] == "Leyning (by pasuk)"


def test_export_csv_has_the_anki_header_and_a_tags_column(tmp_path, genesis_1_1):
    api = _api_with_haftara(tmp_path, genesis_1_1)
    out_path = tmp_path / "haftara.csv"

    class FakeWindow:
        def create_file_dialog(self, *a, **kw):
            return str(out_path)

    api._window = FakeWindow()
    assert api.export_csv(2, True)["ok"] is True
    lines = out_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[:2] == ["#separator:tab", "#tags column:9"]
    first = lines[2].split("\t")
    assert first[:2] == ["1", "Yesha'yahu 42:5"] and first[-1] == "haftara::bereshit"


# =============================================================
#  No duplicates, and the deck is created
# =============================================================
def test_an_ammud_export_skips_a_pasuq_already_exported_as_an_aliyya(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)
    # An old-style note for Bereshit 1:1 from an earlier version: old title,
    # old tag, different HTML -- still recognised as that pasuq's card.
    fake_anki.models["Ankipasuk Aliyah"] = {"fields": list(LPCG_FIELD_NAMES), "css": "", "cardTemplates": []}
    fake_anki.notes[50] = {
        "deck": "Amudim::001", "model": "Ankipasuk Aliyah", "tags": ["amud::001"],
        "fields": {"Title": "Bereshit Amud 1", "Sequence": "1", "FrontRows": "<old/>", "Line": ""},
    }
    result = api.export_ammudim_to_anki([1])
    assert (result["notes_added"], result["already_in_anki"]) == (0, 1)
    assert fake_anki.notes[50]["fields"]["FrontRows"] == "<old/>"  # untouched


def test_both_exports_create_a_missing_deck(tmp_path, genesis_1_1, fake_anki, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)
    api.export_ammudim_to_anki([1])
    fake_anki.models["Leyning (by pasuk)"] = {"fields": CLOZE_FIELDS, "css": "", "cardTemplates": []}
    cloze_api = _api_with_haftara(tmp_path, genesis_1_1)
    cloze_api.export_cloze_to_anki(2, True, "New::Haftarot", "Leyning (by pasuk)")
    assert {"Ammudim::001", "New::Haftarot"} <= fake_anki.decks


def test_tiqqun_cards_can_be_saved_as_csv(tmp_path, monkeypatch):
    api = Api()
    _seed_one_amud(api, tmp_path, monkeypatch)
    out_path = tmp_path / "tiqqun.csv"

    class FakeWindow:
        def create_file_dialog(self, *a, **kw):
            return str(out_path)

    api._window = FakeWindow()
    result = api.export_ammudim_csv([1])
    assert result == {"ok": True, "count": 1, "path": str(out_path)}
    text = out_path.read_text(encoding="utf-8-sig")
    assert "#notetype:Ankipasuk Aliyah\n#tags column:11\n#deck column:12\n" in text
    assert text.rstrip().endswith("ammud::001 holiday::simhat_tora::7\tAmmudim::001")


def _seed_two_ammudim(api, tmp_path, monkeypatch):
    """'Ammudim 1 and 2 of a fake two-verse Genesis, one pasuq each."""
    from tests.test_anki_connect.test_tagging import _placeholder_genesis_parashot

    monkeypatch.setattr("ankipasuk.tikkun.TORAH_VERSE_COUNTS", {"Genesis": [2]})
    api._cache = SefariaCache(cache_dir=tmp_path)
    api._settings = Settings(cache_dir=tmp_path)
    api._cache.set_parasha_structure("Genesis", _placeholder_genesis_parashot())
    api._cache.set_text("Genesis 1", POINTED_VERSION, ["א", "ב"])
    api._cache.set_tikkun_toc({"1": {"1": {"1": {"p": 1, "l": 1}, "2": {"p": 2, "l": 1}}}})
    api._cache.set_tikkun_page(1, [
        {"text": [["אאא"]], "verses": [{"chapter": 1, "verse": 1}], "aliyot": [], "isPetucha": False},
    ])
    api._cache.set_tikkun_page(2, [
        {"text": [["בבב"]], "verses": [{"chapter": 1, "verse": 2}], "aliyot": [], "isPetucha": False},
    ])
    api._cache.set_tikkun_font("ZmFrZS1mb250")


def test_several_ammudim_each_go_to_their_own_deck_once(tmp_path, fake_anki, monkeypatch):
    api = Api()
    _seed_two_ammudim(api, tmp_path, monkeypatch)
    # Overlapping ranges, out of order: each 'ammud still counts once.
    result = api.export_ammudim_to_anki([2, 1, 2, 1])
    assert result["ok"] is True, result
    assert result["ammudim"] == [1, 2]
    assert result["decks"] == ["Ammudim::001", "Ammudim::002"]
    assert result["notes_added"] == 2
    assert sorted(n["deck"] for n in fake_anki.notes.values()) == ["Ammudim::001", "Ammudim::002"]
    assert {"Ammudim::001", "Ammudim::002"} <= fake_anki.decks


def test_one_csv_holds_several_ammudim_with_their_decks(tmp_path, monkeypatch):
    api = Api()
    _seed_two_ammudim(api, tmp_path, monkeypatch)
    out_path = tmp_path / "t.csv"

    class FakeWindow:
        def create_file_dialog(self, *a, save_filename=None, **kw):
            assert save_filename == "tiqqun_ammudim_001-002.csv"
            return str(out_path)

    api._window = FakeWindow()
    assert api.export_ammudim_csv([1, 2])["count"] == 2
    rows = [line.split("\t")[-1] for line in out_path.read_text(encoding="utf-8-sig").splitlines()
            if not line.startswith("#")]
    assert rows == ["Ammudim::001", "Ammudim::002"]


def test_no_ammudim_is_an_error(tmp_path):
    assert Api().export_ammudim_to_anki([])["ok"] is False


def test_anki_status_says_whether_anki_answers(fake_anki, monkeypatch):
    assert Api().anki_status() == {"ok": True}

    import ankipasuk.anki_connect.client as client_module
    from ankipasuk.anki_connect.client import AnkiConnectError

    def refused(action, **_kw):
        raise AnkiConnectError("Connection refused")

    monkeypatch.setattr(client_module, "invoke", refused)
    assert Api().anki_status()["ok"] is False


def test_preview_ammud_is_the_page_export_or_its_error(monkeypatch):
    import ankipasuk.webgui.api as api_module

    monkeypatch.setattr(api_module, "ammud_pages_html", lambda ammudim, cache: f"<html>{ammudim}</html>")
    assert Api().preview_ammud(7) == {"ok": True, "html": "<html>[7]</html>"}

    def offline(ammudim, cache):
        raise OSError("no network")

    monkeypatch.setattr(api_module, "ammud_pages_html", offline)
    assert Api().preview_ammud(7) == {"ok": False, "error": "no network"}


_ALIYOT = {
    ("Noach", 1): "Genesis 6:9-6:22", ("Noach", 7): "Genesis 11:10-11:32",
    ("Lech-Lecha", 2): "Genesis 12:14-13:4", ("Vayera", 3): "Genesis 18:20",
}


def test_a_parasha_span_runs_from_one_aliyyas_start_to_anothers_end(monkeypatch):
    import ankipasuk.webgui.api as api_module

    monkeypatch.setattr(api_module, "get_aliyah_ref", lambda book, p, n, cache: _ALIYOT[(p, n)])
    api = Api()
    assert api.get_parasha_span("Genesis", "Noach", 1, "Lech-Lecha", 2) == {
        "ok": True, "start": [6, 9], "end": [13, 4]}
    assert api.get_parasha_span("Genesis", "Noach", 7, "Noach", 7) == {
        "ok": True, "start": [11, 10], "end": [11, 32]}
    # An 'aliyya of a single pasuq ends where it starts.
    assert api.get_parasha_span("Genesis", "Vayera", 3, "Vayera", 3)["end"] == [18, 20]
    assert api.get_parasha_span("Genesis", "Lech-Lecha", 2, "Noach", 1)["ok"] is False


def test_export_diagrams_saves_the_drawn_page_as_html(tmp_path, monkeypatch):
    import ankipasuk.diagram_pages as diagram_pages_module

    monkeypatch.setattr(diagram_pages_module, "get_font_base64", lambda cache: "Rk9OVA==")
    out_path = tmp_path / "d.html"

    class FakeWindow:
        def create_file_dialog(self, *a, save_filename=None, **kw):
            assert save_filename == "Bereshit_1_1_8.html"
            return str(out_path)

    api = Api()
    api._window = FakeWindow()
    result = api.export_diagrams('<div class="dg-pasuq">x</div>', "html", "Bereshit 1:1–8", "8 pesuqim")
    assert result == {"ok": True, "path": str(out_path), "pages": None}
    html = out_path.read_text(encoding="utf-8")
    assert '<div class="dg-pasuq">x</div>' in html and "<h1>Bereshit 1:1–8</h1>" in html
    assert "data:font/ttf;base64,Rk9OVA==" in html
    assert api.export_diagrams("", "docx", "t", "s")["ok"] is False
