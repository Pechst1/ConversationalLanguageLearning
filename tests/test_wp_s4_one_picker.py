# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-S4 — La Forge: one engine, one picker, one day.

* One picker: ``forge_picker.forge_plan`` is read by the séance start, the
  Atelier's ``select_today``, the generation context and the journey; the old
  ``select_daily_concepts`` and the pad-to-three are gone.
* The intake quota holds across both surfaces: two simulated weeks per rhythm,
  the journey's Règle and the forge each day, in both orders — new rules a
  week equal the rhythm's quota.
* The chosen rule is always seated: an in-progress séance no longer overrides
  ``preferred_concept_id``; it is parked and comes back on a bare start.
* The day: Soutenu and Intensif fold a forge step into the Scène movement,
  inside the budget; Léger and Régulier get «Forge today's rule» after the day.
* Time: a folded block is the forge step's segment; an after-day block counts
  towards the day's measured time.
* End to end: introduced in the journey → forged → held, and the level's
  coverage recomputed when a forge block completes.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.atelier import AtelierSession
from app.db.models.daily_journey import DailyJourney
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.schemas.daily_journey import ForgePrompt, ForgeStep
from app.services import concept_life, forge_picker
from app.services import journey_planner as planner
from app.services.grammar import GrammarService, apply_grammar_evidence
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.journey_contracts import StepKind
from app.services.journey_day_shapes import DayShapeInputs
from app.services.journey_events import forge_after_day_seconds
from tests.test_journey_end_to_end import (
    Driver,
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
)
from tests.test_journey_planner import _brief

ROOT = Path(__file__).resolve().parents[1]
DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
RHYTHM_MINUTES = {"leger": 5, "regulier": 10, "soutenu": 20, "intensif": 30}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def v2(monkeypatch, db_session: Session):
    """The v2 syllabus (rule cards for every unit); v1 is restored afterwards."""

    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    yield
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


def _learner(db: Session, *, minutes: int = 10) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp-s4-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.1",
        daily_goal_minutes=minutes,
    )
    db.add(user)
    db.commit()
    return user


def _progress(db: Session, user: User, concept_id: int) -> UserGrammarProgress | None:
    db.expire_all()
    return (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept_id)
        .first()
    )


def _forge(db: Session, user: User, now: datetime, *, free_use: bool = True) -> forge_picker.ForgePlan:
    """One forge block, graded as all correct (mock grading). Every unit gets
    one item through the one evidence door WP-S3's composer writes through."""

    plan = forge_picker.forge_plan(db, user, now)
    for unit in plan.units:
        progress = GrammarService(db).get_or_create_progress(user_id=user.id, concept_id=unit.concept_id)
        fmt = EvidenceFormat.PRODUCE if unit.role == "today" and free_use else EvidenceFormat.RECOGNISE
        apply_grammar_evidence(progress, Evidence(fmt, correct=True), now=now, score=8.0)
        db.add(progress)
    db.flush()
    return plan


def _journey_intake(db: Session, user: User, now: datetime) -> int | None:
    """The journey's Règle: today's new rule from the quota, read (introduced)."""

    brief = concept_life.introduction_for_today(db, user, now=now, control_language="en")
    if brief is None:
        return None
    concept_life.mark_introduced(db, user=user, concept_id=int(brief["concept_id"]), now=now)
    db.flush()
    return int(brief["concept_id"])


# ---------------------------------------------------------------------------
# 1. One picker
# ---------------------------------------------------------------------------


