"""WP-66 ⋈ WP-64 — «le jour de lettre», wired.

WP-66 shipped the day shape behind one registration point and WP-64 shipped the
letters; neither package could close the seam between them, so «jour de lettre»
was a contract nobody had switched on. These tests hold the join down:

* the letter the journey offers is the letter the Courrier is already showing —
  read through the scheduler's own predicate, so the two surfaces cannot
  disagree about which letter is next;
* answering it inside the journey finishes that mission through
  ``MissionScheduler.complete``, which is where WP-64 put the writeback, the
  outcome, the mood step and the chain's next instalment — once, and only once;
* the answered letter is no longer waiting in the Courrier;
* a day with nothing waiting is a day whose shape is simply not eligible.

Everything runs on the fake path (``_safe_llm`` returns ``None``): no provider is
called and nothing is spent.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

import app.services.missions as missions_module
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import story_correspondence as courrier
from app.services.daily_journey import DailyJourneyService
from app.services.journey_contracts import (
    AssistanceLevel,
    DayShape,
    EvidenceKind,
    InputMode,
    StepKind,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_day_shapes import (
    DayShapeInputs,
    LetterOffer,
    choose_day_shape,
    eligible_shapes,
    letter_offer_for,
    set_letter_provider,
)
from app.services.living_story import STATE_KEY, story_context
from app.services.missions import MissionScheduler

#: A fixed thread id: the story-letter die is seeded on it, so the hand dealt
#: here is the same one in September 2026 and in CI next year.
THREAD_SEED = UUID("aaaaaaaa-1111-4111-8111-1111111111a1")

MONDAY = date(2026, 9, 21)


# ---------------------------------------------------------------------------
# Fixtures — a learner with a living story and a letter waiting
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _installed_provider(monkeypatch: pytest.MonkeyPatch):
    """The wiring under test, installed and taken down around every test.

    The provider is a module-level global, so leaving it registered would leak
    a Courrier into every other suite in the same process.
    """

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    courrier.install_letter_provider()
    try:
        yield
    finally:
        set_letter_provider(None)


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"letter-day-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _living_thread(
    db_session, user: User, *, moods: dict | None = None, thread_id: UUID | None = None
) -> SerialThread:
    thread = SerialThread(
        id=thread_id or uuid4(),
        user_id=user.id,
        status="active",
        world_bible={
            "logline": "Une vie parisienne.",
            "cast": [
                {"id": "samira", "name": "Samira", "role": "boulangère"},
                {"id": "romy_tremblay", "name": "Romy", "role": "journaliste"},
            ],
            "setting": {"recurring_locations": [{"id": "le_mistral", "name_fr": "Le Mistral"}]},
        },
        state={STATE_KEY: {"events": [], "commitments": [], "moods": dict(moods or {})}},
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()
    return thread


def _journey_event(thread: SerialThread, *, event_id: str) -> None:
    """One resolved journey scene in the ledger — what a letter may be born of."""

    state = dict(thread.state)
    live = dict(state[STATE_KEY])
    live["events"] = [
        *list(live.get("events") or []),
        {
            "id": event_id,
            "scene_id": str(uuid4()),
            "witnesses": ["romy_tremblay"],
            "summary_fr": "Vous avez refusé de signer la pétition de Romy.",
            "source_quotes": ["Je ne signerai pas."],
            "outcome": "met",
            "at": datetime.now(UTC).isoformat(),
        },
    ]
    state[STATE_KEY] = live
    thread.state = state


def _waiting_letter(db_session, user: User, **columns) -> RealWorldMission:
    """An `ad_hoc` letter of the kind `/missions/today` materialises."""

    mission = RealWorldMission(
        user_id=user.id,
        status="available",
        cadence="ad_hoc",
        mission_type="message",
        title="Le pain de demain",
        brief="Répondez à la boulangère.",
        correspondent_id="samira",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[
            {
                "id": "real_world_task",
                "label": "Écrire un message qu'on pourrait vraiment envoyer",
                "kind": "communication",
                "required": True,
            },
            {
                "id": "vocabulary_41",
                "label": "Placer « le pain » naturellement",
                "kind": "vocabulary",
                "word_id": 41,
                "required": False,
            },
        ],
        prompt_payload={
            "messenger": {
                "contact_name": "Samira",
                "contact_role": "boulangère",
                "thread_title": "Le pain de demain",
                "opening_message": "Bonjour ! Je vous garde le pain aux céréales ?",
            },
            "variety": {"domain": "food_dining", "contact": "Samira", "channel": "counter_chat"},
        },
        recap_payload={},
        **columns,
    )
    db_session.add(mission)
    db_session.commit()
    db_session.refresh(mission)
    return mission


def _journey_with_letter(db_session, user: User, mission: RealWorldMission, *, text: str):
    """A real journey whose respond step is that letter, answered.

    The rows are the ones the planner writes (`_persist_plan`): the letter block
    on the respond step's `public_prompt`, the learner's turns on its
    `private_task`. Building them here keeps the test on the seam rather than on
    the whole daily-journey state machine, which has its own suite.
    """

    journey = DailyJourney(
        user_id=user.id,
        local_date=MONDAY,
        timezone="Europe/Paris",
        status="active",
        plan_selection={"day_shape": str(DayShape.LETTER), "shape_reason": "seeded_dice"},
    )
    step = DailyJourneyStep(
        ordinal=0,
        kind=str(StepKind.RESPOND),
        status="completed",
        public_prompt={
            "turn_index": 0,
            "max_turns": 2,
            "letter": {
                "mission_id": str(mission.id),
                "correspondent_id": "samira",
                "correspondent_name": "Samira",
                "subject_fr": "Le pain de demain",
                "body_fr": "Bonjour ! Je vous garde le pain aux céréales ?",
                "objective_native": "Écrire un message qu'on pourrait vraiment envoyer",
            },
        },
        private_task={"turns": [{"learner": text, "character": "Parfait, à demain."}]},
    )
    journey.steps.append(step)
    db_session.add(journey)
    db_session.commit()
    return journey, step


def _evaluation(outcome: TaskOutcome, *, produced: tuple[str, ...] = ()):
    """The shape `_finish_answered_letter` reads off a graded respond turn."""

    class _Evaluation:
        def __init__(self) -> None:
            self.outcome = outcome
            self.observations = [
                TargetObservation(
                    target=TargetRef(kind=TargetKind.VOCABULARY, id=item, label_fr="le pain"),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                )
                for item in produced
            ]

    return _Evaluation()


def _service(db_session) -> DailyJourneyService:
    # The seam reaches no adapter: `_finish_answered_letter` touches the session
    # and the Courrier and nothing else.
    return DailyJourneyService(db_session, adapters=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. The offer
# ---------------------------------------------------------------------------


def test_no_letter_waiting_keeps_the_shape_ineligible(db_session):
    """WP-66's rule survives the wiring: no letter, no letter day."""

    user = _user(db_session)
    _living_thread(db_session, user)

    assert courrier.awaiting_letter(db_session, user=user) is None
    offer = letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session)
    assert offer is None
    inputs = DayShapeInputs(user_id=str(user.id), local_date=MONDAY, letter=offer)
    assert DayShape.LETTER not in eligible_shapes(inputs)


