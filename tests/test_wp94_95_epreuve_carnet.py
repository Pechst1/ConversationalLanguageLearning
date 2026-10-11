"""WP-94 «Numéro spécial» and WP-95 «Le Carnet» — the services/API half.

* a respond step completed with its objective met presses the scene's can-do
  (the authored café presses «commander au café»), first stamp only;
* a journey staged as an épreuve is graded server-side on completion: a pass
  records the checkpoint, stamps the épreuve's can-dos, closes the band and
  fires ``level_up`` once; a fail sets ``retry_after`` a week out;
* ``GET /api/v1/can-dos`` is the Carnet; Home's level line (``GET
  /progress/cefr`` and ``GET /atelier/today`` → ``cefr``) carries the next can-do.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models.cefr import UserCanDoStamp, UserLevelCheckpoint
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.services import can_do as can_do_service
from app.services import daily_journey as journey_module
from app.services import level_checkpoint as checkpoints
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    drive_to_finish,
    enabled,
    freeze,
    make_user,
)

CAFE_ANSWER = "Je voudrais un café en terrasse, s'il vous plaît."


def _service(db: Session) -> DailyJourneyService:
    return DailyJourneyService(db, build_default_adapters())


def _engine_scene(db: Session, user: User, script_payload: dict) -> GraphicNovelScene:
    scene = GraphicNovelScene(
        user_id=user.id,
        status="available",
        cadence="ad_hoc",
        title="Le Numéro spécial",
        brief="test",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload=script_payload,
        recap_payload={},
        cache_key=uuid.uuid4().hex,
        prompt_version="living-story-test",
        image_model="none",
        image_quality="low",
    )
    db.add(scene)
    db.commit()
    return scene


def _stage(monkeypatch: pytest.MonkeyPatch, scene: GraphicNovelScene) -> None:
    """The story agent's scene, as the pinned brief would name it."""

    monkeypatch.setattr(
        journey_module, "_journey_story_context", lambda journey: {"scene_id": str(scene.id)}
    )


def _ready(db: Session, user: User, band: str = "A1.1") -> None:
    checkpoints.mark_ready(db, user.id, band, now=datetime.now(UTC) - timedelta(days=1))
    db.commit()


# ---------------------------------------------------------------------------
# Contract reading and the grading rule
# ---------------------------------------------------------------------------


def test_the_scene_script_reads_the_engine_contract_defensively(db_session: Session) -> None:
    user = make_user(db_session, f"wp94-read-{uuid.uuid4().hex[:6]}@example.com")
    scene = _engine_scene(
        db_session,
        user,
        {
            "can_do_id": "CD_A11_GREET",
            "special": "epreuve",
            "epreuve": {
                "band": "A1.1",
                "can_do_ids": ["CD_A11_GREET", "CD_A11_ORDER_CAFE"],
                "attempt": 1,
                "pass_line_fr": "Bravo !",
                "fail_line_fr": "On se revoit la semaine prochaine.",
            },
        },
    )
    script = can_do_service.scene_script(db_session, {"scene_id": str(scene.id)})
    assert script["special"] == "epreuve" and script["can_do_id"] == "CD_A11_GREET"
    assert script["epreuve"]["can_do_ids"] == ["CD_A11_GREET", "CD_A11_ORDER_CAFE"]
    view = can_do_service.epreuve_snapshot_view(script["epreuve"], "de")
    assert view["band"] == "A1.1"
    assert view["can_dos"][1] == {
        "id": "CD_A11_ORDER_CAFE",
        "title_fr": "commander au café",
        "title_native": "im Café bestellen",
    }
    # Nothing, or garbage, reads as an ordinary day.
    assert can_do_service.scene_script(db_session, {})["special"] is None
    assert can_do_service.scene_script(db_session, {"scene_id": "not-a-uuid"})["epreuve"] is None
    # The brief's draft stands in while the scene row is not readable.
    draft = can_do_service.scene_script(db_session, {"draft": {"can_do_id": "CD_A11_PAY"}})
    assert draft["can_do_id"] == "CD_A11_PAY"


