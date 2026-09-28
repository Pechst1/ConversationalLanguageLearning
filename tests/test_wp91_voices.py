# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-91 «Les voix» — every character has a voice, and listening is real.

Pinned here, behaviourally:

* one voice per cast member, from one table the world bible and the radio
  episode agree with;
* the line-audio route speaks only lines that appear in the learner's step
  (404 on anything else), answers ``disabled`` when it cannot speak, caches per
  voice and text so a replay costs nothing, and prices every synthesis;
* listen-and-tap items carry a real clip and a dictation hears a line of
  today's scene without ever printing it — only when audio is on;
* the dictation's grading table;
* Soutenu and Intensif hear every third day first.

**No live TTS call is made anywhere in this file**: every synthesis goes to a
fake provider that counts what it was asked for.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.line_audio import LineAudioClip
from app.db.models.pilot_event import PilotEvent
from app.schemas.daily_journey import RecallPrompt
from app.services import cast_voices, episode_audio, line_audio
from app.services import journey_planner as planner
from app.services.cast_voices import (
    CAST_VOICES,
    LINE_AUDIO_PATH_PREFIX,
    NARRATOR_VOICE,
    clip_id_for,
    voice_for_character,
)
from app.services.journey_contracts import (
    DICTATION_RECALL_FORMATS,
    AssistanceLevel,
    AttemptAnswer,
    DayShape,
    InputMode,
    StepKind,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_day_shapes import (
    DayShapeInputs,
    choose_day_shape,
    is_listen_first_day,
)
from app.services.journey_learning import evaluate_dictation, evaluate_recall
from tests.test_episode_audio import FakeSynthesizer
from tests.test_journey_end_to_end import (
    CAFE_WORDS,
    Clock,  # noqa: F401 - fixture type
    Driver,
    assembled_client,  # noqa: F401 - fixture
    clock,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
    seed_due_vocabulary,
)
from tests.test_journey_planner import _brief
from tests.test_wp78_practice_day import _queue

WORLD_BIBLE = Path("app/prompts/serial/world_bible_paris_v2.json")


@pytest.fixture()
def fake_tts(monkeypatch: pytest.MonkeyPatch) -> FakeSynthesizer:
    provider = FakeSynthesizer()
    monkeypatch.setattr(line_audio, "_default_synthesizer", lambda: provider)
    return provider


@pytest.fixture()
def audio_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)


@pytest.fixture()
def audio_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", False)


@pytest.fixture()
def practice_day(monkeypatch: pytest.MonkeyPatch) -> None:
    # As production: the practice day is on (conftest turns it off by module name).
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)


def _dice(user: str = "learner-a", **kwargs: Any) -> DayShapeInputs:
    return DayShapeInputs(user_id=user, local_date=date(2026, 9, 21), **kwargs)


def _plan(*, budget: int = 600, audio: bool = True, shape: DayShape = DayShape.STANDARD,
          band: str = "A1", language: str = "en"):
    plan = planner.plan_journey(
        scenario=_brief(level_band=band, control_language=language),
        candidates=_queue(),
        practice=True,
        dice=_dice(),
        day_shape=shape,
        audio_available=audio,
        budget_seconds=budget,
    )
    plan.validate()
    return plan


def _recalls(plan) -> list:
    return [step for step in plan.steps if step.kind is StepKind.RECALL]


# ---------------------------------------------------------------------------
# 1. One voice per cast member, one table
# ---------------------------------------------------------------------------


def test_every_cast_member_and_the_narrator_have_their_own_voice() -> None:
    people = {
        "romy_tremblay", "marin_leveque", "lila_bonnet", "augustin_de_roncourt",
        "margaux_barman", "landlord_marchand",
    }
    assert set(CAST_VOICES) == people
    voices = [voice_for_character(person) for person in sorted(people)] + [
        voice_for_character("narrator")
    ]
    assert len(set(voices)) == len(voices) == 7, "two people share a voice"
    assert voice_for_character(None) == voice_for_character("narrator") == NARRATOR_VOICE
    # Short ids and nicknames are the same person.
    assert voice_for_character("gus") == voice_for_character("augustin_de_roncourt")
    assert voice_for_character("marchand") == voice_for_character("landlord_marchand")
    assert voice_for_character("margaux") == voice_for_character("margaux_barman")
    # A generated character keeps one voice, never the narrator's.
    assert voice_for_character("henriette_dubois") == voice_for_character("henriette_dubois")
    assert voice_for_character("henriette_dubois") != NARRATOR_VOICE


