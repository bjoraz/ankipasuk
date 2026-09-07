"""A tiny JSON-backed store for GUI preferences (e.g. the last-used Anki
deck name) that should persist across app restarts.

Kept separate from :class:`~ankipasuk.cache.SefariaCache`, which is
specifically for Sefaria/tikkun.io network data, not user preferences.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .cache import default_cache_dir

_REPLACE_MAX_ATTEMPTS = 6
_REPLACE_BASE_DELAY_SECONDS = 0.05


class Settings:
    """Loaded once at construction, written through to disk on every
    :meth:`set` -- there's no high-frequency write path here (unlike
    SefariaCache's per-verse caching), so no batching/deferral is needed.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.path = (Path(cache_dir) if cache_dir is not None else default_cache_dir()) / "settings.json"
        self._data = self._read()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # A corrupted or unreadable settings file should never crash
            # the app -- just fall back to defaults.
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # A unique temp filename per call, then an atomic replace -- same
        # approach (and same Windows sharing-violation retry) as
        # SefariaCache._write_json_atomic; see that docstring for why.
        tmp_path = self.path.with_name(f"{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)

        last_error = None
        for attempt in range(_REPLACE_MAX_ATTEMPTS):
            try:
                os.replace(tmp_path, self.path)
                return
            except OSError as e:
                last_error = e
                time.sleep(_REPLACE_BASE_DELAY_SECONDS * (2**attempt))
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise last_error
