"""Static configuration and constants shared across the package.

Nothing in this module performs I/O or depends on tkinter/requests, so it is
safe to import from anywhere (including tests) with no side effects.
"""

# =============================================================
#  SEFARIA API
# =============================================================
SEFARIA_API_BASE = "https://www.sefaria.org/api/v3/texts"
SEFARIA_INDEX_BASE = "https://www.sefaria.org/api/v2/raw/index"
REQUEST_TIMEOUT = 20
POINTED_VERSION = "source"

# =============================================================
#  TORA STRUCTURE
# =============================================================
# Pesuqim per chapter, as Sefaria and tikkun.io both have them: the Hebrew
# chapter division, and the 'Aseret haDibberot (Shemot 20, Devarim 5)
# divided into pesuqim as those texts divide them. An earlier version of
# this table followed English Bibles, which split 16 chapters
# differently (Shemot 7/8, Bemidbar 16/17, ...); that threw tikkun.io
# lookups and parasha numbering off at those boundaries.
TORAH_VERSE_COUNTS = {
    "Genesis": [
        31, 25, 24, 26, 32, 22, 24, 22, 29, 32,
        32, 20, 18, 24, 21, 16, 27, 33, 38, 18,
        34, 24, 20, 67, 34, 35, 46, 22, 35, 43,
        54, 33, 20, 31, 29, 43, 36, 30, 23, 23,
        57, 38, 34, 34, 28, 34, 31, 22, 33, 26,
    ],
    "Exodus": [
        22, 25, 22, 31, 23, 30, 29, 28, 35, 29,
        10, 51, 22, 31, 27, 36, 16, 27, 25, 23,
        37, 30, 33, 18, 40, 37, 21, 43, 46, 38,
        18, 35, 23, 35, 35, 38, 29, 31, 43, 38,
    ],
    "Leviticus": [
        17, 16, 17, 35, 26, 23, 38, 36, 24, 20,
        47, 8, 59, 57, 33, 34, 16, 30, 37, 27,
        24, 33, 44, 23, 55, 46, 34,
    ],
    "Numbers": [
        54, 34, 51, 49, 31, 27, 89, 26, 23, 36,
        35, 16, 33, 45, 41, 35, 28, 32, 22, 29,
        35, 41, 30, 25, 18, 65, 23, 31, 39, 17,
        54, 42, 56, 29, 34, 13,
    ],
    "Deuteronomy": [
        46, 37, 29, 49, 30, 25, 26, 20, 29, 22,
        32, 31, 19, 29, 23, 22, 20, 22, 21, 20,
        23, 29, 26, 22, 19, 19, 26, 69, 28, 20,
        30, 52, 29, 12,
    ],
}

# Chapter counts per book, derived from TORAH_VERSE_COUNTS so the two never
# drift out of sync.
TORAH_BOOKS = {book: len(verses) for book, verses in TORAH_VERSE_COUNTS.items()}

# =============================================================
#  NEVI'IM / MEGILLOT
# =============================================================
# Unlike TORAH_VERSE_COUNTS, these have no hardcoded per-chapter verse
# counts -- Nevi'im alone is 21 books, several very long (Isaiah,
# Jeremiah, Ezekiel, Psalms-length material), so hand-maintaining that
# table the way Tora's is maintained isn't practical. Chapter/verse
# counts for these are instead discovered live from Sefaria on first use
# (see sefaria.get_book_chapter_count / get_chapter_lengths) and cached
# afterward via SefariaCache, the same caching layer everything else here
# already goes through.
#
# All of these use the standard 21-book cantillation system (the same
# TROPE_UNICODE table below applies unchanged) -- this deliberately
# excludes Tehillim, Mishle and Iyov, which use the distinct "three
# books" (Sifre Emet) cantillation system with a different ta'amim
# hierarchy entirely, not supported here.
NEVIIM_BOOKS = [
    "Joshua", "Judges", "I Samuel", "II Samuel", "I Kings", "II Kings",
    "Isaiah", "Jeremiah", "Ezekiel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
    "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
]

MEGILLOT_BOOKS = [
    "Song of Songs", "Ruth", "Lamentations", "Ecclesiastes", "Esther",
]