def test_without_a_session_the_provider_offers_nothing(db_session):
    """A caller with nothing to read gets the answer it had before the wiring."""

    user = _user(db_session)
    _waiting_letter(db_session, user)
    assert letter_offer_for(user_id=str(user.id), local_date=MONDAY) is None


def test_the_offer_is_the_letter_the_courrier_is_already_showing(db_session):
    """One selection, not two: the journey reads the scheduler's own predicate."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)

    assert courrier.awaiting_letter(db_session, user=user).id == mission.id
    offer = letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session)
    assert isinstance(offer, LetterOffer)
    assert offer.mission_id == str(mission.id)
    assert offer.correspondent_id == "samira"
    assert offer.correspondent_name == "Samira"
    assert offer.body_fr == "Bonjour ! Je vous garde le pain aux céréales ?"
    assert offer.is_renderable()
    # No rubric, no answer key, no mission model crosses the seam.
    assert set(offer.__slots__) == {
        "mission_id",
        "correspondent_id",
        "correspondent_name",
        "subject_fr",
        "body_fr",
        "objective_native",
    }
    assert DayShape.LETTER in eligible_shapes(
        DayShapeInputs(user_id=str(user.id), local_date=MONDAY, letter=offer)
    )


def test_a_finished_letter_is_not_offered_again(db_session):
    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)
    mission.status = "completed"
    db_session.commit()

    assert courrier.awaiting_letter(db_session, user=user) is None
    assert letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session) is None


# ---------------------------------------------------------------------------
# 2. WP-63's chapter shape, honoured defensively
# ---------------------------------------------------------------------------


def _offer() -> LetterOffer:
    return LetterOffer(
        mission_id="m-1",
        correspondent_id="samira",
        correspondent_name="Samira",
        subject_fr="Le pain de demain",
        body_fr="Bonjour ! Je vous garde le pain aux céréales ?",
        objective_native="Écrire un message qu'on pourrait vraiment envoyer",
    )


def test_a_letter_chapter_deals_a_letter_day():
    """WP-63 may say this chapter's turn beat is a letter. The day agrees."""

    decision = choose_day_shape(
        DayShapeInputs(
            user_id="learner-a",
            local_date=MONDAY,
            chapter_shape="letter",
            letter=_offer(),
            audio_available=True,
            errata_count=3,
        )
    )
    assert decision.shape is DayShape.LETTER
    assert decision.reason == "chapter_letter_shape"


