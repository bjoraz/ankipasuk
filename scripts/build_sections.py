"""Make the Masoretic sections data the app ships with
(src/ankipasuk/data/sections.json.gz) from Sefaria's Miqra according to
the Masorah -- see ankipasuk.sections.

Needs the network: fetches every chapter of the Tora, the Nevi'im and the
Megillot (about 600 requests) from Sefaria's API, keeping each answer in
--cache (a temporary folder by default) so a rerun fetches nothing again.
Only needed when updating that data:

    python scripts/build_sections.py [--cache DIR]
"""

import argparse
import gzip
import json
import sys
import tempfile
import time
from pathlib import Path

import _bootstrap  # noqa: F401  (sets up sys.path if not pip-installed)
import requests

from ankipasuk.config import (
    ALL_BOOKS,
    NON_TORAH_CHAPTER_COUNTS,
    POINTED_VERSION,
    SEFARIA_API_BASE,
    TORAH_VERSE_COUNTS,
)
from ankipasuk.sections import DATA, breaks_in, one_section


def chapter(book: str, ch: int, cache: Path) -> list[str]:
    path = cache / f"{book}.{ch}.json"
    if not path.exists():
        for attempt in range(4):
            try:
                url = f"{SEFARIA_API_BASE}/{requests.utils.quote(f'{book} {ch}', safe='')}"
                resp = requests.get(url, params={"version": POINTED_VERSION, "return_format": "text_only"},
                                    timeout=60)
                resp.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        path.write_text(resp.text, encoding="utf-8")
        time.sleep(0.1)  # gently
    return json.loads(path.read_text(encoding="utf-8"))["versions"][0]["text"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="folder to keep Sefaria's answers in")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        cache = args.cache or Path(tmp)
        cache.mkdir(parents=True, exist_ok=True)
        table: dict[str, dict[str, list]] = {}
        for book in ALL_BOOKS:
            chapters = (len(TORAH_VERSE_COUNTS[book]) if book in TORAH_VERSE_COUNTS
                        else NON_TORAH_CHAPTER_COUNTS[book])
            found = {}
            for ch in range(1, chapters + 1):
                for vs, raw in enumerate(chapter(book, ch, cache), start=1):
                    marks = breaks_in(raw) if isinstance(raw, str) else []
                    if marks:
                        found[f"{ch}:{vs}"] = marks
            table[book] = found = one_section(book, found)
            kinds = [m if isinstance(m, str) else m[0] for ms in found.values() for m in ms]
            print(f"{book}: {kinds.count('P')} petuḥot, {kinds.count('S')} setumot")
    raw = json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # A fixed mtime, so rebuilding unchanged data gives identical files.
    with open(DATA, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
        gz.write(raw)
    print(f"-> {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
