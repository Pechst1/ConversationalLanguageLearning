"""P11 · the night run lands a page (pilot packages of 17 Nov).

Real-model play of 17 Nov (Sonnet 5.5 writer, B1): three of four night runs ended
«unavailable». One night lost all six plans to «The task has 13 words; say who asks what
in at most 12.»; another lost an attempt each to a plan with ``beats`` empty and to
«trailing characters» after valid JSON. These guards play the night with the split
writer's fake (``tests/test_story_split.py``) and read its outcome line.
"""

from __future__ import annotations

import json
import logging

import pytest
from loguru import logger as loguru_logger

from app.config import settings
from app.services import story_split
from app.services.journey_latency import prefetch_scene_for
from tests import test_journey_end_to_end as support
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import (
    SplitProvider,
    _context,
    _learner_on_gap_day,
    _plan,
    split_on,  # noqa: F401 - fixture
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

#: 13 words, one ask, no clause separator: what the writer kept sending on 17 Nov.
THIRTEEN = "Lila wants to know who wrote the caption on the old photo today."
#: 16 words: over the limit by more than a readability margin.
SIXTEEN = "Lila wants to know who wrote the caption on the old photo in the box today."
#: What main allows a night that refuses every plan: three attempts of two plans each.
MAIN_PLAN_CALLS = 6


class _Writer(SplitProvider):
    """The split fake with a settable task line and plan shape."""

    def __init__(self, task: str | None = None, *, empty_beats_once=False, trailing=False) -> None:
        super().__init__()
        self.task = task
        self.empty_beats_once = empty_beats_once
        self.trailing = trailing

    def _plan(self, source: dict) -> dict:
        plan = super()._plan(source)
        if self.task:
            plan["task"] = self.task
        if self.empty_beats_once:
            # 17 Nov, night of day 3: a plan came back with beats empty in 1.1 s.
            self.empty_beats_once = False
            plan = {**plan, "beats": [], "change": {"before": "", "after": ""}, "question": ""}
        return plan

    def generate_chat_completion(self, messages, **kwargs):
        result = super().generate_chat_completion(messages, **kwargs)
        if self.trailing and json.loads(messages[0]["content"])["output_schema"]["title"] == "PagePlan":
            # 17 Nov: «Invalid JSON: trailing characters at line 3 column 1».
            result.content = result.content + "\n\n}"
        return result


@pytest.fixture
def night(split_on, monkeypatch):  # noqa: F811 - the fixture above
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    monkeypatch.setattr(settings, "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD", 0.0, raising=False)

    def use(writer: _Writer) -> _Writer:
        from app.services import living_story as engine

        writer.critic_refusals_left = 0
        monkeypatch.setattr(engine, "_client", lambda: writer)
        return writer

    return use


def _plans(writer) -> list[dict]:
    return [payload for schema, payload in writer.calls if schema == "PagePlan"]


def _outcome(caplog) -> dict:
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("journey_latency: night_run ")]
    assert len(lines) == 1, f"one outcome line per night run, got {lines}"
    return json.loads(lines[0].removeprefix("journey_latency: night_run "))


def test_a_task_a_word_over_the_limit_does_not_cost_the_night(assembled_client, db_session, journey_enabled, clock, night, caplog):
    writer = night(_Writer(THIRTEEN))
    user = _learner_on_gap_day(assembled_client, db_session)
    with caplog.at_level(logging.INFO, logger="app.services.journey_latency"):
        status = prefetch_scene_for(db_session, user)
    assert status == "prefetched"
    plans = _plans(writer)
    assert len(plans) == 2 and len(plans) <= MAIN_PLAN_CALLS, "the re-asked plan is kept"
    # The re-ask quotes the line and its count, so the writer knows what to shorten.
    assert any(THIRTEEN in hint and "13 words" in hint for hint in plans[1]["previous_rejections"])
    outcome = _outcome(caplog)
    assert outcome["status"] == "prefetched" and outcome["attempts"] == 1


def test_a_task_far_over_the_limit_is_still_refused(assembled_client, db_session, journey_enabled, clock, night, caplog):
    writer = night(_Writer(SIXTEEN))
    user = _learner_on_gap_day(assembled_client, db_session)
    with caplog.at_level(logging.INFO, logger="app.services.journey_latency"):
        assert prefetch_scene_for(db_session, user) == "unavailable"
    assert "PageText" not in [schema for schema, _ in writer.calls], "no French is paid for that plan"
    outcome = _outcome(caplog)
    assert outcome["status"] == "unavailable"
    assert outcome["kept"] is None and outcome["seconds"] >= 0 and outcome["calls"] == len(_plans(writer))
    assert outcome["attempts"] == len(outcome["refusals"]) >= 2
    assert {row["class"] for row in outcome["refusals"]} == {"plan_refused"}
    assert all("16 words" in row["reason"] for row in outcome["refusals"])


def test_the_grace_is_a_readability_margin_not_a_new_limit():
    assert story_split.TASK_WORDS == 12 and story_split.TASK_WORDS_GRACE == 3
    over = _plan(task=THIRTEEN)
    assert "13 words" in story_split.plan_issue(over, _context()), "the first plan is held to 12"
    assert story_split.plan_issue(over, _context(), task_grace=story_split.TASK_WORDS_GRACE) is None
    far = _plan(task=SIXTEEN)
    assert "16 words" in story_split.plan_issue(far, _context(), task_grace=story_split.TASK_WORDS_GRACE)
    # The grace never hides another rule the plan breaks.
    repeat = _plan(task=THIRTEEN, lead_id="marin_leveque", cast=["marin_leveque"], location_id="le_mistral")
    assert "carried the last days" in story_split.plan_issue(repeat, _context(), task_grace=3)


def test_trailing_characters_after_a_plan_s_json_cost_nothing(assembled_client, db_session, journey_enabled, clock, night):
    writer = night(_Writer(trailing=True))
    user = _learner_on_gap_day(assembled_client, db_session)
    assert prefetch_scene_for(db_session, user) == "prefetched"
    assert len(_plans(writer)) == 1, "the plan is read up to its closing brace"


def test_a_plan_with_no_beats_is_asked_again_inside_the_attempt(assembled_client, db_session, journey_enabled, clock, night, caplog):
    writer = night(_Writer(empty_beats_once=True))
    user = _learner_on_gap_day(assembled_client, db_session)
    with caplog.at_level(logging.INFO, logger="app.services.journey_latency"):
        assert prefetch_scene_for(db_session, user) == "prefetched"
    schemas = [schema for schema, _ in writer.calls if schema != "StoryReview"]
    assert schemas[:3] == ["PagePlan", "PagePlan", "PageText"], "an empty plan is still refused, then re-asked"
    assert any("beats" in hint for hint in _plans(writer)[1]["previous_rejections"])
    assert _outcome(caplog)["attempts"] == 1, "the empty plan cost a plan, not the attempt"


def test_a_refused_plan_s_reason_is_in_the_log(assembled_client, db_session, journey_enabled, clock, night):
    """loguru formats with ``{}``: ``%s`` printed «plan refused (%s)» with the reason lost."""

    night(_Writer(THIRTEEN))
    user = _learner_on_gap_day(assembled_client, db_session)
    messages: list[str] = []
    sink = loguru_logger.add(lambda message: messages.append(message.record["message"]), level="INFO")
    try:
        prefetch_scene_for(db_session, user)
    finally:
        loguru_logger.remove(sink)
    refused = [m for m in messages if m.startswith("story_split: plan refused")]
    assert refused and all("13 words" in m for m in refused), refused
