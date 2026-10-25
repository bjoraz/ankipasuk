# Semantic domains

Each word's sense and its semantic domains, from the open release of the
**Semantic Dictionary of Biblical Hebrew** (SDBH): the *UBS Dictionary of
Biblical Hebrew*, version 0.9.4, © United Bible Societies 2023, adapted
from SDBH © 2000–2023 United Bible Societies, under the
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license
([ubsicap/ubs-open-license](https://github.com/ubsicap/ubs-open-license)).
They're lined up with the Open Scriptures Hebrew Bible's words (OSHB, as
for the shorashim), so every word the app shows can have its sense.

The data is made by `scripts/build_semantics.py`
(`src/ankipasuk/semantics_build.py`) and read by `src/ankipasuk/semantics.py`.
The app shows it in the Text view's **Fields** pane ([below](#in-the-app),
and the README's Semantic fields section).

## What SDBH gives

- **Senses.** Each dictionary entry has one or more *meanings*, each with
  English glosses, a short definition, and one or more lexical domains.
  Each place a word is used in is assigned to one of its senses: רוּחַ in
  Bereshit 1:2 is both "Spirit" (Beings › Deities) and "breeze, wind"
  (Natural World › Substances › Air), the two readings of רוח אלהים.
- **Lexical domains**, a tree of 415, three digits a level: `001` Objects,
  `001001` Beings, `001001001` Deities. It has 3 domains at level 1, 9 at
  level 2, 50 at level 3, 312 at level 4 and 41 at level 5. The tree sorts
  words by the kind of meaning, not by theme: בְּרִית is Events ›
  Perception › Sensation › Utter › Vow.
- Of the places with a sense, 57% are Events (actions and states), 23%
  Objects, 20% Reference (names, pronouns, words that point).
- **How deep a word is filed** varies: 65% of places at level 4, 24% at
  level 3, 8% at level 5, and 4% at levels 1–2. Some branches have no
  lower levels (Deities, Land, Heaven, names), and some common words are
  filed at a general node (אִישׁ, אִשָּׁה, יֶלֶד: Beings › People).
- **More than one domain:** 5% of the places have a sense with two or more
  domains (מַיִם: Liquids, and Waterbodies).
- SDBH also has *contextual* domains (themes), but the open release
  assigns no sense to any of them, so the app has none.

## Lining SDBH up with OSHB

SDBH gives each place as `BBBCCCVVVSSWWW`: the book (in the order of an
English Bible), chapter and verse (the Hebrew numbering), a segment
(unused for Hebrew), and the word, in even numbers. Its words are OSHB's
*segments*, counted as OSHB writes them:

- a prefix is a word of its own: וְהָאָרֶץ (OSHB `c/d/776`) is three words,
  ו, ה, אֶרֶץ;
- so is an article hidden in a preposition: בָּאָרֶץ (`b/776`, morphology
  `Rd`) is three too;
- a suffix isn't: אִתָּךְ is one;
- a ketiv and its qere are two.

Each pasuq's places are lined up with OSHB's segments in order
(`semantics_build.line_up`). A place goes where its number says, unless
a word before it was split one way here and another there, which shifts
what follows: SDBH keeps לָמָּה whole, OSHB writes `l/4100`. A place
*matches* its segment if the segment's Strong's number is one of the
entry's, or a prefix is the entry's letter. Each word then has the senses
of its own segment, not its prefixes'.

Of SDBH's 289,968 places (one a word, however many senses):

| | Places | |
|---|---|---|
| Matched their word | 288,737 | 99.58% |
| Placed where their neighbours put them, the Strong's numbers differing | 1,155 | 0.40% |
| Left out (no room) | 76 | 0.03% |

The numbers that differ are words the two dictionaries file apart:
חִזְקִיָּהוּ (3169, 2396), מִצְרַיִם and מִצְרִי (4714, 4713), טוֹב (2895,
2896), בְּאֵר שֶׁבַע (7651, 884).

## Coverage

Of OSHB's 306,785 words in the whole Tanakh, 271,509 (88.5%) have a
sense. SDBH is still being written (about 90% of the Tanakh's words, its
editors say), and what's missing is mostly function words:

| Words (by the shorashim's kinds) | With a sense |
|---|---|
| Words from a root | 99.9% (186,079 of 186,293) |
| Other words | 99.5% |
| Names | 98.0% (some two-word names, like בית אל, have it on one word) |
| Particles | 59.7%: none yet for עַל, אֶל, לְ with a suffix, כִּי, מִן, עִם, הִנֵּה, אַיִן, כֹּה, עוֹד |
| כֹּל | 1.2%: not done yet |

1,403 words have two senses in one place, like רוּחַ and אֱלֹהִים in
Bereshit 1:2.

## In the app

A passage's **fields** (`semantics.passage`) are its words' domains, all
brought to one level of the tree: 4 by default, 3 or 5 in the settings.

- A deeper domain is cut back to the level: Events › Description ›
  Attribute › Shine stays Shine at level 4, and is Attribute at level 3.
- A shallower one stands for itself, its last level repeated: Objects ›
  Natural World › Heaven is Heaven › Heaven at level 4. It's a field of its
  own, apart from any domain under it: a word filed at People isn't in
  People › Relatives.
- A word has a field for each of its senses' domains, so some have two
  (מַיִם: Liquids and Waterbodies), shown striped when both are coloured.
- Reference (names, pronouns, pointing words) is left out unless asked
  for, and so are particles (the shorashim's), each by a switch in the
  pane. A word keeps its other senses' fields: אֱלֹהִים in Bereshit 1:2 is
  also "mighty" (Events › Description › Modification › Intense).

The fields also make frames: a rare field found only at the two ends of a
Masoretic unit, in different words at each, is a candidate frame in the
Phrases pane's Frames tab (`docs/phrases.md`, Frames).

**Key fields** are ranked as the shorashim's key words: Dunning's
log-likelihood (G²) of the field's words here against the rest of the
Tanakh's, counted the same way (the same level, the same things left
out); its *ratio* is how many times its rate in the Tanakh it's used here.

## The data

`src/ankipasuk/data/semantics/`, shared under CC BY-SA 4.0 (see
`THIRD_PARTY_NOTICES.md`):

- `senses.json.gz`: the version, the domains (code → label and
  description), and the senses that have places, each `[lemma, glosses,
  definition, [domain codes], places]`, *places* its words in the whole
  Tanakh;
- `<book>.json.gz`, one per book, the Ketuvim's too: each pasuq, each OSHB
  word's sense (a number into the senses), a list of two, or `-1`, in the
  order the shorashim data has the words.

To make it again, from SDBH's JSON and OSHB's books (downloaded when not
given):

```bash
python scripts/build_semantics.py [--source DIR]
```

It prints, book by book, how many words have a sense, then the table
above.
