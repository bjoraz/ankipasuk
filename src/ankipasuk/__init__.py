"""AnkiPasuk: Anki cards for reading from the sefer -- nested cloze cards
split along the ta'amim, and tiqqun cards laid out as in the sefer.

The package is split into a GUI-free core (config, cache, sefaria,
text_processing, cloze, stats, structure, qeriya, tikkun, ...) and a
web GUI (ankipasuk.webgui) built on top of it. The core has no GUI dependency, so it can be imported, tested,
or scripted without a display.
"""

__version__ = "0.1.0"