def test_select_daily_concepts_and_the_pad_to_three_are_gone() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "app").rglob("*.py")
        if re.search(r"(def |\.)select_daily_concepts\b", path.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders
    endpoint = (ROOT / "app/api/v1/endpoints/atelier.py").read_text(encoding="utf-8")
    assert "fallback_concepts" not in endpoint, "the séance start pads from teaching order again"
    assert "select_today(current_user)" not in endpoint.split("def start_session", 1)[1].split("\n@router", 1)[0]


@pytest.mark.parametrize(
    "module",
    [
        "app/api/v1/endpoints/atelier.py",  # the séance start
        "app/services/atelier.py",  # AtelierScheduler.select_today (today's edition, pregeneration)
        "app/services/exercise_generation.py",  # the generation context
    ],
)
def test_every_surface_reads_the_one_picker(module: str) -> None:
    assert re.search(r"\bforge_plan\b", (ROOT / module).read_text(encoding="utf-8")), module


def test_the_journey_reads_the_same_picker() -> None:
    source = (ROOT / "app/services/daily_journey.py").read_text(encoding="utf-8")
    assert "forge_anchor_id" in source and "forge_anchor_brief" in source
    # The picker's quota step is the journey's own intake (one new-concept picker).
    picker = (ROOT / "app/services/forge_picker.py").read_text(encoding="utf-8")
    assert "introduction_due" in picker and "next_new_concepts" in picker


def test_the_anchor_order(db_session: Session, v2) -> None:
    user = _learner(db_session)
    # A new learner: today's rule is the quota's new rule, the same one the
    # journey's Règle would introduce.
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    plan = forge_picker.forge_plan(db_session, user, DAY0)
    assert plan.reason == forge_picker.REASON_NEW_FROM_QUOTA
    assert plan.anchor.concept_id == brief["concept_id"] == plan.new_concept_id
    assert [unit.role for unit in plan.units] == ["today"], "no padding from teaching order"

    # Once the Règle is read, it is the rule introduced today.
    concept_life.mark_introduced(db_session, user=user, concept_id=brief["concept_id"], now=DAY0)
    plan = forge_picker.forge_plan(db_session, user, DAY0 + timedelta(hours=1))
    assert (plan.anchor.concept_id, plan.reason) == (brief["concept_id"], forge_picker.REASON_INTRODUCED_TODAY)
    assert plan.new_concept_id is None

    # The learner's own choice beats everything.
    other = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr", GrammarConcept.id != brief["concept_id"])
        .first()
    )
    chosen = forge_picker.forge_plan(db_session, user, DAY0, preferred_concept_id=other.id)
    assert chosen.pairs()[0] == (other.id, "today") and chosen.reason == forge_picker.REASON_PREFERRED


def test_due_and_contrast_never_bring_a_new_rule(db_session: Session, v2) -> None:
    user = _learner(db_session, minutes=20)
    concepts = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr")
        .order_by(GrammarConcept.difficulty_order, GrammarConcept.id)
        .limit(4)
        .all()
    )
    for concept in concepts[:3]:
        db_session.add(
            UserGrammarProgress(
                user_id=user.id, concept_id=concept.id, score=5.0, reps=2, stability=2.0,
                introduced_at=DAY0 - timedelta(days=10), next_review=DAY0 - timedelta(days=1),
            )
        )
    db_session.commit()
    plan = forge_picker.forge_plan(db_session, user, DAY0)
    introduced = {concept.id for concept in concepts[:3]}
    new_units = [unit for unit in plan.units if unit.concept_id not in introduced]
    assert all(unit.role == "today" for unit in new_units), plan
    assert len(new_units) <= 1, "at most one new rule, and only as today's"
    assert {unit.concept_id for unit in plan.units if unit.role == "due"} <= introduced
    roles = [unit.role for unit in plan.units]
    assert roles == sorted(roles, key=["today", "due", "contrast"].index)


# ---------------------------------------------------------------------------
# 2. The intake quota holds across both surfaces
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rhythm", list(RHYTHM_MINUTES))
@pytest.mark.parametrize("forge_first", [False, True], ids=["journey-then-forge", "forge-then-journey"])
def test_new_rules_a_week_equal_the_rhythm_quota(db_session: Session, v2, rhythm: str, forge_first: bool) -> None:
    user = _learner(db_session, minutes=RHYTHM_MINUTES[rhythm])
    quota = concept_life.NEW_CONCEPTS_PER_WEEK[rhythm]
    for offset in range(14):
        now = DAY0 + timedelta(days=offset)
        if forge_first:
            _forge(db_session, user, now)
            _journey_intake(db_session, user, now + timedelta(minutes=30))
        else:
            _journey_intake(db_session, user, now)
            _forge(db_session, user, now + timedelta(minutes=30))
    db_session.commit()
    stamps = sorted(
        (value if value.tzinfo else value.replace(tzinfo=UTC))
        for (value,) in db_session.query(UserGrammarProgress.introduced_at)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.introduced_at.isnot(None))
        .all()
    )
    week_one = [stamp for stamp in stamps if stamp < DAY0 + timedelta(days=7)]
    week_two = [stamp for stamp in stamps if DAY0 + timedelta(days=7) <= stamp < DAY0 + timedelta(days=14)]
    assert len(week_one) == quota, (rhythm, stamps)
    assert len(week_two) == quota, (rhythm, stamps)


