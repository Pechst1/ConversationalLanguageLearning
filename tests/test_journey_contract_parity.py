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

#: The scenario families the catalogue actually publishes. WP-37 put
#: `CapabilityKey.REGISTER` on the enum — a *dimension* of a respond turn, with
#: no scenario, no brief and no plan of its own — so the enum is no longer the
#: family list, and this file parametrizes over the production tuple instead.
SCENARIO_FAMILIES = journey_content.SCENARIO_PRIORITY

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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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
    assert {str(b.scenario_key) for b in briefs} == {str(k) for k in SCENARIO_FAMILIES}


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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


@pytest.mark.parametrize("scenario_key", list(SCENARIO_FAMILIES))
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


# ---------------------------------------------------------------------------
# WP-66: day shapes and the three Séance formats, across the seam.
#
# The failure a per-package suite cannot catch here is a planner that produces
# a step the wire schema refuses — or a wire schema that has quietly stopped
# accepting a payload already sitting in somebody's database.
# ---------------------------------------------------------------------------

def test_every_recall_format_the_planner_can_pose_validates_on_the_wire(
    db_session, learner
):
    """Six formats in the planner must be six formats in `RecallPrompt`."""

    from app.schemas.daily_journey import RecallPrompt
    from app.services.journey_contracts import RECALL_FORMATS, TargetKind, TargetRef
    from app.services.journey_planner import (
        build_recall_task_in_format,
        public_recall_target,
    )

    brief = _brief(db_session, learner, CapabilityKey.ORDER_AT_CAFE)
    scene = ["un café", "en terrasse", "s'il vous plaît", "au comptoir"]
    # One target per format, each paired with the scene vocabulary that makes
    # *that* format the honest way to pose it: a word the scene can distract
    # (choice), the same word in a scene that affords nothing (short answer), a
    # phrase with no gloss to choose between (tiles), a phrase the scene can
    # add spare chips to (word bank), a noun with its article (gender
    # classify), and a phrase that tutoies (transform).
    targets = {
        "choice": (
            TargetRef(
                kind=TargetKind.VOCABULARY, id="p1", label_fr="café",
                label_native="coffee",
            ),
            scene,
        ),
        "short_answer": (
            TargetRef(
                kind=TargetKind.VOCABULARY, id="p3", label_fr="brouillard",
                label_native="fog",
            ),
            [],
        ),
        "tiles": (
            TargetRef(
                kind=TargetKind.VOCABULARY, id="p2", label_fr="un grand café",
                label_native=None,
            ),
            scene,
        ),
        "word_bank": (
            TargetRef(
                kind=TargetKind.VOCABULARY, id="p4", label_fr="l'addition maintenant",
                label_native="the bill now",
            ),
            scene,
        ),
        "classify": (
            TargetRef(
                kind=TargetKind.VOCABULARY, id="p5", label_fr="une terrasse",
                label_native="a terrace",
            ),
            scene,
        ),
        "transform": (
            TargetRef(
                kind=TargetKind.GRAMMAR, id="p6", label_fr="tu prends un café",
                label_native="you are having a coffee",
            ),
            scene,
        ),
    }
    # WP-78: the three quick formats are posed from today's other glossed words
    # (matching, listen-and-tap) and from the scene's sentences (unscramble).
    pool = [
        TargetRef(kind=TargetKind.VOCABULARY, id=f"q{index}", label_fr=fr, label_native=native)
        for index, (fr, native) in enumerate(
            [("la clé", "the key"), ("le volet", "the shutter"), ("brouillard", "fog")]
        )
    ]
    quick = TargetRef(
        kind=TargetKind.VOCABULARY, id="p7", label_fr="un café", label_native="a coffee"
    )
    targets.update(
        {
            "match_pairs": (quick, scene),
            "listen_tap": (quick, scene),
            "unscramble": (quick, scene),
        }
    )
    sentences = ["Je voudrais un café au comptoir."]
    assert set(targets) == set(RECALL_FORMATS), "a format with no parity coverage"

    posed = 0
    for task_type, (target, affordances) in targets.items():
        task = build_recall_task_in_format(
            task_type,
            target=target,
            scenario=brief,
            affordances=affordances,
            optional=False,
            pool=pool,
            sentences=sentences,
        )
        assert task is not None, f"{task_type} could not be posed at all"
        assert task.task_type == task_type
        prompt = RecallPrompt.model_validate(
            {
                "task_type": task.task_type,
                "instruction_native": task.instruction_native,
                "prompt_fr": task.prompt_fr,
                "options": [dict(option) for option in task.options],
                "target": public_recall_target(task.target),
                "optional": task.optional,
                "help_available": [],
            }
        )
        serialized = json.dumps(prompt.model_dump(mode="json"), ensure_ascii=False)
        for marker in PROMPT_LEAK_MARKERS:
            assert marker not in serialized, f"{task_type} leaks {marker}"
        posed += 1
    assert posed == len(RECALL_FORMATS)


