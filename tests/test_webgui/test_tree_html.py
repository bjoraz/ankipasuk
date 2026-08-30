"""Tests for ankipasuk.webgui.tree_html.tree_to_html.

The key property this must have -- since it's the actual fix for the Tk
RTL bugs -- is that it emits plain HTML in natural (logical) word order
with no manual reversal or embedding characters, relying entirely on the
browser's native dir="rtl" handling.
"""

from html import escape

from ankipasuk.cloze import verse_to_nested_cloze
from ankipasuk.webgui.tree_html import tree_to_html


def test_words_appear_in_natural_logical_order(genesis_1_1):
    """Regression test for the whole point of this module: words must NOT
    be reversed in the emitted HTML (unlike the old Tk render_colored_tree,
    which had to reverse them to work around Tk's bidi limitations) --
    the browser's dir="rtl" handles display order, so the HTML source
    order should just be the natural reading order."""
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=2)
    html = tree_to_html(tree)

    first_word = escape("בְּרֵאשִׁית")
    second_word = escape("בָּרָא\u0597")  # with its Revia mark, as verse_to_nested_cloze produces it
    assert html.index(first_word) < html.index(second_word)


def test_leaf_produces_one_viz_line_div(genesis_1_1):
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=100)
    html = tree_to_html(tree)
    assert html.count('class="viz-line"') == 1


def test_split_tree_produces_one_div_per_leaf(genesis_1_2):
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    from ankipasuk.cloze import tree_leaf_count

    html = tree_to_html(tree)
    assert html.count('class="viz-line"') == tree_leaf_count(tree)


def test_conjunctive_words_get_conj_class(genesis_1_1):
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=100)
    html = tree_to_html(tree)
    assert 'class="conj"' in html  # "בְּרֵאשִׁית" has no disjunctive trope


def test_html_is_escaped_safely():
    # A leaf is a list of units; construct one directly to check escaping
    # without depending on real trope data containing special characters.
    fake_leaf = [{"level": 3, "subs": [{"text": "<script>", "level": 3}]}]
    html = tree_to_html(fake_leaf)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_depth_determines_background_color(genesis_1_2):
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    html = tree_to_html(tree)
    # At least two distinct depth colors should appear for a verse that
    # actually splits into multiple nesting levels.
    from ankipasuk.config import UNIT_COLORS

    colors_present = [c for c in UNIT_COLORS if c in html]
    assert len(colors_present) >= 2


def test_indented_leaves_get_a_separate_guide_strip(genesis_1_2):
    """Regression test: the indent must be a separate element with its
    own GUIDE_BG background, distinct from the leaf's own depth color --
    not padding within the depth-colored element itself, which loses the
    original Tk visualization's two-tone (gray guide + colored content)
    treatment entirely."""
    from ankipasuk.config import GUIDE_BG

    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    html = tree_to_html(tree)
    assert 'class="viz-guide"' in html
    assert GUIDE_BG in html


def test_guide_comes_after_line_in_dom_order_so_it_renders_on_the_right(genesis_1_2):
    """Regression test: in a default (LTR) flex row, the *first* child
    renders on the left and the *second* on the right. The guide must be
    the second child (after viz-line) so it renders on the right -- the
    side Hebrew reading starts from -- so deeper nesting indents inward
    from the right, mirroring how indentation grows from the left in an
    LTR layout. Guide-before-line would put it on the wrong side."""
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    html = tree_to_html(tree)
    for row in html.split('<div class="viz-row">')[1:]:
        if 'class="viz-guide"' in row:
            assert row.index('class="viz-line"') < row.index('class="viz-guide"')


def test_unindented_leaf_has_no_guide_strip(genesis_1_1):
    """A leaf at indent 0 (e.g. an unsplit verse) shouldn't render an
    empty/zero-width guide div at all."""
    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_1, max_leaf_disj=100)
    html = tree_to_html(tree)
    assert 'class="viz-guide"' not in html