def test_the_world_bible_lists_the_same_voices() -> None:
    bible = json.loads(WORLD_BIBLE.read_text(encoding="utf-8"))
    for member in bible["cast"]:
        listed = (member.get("voice") or {}).get("voice")
        assert listed == CAST_VOICES[member["id"]], member["id"]


def test_the_radio_episode_speaks_with_the_same_table() -> None:
    for person in [*CAST_VOICES, "gus", "romy", "marchand", "narrator", "stranger_x"]:
        assert episode_audio.voice_for_character(person) == cast_voices.voice_for_character(person)
    assert episode_audio.NARRATOR_VOICE == NARRATOR_VOICE
    assert episode_audio.PINNED_VOICES is cast_voices.PINNED_VOICES


# ---------------------------------------------------------------------------
# 2. The planner: real listening items, only when audio is on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_a_regulier_day_with_audio_holds_three_real_listening_items(band, language) -> None:
    plan = _plan(budget=600, band=band, language=language)
    assert plan.estimated_active_seconds <= plan.budget_seconds
    heard = [
        step for step in _recalls(plan)
        if step.public_prompt["task_type"] in ("listen_tap", "dictation")
        and str(step.public_prompt.get("audio_url") or "").startswith(LINE_AUDIO_PATH_PREFIX)
    ]
    assert len(heard) >= 3, plan.rationale
    kinds = [step.public_prompt["task_type"] for step in heard]
    assert kinds.count("dictation") == 1
    for step in heard:
        RecallPrompt.model_validate(step.public_prompt)
        if step.public_prompt["task_type"] == "listen_tap":
            # Heard, not read: the phrase is not printed.
            assert step.public_prompt["prompt_fr"] is None
            clip = step.public_prompt["audio_url"].removeprefix(LINE_AUDIO_PATH_PREFIX)
            voice = cast_voices.voice_of_clip_id(clip)
            assert clip == clip_id_for(voice, step.private_task.prompt_fr)


@pytest.mark.parametrize("budget", [300, 600, 1200, 1800])
@pytest.mark.parametrize("shape", [DayShape.STANDARD, DayShape.REPRISE])
def test_without_audio_the_day_is_exactly_as_before(budget, shape) -> None:
    plan = _plan(budget=budget, audio=False, shape=shape)
    for step in _recalls(plan):
        prompt = step.public_prompt
        assert prompt["task_type"] != "dictation"
        if prompt["task_type"] == "listen_tap":
            assert prompt["audio_url"] is None
            assert prompt["prompt_fr"], "read-and-tap prints its phrase"
        else:
            assert "audio_url" not in prompt


def test_a_dictation_never_prints_its_line() -> None:
    plan = _plan(budget=600, band="B1")
    step = next(s for s in _recalls(plan) if s.public_prompt["task_type"] == "dictation")
    line = step.private_task.solution_fr
    assert line and step.private_task.accepted_answers == [line]
    public = RecallPrompt.model_validate(step.public_prompt).model_dump(mode="json")
    assert public["prompt_fr"] is None
    assert public["options"] == []
    assert public["target"]["label_fr"] == ""
    assert public["audio_url"].startswith(LINE_AUDIO_PATH_PREFIX)
    serialized = json.dumps(public, ensure_ascii=False).lower()
    assert line.lower() not in serialized
    for word in (w.strip(".,!?;:«»") for w in line.split()):
        if len(word) >= 5:
            assert word.lower() not in serialized, f"the prompt spells «{word}»"
    # The clip speaks exactly the line, in its speaker's voice.
    clip = public["audio_url"].removeprefix(LINE_AUDIO_PATH_PREFIX)
    assert clip == clip_id_for(cast_voices.voice_of_clip_id(clip), line)
    # It is posed after the scene, never before it.
    kinds = [s.kind for s in plan.steps]
    assert plan.steps.index(step) > kinds.index(StepKind.SCENE)


