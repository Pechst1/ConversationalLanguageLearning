# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-L6 (first half) and WP-L9 (timing half) — the rhythm sizes the day.

* The planner scales with the learner's rhythm: Léger still fits five minutes,
  Régulier plans an 8–10-minute day at the prior pace, Soutenu and Intensif
  stay inside their budgets, and no rhythm ever plans a second episode.
* The rhythm is a Réglages choice stored as ``daily_goal_minutes``; the server,
  not the client, sizes the day from it.
* The measured pace reaches the planner once three days are measured.
* «Nouveaux mots par jour» is one intake pool: the day and the word drill
  never introduce more than the quota together, and never the same word twice.
* Each step records when it started; the daily rollup reports p50/p90 per rhythm.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import daily_journey as daily_journey_module
from app.services import journey_learning, vocabulary_pace
from app.services import journey_planner as planner
from app.services.journey_contracts import (
    RHYTHM_BUDGETS,
    DayShape,
    LearningCandidate,
    StepKind,
    TargetKind,
    TargetRef,
    rhythm_caps,
)
from app.services.journey_day_shapes import DayShapeInputs
from app.services.journey_events import MeasuredPace, journey_daily_rollup
from app.services.journey_rhythm import (
    RHYTHM_BUDGET_SECONDS,
    budget_seconds_for,
    rhythm_for_minutes,
)
from app.services.streak import local_today
from tests.test_journey_end_to_end import (
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    key,
    learner_id,
    register,
)
from tests.test_journey_events import build_journey, make_user
from tests.test_journey_planner import _brief, _candidate

#: A realistic queue a few weeks in, long enough for a Soutenu day's pool.
WORDS = (
    ("un café", "a coffee"), ("la clé", "the key"), ("tu viens demain", "you are coming tomorrow"),
    ("vous partez déjà", "you are leaving already"), ("à tout à l'heure", "see you shortly"),
    ("brouillard", "fog"), ("le zinc", "the counter"), ("la pluie", "the rain"),
    ("une table", "a table"), ("le comptoir", "the bar"), ("en terrasse", "on the terrace"),
    ("un croissant", "a croissant"), ("merci beaucoup", "thank you very much"),
    ("la porte", "the door"), ("il pleut", "it is raining"), ("un thé", "a tea"),
    ("le canal", "the canal"), ("une chaise", "a chair"), ("à emporter", "to take away"),
    ("l'addition", "the bill"), ("un verre d'eau", "a glass of water"), ("la carte", "the menu"),
    ("le serveur", "the waiter"), ("la fenêtre", "the window"), ("un journal", "a newspaper"),
    ("la gare", "the station"), ("un billet", "a ticket"), ("le quai", "the platform"),
    ("en retard", "late"), ("à l'heure", "on time"), ("la valise", "the suitcase"),
    ("un parapluie", "an umbrella"),
)


def _queue(size: int) -> list[LearningCandidate]:
    return [
        _candidate(identifier=f"w{index}", label_fr=fr, label_native=native, priority=100 - index)
        for index, (fr, native) in enumerate(WORDS[:size])
    ]


def _plan(budget: int, *, shape: DayShape = DayShape.STANDARD, pool: int | None = None):
    size = rhythm_caps(budget).candidate_limit if pool is None else pool
    return planner.plan_journey(
        scenario=_brief(),
        candidates=_queue(size),
        budget_seconds=budget,
        practice=True,
        dice=DayShapeInputs(user_id="learner-l6", local_date=date(2026, 9, 23)),
        day_shape=shape,
    )


# ---------------------------------------------------------------------------
# 1. The planner, per rhythm
# ---------------------------------------------------------------------------


def test_leger_still_fits_five_minutes_and_is_the_wp78_day() -> None:
    plan = _plan(300)
    plan.validate()
    assert plan.estimated_active_seconds <= 300
    assert planner.practice_fill_order(rhythm_caps(300)) == planner.PRACTICE_FILL_ORDER
    # The five-minute day is byte-for-byte the day the default budget plans.
    default = planner.plan_journey(
        scenario=_brief(),
        candidates=_queue(8),
        practice=True,
        dice=DayShapeInputs(user_id="learner-l6", local_date=date(2026, 9, 23)),
        day_shape=DayShape.STANDARD,
    )
    assert [step.public_prompt for step in plan.steps] == [
        step.public_prompt for step in default.steps
    ]


