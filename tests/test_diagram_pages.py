"""Tests for ankipasuk.diagram_pages: the diagram view as a document."""

import pytest

from ankipasuk import diagram_pages as dp
from ankipasuk.cache import SefariaCache

BODY = '<div class="dg-pasuq"><div class="dg-ref">Bereshit 1:1</div></div>'


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "get_font_base64", lambda cache: "Rk9OVA==")
    return SefariaCache(cache_dir=tmp_path)


def test_the_page_has_the_diagrams_the_font_and_the_app_s_own_diagram_styles(cache):
    html = dp.diagrams_html(BODY, "Bereshit <1>", "1 pasuq", cache)
    assert BODY in html
    assert "<h1>Bereshit &lt;1&gt;</h1>" in html
    assert "data:font/ttf;base64,Rk9OVA==" in html
    assert ".dg-r1 .dg-line" in html  # diagram.css, embedded
    assert "break-inside: avoid" in html  # a pasuq isn't split across pages


def test_the_diagrams_are_drawn_at_the_width_between_the_margins():
    # A4 (210mm) less two 15mm margins, at 96px to the inch.
    assert dp.content_width_px() == 680
    assert dp.content_width_px({"orientation": "landscape", "margin_mm": 10}) == int(277 / 25.4 * 96)
    assert dp.content_width_px({"paper": "Letter", "margin_mm": 20}) == int(175.9 / 25.4 * 96)


def test_page_options_keep_only_what_can_be_laid_out():
    o = dp.page_options({"paper": "A3", "orientation": "sideways", "margin_mm": 500, "spacing_px": "x",
                         "references": 0, "bw": 1})
    assert (o["paper"], o["orientation"], o["margin_mm"], o["spacing_px"]) == ("A4", "portrait", 40, 8)
    assert (o["references"], o["bw"], o["separators"]) == (False, True, True)


def test_the_options_shape_the_page(cache):
    plain = dp.diagrams_html(BODY, "t", "s", cache, {
        "orientation": "landscape", "margin_mm": 10, "spacing_px": 20,
        "references": False, "separators": False, "header": False,
    })
    assert "size: 297mm 210mm; margin: 10mm" in plain
    assert "padding: 20px 0" in plain
    assert ".dg-ref { display: none; }" in plain and ".dg-pasuq { border-bottom: none; }" in plain
    assert "<h1>" not in plain
    bw = dp.diagrams_html(BODY, "t", "s", cache, {"bw": True})
    assert "a card's division" in bw and '<body class="dg-bw">' in bw
    assert "not a card" not in dp.diagrams_html(BODY, "t", "s", cache, {"grey": False})


def test_a_long_page_is_cut_between_pesuqim_never_inside_one():
    body = "".join(f'<div class="dg-pasuq">{n}</div>' for n in range(5))
    parts = dp.chunks(body, 2)
    assert parts == [
        '<div class="dg-pasuq">0</div><div class="dg-pasuq">1</div>',
        '<div class="dg-pasuq">2</div><div class="dg-pasuq">3</div>',
        '<div class="dg-pasuq">4</div>',
    ]
    assert "".join(parts) == body


def test_later_chunks_have_no_title_and_number_on(cache):
    later = dp.diagram_document(BODY, "Bereshit", "s", "f.ttf", header=False, first_page=8)
    assert "<h1>" not in later
    assert "counter-reset: page 8" in later


def test_pdf_without_weasyprint_says_how_to_get_it(cache, monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def no_weasyprint(name, *a, **kw):
        if name == "weasyprint":
            raise ImportError(name)
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_weasyprint)
    with pytest.raises(RuntimeError, match="WeasyPrint"):
        dp.write_pdf(BODY, "t", "s", cache, tmp_path / "x.pdf")
