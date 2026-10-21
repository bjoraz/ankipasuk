"""AnkiPasuk: Anki cards for reading from the sefer -- nested cloze cards
split along the ta'amim, and tiqqun cards laid out as in the sefer -- and
the text's shorashim and recurring phrases.

The package is split into a GUI-free core (config, cache, sefaria,
text_processing, cloze, stats, structure, qeriya, tikkun, shorashim,
phrases, ...) and a web GUI (ankipasuk.webgui) built on top of it. The
core has no GUI dependency, so it can be imported, tested, or scripted
without a display.
"""

__version__ = "0.2.0"  # also the package's (pyproject.toml reads it); see CHANGELOG.md