def test_a_letter_chapter_without_a_letter_is_not_a_letter_day():
    """The pool is the floor under every rule: a shape needs its material."""

    decision = choose_day_shape(
        DayShapeInputs(
            user_id="learner-a",
            local_date=MONDAY,
            chapter_shape="letter",
            letter=None,
            audio_available=True,
        )
    )
    assert decision.shape is not DayShape.LETTER
    assert decision.reason != "chapter_letter_shape"


def test_a_chapter_shape_this_build_does_not_know_changes_nothing():
    """WP-63 is in flight; an unknown value must cost nothing."""

    plain = choose_day_shape(DayShapeInputs(user_id="learner-a", local_date=MONDAY))
    exotic = choose_day_shape(
        DayShapeInputs(user_id="learner-a", local_date=MONDAY, chapter_shape="bottle")
    )
    assert exotic.shape is plain.shape and exotic.reason == plain.reason


def test_the_day_reads_the_chapter_shape_off_the_story_context(db_session):
    """`.get` everywhere: the key may live in three places, or in none."""

    user = _user(db_session)
    journey = DailyJourney(
        user_id=user.id, local_date=MONDAY, timezone="UTC", status="preparing"
    )
    db_session.add(journey)
    db_session.commit()

    class _Brief:
        story_context = {"chapter": {"shape": "letter"}}

    inputs = _service(db_session)._day_shape_inputs(
        user, journey, _Brief(), errata_count=0
    )
    assert inputs.chapter_shape == "letter"

    class _Bare:
        story_context = {}

    assert (
        _service(db_session)._day_shape_inputs(user, journey, _Bare(), errata_count=0).chapter_shape
        is None
    )


# ---------------------------------------------------------------------------
# 3. The objective flags the journey's verdict writes
# ---------------------------------------------------------------------------


OBJECTIVES = [
    {"id": "real_world_task", "label": "Mener la situation à son terme", "required": True},
    {"id": "vocabulary_41", "label": "Placer « le pain »", "word_id": 41, "required": False},
]


def test_a_met_turn_keeps_the_letter():
    progress = courrier.objective_progress_from_journey(
        objectives=OBJECTIVES, outcome="met", produced_target_ids=[]
    )
    by_id = {row["id"]: row for row in progress}
    assert by_id["real_world_task"]["met"] is True
    # Nothing was observed for the word, so nothing claims it was placed.
    assert by_id["vocabulary_41"]["met"] is False
    assert (
        courrier.outcome_from_objectives(objectives=OBJECTIVES, progress_by_id=by_id)
        == "kept"
    )


def test_a_partly_met_turn_that_placed_the_word_is_partial():
    progress = courrier.objective_progress_from_journey(
        objectives=OBJECTIVES,
        outcome="partially_met",
        produced_target_ids=["vocabulary:41"],
    )
    by_id = {row["id"]: row for row in progress}
    assert by_id["real_world_task"]["met"] is False
    assert by_id["vocabulary_41"]["met"] is True, "the journey saw that word produced"
    assert (
        courrier.outcome_from_objectives(objectives=OBJECTIVES, progress_by_id=by_id)
        == "partial"
    )