@pytest.mark.parametrize("band,cap", [("A1", 8), ("A2", 12), ("B1", 16), ("B2", 16)])
def test_the_dictated_line_is_short_for_the_band(band, cap) -> None:
    assert planner.dictation_word_cap(band) == cap
    long_line = " ".join(["mot"] * (cap + 1)) + "."
    short_line = "Je voudrais un café."
    brief = _brief(level_band=band)
    from dataclasses import replace

    brief = replace(
        brief,
        panels=[{"id": "p1", "index": 0, "narration_fr": "",
                 "dialogue": [{"character_id": "romy_tremblay", "text_fr": long_line},
                              {"character_id": "romy_tremblay", "text_fr": short_line}]}],
    )
    lines = [line.text_fr for line in planner.dictation_lines(brief)]
    assert long_line.rstrip(".") + "." in lines
    plan = planner.plan_journey(
        scenario=brief, candidates=_queue(), practice=True, dice=_dice(),
        day_shape=DayShape.STANDARD, audio_available=True, budget_seconds=600,
    )
    dictations = [s for s in _recalls(plan) if s.public_prompt["task_type"] == "dictation"]
    assert dictations
    for step in dictations:
        assert len(step.private_task.solution_fr.split()) <= cap


def test_a_listening_day_poses_what_is_heard() -> None:
    plan = _plan(budget=600, shape=DayShape.LISTENING)
    assert plan.day_shape is DayShape.LISTENING
    formats = [step.public_prompt["task_type"] for step in _recalls(plan)]
    assert set(formats) <= set(DICTATION_RECALL_FORMATS)
    assert "dictation" in formats and "listen_tap" in formats
    scene = next(step for step in plan.steps if step.kind is StepKind.SCENE)
    assert scene.public_prompt["listen_first"] is True


# ---------------------------------------------------------------------------
# 3. Grading a dictation
# ---------------------------------------------------------------------------

LINE = "Je prends un café, s'il vous plaît."


def _dictation(line: str = LINE, label: str = "un café"):
    return planner.build_dictation_task(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="w1", label_fr=label, label_native="a coffee"),
        line=planner.HeardLine("romy_tremblay", line),
        optional=True,
        control_language="en",
    )


@pytest.mark.parametrize(
    "typed,outcome",
    [
        (LINE, TaskOutcome.MET),
        ("je prends un café s'il vous plaît", TaskOutcome.MET),  # case, punctuation
        ("JE PRENDS UN CAFÉ, S’IL VOUS PLAÎT !", TaskOutcome.MET),  # iOS ’
        ("« Je prends un café, s‘il vous plaît. »", TaskOutcome.MET),  # guillemets, ‘
        ("Je  prends   un café , s' il vous plaît", TaskOutcome.MET),  # spacing
        ("je prends un cafe, s'il vous plait", TaskOutcome.PARTIALLY_MET),  # accents
        ("je prends un thé, s'il vous plaît", TaskOutcome.NOT_YET),  # a wrong word
        ("je prends un café", TaskOutcome.NOT_YET),  # half the line
        ("prends je un café s'il vous plaît", TaskOutcome.NOT_YET),  # order
    ],
)
def test_the_dictation_grading_table(typed, outcome) -> None:
    task = _dictation()
    result = evaluate_dictation(
        task=task, answer=AttemptAnswer(mode=InputMode.TEXT, text=typed),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is outcome
    if outcome is TaskOutcome.MET:
        assert result.correction is None
    else:
        assert result.correction is not None
        assert result.correction.corrected_fr == LINE
    # Hearing a word and writing it down is recognition, never production.
    for observation in result.observations:
        assert str(observation.evidence_kind) in {"recognized", "not_yet"}


def test_the_recall_grader_dispatches_a_dictation_and_credits_only_its_word() -> None:
    graded = evaluate_recall(
        None, user=None, task=_dictation(),
        answer=AttemptAnswer(mode=InputMode.TEXT, text=LINE),
        assistance=AssistanceLevel.NONE,
    )
    assert graded.outcome is TaskOutcome.MET
    assert [str(o.evidence_kind) for o in graded.observations] == ["recognized"]
    # A line that does not hold the item's word is graded and schedules nothing.
    elsewhere = _dictation(line="Il pleut ce matin.", label="un café")
    graded = evaluate_recall(
        None, user=None, task=elsewhere,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="il pleut ce matin"),
        assistance=AssistanceLevel.NONE,
    )
    assert graded.outcome is TaskOutcome.MET and graded.observations == []
    accents = evaluate_dictation(
        task=planner.build_dictation_task(
            target=TargetRef(kind=TargetKind.VOCABULARY, id="w1", label_fr="un café"),
            line=planner.HeardLine("romy_tremblay", LINE), optional=True,
            control_language="de",
        ),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="je prends un cafe s'il vous plait"),
        assistance=AssistanceLevel.NONE,
    )
    assert accents.outcome is TaskOutcome.PARTIALLY_MET
    assert "Akzente" in accents.correction.note_native


