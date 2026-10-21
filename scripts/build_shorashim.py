"""Make the shorashim and phrase data the app ships with
(src/ankipasuk/data/shorashim/ and phrases/) from the Open Scriptures
Hebrew Bible -- see ankipasuk.shorashim_build.

Needs the network once: downloads OSHB's books and lexicon from GitHub
(about 40 MB) into a temporary folder, unless --source names a folder that
already has them (morphhb's wlc/*.xml and HebrewLexicon's
LexicalIndex.xml, side by side). Only needed when updating that data:

    python scripts/build_shorashim.py [--source DIR]
"""

import argparse
import gzip
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.shorashim_build import (
    OSIS_BOOKS,
    REFERENCE_BOOKS,
    Grouper,
    Lemmas,
    book_lemmas,
    book_words,
    parse_lexicon,
    peoples,
)

MORPHHB = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/{}.xml"
LEXICON = "https://raw.githubusercontent.com/openscriptures/HebrewLexicon/master/LexicalIndex.xml"
DATA = Path(__file__).resolve().parent.parent / "src" / "ankipasuk" / "data"
OUT, PHRASES = DATA / "shorashim", DATA / "phrases"


def fetch(url: str, path: Path) -> str:
    if not path.exists():
        print(f"  downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    return path.read_text(encoding="utf-8")


def write_gz(path: Path, data) -> None:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # A fixed mtime, so rebuilding unchanged data gives identical files.
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
        gz.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, help="folder with the OSHB files already downloaded")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        src = args.source or Path(tmp)
        books = [*OSIS_BOOKS.items(), *REFERENCE_BOOKS.items()]
        xml = {osis: fetch(MORPHHB.format(osis), src / f"{osis}.xml") for _book, osis in books}
        entries = parse_lexicon(fetch(LEXICON, src / "LexicalIndex.xml"))
        grouper = Grouper(entries, peoples(Grouper(entries), xml.values()))
        lemmas = Lemmas(grouper)
        OUT.mkdir(parents=True, exist_ok=True)
        PHRASES.mkdir(parents=True, exist_ok=True)
        words = 0
        # The app's books first: they make the groups. Then the rest of the
        # Tanakh, only counted (each group's total; a word of a group they
        # don't have has none).
        for book, osis in books:
            grouper.reference = book in REFERENCE_BOOKS
            verses = book_words(xml[osis], osis, grouper)
            write_gz(OUT / f"{osis}.json.gz", verses)
            write_gz(PHRASES / f"{osis}.json.gz", book_lemmas(xml[osis], osis, lemmas))
            n = sum(len(w) for w in verses.values())
            words += n
            print(f"{book}: {len(verses)} pesuqim, {n} words")
        write_gz(OUT / "groups.json.gz", {"words": grouper.words, "groups": grouper.table()})
        write_gz(PHRASES / "lemmas.json.gz", lemmas.table)
        print(f"{words} words; {len(grouper.groups)} groups, {len(lemmas.table)} dictionary words -> {DATA}")
        print(f"{grouper.words} words with a group in the Tanakh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
