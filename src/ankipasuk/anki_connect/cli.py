"""Console-friendly entry points.

Each function here prints progress the way the original standalone scripts
did, and (by default) pauses on ``Press Enter to close`` so the wrapper
scripts in ``scripts/`` stay safe to double-click on Windows -- a console
window opened that way closes immediately on exit unless something waits
for input. ``pause=False`` (used by ``console_scripts`` entry points and by
tests) skips that.
"""

from __future__ import annotations

import sys

from .client import DEFAULT_URL, AnkiConnectError, invoke
from .scheduling import initialize_stems, process_lapses, process_promotions
from .tagging import apply_tagging_plan, compute_tagging_plan


def _pause() -> None:
    try:
        input("\nPress Enter to close...")
    except EOFError:
        pass  # non-interactive (CI, pytest, piped input) -- nothing to wait on


def check_connection(url: str = DEFAULT_URL, *, pause: bool = True) -> None:
    print()
    print("Connecting to AnkiConnect...")
    try:
        version = invoke("version", url=url)
    except AnkiConnectError as e:
        print()
        print("ANKICONNECT CONNECTION ERROR")
        print("-" * 40)
        print(e)
        if pause:
            _pause()
        sys.exit(1)

    print(f"Connected. AnkiConnect version: {version}")
    if pause:
        _pause()


def initialize_stems_cli(deck: str, *, url: str = DEFAULT_URL, dry_run: bool, pause: bool = True) -> None:
    print()
    print("=" * 60)
    print("TORAH STEM INITIALIZER")
    print("=" * 60)
    print()
    print(f"Deck: {deck}")
    print()
    print("MODE:", "DRY RUN" if dry_run else "LIVE")

    try:
        print()
        print("Connecting to Anki...")
        version = invoke("version", url=url)
        print(f"Connected. AnkiConnect version: {version}")

        print()
        print("Finding and flagging stems...")
        print()
        result = initialize_stems(deck, url=url, dry_run=dry_run, log=print)
    except AnkiConnectError as e:
        print()
        print("ERROR")
        print("-" * 40)
        print(e)
        if pause:
            _pause()
        sys.exit(1)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print()
    print(f"Flagged:         {result['flagged']}")
    print(f"Already flagged: {result['skipped']}")
    print(f"Total notes:     {result['notes']}")

    if dry_run:
        print()
        print("DRY RUN -- no changes were made.")
        print("If the list looks correct, change DRY_RUN to False.")

    if pause:
        _pause()


def sync_scheduling_cli(
    deck: str, promotion_interval: int, *, url: str = DEFAULT_URL, dry_run: bool, pause: bool = True
) -> None:
    print()
    print("=" * 70)
    print("TORAH LEYNING ANKI AUTOMATION")
    print("=" * 70)
    print()
    print(f"Deck: {deck}")
    print(
        "MODE:",
        "DRY RUN -- NO CHANGES WILL BE MADE" if dry_run else "LIVE -- ANKI WILL BE MODIFIED",
    )

    try:
        version = invoke("version", url=url)
        print(f"AnkiConnect version: {version}")

        print()
        print("=" * 70)
        print("PROMOTION: FLAG 1 -> FLAG 2")
        print("=" * 70)
        promo = process_promotions(deck, promotion_interval, url=url, dry_run=dry_run, log=print)
        print()
        print(f"Promoted: {promo['promoted']}")

        print()
        print("=" * 70)
        print("LAPSE RECOVERY: FLAG 2 -> FLAG 1")
        print("=" * 70)
        lapse = process_lapses(deck, promotion_interval, url=url, dry_run=dry_run, log=print)
        print()
        print(f"Recovered: {lapse['recovered']}")
    except AnkiConnectError as e:
        print()
        print("ERROR")
        print("-" * 40)
        print(e)
        if pause:
            _pause()
        sys.exit(1)

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    if dry_run:
        print()
        print("Nothing was changed. Set DRY_RUN = False to run live.")

    if pause:
        _pause()


def tag_deck_cli(deck: str, *, url: str = DEFAULT_URL, dry_run: bool, pause: bool = True) -> None:
    from ..cache import SefariaCache

    print()
    print("=" * 60)
    print("PARASHA / ALIYAH / MAFTIR / HOLIDAY TAGGER")
    print("=" * 60)
    print()
    print(f"Deck: {deck}")
    print("MODE:", "DRY RUN" if dry_run else "LIVE")

    try:
        print()
        print("Connecting to Anki...")
        version = invoke("version", url=url)
        print(f"Connected. AnkiConnect version: {version}")

        print()
        print("Fetching notes and computing tags (this may take a moment on first")
        print("run, while Sefaria's parasha structure is fetched and cached)...")
        cache = SefariaCache()
        plan = compute_tagging_plan(deck, url=url, cache=cache, log=print)

        print()
        summary = apply_tagging_plan(plan, url=url, dry_run=dry_run, log=print)
    except AnkiConnectError as e:
        print()
        print("ERROR")
        print("-" * 40)
        print(e)
        if pause:
            _pause()
        sys.exit(1)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print()
    print(f"Total notes:              {summary['total_notes']}")
    print(f"Notes not a Torah ref:    {summary['unparsed_notes']}")
    print(f"Notes tagged:             {summary['notes_needing_tags']}")
    print(f"Tags added:               {summary['total_tags_to_add']}")
    print(f"Conflicts (left as-is):   {summary['notes_with_conflicts']}")

    if summary["notes_with_conflicts"]:
        print()
        print("Some notes already had a tag that looks like ours but doesn't match")
        print("what was computed. These were left untouched -- see the CONFLICT")
        print("lines above and review by hand.")

    if dry_run:
        print()
        print("DRY RUN -- no changes were made.")
        print("If the plan looks correct, change DRY_RUN to False.")

    if pause:
        _pause()


# =============================================================
#  console_scripts entry points (installed via pip; terminal use,
#  as an alternative to double-clicking the scripts/ wrappers)
# =============================================================
def _console_check_connection() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check that AnkiConnect is reachable.")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    check_connection(url=args.url, pause=False)


def _console_init_stems() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Flag the stem of every note in a deck.")
    parser.add_argument("deck", help='e.g. "Leyning::1-Bereshit"')
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true", help="Show what would change; make no changes.")
    args = parser.parse_args()
    initialize_stems_cli(args.deck, url=args.url, dry_run=args.dry_run, pause=False)


def _console_sync_scheduling() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run one promotion + lapse-recovery cycle for a deck.")
    parser.add_argument("deck", help='e.g. "Leyning::1-Bereshit"')
    parser.add_argument("--promotion-interval", type=int, default=21)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true", help="Show what would change; make no changes.")
    args = parser.parse_args()
    sync_scheduling_cli(
        args.deck, args.promotion_interval, url=args.url, dry_run=args.dry_run, pause=False
    )


def _console_tag_deck() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Tag every note in a deck with its parasha/aliyah/Maftir/holiday tags."
    )
    parser.add_argument("deck", help='e.g. "Leyning"')
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true", help="Show what would change; make no changes.")
    args = parser.parse_args()
    tag_deck_cli(args.deck, url=args.url, dry_run=args.dry_run, pause=False)