def test_a_turn_that_met_nothing_misses():
    progress = courrier.objective_progress_from_journey(
        objectives=OBJECTIVES, outcome="not_yet", produced_target_ids=["vocabulary:99"]
    )
    by_id = {row["id"]: row for row in progress}
    assert all(row["met"] is False for row in progress), "a different word is not this word"
    assert (
        courrier.outcome_from_objectives(objectives=OBJECTIVES, progress_by_id=by_id)
        == "missed"
    )


def test_the_note_is_in_the_learners_language():
    english = courrier.objective_progress_from_journey(
        objectives=OBJECTIVES, outcome="met", language="en"
    )
    german = courrier.objective_progress_from_journey(
        objectives=OBJECTIVES, outcome="met", language="de"
    )
    assert english[0]["note"] == "Submitted"
    assert german[0]["note"] == "Abgeschickt"


# ---------------------------------------------------------------------------
# 4. End to end: a story-born letter, answered in the journey
# ---------------------------------------------------------------------------


def test_a_story_born_letter_answered_in_the_journey_lands_in_tomorrows_story(db_session):
    """The whole seam, in the order a learner meets it.

    A scene the learner played makes a character write; `/missions/today`
    materialises that letter; the day's dice can now deal «jour de lettre» and
    the planner puts the letter on the respond step; the learner answers it
    inside their journey; and the next day's story context knows.
    """

    user = _user(db_session)
    thread = _living_thread(
        db_session,
        user,
        moods={"romy_tremblay": {"mood": 0, "trust": 2}},
        thread_id=THREAD_SEED,
    )
    for index in range(6):
        _journey_event(thread, event_id=f"journey:{index}:story")
    db_session.add(thread)
    db_session.commit()

    # --- the letter appears, through the Courrier's own entry point ---------
    today = asyncio.run(MissionScheduler(db_session).today(user))
    active = today["active_mission"]
    assert active is not None
    assert active["courrier"]["origin"] == "story_born"
    assert active["correspondent"]["id"] == "romy_tremblay"
    mission_id = active["id"]

    # --- the day can now be a «jour de lettre» -----------------------------
    offer = letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session)
    assert offer is not None and offer.mission_id == mission_id
    inputs = DayShapeInputs(user_id=str(user.id), local_date=MONDAY, letter=offer)
    assert DayShape.LETTER in eligible_shapes(inputs)

    # --- the learner answers it inside the journey -------------------------
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    journey, step = _journey_with_letter(
        db_session,
        user,
        mission,
        text="Bonjour Romy, je vais vous rappeler demain pour en reparler.",
    )
    service = _service(db_session)
    service._finish_answered_letter(user, journey, step, _evaluation(TaskOutcome.MET))

    db_session.refresh(mission)
    assert mission.status == "completed"
    assert mission.outcome == "kept"
    assert mission.recap_payload["courrier_outcome"] == "kept"
    # The reply the learner actually wrote is what the letter was finished with.
    attempts = list(mission.attempts)
    assert len(attempts) == 1
    assert attempts[0].mode == courrier.JOURNEY_ANSWER_MODE
    assert "je vais vous rappeler demain" in attempts[0].answer_payload["text"]
    measured = mission.recap_payload["measured"]
    assert measured["objectives_met"] == measured["objectives_total"]
    assert measured["words_written"] > 0, "counted, never a formula"

    # --- and tomorrow's scene knows ----------------------------------------
    context = story_context(db_session, user)
    event = next(item for item in context["events"] if item.get("source") == "courrier")
    assert event["id"] == f"courrier:{mission.id}"
    assert event["witnesses"] == ["romy_tremblay"]
    assert event["outcome"] == "kept"
    assert context["moods"]["romy_tremblay"]["mood"] == 1, "the correspondent moved"
    assert context["moods"]["romy_tremblay"]["trust"] == 3
    # The promise the learner made is a commitment the story holds.
    assert any("rappeler demain" in item["text_fr"] for item in context["commitments"])