def test_a_v1_payload_still_validates_after_the_wp66_additions(db_session, learner):
    """Additive means additive: the frozen fixtures must not need editing."""

    from app.schemas.daily_journey import JourneySnapshot, ResolutionPrompt

    snapshot = _fixture("cafe_journey_created")
    assert "day_shape" not in snapshot, "the frozen fixture predates WP-66"
    parsed = JourneySnapshot.model_validate(snapshot)
    assert parsed.day_shape == "standard", "an old plan is the standard day it was"
    for step in parsed.steps:
        if step.kind == "scene":
            assert step.prompt.listen_first is False
        if step.kind == "resolution":
            assert step.prompt.chapter_recap_fr is None
            assert step.prompt.register_note_fr is None

    # And the new fields are genuinely optional, not merely defaulted somewhere.
    bare = ResolutionPrompt.model_validate(
        {
            "outcome_key": "served_at_counter",
            "character_line_fr": "Un café pour vous.",
            "summary_native": "Margaux served your coffee.",
        }
    )
    assert (bare.chapter_recap_fr, bare.register_note_fr, bare.register_reason_native) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "shape", ["standard", "letter", "listening", "reprise", "short"]
)
def test_every_day_shape_the_planner_deals_is_a_shape_the_wire_can_carry(shape):
    from app.schemas.daily_journey import JourneySnapshot
    from app.services.journey_contracts import DayShape

    assert shape in {str(value) for value in DayShape}
    snapshot = _fixture("cafe_journey_created")
    parsed = JourneySnapshot.model_validate({**snapshot, "day_shape": shape})
    assert parsed.day_shape == shape


def test_a_shape_this_build_has_never_heard_of_does_not_break_the_day():
    """A client (or an older server) meeting a newer deployment's shape."""

    from app.schemas.daily_journey import JourneySnapshot

    snapshot = _fixture("cafe_journey_created")
    parsed = JourneySnapshot.model_validate({**snapshot, "day_shape": "jour_de_marche"})
    assert parsed.day_shape == "jour_de_marche"
    assert parsed.steps, "the steps are still there to render"


# ---------------------------------------------------------------------------
# WP-75 — the first day's cast introduction, additive on the wire
#
# The first-day payload lives beside the frozen bundle, not in it: the v1 bundle
# is frozen (and the web renderer counts its files), and WP-75 changed no
# existing shape — it added one optional field.
# ---------------------------------------------------------------------------

WP75_FIXTURE = FIXTURES.parent.parent / "wp75" / "first_journey_created.json"


def _wp75_fixture() -> dict:
    return json.loads(WP75_FIXTURE.read_text(encoding="utf-8"))["response"]


def test_cast_intro_is_optional_and_absent_on_every_older_payload():
    """A pre-WP-75 payload validates unchanged and reads ``cast_intro=None``."""

    from app.schemas.daily_journey import JourneySnapshot

    snapshot = _fixture("cafe_journey_created")
    assert "cast_intro" not in snapshot, "the frozen fixture predates WP-75"
    assert JourneySnapshot.model_validate(snapshot).cast_intro is None
    assert JourneySnapshot.model_validate({**snapshot, "cast_intro": None}).cast_intro is None


def test_cast_intro_entries_refuse_extra_keys():
    from pydantic import ValidationError

    from app.schemas.daily_journey import JourneySnapshot

    entry = _wp75_fixture()["cast_intro"][0]
    snapshot = _fixture("cafe_journey_created")
    with pytest.raises(ValidationError):
        JourneySnapshot.model_validate(
            {**snapshot, "cast_intro": [{**entry, "portrait_prompt": "x"}]}
        )


def test_the_first_journey_fixture_validates_against_the_real_schema():
    from app.schemas.daily_journey import JourneySnapshot

    frozen = _wp75_fixture()
    parsed = JourneySnapshot.model_validate(frozen)
    assert parsed.cast_intro is not None and len(parsed.cast_intro) == 3
    assert not set(PRIVATE_MARKERS) & set(json.dumps(frozen).split('"'))


def test_the_real_first_day_matches_the_frozen_first_journey_fixture(db_session, learner):
    """WP-03 + WP-04's real first day is the payload the frontend codes against."""

    from app.services import journey_planner

    frozen = _wp75_fixture()
    brief = journey_content.first_day_brief(db_session, user=learner)
    assert brief.public_descriptor() == frozen["scenario"]
    candidates = journey_content.first_day_candidates(db_session, user=learner, brief=brief)
    plan = journey_planner.plan_journey(scenario=brief, candidates=candidates, first_day=True)
    assert [str(step.kind) for step in plan.steps] == [step["kind"] for step in frozen["steps"]]
    for step, fixture_step in zip(plan.steps, frozen["steps"], strict=True):
        prompt = dict(step.public_prompt)
        fixture_prompt = fixture_step["prompt"]
        if str(step.kind) == "recall":
            assert prompt["task_type"] == fixture_prompt["task_type"]
            # Which of the two first-day words is posed as the choice follows the
            # catalogue rows' ids, which a shared test database assigns in run
            # order: the sentence frame is the contract, the word is either one.
            frame = fixture_prompt["instruction_native"].split('"')[0]
            assert prompt["instruction_native"].split('"')[0] == frame
            # Choice distractors are seeded by the catalogue row's id, which a
            # fresh database assigns differently: the count is the contract.
            if prompt["task_type"] == "tiles":
                # Either first-day phrase, split into its own words.
                phrases = {"un café", "s'il vous plaît"}
                tiles = sorted(o["text_fr"] for o in prompt["options"])
                assert tiles in [sorted(p.split()) for p in phrases]
            else:
                assert len(prompt["options"]) == len(fixture_prompt["options"])
            assert prompt["optional"] is False
        if str(step.kind) == "respond":
            assert prompt["character_line_fr"] == fixture_prompt["character_line_fr"]
            assert prompt["max_turns"] == fixture_prompt["max_turns"]
    assert (
        journey_content.first_day_cast_intro(learner.native_language) == frozen["cast_intro"]
    )
    assert len(frozen["cast_intro"]) == journey_content.CAST_INTRO_SIZE
