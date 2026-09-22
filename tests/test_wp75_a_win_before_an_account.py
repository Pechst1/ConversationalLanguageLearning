"""WP-75 — a win before an account (backend half).

The 2026-09-22 walk (L2–L4, L8, L9, L11): eleven sign-up inputs, placement as
the first task of a self-declared A1 learner, a 20-second cold first scene, the
answer printed above the respond task, and a first day with one exercise in it.
This file holds the backend to the contract the frontend codes against:

1. ``POST /auth/register`` needs only email + password (+ ``starting_point``).
2. Placement is never at sign-up; ``GET /placement/offer`` follows its rules.
3. The first ``POST /daily-journeys`` is authored, instant, ≥3 graded
   interactions, and makes **zero** provider calls.
4. ``journey.cast_intro``: three faces on the first day, ``null`` otherwise.
5. Day 1 finished → day 2's scene is queued to be warmed; day 2 is the engine's.
6. A character line that speaks the expected reply is refused (walk L9).
"""
from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.daily_journey import get_journey_adapters
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.main import create_app
from app.services import daily_journey as daily_journey_service
from app.services import journey_content, journey_planner, living_story, llm_service
from app.services.daily_journey_adapters import build_default_adapters
from app.services.journey_contracts import (
    ContentUnavailable,
    InputMode,
    LearningCandidate,
    TargetKind,
    TargetRef,
)
from app.services.placement import (
    PlacementService,
    journey_placement_evidence,
    opening_band,
    placement_offer,
)
from tests.test_journey_end_to_end import Driver, leaked_keys

PASSWORD = "securepass123"
TZ = "Europe/Paris"
CHARACTER_DIRS = Path(__file__).resolve().parents[1] / "web-frontend" / "public" / "assets" / "serial" / "characters"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def first_day_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", True, raising=False)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_journey_adapters] = build_default_adapters
    with TestClient(app) as test_client:
        yield test_client


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    frozen = Clock(datetime(2026, 3, 10, 9, 0, tzinfo=UTC))
    monkeypatch.setattr(daily_journey_service, "_utcnow", frozen)
    monkeypatch.setattr(
        daily_journey_service,
        "local_date_for",
        lambda tz, now=None: frozen().astimezone(daily_journey_service.ZoneInfo(tz)).date(),
    )
    return frozen