def test_the_letter_is_finished_once_however_often_the_turn_is_replayed(db_session):
    """A replayed mutation must not pay the letter twice.

    Idempotence matters here more than anywhere else in the day: a second
    completion would be a second mood step, a second `events[]` row and a
    second instalment of the chain.
    """

    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": 0, "trust": 2}})
    mission = _waiting_letter(db_session, user)
    journey, step = _journey_with_letter(
        db_session, user, mission, text="Bonjour Samira, je passerai demain matin."
    )
    service = _service(db_session)

    for _ in range(3):
        service._finish_answered_letter(user, journey, step, _evaluation(TaskOutcome.MET))

    db_session.refresh(mission)
    assert len(list(mission.attempts)) == 1
    assert step.private_task["letter_answered"]["mission_id"] == str(mission.id)
    context = story_context(db_session, user)
    courrier_events = [item for item in context["events"] if item.get("source") == "courrier"]
    assert len(courrier_events) == 1
    assert context["moods"]["samira"]["mood"] == 1, "one letter, one step"


def test_the_answered_letter_is_no_longer_waiting_in_the_courrier(db_session):
    """What a learner would find unforgivable: answering, then being asked again."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)
    journey, step = _journey_with_letter(
        db_session, user, mission, text="Bonjour Samira, je passerai demain matin."
    )

    _service(db_session)._finish_answered_letter(user, journey, step, _evaluation(TaskOutcome.MET))

    assert courrier.awaiting_letter(db_session, user=user) is None
    assert letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session) is None
    today = asyncio.run(MissionScheduler(db_session).today(user))
    assert (today["active_mission"] or {}).get("id") != str(mission.id)


def test_an_ordinary_day_touches_no_letter(db_session):
    """No letter block on the step, nothing happens. The Courrier keeps waiting."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)
    journey, step = _journey_with_letter(db_session, user, mission, text="Bonjour.")
    prompt = dict(step.public_prompt)
    prompt["letter"] = None
    step.public_prompt = prompt
    db_session.commit()

    _service(db_session)._finish_answered_letter(user, journey, step, _evaluation(TaskOutcome.MET))

    db_session.refresh(mission)
    assert mission.status == "available"
    assert courrier.awaiting_letter(db_session, user=user).id == mission.id


def test_a_courrier_that_cannot_be_reached_never_costs_the_turn(db_session, monkeypatch):
    """The learner has already answered and already been graded. That stands."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)
    journey, step = _journey_with_letter(db_session, user, mission, text="Bonjour Samira.")

    def boom(*_args, **_kwargs):
        raise RuntimeError("the Courrier is down")

    monkeypatch.setattr(courrier, "answer_letter_from_journey", boom)
    # No exception reaches the turn.
    _service(db_session)._finish_answered_letter(user, journey, step, _evaluation(TaskOutcome.MET))
    assert "letter_answered" not in (step.private_task or {})


def test_a_lapsed_letter_is_never_finished_by_a_journey(db_session):
    """An ignored letter already had its consequence; answering it late is not it."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(
        db_session,
        user,
        chain_id="affair-1",
        chain_index=2,
        chain_total=3,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    mission.status = "lapsed"
    db_session.commit()

    assert (
        courrier.answer_letter_from_journey(
            db_session,
            user=user,
            mission_id=str(mission.id),
            learner_text="Désolé, je réponds tard.",
            outcome="met",
        )
        is None
    )


# ---------------------------------------------------------------------------
# 5. The seam's own guards
# ---------------------------------------------------------------------------


def test_a_provider_written_before_this_wiring_is_still_called_correctly(db_session):
    """WP-66's two-argument contract still holds: `db` is offered, not forced."""

    seen: list[tuple[str, date]] = []

    def legacy(*, user_id: str, local_date: date):
        seen.append((user_id, local_date))
        return _offer()

    set_letter_provider(legacy)
    offer = letter_offer_for(user_id="learner-a", local_date=MONDAY, db=db_session)
    assert offer is not None and offer.correspondent_name == "Samira"
    assert seen == [("learner-a", MONDAY)]


def test_a_letter_with_no_body_is_not_offered(db_session):
    """`is_renderable` is the floor; a blank letter is not a day's respond step."""

    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _waiting_letter(db_session, user)
    payload = dict(mission.prompt_payload)
    payload["messenger"] = {**payload["messenger"], "opening_message": "   "}
    mission.prompt_payload = payload
    db_session.commit()

    assert courrier.journey_letter_facts(db_session, user=user) is None
    assert letter_offer_for(user_id=str(user.id), local_date=MONDAY, db=db_session) is None


