"""The Fields pane's calls (see ankipasuk.semantics): a passage's semantic
fields, and their settings (the level the fields are compared at, kept
in the saved settings as ``"fields"``)."""

from __future__ import annotations

import traceback

from ..semantics import DEFAULT_LEVEL, LEVELS, levels, passage, saved_level
from ..settings import Settings


class FieldApi:
    """Mixed into a bridge that gives its loaded pesuqim
    (``_loaded_pesuqim``) and may have the saved
    settings (``_settings``)."""

    _field_result: tuple | None = None  # (what it was found for, ankipasuk.semantics.passage)
    _settings: Settings | None = None

    def _loaded_pesuqim(self) -> list[dict]:
        raise NotImplementedError

    def _field_level(self) -> int:
        return saved_level(self._settings.get("fields") if self._settings else None)

    def get_fields(self, reference: bool = False, particles: bool = False) -> dict:
        """The loaded pesuqim's fields, word by word, at the saved level;
        Reference's and particles' only if asked (see
        ankipasuk.semantics.passage)."""
        try:
            data, level = self._loaded_pesuqim(), self._field_level()
            key = (tuple((item["book"], item["ch"], item["vs"]) for item in data), level, bool(reference),
                   bool(particles))
            if self._field_result is None or self._field_result[0] != key:
                self._field_result = (key, passage(data, level, bool(reference), bool(particles)))
            return {"ok": True, **self._field_result[1]}
        except Exception as e:  # noqa: BLE001 -- the text still shows without them
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def get_field_settings(self) -> dict:
        """The level the fields are compared at, the ones it can be, and
        how deep SDBH files the Tanakh's words (level -> share)."""
        return {"level": self._field_level(), "default": DEFAULT_LEVEL, "choices": list(LEVELS),
                "levels": {str(n): share for n, share in levels().items()}}

    def save_field_settings(self, values: dict) -> dict:
        """Keeps the level (``values["level"]``), if it's one of LEVELS."""
        level = (values or {}).get("level")
        if level not in LEVELS:
            return {"ok": False, "error": f"The level is one of {', '.join(map(str, LEVELS))}."}
        if self._settings is None:
            return {"ok": False, "error": "There's nowhere to keep the settings."}
        try:
            self._settings.set("fields", {} if level == DEFAULT_LEVEL else {"level": level})
        except OSError as e:
            return {"ok": False, "error": f"Couldn't save the settings: {e}"}
        return {"ok": True, "level": level}