def test_regulier_plans_an_eight_to_ten_minute_day_at_the_prior_pace() -> None:
    plan = _plan(600)
    plan.validate()
    assert 480 <= plan.estimated_active_seconds <= 600, plan.rationale
    kinds = [step.kind for step in plan.steps]
    # The four movements, in order: Rappel (warm-ups), Scène (+ guided
    # items), Réponse, Bouclé (a word from today, then the ending).
    scene_at = kinds.index(StepKind.SCENE)
    respond_at = kinds.index(StepKind.RESPOND)
    assert scene_at > 3, "Régulier's Rappel is longer than Léger's three warm-ups"
    assert respond_at - scene_at - 1 > 2, "and so are the Scène's guided items"
    assert kinds[respond_at + 1] is StepKind.RECALL
    assert kinds[-1] is StepKind.RESOLUTION
    assert plan.steps[respond_at].public_prompt["max_turns"] == 2


@pytest.mark.parametrize("budget", [1200, 1800])
def test_soutenu_and_intensif_stay_within_their_budgets(budget: int) -> None:
    plan = _plan(budget)
    plan.validate()
    assert plan.estimated_active_seconds <= budget
    assert plan.estimated_active_seconds > _plan(600).estimated_active_seconds


@pytest.mark.parametrize("budget", RHYTHM_BUDGETS)
@pytest.mark.parametrize(
    "shape", [DayShape.STANDARD, DayShape.LISTENING, DayShape.REPRISE, DayShape.SHORT]
)
def test_no_rhythm_ever_plans_a_second_episode(budget: int, shape: DayShape) -> None:
    plan = _plan(budget, shape=shape)
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert kinds.count(StepKind.SCENE) == 1
    assert kinds.count(StepKind.RESPOND) == 1
    assert kinds.count(StepKind.RESOLUTION) == 1
    assert kinds[-1] is StepKind.RESOLUTION
    assert plan.estimated_active_seconds <= budget


def test_a_thin_pool_makes_a_shorter_day_never_a_padded_one() -> None:
    plan = _plan(1800, pool=4)
    plan.validate()
    assert plan.estimated_active_seconds < 900
    identities = [step.target for step in plan.steps if step.kind is StepKind.RECALL]
    per_target: dict[str, int] = {}
    for target in identities:
        if target is None:
            continue
        per_target[target.id] = per_target.get(target.id, 0) + 1
    assert max(per_target.values()) <= rhythm_caps(1800).uses_per_target + 1


def test_a_trusted_slow_pace_plans_fewer_items_inside_the_same_budget() -> None:
    prior = _plan(600)
    slow = planner.plan_journey(
        scenario=_brief(),
        candidates=_queue(16),
        budget_seconds=600,
        practice=True,
        dice=DayShapeInputs(user_id="learner-l6", local_date=date(2026, 9, 23)),
        day_shape=DayShape.STANDARD,
        pace=planner.PacingProfile(step_multiplier=1.35, observations=3),
    )
    slow.validate()
    assert slow.estimated_active_seconds <= 600
    assert planner.graded_interactions(slow) < planner.graded_interactions(prior)


# ---------------------------------------------------------------------------
# 2. The rhythm setting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("minutes", "rhythm"),
    [(None, "regulier"), (5, "leger"), (7, "leger"), (8, "regulier"), (10, "regulier"),
     (14, "regulier"), (15, "soutenu"), (20, "soutenu"), (25, "soutenu"), (30, "intensif"),
     (60, "intensif")],
)
def test_stored_minutes_map_onto_a_rhythm(minutes, rhythm) -> None:
    assert rhythm_for_minutes(minutes) == rhythm


