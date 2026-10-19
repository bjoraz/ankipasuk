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

The weekly 'aliya divisions are not taken from this data. They're fetched
live from the [Sefaria API](https://www.sefaria.org/) and cached locally
(see `ankipasuk.sefaria.get_parasha_structure`). The bundled data is used
only for two things Sefaria's `Parasha` structure doesn't provide:

1. **How many pesukim each parasha's maftir has** (a number, such as 4).
   This is counted back from the live end of the seventh 'aliya to find the
   actual maftir, so differences in chapter numbering between sources can't
   throw it off (see `docs/anki-tagging.md` for why this matters at
   Bereshit 31/32).
2. **Holiday and fast-day readings**, which Sefaria's `Parasha` structure
   doesn't cover at all.

The holiday table was trimmed down from Hebcal's full calendar data to one
standard reading per occasion, independent of the year (see
`docs/anki-tagging.md` for the list and what was left out).
