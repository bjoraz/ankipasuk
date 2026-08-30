"""AnkiPasuk: generate nested Anki cloze cards from Torah trope structure.

The package is split into a GUI-free core (config, cache, sefaria,
text_processing, cloze, stats) and a tkinter GUI (ankipasuk.gui) built on
top of it. The core has no GUI dependency, so it can be imported, tested,
or scripted without a display.
"""

__version__ = "0.1.0"