def test_settings_expose_and_change_the_rhythm(assembled_client: TestClient) -> None:
    headers = register(assembled_client, "rhythm-settings@example.com")
    settings = assembled_client.get("/api/v1/users/me/settings", headers=headers).json()
    assert settings["rhythm"] == "regulier", "a new learner starts on Régulier"
    assert settings["daily_goal_minutes"] == 10

    changed = assembled_client.patch(
        "/api/v1/users/me/settings", headers=headers, json={"rhythm": "soutenu"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["rhythm"] == "soutenu"
    assert changed.json()["daily_goal_minutes"] == 20

    refused = assembled_client.patch(
        "/api/v1/users/me/settings", headers=headers, json={"rhythm": "turbo"}
    )
    assert refused.status_code == 422

    pace = assembled_client.patch(
        "/api/v1/users/me/settings", headers=headers, json={"new_words_per_day": 20}
    )
    assert pace.status_code == 200 and pace.json()["new_words_per_day"] == 20
    too_many = assembled_client.patch(
        "/api/v1/users/me/settings", headers=headers, json={"new_words_per_day": 51}
    )
    assert too_many.status_code == 422


def test_a_legacy_minutes_value_reads_as_a_rhythm(
    assembled_client: TestClient, db_session: Session
) -> None:
    headers = register(assembled_client, "rhythm-legacy@example.com")
    user = db_session.get(User, learner_id(db_session, "rhythm-legacy@example.com"))
    user.daily_goal_minutes = 15  # the old default preset
    db_session.commit()
    settings = assembled_client.get("/api/v1/users/me/settings", headers=headers).json()
    assert settings["rhythm"] == "soutenu"
    assert settings["daily_goal_minutes"] == 15, "never rewritten behind the learner's back"
    assert budget_seconds_for(user) == 1200


def test_the_server_sizes_the_day_from_the_rhythm_not_the_client(
    assembled_client: TestClient, db_session: Session, journey_enabled
) -> None:
    headers = register(assembled_client, "rhythm-journey@example.com")
    # An older client still sends 300; the learner is on Régulier.
    created = assembled_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={"mutation_id": key(), "timezone": "Europe/Paris", "budget_seconds": 300},
    )
    assert created.status_code in (200, 201, 202), created.text
    journey = created.json()
    assert journey["budget_seconds"] == RHYTHM_BUDGET_SECONDS["regulier"] == 600
    assert journey["estimated_active_seconds"] <= journey["budget_seconds"]
    scenes = [step for step in journey["steps"] if step["kind"] == "scene"]
    assert len(scenes) == 1


def test_a_leger_learner_gets_a_five_minute_day(
    assembled_client: TestClient, db_session: Session, journey_enabled
) -> None:
    headers = register(assembled_client, "rhythm-leger@example.com")
    assembled_client.patch("/api/v1/users/me/settings", headers=headers, json={"rhythm": "leger"})
    created = assembled_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={"mutation_id": key(), "timezone": "Europe/Paris"},
    )
    assert created.status_code in (200, 201, 202), created.text
    assert created.json()["budget_seconds"] == 300
    assert created.json()["estimated_active_seconds"] <= 300


# ---------------------------------------------------------------------------
# 3. The measured pace reaches the planner after three measured days
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("days", "fed"), [(0, False), (2, False), (3, True), (9, True)])
def test_the_measured_pace_is_fed_once_three_days_are_measured(
    assembled_client: TestClient,
    db_session: Session,
    journey_enabled,
    monkeypatch: pytest.MonkeyPatch,
    days: int,
    fed: bool,
) -> None:
    email = f"rhythm-pace-{days}@example.com"
    headers = register(assembled_client, email)
    monkeypatch.setattr(
        daily_journey_module,
        "measured_pace",
        lambda db, **_: MeasuredPace(days=days, step_multiplier=1.2, samples=days),
    )
    seen: list[object] = []
    original = planner.plan_journey

    def spy(**kwargs):
        seen.append(kwargs.get("pace"))
        return original(**kwargs)

    monkeypatch.setattr(planner, "plan_journey", spy)
    assembled_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={"mutation_id": key(), "timezone": "Europe/Paris"},
    )
    assert seen, "the planner was called"
    pace = seen[-1]
    if fed:
        assert isinstance(pace, planner.PacingProfile)
        assert pace.is_trusted and pace.step_multiplier == 1.2
    else:
        assert pace is None