def test_each_row_is_wrapped_in_viz_row(genesis_1_2):
    from ankipasuk.cloze import tree_leaf_count

    _cl, _last, tree, _tok, _units = verse_to_nested_cloze(genesis_1_2, max_leaf_disj=1)
    html = tree_to_html(tree)
    assert html.count('class="viz-row"') == tree_leaf_count(tree)


# =============================================================
#  Half-indent for sibling leaf pairs
# =============================================================
def _leaf(text: str, level: int = 1):
    """A minimal, hand-built leaf (list of one unit) for precise,
    synthetic tree construction -- independent of real trope parsing, so
    the exact tree shape under test is fully controlled."""
    return [{"level": level, "subs": [{"text": text, "level": level}]}]


def _guide_widths(html: str) -> list[float]:
    """Extract each row's guide width in px, in row order (0 for a row
    with no guide at all, i.e. indent 0)."""
    import re

    widths = []
    for row in html.split('<div class="viz-row">')[1:]:
        m = re.search(r'class="viz-guide" style="width:([\d.]+)px', row)
        widths.append(float(m.group(1)) if m else 0.0)
    return widths


def test_sibling_leaf_pair_first_leaf_gets_half_indent_bump():
    """A node whose BOTH children are leaves (no further nesting on
    either side) is a genuine sibling leaf pair -- its first (upper)
    leaf should render with an extra half indent step compared to what
    it would get without the bump, while the second (lower) leaf is
    unaffected."""
    tree = {"left": _leaf("first"), "right": _leaf("second")}
    widths = _guide_widths(tree_to_html(tree))
    assert widths == [21.0, 14.0]
    # The relationship that actually matters, independent of the exact
    # absolute values above: the first leaf of a genuine pair is always
    # exactly half an indent step (7px = 0.5 * 14) wider than the second.
    assert widths[0] - widths[1] == 7.0


def test_leaf_paired_with_further_nesting_gets_no_half_indent():
    """The user's explicit clarification: a leaf on one side and further
    nesting (not a leaf) on the other side does NOT count as a sibling
    leaf pair -- no half-indent bump applies in that case."""
    tree = {
        "left": _leaf("first"),
        "right": {"left": _leaf("second"), "right": _leaf("third")},
    }
    widths = _guide_widths(tree_to_html(tree))
    assert widths == [14.0, 35.0, 28.0]
    # "first" (root's left, paired with further nesting on the right) is
    # NOT bumped -- confirmed by there being no other leaf at the same
    # nominal indent level to compare it to changing by 7px.
    # "second" and "third", one level down, ARE a genuine sibling leaf
    # pair -- "second" (first/upper) is exactly half a step ahead of
    # "third" (second/lower), same relationship as the simple pair case.
    assert widths[1] - widths[2] == 7.0


def test_half_indent_does_not_apply_transitively():
    """A leaf whose sibling is itself a leaf gets the bump; going one
    more level up the tree, that same leaf's *grandparent* pairing
    (leaf vs. further-nested subtree) must not also apply a bump --
    only the immediate sibling-leaf-pair relationship matters."""
    # Root: left=leaf, right=deeper subtree containing its own sibling
    # leaf pair three levels down.
    tree = {
        "left": _leaf("A"),
        "right": {
            "left": {"left": _leaf("B"), "right": _leaf("C")},
            "right": _leaf("D"),
        },
    }
    widths = _guide_widths(tree_to_html(tree))
    assert widths == [14.0, 49.0, 42.0, 28.0]
    # A: root.left is a leaf, root.right is a dict -> not a sibling pair
    # at the root level -> no bump (nothing to compare against here, but
    # confirmed by the exact value matching plain indent_level 1 = 14px,
    # not 21px which is what a bump at that level would produce).
    # B and C: a genuine sibling leaf pair one level inside root.right ->
    # B (first/upper) is exactly half a step ahead of C (second/lower).
    assert widths[1] - widths[2] == 7.0
    # D: paired with a dict (not C directly) at its own level -> not a
    # sibling leaf pair -> no bump, and critically not "transitively"
    # bumped just because ITS subtree happens to contain a bumped leaf.
