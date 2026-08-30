"""Local, on-disk cache for data fetched from the Sefaria API.

Sefaria verse text and parashah structure don't change, so once a (ref,
version) pair or a book's parashah layout has been fetched it's safe to
reuse it forever. Caching it on disk (not just in memory) means the app
doesn't have to re-fetch the same range from the network every time it is
launched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CACHE_FORMAT_VERSION = 1


def default_cache_dir() -> Path:
    """Return the platform-appropriate directory to store the cache in.

    Honors ``ANKIPASUK_CACHE_DIR`` if set (handy for tests / custom setups),
    otherwise follows the usual per-OS convention.
    """
    override = os.environ.get("ANKIPASUK_CACHE_DIR")
    if override:
        return Path(override)

    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
        return Path(base) / "AnkiPasuk"

    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "ankipasuk"


class SefariaCache:
    """A small JSON-backed cache for Sefaria text and parashah-structure
    lookups.

    Entries are held in memory for the lifetime of the instance and written
    through to disk on every write, so a fresh instance pointed at the same
    ``cache_dir`` immediately sees everything a previous run fetched.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
        self.text_path = self.cache_dir / "text_cache.json"
        self.parasha_path = self.cache_dir / "parasha_cache.json"
        self._text_cache: dict = {}
        self._parasha_cache: dict = {}
        self._load()

    # --- persistence ----------------------------------------------------
    def _load(self) -> None:
        self._text_cache = self._read_json(self.text_path) or {}
        self._parasha_cache = self._read_json(self.parasha_path) or {}

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # A corrupted or unreadable cache file should never crash the
            # app -- just treat it as empty and let it be rebuilt.
            return None
        if isinstance(data, dict) and data.get("_version") == CACHE_FORMAT_VERSION:
            return data.get("entries", {})
        return None

    @staticmethod
    def _write_json_atomic(path: Path, entries: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload = {"_version": CACHE_FORMAT_VERSION, "entries": entries}
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp_path, path)  # atomic on POSIX and Windows

    def _save_text(self) -> None:
        self._write_json_atomic(self.text_path, self._text_cache)

    def _save_parasha(self) -> None:
        self._write_json_atomic(self.parasha_path, self._parasha_cache)

    # --- verse text cache -------------------------------------------------
    @staticmethod
    def _text_key(ref_str: str, version_param: str) -> str:
        return f"{version_param}::{ref_str}"

    def get_text(self, ref_str: str, version_param: str):
        """Return the cached, cleaned verse list for (ref, version), or
        None if it hasn't been fetched before."""
        return self._text_cache.get(self._text_key(ref_str, version_param))

    def set_text(self, ref_str: str, version_param: str, cleaned_text) -> None:
        self._text_cache[self._text_key(ref_str, version_param)] = cleaned_text
        self._save_text()

    # --- parashah-structure cache ------------------------------------------
    def get_parasha_structure(self, book: str):
        return self._parasha_cache.get(book)

    def set_parasha_structure(self, book: str, structure) -> None:
        self._parasha_cache[book] = structure
        self._save_parasha()

    # --- maintenance --------------------------------------------------------
    def clear(self) -> None:
        """Forget everything, both in memory and on disk."""
        self._text_cache = {}
        self._parasha_cache = {}
        for path in (self.text_path, self.parasha_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def stats(self) -> dict:
        return {
            "cached_refs": len(self._text_cache),
            "cached_books": len(self._parasha_cache),
            "location": str(self.cache_dir),
        }
