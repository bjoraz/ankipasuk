# Phrases

How AnkiPasuk finds a passage's recurring phrases and sorts them: what
counts as a phrase, how phrases are found, the tests and their thresholds,
and which phrases are set apart as formulas. The code is
`src/ankipasuk/phrases.py`, which follows this page section by section; the
data is OSHB's, as for the shorashim (see the README's Shorashim section,
and [Data](#data) below).

The *passage* is whatever is loaded: all its range rows, a pasuq loaded
twice counting once.

## What it shows

Four sections, for the loaded passage:

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

The three kinds are tested independently. A phrase is listed in every
section whose test it passes, and is tagged there with the other sections
it's in. For example, in Balaq וחרבו שלופה בידו is a refrain, an echo of
Divre haYamim I 21:16 and an idiom. A formula is listed under Formulas
only.

## Words

A phrase is a sequence of dictionary words (OSHB's lemmas), so the same
words in different forms make the same phrase:

- **Prefixes and suffixes are ignored.** בְּיָד חֲזָקָה is the same as
  וּבְיָד חֲזָקָה, and וַיַּרְא the same as וַתֵּרֶא.
- **The object marker is left out.** That's אֵת, with or without a suffix.
- **The qere is read**, not the ketiv. A two-word name like בֵּית לֶחֶם is
  one word.
- **One book only.** A phrase never runs from one book into the next.

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
   occurrences allow, with no length limit. The princes' offering in
   Bamidbar 7 is a single phrase of 55 words, occurring 12 times. The
   Decalogue in Devarim 5 comes out in long pieces (74, 20 and 16 words),
   split where its wording differs from Shemot 20.
3. **Cut at the ta'amim** of the passage's occurrence. A phrase may cross:
   - a sof pasuq only if it contains a whole pasuq;
   - an etnaḥta only if it contains a whole half-pasuq;
   - a segol, shalshelet, zaqef qatan, zaqef gadol or tifḥa only if it
     contains a whole unit between two such breaks (or an etnaḥta or sof
     pasuq).

   Otherwise it's cut there into pieces. Long parallels cross freely,
   while a phrase that only joins the end of one pasuq or half to the
   start of the next doesn't: וירא אלהים כי טוב | ויהי ערב ויהי בקר יום,
   ויהי כן | ויעש אלהים.
4. **Trim.** Particles come off both ends, except לֹא and אַל. At the end,
   כֹּל and a verb of saying (אמר, דבר, ענה) come off too, because what
   was said follows: וישא משלו ויאמר becomes וישא משלו.
5. **At least two content words.**

A piece made by steps 3 and 4 keeps the occurrences of the phrase it came
from. If it also occurs elsewhere on its own, step 2 finds it separately,
with all its occurrences.

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
| **Names and their families** | a name | בֵּן, בַּת, אָב, אָח, אִשָּׁה, בַּיִת, אֶרֶץ, מֶלֶךְ, עַם, מַטֶּה, שֵׁבֶט, מִשְׁפָּחָה, עִיר, עֵבֶר; other names; God's names | בני ישראל, בלק בן צפור, מלך מצרים, מארץ מצרים, יהוה אל משה | רות המואביה (a people is no name here), משדי מואב |
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

**An exceptional wording of God's names is not a formula.** The wording is
the letters of the words without their prefixes, keeping whether a word
has a suffix but not which one. A wording is exceptional if either:
- it occurs in at most 10 places in the Tanakh: אל שדי (8), אל עליון (5),
  יהוה יהוה (7, Shemot 34), אלהי העברים, and אלהי אברהם אלהי יצחק ואלהי
  יעקב;
- it occurs at least twice in the passage, and the passage has at least a
  third of its occurrences: יהוה אלהים in Bereshit 2–3 (20 of 49).

יהוה אלהינו in Devarim 5–6 stays a formula: the wording יהוה + אלהי with
a suffix has 610 places, 29 of them here. So do יהוה אלהי אבתיכם (18
places) and לפני יהוה אלהינו (32).

**Lists are not formulas.** A phrase with three or more names or peoples,
with or without other words, is tested like any other phrase: הכנעני
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

## Display

- **In the Text view.** The side panel switches between Shorashim and
  Phrases. Phrases shows one section at a time, by its tab (each with its
  count), under a line saying what the section holds.
  - Each row is the phrase, in its first wording here (Sefaria's text,
    via the shorashim's lining-up of words; a long one shortened: "קצות
    החשן שתי קצות … מעל האפד (67 words)"), and under it how often it's
    here and where else: an echo's places, each a link, or "35
    elsewhere", a link too (the other pesuqim it's in).
  - Clicking a row underlines the phrase in the text, in the palette's
    colours (the shorashim's, in click order), and brings its first pasuq
    into view; the row is marked in the same colour. **Clear colours**
    clears roots and phrases. Each underline is one line from a phrase's
    first word to its last, spaces and maqaf included; where picked
    phrases share words, each keeps its own depth below the text.
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
  each `[word, flags]`, or `[word, flags, form]` for God's names and the
  words of their titles. The flags are the qere, a name, a people, a
  numeral, construct state, a suffix, an etnaḥta, and a segol,
  shalshelet, zaqef or tifḥa (`shorashim_build.book_lemmas`).
- the shorashim's data (letters and groups) for the eight books the app
  has no readings from, so a phrase can be marked in them.

The app reads it all into parallel arrays, one entry per token, with an
index of every pair of words; a passage's phrases take well under a
second, a whole book about one.

## Thresholds

These are the defaults. **Settings**, in the main window's top bar, changes
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
| God's names: rare wording | ≤ 10 places | 0–100 | calibrated: אל שדי (8) in, אלהי יעקב (15) out |
| God's names: concentrated wording | ≥ 2 here and ≥ ⅓ of all | ¼–¾ | יהוה אלהים in Bereshit 2–3 (20 of 49) in, יהוה אלהינו in Devarim 5–6 out |

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
- **A whole book loaded** makes its own common titles concentrated, so for
  all of Devarim, יהוה אלהיך counts as exceptional.
