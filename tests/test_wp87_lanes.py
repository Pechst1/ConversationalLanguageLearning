"""WP-87 «La réplique d'abord» — the turn in three lanes, with a fake provider only.

What these tests pin (never a paid call):

* the respond POST's server time is ≈ max(tutor, voice), not their sum, and never
  includes the story lane or the critic;
* a replay of the same mutation is byte-identical and pays nothing;
* the story lane's ending is on the resolution step before it renders, and a failed
  (or dead) lane gets today's authored ending;
* a clarification caps the grade; deterministic guards run on the reply;
* one cost row per lane; the flag off is the old single-actor path.
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.daily_journey import DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.journey_latency import LATENCY_EVENT, PHASE_RESPOND
from app.services.llm_service import LLMProviderError
from tests import test_journey_end_to_end as support
from tests.test_living_story import FakeProvider, _turn, driver

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled
clock = support.clock

TUTOR_DELAY = 0.30
VOICE_DELAY = 0.40
STORY_DELAY = 0.50
CRITIC_DELAY = 0.30
ANSWER = "Je peux apporter les affiches samedi."

# What a gpt-5 reasoning model spends before the first visible token, per effort.
REASONING_TOKENS = {"minimal": 40, "low": 900, "medium": 2500, None: 2500}
OUTPUT_TOKENS = {"TutorVerdict": 180, "VoiceReply": 160, "StoryTurn": 420, "TurnReview": 60}


class LaneProvider(FakeProvider):
    """The scripted story provider, speaking the lane schemas, with a wall-clock cost
    per lane and gpt-5 token starvation (empty content when the ceiling is spent on
    reasoning)."""

    def __init__(self):
        super().__init__()
        self.delays = {
            "TutorVerdict": TUTOR_DELAY,
            "VoiceReply": VOICE_DELAY,
            "StoryTurn": STORY_DELAY,
            "TurnReview": CRITIC_DELAY,
        }
        self.kwargs: list[tuple[str, dict]] = []
        self.contents: list[tuple[str, str]] = []
        self.lock = threading.Lock()
        self.tutor = {}
        self.voice = {}
        self.story = {}
        self.review = {}
        self.fail = set()

    def generate_chat_completion(self, messages, **kwargs):
        content = messages[0]["content"]
        data = json.loads(content)
        schema = data["output_schema"]["title"]
        if schema not in self.delays:
            return super().generate_chat_completion(messages, **kwargs)
        with self.lock:
            self.calls.append((schema, data["data"]))
            self.kwargs.append((schema, dict(kwargs)))
            self.contents.append((schema, content))
        time.sleep(self.delays[schema])
        if schema in self.fail:
            raise LLMProviderError("scripted failure")
        needed = REASONING_TOKENS.get(kwargs.get("reasoning_effort")) + OUTPUT_TOKENS[schema]
        if kwargs.get("max_tokens", 0) < needed:
            raise LLMProviderError("OpenAI response did not include content")
        source = data["data"]
        full = _turn(source.get("learner_text") or ANSWER)
        if schema == "TutorVerdict":
            keys = ("outcome", "evidence_quotes", "demonstrated_target_ids")
            value = {**{k: full[k] for k in keys}, **self.tutor}
        elif schema == "VoiceReply":
            keys = ("reply_fr", "understood_intent", "needs_clarification")
            value = {**{k: full[k] for k in keys}, **self.voice}
        elif schema == "StoryTurn":
            released = source["released"]
            keys = ("resolution_fr", "summary_native", "callback_fr", "resolved_commitment_ids")
            value = {
                **{k: full[k] for k in keys},
                "commitments": [
                    {"text_fr": "Apporter les affiches samedi.", "source_quote": source["learner_text"]}
                ],
                **self.story,
            }
            assert released["reply_fr"], "the story lane is told what the learner saw"
        else:
            value = {"accepted": not self.reject, "issues": [] if not self.reject else ["contradiction"],
                     **self.review}
        return SimpleNamespace(
            content=json.dumps(value), model="fake-lane", provider="test", total_tokens=30,
            cost=self.cost_usd,
        )

    def schemas(self):
        return [schema for schema, _ in self.calls]


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = LaneProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


@pytest.fixture
def jobs(monkeypatch):
    """Story lanes are queued, and run when the test says so."""

    queued: list = []
    monkeypatch.setattr(lanes, "dispatcher", queued.append)
    return queued


@pytest.fixture
def inline(monkeypatch):
    """Story lanes run right after the respond commit, before the next request."""

    ran: list[str] = []
    monkeypatch.setattr(lanes, "dispatcher", lambda job: ran.append(lanes.run_story_job(job)))
    return ran


def _to_respond(d) -> dict:
    d.create()
    for _ in range(12):
        step = d.current()
        if step["kind"] == "respond":
            return step
        if step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
        else:
            d.advance()
    raise AssertionError("no respond step")


def _respond(client, d, step, text=ANSWER, mutation_id=None):
    import uuid

    body = {
        "mutation_id": mutation_id or str(uuid.uuid4()),
        "expected_revision": d.journey["revision"],
        "input": {"mode": "text", "text": text},
    }
    route = f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts"
    response = client.post(route, json=body, headers=d.headers)
    if response.status_code == 200:
        d.journey = response.json()["journey"]
    return route, body, response


def _walk_to_end(d) -> None:
    for _ in range(12):
        step = d.current()
        if step is None:
            return
        if step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
            if d.journey.get("current_step_id") != step["id"]:
                continue
        d.advance()


def _resolution(journey: dict) -> dict:
    return next(s for s in journey["steps"] if s["kind"] == "resolution")


def _respond_ms(db, journey_id) -> int:
    rows = db.scalars(
        select(PilotEvent).where(PilotEvent.event_type == LATENCY_EVENT, PilotEvent.entity_id == journey_id)
    ).all()
    return [r.payload["ms"] for r in rows if r.payload.get("phase") == PHASE_RESPOND][-1]


def test_respond_costs_max_of_tutor_and_voice_and_the_story_lane_comes_after(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    started = time.monotonic()
    route, body, first = _respond(assembled_client, d, step)
    served = time.monotonic() - started
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["reply_source"] == "model"
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert result["task_outcome"] == "met"
    pending = _resolution(result["journey"])["prompt"]
    assert pending["story_pending"] is True and pending["character_line_fr"] == ""
    # Server time ≈ max(tutor, voice): not the sum, and no story or critic in it.
    ms = _respond_ms(db_session, d.journey["id"]) / 1000
    assert max(TUTOR_DELAY, VOICE_DELAY) <= ms < TUTOR_DELAY + VOICE_DELAY, ms
    assert "StoryTurn" not in provider.schemas() and "TurnReview" not in provider.schemas()
    assert len(jobs) == 1
    print(f"\n[wp87] respond server {ms:.3f}s (tutor {TUTOR_DELAY}s ‖ voice {VOICE_DELAY}s), "
          f"client {served:.3f}s; old path would be ≥ actor+critic")

    lane_started = time.monotonic()
    assert lanes.run_story_job(jobs[0]) == "done"
    lane_seconds = time.monotonic() - lane_started
    assert lane_seconds >= STORY_DELAY + CRITIC_DELAY
    print(f"[wp87] story lane (story {STORY_DELAY}s + critic {CRITIC_DELAY}s) {lane_seconds:.3f}s, "
          "off the critical path")

    # The resolution renders the story lane's ending.
    d.advance()
    shown = _resolution(d.journey)["prompt"]
    assert shown["story_pending"] is False
    assert shown["character_line_fr"] == "Romy note votre proposition pour samedi."
    assert shown["summary_native"] == "You offered to bring posters on Saturday."

    # A replay of the same mutation is byte-identical and pays nothing.
    calls = len(provider.calls)
    again = assembled_client.post(route, json=body, headers=d.headers)
    assert again.status_code == 200 and again.content == first.content
    assert len(provider.calls) == calls

    _walk_to_end(d)
    assert d.finish("complete").status_code == 200
    assert d.journey["status"] == "completed"
    thread_state = engine._active_thread(db_session, SimpleNamespace(id=d.user_id)).state
    live = thread_state["living_story"]
    assert len(live["events"]) >= 1
    assert any(c["source_quote"] == ANSWER for c in live["commitments"])


def test_one_cost_row_per_lane(assembled_client, db_session, journey_enabled, clock, provider, inline):
    provider.cost_usd = 0.001
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    assert _respond(assembled_client, d, step)[2].status_code == 200
    assert inline == ["done"]
    rows = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.event_type == "journey_story_turn_cost", PilotEvent.user_id == d.user_id
        )
    ).all()
    stages = sorted(row.payload["stage"] for row in rows)
    assert stages == ["story", "tutor", "voice"]
    by_stage = {row.payload["stage"]: row for row in rows}
    assert by_stage["tutor"].payload["calls"] == 1 and by_stage["voice"].payload["calls"] == 1
    assert by_stage["story"].payload["calls"] == 2  # the story call and its critic
    assert all(row.cost_usd > 0 for row in rows)


def test_a_failed_story_lane_gets_the_authored_ending_around_the_shown_reply(
    assembled_client, db_session, journey_enabled, clock, provider, inline
):
    provider.story = {"resolution_fr": "", "summary_native": ""}  # never an ending
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert inline == ["fallback"]
    d.advance()
    shown = _resolution(d.journey)["prompt"]
    assert shown["story_pending"] is False
    assert "doit partir avant de répondre" in shown["character_line_fr"]
    thread = engine._active_thread(db_session, SimpleNamespace(id=d.user_id))
    live = thread.state["living_story"]
    assert not [c for c in live.get("commitments", []) if c.get("source_quote") == ANSWER], (
        "an authored ending invents no commitment"
    )
    events = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "journey_story_turn_fallback",
                                 PilotEvent.user_id == d.user_id)
    ).all()
    assert [e.payload["stage"] for e in events] == ["story_lane"]


def test_a_released_reply_the_critic_refuses_is_logged_never_retracted(
    assembled_client, db_session, journey_enabled, clock, provider, inline
):
    provider.review = {"released_issues": ["gendered address in reply_fr"]}
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert inline == ["done"]
    logged = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "reply_refused_after_release",
                                 PilotEvent.user_id == d.user_id)
    ).all()
    assert [row.payload["issue"] for row in logged] == ["gendered address in reply_fr"]
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."


def test_the_voice_owns_understanding_a_clarification_caps_the_grade(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    provider.voice = {"needs_clarification": True, "reply_fr": "Samedi matin ou samedi soir ?"}
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert result["task_outcome"] == "partially_met", "the tutor said met; the voice asked back"
    assert result["next_turn"] is not None, "the scene continues on a clarification"
    assert jobs == [], "no ending is owed while the character is still asking"
    assert "StoryTurn" not in provider.schemas()


def test_deterministic_guards_run_on_the_reply_before_it_is_returned(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    # A forbidden endearment is scrubbed; an inclusive-dot reply is refused and retried.
    replies = iter(["Tu es prêt·e ? Merci !", "Merci, mon grand. On prépare la salle ensemble."])
    original = provider.generate_chat_completion

    def scripted(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "VoiceReply":
            provider.voice = {"reply_fr": next(replies)}
        return original(messages, **kwargs)

    provider.generate_chat_completion = scripted
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert result["character_reply_fr"] == "Merci. On prépare la salle ensemble."
    voice_calls = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert len(voice_calls) == 2
    assert voice_calls[1]["previous_rejections"], "the retry carries the guard's hint"


def test_flag_off_is_the_single_actor_path_unchanged(
    assembled_client, db_session, journey_enabled, clock, provider, jobs, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", False)
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    schemas = [schema for schema, _ in provider.calls]
    assert "SemanticTurn" in schemas and "Review" in schemas
    assert not {"TutorVerdict", "VoiceReply", "StoryTurn", "TurnReview"} & set(schemas)
    assert jobs == []
    prompt = _resolution(result["journey"])["prompt"]
    assert prompt["story_pending"] is False
    assert prompt["character_line_fr"] == "Romy note votre proposition pour samedi."


def test_a_dead_lane_is_healed_by_the_polling_read_without_a_paid_call(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert len(jobs) == 1
    url = f"/api/v1/daily-journeys/{d.journey['id']}"
    fresh = assembled_client.get(url, headers=d.headers).json()
    assert _resolution(fresh)["prompt"]["story_pending"] is True, "a live lane is left alone"
    # The worker died: nobody claimed the lane within the grace window.
    db_session.expire_all()
    row = db_session.scalars(
        select(DailyJourneyStep).where(
            DailyJourneyStep.journey_id == UUID(d.journey["id"]), DailyJourneyStep.kind == "resolution"
        )
    ).one()
    private = dict(row.private_task)
    private["story_lane"] = {**private["story_lane"], "dispatched_at": "2020-01-01T00:00:00+00:00"}
    row.private_task = private
    db_session.commit()
    calls = len(provider.calls)
    healed = assembled_client.get(url, headers=d.headers).json()
    prompt = _resolution(healed)["prompt"]
    assert prompt["story_pending"] is False and "doit partir" in prompt["character_line_fr"]
    assert len(provider.calls) == calls, "GET never pays"
    # The worker that wakes up late finds the lane settled and changes nothing.
    assert lanes.run_story_job(jobs[0]) == "skipped"


def test_finishing_before_the_lane_settles_it_with_the_authored_ending(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert d.finish("early").status_code == 200
    assert d.journey["status"] == "ended_early"
    assert "doit partir" in _resolution(d.journey)["prompt"]["character_line_fr"]
    assert lanes.run_story_job(jobs[0]) == "skipped"


def test_reply_lanes_run_in_parallel_with_minimal_reasoning_and_no_starvation(provider):
    payload = {
        "story": {"level": "A1", "control_language": "en", "learner": {"address": "neutral"},
                  "world": {"cast": [{"id": "romy_tremblay", "name": "Romy"}]}, "commitments": []},
        "scene": {"character_id": "romy_tremblay", "opening_line_fr": "Vous pouvez nous aider ?",
                  "suggested_response_fr": "Je peux apporter les affiches samedi."},
        "rubric": "Offer help.",
        "targets": [],
        "history": [],
        "learner_text": "Oui, je viens samedi avec des affiches.",
        "turn_plan": {"closing_turn": False, "clarify_form_fr": None},
    }
    started = time.monotonic()
    result = lanes.run_reply_lanes(payload)
    elapsed = time.monotonic() - started
    assert elapsed < TUTOR_DELAY + VOICE_DELAY, "the lanes overlap"
    assert elapsed >= VOICE_DELAY
    assert set(result.seconds) == {"tutor", "voice"}
    for schema, kwargs in provider.kwargs:
        assert kwargs["reasoning_effort"] == "minimal"
        assert kwargs["request_timeout"] <= lanes.LANE_REQUEST_TIMEOUT_SECONDS
        assert kwargs["prompt_cache_key"] == f"atelier-{schema}"
    budgets = {schema: kwargs["max_tokens"] for schema, kwargs in provider.kwargs}
    assert budgets["TutorVerdict"] == lanes.TUTOR_OUTPUT_TOKENS + lanes.LANE_REASONING_HEADROOM
    assert budgets["VoiceReply"] == lanes.VOICE_OUTPUT_TOKENS + lanes.LANE_REASONING_HEADROOM
    # Why the headroom and the effort: a bare 300-token ceiling at "low" starves.
    for schema in ("TutorVerdict", "VoiceReply"):
        assert REASONING_TOKENS["low"] + OUTPUT_TOKENS[schema] > lanes.TUTOR_OUTPUT_TOKENS
        assert REASONING_TOKENS["minimal"] + OUTPUT_TOKENS[schema] <= budgets[schema]


def test_lane_windows_fit_the_operation_budget():
    attempts = settings.ATELIER_STORY_MAX_ATTEMPTS
    assert lanes.LANE_REQUEST_TIMEOUT_SECONDS * attempts <= engine.OPERATION_BUDGET_SECONDS
    assert lanes.RUN_STALE_SECONDS > engine.OPERATION_BUDGET_SECONDS


def test_payloads_are_laid_out_static_first_for_the_prompt_cache():
    payload = {
        "previous_rejections": [], "learner_text": "Oui.", "history": [], "rubric": "r",
        "scene": {"a": 1}, "story": {"revision": "x", "events": [], "world": {"cast": []}},
    }
    content = engine._cache_friendly_content(payload, lanes.TutorVerdict)
    assert content.startswith('{"output_schema": ')
    data = json.loads(content)["data"]
    assert list(data)[:2] == ["story", "scene"]
    assert list(data)[-3:] == ["history", "learner_text", "previous_rejections"]
    assert list(data["story"])[0] == "world"
    # Byte-stable schema prefix across calls with different turns.
    other = engine._cache_friendly_content({**payload, "learner_text": "Non."}, lanes.TutorVerdict)
    prefix = content.split('"learner_text"')[0]
    assert other.startswith(prefix)