# ---------------------------------------------------------------------------
# 4. «Nouveaux mots par jour» — one intake pool
# ---------------------------------------------------------------------------


def _learner(db: Session, email: str, *, quota: int, minutes: int = 10) -> User:
    user = make_user(db, email)
    user.new_words_per_day = quota
    user.daily_goal_minutes = minutes
    user.timezone = "Europe/Paris"
    db.commit()
    return user


def _word(db: Session, text: str) -> VocabularyWord:
    word = VocabularyWord(
        word=text,
        normalized_word=text,
        language="fr",
        english_translation=f"{text} (en)",
        is_anki_card=True,
        frequency_rank=100,
    )
    db.add(word)
    db.flush()
    return word


def _introduce(db: Session, user: User, word: VocabularyWord) -> None:
    db.add(UserVocabularyProgress(user_id=user.id, word_id=word.id, reps=1, state="learning"))
    db.flush()


def test_the_drill_leaves_the_journeys_share_until_the_day_is_planned(
    db_session: Session,
) -> None:
    user = _learner(db_session, f"pool-{uuid.uuid4().hex[:8]}@example.com", quota=10)
    # Régulier's journey share is four new words.
    room, excluded = vocabulary_pace.drill_new_word_room(db_session, user)
    assert (room, excluded) == (10 - rhythm_caps(600).journey_new_words, set())
    for index in range(3):
        _introduce(db_session, user, _word(db_session, f"drillmot{index}"))
    room, _ = vocabulary_pace.drill_new_word_room(db_session, user)
    assert room == 10 - 3 - 4
    assert vocabulary_pace.journey_new_word_room(db_session, user) == 7


def test_drill_and_journey_never_exceed_the_quota_or_introduce_a_word_twice(
    db_session: Session,
) -> None:
    user = _learner(db_session, f"pool-{uuid.uuid4().hex[:8]}@example.com", quota=5)
    drilled = [_word(db_session, f"poolmot{index}") for index in range(2)]
    for word in drilled:
        _introduce(db_session, user, word)
    # The journey may introduce what the drill left: 5 - 2 = 3.
    journey_room = vocabulary_pace.journey_new_word_room(db_session, user)
    assert journey_room == 3
    reserved = [_word(db_session, f"scenemot{index}") for index in range(journey_room)]
    db_session.add(
        DailyJourney(
            id=uuid.uuid4(),
            user_id=user.id,
            local_date=local_today(user),
            timezone="Europe/Paris",
            status="active",
            budget_seconds=600,
            plan_selection={vocabulary_pace.JOURNEY_NEW_WORDS_KEY: [w.id for w in reserved]},
            created_at=datetime.now(UTC),
        )
    )
    db_session.flush()
    room, excluded = vocabulary_pace.drill_new_word_room(db_session, user)
    assert room == 0, "2 drilled + 3 reserved = the quota of 5"
    assert excluded == {w.id for w in reserved}
    # The learner then answers the journey's words: introduced, not doubled.
    for word in reserved:
        _introduce(db_session, user, word)
    room, excluded = vocabulary_pace.drill_new_word_room(db_session, user)
    assert room == 0 and excluded == set()
    total = len(vocabulary_pace.introduced_today(db_session, user))
    assert total == 5 <= vocabulary_pace.daily_quota(db_session, user)
    # And the drill's endpoint clamp offers nothing new at all today.
    limit, reserved_ids = vocabulary_pace.vocabulary_pace_limit(db_session, user, 8)
    assert limit == 0


