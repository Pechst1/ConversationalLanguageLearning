"""Capture the `page` surface's inputs: a real ``story_context()`` for a learner jumped to a
season gap day, at one level, the way ``tests/prompt_regression/contexts/`` were captured.

Skipped unless ``GOLD_CAPTURE_PAGES=1``; it needs the test database like the rest of the
suite and calls no model. Run it again when the story context changes shape:

    GOLD_CAPTURE_PAGES=1 python -m pytest tests/gold_transcripts/test_capture_pages.py -q

Each context lands in ``tests/gold_transcripts/sets/pages/<id>.json``; the item list is
``sets/page.json``.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from tests import test_journey_end_to_end as support
from tests.gold_transcripts import surfaces as S
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import split_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

pytestmark = pytest.mark.skipif(
    os.environ.get("GOLD_CAPTURE_PAGES") != "1", reason="capture only: GOLD_CAPTURE_PAGES=1"
)

#: Keys story_context() carries that are not JSON or not read by the page writer, dropped
#: as the prompt-regression captures drop them.
DROPPED = ("lexicon", "mots_a_placer", "thread_id", "revision")


def _plain(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, SimpleNamespace):
        return vars(value)
    return str(value)


def _jsonable(context: dict) -> dict:
    out = {key: value for key, value in context.items() if key not in DROPPED and key != "_season"}
    today = context.get("_season")
    if today is not None:
        out["_season"] = {"season_id": today.season.id, "flags": dict(today.flags), "seed": str(today.seed)}
    return json.loads(json.dumps(out, ensure_ascii=False, default=_plain))


def test_capture_page_contexts(assembled_client, db_session, journey_enabled, clock, split_on, monkeypatch):  # noqa: F811
    from app.db.models.user import User
    from app.services import living_story as engine
    from app.services import story_split
    from app.services.journey_contracts import InputMode
    from app.services.season.admin import jump_to_day

    # The writer's context is the one generate_scene completes (errata, can-dos, kept
    # words, line translation…) and hands the page writer: take it where the split is
    # decided, then let the fake writer finish the day.
    seen: list[dict] = []
    real_applies = story_split.applies

    def applies(context):
        seen.append(context)
        return real_applies(context)

    monkeypatch.setattr(story_split, "applies", applies)

    items = S.load_set("page")["items"]
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()  # noqa: S603, S607
    S.PAGES.mkdir(parents=True, exist_ok=True)
    for item in items:
        email = f"gold-page-{uuid.uuid4()}@example.com"
        support.register(assembled_client, email, cefr=item["cefr"])
        user = db_session.scalar(select(User).where(User.email == email))
        jump_to_day(db_session, user, day=item["season_day"])
        db_session.commit()
        seen.clear()
        with engine.written_ahead_of_time():
            engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
        assert seen, f"{item['id']}: no page was asked for"
        context = _jsonable(seen[0])
        position = ((context.get("season_script") or {}).get("position") or {})
        assert position.get("season_day") == item["season_day"], (item["id"], position)
        assert position.get("kind") == "gap", (item["id"], position)
        context = {
            "_captured": (
                f"story_context() of a learner at {item['cefr']} jumped to season day {item['season_day']} "
                f"by tests/gold_transcripts/test_capture_pages.py, {datetime.now(UTC):%Y-%m-%d}, main @ {head}. "
                f"Dropped: {', '.join(DROPPED)}. _season is the runtime handle, rebuilt from season_id + flags + seed."
            ),
            **context,
        }
        (S.PAGES / f"{item['id']}.json").write_text(json.dumps(context, ensure_ascii=False) + "\n", encoding="utf-8")
