"""WP-126 — an appropriate day one, and the placement after the first ending.

Review 2026-10-04 §2.1 F-1/F-2, owner decision 2:

* sign-up offers five plain-language starting points (A1 → C1); the three WP-75
  values still mean what they meant for an older client;
* the declaration is ``estimate_source: declared``, never «placement»;
* a B2 or C1 declaration gets B2/C1 content on day one (story, practice, letter);
* the placement is offered right after the first completed ending to a learner
  who declared more than «Nouveau» — with skip, resume and the manual re-run;
* a declined offer does not come back every day;
* own-band A1 success never makes an unsolicited offer: only days served *above*
  the learner's band, met unaided, on distinct days do;
* a placement closes out the scenes prefetched at the old band, never the day in
  progress.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.main import create_app
from app.schemas.user import STARTING_POINT_LEVELS, STARTING_POINTS
from app.services import journey_latency
from app.services import placement as placement_module
from app.services.journey_contracts import InputMode
from app.services.placement import (
    PlacementService,
    journey_placement_evidence,
    placement_offer,
    placement_offer_state,
    reconcile_after_placement,
)

PASSWORD = "securepass123"


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _email() -> str:
    return f"wp126-{uuid.uuid4().hex[:10]}@example.com"


def register(client: TestClient, address: str, **extra) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json={"email": address, "password": PASSWORD, **extra})
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": address, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def user_of(db: Session, address: str) -> User:
    return db.query(User).filter(User.email == address).one()


def completed_days(
    db: Session, user: User, count: int, *, band: str = "A1", met_unaided: bool = True, replies: int = 1,
    start: date = date(2026, 3, 1),
) -> None:
    already = db.query(DailyJourney).filter(DailyJourney.user_id == user.id).count()
    for index in range(already, already + count):
        journey = DailyJourney(
            user_id=user.id,
            local_date=start + timedelta(days=index),
            timezone="UTC",
            level_band=band,
            status="completed",
            completed_at=datetime(2026, 3, 1, 10, tzinfo=UTC) + timedelta(days=index),
            scenario_snapshot={},
            plan_selection={},
        )
        db.add(journey)
        db.flush()
        for ordinal in range(replies):
            db.add(
                DailyJourneyStep(
                    journey_id=journey.id,
                    ordinal=ordinal,
                    kind="respond",
                    status="completed",
                    public_prompt={},
                    private_task={
                        "result": {"outcome": "met" if met_unaided else "partially_met", "assistance_level": "none"}
                    },
                )
            )
    db.commit()


class FakeGrader:
    def generate_error_detection(self, messages, **kwargs):
        return SimpleNamespace(
            content=json.dumps(
                {
                    "score_0_4": 3.5,
                    "demonstrated_band": "C1.1",
                    "dimensions": {"range": 4, "accuracy": 3, "coherence": 4, "task": 3},
                    "evidence_fr": "réponse nuancée",
                    "off_task": False,
                }
            ),
            model="test-model",
            provider="test",
            prompt_tokens=90,
            completion_tokens=30,
            total_tokens=120,
            cost=0.0003,
        )


# ---------------------------------------------------------------------------
# 1. Five starting points; the legacy three unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("point", "level", "estimate", "target"),
    [
        ("new", "A1", "A1.1", "A1.2"),
        ("some", "A2", "A2.1", "A2.2"),
        ("comfortable", "B1", "B1.1", "B1.2"),
        ("confident", "B2", "B2.1", "B2.2"),
        ("advanced", "C1", "C1.1", "C1.2"),
    ],
)
def test_five_starting_points_cover_a1_to_c1(client, db_session, point, level, estimate, target):
    address = _email()
    headers = register(client, address, starting_point=point)
    user = user_of(db_session, address)
    assert (user.proficiency_level, user.cefr_estimate, user.cefr_target_level) == (level, estimate, target)
    cefr = client.get("/api/v1/progress/cefr", headers=headers).json()
    # A declaration is a declaration: never dressed as a measured placement.
    assert cefr["estimate_source"] == "declared"
    assert cefr["estimate"] == estimate


def test_the_scale_ends_at_c1_and_unknown_answers_are_refused(client):
    assert STARTING_POINTS == ("new", "some", "comfortable", "confident", "advanced")
    assert STARTING_POINT_LEVELS["advanced"] == "C1"
    for bad in ("C1+", "expert", "fluent"):
        response = client.post(
            "/api/v1/auth/register", json={"email": _email(), "password": PASSWORD, "starting_point": bad}
        )
        assert response.status_code == 422, bad


def test_a_legacy_three_option_payload_is_read_as_before(client, db_session):
    for point, level in (("new", "A1"), ("some", "A2"), ("comfortable", "B1")):
        address = _email()
        register(client, address, starting_point=point, native_language="de")
        assert user_of(db_session, address).proficiency_level == level


# ---------------------------------------------------------------------------
# 2. The offer: after the first ending, for non-beginners; never own-band A1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("point", ["some", "comfortable", "confident", "advanced"])
def test_the_offer_follows_the_first_completed_ending_for_non_beginners(client, db_session, point):
    address = _email()
    headers = register(client, address, starting_point=point)
    before = client.get("/api/v1/placement/offer", headers=headers).json()
    assert before == {"offer": False, "resume": False, "reason": "too_early"}
    completed_days(db_session, user_of(db_session, address), 1, met_unaided=False)
    after = client.get("/api/v1/placement/offer", headers=headers).json()
    assert after == {"offer": True, "resume": False, "reason": "declared"}


def test_own_band_a1_success_never_triggers_an_unsolicited_offer(client, db_session):
    address = _email()
    register(client, address, starting_point="new")
    user = user_of(db_session, address)
    # A whole window of perfect, unaided A1 days, several replies a day.
    completed_days(db_session, user, 5, band="A1", met_unaided=True, replies=3)
    evidence = journey_placement_evidence(db_session, user)
    assert evidence["met_unaided"] == 0 and evidence["above_band"] is False
    assert placement_offer_state(db_session, user) == {"offer": False, "resume": False, "reason": "beginner"}


def test_above_band_evidence_needs_distinct_days(client, db_session):
    address = _email()
    register(client, address, starting_point="new")
    user = user_of(db_session, address)
    # Many above-band replies on two days are still two days.
    completed_days(db_session, user, 2, band="A2", met_unaided=True, replies=4)
    evidence = journey_placement_evidence(db_session, user)
    assert evidence["met_unaided"] == 8 and evidence["qualifying_days"] == 2
    assert placement_offer(db_session, user) is False
    completed_days(db_session, user, 1, band="A2", met_unaided=True)
    assert placement_offer_state(db_session, user)["reason"] == "journey_evidence"


def test_band_order_is_explicit_not_a_string_comparison():
    assert placement_module.band_rank("A2") > placement_module.band_rank("A1")
    assert placement_module.band_rank("c1.1") == placement_module.band_rank("C1")
    assert placement_module.band_rank("") == -1
    assert placement_module.band_rank(None) == -1


# ---------------------------------------------------------------------------
# 3. Skip, resume, manual — and a declined offer does not nag
# ---------------------------------------------------------------------------


def test_a_declined_offer_does_not_come_back_on_later_days(client, db_session):
    address = _email()
    headers = register(client, address, starting_point="confident")
    user = user_of(db_session, address)
    completed_days(db_session, user, 1)
    assert client.get("/api/v1/placement/offer", headers=headers).json()["offer"] is True
    assert client.post("/api/v1/placement/skip", headers=headers).json()["status"] == "skipped"
    for _day in range(5):
        completed_days(db_session, user, 1)
        offer = client.get("/api/v1/placement/offer", headers=headers).json()
        assert offer == {"offer": False, "resume": False, "reason": "settled"}


def test_an_open_placement_is_offered_for_resuming_and_the_manual_rerun_stays(client, db_session, monkeypatch):
    monkeypatch.setattr(placement_module.PlacementService, "_get_llm_service", lambda self: FakeGrader())
    address = _email()
    headers = register(client, address, starting_point="advanced")
    user = user_of(db_session, address)
    completed_days(db_session, user, 1)
    started = client.post("/api/v1/placement/start", headers=headers, json={"restart": False}).json()
    assert started["status"] == "in_progress"
    assert client.get("/api/v1/placement/offer", headers=headers).json() == {
        "offer": True, "resume": True, "reason": "resume",
    }
    # Resuming hands back the same session, the same question.
    again = client.post("/api/v1/placement/start", headers=headers, json={"restart": False}).json()
    assert again["session_id"] == started["session_id"] and again["prompt"] == started["prompt"]
    client.post("/api/v1/placement/skip", headers=headers)
    assert client.get("/api/v1/placement/offer", headers=headers).json()["offer"] is False
    # Réglages: the voluntary re-run is always there, offer or not.
    manual = client.post("/api/v1/placement/start", headers=headers, json={"restart": True}).json()
    assert manual["status"] == "in_progress" and manual["prompt"]


def test_a_new_learner_can_always_take_the_placement_voluntarily(client, db_session):
    address = _email()
    headers = register(client, address, starting_point="new")
    assert client.get("/api/v1/placement/offer", headers=headers).json()["offer"] is False
    manual = client.post("/api/v1/placement/start", headers=headers, json={"restart": True}).json()
    assert manual["status"] == "in_progress"


def test_an_unassessed_placement_is_not_re_offered_every_morning(client, db_session):
    address = _email()
    register(client, address, starting_point="comfortable")
    user = user_of(db_session, address)
    completed_days(db_session, user, 1)
    db_session.add(PlacementSession(user_id=user.id, status="unassessed", turns=[], estimate={}))
    db_session.commit()
    completed_days(db_session, user, 1)
    assert placement_offer_state(db_session, user)["reason"] == "settled"


# ---------------------------------------------------------------------------
# 4. After the placement: prefetched work reconciled, the day in progress kept
# ---------------------------------------------------------------------------


def test_a_placement_closes_out_scenes_prefetched_at_the_old_band(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    monkeypatch.setattr(placement_module.PlacementService, "_get_llm_service", lambda self: FakeGrader())
    address = _email()
    headers = register(client, address, starting_point="comfortable")
    user = user_of(db_session, address)
    completed_days(db_session, user, 1)
    old_key = journey_latency.scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    assert old_key is not None
    stale = PilotEvent(
        user_id=user.id,
        event_type=journey_latency.PREFETCH_EVENT,
        entity_type=journey_latency.PREFETCH_ENTITY_TYPE,
        entity_id=old_key,
        payload={"cache_key": old_key, "brief": {}},
    )
    db_session.add(stale)
    # The day in progress, planned at the declared band.
    in_progress = DailyJourney(
        user_id=user.id, local_date=date(2026, 4, 1), timezone="UTC", level_band="B1", status="active",
        scenario_snapshot={}, plan_selection={},
    )
    db_session.add(in_progress)
    db_session.commit()

    session = client.post("/api/v1/placement/start", headers=headers, json={"restart": False}).json()
    for _ in range(8):
        if session["status"] != "in_progress":
            break
        session = client.post(
            f"/api/v1/placement/{session['session_id']}/respond",
            headers=headers,
            json={"answer": "À supposer que la réforme aboutisse, encore faudrait-il des moyens.",
                  "turn_index": session["prompt"]["index"]},
        ).json()
    assert session["status"] == "complete"
    db_session.refresh(user)
    assert user.cefr_estimate[:2] != "B1"
    discarded = db_session.query(PilotEvent).filter(
        PilotEvent.event_type == journey_latency.PREFETCH_DISCARDED_EVENT,
        PilotEvent.entity_id == str(stale.id),
    ).one()
    assert discarded.payload["reason"] == "placement"
    db_session.refresh(in_progress)
    assert (in_progress.level_band, in_progress.status) == ("B1", "active")
    # Idempotent: nothing left to close.
    assert reconcile_after_placement(db_session, user) == 0


def test_skip_is_recorded_once_and_a_service_skip_keeps_working(db_session, client):
    address = _email()
    register(client, address, starting_point="some")
    user = user_of(db_session, address)
    PlacementService(db_session).skip(user)
    assert db_session.query(PlacementSession).filter(PlacementSession.user_id == user.id).count() == 1


# ---------------------------------------------------------------------------
# 5. Day one at the declared band (story, practice, letter)
# ---------------------------------------------------------------------------


from tests import experience_walk as life  # noqa: E402
from tests import learner_walk as walk  # noqa: E402
from tests.test_learner_walk import (  # noqa: E402, F401 - fixtures
    assembled_client,
    clock,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: E402, F401 - fixture


@pytest.mark.parametrize(("persona_key", "band"), [("b2-en", "B2"), ("c1-de", "C1")])
def test_a_b2_or_c1_declaration_gets_its_own_band_on_day_one(
    persona_key, band, assembled_client, db_session, journey_enabled, clock, production_day  # noqa: F811
):
    persona = next(p for p in walk.PERSONAS if p.key == persona_key)
    assert life.STARTING_POINT[band] in {"confident", "advanced"}
    headers, _email_ = life.register_as_onboarding(assembled_client, persona)
    transcript = walk.play_day(
        assembled_client, db_session, headers, persona=persona, quality="strong", day=1, provider=production_day
    )
    assert transcript.get("error") is None, transcript.get("error")
    # The story is read at the declared band, not B1.1.
    assert str(transcript["learner_level"]).startswith(band)
    assert transcript["scenario"]["level_band"] == band
    # Practice: no beginner recognition item on a B2/C1 morning.
    kinds = {
        (event["step"].get("prompt") or {}).get("task_type")
        for event in transcript["events"]
        if event["step"].get("kind") == "recall"
    }
    assert "listen_tap" not in kinds
    # The letter's grammar is the declared band's.
    today = assembled_client.get("/api/v1/missions/today", headers=headers).json()
    letter = today.get("active_mission") or today.get("weekly_mission")
    assert letter, "a first letter is waiting"
    units = [o.get("external_id") for o in letter.get("objectives") or [] if o.get("kind") == "grammar"]
    assert units, letter.get("objectives")
    code = band.replace(".", "")
    assert all(f"_{code}" in str(unit) for unit in units), units


# ---------------------------------------------------------------------------
# 6. The life-walk checks fire on a bad record and stay quiet on a good one
# ---------------------------------------------------------------------------

from tests import walk_checks_wp126 as checks  # noqa: E402


def _life(level: str, days: list[dict]) -> dict:
    return {"persona": "x", "quality": "strong", "true_level": level, "days": days}


def _day(n: int, band: str, *, offer: dict | None = None, checks_: list | None = None, level: str | None = None) -> dict:
    return {
        "day": n,
        "journey": {"learner_level": level or band, "scenario": {"level_band": band}},
        "placement_offer": offer or {"offer": False},
        "band_check": checks_ or [],
    }


def test_walk_check_visit_items():
    good = _life("C1.1", [_day(1, "C1", checks_=[{"sub_band": "B2.2", "item_count": 24}, {"sub_band": "B2.1", "item_count": 24}])])
    bad = _life("C1.1", [_day(1, "C1", checks_=[{"sub_band": b, "item_count": 24} for b in ("B2.2", "B2.1", "B1.2")])])
    assert checks.check_band_check_visits(good) == []
    assert checks.check_band_check_visits(bad)


def test_walk_check_new_life_offer():
    own_band = _life("A1.1", [_day(n, "A1") for n in range(1, 5)] + [_day(5, "A1", offer={"offer": True, "reason": "journey_evidence"})])
    declared = _life("A1.1", [_day(1, "A1", offer={"offer": True, "reason": "declared"})])
    earned = _life("A1.1", [_day(n, "A2") for n in range(1, 4)] + [_day(4, "A2", offer={"offer": True, "reason": "journey_evidence"})])
    quiet = _life("A1.1", [_day(n, "A1") for n in range(1, 6)])
    assert checks.check_new_life_offer(own_band)
    assert checks.check_new_life_offer(declared)
    assert checks.check_new_life_offer(earned) == []
    assert checks.check_new_life_offer(quiet) == []
    assert checks.check_new_life_offer(_life("B1.1", [_day(1, "B1", offer={"offer": True, "reason": "declared"})])) == []


def test_walk_check_declared_day_one():
    assert checks.check_declared_day_one(_life("B2.1", [_day(1, "B2", level="B2.1")])) == []
    assert checks.check_declared_day_one(_life("C1.1", [_day(1, "B1", level="B1.1")]))
    assert checks.check_declared_day_one(_life("A2.1", [_day(1, "A1")])) == []
    assert checks.check_life_wp126(_life("C1.1", [_day(1, "C1", level="C1.1")])) == []
