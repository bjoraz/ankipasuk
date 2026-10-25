"""Make the semantic data the app ships with (src/ankipasuk/data/semantics/)
from the UBS Dictionary of Biblical Hebrew (the open SDBH) and the Open
Scriptures Hebrew Bible -- see ankipasuk.semantics_build.

Needs the network once: downloads SDBH's dictionary and domains (about
25 MB) and OSHB's books (about 40 MB) into a temporary folder, unless
--source names a folder that already has them (SDBH's JSON files, and
morphhb's wlc/*.xml, side by side). Prints how well the two lined up.
Only needed when updating that data:

    python scripts/build_semantics.py [--source DIR]
"""

import argparse
import gzip
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)

from ankipasuk.semantics_build import Report, book_senses, domain_table, read_sdbh
from ankipasuk.shorashim_build import OSIS_BOOKS, REFERENCE_BOOKS

SDBH = "https://raw.githubusercontent.com/ubsicap/ubs-open-license/main/dictionaries/hebrew/JSON/{}"
VERSION = "0.9.4"
DICTIONARY = f"UBSHebrewDic-v{VERSION}-en.JSON"
DOMAINS = f"UBSHebrewDicLexicalDomains-v{VERSION}-en.JSON"
MORPHHB = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/{}.xml"
OUT = Path(__file__).resolve().parent.parent / "src" / "ankipasuk" / "data" / "semantics"


def fetch(url: str, path: Path) -> str:
    if not path.exists():
        print(f"  downloading {url}")
        with urllib.request.urlopen(url, timeout=300) as response:
            path.write_bytes(response.read())
    return path.read_text(encoding="utf-8-sig")


def write_gz(path: Path, data) -> None:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # A fixed mtime, so rebuilding unchanged data gives identical files.
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
        gz.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, help="folder with SDBH's and OSHB's files already downloaded")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        src = args.source or Path(tmp)
        senses = read_sdbh(json.loads(fetch(SDBH.format(DICTIONARY), src / DICTIONARY)))
        domains = domain_table(json.loads(fetch(SDBH.format(DOMAINS), src / DOMAINS)))
        OUT.mkdir(parents=True, exist_ok=True)
        report = Report()
        for book, osis in [*OSIS_BOOKS.items(), *REFERENCE_BOOKS.items()]:
            path = src / "wlc" / f"{osis}.xml"
            if not path.exists():
                path = src / f"{osis}.xml"
            xml = fetch(MORPHHB.format(osis), path)
            before = report.words["with a sense"], sum(report.words.values())
            write_gz(OUT / f"{osis}.json.gz", book_senses(xml, osis, senses, report))
            got, of = report.words["with a sense"] - before[0], sum(report.words.values()) - before[1]
            print(f"{book}: {got:,} of {of:,} words with a sense ({100 * got / max(of, 1):.1f}%)")
        write_gz(OUT / "senses.json.gz", {"version": VERSION, "domains": domains, "senses": senses.table})
        print("\n".join(report.lines()))
        print(f"{len(senses.table):,} senses, {len(domains)} domains -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