# ---------------------------------------------------------------------------
# 3. The chosen rule is always seated
# ---------------------------------------------------------------------------


def _headers(client: TestClient) -> dict[str, str]:
    email = f"wp-s4-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "forge-secure-1", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "forge-secure-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_a_request_for_another_rule_parks_the_open_seance_and_seats_it(client: TestClient, db_session: Session) -> None:
    headers = _headers(client)
    first = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert first.status_code == 201, first.text
    first_id = first.json()["session_id"]
    seated = first.json()["concepts"][0]["id"]
    other = (
        db_session.query(GrammarConcept)
        .filter(
            GrammarConcept.active.is_(True),
            GrammarConcept.language == "fr",
            GrammarConcept.external_id.isnot(None),
            GrammarConcept.id != seated,
        )
        .first()
    )

    chosen = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": other.id})
    assert chosen.status_code == 201, chosen.text
    assert chosen.json()["session_id"] != first_id
    assert chosen.json()["concepts"][0]["id"] == other.id, "the chosen rule leads"
    assert chosen.json()["quote"]["forge"]["reason"] == "preferred"
    db_session.expire_all()
    assert db_session.get(AtelierSession, uuid.UUID(first_id)).status == "parked"

    again = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": other.id})
    assert again.json()["session_id"] == chosen.json()["session_id"], "the same rule resumes, never restarts"
    bare = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert bare.json()["session_id"] == chosen.json()["session_id"]

    done = client.post(f"/api/v1/atelier/sessions/{chosen.json()['session_id']}/complete", headers=headers)
    assert done.status_code == 200, done.text
    resumed = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert resumed.json()["session_id"] == first_id, "the parked séance comes back"


# ---------------------------------------------------------------------------
# 4. The day: folded on Soutenu / Intensif, after the day on Léger / Régulier
# ---------------------------------------------------------------------------


def _plan(budget: int, *, forge: dict | None, introduction: dict | None = None):
    plan = planner.plan_journey(
        scenario=_brief(), candidates=[], budget_seconds=budget, practice=True,
        dice=DayShapeInputs(user_id=f"forge-{budget}", local_date=DAY0.date()),
        introduction=introduction, forge=forge,
    )
    plan.validate()
    return plan


@pytest.mark.parametrize("rhythm", ["soutenu", "intensif"])
def test_soutenu_and_intensif_fold_the_forge_into_the_scene_movement(db_session: Session, v2, rhythm: str) -> None:
    from app.services.daily_journey import DailyJourneyService

    user = _learner(db_session, minutes=RHYTHM_MINUTES[rhythm])
    budget = {"soutenu": 1200, "intensif": 1800}[rhythm]
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    forge = DailyJourneyService(db_session, adapters=None)._forge_for_today(user, brief)
    assert forge is not None and forge["concept_id"] == brief["concept_id"]

    plan = _plan(budget, forge=forge, introduction=brief)
    kinds = [step.kind for step in plan.steps]
    assert kinds.count(StepKind.FORGE) == 1, plan.rationale
    forge_at = kinds.index(StepKind.FORGE)
    assert kinds.index(StepKind.RULE) < forge_at < kinds.index(StepKind.RESPOND), "after the guided items"
    guided_after_rule = kinds[kinds.index(StepKind.RULE) + 1 : forge_at]
    assert guided_after_rule and set(guided_after_rule) == {StepKind.RECALL}
    step = plan.steps[forge_at]
    assert planner.FORGE_MIN_SECONDS <= step.estimated_seconds <= forge_picker.FORGE_SECONDS[rhythm]
    assert plan.estimated_active_seconds <= budget, "the fold fits the day's budget"
    assert step.public_prompt["concept_id"] == brief["concept_id"]
    ForgeStep.model_validate(
        {
            "id": "x", "ordinal": step.ordinal, "status": "pending", "estimated_seconds": step.estimated_seconds,
            "prompt": {**step.public_prompt, "href": "/atelier?mode=forge", "forged": False},
        }
    )