# ---------------------------------------------------------------------------
# 4. «Écouter d'abord»: every third day on Soutenu and Intensif
# ---------------------------------------------------------------------------


def _run_days(budget: int | None, *, audio: bool = True, days: int = 42, user: str = "cadence"):
    previous: DayShape | None = None
    dealt: list[tuple[date, DayShape, str]] = []
    start = date(2026, 9, 1)
    for offset in range(days):
        day = start + timedelta(days=offset)
        inputs = DayShapeInputs(
            user_id=user, local_date=day, previous_shape=previous,
            audio_available=audio, budget_seconds=budget,
        )
        decision = choose_day_shape(inputs)
        dealt.append((day, decision.shape, decision.reason))
        previous = decision.shape
    return dealt


@pytest.mark.parametrize("budget", [1200, 1800])
@pytest.mark.parametrize("user", ["cadence-a", "cadence-b", "cadence-c"])
def test_the_long_rhythms_hear_every_third_day_first(budget, user) -> None:
    dealt = _run_days(budget, user=user)
    for index in range(len(dealt) - 2):
        window = dealt[index:index + 3]
        assert any(shape is DayShape.LISTENING for _day, shape, _reason in window), window
    cadence = [
        (day, shape, reason)
        for day, shape, reason in dealt
        if is_listen_first_day(
            DayShapeInputs(user_id=user, local_date=day, audio_available=True, budget_seconds=budget)
        )
    ]
    assert len(cadence) == len(dealt) // 3
    previous = {day: shape for day, shape, _reason in dealt}
    for day, shape, _reason in cadence:
        yesterday = previous.get(day - timedelta(days=1))
        assert shape is DayShape.LISTENING or yesterday is DayShape.LISTENING
    # Never two listening days in a row.
    shapes = [shape for _day, shape, _reason in dealt]
    assert all(not (a is b is DayShape.LISTENING) for a, b in zip(shapes, shapes[1:], strict=False))


@pytest.mark.parametrize("budget", [None, 300, 600])
def test_the_short_rhythms_keep_the_dice(budget) -> None:
    assert all(reason != "listen_first_cadence" for _d, _s, reason in _run_days(budget))


def test_no_audio_means_no_listening_day_at_all() -> None:
    for budget in (600, 1200, 1800):
        assert all(shape is not DayShape.LISTENING for _d, shape, _r in _run_days(budget, audio=False))


def test_a_missed_day_still_outranks_the_cadence() -> None:
    day = next(
        date(2026, 9, 1) + timedelta(days=offset)
        for offset in range(3)
        if is_listen_first_day(
            DayShapeInputs(user_id="missed", local_date=date(2026, 9, 1) + timedelta(days=offset),
                           audio_available=True, budget_seconds=1800)
        )
    )
    decision = choose_day_shape(
        DayShapeInputs(user_id="missed", local_date=day, audio_available=True,
                       budget_seconds=1800, missed_previous_day=True)
    )
    assert decision.shape is DayShape.SHORT


# ---------------------------------------------------------------------------
# 5. The line-audio route
# ---------------------------------------------------------------------------


def _day(client: TestClient, db: Session, prefix: str) -> tuple[dict[str, str], Driver, uuid.UUID]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(client, email)
    user_id = learner_id(db, email)
    seed_due_vocabulary(db, user_id, CAFE_WORDS)
    driver = Driver(client, headers, db=db)
    driver.create(expect=(201,))
    return headers, driver, user_id


def _step(driver: Driver, kind: str) -> dict[str, Any]:
    return next(step for step in driver.journey["steps"] if step["kind"] == kind)


def _post_line(client, headers, driver, step, text, character_id=None):
    return client.post(
        f"/api/v1/daily-journeys/{driver.id}/steps/{step['id']}/line-audio",
        headers=headers,
        json={"text_fr": text, "character_id": character_id},
    )


