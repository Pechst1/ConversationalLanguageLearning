"""The cast registry as JSON, for the client's generated module (#147).

``cd web-frontend && npm run cast:generate`` reads this and writes ``lib/generated/cast.ts``;
``npm run cast:check`` fails in CI when the committed file is stale. The registry is the one
place a person's name lives: nothing here is typed, only read.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The registry reads only its data files; the settings it may import must not need a real .env.
os.environ.update(DATABASE_URL="sqlite://", SECRET_KEY="cast-export-only-not-for-auth")  # noqa: S106
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import cast_registry  # noqa: E402


def payload() -> dict[str, object]:
    tokens = cast_registry.name_tokens()
    aliases = cast_registry.aliases()
    people = []
    for cast_id, row in sorted(cast_registry.all_members().items()):
        spellings = cast_registry._spellings(row) | {row.name}
        spellings |= {alias for alias, target in aliases.items() if target == cast_id}
        people.append(
            {
                "id": cast_id,
                "name": row.short_name,
                "fullName": row.name,
                "spokenName": row.spoken_name,
                "address": row.address,
                "hasDrawnFace": row.face is not None,
                "firstDay": list(row.first_day),
                "tokens": tokens[cast_id],
                "spellings": sorted(spellings),
            }
        )
    return {"people": people}


if __name__ == "__main__":
    json.dump(payload(), sys.stdout, ensure_ascii=False, sort_keys=True)
