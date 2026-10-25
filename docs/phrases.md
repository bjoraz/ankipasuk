# Phrases

How AnkiPasuk finds a passage's recurring phrases and sorts them: what
counts as a phrase, how phrases are found, the tests and their thresholds,
which phrases are set apart as formulas, and frames. The code is
`src/ankipasuk/phrases.py` (frames: `src/ankipasuk/frames.py`), which
follows this page section by section; the
data is OSHB's, as for the shorashim (see the README's Shorashim section,
and [Data](#data) below).

The *passage* is whatever is loaded: all its range rows, a pasuq loaded
twice counting once.

## What it shows

Five sections, for the loaded passage:

- **Refrains**: phrases repeated in the passage more than chance would
  give. ויהי ערב ויהי בקר (Bereshit 1), וישא משלו (Balaq), צוה יהוה את משה
  (Pequdei), משדי מואב (Ruth).
- **Echoes**: phrases the passage shares with one to three other places.
  תהו ובהו (Bereshit 1; Yirmeyahu 4:23), של נעליך מעל רגליך (Shemot 3;
  Yehoshua 5:15), מבית לחם יהודה לגור (Ruth; Shofetim 17:8), and whole
  parallels: the Decalogue (Devarim 5; Shemot 20), Shemuel II 22 (Tehillim
  18).
- **Idioms**: fixed expressions used across the Tanakh. ארץ זבת חלב ודבש,
  ויחר אף יהוה, בכל לבבך ובכל נפשך, וטמא עד הערב.
- **Formulas**, collapsed: phrases that only frame. ויאמר אלהים, בני
  ישראל, יהוה אלהיך.
- **Frames**: units of the book's Masoretic sections that open and close
  with the same words (an *inclusio*). ברא אלהים, Bereshit 1:1–2:3; ילד,
  Ruth 1:5 and 4:16. See [Frames](#frames).

The three kinds are tested independently. A phrase is listed in every
section whose test it passes, and is tagged there with the other sections
it's in. For example, in Balaq וחרבו שלופה בידו is a refrain, an echo of
Divre haYamim I 21:16 and an idiom. A formula is listed under Formulas
only. Frames are found apart from the rest, over the whole book.

## Words

A phrase is a sequence of dictionary words (OSHB's lemmas), so the same
words in different forms make the same phrase:

- **Prefixes and suffixes are ignored.** בְּיָד חֲזָקָה is the same as
  וּבְיָד חֲזָקָה, and וַיַּרְא the same as וַתֵּרֶא.
- **The object marker is left out.** That's אֵת, with or without a suffix.
- **The qere is read**, not the ketiv. A two-word name like בֵּית לֶחֶם is
  one word.
- **One book only.** A phrase never runs from one book into the next.

Every count and every test goes by these dictionary words, the one for
God's names included ([Formulas](#formulas)): nothing looks at a word's
exact form.

Phrases go by dictionary word, not root: מַלְאָךְ and מְלָאכָה share
ל־א־כ, but they're different words.

**Content words** are all words except particles (the lexicon's
prepositions, conjunctions, pronouns, adverbs and the like) and כֹּל.

The Tanakh here means all of it, including the books the app has no
readings from.

## Finding phrases

For each word of the passage:

1. **Occurrences.** Follow the sequence starting at this word through all
   its occurrences in the Tanakh, one word at a time, for as long as at
   least two occurrences remain. An index of word pairs gives the first
   two words at once.
2. **Closed.** Keep a phrase only if it can't be extended at either end
   without losing an occurrence. Each phrase is therefore as long as its
   occurrences allow, with no length limit, before step 3 divides it.
3. **Divided as the ta'amim divide** the passage's occurrence. The breaks
   are, from the strongest: sof pasuq; etnaḥta; the kings (segolta,
   shalshelet, zaqef qatan and gadol, tifḥa); the dukes (revia', zarqa,
   pashta, yetiv, tevir), as in the diagrams' rank table. A phrase may
   cross a sof pasuq, an etnaḥta or a king only if it starts and ends on
   breaks at most one step weaker than the strongest it crosses: an
   etnaḥta for a sof pasuq, a king for an etnaḥta, a duke for a king.
   Particles between a phrase's end and a break don't count (אל ארץ זבת
   חלב ודבש starts on the zaqef before אל), and a particle's own accent
   doesn't hide a stronger break beyond it.

   Otherwise the part-unit at either end is cut off at the strongest
   break, and each piece is divided the same way. So ויהי ערב ויהי בקר
   יום, which runs past the tifḥa into יום אחד (יום has no disjunctive),
   is ויהי ערב ויהי בקר; and Yeḥezqel's ויהי דבר יהוה אלי לאמר doesn't
   run on into the next pasuq's בן אדם, which ends on a zaqef, not an
   etnaḥta. But מארץ מצרים מבית עבדים (Devarim 5:6) crosses its tifḥa
   whole, since it starts on the tevir of הוצאתיך; and ואהבת את יהוה
   אלהיך בכל לבבך ובכל נפשך crosses the etnaḥta, ending on the tifḥa of
   נפשך. The princes' offering in Bamidbar 7 comes out as its four whole
   pesuqim (41 words), 12 times: the fifth ends with each prince's name.
   The Decalogue in Devarim 5 comes out in a long piece of whole pesuqim
   (72 words) and shorter ones at the commandments, where its wording
   differs from Shemot 20.
4. **Trim.** Particles come off both ends, except לֹא and אַל. At the end,
   כֹּל and a verb of saying (אמר, דבר, ענה) come off too, because what
   was said follows: וישא משלו ויאמר becomes וישא משלו. A trimmed piece
   whose new ends no longer stand on its breaks is divided again.
5. **At least two content words.**

A piece made by steps 3 and 4 keeps the occurrences of the phrase it came
from. If it also occurs elsewhere on its own, step 2 finds it separately,
with all its occurrences.

One step weaker lets an expression the ta'amim divide stay whole where its
ends still stand on their division, as מארץ מצרים מבית עבדים does. One
that starts after a conjunctive is still cut: חן בעיניו in מצאתי חן |
בעיניו. A duke is a light break, so a few phrases ending on one read as
fragments (לרקיע | שמים).

## The tests

Notation:
- *W* is the number of words in the passage and *N* the number in the
  Tanakh.
- *f(w)* is a word's count in the Tanakh and *f*ₚ*(w)* its count in the
  passage.
- The *chance* of a phrase is the probability of seeing it at least as
  often as it occurs, if words fell independently. It's a Poisson tail,
  whose expected value is the number of word positions times the product
  of its words' relative frequencies.

**Refrain**
- At least 2 times here.
- Chance below 1/1000, with expected value *W* · ∏ *f*ₚ*(w)*/*W*.
- Ranked by chance, lowest first.

This tests against the passage's own word counts, because a word that's
frequent in the passage makes its pairs recur by chance. בלעם לך in Balaq
doesn't pass: Bil'am is everywhere there.

**Echo**
- At least once here, in 1 to 3 pesuqim outside the passage.
- Chance below 1/1000 for its total count, with expected value *N* · ∏
  *f(w)*/*N*.
- Ranked by chance, lowest first, so long, rare phrases come first.

**Idiom**
- At least 4 occurrences, in at least 3 chapters.
- At every split into two parts, the parts occur together far more often
  than chance would give: a log-likelihood of G² ≥ 10.83 (p < 0.001), from
  the 2×2 table of the two parts' counts over *N*.
- At the weakest split, *bound* ≥ 0.1. A split's bound is the phrase's
  count divided by the count of its rarer part, so at least a tenth of
  that part's uses are in this phrase.
- Ranked by bound, then by count.

The test counts chapters, not books, so a book's stock phrases count:
Devarim's המקום אשר יבחר יהוה, Vayiqra's וטמא עד הערב. A refrain confined
to one chapter doesn't count as an idiom, such as וירא אלהים כי טוב.

**Folding.** In each section, a phrase inside a longer phrase of the same
section is folded under it when it doesn't recur apart from it:
- for refrains, when fewer of its occurrences here than a refrain needs
  (2) lie outside the longer phrase;
- for echoes, when none of its other places lie outside it;
- for idioms, when fewer than 2 of its occurrences in the Tanakh lie
  outside it;
- for formulas, when none of its occurrences here lie outside it.

The longest phrases are placed first, and a phrase goes under the first
longer one that holds it. A folded phrase isn't listed on its own: it's
part of the longer one (the data still gives it, as the longer one's
`children`).

## Formulas

A formula only frames: it says who speaks, names someone or God, counts or
dates, and says nothing else. A phrase is a formula of a class if it has
one of the class's **core** words and every other content word is a core
word or one the class **also** allows.

A *name* in these classes is a person's or a place's. The lexicon calls
יהוה a name too, but God's names count only where a class allows them, so
בית יהוה and ויהי יהוה את יוסף are not name or time formulas.

Names and peoples (gentilics) are as the shorashim have them, decided
once for each dictionary word: a people is a word the lexicon calls one,
or one OSHB's morphology calls one in most of its places. Neither alone is
steady: the lexicon calls כְּנַעֲנִי a noun and מוֹאָבִי an adjective, and
OSHB tags בֵּן a people twice in its 4,940 places. Numerals, construct
state and suffixes come from OSHB's morphology (`Ac`/`Ao`), word by word;
all other words go by Strong's number.

| Class | Core | Also | Formulas | Not formulas |
|---|---|---|---|---|
| **God's names and titles** | see below | | יהוה אלהיך, יהוה צבאות, אדני יהוה, אלהי ישראל, לפני יהוה | מלאך יהוה, ברוך יהוה, יד יהוה, חי יהוה |
| **Names and their families** | a name, not God's | בֵּן, בַּת, אָב, אָח, אִשָּׁה, בַּיִת, אֶרֶץ, מֶלֶךְ, עַם, מַטֶּה, שֵׁבֶט, מִשְׁפָּחָה, עִיר, עֵבֶר; other names; God's names | בני ישראל, בלק בן צפור, מלך מצרים, מארץ מצרים, יהוה אל משה | רות המואביה (a people is no name here), משדי מואב, בית יהוה |
| **Speech** | אָמַר, דָּבַר, דָּבָר, נְאֻם, עָנָה | names, God's names, family words, הָיָה, עַם | ויאמר אלהים, ויאמר בלק אל בלעם, וידבר יהוה אל משה לאמר, ויען בלעם, ויהי דבר יהוה, נאם יהוה | ויאמר אלהים יהי אור, שמע ישראל |
| **Numbers, dates and measures** | a numeral | שָׁנָה, חֹדֶשׁ, יוֹם, אַמָּה, שֶׁקֶל, אֹרֶךְ, רֹחַב, קוֹמָה, מִשְׁקָל, בֶּקַע, כִּכָּר, בֵּן (בן שנה) | שלשים ומאה משקלה, ואלף ושבע מאות וחמשה ושבעים, יום שלישי, ביום השביעי | ויום השביעי שבת, כבשים בני שנה |
| **Genealogies and censuses** | יָלַד, חָיָה, מוּת, פָּקַד, תּוֹלְדוֹת, מִסְפָּר, גֻּלְגֹּלֶת, with a name or a numeral | names, family words, numbers and measures, זָכָר, שֵׁם, יָצָא, צָבָא | ורם הוליד את עמינדב, ויחי X שנה ויולד, הפקדים מבן עשרים שנה | מות יומת, תלדי בנים |
| **Time** | הָיָה | יוֹם, עֵת, names, numerals | ויהיו ימי, ויהי ביום, ויהי בימי X | ויהי ערב ויהי בקר |

The classes are tried in this order, and a formula is listed under the
first class that fits.

**What's deliberately left out of the classes:**
- קָרָא is no speech word, because God naming day and night (ויקרא
  אלהים) is a refrain of Bereshit 1.
- צִוָּה is no speech word, because כאשר צוה יהוה את משה is the refrain of
  Pequdei.

**God's names and titles** follow their shape. A phrase is one if every
word (כֹּל aside) is one of:
- a name of God: יהוה, אֱלֹהִים, אֲדֹנָי, אֵל, אֱלוֹהַּ, שַׁדַּי, עֶלְיוֹן;
  or צְבָאוֹת right after one of these, since alone it's an army, as in
  צבא ישראל;
- a name, a people, or אָב, right after a construct form of a name of
  God that has no suffix: אלהי אברהם, אלהי העברים, אלהי אבתיכם;
- פְּנֵי or עֵינֵי, without a suffix, right before a name of God: לפני
  יהוה, בעיני יהוה.

There may be no particle in it, and no left-out אֵת inside. So צוה יהוה
את משה contains no title "יהוה משה", and יהוה אל משה is a name formula.

**An exceptional title of God is not a formula.** It's counted like every
phrase, by its dictionary words, so in all its forms: יהוה אלהים, יהוה
אלהיך and יהוה אלהינו are one title, 903 times in the Tanakh. A title is
exceptional if either:
- it's **rare**, at most 10 times in the Tanakh: אל שדי (8), אל עליון (5),
  יהוה יהוה (7, Shemot 34), אלהי העברים (6), and אלהי אברהם אלהי יצחק
  ואלהי יעקב (3);
- it's **mostly here**, at least twice in the passage and at least a
  third of all its times: Yeḥezqel's אדני יהוה (217 of 301), Yirmeyahu's
  יהוה צבאות אלהי ישראל (32 of 37).

So יהוה אלהים in Bereshit 2–3 is a formula (20 of 903), as is יהוה אלהינו
in Devarim 5–6. The row of an exceptional title is badged "rare" or
"mostly here", with its counts.

**Lists are not formulas.** A phrase with three or more names or peoples
(God's not counted), with or without other words, is tested like any
other phrase: הכנעני
והחתי והאמרי והפרזי והחוי והיבוסי, לאבתיך לאברהם ליצחק וליעקב, ובצלאל
בן אורי בן חור. The common lists come out as idioms.

**Formulaic but meaningful phrases are not formulas either.** They say
something, and come out as idioms (hence chapters, not books, in the idiom
test):
- Kings' regnal formulas: ויעש הרע בעיני יהוה, וישכב עם אבתיו
- priestly formulas: ריח ניחח ליהוה, חקת עולם לדרתיכם, ונכרתה הנפש ההוא
  מעמיה, וטמא עד הערב
- Deuteronomic formulas: אשר אנכי מצוך היום, המקום אשר יבחר יהוה
- the recognition formula, וידעתם כי אני יהוה
- the oath, חי יהוה

## Frames

A frame (an *inclusio*) is a unit of the text that opens and closes with
the same words. The units are the book's Masoretic sections (the
README's Text view section has where they come from):

- a **setuma section**: one section, a setuma at either of its ends;
- a **petuḥa section**: from a petuḥa to the next, however many setumot
  it holds (the book's start and end count as petuḥot): Bereshit 2:4–3:21,
  with setumot after 3:15 and 3:16, or Devarim 22:6–25:16, with 35;
- a **run** of up to 8 consecutive sections, otherwise.

The whole book is searched, whatever is loaded, and a frame is listed when
its unit overlaps the passage. A break inside a pasuq doesn't end a unit.
A book without section data (the Ketuvim but the Megillot) has no frames.

There are three kinds, listed apart:

- **Phrases**: a phrase of the book (as the tests above find them in the
  whole book, formulas left out) that is in the unit's first pasuq and its
  last. Sections: עשות יהוה אלהים, Bereshit 2:4–3:21; ביום אפו, Eikha 2;
  שמע ישראל, Devarim 5:1–6:3; each camp of Bemidbar 2 opens and closes with
  its מחנה. Runs: ברא אלהים frames the creation, Bereshit 1:1–2:3, seven
  petuḥa sections; Miryam's song closes as the song of the sea opens
  (Shemot 15:1–21).
- **Words (candidates)**: a rare dictionary word, at most 15 times in the
  book and 4 in the unit, found only near the unit's two ends: in its
  first and its last tenth (at most 5 pesuqim each), at least once in each,
  nowhere between. ילד in Ruth (1:5, Naomi's children lost; 4:16, the
  child in her lap), רוח in Yona (1:4, 4:8), צלם and דמות in Bereshit (1:26
  and 5:1–3), והארכת ימים around Devarim's laws (22:7, 25:15). God's names
  are left out.
- **Fields (candidates)**: a rare semantic field (see
  [`semantics.md`](semantics.md), at the level the Fields pane uses), in at
  most 25 of the book's pesuqim and 4 of the unit's, found only near the
  unit's two ends as a word is, and said in other words at one end than
  at the other: the same meaning, said differently. Marry around Shemot
  2:1–22 (וַיִּקַּח, 2:1; וַיִּתֵּן, 2:21); signs and wonders around Shemot
  10:1–11:10 (אֹתֹת, מוֹפְתִים); Festivals around Devarim 16:1–8 (פֶּסַח,
  עֲצֶרֶת); writing around Devarim 10:1–11:21 (the tablets, and "write them
  on the doorposts"). A field's frame in the same word at both ends is a
  word's frame, and isn't listed again (Shemot 2's births, וַתֵּלֶד).

**The chance** of each is how likely its places in the unit would fall so
if they were spread at random over the unit's pesuqim:

- a phrase in *m* of the unit's *P* pesuqim has its first and its last
  among them with chance *m*(*m*−1) / *P*(*P*−1): ברא אלהים is in 4 of the
  34 pesuqim of Bereshit 1:1–2:3, so 12 / 1,122, 1 in 94;
- a word in *m* pesuqim of the unit, with ends of *e* pesuqim, is in the
  ends only, some in each, with chance [C(2*e*, *m*) − 2 C(*e*, *m*)] /
  C(*P*, *m*).

A phrase or word is tried in every unit it could frame, so its best chance
is multiplied by the number of units tried, and it's kept if that's under
0.05; for each, its strongest unit is listed. **The sections come first**:
a phrase or word is tested on the setuma and petuḥa sections it could
frame, against their number, and only if it frames none of them, on all
its units, against all of them. So a section's frame is kept over a
stronger run's, and is found more easily. The list has the phrases framing
a section first, then those framing a run, then the words, each in order
of that chance (times the units).

**Words and fields are candidates**, not findings: about a third of the
words are the same rare word in two neighbouring stories, or two senses of
one word, and some fields are as much chance (bodily fluids around
Yesha'yahu 36–38). Their groups are folded; click a header to show them. A frame shows its unit,
what the unit is ("a petuḥa section with 2 setumot", "7 sections") and
its chance; its ends outside the passage are links, each opening the
frame's viewer on that pasuq in its chapter.

## Display

- **In the Text view.** The side panel switches between Shorashim and
  Phrases. Phrases shows one section at a time, by its tab (each with its
  count), under a line saying what the section holds. A section lists its
  first 12 phrases, in its ranking; **Show all** lists every one, and is
  remembered per section. The Statistics window lists them the same way.
  - Each row is the phrase, in its first wording here (Sefaria's text,
    via the shorashim's lining-up of words; a long one shortened: "קצות
    החשן שתי קצות … מעל האפד (67 words)"), and under it how often it's
    here and where else: an echo's places, each a link, or "35
    elsewhere", a link too (the other pesuqim it's in).
  - Clicking a row underlines the phrase in the text, in the palette's
    colours (the shorashim's, in click order), and shows an occurrence:
    the first one in view, or else the first, brought into view and
    flashed. The row is marked in the same colour. **Clear colours**
    clears roots and phrases. Each underline is one line from a phrase's
    first word to its last, spaces and maqaf included; where picked
    phrases share words, each keeps its own depth below the text.
  - A picked phrase moves to the top of its section (picked ones in the
    order picked, above a line), with a strip showing where it is in the
    passage: a tick at each pasuq it's in, the first pasuq on the right.
    Clicking the strip goes to the occurrence nearest the click.
  - A picked phrase that's here more than once gets arrows, ‹ 2/6 ›, that
    go to its previous or next occurrence in the text (round from the
    last to the first), each flashed; a pasuq loaded twice has one in
    each.
  - A group of a section (a formula class, the frames' kinds) folds and
    opens by its header, and stays so.
  - **The archive.** Hovering over a row shows **archive**: it puts the
    phrase away, out of every section it's in, in every passage, until
    it's restored. A phrase is archived by its dictionary words, so in all
    its wordings; a frame is archived for its book. **Archive (n)**, below
    the list, lists everything archived, the last first, with the section
    it was archived from, its pasuq (a frame's unit) and the day, each
    with **Restore** (and **Restore all**). It's kept with the settings,
    and the Statistics window shares it.
  - The phrases are found once the shorashim are in. The Tanakh's index
    is built when the app starts, in the background (a second or two).
- **The viewer.** A place's link opens the phrase's viewer: on the right,
  its pesuqim here, the phrase marked; on the left, the place in its whole
  chapter, fetched from Sefaria (and cached, like everything fetched), the
  pasuq tinted, the phrase marked, scrolled to it. Up to six places are
  buttons; more, a list to step through (‹ ›), the first 30. A chapter
  that can't be fetched, offline, shows the place and why. Esc closes it.
- **In Statistics.** A Phrases tab has the same tabs and rows, a row a
  line; a row, or one of its places, opens the same viewer.

## Data

`scripts/build_shorashim.py` writes, besides the shorashim's data:

- `data/phrases/lemmas.json.gz`: every dictionary word the Tanakh has,
  numbered, as `[strong, kind]` (a particle, a name, a name of two words,
  another word).
- `data/phrases/<book>.json.gz`, for all 39 books: each pasuq's words, as
  OSHB has them (the same words in the same order as the shorashim's),
  each `[word, flags]`. The flags are the qere, a name, a people, a
  numeral, construct state (without a suffix), an etnaḥta, a king
  (segolta, shalshelet, zaqef or tifḥa) and a duke (revia', zarqa,
  pashta, yetiv or tevir) (`shorashim_build.book_lemmas`).
- the shorashim's data (letters and groups) for the eight books the app
  has no readings from, so a phrase can be marked in them.

The app reads it all into parallel arrays, one entry per token, with an
index of every pair of words; a passage's phrases take well under a
second, a whole book about one.

## Thresholds

These are the defaults. **Settings…**, in the Text view's Phrases pane, changes
any of them, within the limits shown; the phrases are found again at once,
in an open statistics window too. Only the changed ones are saved, so a
later change of a default still applies to the rest
(`phrases.Thresholds`, `phrases.LIMITS`).

| Threshold | Default | Limits | Why |
|---|---|---|---|
| Content words in a phrase | ≥ 2 | 2–6 | one word is the shorashim's job |
| Refrain: times here | ≥ 2 | 2–10 | a refrain repeats |
| Refrain: chance | < 0.001 | | a common significance level |
| Echo: other pesuqim | 1–3 | 1–10 | more is a stock phrase, an idiom's test |
| Echo: chance | < 0.001 | | a common significance level |
| Idiom: occurrences / chapters | ≥ 4 / ≥ 3 | 3–50 / 2–30 | used widely, not one passage's repetition |
| Idiom: chance of the G² at every split | < 0.001 (G² ≥ 10.83) | | one degree of freedom |
| Idiom: bound at the weakest split | ≥ 0.1 | 0.01–1 | calibrated: drops ויקח שני and ישראל באה, keeps ככוכבי השמים and מלאך יהוה |
| God's names: rare title | ≤ 10 times | 0–100 | calibrated: אל שדי (8) in, אלהי יעקב (15) out |
| God's names: title mostly here | ≥ 2 here and ≥ ⅓ of all | ¼–¾ | a book's own titles: Yeḥezqel's אדני יהוה (217 of 301) |

The chances are offered from 1/100 to 1/1,000,000. The refrains' fold
follows their times here: a shorter refrain stays listed on its own when
it recurs that often apart from the longer one.

## Limitations

- **Statistics, not judgement.** The tests treat words as independent, but
  syntax makes some common pairs likelier than that. The floors and the
  formula classes make up for most of this; fragments like בלעם ויעלהו
  still turn up low in a list.
- **Dictionary words match different wordings.** That's by design: ואשובה
  אל אחי (Shemot 4:18) finds Bereshit 37:30. But some exact allusions are
  missed: לך לך has one content word.
- **Small differences split long parallels** into several echoes, like the
  Decalogue.
- **The ta'amim are OSHB's** (the Leningrad Codex), which can differ from
  Sefaria's here and there. The poetic books' accents work differently,
  but the app has no readings from them, and the cut uses only the
  passage's own accents.
- **Frames find words, not themes.** A frame of related words (ילד in Ruth
  opens with יְלָדֶיהָ and closes with הַיֶּלֶד) is found; a theme told in
  different words isn't. And the units are the Masoretic sections, which
  needn't be a passage's literary units.
- **A whole book loaded** makes its own common titles mostly here, so for
  all of Devarim, יהוה אלהיך counts as exceptional (316 of its 903 times).
