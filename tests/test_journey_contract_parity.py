"""Integration owner's parity gate: real service output vs the WP-00 frozen fixtures.

Each package tests itself. This file tests that the packages agree with the frozen
contract and with each other — the failure mode a per-package suite cannot catch.
"""
from __future__ import annotations

import json
import pathlib
from uuid import uuid4

import pytest

from app.db.models import User
from app.services import journey_content
from app.services.journey_contracts import (
    MAX_RECALL_STEPS,
    MAX_RESPOND_TURNS,
    AssistanceLevel,
    CapabilityKey,
    InputMode,
    normalize_control_language,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "daily_journey_v1" / "public"

# Evaluator material that must never reach a renderer payload.
PRIVATE_MARKERS = (
    "rubric", "accepted_answers", "correct_option_id", "correct_tile_order",
    "solution_fr", "allowed_outcomes", "required_intents", "optional_intents",
    "suggested_response_fr", "target_answer",
)


@pytest.fixture()
def learner(db_session):
    """A real persisted learner; no fixture names or fake progress leak into shipping paths."""

    user = User(
        id=uuid4(),
        email=f"{uuid4()}@parity.test",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["response"]


def _brief(db, user, scenario_key: CapabilityKey):
    result = journey_content.resolve_scenario_brief(
        db, user=user, scenario_key=scenario_key, input_mode=InputMode.TEXT,
        allow_generation=False,
    )
    assert not isinstance(result, journey_content.ContentUnavailable), result
    return result


def test_cafe_descriptor_matches_the_frozen_fixture(db_session, learner) -> None:
    """WP-03's real café output is the payload WP-00 froze and WP-07 will render."""

    learner.native_language = "en"
    learner.cefr_estimate = "A1.1"
    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert brief.public_descriptor() == _fixture("cafe_journey_created")["scenario"]


@pytest.mark.parametrize(
    "language,fixture",
    [("de", "controls_de"), ("fr", "controls_fr"), ("en", "first_day")],
)
def test_control_language_descriptors_match(db_session, learner, language, fixture) -> None:
    learner.native_language = language
    learner.cefr_estimate = "A1.1"
    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert brief.public_descriptor() == _fixture(fixture)["available"]


def test_an_unsupported_control_language_falls_back_to_english(db_session, learner) -> None:
    learner.native_language = "pt-BR"
    learner.cefr_estimate = "A1.1"
    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert normalize_control_language(learner.native_language) == "en"
    assert brief.public_descriptor() == _fixture("first_day")["available"]


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_every_scenario_family_is_publishable_and_bounded(
    db_session, learner, scenario_key
) -> None:
    """A brief must be renderable, answerable, and inside the five-minute envelope."""

    learner.native_language = "en"
    brief = _brief(db_session, learner, scenario_key)

    assert brief.setup_fr and brief.setup_native, "the scene must be readable"
    assert brief.objective_native, "the learner must know what they are trying to do"
    assert brief.character_id and brief.location_id, "a real cast and place"
    assert brief.estimated_seconds <= 300, brief.estimated_seconds

    task = brief.response_task
    assert task.max_turns <= MAX_RESPOND_TURNS
    assert task.required_intents, "a purposeful response needs an obligation"
    assert task.allowed_outcomes, "consequences must be typed, not model-invented"
    assert brief.resolution_lines, "every scenario needs an ending"
    for outcome in task.allowed_outcomes:
        assert outcome in brief.resolution_lines, f"{outcome} has no ending line"
        assert outcome in brief.resolution_summaries, f"{outcome} has no native summary"


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_public_descriptor_never_carries_evaluator_material(
    db_session, learner, scenario_key
) -> None:
    brief = _brief(db_session, learner, scenario_key)
    serialized = json.dumps(brief.public_descriptor(), ensure_ascii=False)
    for marker in PRIVATE_MARKERS:
        assert marker not in serialized, f"{scenario_key} leaks {marker}"


def test_the_suggested_reply_exists_but_stays_assistance(db_session, learner) -> None:
    """Copying it must be possible only through the help endpoint, never by default."""

    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert brief.response_task.suggested_response_fr, "help must have something to reveal"
    assert "suggested_response_fr" not in json.dumps(brief.public_descriptor())


def test_a_zero_cost_offer_list_needs_no_model_or_image_call(
    db_session, learner, monkeypatch
) -> None:
    """The end-to-end café path the integration owner drives must not call a provider."""

    def explode(*args, **kwargs):  # pragma: no cover - the point is that it never runs
        raise AssertionError("list_available_scenarios must not call a model")

    monkeypatch.setattr(journey_content, "_generate_variation", explode, raising=False)
    briefs = journey_content.list_available_scenarios(
        db_session, user=learner, input_mode=InputMode.TEXT
    )
    assert {str(b.scenario_key) for b in briefs} == {str(k) for k in CapabilityKey}


def test_wp05_classifies_the_frozen_fixture_evidence_the_same_way() -> None:
    """WP-03/WP-05/WP-00 must agree on what counts as independent production."""

    from app.services.journey_learning import classify_evidence

    unassisted = _fixture("unassisted_success")
    assert unassisted["assistance_level"] == "none"
    assert str(
        classify_evidence(
            opportunity="open_production", is_correct=True, assistance=AssistanceLevel.NONE
        )
    ) == "produced_independent"

    supported = _fixture("wrong_then_supported")
    assert supported["assistance_level"] != "none"
    assert str(
        classify_evidence(
            opportunity="open_production", is_correct=True, assistance=AssistanceLevel.HINT
        )
    ) == "produced_supported"

    # A choice can never reach independence, whatever the assistance level.
    for level in (AssistanceLevel.NONE, AssistanceLevel.HINT):
        assert str(
            classify_evidence(opportunity="choice", is_correct=True, assistance=level)
        ) == "recognized"


def test_wp05_help_reveal_downgrades_the_frozen_help_fixture() -> None:
    """The help fixture reveals a suggested response; that can never be independent."""

    from app.services.journey_learning import classify_evidence

    helped = _fixture("help_revealed")
    assert helped["assistance_level"] == "suggested_response"
    assert str(
        classify_evidence(
            opportunity="open_production",
            is_correct=True,
            assistance=AssistanceLevel.SUGGESTED_RESPONSE,
        )
    ) == "produced_supported"


# ---------------------------------------------------------------------------
# WP-03 -> WP-05 -> WP-04 chain, driven through the real modules.
# ---------------------------------------------------------------------------

PROMPT_LEAK_MARKERS = (
    "accepted_answers", "correct_option_id", "correct_tile_order", "solution_fr",
    "rubric_native", "allowed_outcomes", "required_intents", "optional_intents",
    "suggested_response_fr", "target_answer",
)


def _plan_for(db, user, scenario_key, input_mode=InputMode.TEXT):
    from app.services.journey_learning import select_learning_candidates
    from app.services.journey_planner import plan_journey

    brief = _brief(db, user, scenario_key)
    candidates = select_learning_candidates(db, user=user, scenario=brief, limit=3)
    return brief, candidates, plan_journey(
        scenario=brief, candidates=candidates, input_mode=input_mode
    )


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_the_real_chain_produces_a_valid_bounded_plan(db_session, learner, scenario_key):
    """WP-03's brief + WP-05's candidates + WP-04's planner must satisfy the envelope."""

    _, _, plan = _plan_for(db_session, learner, scenario_key)
    plan.validate()  # raises on any CONTRACTS §3/§9 violation

    kinds = [step.kind for step in plan.steps]
    assert kinds[0] == "scene" and kinds[-1] == "resolution"
    assert kinds.count("respond") == 1
    assert kinds.count("recall") <= MAX_RECALL_STEPS
    mandatory = sum(s.estimated_seconds for s in plan.steps if not s.optional)
    assert mandatory <= 300, f"{scenario_key}: {mandatory}s"


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_no_planned_public_prompt_leaks_the_answer_key(db_session, learner, scenario_key):
    _, _, plan = _plan_for(db_session, learner, scenario_key)
    for step in plan.steps:
        serialized = json.dumps(step.public_prompt, ensure_ascii=False, default=str)
        for marker in PROMPT_LEAK_MARKERS:
            assert marker not in serialized, f"{scenario_key} step {step.ordinal} leaks {marker}"
        if step.kind == "recall":
            for option in step.public_prompt["options"]:
                assert set(option) == {"id", "text_fr"}


def test_voice_is_offered_only_when_the_journey_asked_for_it(db_session, learner):
    """The ratified `input_mode` parameter must actually reach the public prompt."""

    _, _, text_plan = _plan_for(db_session, learner, CapabilityKey.ORDER_AT_CAFE,
                                input_mode=InputMode.TEXT)
    _, _, voice_plan = _plan_for(db_session, learner, CapabilityKey.ORDER_AT_CAFE,
                                 input_mode=InputMode.VOICE)
    text_respond = next(s for s in text_plan.steps if s.kind == "respond")
    voice_respond = next(s for s in voice_plan.steps if s.kind == "respond")
    assert text_respond.public_prompt["input_modes"] == ["text"]
    assert "voice" in voice_respond.public_prompt["input_modes"]
    assert "text" in voice_respond.public_prompt["input_modes"], "text is always available"


def test_an_empty_queue_still_reaches_a_real_ending(db_session, learner):
    """A brand-new learner has nothing due; the day must still end honestly."""

    from app.services.journey_learning import select_learning_candidates

    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert select_learning_candidates(db_session, user=learner, scenario=brief, limit=3) == []

    _, _, plan = _plan_for(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    plan.validate()
    assert [s.kind for s in plan.steps] == ["scene", "respond", "resolution"]
    assert plan.selected_target_ids == [], "nothing may be claimed as due"


def test_a_large_due_queue_does_not_become_a_large_obligation(db_session, learner):
    """A hundred overdue words must not turn the five-minute day into a worksheet."""

    from app.services.journey_contracts import LearningCandidate, TargetKind, TargetRef
    from app.services.journey_planner import plan_journey

    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    candidates = [
        LearningCandidate(
            target=TargetRef(kind=TargetKind.VOCABULARY, id=f"v{i}",
                             label_fr=f"mot{i}", label_native=f"word {i}"),
            priority_score=90 - i * 0.1, due_since_days=30 - i % 7,
            estimated_seconds=8, is_new=False,
        )
        for i in range(100)
    ]
    before = [(c.target.id, c.due_since_days, c.priority_score) for c in candidates]

    plan = plan_journey(scenario=brief, candidates=candidates)
    plan.validate()

    assert len([s for s in plan.steps if s.kind == "recall"]) <= MAX_RECALL_STEPS
    assert len(plan.selected_target_ids) <= 3
    assert len(plan.omitted_candidate_ids) >= 97
    # The planner is pure: it cannot have marked anything reviewed.
    assert [(c.target.id, c.due_since_days, c.priority_score) for c in candidates] == before


def test_repeating_the_same_inputs_produces_an_identical_plan(db_session, learner):
    """A refresh must not re-randomize the day."""

    _, _, first = _plan_for(db_session, learner, CapabilityKey.ARRANGE_MEETING)
    _, _, second = _plan_for(db_session, learner, CapabilityKey.ARRANGE_MEETING)
    assert [(s.ordinal, s.kind, s.estimated_seconds, s.public_prompt) for s in first.steps] == \
           [(s.ordinal, s.kind, s.estimated_seconds, s.public_prompt) for s in second.steps]
    assert first.selected_target_ids == second.selected_target_ids


# ---------------------------------------------------------------------------
# WP-06: a consequence must be one the scenario declared, never model-invented.
# ---------------------------------------------------------------------------

def _respond_task(db, user, scenario_key):
    return _brief(db, user, scenario_key).response_task


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_a_consequence_is_always_one_the_scenario_declared(db_session, learner, scenario_key):
    """A model may propose an outcome; it may never invent one."""

    from app.services.journey_conversation import coerce_outcome_key, default_outcome_key

    brief = _brief(db_session, learner, scenario_key)
    task = brief.response_task

    for invented in ("romy_buys_you_a_car", "", "DROP TABLE users", "served_at_counter_x"):
        coerced = coerce_outcome_key(invented, task=task, scenario_key=scenario_key)
        assert coerced in task.allowed_outcomes, (
            f"{scenario_key}: {invented!r} escaped into the outcome schema as {coerced!r}"
        )

    for declared in task.allowed_outcomes:
        assert coerce_outcome_key(declared, task=task, scenario_key=scenario_key) == declared

    assert default_outcome_key(task, scenario_key) in task.allowed_outcomes


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_every_declared_outcome_has_an_ending_the_learner_can_be_shown(
    db_session, learner, scenario_key
):
    from app.services.journey_conversation import resolution_line, resolution_summary

    brief = _brief(db_session, learner, scenario_key)
    for outcome in brief.response_task.allowed_outcomes:
        assert resolution_line(brief, outcome), f"{scenario_key}/{outcome} has no French line"
        assert resolution_summary(brief, outcome), f"{scenario_key}/{outcome} has no summary"


def test_the_neutral_default_never_claims_an_agreement_that_did_not_happen(
    db_session, learner
):
    """The bug I ruled on: a learner who settled nothing must not see a Saturday plan."""

    from app.services.journey_conversation import default_outcome_key

    brief = _brief(db_session, learner, CapabilityKey.ARRANGE_MEETING)
    fallback = default_outcome_key(brief.response_task, CapabilityKey.ARRANGE_MEETING)
    assert fallback == "meeting_postponed", (
        "the no-consequence fallback must be the neutral outcome, not an agreed meeting"
    )


def test_a_repair_turn_exists_beyond_the_two_normal_turns(db_session, learner):
    """CONTRACTS §3: at most two learner turns PLUS one optional repair."""

    from app.services.journey_conversation import normal_turns, turn_budget

    task = _respond_task(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    assert normal_turns(task) <= MAX_RESPOND_TURNS
    if task.repair_allowed:
        assert turn_budget(task) == normal_turns(task) + 1


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
def test_every_scenario_can_end_without_claiming_the_learner_succeeded(
    db_session, learner, scenario_key
):
    """A learner who never gets the task done must have an honest ending available.

    Found on 2026-09-05 driving the live API: `order_at_cafe` declared only
    `served_at_counter | served_at_terrace | takeaway` — all successes — so a learner
    who answered "euh je sais pas" three times was still shown Margaux serving them
    "what you asked for". Every family now needs at least one non-success outcome,
    and the no-consequence fallback must be one of them.
    """

    from app.services.journey_conversation import NEUTRAL_OUTCOMES, default_outcome_key

    brief = _brief(db_session, learner, scenario_key)
    task = brief.response_task

    honest = [key for key in task.allowed_outcomes if key in NEUTRAL_OUTCOMES]
    assert honest, (
        f"{scenario_key} has no outcome that admits the learner did not succeed: "
        f"{task.allowed_outcomes}"
    )

    fallback = default_outcome_key(task, scenario_key)
    assert fallback in NEUTRAL_OUTCOMES, (
        f"{scenario_key} falls back to {fallback!r}, which claims a success the learner "
        "may not have earned"
    )
    # The honest ending still has to be renderable, not a bare key.
    from app.services.journey_conversation import resolution_line, resolution_summary

    assert resolution_line(brief, fallback)
    assert resolution_summary(brief, fallback)


# ---------------------------------------------------------------------------
# WP-11: telemetry may never carry learner content.
# ---------------------------------------------------------------------------

def test_no_learner_content_can_reach_the_event_ledger(db_session, learner):
    """CONTRACTS §11.3: never copy raw utterances, audio, email or free text.

    Written as a hostile call rather than a happy-path one: a producer that
    forwards its whole context by mistake must still store nothing personal.
    """

    import json
    from uuid import uuid4

    from app.services import journey_events

    journey_id = uuid4()
    utterance = "Je voudrais un café en terrasse, s'il vous plaît."
    event = journey_events.record_journey_event(
        db_session,
        event_name="journey_step_completed",
        user_id=learner.id,
        source_key=f"journey:{journey_id}:journey_step_completed",
        metadata={
            "journey_id": str(journey_id),
            "step_kind": "respond",
            "learner_text": utterance,
            "answer": utterance,
            "transcript": utterance,
            "corrected_text": utterance,
            "email": learner.email,
            "full_name": "A Real Person",
            "audio_url": "https://cdn.example/audio/abc.m4a",
            "note": "free personal text",
        },
    )
    db_session.flush()
    assert event is not None

    blob = json.dumps(event.payload, ensure_ascii=False)
    for secret in (utterance, learner.email, "A Real Person",
                   "cdn.example/audio", "free personal text"):
        assert secret not in blob, f"telemetry leaked {secret!r}"

    # The key NAMES may be recorded so a producer bug is diagnosable.
    dropped = set(event.payload.get("dropped_metadata_keys") or [])
    assert {"learner_text", "answer", "transcript", "email", "audio_url"} <= dropped


def test_an_unfrozen_event_name_is_refused(db_session, learner):
    """The ten names in JourneyEventName are the contract; nothing invents another."""

    from uuid import uuid4

    from app.services import journey_events

    journey_id = uuid4()
    refused = journey_events.record_journey_event(
        db_session,
        event_name="journey_learner_seemed_confused",
        user_id=learner.id,
        source_key=f"journey:{journey_id}:invented",
        metadata={"journey_id": str(journey_id)},
    )
    assert refused is None
