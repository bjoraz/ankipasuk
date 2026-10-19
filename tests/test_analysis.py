"""Tests for ankipasuk.analysis.cloze_breakdown -- the per-cloze
explanation behind the app's analysis view. The one property everything
rests on: its cloze numbers are the ones the exported markup uses."""

import pytest

from ankipasuk.analysis import cloze_breakdown
from ankipasuk.cloze import verse_to_nested_cloze
from ankipasuk.config import LEGARMEH_NAME, TROPE_UNICODE
from ankipasuk.text_processing import strip_vowels_and_trope

ATNAH = TROPE_UNICODE["֑"][0]


def _breakdown(pasuq, max_leaf_disj, start=1):
    markup, last, tree, _tok, _units = verse_to_nested_cloze(pasuq, start, max_leaf_disj)
    return markup, last, cloze_breakdown(tree, start)


@pytest.mark.parametrize("fixture", ["genesis_1_1", "genesis_1_2", "munach_legarmeh_verse"])
@pytest.mark.parametrize("max_leaf_disj", [1, 2, 3])
@pytest.mark.parametrize("start", [1, 7])
def test_numbers_match_the_exported_markup(request, fixture, max_leaf_disj, start):
    pasuq = request.getfixturevalue(fixture)
    markup, last, rows = _breakdown(pasuq, max_leaf_disj, start)

    assert [r["n"] for r in rows] == list(range(start, last + 1))
    for row in rows:
        if row["kind"] == "clause":
            # A leaf's markup is exactly {{cN::words::hint}}.
            assert f"{{{{c{row['n']}::{row['text']}::" in markup
        # Every cloze, leaf or merged, closes with its own hint.
        assert f"{{{{c{row['n']}::" in markup
        assert f"::{strip_vowels_and_trope(row['text'])}}}}}" in markup


def test_the_last_cloze_is_the_whole_pasuq(genesis_1_2):
    _markup, _last, rows = _breakdown(genesis_1_2, 1)
    assert rows[-1]["depth"] == 0
    assert rows[-1]["text"] == genesis_1_2
    assert [r for r in rows if r["depth"] == 0] == [rows[-1]]


def test_the_pasuq_splits_after_atnah(genesis_1_1):
    _markup, _last, rows = _breakdown(genesis_1_1, 1)
    whole = rows[-1]
    assert whole["kind"] == "split"
    assert whole["split_after"] == {"word": "אֱלֹהִים֑", "name": ATNAH, "rank": 1}


def test_each_clause_names_the_taam_it_ends_on(genesis_1_1):
    _markup, _last, rows = _breakdown(genesis_1_1, 1)
    clauses = [r for r in rows if r["kind"] == "clause"]
    assert " ".join(r["text"] for r in clauses) == genesis_1_1
    assert all(r["ends_on"]["rank"] in (1, 2, 3, 4) for r in clauses)
    assert clauses[-1]["ends_on"]["rank"] == 1  # sof pasuq


def test_paseq_shows_as_paseq_at_rank_4(munach_legarmeh_verse):
    _markup, _last, rows = _breakdown(munach_legarmeh_verse, 1)
    names = {(r["ends_on"]["name"], r["ends_on"]["rank"]) for r in rows if r["kind"] == "clause"}
    assert (LEGARMEH_NAME, 4) in names


def test_an_unsplit_pasuq_is_a_single_clause(genesis_1_1):
    _markup, last, rows = _breakdown(genesis_1_1, 100)
    assert len(rows) == 1
    assert rows[0] == {
        "n": 1, "depth": 0, "kind": "clause", "text": genesis_1_1,
        "ends_on": rows[0]["ends_on"],
    }
    assert last == 1


def test_tere_qadmin_is_labeled_as_such_and_ranked_as_qadma():
    # Bereshit 1:2's first half, as in the README's worked example:
    # תֹ֨הוּ֙ carries qadma twice (U+05A8 and U+0599).
    pasuq = "וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֨הוּ֙ וָבֹ֔הוּ וְחֹ֖שֶׁךְ עַל־פְּנֵ֣י תְה֑וֹם"
    _markup, _last, rows = _breakdown(pasuq, 1)
    ends = [r["ends_on"] for r in rows if r["kind"] == "clause"]
    assert ends[1] == {"word": "תֹ֨הוּ֙", "name": "Tere qadmin", "rank": TROPE_UNICODE["\u0599"][1]}
    assert ends[0]["name"] == TROPE_UNICODE["\u0597"][0]  # ravia', unaffected