# Chapters per book (Hebrew chapter numbering, as on Sefaria). Live
# discovery only finds where a book ends by probing for the chapter after
# it, so this guards against a book being cut short by a failed request:
# a discovered or cached structure with a different chapter count is not
# trusted. Verse counts per chapter still come from Sefaria.
NON_TORAH_CHAPTER_COUNTS = {
    "Joshua": 24, "Judges": 21, "I Samuel": 31, "II Samuel": 24, "I Kings": 22, "II Kings": 25,
    "Isaiah": 66, "Jeremiah": 52, "Ezekiel": 48,
    "Hosea": 14, "Joel": 4, "Amos": 9, "Obadiah": 1, "Jonah": 4, "Micah": 7, "Nahum": 3,
    "Habakkuk": 3, "Zephaniah": 3, "Haggai": 2, "Zechariah": 14, "Malachi": 3,
    "Song of Songs": 8, "Ruth": 4, "Lamentations": 5, "Ecclesiastes": 12, "Esther": 10,
}

# Category -> ordered book list, the single source of truth the frontend
# uses to build a grouped book picker (Tora / Nevi'im / Megillot
# optgroups) and that ALL_BOOKS is derived from.
BOOK_CATEGORIES = {
    "Tora": list(TORAH_BOOKS.keys()),
    "Nevi'im": NEVIIM_BOOKS,
    "Megillot": MEGILLOT_BOOKS,
}

ALL_BOOKS = [book for books in BOOK_CATEGORIES.values() for book in books]

# How each book is written in the app (see docs/transliteration.md): in a
# note's Source field, on card titles, and (Tora only) in tags.
BOOK_HEBREW_NAMES = {
    "Genesis": "Bereshit",
    "Exodus": "Shemot",
    "Leviticus": "Vayyiqra",
    "Numbers": "Bemidbar",
    "Deuteronomy": "Devarim",
    "Joshua": "Yehoshua'",
    "Judges": "Shofetim",
    "I Samuel": "Shemuel Alef",
    "II Samuel": "Shemuel Bet",
    "I Kings": "Melakhim Alef",
    "II Kings": "Melakhim Bet",
    "Isaiah": "Yesha'yahu",
    "Jeremiah": "Yirmeyahu",
    "Ezekiel": "Yeḥezqel",
    "Hosea": "Hoshea'",
    "Joel": "Yo'el",
    "Amos": "'Amos",
    "Obadiah": "'Ovadya",
    "Jonah": "Yona",
    "Micah": "Mikha",
    "Nahum": "Naḥum",
    "Habakkuk": "Ḥavaqquq",
    "Zephaniah": "Tsefanya",
    "Haggai": "Ḥaggai",
    "Zechariah": "Zekharya",
    "Malachi": "Mal'akhi",
    "Song of Songs": "Shir haShirim",
    "Ruth": "Rut",
    "Lamentations": "Ekha",
    "Ecclesiastes": "Qohelet",
    "Esther": "Ester",
}

# The same books in Hebrew script, shown next to the transliteration in
# the app's book pickers. Display only: nothing is stored under these.
BOOK_HEBREW_SCRIPT_NAMES = {
    "Genesis": "בראשית",
    "Exodus": "שמות",
    "Leviticus": "ויקרא",
    "Numbers": "במדבר",
    "Deuteronomy": "דברים",
    "Joshua": "יהושע",
    "Judges": "שופטים",
    "I Samuel": "שמואל א׳",
    "II Samuel": "שמואל ב׳",
    "I Kings": "מלכים א׳",
    "II Kings": "מלכים ב׳",
    "Isaiah": "ישעיהו",
    "Jeremiah": "ירמיהו",
    "Ezekiel": "יחזקאל",
    "Hosea": "הושע",
    "Joel": "יואל",
    "Amos": "עמוס",
    "Obadiah": "עובדיה",
    "Jonah": "יונה",
    "Micah": "מיכה",
    "Nahum": "נחום",
    "Habakkuk": "חבקוק",
    "Zephaniah": "צפניה",
    "Haggai": "חגי",
    "Zechariah": "זכריה",
    "Malachi": "מלאכי",
    "Song of Songs": "שיר השירים",
    "Ruth": "רות",
    "Lamentations": "איכה",
    "Ecclesiastes": "קהלת",
    "Esther": "אסתר",
}

