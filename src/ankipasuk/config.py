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
#  TORAH STRUCTURE
# =============================================================
TORAH_VERSE_COUNTS = {
    "Genesis": [
        31, 25, 24, 26, 32, 22, 24, 22, 29, 32,
        32, 20, 18, 24, 21, 16, 27, 33, 38, 18,
        34, 24, 20, 67, 34, 35, 46, 22, 35, 43,
        55, 32, 20, 31, 29, 43, 36, 30, 23, 23,
        57, 38, 34, 34, 28, 34, 31, 22, 33, 26
    ],
    "Exodus": [
        22, 25, 22, 31, 23, 30, 25, 32, 35, 29,
        10, 51, 22, 31, 27, 36, 16, 27, 25, 26,
        36, 31, 33, 18, 40, 37, 21, 43, 46, 38,
        18, 35, 23, 35, 35, 38, 29, 31, 43, 38
    ],
    "Leviticus": [
        17, 16, 17, 35, 19, 30, 38, 36, 24, 20,
        47, 8, 59, 57, 33, 34, 16, 30, 37, 27,
        24, 33, 44, 23, 55, 46, 34
    ],
    "Numbers": [
        54, 34, 51, 49, 31, 27, 89, 26, 23, 36,
        35, 16, 33, 45, 41, 50, 13, 32, 22, 29,
        35, 41, 30, 25, 18, 65, 23, 31, 39, 17,
        54, 42, 56, 29, 34, 13
    ],
    "Deuteronomy": [
        46, 37, 29, 49, 33, 25, 26, 20, 29, 22,
        32, 32, 18, 29, 23, 22, 20, 22, 21, 20,
        23, 30, 25, 22, 19, 19, 26, 69, 28, 20,
        30, 52, 29, 12
    ],
}

# Chapter counts per book, derived from TORAH_VERSE_COUNTS so the two never
# drift out of sync.
TORAH_BOOKS = {book: len(verses) for book, verses in TORAH_VERSE_COUNTS.items()}

BOOK_HEBREW_NAMES = {
    "Genesis": "Bereshit",
    "Exodus": "Shemot",
    "Leviticus": "Vayikra",
    "Numbers": "Bamidbar",
    "Deuteronomy": "Devarim",
}

# =============================================================
#  ANKI EXPORT
# =============================================================
CSV_FLAGS = "1,0,false,true,false,true"

# =============================================================
#  TROPE UNICODE HIERARCHY
# =============================================================
# name, disjunctive rank (1 = strongest / verse-final, 4 = weakest; 0 = conjunctive)
TROPE_UNICODE = {
    "\u05C3": ("Sof pasuq", 1),
    "\u0591": ("Etnachta", 1),
    "\u0592": ("Segol", 2),
    "\u0593": ("Shalshelet", 2),
    "\u0594": ("Zakef katan", 2),
    "\u0595": ("Zakef gadol", 2),
    "\u0596": ("Tifcha", 2),
    "\u0597": ("Revia", 3),
    "\u05AE": ("Zarka", 3),
    "\u0599": ("Pashta", 3),
    "\u059A": ("Yetiv", 3),
    "\u059B": ("Tevir", 3),
    "\u05A0": ("Telisha gedola", 4),
    "\u059C": ("Geresh", 4),
    "\u059E": ("Gershayim", 4),
    "\u05A1": ("Pazer", 4),
    "\u05C0": ("Paseq", 0),
    "\u05A5": ("Mercha", 0),
    "\u05A3": ("Munach", 0),
    "\u05A4": ("Mahpach", 0),
    "\u05A7": ("Darga", 0),
    "\u05A8": ("Kadma", 0),
    "\u05A9": ("Telisha ketana", 0),
}

MAKEF = "\u05BE"
MUNACH = "\u05A3"
PASEQ = "\u05C0"

# --- Bidi helpers (force RTL rendering of Hebrew inside tk.Text widgets) ---
RLE = "\u202B"
PDF = "\u202C"

# =============================================================
#  VISUALIZATION
# =============================================================
INDENT_SPACES_PER_LEVEL = 2
GUIDE_BG = "#eceff1"
UNIT_COLORS = ["#fff9c4", "#bbdefb", "#c8e6c9", "#f8bbd0", "#e1bee7"]
INDENT_UNIT_PX = 14
