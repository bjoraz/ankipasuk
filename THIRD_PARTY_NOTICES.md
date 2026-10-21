# Third-party data

## Maftir lengths and holiday/fast-day readings

`src/ankipasuk/data/parashot.json` (the `maftir_verses` field only) and
`src/ankipasuk/data/holiday_readings.json` were derived from the
[`@hebcal/leyning`](https://github.com/hebcal/hebcal-leyning) npm package
(`aliyot.json` and `holiday-readings.json`), Copyright (c) 2020, Hebcal,
licensed under the BSD 2-Clause License:

```
BSD 2-Clause License

Copyright (c) 2020, hebcal
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

The weekly 'aliyya divisions are not taken from this data. They're fetched
live from the [Sefaria API](https://www.sefaria.org/) and cached locally
(see `ankipasuk.sefaria.get_parasha_structure`). The bundled data is used
only for two things Sefaria's `Parasha` structure doesn't provide:

1. **How many pesuqim each parasha's maftir has** (a number, such as 4).
   This is counted back from the live end of the seventh 'aliyya to find the
   actual maftir, so differences in chapter numbering between sources can't
   throw it off (see `docs/anki-tagging.md` for why this matters at
   Bereshit 31/32).
2. **Holiday and fast-day readings**, which Sefaria's `Parasha` structure
   doesn't cover at all.

The holiday table was trimmed down from Hebcal's full calendar data to one
standard reading per occasion, independent of the year (see
`docs/anki-tagging.md` for the list and what was left out).

## Shorashim

`src/ankipasuk/data/shorashim/` and `src/ankipasuk/data/phrases/` were made
by `scripts/build_shorashim.py` from two Open Scriptures projects:

- the [Open Scriptures Hebrew Bible](https://github.com/openscriptures/morphhb)
  (`wlc/*.xml`): each word's lemma. The text is the Westminster Leningrad
  Codex, which is in the public domain; OSHB's lemmas and morphology are
  licensed under the
  [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/)
  (CC BY 4.0), Open Scriptures Hebrew Bible, https://hb.openscriptures.org;
- [HebrewLexicon](https://github.com/openscriptures/HebrewLexicon)
  (`LexicalIndex.xml`): each lemma's part of speech, gloss, and place in
  Brown–Driver–Briggs (a public-domain work, 1906), from the same project.

What's bundled is derived from them: each word's letters and the group
(root, or the word itself) it belongs to, and each group's label, gloss,
words, and count in the whole of OSHB's Tanakh; and, for the phrases, each
word of the Tanakh's dictionary entry (numbered, with its Strong's number
and part of speech) and a few facts from its morphology and accents (a
name, a people, a numeral, construct state, an etnaḥta or other mafsiq on
it, a qere).

The Name's gloss was changed from "Jehovah" to "the Name", and the other
names' English glosses, peoples' included, to the names in AnkiPasuk's
own spelling. Some common words, whose BDB gloss is more an etymology
than a meaning, also have a plain meaning added beside it (`MEANINGS` in
`src/ankipasuk/shorashim_build.py`); their BDB gloss is kept.