# Spellings used before docs/transliteration.md. Notes created with them
# (their Source field is fixed text) must still be recognized, so the
# tagger accepts these too -- see anki_connect.tagging.HEBREW_TO_BOOK.
LEGACY_BOOK_HEBREW_NAMES = {
    "Leviticus": "Vayikra",
    "Numbers": "Bamidbar",
    "Joshua": "Yehoshua",
    "Judges": "Shoftim",
    "I Samuel": "Shmuel Alef",
    "II Samuel": "Shmuel Bet",
    "I Kings": "Melachim Alef",
    "II Kings": "Melachim Bet",
    "Isaiah": "Yeshayahu",
    "Jeremiah": "Yirmiyahu",
    "Ezekiel": "Yechezkel",
    "Hosea": "Hoshea",
    "Joel": "Yoel",
    "Amos": "Amos",
    "Obadiah": "Ovadiah",
    "Jonah": "Yonah",
    "Micah": "Michah",
    "Nahum": "Nachum",
    "Habakkuk": "Chavakuk",
    "Zephaniah": "Tzefaniah",
    "Haggai": "Chaggai",
    "Zechariah": "Zechariah",
    "Malachi": "Malachi",
    "Song of Songs": "Shir HaShirim",
    "Lamentations": "Eichah",
    "Ecclesiastes": "Kohelet",
    "Esther": "Esther",
}


# Example Anki deck names for the qeriya scheduling automation (ankipasuk.anki_connect),
# one per book of the Tora, in reading order.
QERIYA_DECK_NAMES = {
    "Genesis": "Qeriya::1-Bereshit",
    "Exodus": "Qeriya::2-Shemot",
    "Leviticus": "Qeriya::3-Vayyiqra",
    "Numbers": "Qeriya::4-Bemidbar",
    "Deuteronomy": "Qeriya::5-Devarim",
}

# =============================================================
#  ANKI EXPORT
# =============================================================
CSV_FLAGS = "1,0,false,true,false,true"

# =============================================================
#  TA'AMIM: UNICODE -> NAME AND RANK
# =============================================================
# name, disjunctive rank (1 = strongest / verse-final, 4 = weakest; 0 = mesharet)
#
# The names shown to the user are the Sephardi names, following the table
# in Wikipedia's "Hebrew cantillation" article. Unicode's own character
# names (and the identifiers in this package that follow them, such as
# MUNACH below or text_processing.adjust_for_munach_legarmeh) use the
# other naming, which has a few false friends -- go by the codepoint, not
# the name:
#
#   U+0599  Unicode "PASHTA"  -> Qadma
#   U+05A8  Unicode "QADMA"   -> Azla
#   U+0591  Unicode "ETNAHTA" -> Atnaḥ
#   U+0596  Unicode "TIPEHA"  -> Tarḥa
#   U+05A3  Unicode "MUNAH"   -> Shofar holekh
#   U+05A5  Unicode "MERKHA"  -> Ma'arikh
#   U+05A4  Unicode "MAHAPAKH" -> Shofar mehuppakh
#   U+05C0  Unicode "PASEQ"   -> the vertical stroke, see below
#
# The vertical stroke after a shofar holekh is either part of a mafsiq or
# only a pause, and only its position tells which (the rule is in
# text_processing.adjust_for_munach_legarmeh):
#
#   - Part of a mafsiq: named Paseq here (LEGARMEH_NAME), rank 4. That's
#     the Sephardi name in the Wikipedia table; the Ashkenazi name is
#     munach legarmeh.
#   - Only a pause after a mesharet: the word stays rank 0. The Ashkenazi
#     name is pasek (munach pasek). No separate established Sephardi name
#     for this was found. "Pesiq" in the table below is AnkiPasuk's own
#     label, used only to keep the two apart in code; rank-0 names are
#     never shown in the app.
#
# Zarqa and tsinnorit: Unicode's names for these two codepoints are
# swapped (Unicode Technical Note #27). Zarqa is encoded as U+05AE, whose
# Unicode name is "ZINOR", and tsinnorit as U+0598, whose Unicode name is
# "ZARQA". Sefaria's text follows that encoding, so U+05AE is listed here
# as Zarqa and U+0598 is deliberately not listed at all: tsinnorit only
# decorates a mesharet and doesn't change the word's rank. Don't "fix"
# this by swapping the two.
TROPE_UNICODE = {
    "\u05C3": ("Sof pasuq", 1),
    "\u0591": ("Atnaḥ", 1),
    "\u0592": ("Segolta", 2),
    "\u0593": ("Shalshelet", 2),
    "\u0594": ("Zaqef qaton", 2),
    "\u0595": ("Zaqef gadol", 2),
    "\u0596": ("Tarḥa", 2),
    "\u0597": ("Ravia'", 3),
    "\u05AE": ("Zarqa", 3),
    "\u0599": ("Qadma", 3),
    "\u059A": ("Yetiv", 3),
    "\u059B": ("Tevir", 3),
    "\u05A0": ("Talsha", 4),
    "\u059C": ("Gerish", 4),
    "\u059E": ("Shene gerishin", 4),
    "\u05A1": ("Pazer gadol", 4),
    "\u05C0": ("Pesiq", 0),
    "\u05A5": ("Ma'arikh", 0),
    "\u05A3": ("Shofar holekh", 0),
    "\u05A4": ("Shofar mehuppakh", 0),
    "\u05A7": ("Darga", 0),
    "\u05A8": ("Azla", 0),
    "\u05A9": ("Tarsa", 0),
}