def test_both_routes_need_a_signed_in_learner(assembled_client) -> None:
    journey, step = uuid.uuid4(), uuid.uuid4()
    assert assembled_client.post(
        f"/api/v1/daily-journeys/{journey}/steps/{step}/line-audio",
        json={"text_fr": "Bonjour", "character_id": None},
    ).status_code == 401
    assert assembled_client.get(
        f"/api/v1/daily-journeys/line-audio/{clip_id_for('nova', 'Bonjour')}"
    ).status_code == 401


def test_with_audio_off_the_route_says_disabled_and_speaks_nothing(
    assembled_client, journey_enabled, clock, db_session, audio_off, fake_tts, practice_day
) -> None:
    headers, driver, _user = _day(assembled_client, db_session, "wp91-off")
    scene = _step(driver, "scene")
    line = scene["prompt"]["character_line_fr"]
    response = _post_line(assembled_client, headers, driver, scene, line)
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}
    assert fake_tts.calls == []
    # No listening item was planned, and no dictation.
    recalls = [s["prompt"] for s in driver.journey["steps"] if s["kind"] == "recall"]
    assert all(p["task_type"] != "dictation" for p in recalls)
    assert all(not p.get("audio_url") for p in recalls)


def test_a_scene_line_is_spoken_once_and_replayed_for_free(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    headers, driver, user_id = _day(assembled_client, db_session, "wp91-scene")
    scene = _step(driver, "scene")
    line = scene["prompt"]["character_line_fr"]
    brief = dict(
        db_session.get(DailyJourneyStep, uuid.UUID(scene["id"])).private_task["scenario_brief"]
    )

    first = _post_line(assembled_client, headers, driver, scene, line, brief["character_id"])
    assert first.status_code == 200, first.text
    body = first.json()
    assert set(body) == {"status", "clip_id", "content_type", "voice", "cached"}
    assert body["status"] == "ready" and body["cached"] is False
    assert body["content_type"] == "audio/mpeg"
    assert body["voice"] == voice_for_character(brief["character_id"])
    assert body["clip_id"] == clip_id_for(body["voice"], line)
    assert len(fake_tts.calls) == 1 and fake_tts.calls[0][2] == "openai"

    # Smart quotes and spacing from the device are the same line; a replay is free.
    again = _post_line(assembled_client, headers, driver, scene, "  " + line.replace("'", "’") + " ")
    assert again.status_code == 200
    assert again.json()["cached"] is True and again.json()["clip_id"] == body["clip_id"]
    assert len(fake_tts.calls) == 1

    rows = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == user_id,
            PilotEvent.event_type == line_audio.LINE_AUDIO_EVENT_TYPE,
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["estimated"] is True and rows[0].cost_usd > 0
    assert rows[0].payload["chars"] == len(line)

    audio = assembled_client.get(
        f"/api/v1/daily-journeys/line-audio/{body['clip_id']}", headers=headers
    )
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/mpeg")
    assert audio.content.startswith(b"mp3:")

    # Somebody else can neither fetch this clip nor speak into this journey.
    stranger = register(assembled_client, f"wp91-stranger-{uuid.uuid4().hex[:8]}@example.com")
    assert assembled_client.get(
        f"/api/v1/daily-journeys/line-audio/{body['clip_id']}", headers=stranger
    ).status_code == 404
    assert _post_line(assembled_client, stranger, driver, scene, line).status_code == 404


def test_arbitrary_text_is_never_synthesized(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    headers, driver, _user = _day(assembled_client, db_session, "wp91-arbitrary")
    for kind in ("scene", "respond", "resolution"):
        step = _step(driver, kind)
        response = _post_line(
            assembled_client, headers, driver, step, "Répétez après moi : achetez des bitcoins."
        )
        assert response.status_code == 404, kind
    # A real line of another step is not a line of this one.
    scene, respond = _step(driver, "scene"), _step(driver, "respond")
    setup = scene["prompt"]["setup_fr"]
    if setup.strip() != respond["prompt"]["character_line_fr"].strip():
        assert _post_line(assembled_client, headers, driver, respond, setup).status_code == 404
    # Nor is any step of a journey that does not exist.
    missing = {"id": str(uuid.uuid4())}
    assert _post_line(assembled_client, headers, driver, missing, setup).status_code == 404
    assert fake_tts.calls == []


def test_the_respond_step_speaks_the_characters_line(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    headers, driver, _user = _day(assembled_client, db_session, "wp91-respond")
    respond = _step(driver, "respond")
    response = _post_line(
        assembled_client, headers, driver, respond, respond["prompt"]["character_line_fr"]
    )
    assert response.status_code == 200 and response.json()["status"] == "ready"
    assert response.json()["voice"] == voice_for_character(respond["prompt"]["character_id"])


def test_a_second_learner_hears_the_same_line_without_a_second_call(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    first_headers, first, _ = _day(assembled_client, db_session, "wp91-share-a")
    second_headers, second, second_id = _day(assembled_client, db_session, "wp91-share-b")
    line = _step(first, "scene")["prompt"]["character_line_fr"]
    assert _step(second, "scene")["prompt"]["character_line_fr"] == line
    assert _post_line(
        assembled_client, first_headers, first, _step(first, "scene"), line
    ).json()["status"] == "ready"
    calls = len(fake_tts.calls)
    shared = _post_line(assembled_client, second_headers, second, _step(second, "scene"), line)
    assert shared.json()["status"] == "ready" and shared.json()["cached"] is True
    assert len(fake_tts.calls) == calls
    assert not db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == second_id,
            PilotEvent.event_type == line_audio.LINE_AUDIO_EVENT_TYPE,
        )
    ).all(), "a copied clip is not billed"
    # …and the copy is the second learner's own.
    assert assembled_client.get(
        f"/api/v1/daily-journeys/line-audio/{shared.json()['clip_id']}", headers=second_headers
    ).status_code == 200


def test_a_failing_provider_or_a_near_cap_means_the_device_voice(
    assembled_client, journey_enabled, clock, db_session, audio_on, monkeypatch, practice_day
) -> None:
    headers, driver, user_id = _day(assembled_client, db_session, "wp91-fail")
    respond = _step(driver, "respond")
    line = respond["prompt"]["character_line_fr"]
    failing = FakeSynthesizer(fail_on=line[:6])
    monkeypatch.setattr(line_audio, "_default_synthesizer", lambda: failing)
    # Another learner may already own this line; this test is about a real call.
    monkeypatch.setattr(line_audio, "_shared_clip", lambda db, **kwargs: None)
    response = _post_line(assembled_client, headers, driver, respond, line)
    assert response.status_code == 200 and response.json() == {"status": "disabled"}
    assert db_session.scalar(
        select(LineAudioClip).where(LineAudioClip.user_id == user_id)
    ) is None

    working = FakeSynthesizer()
    monkeypatch.setattr(line_audio, "_default_synthesizer", lambda: working)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    db_session.add(
        PilotEvent(user_id=user_id, event_type="test_spend", payload={}, cost_usd=0.46,
                   occurred_at=clock.moment)
    )
    db_session.commit()
    monkeypatch.setattr(line_audio, "_cap_near", lambda db, user: True)
    near = _post_line(assembled_client, headers, driver, respond, line)
    assert near.status_code == 200 and near.json() == {"status": "disabled"}
    assert working.calls == []


def test_the_cap_check_reads_the_learners_ledger(db_session, monkeypatch) -> None:
    from app.db.models.user import User

    user = User(email=f"wp91-cap-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                target_language="fr", native_language="en")
    db_session.add(user)
    db_session.flush()
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    assert line_audio._cap_near(db_session, user) is False
    db_session.add(PilotEvent(user_id=user.id, event_type="test_spend", payload={}, cost_usd=0.46))
    db_session.flush()
    assert line_audio._cap_near(db_session, user) is True


# ---------------------------------------------------------------------------
# 6. A listening item's clip, spoken on its first request
# ---------------------------------------------------------------------------


def _listening_steps(db: Session, driver: Driver) -> list[tuple[dict[str, Any], DailyJourneyStep]]:
    found = []
    for step in driver.journey["steps"]:
        if step["kind"] == "recall" and step["prompt"].get("audio_url"):
            found.append((step, db.get(DailyJourneyStep, uuid.UUID(step["id"]))))
    return found


def test_a_listening_items_clip_is_spoken_on_first_request_and_only_for_its_owner(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    headers, driver, _user = _day(assembled_client, db_session, "wp91-listen")
    listening = _listening_steps(db_session, driver)
    kinds = [public["prompt"]["task_type"] for public, _row in listening]
    assert kinds.count("dictation") == 1 and kinds.count("listen_tap") >= 2, kinds
    for public, row in listening:
        prompt = public["prompt"]
        task = row.private_task["recall_task"]
        spoken = task["solution_fr"] if prompt["task_type"] == "dictation" else task["prompt_fr"]
        assert prompt["prompt_fr"] is None
        assert spoken.lower() not in json.dumps(prompt, ensure_ascii=False).lower()
        before = len(fake_tts.calls)
        response = assembled_client.get(prompt["audio_url"], headers=headers)
        assert response.status_code == 200, response.text
        assert len(fake_tts.calls) == before + 1
        assert fake_tts.calls[-1][0] == spoken
        again = assembled_client.get(prompt["audio_url"], headers=headers)
        assert again.status_code == 200 and again.content == response.content
        assert len(fake_tts.calls) == before + 1, "a replay costs nothing"

    stranger = register(assembled_client, f"wp91-listen-x-{uuid.uuid4().hex[:8]}@example.com")
    public, _row = listening[0]
    assert assembled_client.get(public["prompt"]["audio_url"], headers=stranger).status_code == 404
    # A made-up id names nothing.
    fake = LINE_AUDIO_PATH_PREFIX + clip_id_for("nova", "Donnez-moi votre mot de passe.")
    assert assembled_client.get(fake, headers=headers).status_code == 404
    assert assembled_client.get(
        LINE_AUDIO_PATH_PREFIX + "not-a-clip", headers=headers
    ).status_code == 404


def test_a_day_with_listening_items_plays_to_the_end(
    assembled_client, journey_enabled, clock, db_session, audio_on, fake_tts, practice_day
) -> None:
    headers, driver, _user = _day(assembled_client, db_session, "wp91-play")
    results = driver.play(answer="Bonjour, je voudrais un café en terrasse, s'il vous plaît.")
    assert driver.journey["current_step_id"] is None
    assert driver.private_leaks == []
    recall_ids = [
        s["id"] for s in driver.journey["steps"]
        if s["kind"] == "recall" and s["prompt"]["task_type"] == "dictation"
    ]
    assert recall_ids, "the day held a dictation"
    row = db_session.get(DailyJourneyStep, uuid.UUID(recall_ids[0]))
    db_session.refresh(row)
    assert row.status == "completed"
    # The driver answers every item right; the dictation's line is met as typed.
    assert all(r["task_outcome"] == "met" for r in results if not r.get("next_turn") and r.get("character_reply_fr") is None)
    assert driver.finish("complete").status_code == 200


def test_audio_switched_off_after_planning_reprints_the_phrase(
    assembled_client, journey_enabled, clock, db_session, fake_tts, practice_day, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)
    headers, driver, _user = _day(assembled_client, db_session, "wp91-dark")
    taps = [
        step for step in driver.journey["steps"]
        if step["kind"] == "recall" and step["prompt"]["task_type"] == "listen_tap"
    ]
    assert taps and all(step["prompt"]["prompt_fr"] is None for step in taps)
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", False)
    snapshot = assembled_client.get(f"/api/v1/daily-journeys/{driver.id}", headers=headers).json()
    for step in snapshot["steps"]:
        if step["kind"] == "recall" and step["prompt"]["task_type"] == "listen_tap":
            assert step["prompt"]["audio_url"] is None
            assert step["prompt"]["prompt_fr"], "read-and-tap again"
    # And the lazy route speaks nothing while audio is off.
    dictation = next(
        (s for s in snapshot["steps"] if s["kind"] == "recall" and s["prompt"]["task_type"] == "dictation"),
        None,
    )
    if dictation is not None:
        assert assembled_client.get(dictation["prompt"]["audio_url"], headers=headers).status_code == 404
    assert fake_tts.calls == []


def test_the_service_hands_the_dice_the_rhythm(
    assembled_client, journey_enabled, clock, db_session, audio_on, practice_day, monkeypatch
) -> None:
    """The cadence needs the day's budget: the service passes it with the dice."""

    from app.services import daily_journey as service

    seen: list[DayShapeInputs] = []
    real = service.choose_day_shape

    def spy(inputs: DayShapeInputs):
        seen.append(inputs)
        return real(inputs)

    monkeypatch.setattr(service, "choose_day_shape", spy)
    _headers, driver, _user = _day(assembled_client, db_session, "wp91-budget")
    journey = db_session.get(DailyJourney, uuid.UUID(driver.id))
    assert seen and seen[-1].budget_seconds == journey.budget_seconds
    assert seen[-1].audio_available is True