@pytest.mark.parametrize("rhythm", ["leger", "regulier"])
def test_leger_and_regulier_keep_the_forge_after_the_day(db_session: Session, v2, rhythm: str) -> None:
    from app.services.daily_journey import DailyJourneyService

    user = _learner(db_session, minutes=RHYTHM_MINUTES[rhythm])
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    assert DailyJourneyService(db_session, adapters=None)._forge_for_today(user, brief) is None
    budget = {"leger": 300, "regulier": 600}[rhythm]
    plan = _plan(budget, forge=None, introduction=brief)
    assert StepKind.FORGE not in [step.kind for step in plan.steps]
    entry = DailyJourneyService(db_session, adapters=None)._forge_entry(user)
    assert entry.folded is False
    assert entry.href.startswith("/atelier?mode=forge")
    assert entry.budget_seconds == forge_picker.FORGE_SECONDS[rhythm]


def test_a_forge_step_needs_room() -> None:
    forge = {"concept_id": 7, "title_native": "x", "title_fr": "", "reserve_seconds": 0, "max_seconds": 420}
    assert planner._forge_step(3, forge=forge, introduction=None, room=planner.FORGE_MIN_SECONDS - 1) is None
    step = planner._forge_step(3, forge=forge, introduction=None, room=900)
    assert step is not None and step.estimated_seconds == 420


def test_the_forge_step_may_only_sit_before_the_reply() -> None:
    from dataclasses import replace

    forge = {"concept_id": None, "reserve_seconds": 240, "max_seconds": 420}
    plan = _plan(1200, forge=forge)
    kinds = [step.kind for step in plan.steps]
    assert StepKind.FORGE in kinds
    steps = [step for step in plan.steps if step.kind is not StepKind.FORGE]
    moved = [*steps[:-1], plan.steps[kinds.index(StepKind.FORGE)], steps[-1]]
    moved = [replace(step, ordinal=index) for index, step in enumerate(moved)]
    with pytest.raises(ValueError, match="before the reply"):
        replace(plan, steps=moved).validate()
    with pytest.raises(ValueError, match="practice day"):
        replace(plan, practice=False).validate()


