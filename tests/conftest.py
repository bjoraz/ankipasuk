"""Shared fixtures: small, hand-built pointed verses using real ta'amim
(combining marks), so tests exercise the actual parsing logic without
depending on network access to Sefaria."""

import pytest

SOF_PASUQ = "\u05C3"
ETNACHTA = "\u0591"
TIFCHA = "\u0596"
REVIA = "\u0597"
ZAKEF_KATAN = "\u0594"
MUNACH = "\u05A3"
PASEQ = "\u05C0"


def word(base: str, *marks: str) -> str:
    return base + "".join(marks)


@pytest.fixture
def genesis_1_1() -> str:
    """A short verse: 7 words, ending Sof pasuq, with an atnaḥ split."""
    return " ".join([
        word("בְּרֵאשִׁית"),
        word("בָּרָא", REVIA),
        word("אֱלֹהִים", ETNACHTA),
        word("אֵת", TIFCHA),
        word("הַשָּׁמַיִם", TIFCHA),
        word("וְאֵת", TIFCHA),
        word("הָאָרֶץ", SOF_PASUQ),
    ])


@pytest.fixture
def genesis_1_2() -> str:
    """A longer verse: 12 words, multiple disjunctive groups."""
    return " ".join([
        word("וְהָאָרֶץ", REVIA),
        word("הָיְתָה", TIFCHA),
        word("תֹהוּ", REVIA),
        word("וָבֹהוּ", REVIA),
        word("וְחֹשֶׁךְ", TIFCHA),
        word("עַל", REVIA),
        word("פְּנֵי", REVIA),
        word("תְהוֹם", ETNACHTA),
        word("וְרוּחַ", REVIA),
        word("אֱלֹהִים", REVIA),
        word("מְרַחֶפֶת", TIFCHA),
        word("עַל", SOF_PASUQ),
    ])


@pytest.fixture
def munach_legarmeh_verse() -> str:
    """A word carrying shofar holekh (Unicode MUNAH) immediately followed by a
    pesiq, with the next mafsiq at ravia's level -- this should be read as
    paseq (Ashkenazi munach legarmeh, level 4)."""
    return " ".join([
        word("אָב", MUNACH),
        word("גָּדוֹל", PASEQ),
        word("מְאֹד", REVIA),
        word("שָׁלוֹם", SOF_PASUQ),
    ])
