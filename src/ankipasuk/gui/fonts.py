"""Hebrew font detection for Tk widgets.

Tk silently substitutes an unrelated font whenever a named font isn't
installed, with no warning and often much worse trope/niqud-mark
rendering than a font actually built for it -- so rather than hardcoding
one font name and hoping it's present, this picks the best available one
from :data:`ankipasuk.config.HEBREW_FONT_CANDIDATES` at runtime.
"""

from __future__ import annotations

import tkinter.font as tkfont
from functools import lru_cache

from ..config import HEBREW_FONT_CANDIDATES


@lru_cache(maxsize=1)
def pick_hebrew_font() -> str:
    """The first font in ``HEBREW_FONT_CANDIDATES`` actually installed,
    or the last (most widely available) candidate if none are found.

    Requires a live Tk root to already exist (font family lookup is a Tk
    operation), so this is only called from within GUI code, never at
    import time. Cached for the process lifetime -- installed fonts don't
    change mid-run.
    """
    available = {f.lower() for f in tkfont.families()}
    for candidate in HEBREW_FONT_CANDIDATES:
        if candidate.lower() in available:
            return candidate
    return HEBREW_FONT_CANDIDATES[-1]
