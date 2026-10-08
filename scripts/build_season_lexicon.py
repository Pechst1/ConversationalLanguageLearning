"""WP-131 — derive a season's words per tentpole day and level.

Reads the bible tentpoles and the level files (never writes them) and writes
``app/data/season/<id>/lexicon.json`` (see :mod:`app.services.season_lexicon`).
Deterministic: rerun it after any bible or level-file change; the test
``tests/test_wp131_words_and_quotas.py`` fails while the file is stale.

    venv/bin/python scripts/build_season_lexicon.py [s1]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.season_lexicon import build, lexicon_path  # noqa: E402


def main(argv: list[str]) -> int:
    season_id = argv[1] if len(argv) > 1 else "s1"
    payload = build(season_id)
    path = lexicon_path(season_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    days = payload["days"]
    counts = {
        level: sum(1 for rows in days.values() for row in rows.get(level) or [] if row["role"] == "new")
        for level in ("b1", "b2", "c1")
    }
    print(f"{path}: {len(days)} days; new anchors {counts}; source {payload['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