# ---------------------------------------------------------------------------
# 6. The whole thing over HTTP, with nothing stubbed but the dice
# ---------------------------------------------------------------------------


def test_a_letter_day_played_over_the_real_api_finishes_the_letter(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """The assembled system: real router, real planner, real respond turn.

    Only the dice are held still — which shape a learner is dealt is decided and
    tested in `test_journey_planner.py`; what this test needs is the letter day
    itself. Everything else is the shipped path, including the part that made
    this integration worth a test of its own: `MissionScheduler.complete`
    commits, and it is called from inside the turn's own transaction.
    """

    from app.api.deps import get_db
    from app.api.v1.endpoints.daily_journey import get_journey_adapters
    from app.config import settings
    from app.main import create_app
    from app.services import daily_journey as daily_journey_service
    from app.services.daily_journey_adapters import build_default_adapters
    from app.services.journey_day_shapes import DayShapeDecision

    real_choice = daily_journey_service.choose_day_shape

    def always_the_letter(inputs: DayShapeInputs) -> DayShapeDecision:
        if inputs.letter is not None:
            return DayShapeDecision(shape=DayShape.LETTER, reason="seeded_dice")
        return real_choice(inputs)

    monkeypatch.setattr(daily_journey_service, "choose_day_shape", always_the_letter)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")

    app = create_app()
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_journey_adapters] = build_default_adapters

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        email = f"letter-day-{uuid4().hex}@example.com"
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "securepass123",
                "target_language": "fr",
                "native_language": "en",
                "cefr_estimate": "A1.1",
            },
        )
        login = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "securepass123"}
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        user = db_session.query(User).filter(User.email == email).one()
        _living_thread(db_session, user, moods={"samira": {"mood": 0, "trust": 2}})
        mission = _waiting_letter(db_session, user)

        created = client.post(
            "/api/v1/daily-journeys",
            headers=headers,
            json={
                "mutation_id": uuid4().hex,
                "timezone": "Europe/Paris",
                "budget_seconds": 300,
                "preferred_input_mode": "text",
            },
        )
        assert created.status_code in (200, 201, 202), created.text
        journey = created.json()
        assert journey["day_shape"] == "letter"

        # Walk to the respond step, answering nothing on the way.
        for _ in range(12):
            step_id = journey.get("current_step_id")
            assert step_id, "the day ran out of steps before the letter"
            step = next(item for item in journey["steps"] if item["id"] == step_id)
            if step["kind"] == "respond":
                break
            response = client.post(
                f"/api/v1/daily-journeys/{journey['id']}/advance",
                headers=headers,
                json={
                    "mutation_id": uuid4().hex,
                    "expected_revision": journey["revision"],
                    "current_step_id": step_id,
                },
            )
            assert response.status_code == 200, response.text
            journey = response.json()

        # The letter the Courrier was showing is the letter on the step.
        assert step["prompt"]["letter"]["mission_id"] == str(mission.id)
        assert step["prompt"]["letter"]["correspondent_name"] == "Samira"
        assert "rubric" not in step["prompt"]["letter"]

        # The turn, including the repair turn WP-06 may ask for: the letter is
        # finished when the *step* is, never in the middle of a conversation.
        for _attempt in range(3):
            answered = client.post(
                f"/api/v1/daily-journeys/{journey['id']}/steps/{step['id']}/attempts",
                headers=headers,
                json={
                    "mutation_id": uuid4().hex,
                    "expected_revision": journey["revision"],
                    "input": {
                        "mode": "text",
                        "text": "Bonjour Samira, je passerai demain matin prendre le pain.",
                    },
                },
            )
            assert answered.status_code == 200, answered.text
            body = answered.json()
            journey = body["journey"]
            if not body.get("next_turn"):
                break
            # Mid-conversation: the letter must still be waiting.
            db_session.refresh(mission)
            assert mission.status != "completed", "a repair turn is not an answer"

    db_session.refresh(mission)
    assert mission.status == "completed", "the letter was answered; it is finished"
    assert mission.outcome in {"kept", "partial", "missed"}
    assert len(list(mission.attempts)) == 1
    assert courrier.awaiting_letter(db_session, user=user) is None
    event = next(
        item
        for item in story_context(db_session, user)["events"]
        if item.get("source") == "courrier"
    )
    assert event["mission_id"] == str(mission.id)
