"""The phrase views' calls (see ankipasuk.phrases), shared by the main
window's bridge and the statistics window's: the list, a phrase's
pesuqim here, one of its other places in its chapter, and the archive.
The tests' thresholds are the saved settings' (``"phrases"``), and so is
the archive (``"phrase_archive"``)."""

from __future__ import annotations

import traceback
from dataclasses import asdict
from datetime import date

from ..cache import SefariaCache
from ..config import POINTED_VERSION
from ..frames import add_to as add_frames
from ..phrases import Thresholds, _name, context, here_verses, passage
from ..sefaria import get_text_for_ref
from ..semantics import saved_level
from ..settings import Settings
from ..shorashim import lined_up

ARCHIVE = "phrase_archive"


class PhraseApi:
    """Mixed into a bridge that gives its loaded pesuqim
    (``_phrase_pesuqim``) and may have a Sefaria cache (``_cache``) and
    the saved settings (``_settings``)."""

    _phrase_result: tuple | None = None  # (the pesuqim's refs and thresholds, ankipasuk.phrases.passage)
    _cache: SefariaCache | None = None
    _settings: Settings | None = None
    _on_archive = None  # called with this bridge when the archive changes, to tell the other windows

    def _phrase_pesuqim(self) -> list[dict]:
        raise NotImplementedError

    def _phrase_thresholds(self) -> Thresholds:
        return Thresholds.from_settings(self._settings.get("phrases") if self._settings else None)

    def _phrase_data(self) -> dict:
        data, thresholds = self._phrase_pesuqim(), self._phrase_thresholds()
        level = saved_level(self._settings.get("fields") if self._settings else None)  # (fields' frames)
        key = (tuple((item["book"], item["ch"], item["vs"]) for item in data), thresholds, level)
        if self._phrase_result is None or self._phrase_result[0] != key:
            self._phrase_result = (key, add_frames(passage(data, thresholds), data, level))
        return self._phrase_result[1]

    def get_phrases(self) -> dict:
        """The loaded pesuqim's recurring phrases, by section (see
        ankipasuk.phrases.passage), the thresholds they were found with,
        and the archive (the views leave out the phrases in it)."""
        try:
            return {"ok": True, **self._phrase_data(), "thresholds": asdict(self._phrase_thresholds()),
                    "archive": self.get_phrase_archive()}
        except Exception as e:  # noqa: BLE001 -- the text still shows without them
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def get_phrase_verses(self, pid: int) -> list:
        """The loaded pesuqim phrase ``pid`` is in, its words marked:
        ``[{"ref", "words": [[text, separator, marked]]}]``."""
        data = self._phrase_pesuqim()
        return here_verses(self._phrase_data()["phrases"][pid], data, lined_up(data))

    def get_phrase_context(self, pid: int, place: int) -> dict:
        """Phrase ``pid``'s other place number ``place`` in its chapter,
        fetched from Sefaria (and cached): ``{"ok", "ref", "title",
        "verses"}`` (see ankipasuk.phrases.context), or ``{"ok": False,
        "ref", "error"}`` when it can't be fetched."""
        spot = self._phrase_data()["phrases"][pid]["places"][place]
        if self._cache is None:
            self._cache = SefariaCache()

        def chapter_of(book: str, ch: int) -> list[str]:
            return get_text_for_ref(f"{book} {ch}", POINTED_VERSION, self._cache)

        try:
            return {"ok": True, **context(spot["at"], spot["length"], chapter_of)}
        except Exception as e:  # noqa: BLE001 -- offline, or Sefaria has no such chapter
            return {"ok": False, "ref": spot["ref"], "error": str(e)}

    # The archive: phrases the user put away, hidden in every passage until
    # restored -- a phrase by its dictionary words (its ``key``), so in all
    # its sections, and a frame as one of its book's.
    def get_phrase_archive(self) -> list[dict]:
        """The archived phrases, the last archived first: ``[{"key", "text",
        "kind", "where", "date"}]``, ``kind`` the section it was archived
        from and ``where`` its pasuq there (a frame's, its unit)."""
        archive = self._settings.get(ARCHIVE) if self._settings else None
        return list(archive) if isinstance(archive, list) else []

    def archive_phrase(self, pid: int, kind: str) -> dict:
        """Puts phrase ``pid`` (archived from section ``kind``) in the
        archive: ``{"ok", "archive"}``, or ``{"ok": False, "error"}``."""
        p = self._phrase_data()["phrases"][pid]
        if p.get("frame"):
            f = p["frame"]
            where = f"{f['first']}–{f['last'].rpartition(' ')[2]}"
        else:
            item = self._phrase_pesuqim()[p["verses"][0]] if p["verses"] else None
            where = f"{_name(item['book'])} {item['ch']}:{item['vs']}" if item else ""
        entry = {"key": p["key"], "text": p["text"], "kind": kind, "where": where,
                 "date": date.today().isoformat()}
        rest = [e for e in self.get_phrase_archive() if e.get("key") != p["key"]]
        return self._save_archive([entry, *rest])

    def restore_phrases(self, keys: list[str]) -> dict:
        """Takes the phrases ``keys`` out of the archive (as archive_phrase)."""
        keys = set(keys)
        return self._save_archive([e for e in self.get_phrase_archive() if e.get("key") not in keys])

    def _save_archive(self, archive: list[dict]) -> dict:
        if self._settings is None:
            return {"ok": False, "error": "There's nowhere to keep the archive."}
        try:
            self._settings.set(ARCHIVE, archive)
        except OSError as e:
            return {"ok": False, "error": f"Couldn't save the archive: {e}"}
        if self._on_archive:
            self._on_archive(self)
        return {"ok": True, "archive": archive}