# The name a shofar holekh + stroke pair takes once it's read as a mafsiq
# (Ashkenazi: munach legarmeh) -- see the stroke note above and
# text_processing.adjust_for_munach_legarmeh.
LEGARMEH_NAME = "Paseq"

# The mafsiqim in Hebrew, as the diagram labels them (see ankipasuk.diagram):
# the Sephardi names, matching the transliterations above.
TROPE_HEBREW_NAMES = {
    "Sof pasuq": "סוף פסוק", "Atnaḥ": "אתנח",
    "Segolta": "סגולתא", "Shalshelet": "שלשלת", "Tarḥa": "טרחא",
    "Zaqef qaton": "זקף קטן", "Zaqef gadol": "זקף גדול",
    "Ravia'": "רביע", "Tevir": "תביר", "Qadma": "קדמא", "Yetiv": "יתיב", "Zarqa": "זרקא",
    "Gerish": "גריש", "Shene gerishin": "שני גרישין", "Pazer gadol": "פזר גדול",
    "Talsha": "תלשא", "Paseq": "פסק",
}

MAKEF = "\u05BE"
MUNACH = "\u05A3"
PASEQ = "\u05C0"

# --- Bidi helpers (force RTL rendering of Hebrew inside tk.Text widgets) ---
RLE = "\u202B"
PDF = "\u202C"

# Fonts that render the ta'amim (cantillation combining marks) well, most
# to least capable. Proper ta'am stacking is a much narrower font
# requirement than plain Hebrew support -- most system-default fonts (and
# Tk's silent substitute when none of these are installed) will show
# niqqud/ta'amim crowding or overlap. See gui.fonts.pick_hebrew_font, which
# picks the first of these actually installed, falling back to Tk's
# default if none are. For the best rendering, install one of the first
# three (all free): SBL Hebrew, Ezra SIL, or a Taamey Torah font from
# https://www.keyman.com/keyboards/taameyfrankcn or https://software.sil.org/ezra/.
HEBREW_FONT_CANDIDATES = [
    "SBL Hebrew",
    "Ezra SIL",
    "Taamey Frank CLM",
    "Taamey Ashkenaz",
    "Cardo",
    "Noto Serif Hebrew",
    "Noto Sans Hebrew",
    "Times New Roman",
    "David",
    "Arial",
]

# =============================================================
#  VISUALIZATION
# =============================================================
INDENT_SPACES_PER_LEVEL = 2
GUIDE_BG = "#eceff1"
UNIT_COLORS = ["#fff9c4", "#bbdefb", "#c8e6c9", "#f8bbd0", "#e1bee7"]
INDENT_UNIT_PX = 14