class ProviderCalls:
    """Every door to a model provider, counted. A first day may open none."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def record(self, name: str):
        def _call(*_args: Any, **_kwargs: Any) -> Any:
            self.calls.append(name)
            return ContentUnavailable(reason="provider_spy")

        return _call


@pytest.fixture()
def provider_calls(monkeypatch: pytest.MonkeyPatch) -> ProviderCalls:
    spy = ProviderCalls()

    def refuse(name: str):
        def _call(*_args: Any, **_kwargs: Any) -> Any:
            spy.calls.append(name)
            raise llm_service.LLMProviderError(f"{name}: no provider in this test")

        return _call

    monkeypatch.setattr(llm_service.OpenAIProvider, "generate", refuse("openai.generate"))
    monkeypatch.setattr(llm_service.AnthropicProvider, "generate", refuse("anthropic.generate"))
    monkeypatch.setattr(
        llm_service.LLMService, "generate_chat_completion", refuse("llm.generate_chat_completion")
    )
    monkeypatch.setattr(living_story, "generate_scene", spy.record("living_story.generate_scene"))
    monkeypatch.setattr(
        journey_content, "_generate_variation", spy.record("journey_content._generate_variation")
    )
    return spy


def register(client: TestClient, email: str, **extra: Any) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, **extra}
    )
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def email() -> str:
    return f"wp75-{uuid.uuid4().hex[:10]}@example.com"


def user_by_email(db: Session, address: str) -> User:
    return db.query(User).filter(User.email == address).one()


# ---------------------------------------------------------------------------
# 1. Register with only email + password + starting_point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("starting_point", "level", "estimate"),
    [("new", "A1", "A1.1"), ("some", "A2", "A2.1"), ("comfortable", "B1", "B1.1")],
)
def test_register_needs_only_email_password_and_a_starting_point(
    client: TestClient, db_session: Session, starting_point: str, level: str, estimate: str
) -> None:
    address = email()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": address, "password": PASSWORD, "starting_point": starting_point},
    )
    assert response.status_code == 201, response.text
    user = user_by_email(db_session, address)
    assert user.proficiency_level == level
    assert user.cefr_estimate == estimate
    assert user.native_language == "en"
    assert user.target_language == "fr"


def test_register_with_email_and_password_alone_still_works(
    client: TestClient, db_session: Session
) -> None:
    address = email()
    response = client.post("/api/v1/auth/register", json={"email": address, "password": PASSWORD})
    assert response.status_code == 201, response.text
    user = user_by_email(db_session, address)
    assert user.native_language == "en"
    assert user.proficiency_level == "beginner"


def test_an_explicit_level_from_an_older_client_wins_over_the_starting_point(
    client: TestClient, db_session: Session
) -> None:
    address = email()
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": address,
            "password": PASSWORD,
            "starting_point": "new",
            "proficiency_level": "B2",
            "native_language": "de",
        },
    )
    assert response.status_code == 201, response.text
    user = user_by_email(db_session, address)
    assert user.proficiency_level == "B2"
    assert user.native_language == "de"


def test_an_unknown_starting_point_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email(), "password": PASSWORD, "starting_point": "expert"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 2. Placement is offered after day 3, never at sign-up
# ---------------------------------------------------------------------------


def _completed_days(
    db: Session, user: User, count: int, *, band: str = "A1", met_unaided: bool = False
) -> None:
    already = db.query(DailyJourney).filter(DailyJourney.user_id == user.id).count()
    for index in range(already, already + count):
        journey = DailyJourney(
            user_id=user.id,
            local_date=date(2026, 3, 1) + timedelta(days=index),
            timezone="UTC",
            level_band=band,
            status="completed",
            completed_at=datetime(2026, 3, 1, 10, tzinfo=UTC) + timedelta(days=index),
            scenario_snapshot={},
            plan_selection={},
        )
        db.add(journey)
        db.flush()
        db.add(
            DailyJourneyStep(
                journey_id=journey.id,
                ordinal=0,
                kind="respond",
                status="completed",
                public_prompt={},
                private_task={
                    "result": {
                        "outcome": "met" if met_unaided else "partially_met",
                        "assistance_level": "none",
                    }
                },
            )
        )
    db.commit()


def test_nobody_is_offered_placement_at_sign_up(client: TestClient, db_session: Session) -> None:
    headers = register(client, email(), starting_point="comfortable")
    response = client.get("/api/v1/placement/offer", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"offer": False}


def test_after_three_days_a_learner_who_declared_some_french_is_offered_placement(
    client: TestClient, db_session: Session
) -> None:
    address = email()
    headers = register(client, address, starting_point="some")
    user = user_by_email(db_session, address)
    _completed_days(db_session, user, 2)
    assert client.get("/api/v1/placement/offer", headers=headers).json() == {"offer": False}
    _completed_days(db_session, user, 1)
    assert client.get("/api/v1/placement/offer", headers=headers).json() == {"offer": True}


def test_a_new_learner_is_offered_placement_only_when_their_days_say_so(
    db_session: Session, client: TestClient
) -> None:
    struggling_email, strong_email = email(), email()
    register(client, struggling_email, starting_point="new")
    register(client, strong_email, starting_point="new")
    struggling = user_by_email(db_session, struggling_email)
    strong = user_by_email(db_session, strong_email)
    _completed_days(db_session, struggling, 4, met_unaided=False)
    _completed_days(db_session, strong, 4, met_unaided=True)

    assert placement_offer(db_session, struggling) is False
    assert placement_offer(db_session, strong) is True
    assert journey_placement_evidence(db_session, strong)["above_band"] is True


def test_a_taken_or_declined_placement_is_never_offered_again(
    db_session: Session, client: TestClient
) -> None:
    address = email()
    register(client, address, starting_point="comfortable")
    user = user_by_email(db_session, address)
    _completed_days(db_session, user, 3)
    assert placement_offer(db_session, user) is True
    PlacementService(db_session).skip(user)
    assert placement_offer(db_session, user) is False


def test_journey_evidence_is_the_placement_prior(db_session: Session, client: TestClient) -> None:
    address = email()
    register(client, address, starting_point="new")
    user = user_by_email(db_session, address)
    assert opening_band(user) == "A1.2"
    _completed_days(db_session, user, 4, band="A2", met_unaided=True)
    user.cefr_estimate = "A2.1"
    db_session.commit()
    evidence = journey_placement_evidence(db_session, user)
    assert evidence["band"] == "A2"
    assert opening_band(user, evidence) == "A2.2"
    session = PlacementService(db_session).start(user)
    assert session.current_band == "A2.2"


# ---------------------------------------------------------------------------
# 3 + 4. The first day: authored, instant, the cast, zero provider calls
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("starting_point", "band"), [("new", "A1"), ("some", "A2"), ("comfortable", "A2")]
)
def test_the_first_journey_is_authored_instant_and_makes_no_provider_call(
    client: TestClient,
    db_session: Session,
    first_day_on: None,
    clock: Clock,
    provider_calls: ProviderCalls,
    monkeypatch: pytest.MonkeyPatch,
    starting_point: str,
    band: str,
) -> None:
    # The engine and the model are *on*: the first day must still not call them.
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True, raising=False)
    headers = register(client, email(), starting_point=starting_point)
    driver = Driver(client, headers, TZ, db=db_session)

    journey = driver.create(expect=(201,))

    assert provider_calls.calls == []
    assert journey["status"] == "active"
    assert journey["scenario"]["location_id"] == "le_mistral"
    assert journey["scenario"]["level_band"] == band
    kinds = [step["kind"] for step in journey["steps"]]
    assert kinds == ["scene", "recall", "recall", "respond", "resolution"]
    graded = [step for step in journey["steps"] if step["kind"] in ("recall", "respond")]
    assert len(graded) >= 3
    # Quick wins, not homework: required, and never typed.
    recalls = [step for step in journey["steps"] if step["kind"] == "recall"]
    assert all(not step["prompt"]["optional"] for step in recalls)
    assert {step["prompt"]["task_type"] for step in recalls} == {"choice", "tiles"}
    assert driver.private_leaks == []

    cast = journey["cast_intro"]
    assert [row["character_id"] for row in cast] == ["romy_tremblay", "marin_leveque", "lila_bonnet"]
    for row in cast:
        assert (CHARACTER_DIRS / row["character_id"]).is_dir()
        assert 0 < len(row["line_fr"].split()) <= journey_content.CAST_LINE_MAX_WORDS
        assert row["role_native"] and row["line_native"] and row["name"]

    stored = db_session.get(DailyJourney, uuid.UUID(journey["id"]))
    assert stored.plan_selection["first_day"]["kind"] == "first_day"
    assert stored.serial_episode_id is None, "day 1 is not a chapter of the living story"


def test_the_cast_speaks_to_the_learner_in_their_own_language(
    client: TestClient, db_session: Session, first_day_on: None, clock: Clock
) -> None:
    headers = register(client, email(), starting_point="new", native_language="de")
    journey = Driver(client, headers, TZ, db=db_session).create(expect=(201,))
    romy = journey["cast_intro"][0]
    assert romy["line_fr"] == "Salut ! Moi, c'est Romy."
    assert romy["line_native"] == "Hallo! Ich bin Romy."
    recall = next(step for step in journey["steps"] if step["kind"] == "recall")
    assert "Welcher" in recall["prompt"]["instruction_native"]


def test_a_first_day_is_playable_to_the_end_and_day_two_belongs_to_the_engine(
    client: TestClient,
    db_session: Session,
    first_day_on: None,
    clock: Clock,
    provider_calls: ProviderCalls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[dict[str, Any]] = []
    from app.tasks import journey_prefetch

    def fake_schedule(user: User, *, timezone_name: str | None, input_mode: InputMode, now=None):
        queued.append({"user_id": str(user.id), "tz": timezone_name, "mode": str(input_mode)})
        return None

    monkeypatch.setattr(journey_prefetch, "schedule_next_day_warmup", fake_schedule)
    address = email()
    headers = register(client, address, starting_point="new")
    driver = Driver(client, headers, TZ, db=db_session)
    driver.create(expect=(201,))
    driver.play(answer="Je voudrais un café au comptoir, s'il vous plaît.")
    finished = driver.finish()
    assert finished.status_code == 200, finished.text
    assert driver.journey["status"] == "completed"
    assert queued == [{"user_id": str(user_by_email(db_session, address).id), "tz": TZ, "mode": "text"}]

    # Day 2: the story engine's (spied: it answers "unavailable", and the
    # WP-69 authored stand-in covers the day). Not the first day again.
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    clock.moment = clock.moment + timedelta(days=1)
    before = list(provider_calls.calls)
    day_two = driver.create()
    assert provider_calls.calls[len(before):] == ["living_story.generate_scene"]
    assert day_two.get("cast_intro") is None
    stored = db_session.get(DailyJourney, uuid.UUID(day_two["id"]))
    assert "first_day" not in (stored.plan_selection or {})


def test_with_the_flag_off_the_first_day_is_the_old_first_day(
    client: TestClient, db_session: Session, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", False, raising=False)
    headers = register(client, email(), starting_point="new")
    journey = Driver(client, headers, TZ, db=db_session).create(expect=(201,))
    assert journey.get("cast_intro") is None
    assert not leaked_keys(journey)


# ---------------------------------------------------------------------------
# 5. The warm-up is queued for the next local day, behind the prefetch guards
# ---------------------------------------------------------------------------


def test_the_warm_up_waits_for_the_next_local_day() -> None:
    from app.tasks.journey_prefetch import next_day_warmup_eta

    evening_paris = datetime(2026, 3, 10, 21, 30, tzinfo=UTC)  # 22:30 in Paris
    eta = next_day_warmup_eta("Europe/Paris", now=evening_paris)
    # Paris midnight is 23:00 UTC, UTC midnight is later: the later one wins.
    assert eta == datetime(2026, 3, 11, 0, 10, tzinfo=UTC)
    tokyo = next_day_warmup_eta("Asia/Tokyo", now=datetime(2026, 3, 10, 20, 0, tzinfo=UTC))
    # Tokyo's next midnight (15:00 UTC on the 11th) is after UTC's.
    assert tokyo == datetime(2026, 3, 11, 15, 10, tzinfo=UTC)


def test_the_warm_up_is_never_queued_outside_the_prefetch_guards(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tasks import journey_prefetch

    sent: list[Any] = []
    monkeypatch.setattr(
        journey_prefetch.warm_learner_next_day,
        "apply_async",
        lambda *args, **kwargs: sent.append((args, kwargs)),
    )
    user = User(
        id=uuid.uuid4(), email=email(), hashed_password="x", native_language="en", target_language="fr"
    )
    # Engine off (the suite's default): nothing to prefetch, nothing queued.
    assert journey_prefetch.schedule_next_day_warmup(user, timezone_name=TZ) is None
    assert sent == []

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)
    eta = journey_prefetch.schedule_next_day_warmup(
        user, timezone_name=TZ, input_mode=InputMode.VOICE
    )
    assert eta is not None
    assert sent == [((), {"args": [str(user.id), "voice"], "eta": eta})]


# ---------------------------------------------------------------------------
# 6. Walk L9 — the respond step never prints its own answer
# ---------------------------------------------------------------------------


def test_a_line_that_speaks_the_expected_reply_is_detected() -> None:
    assert journey_content.line_spoils_reply(
        "Marin, tu vas demander à Lila ?", "Tu vas demander à Lila ?"
    )
    assert journey_content.line_spoils_reply(
        "Je voudrais un cafe au comptoir, s’il vous plait !",
        "Je voudrais un café au comptoir, s'il vous plaît.",
    )
    assert not journey_content.line_spoils_reply(
        "Alors, qu'est-ce que je vous sers ?",
        "Je voudrais un café au comptoir, s'il vous plaît.",
    )
    assert not journey_content.line_spoils_reply("Alors ?", "Alors ?")


def test_the_planner_replaces_a_respond_line_that_is_the_answer(db_session: Session) -> None:
    user = User(
        id=uuid.uuid4(),
        email=email(),
        hashed_password="x",
        native_language="en",
        target_language="fr",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    brief = journey_content.first_day_brief(db_session, user=user)
    assert not isinstance(brief, ContentUnavailable)
    from dataclasses import replace

    spoiled = replace(
        brief,
        opening_line_fr=brief.response_task.suggested_response_fr,
        response_task=replace(
            brief.response_task, opening_line_fr=brief.response_task.suggested_response_fr
        ),
    )
    plan = journey_planner.plan_journey(scenario=spoiled, candidates=[])
    respond = next(step for step in plan.steps if step.kind == "respond")
    scene = plan.steps[0]
    assert respond.public_prompt["character_line_fr"] == journey_planner.SPOILER_SAFE_OPENING_FR
    assert respond.private_task.opening_line_fr == journey_planner.SPOILER_SAFE_OPENING_FR
    assert scene.public_prompt["character_line_fr"] is None

    honest = journey_planner.plan_journey(scenario=brief, candidates=[])
    respond = next(step for step in honest.steps if step.kind == "respond")
    assert respond.public_prompt["character_line_fr"] == brief.response_task.opening_line_fr


def test_first_day_planning_keeps_two_new_words_and_makes_them_required(
    db_session: Session,
) -> None:
    user = User(
        id=uuid.uuid4(), email=email(), hashed_password="x", native_language="en",
        target_language="fr", cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    brief = journey_content.first_day_brief(db_session, user=user)
    candidates = journey_content.first_day_candidates(db_session, user=user, brief=brief)
    assert [c.target.label_fr for c in candidates] == ["un café", "s'il vous plaît"]
    assert all(isinstance(c, LearningCandidate) and c.is_new for c in candidates)

    ordinary = journey_planner.plan_journey(scenario=brief, candidates=candidates)
    assert sum(1 for step in ordinary.steps if step.kind == "recall") <= 1

    first = journey_planner.plan_journey(scenario=brief, candidates=candidates, first_day=True)
    recalls = [step for step in first.steps if step.kind == "recall"]
    assert len(recalls) == 2
    assert all(not step.optional for step in recalls)
    assert first.shape_reason == "first_day"
    # The catalogue rows are reused, never duplicated.
    again = journey_content.first_day_candidates(db_session, user=user, brief=brief)
    assert [c.target.id for c in again] == [c.target.id for c in candidates]
    assert all(c.target.kind is TargetKind.VOCABULARY for c in again)
    assert isinstance(again[0].target, TargetRef)


def test_placement_session_model_is_untouched_by_the_offer(db_session: Session) -> None:
    """Reading the offer writes nothing: no placement row appears."""

    user = User(
        id=uuid.uuid4(), email=email(), hashed_password="x", native_language="en",
        target_language="fr", proficiency_level="B1",
    )
    db_session.add(user)
    db_session.commit()
    assert placement_offer(db_session, user) is False
    assert db_session.query(PlacementSession).filter_by(user_id=user.id).count() == 0


def test_today_offers_the_cafe_the_first_day_will_serve(
    client: TestClient, db_session: Session, first_day_on: None, clock: Clock
) -> None:
    headers = register(client, email(), starting_point="new")
    driver = Driver(client, headers, TZ, db=db_session)
    today = driver.today()
    assert today["is_warm"] is True, "an authored first day is ready before it is asked for"
    offer = today["available"]
    journey = driver.create(expect=(201,))
    assert offer["scenario_key"] == journey["scenario"]["scenario_key"] == "order_at_cafe"
    assert offer["location_id"] == "le_mistral"
