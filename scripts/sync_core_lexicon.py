"""Mirror the core French lexicon (A1 → C1) into ``vocabulary_words``.

Idempotent: a no-op when the catalogue already mirrors the current lexicon build.
Run at deploy (docker/entrypoint.sh, after migrations) and after rebuilding the
lexicon (scripts/build_lexicon_v3.py).

    venv/bin/python scripts/sync_core_lexicon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services.core_lexicon import core_marker, ensure_core_lexicon  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        ensure_core_lexicon(db)
        db.commit()
        print(f"core lexicon current ({core_marker()})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
