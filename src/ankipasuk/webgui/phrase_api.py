"""The phrase views' calls (see ankipasuk.phrases), shared by the main
window's bridge and the statistics window's: the list, a phrase's
pesuqim here, and one of its other places in its chapter."""

from __future__ import annotations

import traceback

from ..cache import SefariaCache
from ..config import POINTED_VERSION
from ..phrases import context, here_verses, passage
from ..sefaria import get_text_for_ref
from ..shorashim import lined_up


class PhraseApi:
    """Mixed into a bridge that gives its loaded pesuqim
    (``_phrase_pesuqim``) and may have a Sefaria cache (``_cache``)."""

    _phrase_result: tuple | None = None  # (the pesuqim's refs, ankipasuk.phrases.passage)
    _cache: SefariaCache | None = None

    def _phrase_pesuqim(self) -> list[dict]:
        raise NotImplementedError

    def _phrase_data(self) -> dict:
        data = self._phrase_pesuqim()
        key = tuple((item["book"], item["ch"], item["vs"]) for item in data)
        if self._phrase_result is None or self._phrase_result[0] != key:
            self._phrase_result = (key, passage(data))
        return self._phrase_result[1]

    def get_phrases(self) -> dict:
        """The loaded pesuqim's recurring phrases, by section (see
        ankipasuk.phrases.passage)."""
        try:
            return {"ok": True, **self._phrase_data()}
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