def test_the_epreuve_needs_the_objective_and_one_band_unit_used(db_session: Session) -> None:
    turns = [{"learner": CAFE_ANSWER, "correction": None}]
    passed = checkpoints.grade_epreuve(
        db_session, band="A1.1", can_do_ids=["CD_A11_ORDER_CAFE"], objective_met=True,
        turns=turns, concept_evidence=[],
    )
    assert passed["passed"] and "FR2_A11_JE_VOUDRAIS" in passed["units_used"]
    # Partially met is not a pass, whatever the grammar.
    assert not checkpoints.grade_epreuve(
        db_session, band="A1.1", can_do_ids=["CD_A11_ORDER_CAFE"], objective_met=False,
        turns=turns, concept_evidence=[],
    )["passed"]
    # The objective without any of the band's units is not a pass either.
    assert not checkpoints.grade_epreuve(
        db_session, band="A1.1", can_do_ids=["CD_A11_ORDER_CAFE"], objective_met=True,
        turns=[{"learner": "Bonjour.", "correction": None}], concept_evidence=[],
    )["passed"]
    # A corrected form is not a correct use.
    corrected = checkpoints.grade_epreuve(
        db_session, band="A1.1", can_do_ids=["CD_A11_ORDER_CAFE"], objective_met=True,
        turns=[{"learner": "je voudrais café", "correction": {"span_fr": "je voudrais café", "corrected_fr": "je voudrais un café"}}],
        concept_evidence=[],
    )
    assert "FR2_A11_JE_VOUDRAIS" not in corrected["units_used"]


# ---------------------------------------------------------------------------
# WP-95 — a met objective presses the scene's can-do
# ---------------------------------------------------------------------------


