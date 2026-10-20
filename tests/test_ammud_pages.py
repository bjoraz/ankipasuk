"""Tests for ankipasuk.ammud_pages: 'ammudim as printable pages."""

import pytest

import ankipasuk.ammud_pages as ap
from ankipasuk.cache import SefariaCache


@pytest.fixture
def two_ammudim(monkeypatch, tmp_path):
    lines = {1: [{"html": "<div>בראשית</div>", "is_petucha": False, "char_count": 6}],
             2: [{"html": "<div>ויכלו</div>", "is_petucha": True, "char_count": 5}]}
    monkeypatch.setattr(ap, "get_amud_lines", lambda n, cache, keep_blank=False: lines[n])
    monkeypatch.setattr(ap, "get_book_verses_on_amud", lambda n, cache: [("Genesis", n, 1)])
    monkeypatch.setattr(ap, "get_font_base64", lambda cache: "Rk9OVA==")
    return SefariaCache(cache_dir=tmp_path)


def test_each_ammud_is_its_own_page_once_and_in_order(two_ammudim):
    html = ap.ammud_pages_html([2, 1, 2], two_ammudim)
    assert html.count('<section class="ammud">') == 2
    assert html.index("'Ammud 1") < html.index("'Ammud 2")
    assert "break-after: page" in html
    assert "<title>'Ammudim 1–2</title>" in html


def test_the_font_is_embedded_and_no_css_variables_are_left(two_ammudim):
    html = ap.ammud_pages_html([1], two_ammudim)
    assert 'url("data:font/ttf;base64,Rk9OVA==")' in html
    assert "var(" not in html  # WeasyPrint can't evaluate them inside calc()


def test_a_caption_names_both_books_where_one_ends_and_the_next_begins(monkeypatch, tmp_path):
    monkeypatch.setattr(ap, "get_book_verses_on_amud", lambda n, cache: [
        ("Exodus", 40, 38), ("Leviticus", 1, 1),
    ])
    assert ap.caption(111, SefariaCache(cache_dir=tmp_path)) == "Shemot–Vayyiqra — 'Ammud 111"


def test_out_of_range_or_empty_choices_are_refused(two_ammudim):
    with pytest.raises(ValueError):
        ap.ammud_pages_html([], two_ammudim)
    with pytest.raises(ValueError):
        ap.ammud_pages_html([0], two_ammudim)


def test_pdf_without_weasyprint_says_how_to_get_it(two_ammudim, monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def no_weasyprint(name, *a, **kw):
        if name == "weasyprint":
            raise ImportError("no module")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_weasyprint)
    with pytest.raises(RuntimeError, match=r"ankipasuk\[pdf\]"):
        ap.write_pdf([1], two_ammudim, tmp_path / "x.pdf")


def test_pdf_has_one_page_per_ammud(two_ammudim, monkeypatch, tmp_path):
    pytest.importorskip("weasyprint")
    # A real font isn't needed to count pages; skip loading the fake one.
    monkeypatch.setattr(ap, "get_font_base64", lambda cache: "")
    out = tmp_path / "pages.pdf"
    assert ap.write_pdf([1, 2], two_ammudim, out) == 2
    assert out.read_bytes()[:4] == b"%PDF"
