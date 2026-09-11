"""WP-33 — register and pragmatics as a graded dimension.

Four claims, and one prohibition:

1. the detectors are deterministic and say "non évalué" when they saw nothing;
2. the `register` dimension is scored by the *same* rubric as the three
   practical capabilities — no second ladder, no second set of thresholds;
3. the meta-pragmatic line is explicit, in the learner's own language, and goes
   through the one-correction policy instead of around it;
4. every authored scenario declares the register its counterpart uses.

The prohibition is the owner's standing WON'T-DO: **no pronunciation or accent
judgement anywhere**. A source scan at the bottom of this file fails if the
register surfaces ever start scoring how something sounded.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import journey_capabilities, pragmatics
from app.services.journey_capabilities import (
    build_capability_summary,
    build_register_summary,
)
from app.services.journey_contracts import (
    JOURNEY_CONTENT_VERSION,
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    CapabilityState,
    Correction,
    EvidenceKind,
    InputMode,
    ResponseEvaluation,
    ResponseTask,
    ScenarioBrief,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_conversation import evaluate_response, register_corrections
from app.services.journey_learning import (
    apply_learning_evidence,
    ensure_journey_learning_session,
)
from app.services.learner_copy import LEARNER_COPY, SUPPORTED_COPY_LANGUAGES

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "app" / "data" / "journey_scenarios"


# ==========================================================================
# 1. Deterministic detectors
# ==========================================================================

@pytest.mark.parametrize(
    ("text", "expected", "span", "replacement"),
    [
        # The pronoun is never swapped without its verb: « vous peux » would be
        # a worse sentence than the one the learner wrote.
        ("Tu peux me servir un café ?", "vous", "Tu peux", "vous pouvez"),
        ("Tu travailles demain ?", "vous", "Tu travailles", "vous travaillez"),
        # A stem-changing -er verb is in the table, so no « vous appellez ».
        ("Tu appelles Margaux ?", "vous", "Tu appelles", "vous appelez"),
        # Safe word-for-word swaps are preferred over the pronoun+verb one.
        ("Je te remercie beaucoup", "vous", "te", "vous"),
        ("C'est ton café", "vous", "ton", "votre"),
        # The other direction, including the object pronoun.
        ("Vous pouvez venir samedi ?", "tu", "Vous pouvez", "tu peux"),
        ("Je vous remercie", "tu", "vous", "te"),
    ],
)
def test_a_register_slip_is_named_with_a_repair_that_is_actually_french(
    text, expected, span, replacement
):
    assessment = pragmatics.assess_register(text, expected_register=expected, level_band="A1")
    assert assessment.verdict is pragmatics.RegisterVerdict.SLIPPED
    finding = assessment.slip
    assert finding is not None
    assert (finding.span, finding.replacement) == (span, replacement)
    # The span must survive verbatim in what the learner typed, or WP-05 drops it.
    assert finding.span in text


def test_a_slip_with_no_honest_one_word_repair_still_counts_as_a_slip():
    """« votre » becomes *ton* or *ta* depending on a noun nobody analysed."""

    assessment = pragmatics.assess_register(
        "Votre chat est mignon", expected_register="tu", level_band="A1"
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.SLIPPED
    assert assessment.slip is not None
    assert assessment.slip.replacement is None


def test_one_turn_carrying_both_registers_is_a_slip_of_its_own():
    assessment = pragmatics.assess_register(
        "Bonjour, tu vas bien ? Je voudrais vous demander quelque chose.",
        expected_register="vous",
        level_band="A2",
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.SLIPPED
    assert assessment.slip is not None
    assert assessment.slip.code == pragmatics.MIXED_REGISTER


def test_the_counterparts_own_register_is_respected_and_says_so():
    assessment = pragmatics.assess_register(
        "Bonjour, je voudrais un café, s'il vous plaît.",
        expected_register="vous",
        level_band="A1",
        is_opening_turn=True,
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.RESPECTED
    assert assessment.slip is None
    assert pragmatics.GREETING in pragmatics.politeness_markers(
        "Bonjour, je voudrais un café, s'il vous plaît."
    )


def test_a_missing_greeting_is_reported_on_the_opening_turn_and_is_not_a_slip():
    """A mid-scene turn without « bonjour » is normal French, not a mistake."""

    opening = pragmatics.assess_register(
        "Un café, s'il vous plaît.",
        expected_register="vous",
        level_band="A1",
        is_opening_turn=True,
    )
    codes = {finding.code for finding in opening.findings}
    assert pragmatics.MISSING_GREETING in codes
    assert opening.slip is None

    later = pragmatics.assess_register(
        "Un café, s'il vous plaît.", expected_register="vous", level_band="A1"
    )
    assert pragmatics.MISSING_GREETING not in {finding.code for finding in later.findings}


def test_an_imperative_to_a_stranger_is_a_slip_at_a1_and_a_choice_above_it():
    at_a1 = pragmatics.assess_register(
        "Donnez-moi un café", expected_register="vous", level_band="A1"
    )
    assert at_a1.verdict is pragmatics.RegisterVerdict.SLIPPED
    assert at_a1.slip is not None
    assert at_a1.slip.code == pragmatics.BARE_IMPERATIVE
    # « Donnez-moi un café » → « Je voudrais un café » is a real sentence.
    assert at_a1.slip.replacement == "je voudrais"

    # Above the band the same sentence is a choice, not a mistake — and since
    # it addresses nobody by name either, the honest answer is "non évalué",
    # never a quiet pass.
    at_b1 = pragmatics.assess_register(
        "Donnez-moi un café", expected_register="vous", level_band="B1"
    )
    assert at_b1.verdict is pragmatics.RegisterVerdict.NOT_EVALUATED
    assert at_b1.slip is None


def test_a_softened_imperative_is_not_a_command():
    assessment = pragmatics.assess_register(
        "Donnez-moi un café, s'il vous plaît", expected_register="vous", level_band="A1"
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.RESPECTED


def test_je_veux_is_blunt_at_a1_but_je_veux_bien_is_an_acceptance():
    blunt = pragmatics.bare_request_finding("Je veux un café", level_band="A1")
    assert blunt is not None
    assert (blunt.code, blunt.replacement) == (pragmatics.BLUNT_WANT, "je voudrais")
    assert pragmatics.bare_request_finding("Oui, je veux bien", level_band="A1") is None


# --- the honest "non évalué" fallback --------------------------------------

def test_a_turn_that_addresses_nobody_is_not_evaluated_rather_than_passed():
    assessment = pragmatics.assess_register(
        "Un café", expected_register="vous", level_band="A1"
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.NOT_EVALUATED
    assert assessment.evaluated is False
    assert assessment.respected is False


def test_an_unknown_counterpart_register_is_not_evaluated_rather_than_guessed():
    assessment = pragmatics.assess_register(
        "Tu peux venir ?", expected_register=None, level_band="A1"
    )
    assert assessment.verdict is pragmatics.RegisterVerdict.NOT_EVALUATED
    assert assessment.observed == "tu"
    assert assessment.expected is None


def test_the_counterparts_register_comes_from_their_own_lines_and_never_from_a_vote():
    assert pragmatics.counterpart_register(
        ["Bonjour ! Vous prenez quoi ?", "Je vous l'apporte."]
    ) == "vous"
    assert pragmatics.counterpart_register(["Salut, tu viens ?", "Je t'attends."]) == "tu"
    # Lines that disagree settle nothing; the guard that stops a scene mixing
    # them lives in living_story, and this is what happens if one ever slips.
    assert pragmatics.counterpart_register(["Vous prenez quoi ?", "Tu viens ?"]) is None
    assert pragmatics.counterpart_register(["Il pleut."]) is None
    assert pragmatics.counterpart_register([]) is None


# ==========================================================================
# 2. Every authored scenario declares its counterpart's register
# ==========================================================================

def _scenario_files() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("*/*.json"))


def test_there_is_at_least_one_authored_scenario_to_check():
    assert _scenario_files()


@pytest.mark.parametrize("path", _scenario_files(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_authored_scenario_declares_the_counterparts_expected_register(path: Path):
    spec = json.loads(path.read_text(encoding="utf-8"))
    block = spec.get("counterpart_register")
    assert isinstance(block, dict), f"{path} declares no counterpart_register"
    assert block.get("expected") in {"tu", "vous"}
    assert str(block.get("counterpart") or "").strip()
    # The scene-wide register and the counterpart's register are different
    # claims; today they agree, and this fails loudly the day they stop.
    assert block["expected"] == spec.get("register"), (
        f"{path}: the scene runs on {spec.get('register')!r} but its counterpart "
        f"is declared as {block['expected']!r}"
    )
    reason = block.get("reason_native") or {}
    for language in SUPPORTED_COPY_LANGUAGES:
        assert str(reason.get(language) or "").strip(), f"{path}: no {language} reason"
    assert str(block.get("reason_fr") or "").strip()


@pytest.mark.parametrize("path", _scenario_files(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_the_declaration_is_readable_through_the_public_loader(path: Path):
    declared = pragmatics.declared_counterpart_register(
        path.stem, content_version=path.parent.name
    )
    assert declared is not None
    assert declared.expected in {"tu", "vous"}
    for language in SUPPORTED_COPY_LANGUAGES:
        assert declared.reason(language)
    # An unknown language falls back to English rather than to an empty line.
    assert declared.reason("pt") == declared.reason("en")


def test_a_generated_scene_has_no_declaration_and_says_so():
    assert pragmatics.declared_counterpart_register("no_such_scenario") is None
    assert pragmatics.declared_counterpart_register(None) is None


# ==========================================================================
# 3. The meta-pragmatic line, in three languages, through the one-correction
#    policy
# ==========================================================================

def _user(db_session: Session, **kwargs) -> User:
    fields = {"native_language": "en", "target_language": "fr", "proficiency_level": "A1"}
    fields.update(kwargs)
    user = User(
        id=uuid4(),
        email=f"register-{uuid4().hex}@example.com",
        hashed_password="test",
        **fields,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _brief(**kwargs) -> ScenarioBrief:
    fields: dict = {
        "scenario_key": CapabilityKey.ORDER_AT_CAFE,
        "content_version": JOURNEY_CONTENT_VERSION,
        "title_fr": "Un café au Mistral",
        "objective_key": "order_at_cafe.counter_drink",
        "objective_native": "Order a hot drink.",
        "level_band": "A1",
        "character_id": "margaux_barman",
        "character_name": "Margaux",
        "location_id": "le_mistral",
        "location_name": "Le Mistral",
        "image_url": None,
        "setup_fr": "Il pleut sur le canal.",
        "setup_native": "It is raining.",
        "opening_line_fr": "Tiens, bonjour ! Vous vous installez ?",
        "response_task": _task(),
    }
    fields.update(kwargs)
    return ScenarioBrief(**fields)


def _task(**kwargs) -> ResponseTask:
    fields: dict = {
        "objective_native": "Say what you would like to drink.",
        "character_id": "margaux_barman",
        "character_name": "Margaux",
        "opening_line_fr": "Alors, qu'est-ce que je vous sers ?",
        "required_intents": ["name_a_hot_drink"],
        "allowed_outcomes": [
            "served_at_counter",
            "served_at_terrace",
            "takeaway",
            "not_ordered",
        ],
    }
    fields.update(kwargs)
    return ResponseTask(**fields)


@pytest.mark.parametrize(
    ("language", "fragment"),
    [("en", "vous"), ("de", "siezt"), ("fr", "vouvoie")],
)
def test_the_register_line_explains_itself_in_the_learners_own_language(
    db_session: Session, language, fragment
):
    user = _user(db_session, native_language=language)
    scenario = _brief()
    _assessment, candidates = register_corrections(
        user=user,
        text="Tu peux me servir un café ?",
        scenario=scenario,
        task=scenario.response_task,
    )
    assert len(candidates) == 1
    note = candidates[0].note_native
    assert fragment in note
    assert "Margaux" in note
    # Explicit meta-pragmatics: the rule *and* the reason, which is the whole
    # finding of Taguchi 2015 that this package is built on.
    assert "Mistral" in note


def test_the_register_correction_is_shown_in_the_evaluation(db_session: Session):
    user = _user(db_session)
    scenario = _brief()
    result = evaluate_response(
        db_session,
        user=user,
        scenario=scenario,
        task=scenario.response_task,
        answer=AttemptAnswer(text="Tu peux me servir un café ?", mode=InputMode.TEXT),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    assert result.correction is not None
    assert result.correction.span_fr == "Tu peux"
    assert result.correction.corrected_fr == "Vous pouvez"


def test_a_correction_on_the_days_own_target_still_outranks_the_register_line(
    db_session: Session,
):
    """WP-33 §3: foregrounded *only* when it is the one relevant correction."""

    user = _user(db_session)
    target = TargetRef(
        kind=TargetKind.VOCABULARY,
        id=str(uuid4()),
        label_fr="je prends",
        label_native="I'll have",
    )
    scenario = _brief(response_task=_task(targets=[target]))
    result = evaluate_response(
        db_session,
        user=user,
        scenario=scenario,
        task=scenario.response_task,
        answer=AttemptAnswer(
            text="Tu peux me servir un café ? je prend un café", mode=InputMode.TEXT
        ),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    assert result.correction is not None
    assert result.correction.span_fr == "je prend"


def test_correct_register_produces_no_register_correction(db_session: Session):
    user = _user(db_session)
    scenario = _brief()
    _assessment, candidates = register_corrections(
        user=user,
        text="Bonjour, je voudrais un café, s'il vous plaît.",
        scenario=scenario,
        task=scenario.response_task,
    )
    assert candidates == []


def test_pragmatics_copy_is_complete_in_every_shipped_language():
    keys = [
        key
        for key in LEARNER_COPY
        if key.startswith("pragmatics.") or key.startswith("capability.register")
    ]
    assert keys, "WP-33 added no copy keys"
    for key in keys:
        for language in SUPPORTED_COPY_LANGUAGES:
            assert str(LEARNER_COPY[key].get(language) or "").strip(), f"{key}/{language}"


# ==========================================================================
# 4. The rubric — one ladder, four dimensions
# ==========================================================================

def _word(db_session: Session, user: User) -> VocabularyWord:
    """One due vocabulary word for this learner, so the turn has a real target."""

    suffix = uuid4().hex[:6]
    row = VocabularyWord(
        language="fr",
        word=f"café-{suffix}",
        normalized_word=f"cafe-{suffix}",
        english_translation="coffee",
        difficulty_level=1,
        frequency_rank=100,
    )
    db_session.add(row)
    db_session.flush()
    due = datetime.now(UTC) - timedelta(days=2)
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=row.id,
            state="review",
            stability=3.0,
            difficulty=5.0,
            reps=2,
            due_at=due,
            next_review_date=due,
            due_date=due.date(),
        )
    )
    db_session.flush()
    return row


def _respond_journey(
    db_session: Session,
    user: User,
    *,
    learner_lines: list[str],
    character_lines: list[str] | None = None,
    when: datetime,
    local_date: date,
    scenario_key: str = "order_at_cafe",
    assistance: AssistanceLevel = AssistanceLevel.NONE,
    outcome: TaskOutcome = TaskOutcome.MET,
) -> DailyJourney:
    """One completed respond step, persisted exactly the way WP-02 persists it."""

    journey = DailyJourney(
        user_id=user.id,
        local_date=local_date,
        timezone="UTC",
        content_version=JOURNEY_CONTENT_VERSION,
        level_band="A1",
        status="completed",
        scenario_snapshot={
            "scenario_key": scenario_key,
            "title_fr": "Un café au Mistral",
            "location_name": "Le Mistral",
            "character_name": "Margaux",
        },
    )
    db_session.add(journey)
    db_session.flush()
    lines = character_lines if character_lines is not None else ["Je vous sers quoi ?"]
    step = DailyJourneyStep(
        journey_id=journey.id,
        ordinal=0,
        kind="respond",
        status="completed",
        public_prompt={"character_line_fr": lines[0] if lines else ""},
        private_task={
            "turns": [
                {"learner": learner, "character": lines[index] if index < len(lines) else ""}
                for index, learner in enumerate(learner_lines)
            ]
        },
    )
    db_session.add(step)
    db_session.flush()

    word = _word(db_session, user)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey.id, scenario_key=scenario_key
    )
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey.id,
        step_id=step.id,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=outcome,
            assistance=assistance,
            observations=[
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.VOCABULARY,
                        id=str(word.id),
                        label_fr=word.word,
                        label_native=word.english_translation,
                    ),
                    evidence_kind=(
                        EvidenceKind.PRODUCED_INDEPENDENT
                        if assistance is AssistanceLevel.NONE
                        else EvidenceKind.PRODUCED_SUPPORTED
                    ),
                    assistance=assistance,
                    modality=InputMode.TEXT,
                    learner_text=learner_lines[0] if learner_lines else "",
                )
            ],
        ),
        modality=InputMode.TEXT,
        timezone="UTC",
        now=when,
    )
    return journey


def test_holding_the_register_twice_on_different_days_reaches_used_again_later(
    db_session: Session,
):
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, je voudrais un café, s'il vous plaît."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, vous avez un chocolat chaud ?"],
        when=datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 7),
        scenario_key="arrange_meeting",
        character_lines=["Bonjour, vous désirez ?"],
    )
    summary = build_register_summary(db_session, user=user)
    assert summary.state is CapabilityState.USED_AGAIN_LATER
    assert str(summary.capability_key) == "register"


def test_a_slip_keeps_the_dimension_below_independence(db_session: Session):
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Tu peux me servir un café ?"],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    summary = build_register_summary(db_session, user=user)
    assert summary.state is CapabilityState.WITH_SUPPORT
    assert summary.evidence
    assert summary.evidence[0].state is CapabilityState.WITH_SUPPORT


def test_one_slip_anywhere_in_the_exchange_costs_the_whole_turn(db_session: Session):
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, je voudrais un café s'il vous plaît.", "Et tu as du lait ?"],
        character_lines=["Je vous sers quoi ?", "Bien sûr."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    assert build_register_summary(db_session, user=user).state is CapabilityState.WITH_SUPPORT


def test_turns_that_addressed_nobody_report_unknown_not_a_pass(db_session: Session):
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Un café."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    summary = build_register_summary(db_session, user=user)
    assert summary.state is CapabilityState.UNKNOWN
    assert summary.evidence == []


def test_a_learner_with_no_journeys_has_not_tried_the_dimension(db_session: Session):
    user = _user(db_session)
    assert build_register_summary(db_session, user=user).state is CapabilityState.NOT_TRIED


def test_assistance_holds_the_register_dimension_at_with_support(db_session: Session):
    """The dimension inherits independence from the turn: one rubric, not two."""

    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, je voudrais un café, s'il vous plaît."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
        assistance=AssistanceLevel.SOLUTION,
    )
    assert build_register_summary(db_session, user=user).state is CapabilityState.WITH_SUPPORT


def test_the_register_dimension_is_read_from_the_scene_the_learner_actually_played(
    db_session: Session,
):
    """A generated scene may reuse an authored key and still tutoie the learner.

    The character's own lines win over the authored declaration, so a learner
    who correctly answers *tu* with *tu* is not marked down by a file.
    """

    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Salut ! Tu me sers un café ?"],
        character_lines=["Salut, tu prends quoi ?"],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    assert build_register_summary(db_session, user=user).state is CapabilityState.INDEPENDENT_ONCE


def test_the_dimension_is_the_same_rubric_and_not_a_second_one(db_session: Session):
    """`build_register_summary` must reuse the capability ladder verbatim."""

    source = (ROOT / "app" / "services" / "journey_capabilities.py").read_text(encoding="utf-8")
    # One place names a state, and both the scenario dimensions and the register
    # dimension go through it.
    assert source.count("CapabilityState.USED_AGAIN_LATER") == 2
    assert "_summarize(" in source
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, je voudrais un café, s'il vous plaît."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    view = build_capability_summary(db_session, user=user)
    register = build_register_summary(db_session, user=user)
    cafe = next(
        item for item in view.capabilities if item.capability_key is CapabilityKey.ORDER_AT_CAFE
    )
    assert cafe.state is CapabilityState.INDEPENDENT_ONCE
    assert register.state is CapabilityState.INDEPENDENT_ONCE


def test_the_wire_list_carries_register_now_that_the_enum_does(
    db_session: Session,
):
    """WP-37 landed the enum member, so the list is four keys and no more.

    The two failure modes this guards are the ones the hook could have caused:
    a key `CapabilityKey` has never heard of would 500 the finish recap, and a
    dimension summarised both by the scenario loop and by the register append
    would print `register` twice.
    """

    user = _user(db_session)
    keys = [
        str(item.capability_key)
        for item in build_capability_summary(db_session, user=user).capabilities
    ]
    assert keys == [str(key) for key in CapabilityKey]
    assert keys == ["order_at_cafe", "arrange_meeting", "explain_delay", "register"]
    assert len(keys) == len(set(keys))
    assert journey_capabilities._REGISTER_IS_CONTRACTED is True
    assert "REGISTER" in CapabilityKey.__members__
    # The dimension is not a scenario: nothing is grouped or read under it.
    assert CapabilityKey.REGISTER not in journey_capabilities._SCENARIO_KEYS


def test_the_dimension_is_in_the_summary_and_scored_by_the_one_rubric(
    db_session: Session,
):
    user = _user(db_session)
    _respond_journey(
        db_session,
        user,
        learner_lines=["Bonjour, je voudrais un café, s'il vous plaît."],
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    view = build_capability_summary(db_session, user=user)
    assert [str(item.capability_key) for item in view.capabilities][-1] == "register"
    assert view.capabilities[-1].state is CapabilityState.INDEPENDENT_ONCE
    assert view.capabilities[-1].title_native
    assert view.rubric_version  # still the one rubric version, not a second one
    # And it is the same verdict the standalone reader gives: one rubric.
    assert build_register_summary(db_session, user=user).state is view.capabilities[-1].state


# ==========================================================================
# 5. The model only speaks where the detectors cannot
# ==========================================================================

def test_the_model_is_never_asked_when_the_detector_already_decided(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    called: list[str] = []
    monkeypatch.setattr(
        pragmatics,
        "model_register_gap",
        lambda *args, **kwargs: called.append("asked"),
    )
    decided = pragmatics.assess_register(
        "Tu peux me servir un café ?", expected_register="vous", level_band="A1"
    )
    assert decided.evaluated
    assert called == []


def test_without_a_provider_the_model_gap_is_none_and_stays_non_evalue(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(pragmatics, "_pragmatics_llm", lambda: None)
    assert (
        pragmatics.model_register_gap(
            db_session,
            user_id=None,
            scenario_key="order_at_cafe",
            learner_text="Un café.",
            counterpart="Margaux",
            expected_register="vous",
        )
        is None
    )


def test_an_unparseable_model_answer_is_none_rather_than_a_verdict(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    class _Result:
        content = "sorry, I cannot"
        cost = 0.0

    class _LLM:
        def generate_chat_completion(self, *args, **kwargs):
            return _Result()

    monkeypatch.setattr(pragmatics, "_pragmatics_llm", lambda: _LLM())
    assert (
        pragmatics.model_register_gap(
            db_session,
            user_id=None,
            scenario_key="order_at_cafe",
            learner_text="Un café.",
            counterpart="Margaux",
            expected_register="vous",
        )
        is None
    )


def test_the_model_may_report_a_slip_it_alone_can_see(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    class _Result:
        content = '{"verdict": "too_blunt"}'
        cost = 0.0004

    class _LLM:
        def generate_chat_completion(self, *args, **kwargs):
            return _Result()

    monkeypatch.setattr(pragmatics, "_pragmatics_llm", lambda: _LLM())
    verdict = pragmatics.model_register_gap(
        db_session,
        user_id=None,
        scenario_key="order_at_cafe",
        learner_text="Café. Maintenant.",
        counterpart="Margaux",
        expected_register="vous",
    )
    assert verdict is not None
    assert verdict.verdict is pragmatics.RegisterVerdict.SLIPPED
    assert verdict.source == "model"


def test_an_unclear_model_answer_is_not_a_pass(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    class _Result:
        content = '{"verdict": "unclear"}'
        cost = 0.0

    class _LLM:
        def generate_chat_completion(self, *args, **kwargs):
            return _Result()

    monkeypatch.setattr(pragmatics, "_pragmatics_llm", lambda: _LLM())
    assert (
        pragmatics.model_register_gap(
            db_session,
            user_id=None,
            scenario_key="order_at_cafe",
            learner_text="…",
            counterpart="Margaux",
            expected_register="vous",
        )
        is None
    )


# ==========================================================================
# 6. The owner's WON'T-DO: no pronunciation or accent judgement, anywhere
# ==========================================================================

WP33_SOURCES = [
    ROOT / "app" / "services" / "pragmatics.py",
    ROOT / "app" / "services" / "journey_capabilities.py",
    ROOT / "app" / "services" / "journey_conversation.py",
]

#: Anything that would mean "we judged how it sounded".
PRONUNCIATION_TOKENS = (
    "pronunciation",
    "prononciation",
    "aussprache",
    "phoneme",
    "phonème",
    "phonetic",
    "intonation",
    "accent_score",
    "pronunciationscore",
    "how it sounded",
)
#: A line may name the prohibition, and the accent *marks* of written French are
#: not a judgement about speech.
ALLOWED_MARKERS = (
    "never",
    "no pronunciation",
    "won't-do",
    "wont-do",
    "does not score",
    "not score",
    "judged as text",
    "as text",
    "nobody observed",
)


def test_no_wp33_surface_judges_pronunciation_or_accent():
    offenders: list[str] = []
    for path in WP33_SOURCES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if not any(token in lowered for token in PRONUNCIATION_TOKENS):
                continue
            if any(marker in lowered for marker in ALLOWED_MARKERS):
                continue
            offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, "WP-33 surfaces must not judge pronunciation:\n" + "\n".join(offenders)


def test_the_register_copy_never_talks_about_how_something_sounded():
    for key, row in LEARNER_COPY.items():
        if not (key.startswith("pragmatics.") or key.startswith("capability.register")):
            continue
        for language, sentence in row.items():
            lowered = sentence.lower()
            for token in PRONUNCIATION_TOKENS:
                assert token not in lowered, f"{key}/{language} judges pronunciation"


def test_the_register_line_is_about_words_and_never_about_a_voice(db_session: Session):
    """A voice answer is transcribed and graded exactly like a typed one."""

    user = _user(db_session)
    scenario = _brief()
    result = evaluate_response(
        db_session,
        user=user,
        scenario=scenario,
        task=scenario.response_task,
        answer=AttemptAnswer(text="Tu peux me servir un café ?", mode=InputMode.VOICE),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    typed = evaluate_response(
        db_session,
        user=user,
        scenario=scenario,
        task=scenario.response_task,
        answer=AttemptAnswer(text="Tu peux me servir un café ?", mode=InputMode.TEXT),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    assert isinstance(result.correction, Correction)
    assert result.correction == typed.correction


# ==========================================================================
# 7. The below-B1 register decision (owner's standing guidance)
# ==========================================================================

def test_lilas_coarse_register_is_already_stripped_below_b1_in_the_data_path():
    """WP-17 landed this; WP-33 only re-pins it so it cannot quietly regress.

    The stripping lives in `living_story._cast_for_level`, which WP-33 does not
    own — hence a read-only assertion rather than an edit.
    """

    from app.services import living_story

    assert "putain" in living_story.VULGAR_TERMS
    assert living_story.CLEAN_REGISTER_LEVELS == frozenset({"A1", "A2"})
    cleaned = living_story._cast_for_level(
        [{"id": "lila_bonnet", "speech_pattern": "Warmth. Lots of 'putain' affectionately."}],
        "A1",
    )
    assert "putain" not in json.dumps(cleaned)
    assert cleaned[0]["register_note"]
    # Above the band the bible keeps its own voice.
    kept = living_story._cast_for_level(
        [{"id": "lila_bonnet", "speech_pattern": "Lots of 'putain' affectionately."}], "B1"
    )
    assert "putain" in json.dumps(kept)


def test_the_authored_scenarios_carry_no_coarse_register_at_any_band():
    from app.services.living_story import VULGAR_TERMS

    for path in _scenario_files():
        text = path.read_text(encoding="utf-8").lower()
        for term in VULGAR_TERMS:
            if term == "con":  # a substring of « conseil », « content », « raconte »
                continue
            assert f" {term} " not in text, f"{path} carries coarse register: {term}"
