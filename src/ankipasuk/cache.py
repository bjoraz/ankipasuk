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
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

CACHE_FORMAT_VERSION = 1

# How many times to retry an atomic file replace before giving up -- see
# _write_json_atomic's docstring for why this is needed at all.
_REPLACE_MAX_ATTEMPTS = 6
_REPLACE_BASE_DELAY_SECONDS = 0.05


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
    through to disk on every write (unless inside a :meth:`defer_saves`
    block), so a fresh instance pointed at the same ``cache_dir``
    immediately sees everything a previous run fetched.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
        self.text_path = self.cache_dir / "text_cache.json"
        self.parasha_path = self.cache_dir / "parasha_cache.json"
        self.book_structure_path = self.cache_dir / "book_structure_cache.json"
        self._text_cache: dict = {}
        self._parasha_cache: dict = {}
        self._book_structure_cache: dict = {}
        self._defer_depth = 0  # >0 while inside a defer_saves() block
        self._dirty: set[str] = set()  # which cache(s) changed since the last flush, while deferred
        self._load()

    # --- persistence ----------------------------------------------------
    def _load(self) -> None:
        self._text_cache = self._read_json(self.text_path) or {}
        self._parasha_cache = self._read_json(self.parasha_path) or {}
        self._book_structure_cache = self._read_json(self.book_structure_path) or {}

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

    @contextmanager
    def defer_saves(self):
        """Suppress the normal write-through-to-disk-on-every-write
        behavior for the duration of the block, flushing once at the end
        instead (even if the block raises) -- and only for whichever of
        the three caches were actually written to during the block, not
        all three unconditionally.

        For call sites that make many small writes in a tight loop --
        fetching or probing a book many chapters at a time -- writing the
        whole cache file to disk after EVERY single entry is both
        wasteful (one JSON dump of the entire cache per chapter, when one
        dump at the end would do) and, on Windows specifically, can
        trigger a transient PermissionError ("being used by another
        process") if something else -- commonly antivirus real-time
        scanning, or a cloud-sync client -- briefly holds a handle on the
        just-written file before the next write tries to replace it
        again moments later. Writing once at the end instead of dozens of
        times removes nearly all of that exposure, on top of
        _write_json_atomic's own retry as a second line of defense.

        Reentrant: nested defer_saves() blocks only flush once, when the
        outermost one exits, so a function that itself calls another
        defer_saves()-wrapped function doesn't flush twice.
        """
        self._defer_depth += 1
        try:
            yield
        finally:
            self._defer_depth -= 1
            if self._defer_depth == 0:
                self._flush_dirty()

    def _flush_dirty(self) -> None:
        if "text" in self._dirty:
            self._write_json_atomic(self.text_path, self._text_cache)
        if "parasha" in self._dirty:
            self._write_json_atomic(self.parasha_path, self._parasha_cache)
        if "book_structure" in self._dirty:
            self._write_json_atomic(self.book_structure_path, self._book_structure_cache)
        self._dirty.clear()

    @staticmethod
    def _write_json_atomic(path: Path, entries: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"_version": CACHE_FORMAT_VERSION, "entries": entries}
        # A unique temp filename per call -- not a fixed "<name>.tmp" --
        # so that even if two writes to the same path somehow overlap in
        # time, they can never race over the SAME temp file (one call's
        # os.replace consuming/renaming the very file another call is
        # mid-write to, which surfaces as a confusing FileNotFoundError
        # rather than the more obvious PermissionError).
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        # os.replace is documented as atomic on both POSIX and Windows,
        # but on Windows specifically it can transiently fail with a
        # sharing-violation PermissionError (WinError 32) if something
        # else -- commonly antivirus real-time scanning, or a cloud-sync
        # client like OneDrive -- briefly holds a handle on the
        # destination file right after a previous write touched it. That
        # lock is transient by nature (whatever's holding it releases
        # within milliseconds), so a short retry-with-backoff resolves it
        # silently rather than crashing the whole app on what is, in
        # practice, a common Windows environment interaction and not a
        # real failure -- confirmed against a real crash report showing
        # exactly this error, repeatedly, during rapid sequential writes.
        last_error = None
        for attempt in range(_REPLACE_MAX_ATTEMPTS):
            try:
                os.replace(tmp_path, path)
                return
            except OSError as e:
                last_error = e
                time.sleep(_REPLACE_BASE_DELAY_SECONDS * (2**attempt))
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise last_error

    def _save_text(self) -> None:
        if self._defer_depth:
            self._dirty.add("text")
            return
        self._write_json_atomic(self.text_path, self._text_cache)

    def _save_parasha(self) -> None:
        if self._defer_depth:
            self._dirty.add("parasha")
            return
        self._write_json_atomic(self.parasha_path, self._parasha_cache)

    def _save_book_structure(self) -> None:
        if self._defer_depth:
            self._dirty.add("book_structure")
            return
        self._write_json_atomic(self.book_structure_path, self._book_structure_cache)

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

    # --- book-structure cache (per-chapter verse counts) --------------------
    # Used for books without a hardcoded TORAH_VERSE_COUNTS-style table
    # (all of Nevi'im and the Megillot) -- discovered live once by probing
    # Sefaria chapter by chapter (see sefaria.discover_book_structure),
    # then cached here so every subsequent use -- even in a later app
    # run -- is instant, no re-probing needed.
    def get_book_structure(self, book: str):
        return self._book_structure_cache.get(book)

    def set_book_structure(self, book: str, chapter_lengths) -> None:
        self._book_structure_cache[book] = chapter_lengths
        self._save_book_structure()

    # --- maintenance --------------------------------------------------------
    def clear(self) -> None:
        """Forget everything, both in memory and on disk."""
        self._text_cache = {}
        self._parasha_cache = {}
        self._book_structure_cache = {}
        for path in (self.text_path, self.parasha_path, self.book_structure_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def stats(self) -> dict:
        return {
            "cached_refs": len(self._text_cache),
            "cached_books": len(self._parasha_cache),
            "cached_book_structures": len(self._book_structure_cache),
            "location": str(self.cache_dir),
        }