def test_the_soutenu_day_serves_the_forge_step_and_returns_to_it(
    assembled_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    email = f"wp-s4-fold-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    user = db_session.get(User, learner_id(db_session, email))
    user.daily_goal_minutes = 20
    db_session.commit()
    driver = Driver(assembled_client, headers, db=db_session)
    journey = driver.create()
    assert journey["budget_seconds"] == 1200
    assert journey["estimated_active_seconds"] <= 1200
    forges = [step for step in journey["steps"] if step["kind"] == "forge"]
    assert len(forges) == 1, [step["kind"] for step in journey["steps"]]
    prompt = ForgePrompt.model_validate(forges[0]["prompt"])
    assert prompt.href.startswith("/atelier?mode=forge") and f"step={forges[0]['id']}" in prompt.href
    assert prompt.forged is False

    for _ in range(80):
        step = driver.current()
        if step is None or step["kind"] == "forge":
            break
        if step["kind"] == "recall":
            driver.attempt(driver.recall_answer(step, correct=True))
            if driver.journey.get("current_step_id") == step["id"]:
                driver.advance()
        else:
            driver.advance()
    assert driver.current()["kind"] == "forge"

    started = assembled_client.post(
        "/api/v1/atelier/sessions",
        headers=headers,
        json={
            "preferred_concept_id": prompt.concept_id,
            "origin": "journey",
            "budget_seconds": prompt.budget_seconds,
            "journey_step_id": forges[0]["id"],
        },
    )
    assert started.status_code == 201, started.text
    forge_payload = started.json()["quote"]["forge"]
    assert forge_payload["origin"] == "journey" and forge_payload["journey_step_id"] == forges[0]["id"]
    assert forge_payload["budget_seconds"] == prompt.budget_seconds
    done = assembled_client.post(f"/api/v1/atelier/sessions/{started.json()['session_id']}/complete", headers=headers)
    assert done.status_code == 200, done.text

    driver.journey = driver.today()["journey"]
    back = next(step for step in driver.journey["steps"] if step["kind"] == "forge")
    assert back["prompt"]["forged"] is True
    driver.advance()
    assert driver.current()["kind"] != "forge"


def test_the_envelope_names_the_forge_per_rhythm(
    assembled_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    email = f"wp-s4-env-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    driver = Driver(assembled_client, headers, db=db_session)
    envelope = driver.client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": "UTC"}).json()
    assert envelope["forge"]["folded"] is False
    assert envelope["forge"]["href"].startswith("/atelier?mode=forge")
    user = db_session.get(User, learner_id(db_session, email))
    user.daily_goal_minutes = 30
    db_session.commit()
    envelope = driver.client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": "UTC"}).json()
    assert envelope["forge"]["folded"] is True


# ---------------------------------------------------------------------------
# 5. Time: the after-day forge counts towards the day
# ---------------------------------------------------------------------------


def test_after_day_forge_minutes_count_towards_the_day(db_session: Session) -> None:
    user = _learner(db_session)
    finished = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    journey = DailyJourney(
        user_id=user.id, local_date=finished.date(), timezone="UTC", status="completed",
        budget_seconds=600, completed_at=finished,
    )
    db_session.add(journey)

    def block(start_after: int, minutes: int, *, step_id: str | None = None, budget: int = 300) -> None:
        start = finished + timedelta(minutes=start_after)
        db_session.add(
            AtelierSession(
                user_id=user.id, selected_concept_ids=[], status="completed", recap_payload={},
                quote_payload={"forge": {"budget_seconds": budget, "origin": "after_day", "journey_step_id": step_id}},
                started_at=start, created_at=start, completed_at=start + timedelta(minutes=minutes),
            )
        )

    block(5, 4)  # counted: 240 s
    block(20, 30)  # counted, capped at twice its plan: 600 s
    block(40, 3, step_id=str(uuid.uuid4()))  # folded into a step: already the journey's
    db_session.commit()
    assert forge_after_day_seconds(db_session, journey_id=journey.id) == 240 + 600


# ---------------------------------------------------------------------------
# 6. End to end: introduced in the journey → forged → held → the level shows it
# ---------------------------------------------------------------------------


def test_introduced_in_the_journey_forged_and_held(client: TestClient, db_session: Session, v2) -> None:
    from app.services.level_coverage import held_unit_ids

    user = _learner(db_session)
    concept_id = _journey_intake(db_session, user, DAY0)
    assert concept_id is not None
    assert concept_life.concept_stage(_progress(db_session, user, concept_id)) == concept_life.STAGE_INTRODUCED

    # Day 0 — the after-day forge works on the rule the day introduced.
    plan = _forge(db_session, user, DAY0 + timedelta(hours=1))
    assert plan.pairs()[0] == (concept_id, "today") and plan.reason == forge_picker.REASON_INTRODUCED_TODAY
    assert concept_life.concept_stage(_progress(db_session, user, concept_id)) == concept_life.STAGE_PRACTISING

    # Then — the rule keeps coming back through the picker (as a due rule)
    # until it is held: a second free use a week on, a spaced item after two.
    seen_on: list[int] = []
    for offset in range(1, 61):
        now = DAY0 + timedelta(days=offset, hours=1)
        progress = _progress(db_session, user, concept_id)
        if progress.held_at is not None:
            break
        plan = forge_picker.forge_plan(db_session, user, now)
        if concept_id not in plan.concept_ids:
            continue
        seen_on.append(offset)
        free_use, _spaced = concept_life.held_conditions(progress)
        fmt = EvidenceFormat.PRODUCE if offset >= 7 and not free_use else EvidenceFormat.RECOGNISE
        apply_grammar_evidence(progress, Evidence(fmt, correct=True), now=now, score=8.0)
        db_session.flush()
    db_session.commit()
    progress = _progress(db_session, user, concept_id)
    assert progress.held_at is not None, seen_on
    assert concept_life.concept_stage(progress) == concept_life.STAGE_HELD
    assert concept_id in held_unit_ids(db_session, user)

    # Completing a forge block recomputes the level: Home's «A1.1 · x %».
    token_user = db_session.get(User, user.id)
    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token(str(token_user.id), auth_version=int(token_user.auth_version or 0))}"}
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": concept_id})
    assert started.status_code == 201, started.text
    done = client.post(f"/api/v1/atelier/sessions/{started.json()['session_id']}/complete", headers=headers)
    assert done.status_code == 200, done.text
    db_session.expire_all()
    coverage = (db_session.get(User, user.id).cefr_estimate_payload or {}).get("coverage") or {}
    assert coverage.get("units", {}).get("held", 0) >= 1, coverage
