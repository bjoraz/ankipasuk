"""Make the shorashim data the app ships with (src/ankipasuk/data/shorashim/)
from the Open Scriptures Hebrew Bible -- see ankipasuk.shorashim_build.

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

from ankipasuk.shorashim_build import OSIS_BOOKS, REFERENCE_BOOKS, Grouper, book_words, parse_lexicon

MORPHHB = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/{}.xml"
LEXICON = "https://raw.githubusercontent.com/openscriptures/HebrewLexicon/master/LexicalIndex.xml"
OUT = Path(__file__).resolve().parent.parent / "src" / "ankipasuk" / "data" / "shorashim"


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
        grouper = Grouper(parse_lexicon(fetch(LEXICON, src / "LexicalIndex.xml")))
        OUT.mkdir(parents=True, exist_ok=True)
        words = 0
        for book, osis in OSIS_BOOKS.items():
            verses = book_words(fetch(MORPHHB.format(osis), src / f"{osis}.xml"), osis, grouper)
            write_gz(OUT / f"{osis}.json.gz", verses)
            n = sum(len(w) for w in verses.values())
            words += n
            print(f"{book}: {len(verses)} pesuqim, {n} words")
        # The rest of the Tanakh, only counted (each group's total).
        grouper.reference = True
        for osis in REFERENCE_BOOKS:
            book_words(fetch(MORPHHB.format(osis), src / f"{osis}.xml"), osis, grouper)
        write_gz(OUT / "groups.json.gz", {"words": grouper.words, "groups": grouper.table()})
        print(f"{words} words in {len(grouper.groups)} groups -> {OUT}")
        print(f"{grouper.words} words with a group in the Tanakh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
