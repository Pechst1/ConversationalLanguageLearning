"""STORY_SCENE_RECORD off is main before the story-truth stack: the same payloads.

The story-truth stack (#145 scene record, #147 one cast, #621 one scene per page) landed
behind one switch, ``STORY_SCENE_RECORD``. With it off a learner must meet exactly what
they met before. This plays the authored first day (a scripted day) and the next day (a
season day) for an A1 German learner and a B1 English learner, with production's story
flags, and compares two things with what ``origin/main`` produced at 9fbba75f:

* every payload the learner's client received, in reading order (the walk's transcript);
* every request the story engine sent to a model (system prompt, output schema, data),
  in order.

The golden files were written by this same test on ``origin/main``
(``SCENE_RECORD_GOLDEN_WRITE=1``). A change to main's own behaviour after that commit
means rewriting them from main, never from this branch.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests.test_learner_walk import clock, production_day  # noqa: F401 - fixtures
from tests.test_season_one import season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled

GOLDEN = Path(__file__).parent / "fixtures" / "scene_record_off"
WRITE = os.environ.get("SCENE_RECORD_GOLDEN_WRITE") == "1"
DAYS = tuple(int(day) for day in os.environ.get("SCENE_RECORD_DAYS", "1,2,3").split(","))

#: Production's story flags (render.yaml), so the day runs the paths learners get.
PRODUCTION_STORY_FLAGS = {
    "STORY_DAY_CONTRACT": True,
    "STORY_SHARED_PAGES": True,
    "STORY_CONTRACT_REASK": True,
    "STORY_CONTRACT_STAND_IN": True,
}

_UUID = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}")
_HEX_ID = re.compile(r"\b[0-9a-f]{32}\b")
_EMAIL = re.compile(r"life-[\w.-]+@example\.com|[\w.-]+-[0-9a-f]{8}@example\.com")
#: Wall-clock measurements: how long a call took is not behaviour.
_TIMINGS = {"reply_seconds", "seconds", "latency_ms", "elapsed_ms", "duration_ms"}


def normalised(value: Any) -> Any:
    """``value`` with ids and wall-clock timings replaced, so two runs compare equal."""

    if isinstance(value, dict):
        return {
            key: ("<timing>" if key in _TIMINGS and isinstance(item, int | float) else normalised(item))
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [normalised(item) for item in value]
    if isinstance(value, str):
        value = _UUID.sub("<id>", value)
        value = _HEX_ID.sub("<hex>", value)
        return _EMAIL.sub("<email>", value)
    return value


class Recorder:
    """Every request the engine sends the provider, whole: the system prompt, the output
    schema and the data. A prompt or a schema the model sees is behaviour too."""

    def __init__(self, provider: Any, monkeypatch: Any) -> None:
        self.requests: list[dict[str, Any]] = []
        answer = provider.generate_chat_completion

        def recording(messages, **kwargs):
            try:
                content: Any = json.loads(messages[0]["content"])
            except (ValueError, KeyError, IndexError, TypeError):
                content = [message.get("content") for message in messages]
            self.requests.append({"system": kwargs.get("system_prompt"), "content": content})
            return answer(messages, **kwargs)

        monkeypatch.setattr(provider, "generate_chat_completion", recording)


def _compare(name: str, got: Any) -> None:
    path = GOLDEN / f"{name}.json"
    text = json.dumps(normalised(got), ensure_ascii=False, indent=1, sort_keys=True, default=str)
    if WRITE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        return
    expected = path.read_text(encoding="utf-8").rstrip("\n")
    if text != expected:
        import difflib

        diff = "\n".join(
            list(difflib.unified_diff(expected.splitlines(), text.splitlines(), "origin/main", "flag off", lineterm=""))[:120]
        )
        pytest.fail(f"{name}: STORY_SCENE_RECORD off differs from origin/main\n{diff}")


@pytest.mark.parametrize("season_on", [True], indirect=True, ids=["lanes"])
@pytest.mark.parametrize("persona", [walk.PERSONAS[0], walk.PERSONAS[2]], ids=lambda p: p.key)
def test_flag_off_days_match_main(
    persona, season_on, monkeypatch, assembled_client, db_session, journey_enabled, clock, production_day  # noqa: F811
):
    # On origin/main the setting does not exist yet (the golden files were written there).
    if "STORY_SCENE_RECORD" in type(settings).model_fields:
        monkeypatch.setattr(settings, "STORY_SCENE_RECORD", False)
    for flag, value in PRODUCTION_STORY_FLAGS.items():
        monkeypatch.setattr(settings, flag, value)
    # The season seeds its choices (Camille's gender, a chapter's shape) with the learner's
    # and the thread's ids. Fixed bytes behind ``uuid4`` make the two runs choose alike.
    rng = random.Random(f"scene-record-off|{persona.key}")
    monkeypatch.setattr(os, "urandom", lambda size: bytes(rng.getrandbits(8) for _ in range(size)))
    recorder = Recorder(production_day, monkeypatch)
    headers, _email = walk.register(assembled_client, persona)
    for day in DAYS:
        recorder.requests.clear()
        transcript = walk.play_day(
            assembled_client, db_session, headers, persona=persona, quality="average", day=day, provider=production_day
        )
        assert transcript.get("error") is None, transcript.get("error")
        _compare(f"{persona.key}-day{day}-payloads", transcript)
        _compare(f"{persona.key}-day{day}-model-calls", recorder.requests)
        clock.advance(days=1)
