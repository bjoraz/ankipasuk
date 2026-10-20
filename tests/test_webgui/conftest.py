"""Local fake_anki fixture for tests/test_webgui.

Reuses the FakeAnki backend from tests/test_anki_connect/conftest.py, but
patches one more module reference than that fixture does:
ankipasuk.webgui.anki_connect_api imports ``invoke`` directly (the same
style ``gui/anki_connect_window.py`` already used), so it needs its own
monkeypatch target -- patching ankipasuk.anki_connect.client.invoke alone
doesn't affect a name already bound into another module's namespace at
import time.
"""

import pytest

from tests.test_anki_connect.conftest import FakeAnki


@pytest.fixture
def fake_anki(monkeypatch):
    import ankipasuk.anki_connect.client as client_module
    import ankipasuk.anki_connect.operations as operations_module
    import ankipasuk.webgui.anki_connect_api as anki_connect_api_module

    backend = FakeAnki()

    def fake_invoke(
        action, *, url=client_module.DEFAULT_URL, timeout=client_module.DEFAULT_TIMEOUT, **params
    ):
        return backend.invoke(action, **params)

    monkeypatch.setattr(client_module, "invoke", fake_invoke)
    monkeypatch.setattr(operations_module, "invoke", fake_invoke)
    monkeypatch.setattr(anki_connect_api_module, "invoke", fake_invoke)

    return backend


@pytest.fixture(autouse=True)
def offline_chapter_lengths(monkeypatch):
    """The exports compute each note's qeriya tags, which needs the length
    of every chapter in the book; tests seed only the chapters they use,
    so the rest come from the static table instead of the network."""
    import ankipasuk.cloze_export as cloze_export_module
    import ankipasuk.tiqqun_export as tiqqun_export_module
    from ankipasuk.config import POINTED_VERSION, TORAH_VERSE_COUNTS

    def chapter_lengths(book, cache, version_param=POINTED_VERSION):
        lengths = []
        for ch, static_n in enumerate(TORAH_VERSE_COUNTS[book], start=1):
            text = cache.get_text(f"{book} {ch}", version_param)
            lengths.append(len(text) if text is not None else static_n)
        return lengths

    monkeypatch.setattr(cloze_export_module, "get_chapter_lengths", chapter_lengths)
    monkeypatch.setattr(tiqqun_export_module, "get_chapter_lengths", chapter_lengths)
