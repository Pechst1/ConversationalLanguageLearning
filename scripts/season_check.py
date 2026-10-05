#!/usr/bin/env python
"""Check a season's tentpole files against the format and against the bible (WP-111).

    venv/bin/python scripts/season_check.py            # every tentpole file present
    venv/bin/python scripts/season_check.py t4 t5      # just these
    venv/bin/python scripts/season_check.py epilogue   # the epilogue week (WP-132B)

For each tentpole: the file must parse as the season format, every cross-reference
(speakers, flags, locations, conditions) must resolve, and every French line of the
bible (``docs/story/season-1/0N-*.md``) must be carried verbatim, up to typography.
Exit code 1 on any problem. No database, no model, no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.services.season.fidelity import missing_lines  # noqa: E402
from app.services.season.format import (  # noqa: E402
    SEASON_ROOT,
    Season,
    SeasonFormatError,
    Tentpole,
    _check_tentpole,
)
from app.services.season.world import season_location_ids  # noqa: E402

BIBLES = {
    "t1": "01-le-mauvais-accueil.md",
    "t2": "02-la-haut.md",
    "t3": "03-deux-promesses.md",
    "t4": "04-la-photographie.md",
    "t5": "05-berlin.md",
    "t6": "06-lautre-cote.md",
    "t7": "07-le-dernier-soir.md",
    "t8": "08-ce-quon-garde.md",
}


def check(season_id: str, tentpole_id: str) -> list[str]:
    folder = SEASON_ROOT / season_id
    season = Season.model_validate(json.loads((folder / "season.json").read_text(encoding="utf-8")))
    path = folder / f"{tentpole_id}.json"
    if not path.is_file():
        return [f"{path} does not exist"]
    try:
        tentpole = Tentpole.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, SeasonFormatError) as exc:
        return [f"{tentpole_id}: does not parse: {exc}"]
    problems = _check_tentpole(season, tentpole, locations=season_location_ids())
    bible = REPO / "docs" / "story" / f"season-{season_id[1:]}" / BIBLES[tentpole_id]
    problems += [f"{tentpole_id}: bible line not carried: «{line}»" for line in missing_lines(bible, path)]
    return problems


# ---------------------------------------------------------------------------
# WP-132B: the epilogue week after the finale (``epilogue.json``)
# ---------------------------------------------------------------------------

EPILOGUE_ID = "epilogue"
EPILOGUE_BIBLE = "12-la-semaine-dapres.md"


def check_epilogue(season_id: str) -> list[str]:
    """The epilogue parses with its level variants and plain tasks, every cross-reference
    resolves, every finale ending reaches every one of its days (``epilogue_problems``),
    and every French line of its bible chapter is carried verbatim."""

    from app.services.season.epilogue import (
        EPILOGUE_FILE,
        epilogue_problems,
        read_epilogue,
        world_addressees,
    )
    from app.services.season.levels import read_levels, read_tasks

    folder = SEASON_ROOT / season_id
    path = folder / EPILOGUE_FILE
    if not path.is_file():
        return [f"{path} does not exist"]
    season = Season.model_validate(json.loads((folder / "season.json").read_text(encoding="utf-8")))
    try:
        epilogue = read_epilogue(folder, levels=read_levels(folder), tasks=read_tasks(folder))
    except (ValueError, SeasonFormatError) as exc:
        return [f"{EPILOGUE_ID}: does not parse: {exc}"]
    if epilogue is None:
        return [f"{path} does not exist"]
    problems = epilogue_problems(season, epilogue, locations=season_location_ids(), addressees=world_addressees(folder))
    bible = REPO / "docs" / "story" / f"season-{season_id[1:]}" / EPILOGUE_BIBLE
    if not bible.is_file():
        return [*problems, f"{EPILOGUE_ID}: no bible chapter {bible.name}"]
    problems += [f"{EPILOGUE_ID}: bible line not carried: «{line}»" for line in missing_lines(bible, path)]
    return problems


def main() -> int:
    wanted = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    season_id = "s1"
    ids = wanted or [tid for tid in BIBLES if (SEASON_ROOT / season_id / f"{tid}.json").is_file()]
    if not wanted and (SEASON_ROOT / season_id / "epilogue.json").is_file():
        ids.append(EPILOGUE_ID)
    failures = 0
    for tid in ids:
        problems = check_epilogue(season_id) if tid == EPILOGUE_ID else check(season_id, tid)
        print(f"{tid}: {'ok' if not problems else f'{len(problems)} problem(s)'}")
        for problem in problems:
            print(f"  - {problem}")
        failures += len(problems)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
