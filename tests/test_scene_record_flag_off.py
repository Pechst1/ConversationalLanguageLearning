"""STORY_SCENE_RECORD off: no code of the story-truth stack runs.

The story-truth stack (#145 scene record, #147 one cast, #621 one scene per page, the
veto and the record-read re-ask of #710) landed behind one switch, ``STORY_SCENE_RECORD``.
With it off a learner must meet what they met before the stack.

This plays the authored first day, a season page and a generated day for an A1 German
learner and a B1 English learner, with production's story flags, and asserts through the
code that the stack stayed shut:

* none of the stack's own functions is called (the record's stack build, its reading of a
  turn, the record handed to a writer, the caption from the record, the record-read
  re-ask, the veto's authored line, the closing call, the one-scene check…);
* no request to a model asks for a stack field (``scene_record.STACK_FIELDS``), uses the
  ``SceneClosing`` schema, or carries a line only the stack's prompts hold;
* ``day_contract.reask`` decides by main's rule (the tutor's ``not_yet``), never the record;
* no reply is labelled authored.

The same days with the flag on must reach the stack's code, so the spies are not blind.

Before 11 Nov 2026 this test compared byte-for-byte golden files written on main before
#710. That proved the merge once; afterwards any payload change on main, or a random draw
moved by the tests that ran earlier in the process, broke it (main's run 43000929857).
"""

# ruff: noqa: F811 - pytest fixtures are imported, then named as arguments
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

import pytest

from app.config import settings
from app.services import (
    journal,
    living_story,
    scene_exit,
    scene_ledger,
    scene_record,
    scene_unity,
    story_lanes,
    story_split,
    story_split_main,
)
from app.services.season import closing as season_closing
from app.services.season import day_contract
from app.services.season import runtime as season_runtime
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests.test_learner_walk import clock, production_day  # noqa: F401 - fixtures
from tests.test_season_one import season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled

DAYS = tuple(int(day) for day in os.environ.get("SCENE_RECORD_DAYS", "1,2,3").split(","))

#: Production's story flags (render.yaml), so the day runs the paths learners get.
PRODUCTION_STORY_FLAGS = {
    "STORY_DAY_CONTRACT": True,
    "STORY_SHARED_PAGES": True,
    "STORY_CONTRACT_REASK": True,
    "STORY_CONTRACT_STAND_IN": True,
}

#: The stack's own functions: each runs only with the flag on.
STACK_ONLY = (
    (scene_ledger, "for_writer"),
    (scene_ledger, "turn_caption"),
    (scene_ledger, "read_turn"),
    (scene_ledger, "_established"),
    (day_contract, "_open_in_record"),
    (scene_exit, "reaction"),
    (scene_unity, "gap"),
    (journal, "_said_in_scene"),
    (season_runtime, "_ledger_now"),
    (season_runtime, "_listening_route"),
    (season_closing, "written_close"),
)

#: The stack's prompts and main's: a line only the stack's prompt holds is never sent.
PROMPTS = (
    (story_lanes.VOICE, story_lanes.VOICE_MAIN),
    (story_lanes.STORY, story_lanes.STORY_MAIN),
    (living_story.DIRECTOR, living_story.DIRECTOR_MAIN),
    (living_story.ACTOR, living_story.ACTOR_MAIN),
    (story_split.PLANNER, story_split_main.PLANNER),
    (story_split.AUTHOR, story_split_main.AUTHOR),
)


def _stack_lines() -> set[str]:
    lines: set[str] = set()
    for stack, main in PROMPTS:
        kept = set(main.splitlines())
        lines |= {
            line
            for line in stack.splitlines()
            if line not in kept and len(line) > 30 and "{" not in line
        }
    return lines


def _schema_fields(node: Any, found: set[tuple[str, str]]) -> None:
    """Every (model title, property) the schema names, nested models included."""

    if isinstance(node, dict):
        title = str(node.get("title") or "")
        if isinstance(node.get("properties"), dict):
            found |= {(title, key) for key in node["properties"]}
        for value in node.values():
            _schema_fields(value, found)
    elif isinstance(node, list):
        for value in node:
            _schema_fields(value, found)