def test_the_journey_admits_no_more_new_scene_words_than_its_room(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _learner(db_session, f"pool-{uuid.uuid4().hex[:8]}@example.com", quota=10)
    lexicon = [
        LearningCandidate(
            target=TargetRef(kind=TargetKind.VOCABULARY, id=str(9000 + index), label_fr=f"mot{index}",
                             label_native=f"word{index}"),
            priority_score=0.0,
            due_since_days=0,
            estimated_seconds=30,
            is_new=True,
            relevance=1.0,
            source_item_type="vocabulary",
            metadata={"anchor": "scene_lexicon"},
        )
        for index in range(5)
    ]
    monkeypatch.setattr(journey_learning, "_scene_lexicon_candidates", lambda *a, **k: list(lexicon))
    capped = journey_learning.select_learning_candidates(
        db_session, user=user, scenario=_brief(), limit=16, new_word_quota=2
    )
    assert sum(1 for c in capped if c.is_new) == 2
    unbounded = journey_learning.select_learning_candidates(
        db_session, user=user, scenario=_brief(), limit=16
    )
    assert sum(1 for c in unbounded if c.is_new) == 5, "no quota passed: the pre-WP-L6 day"


def test_a_drilled_but_not_held_word_is_preferred_among_equals() -> None:
    fragile = LearningCandidate(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="drilled", label_fr="le zinc",
                         label_native="the counter"),
        priority_score=0.0, due_since_days=0, estimated_seconds=30, is_new=False,
        relevance=0.0, source_item_type="vocabulary",
        metadata={"state": "learning", "stability": 2.5},
    )
    assert journey_learning.drilled_not_held(fragile) is True
    solid = LearningCandidate(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="solid", label_fr="la clé",
                         label_native="the key"),
        priority_score=0.0, due_since_days=0, estimated_seconds=30, is_new=False,
        relevance=0.0, source_item_type="vocabulary",
        metadata={"state": "review", "stability": 60.0},
    )
    assert journey_learning.drilled_not_held(solid) is False


def test_the_review_load_is_an_honest_estimate() -> None:
    load = vocabulary_pace.review_load_estimate(20)
    assert (load["reviews_low"], load["reviews_high"]) == (160, 200)
    assert (load["minutes_low"], load["minutes_high"]) == (16, 20)


# ---------------------------------------------------------------------------
# 5. WP-L9 — step start times and session length per rhythm
# ---------------------------------------------------------------------------


def test_each_step_records_when_it_started(
    assembled_client: TestClient, db_session: Session, journey_enabled
) -> None:
    headers = register(assembled_client, "rhythm-steps@example.com")
    created = assembled_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={"mutation_id": key(), "timezone": "Europe/Paris"},
    ).json()
    current = created["current_step_id"]
    assert current
    row = db_session.get(DailyJourneyStep, uuid.UUID(current))
    assert row.started_at is not None
    pending = [step for step in created["steps"] if step["status"] == "pending"]
    for step in pending:
        assert db_session.get(DailyJourneyStep, uuid.UUID(step["id"])).started_at is None


@pytest.fixture()
def _clean_ledger(db_session: Session):
    db_session.query(PilotEvent).delete()
    db_session.commit()
    yield
    db_session.rollback()
    db_session.query(PilotEvent).delete()
    db_session.commit()


def test_the_rollup_reports_session_length_per_rhythm(db_session: Session, _clean_ledger) -> None:
    user = make_user(db_session, f"rollup-{uuid.uuid4().hex[:8]}@example.com")
    budgets = {"leger": 300, "regulier": 600}
    for budget in budgets.values():
        for offset in range(2):
            journey_id = uuid.uuid4()
            db_session.add(
                DailyJourney(
                    id=journey_id,
                    user_id=user.id,
                    local_date=date(2026, 9, 5) - timedelta(days=offset + (2 if budget == 600 else 0)),
                    timezone="Europe/Paris",
                    status="completed",
                    budget_seconds=budget,
                    created_at=datetime.now(UTC),
                )
            )
            db_session.flush()
            build_journey(db_session, user, journey_id=journey_id, start_offset=offset * 900)
    db_session.commit()
    report = journey_daily_rollup(db_session, date(2026, 9, 5))
    by_rhythm = report["active_duration"]["by_rhythm"]
    assert list(by_rhythm) == ["leger", "regulier"]
    for row in by_rhythm.values():
        assert row["measured"] == 2
        assert row["p50_seconds"] is not None and row["p90_seconds"] is not None
