# Third-party data

## Maftir verse counts and holiday/fast-day readings

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

Everything else in `parashot.json` (the weekly aliyah 1-7 boundaries
themselves) is *not* taken from this data and is instead fetched live from
the [Sefaria API](https://www.sefaria.org/) at runtime, cached locally --
see `ankipasuk.sefaria.get_parasha_structure`. The bundled data is used only
for two things Sefaria's `Parasha` alt-structure doesn't provide:

1. **How many verses long each parasha's Maftir is** (an integer, e.g. 4)
   -- combined with the live-fetched aliyah 7 boundary to compute the actual
   Maftir verse range, so it's immune to any chapter/verse numbering
   differences between data sources (see `docs/anki-tagging.md` for why this
   matters, specifically around the Genesis 31/32 boundary).
2. **Holiday and fast-day Torah reading ranges**, which have no equivalent
   in Sefaria's Parasha structure at all.

The holiday/fast-day table was curated down from Hebcal's full liturgical
calendar data to one representative, non-year-dependent verse range per
occasion (see `docs/anki-tagging.md` for the exact list and scope).