class Spies:
    """Counts the calls of the stack's functions, the requests sent to the model and what
    ``day_contract.reask`` decided."""

    def __init__(self, provider: Any, monkeypatch: Any) -> None:
        self.calls: Counter[str] = Counter()
        self.requests: list[dict[str, Any]] = []
        self.reasks: list[dict[str, Any]] = []
        for module, name in STACK_ONLY:
            self._count(monkeypatch, module, name)
        reask = day_contract.reask

        def reasking(plan, **kwargs):
            asked = reask(plan, **kwargs)
            self.reasks.append({**kwargs, "asked": asked, "plan": plan})
            return asked

        monkeypatch.setattr(day_contract, "reask", reasking)
        answer = provider.generate_chat_completion

        def recording(messages, **kwargs):
            try:
                content: Any = json.loads(messages[0]["content"])
            except (ValueError, KeyError, IndexError, TypeError):
                content = None
            self.requests.append(
                {"system": str(kwargs.get("system_prompt") or ""), "content": content}
            )
            return answer(messages, **kwargs)

        monkeypatch.setattr(provider, "generate_chat_completion", recording)

    def _count(self, monkeypatch: Any, module: Any, name: str) -> None:
        original = getattr(module, name)
        label = f"{module.__name__.rsplit('.', 1)[-1]}.{name}"

        def counted(*args, **kwargs):
            self.calls[label] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)

    def schemas(self) -> list[dict[str, Any]]:
        return [
            request["content"]["output_schema"]
            for request in self.requests
            if isinstance(request["content"], dict)
            and isinstance(request["content"].get("output_schema"), dict)
        ]


def _play(persona, record: bool, monkeypatch, client, db_session, clock, provider):
    monkeypatch.setattr(settings, "STORY_SCENE_RECORD", record)
    for flag, value in PRODUCTION_STORY_FLAGS.items():
        monkeypatch.setattr(settings, flag, value)
    spies = Spies(provider, monkeypatch)
    headers, _email = walk.register(client, persona)
    transcripts = []
    for day in DAYS:
        transcript = walk.play_day(
            client,
            db_session,
            headers,
            persona=persona,
            quality="average",
            day=day,
            provider=provider,
        )
        assert transcript.get("error") is None, transcript.get("error")
        transcripts.append(transcript)
        clock.advance(days=1)
    return spies, transcripts


def _authored_replies(value: Any) -> list[Any]:
    if isinstance(value, dict):
        own = [value] if value.get("reply_source") == "authored" else []
        return own + [found for item in value.values() for found in _authored_replies(item)]
    if isinstance(value, list):
        return [found for item in value for found in _authored_replies(item)]
    return []


@pytest.mark.parametrize("season_on", [True], indirect=True, ids=["lanes"])
@pytest.mark.parametrize("persona", [walk.PERSONAS[0], walk.PERSONAS[2]], ids=lambda p: p.key)
def test_flag_off_runs_no_stack_code(
    persona,
    season_on,
    monkeypatch,
    assembled_client,
    db_session,
    journey_enabled,
    clock,
    production_day,
):
    spies, transcripts = _play(
        persona, False, monkeypatch, assembled_client, db_session, clock, production_day
    )
    assert spies.requests, "the days made no model call: nothing was checked"

    assert not spies.calls, f"stack code ran with STORY_SCENE_RECORD off: {dict(spies.calls)}"

    fields: set[tuple[str, str]] = set()
    for schema in spies.schemas():
        _schema_fields(schema, fields)
    stack_fields = {
        (title, key) for title, key in fields if key in scene_record.STACK_FIELDS.get(title, ())
    }
    assert not stack_fields, f"a model was asked for the stack's fields: {sorted(stack_fields)}"
    assert "SceneClosing" not in {title for title, _key in fields}, "the closing call ran"

    lines = _stack_lines()
    sent = [line for request in spies.requests for line in lines if line in request["system"]]
    assert not sent, f"a stack-only prompt line was sent: {sent[:3]}"

    # Main's rule: the simpler question comes back only after a «not yet», and only once.
    for call in spies.reasks:
        if call["asked"]:
            assert call["outcome"] == "not_yet", call
            assert call["asked"] not in [
                row.get("character") for row in call.get("history") or [] if isinstance(row, dict)
            ]

    assert not _authored_replies(transcripts), "a reply was labelled authored (the veto ran)"


@pytest.mark.parametrize("season_on", [True], indirect=True, ids=["lanes"])
def test_flag_on_reaches_the_stack_code(
    season_on,
    monkeypatch,
    assembled_client,
    db_session,
    journey_enabled,
    clock,
    production_day,
):
    """The spies above can see: the same days with the flag on run the stack's code."""

    persona = walk.PERSONAS[2]
    spies, _transcripts = _play(
        persona, True, monkeypatch, assembled_client, db_session, clock, production_day
    )
    reached = (
        "scene_ledger.for_writer",
        "scene_ledger.read_turn",
        "scene_ledger._established",
        "scene_ledger.turn_caption",
        "runtime._ledger_now",
        "runtime._listening_route",
        "closing.written_close",
        "scene_unity.gap",
    )
    for label in reached:
        assert spies.calls[label], f"{label} never ran with the flag on: {dict(spies.calls)}"
    fields: set[tuple[str, str]] = set()
    for schema in spies.schemas():
        _schema_fields(schema, fields)
    assert any(key in scene_record.STACK_FIELDS.get(title, ()) for title, key in fields), (
        "no stack field was asked for"
    )
    lines = _stack_lines()
    assert any(line in request["system"] for request in spies.requests for line in lines), (
        "no stack prompt line was sent"
    )
