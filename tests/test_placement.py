"""WP-25 — an honest placement in the first five minutes.

What these tests hold down, in the order the package promises it:

1. the adaptive ladder escalates, holds and de-escalates on the evidence, and
   never moves on a turn nobody graded;
2. the estimate math weighs later turns more, reports a confidence that falls
   when the turns disagree, and refuses to name a level with no evidence;
3. the placement becomes the CEFR prior, outranks the declaration, and is
   overtaken by measurement once the attempts exist;
4. a provider that does not answer yields "non évalué", never a fabricated band;
5. the placement is resumable and idempotent — a replayed turn pays nothing.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.pilot_event import PilotEvent
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.services.cefr_progress import (
    DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
    CEFRProgressService,
)
from app.services.placement import (
    MAX_TURNS,
    MIN_PRIOR_CONFIDENCE,
    MIN_TURNS,
    PLACEMENT_BANDS,
    PLACEMENT_EVENT_TYPE,
    PROMPT_BANK,
    PlacementService,
    band_index,
    clamp_band,
    estimate_from_turns,
    latest_placement_prior,
    next_band,
    normalize_grading,
    opening_band,
    should_continue,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _user(db_session, *, email: str | None = None, declared: str = "A1") -> User:
    user = User(
        id=uuid4(),
        email=email or f"placement-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=declared,
        cefr_estimate="A1.1",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _turn(band: str, score: float, *, grader_band: str | None = None, dims: float | None = None) -> dict:
    value = score if dims is None else dims
    return {
        "band": band,
        "prompt_fr": PROMPT_BANK[band].prompt_fr,
        "answer": "Je voudrais un café, s’il vous plaît.",
        "grading": {
            "score_0_4": score,
            "demonstrated_band": grader_band,
            "dimensions": {"range": value, "accuracy": value, "coherence": value, "task": value},
            "evidence_fr": "phrase complète et correcte",
            "model": "test-model",
        },
    }


class _FakeLLM:
    """A grader that answers with whatever the test told it to answer.

    ``scores`` is consumed one per call; ``raise_on`` makes a call fail the way
    a real provider fails — an exception with tokens already billed and no
    content — which is the case the honesty test exists for.
    """

    def __init__(self, scores: list[float], *, fail_all: bool = False, junk: bool = False):
        self.scores = list(scores)
        self.fail_all = fail_all
        self.junk = junk
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        self.calls += 1
        if self.fail_all:
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("openai: The read operation timed out")
        if self.junk:
            content = json.dumps({"nonsense": True})
        else:
            score = self.scores.pop(0) if self.scores else 2.0
            content = json.dumps(
                {
                    "score_0_4": score,
                    "demonstrated_band": None,
                    "dimensions": {
                        "range": score,
                        "accuracy": score,
                        "coherence": score,
                        "task": score,
                    },
                    "evidence_fr": "réponse complète",
                    "off_task": False,
                }
            )
        return SimpleNamespace(
            content=content,
            model="test-model",
            provider="test",
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            cost=0.0004,
        )


def _run(db_session, user, llm) -> PlacementSession:
    service = PlacementService(db_session, llm_service=llm)
    session = service.start(user)
    while session.status == "in_progress":
        session = service.respond(
            session, answer="Je voudrais un café, s’il vous plaît.", turn_index=len(session.turns or [])
        )
    return session


# ---------------------------------------------------------------------------
# 1. the adaptive ladder
# ---------------------------------------------------------------------------


def test_a_strong_answer_escalates_a_weak_one_de_escalates_a_middling_one_holds():
    assert next_band("A2.1", 4.0) == "A2.2"
    assert next_band("A2.1", 3.0) == "A2.2"
    assert next_band("A2.1", 2.0) == "A2.1"
    assert next_band("A2.1", 1.0) == "A1.2"
    assert next_band("A2.1", 0.0) == "A1.2"


def test_an_ungraded_turn_moves_the_ladder_in_neither_direction():
    """A missing measurement is not a bad one. It must not demote the learner."""
    assert next_band("B1.1", None) == "B1.1"


def test_the_ladder_never_walks_off_either_end():
    assert next_band(PLACEMENT_BANDS[0], 0.0) == PLACEMENT_BANDS[0]
    assert next_band(PLACEMENT_BANDS[-1], 4.0) == PLACEMENT_BANDS[-1]
    assert clamp_band(-5) == PLACEMENT_BANDS[0]
    assert clamp_band(500) == PLACEMENT_BANDS[-1]


def test_every_band_on_the_ladder_has_a_prompt():
    assert set(PROMPT_BANK) == set(PLACEMENT_BANDS)
    for band, prompt in PROMPT_BANK.items():
        assert prompt.band == band
        assert prompt.prompt_fr and prompt.hint_fr


def test_the_opening_rung_sits_one_below_the_declaration(db_session):
    """Failing the first question is a bad first minute; the ladder climbs fast."""
    assert opening_band(_user(db_session, declared="B1")) == "A2.2"
    assert opening_band(_user(db_session, declared="A1")) == "A1.2"
    # C1/C2 clamp to B2.2 on the internal scale; one rung below is the top
    # of the placement ladder, which is as high as this prompt bank can measure.
    assert opening_band(_user(db_session, declared="C2")) == "B2.1"
    assert opening_band(None) == "A1.2"


def test_a_strong_run_climbs_the_ladder_end_to_end(db_session):
    user = _user(db_session, declared="A1")
    llm = _FakeLLM([4.0] * MAX_TURNS)
    session = _run(db_session, user, llm)
    bands = [turn["band"] for turn in session.turns]
    assert bands == sorted(bands, key=band_index)
    assert band_index(bands[-1]) > band_index(bands[0])
    assert session.status == "complete"


def test_a_weak_run_descends_and_lands_at_the_bottom(db_session):
    user = _user(db_session, declared="B2")
    session = _run(db_session, user, _FakeLLM([0.5] * MAX_TURNS))
    assert session.status == "complete"
    assert session.estimate_level == PLACEMENT_BANDS[0]


# ---------------------------------------------------------------------------
# 2. the estimate math
# ---------------------------------------------------------------------------


def test_no_graded_turn_means_no_level_at_all():
    estimate = estimate_from_turns([{"band": "A1.2", "answer": "x", "grading": None}])
    assert estimate.status == "unassessed"
    assert estimate.level is None
    assert estimate.confidence == 0.0
    assert estimate.graded_turns == 0


def test_the_estimate_leans_on_the_later_turns(db_session):
    """The ladder converges, so the last rung is the better evidence."""
    early_low = estimate_from_turns(
        [_turn("A1.2", 1.0), _turn("A1.2", 1.0), _turn("B1.1", 4.0), _turn("B1.2", 4.0)]
    )
    late_low = estimate_from_turns(
        [_turn("B1.2", 4.0), _turn("B1.1", 4.0), _turn("A1.2", 1.0), _turn("A1.2", 1.0)]
    )
    assert band_index(early_low.level) > band_index(late_low.level)


def test_agreeing_turns_are_more_confident_than_disagreeing_ones():
    steady = estimate_from_turns([_turn("A2.1", 3.0) for _ in range(4)])
    erratic = estimate_from_turns(
        [_turn("A1.1", 0.0), _turn("B2.1", 4.0), _turn("A1.1", 0.0), _turn("B2.1", 4.0)]
    )
    assert steady.confidence > erratic.confidence
    assert 0.0 < erratic.confidence <= steady.confidence <= 0.92


def test_the_estimate_carries_its_dimensions_and_its_evidence():
    estimate = estimate_from_turns([_turn("A2.1", 3.0, dims=2.5) for _ in range(4)])
    assert set(estimate.dimensions) == {"range", "accuracy", "coherence", "task"}
    assert estimate.dimensions["accuracy"] == pytest.approx(2.5)
    payload = estimate.as_dict()
    assert payload["dimension_labels"]["accuracy"] == "Correction grammaticale"
    assert len(payload["evidence"]) == 4
    assert payload["evidence"][0]["prompt_fr"]
    assert payload["evidence"][0]["evidence_fr"] == "phrase complète et correcte"


def test_the_graders_own_read_lifts_a_learner_writing_above_the_rung():
    """A learner who writes B2 French at an A1 prompt is not capped at A1."""
    capped = estimate_from_turns([_turn("A1.1", 4.0) for _ in range(4)])
    lifted = estimate_from_turns([_turn("A1.1", 4.0, grader_band="B1.2") for _ in range(4)])
    assert band_index(lifted.level) > band_index(capped.level)


def test_the_conversation_stops_between_four_and_six_turns():
    steady = [_turn("A2.1", 3.0) for _ in range(MIN_TURNS)]
    assert should_continue(steady[:2], estimate_from_turns(steady[:2])) is True
    assert should_continue(steady[:MIN_TURNS], estimate_from_turns(steady[:MIN_TURNS])) is False
    erratic = [_turn("A1.1", 0.0), _turn("B2.1", 4.0), _turn("A1.1", 0.0), _turn("B2.1", 4.0)]
    assert should_continue(erratic, estimate_from_turns(erratic)) is True
    long_run = erratic + [_turn("A1.1", 0.0), _turn("B2.1", 4.0)]
    assert len(long_run) == MAX_TURNS
    assert should_continue(long_run, estimate_from_turns(long_run)) is False


def test_a_real_session_never_exceeds_the_five_minute_turn_budget(db_session):
    session = _run(db_session, _user(db_session), _FakeLLM([0.0, 4.0, 0.0, 4.0, 0.0, 4.0]))
    assert MIN_TURNS <= len(session.turns) <= MAX_TURNS


# ---------------------------------------------------------------------------
# 3. the grading contract
# ---------------------------------------------------------------------------


def test_an_unusable_grading_raises_rather_than_scoring_zero():
    """A zero would push the ladder down on a provider hiccup. It must not."""
    for junk in ({}, {"score_0_4": "high"}, {"score_0_4": 9}, {"score_0_4": True}):
        with pytest.raises(ValueError):
            normalize_grading(junk)
    with pytest.raises(ValueError):
        normalize_grading({"score_0_4": 3, "dimensions": {}})
    with pytest.raises(ValueError):
        normalize_grading(
            {"score_0_4": 3, "demonstrated_band": "C1", "dimensions": {"range": 3}}
        )


def test_an_off_task_response_scores_zero_and_demonstrates_nothing():
    graded = normalize_grading(
        {
            "score_0_4": 3,
            "demonstrated_band": "B1.1",
            "dimensions": {"range": 3, "accuracy": 3, "coherence": 3, "task": 3},
            "evidence_fr": "réponse en anglais",
            "off_task": True,
        }
    )
    assert graded["score_0_4"] == 0.0
    assert graded["demonstrated_band"] is None
    assert set(graded["dimensions"].values()) == {0.0}


# ---------------------------------------------------------------------------
# 4. provider-failure honesty
# ---------------------------------------------------------------------------


def test_a_provider_that_never_answers_yields_no_level(db_session):
    user = _user(db_session)
    session = _run(db_session, user, _FakeLLM([], fail_all=True))
    assert session.status == "unassessed"
    assert session.estimate_level is None
    assert session.confidence == 0.0
    assert session.estimate["status"] == "unassessed"
    assert session.estimate["level"] is None


def test_an_unparseable_grader_yields_no_level_either(db_session):
    session = _run(db_session, _user(db_session), _FakeLLM([], junk=True))
    assert session.status == "unassessed"
    assert session.estimate_level is None


def test_an_unassessed_placement_is_not_offered_to_the_cefr_service(db_session):
    user = _user(db_session)
    _run(db_session, user, _FakeLLM([], fail_all=True))
    assert latest_placement_prior(db_session, user) is None


def test_a_placement_with_no_grader_at_all_never_invents_a_band(db_session):
    """No LLM configured is the same honesty case as a failing one."""
    user = _user(db_session)
    service = PlacementService(db_session, llm_service=None)
    service._llm_unavailable = True
    session = service.start(user)
    while session.status == "in_progress":
        session = service.respond(session, answer="Bonjour", turn_index=len(session.turns or []))
    assert session.status == "unassessed"
    assert session.estimate_level is None


def test_a_low_confidence_placement_is_not_used_as_a_prior(db_session):
    user = _user(db_session)
    session = PlacementSession(
        user_id=user.id,
        status="complete",
        current_band="B1.1",
        turns=[],
        estimate={"graded_turns": 2},
        estimate_level="B1.1",
        confidence=MIN_PRIOR_CONFIDENCE - 0.1,
    )
    db_session.add(session)
    db_session.commit()
    assert latest_placement_prior(db_session, user) is None


# ---------------------------------------------------------------------------
# 5. resumable and idempotent
# ---------------------------------------------------------------------------


def test_starting_twice_resumes_one_session(db_session):
    user = _user(db_session)
    service = PlacementService(db_session, llm_service=_FakeLLM([3.0] * MAX_TURNS))
    first = service.start(user)
    second = service.start(user)
    assert first.id == second.id
    assert db_session.query(PlacementSession).filter_by(user_id=user.id).count() == 1


def test_a_replayed_turn_is_graded_once_and_paid_for_once(db_session):
    user = _user(db_session)
    llm = _FakeLLM([3.0] * MAX_TURNS)
    service = PlacementService(db_session, llm_service=llm)
    session = service.start(user)
    session = service.respond(session, answer="Bonjour, je m’appelle Léa.", turn_index=0)
    calls_after_first = llm.calls
    events_after_first = db_session.query(PilotEvent).filter_by(event_type=PLACEMENT_EVENT_TYPE).count()

    # The same request again — a retried POST, a double tap, a flaky network.
    session = service.respond(session, answer="Bonjour, je m’appelle Léa.", turn_index=0)

    assert llm.calls == calls_after_first
    assert len(session.turns) == 1
    assert (
        db_session.query(PilotEvent).filter_by(event_type=PLACEMENT_EVENT_TYPE).count()
        == events_after_first
    )


def test_a_resumed_session_keeps_its_graded_turns(db_session):
    user = _user(db_session)
    llm = _FakeLLM([3.0] * MAX_TURNS)
    service = PlacementService(db_session, llm_service=llm)
    session = service.start(user)
    session = service.respond(session, answer="Bonjour.", turn_index=0)
    band_after_one = session.current_band

    resumed = PlacementService(db_session, llm_service=llm).start(user)
    assert resumed.id == session.id
    assert len(resumed.turns) == 1
    assert resumed.current_band == band_after_one


def test_a_re_run_supersedes_the_open_session_rather_than_competing_with_it(db_session):
    user = _user(db_session)
    service = PlacementService(db_session, llm_service=_FakeLLM([3.0] * MAX_TURNS))
    first = service.start(user)
    second = service.start(user, restart=True)
    db_session.refresh(first)
    assert second.id != first.id
    assert first.status == "abandoned"
    assert service.active_session(user).id == second.id


def test_skipping_records_the_refusal_so_the_offer_is_made_once(db_session):
    user = _user(db_session)
    service = PlacementService(db_session)
    skipped = service.skip(user)
    assert skipped.status == "skipped"
    assert service.latest_session(user).id == skipped.id
    assert latest_placement_prior(db_session, user) is None


# ---------------------------------------------------------------------------
# 6. cost telemetry
# ---------------------------------------------------------------------------


def test_one_priced_pilot_event_per_grading_call(db_session):
    user = _user(db_session)
    llm = _FakeLLM([3.0] * MAX_TURNS)
    session = _run(db_session, user, llm)
    events = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == PLACEMENT_EVENT_TYPE, PilotEvent.user_id == user.id)
        .all()
    )
    assert len(events) == llm.calls == len(session.turns)
    for event in events:
        assert event.cost_usd == pytest.approx(0.0004)
        assert event.entity_type == "placement_session"
        assert event.payload["total_tokens"] == 140
        assert event.payload["band"] in PLACEMENT_BANDS


def test_a_failed_call_writes_no_cost_row(db_session):
    """Nothing was billed because nothing was answered; the ledger must agree."""
    user = _user(db_session)
    _run(db_session, user, _FakeLLM([], fail_all=True))
    assert (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == PLACEMENT_EVENT_TYPE, PilotEvent.user_id == user.id)
        .count()
        == 0
    )


# ---------------------------------------------------------------------------
# 7. the CEFR prior
# ---------------------------------------------------------------------------


def test_the_placement_outranks_the_declaration(db_session):
    """A declared A1 who places at A2.2 is served A2.2, not A1.1."""
    user = _user(db_session, declared="A1")
    _run(db_session, user, _FakeLLM([4.0] * MAX_TURNS))
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate_source"] == "placement"
    assert payload["declared_level"] == "A1.1"
    assert band_index(payload["estimate"]) > band_index("A1.1")
    assert payload["placement"]["level"] == payload["estimate"]
    assert payload["placement"]["confidence"] >= MIN_PRIOR_CONFIDENCE


def test_the_payload_says_a_placement_is_not_verified_in_app_work(db_session):
    user = _user(db_session, declared="A1")
    _run(db_session, user, _FakeLLM([4.0] * MAX_TURNS))
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    # The learner's French was measured; their in-app counters are still zero,
    # and the breakdown must not draw them as a verified level.
    assert payload["breakdown"]["status"] == "unverified"


def test_without_a_placement_the_declaration_still_stands(db_session):
    user = _user(db_session, declared="B1")
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate_source"] == "declared"
    assert payload["estimate"] == "B1.1"
    assert payload["placement"] is None


def test_measurement_overtakes_the_placement_once_the_attempts_exist(db_session):
    user = _user(db_session, declared="A1")
    _run(db_session, user, _FakeLLM([4.0] * MAX_TURNS))
    placed = CEFRProgressService(db_session).recompute(user, source="test")
    assert placed["estimate_source"] == "placement"

    mission = RealWorldMission(
        user_id=user.id,
        status="completed",
        cadence="ad_hoc",
        mission_type="message",
        title="Placement fixture",
        brief="Reply clearly.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={},
        recap_payload={},
    )
    db_session.add(mission)
    db_session.flush()
    for _ in range(DECLARED_LEVEL_EVIDENCE_ATTEMPTS):
        db_session.add(
            RealWorldMissionAttempt(
                mission_id=mission.id,
                user_id=user.id,
                mode="chat",
                answer_payload={"text": "Bon."},
                correction_payload={},
                verdict="passed",
                score_0_4=1.0,
            )
        )
    db_session.commit()

    measured = CEFRProgressService(db_session).recompute(user, source="test")
    assert measured["estimate_source"] == "measured"
    # The prior no longer holds the estimate up: what remains above the raw
    # threshold walk is the existing down-step smoothing (three consecutive
    # weaker recomputes before a level falls), not the placement.
    assert measured["computed_estimate"] == "A1.1"
    for _ in range(3):
        measured = CEFRProgressService(db_session).recompute(user, source="test")
    assert measured["estimate"] == "A1.1"
    assert measured["estimate_source"] == "measured"
    # The placement is still reported — it happened, and the learner can see it.
    assert measured["placement"]["level"] == placed["estimate"]


def test_a_placement_below_the_measurement_does_not_hold_a_learner_back(db_session):
    """A prior is a floor, never a ceiling."""
    user = _user(db_session, declared="A1")
    session = PlacementSession(
        user_id=user.id,
        status="complete",
        current_band="A1.1",
        turns=[],
        estimate={"graded_turns": 4},
        estimate_level="A1.1",
        confidence=0.8,
    )
    db_session.add(session)
    db_session.commit()
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate_source"] in {"measured", "placement"}
    assert band_index(payload["estimate"]) >= band_index("A1.1")


def test_one_low_turn_at_a_newly_reached_band_is_a_second_chance_not_a_descent():
    """2026-09-17 calibration: a B1 learner who misread one B1.1 prompt was sent
    straight back to A2 and placed one band low. The first low turn at a band
    holds the rung; a second low turn there descends."""
    history = [_turn("A2.1", 3.0), _turn("A2.2", 4.0)]
    # first low turn at B1.1: hold
    assert next_band("B1.1", 1.0, history) == "B1.1"
    # a second low turn at B1.1 descends
    assert next_band("B1.1", 1.0, history + [_turn("B1.1", 1.0)]) == "A2.2"
    # without a history the rule is the plain ladder (older callers)
    assert next_band("B1.1", 1.0) == "A2.2"
    # a learner who *started* at B1.1 (declared high) and scores low has earned
    # no second chance: the ladder descends at once
    assert next_band("B1.1", 1.0, []) == "A2.2"
    assert next_band("B1.1", 1.0, [_turn("B1.1", None)]) == "A2.2"
    # a strong turn still climbs, an ungraded one still holds
    assert next_band("B1.1", 4.0, history) == "B1.2"
    assert next_band("B1.1", None, history) == "B1.1"