def test_the_authored_cafe_presses_commander_au_cafe_once(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    user = make_user(db_session, f"wp95-cafe-{uuid.uuid4().hex[:6]}@example.com")
    service = _service(db_session)
    freeze(monkeypatch, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    created, _ = service.create_journey(user, create_request())
    assert created.special is None and created.epreuve is None
    final = drive_to_finish(service, user, created, finish_kind="complete", answer=CAFE_ANSWER)
    assert final.recap.objective_outcome == "met"
    assert final.recap.can_dos_stamped == ["CD_A11_ORDER_CAFE"]
    assert final.recap.epreuve_result is None
    stamp = db_session.query(UserCanDoStamp).filter_by(user_id=user.id).one()
    assert stamp.source == "authored" and stamp.band == "A1.1"
    assert stamp.quote_fr == CAFE_ANSWER and stamp.journey_id == uuid.UUID(final.id)

    freeze(monkeypatch, datetime(2026, 9, 2, 9, 0, tzinfo=UTC))
    second, _ = service.create_journey(user, create_request())
    again = drive_to_finish(service, user, second, finish_kind="complete", answer=CAFE_ANSWER)
    assert again.recap.can_dos_stamped == [], "first stamp only"
    assert db_session.query(UserCanDoStamp).filter_by(user_id=user.id).count() == 1


def test_an_engine_scene_presses_its_can_do(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    user = make_user(db_session, f"wp95-engine-{uuid.uuid4().hex[:6]}@example.com")
    scene = _engine_scene(db_session, user, {"can_do_id": "CD_A11_LIKES"})
    _stage(monkeypatch, scene)
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    final = drive_to_finish(service, user, created, finish_kind="complete", answer=CAFE_ANSWER)
    assert final.recap.can_dos_stamped == ["CD_A11_LIKES"]
    stamp = db_session.query(UserCanDoStamp).filter_by(user_id=user.id).one()
    assert (stamp.source, stamp.scene_id) == ("scene", str(scene.id))
    assert can_do_service.stamped_can_do_ids(db_session, user.id) == {"CD_A11_LIKES"}


# ---------------------------------------------------------------------------
# WP-94 — checkpoint ready → staged → passed → level shown, level_up once
# ---------------------------------------------------------------------------


def _epreuve_payload(can_do_ids: list[str]) -> dict:
    return {
        "can_do_id": can_do_ids[0],
        "special": "epreuve",
        "epreuve": {
            "band": "A1.1",
            "can_do_ids": can_do_ids,
            "attempt": 1,
            "pass_line_fr": "Bravo, c'est le numéro spécial !",
            "fail_line_fr": "On se revoit la semaine prochaine.",
        },
    }


def test_a_passed_epreuve_closes_the_band_and_the_level_moves_once(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    user = make_user(db_session, f"wp94-pass-{uuid.uuid4().hex[:6]}@example.com")
    _ready(db_session, user)
    scene = _engine_scene(db_session, user, _epreuve_payload(["CD_A11_GREET", "CD_A11_ORDER_CAFE"]))
    _stage(monkeypatch, scene)
    service = _service(db_session)
    freeze(monkeypatch, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    created, _ = service.create_journey(user, create_request())
    assert created.special == "epreuve"
    assert [item.id for item in created.epreuve.can_dos] == ["CD_A11_GREET", "CD_A11_ORDER_CAFE"]
    assert created.epreuve.band == "A1.1"

    final = drive_to_finish(service, user, created, finish_kind="complete", answer=CAFE_ANSWER)
    recap = final.recap
    assert recap.epreuve_result == "passed"
    assert recap.epreuve_line_fr == "Bravo, c'est le numéro spécial !"
    assert set(recap.can_dos_stamped) == {"CD_A11_GREET", "CD_A11_ORDER_CAFE"}
    row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A1.1").one()
    assert row.status == "passed" and row.attempts == 1 and row.source == "epreuve"
    assert recap.level == "A1.2"
    assert recap.level_up is not None
    assert (recap.level_up.from_level, recap.level_up.to_level) == ("A1.1", "A1.2")
    sources = {s.source for s in db_session.query(UserCanDoStamp).filter_by(user_id=user.id)}
    assert sources == {"epreuve"}

    # The next day is ordinary, and the move is not shown again.
    monkeypatch.setattr(journey_module, "_journey_story_context", lambda journey: {})
    freeze(monkeypatch, datetime(2026, 9, 2, 9, 0, tzinfo=UTC))
    second, _ = service.create_journey(user, create_request())
    day2 = drive_to_finish(service, user, second, finish_kind="complete", answer=CAFE_ANSWER)
    assert day2.recap.level == "A1.2" and day2.recap.level_up is None
    assert day2.recap.epreuve_result is None


def test_a_failed_epreuve_waits_a_week_without_a_level_move(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    user = make_user(db_session, f"wp94-fail-{uuid.uuid4().hex[:6]}@example.com")
    _ready(db_session, user)
    scene = _engine_scene(db_session, user, _epreuve_payload(["CD_A11_ORDER_CAFE"]))
    _stage(monkeypatch, scene)
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    final = drive_to_finish(service, user, created, finish_kind="complete", answer="Bonjour.")
    assert final.recap.epreuve_result == "failed"
    assert final.recap.epreuve_line_fr == "On se revoit la semaine prochaine."
    assert final.recap.level_up is None and final.recap.can_dos_stamped == []
    row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A1.1").one()
    assert row.status == "failed" and row.retry_after is not None
    retry = row.retry_after if row.retry_after.tzinfo else row.retry_after.replace(tzinfo=UTC)
    assert timedelta(days=6, hours=23) < retry - datetime.now(UTC) <= timedelta(days=7)


def test_an_epreuve_the_state_machine_refuses_claims_no_verdict(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    user = make_user(db_session, f"wp94-locked-{uuid.uuid4().hex[:6]}@example.com")
    scene = _engine_scene(db_session, user, _epreuve_payload(["CD_A11_ORDER_CAFE"]))
    _stage(monkeypatch, scene)
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    final = drive_to_finish(service, user, created, finish_kind="complete", answer=CAFE_ANSWER)
    assert final.recap.epreuve_result is None
    assert db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A1.1").count() == 0


# ---------------------------------------------------------------------------
# The Carnet API and Home's level line
# ---------------------------------------------------------------------------


def _login(client, native: str = "de") -> tuple[dict[str, str], str]:
    email = f"wp95-api-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "target_language": "fr",
            "native_language": native,
            "proficiency_level": "A1",
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}, email


def test_the_carnet_and_homes_next_can_do(client, db_session: Session) -> None:
    headers, email = _login(client)
    user = db_session.query(User).filter(User.email == email).one()
    can_do_service.stamp_can_do(
        db_session, user.id, "CD_A11_GREET", source="scene", scene_id="s-1",
        scene_title_fr="Le comptoir", character_id="margaux", quote_fr="Bonjour, je suis Paul.",
    )
    db_session.commit()

    carnet = client.get("/api/v1/can-dos", headers=headers)
    assert carnet.status_code == 200
    body = carnet.json()
    assert body["current_band"] == "A1.1"
    assert [band["band"] for band in body["bands"]][:2] == ["A1.1", "A1.2"]
    assert sum(len(band["can_dos"]) for band in body["bands"]) == 72  # + 14 C1 can-dos (2026-10-03)
    greet = body["bands"][0]["can_dos"][0]
    assert greet["id"] == "CD_A11_GREET" and greet["title_native"] == "jemanden begrüßen und sich vorstellen"
    assert greet["stamped_at"] and greet["source"] == "scene" and greet["character_id"] == "margaux"
    assert greet["quote_fr"] == "Bonjour, je suis Paul." and greet["scene_title_fr"] == "Le comptoir"
    assert body["bands"][0]["can_dos"][1]["stamped_at"] is None

    cefr = client.get("/api/v1/progress/cefr", headers=headers).json()
    assert cefr["next_can_do"] == {
        "id": "CD_A11_ORDER_CAFE",
        "title_fr": "commander au café",
        "title_native": "im Café bestellen",
        "band": "A1.1",
    }
    assert (cefr["can_dos_stamped"], cefr["can_dos_total"]) == (1, 8)


def test_the_checkpoint_view_says_whether_a_story_stages_the_epreuve(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False)
    view = checkpoints.checkpoint_view("A1.1", None, coverage_met=False, now=datetime.now(UTC))
    assert view["staged_in_story"] is False
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    assert checkpoints.checkpoint_view("A1.1", None, coverage_met=False, now=datetime.now(UTC))["staged_in_story"]


# ---------------------------------------------------------------------------
# WP-94 harness honesty — the Rappel's coach mini-scene, and avoidance
# ---------------------------------------------------------------------------


def _strong_brief(external_id: str = "FR2_A11_JE_VOUDRAIS") -> dict:
    return {
        "concept_id": 4242,
        "external_id": external_id,
        "title_fr": "je voudrais",
        "title_native": "I would like",
        "stability": 12.0,
    }


def test_a_strong_units_rappel_is_the_coachs_mini_scene_credited_as_free_use() -> None:
    from app.core.srs.memory import EvidenceFormat, format_for_name
    from app.services.daily_journey import _recall_task_from_json, _recall_task_to_json
    from app.services.grammar_items import review_band, review_item
    from app.services.journey_contracts import AssistanceLevel, AttemptAnswer, InputMode
    from app.services.journey_learning import coach_scene_review_task, evaluate_recall

    brief = _strong_brief()
    assert review_band(brief["stability"]) == "high"
    assert review_item(brief, sentences=[], language="en", day_key="d") is None, "before: nothing posed"
    task = coach_scene_review_task(brief, language="de", day_key="2026-09-29")
    assert task is not None and task.task_type == "short_answer"
    assert task.prompt_fr and "«" in task.prompt_fr and task.instruction_native.endswith("“")
    assert task.evidence_format == "conversation"
    assert format_for_name(task.evidence_format) is EvidenceFormat.PRODUCE
    # The reply is never printed in the prompt (no spoil).
    assert task.solution_fr not in task.prompt_fr
    # It survives the private-task round trip, and a plain task still reads as before.
    assert _recall_task_from_json(_recall_task_to_json(task)).evidence_format == "conversation"
    assert "evidence_format" not in _recall_task_to_json(
        _recall_task_from_json({**_recall_task_to_json(task), "evidence_format": None})
    )
    evaluation = evaluate_recall(
        None, user=None, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=task.solution_fr),
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.outcome == "met"
    assert evaluation.observations[0].task_format == "conversation"
    # Deterministic per day; a unit without bank templates poses nothing.
    assert coach_scene_review_task(brief, language="de", day_key="2026-09-29") == task
    assert coach_scene_review_task(_strong_brief("FR2_UNKNOWN"), language="en", day_key="d") is None


def test_measured_avoidance_slows_the_harness_hold() -> None:
    from app.core.srs.rhythm_horizon import simulate_rhythm_horizon

    bands = [("A1.1", 12, 60), ("A1.2", 12, 60)]

    def held(avoidance: float) -> tuple[int, int]:
        run = simulate_rhythm_horizon(
            "regulier", 0.9, bands=bands, seance_seconds=540, seance_graded=8, days=90, avoidance=avoidance
        )
        return len(run.bands_closed), run.days[-1].percent

    assert held(0.0) >= held(0.5) >= held(1.0)
    assert held(0.0) > held(1.0), "a learner who always avoids the form is never held"


def test_the_avoidance_rate_is_measured_from_concept_evidence(db_session: Session) -> None:
    from app.services.journey_learning import measured_avoidance_rate

    view = measured_avoidance_rate(db_session)
    assert set(view) == {"correct", "error", "avoided", "total", "rate"}
    assert view["rate"] is None or 0.0 <= view["rate"] <= 1.0


# ---------------------------------------------------------------------------
# WP-94 — the special edition is announced on the offer, before Start
# ---------------------------------------------------------------------------


def test_the_offered_scenario_announces_the_epreuve_before_start(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from app.config import settings

    user = make_user(db_session, f"wp94-offer-{uuid.uuid4().hex[:6]}@example.com", native_language="de")
    service = _service(db_session)
    # Nothing is due yet: an ordinary offer.
    before = service.get_today(user)
    assert before.available is not None
    assert before.available.special is None and before.available.epreuve is None

    _ready(db_session, user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    offered = service._offered_epreuve(user)
    assert offered["special"] == "epreuve"
    epreuve = offered["epreuve"]
    assert epreuve["band"] == "A1.1", "the band the épreuve closes"
    assert 2 <= len(epreuve["can_dos"]) <= 3
    assert all(item["id"].startswith("CD_A11_") and item["title_native"] for item in epreuve["can_dos"])

    # Wired into the envelope: `available` carries it (the offer itself is stubbed
    # here — the engine's own offer needs a story thread).
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False)
    monkeypatch.setattr(DailyJourneyService, "_offered_epreuve", lambda self, user: offered)
    today = service.get_today(user)
    assert today.available.special == "epreuve"
    assert today.available.epreuve.band == "A1.1"
    assert today.model_dump(mode="json")["available"]["epreuve"]["can_dos"][0]["title_native"]


def test_no_epreuve_is_offered_without_the_story_engine_or_readiness(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    user = make_user(db_session, f"wp94-nooffer-{uuid.uuid4().hex[:6]}@example.com")
    service = _service(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    assert service._offered_epreuve(user) == {"special": None, "epreuve": None}, "not ready"
    _ready(db_session, user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False)
    assert service._offered_epreuve(user) == {"special": None, "epreuve": None}, "engine off"


def test_the_planner_poses_the_coach_scene_the_learning_adapter_attached() -> None:
    from app.services.journey_learning import _with_coach_scene
    from app.services.journey_planner import _coach_scene_task

    weak = {**_strong_brief(), "stability": 4.0}
    assert "coach_scene" not in _with_coach_scene(weak, language="en")
    brief = _with_coach_scene(_strong_brief(), language="en")
    task = _coach_scene_task(brief)
    assert task is not None and task.evidence_format == "conversation"
    assert task.target.kind == "grammar" and task.target.id == "4242"
    assert _coach_scene_task(_strong_brief()) is None
