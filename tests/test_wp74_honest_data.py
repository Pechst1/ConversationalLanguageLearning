"""WP-74 — honest data: graders, vocabulary, word counts, cost rows, export."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import story_correspondence as courrier
from app.services.analytics import AnalyticsService, acquired_word_count
from app.services.gdpr_export import (
    CHILD_TABLES,
    EXCLUDED_USER_TABLES,
    export_learner_records,
    user_linked_tables,
)
from app.services.lexical_coverage import known_word_set
from app.services.llm_service import LLMResult
from app.services.missions import (
    MISSION_LLM_COST_EVENT_TYPE,
    MissionCorrectionService,
    MissionDebriefService,
    MissionSRSService,
    is_polluted_mission_word,
)
from app.services.story_visualization import StoryVisualizationService


def _user(db_session, *, native: str = "en", email: str | None = None) -> User:
    user = User(
        email=email or f"{uuid4()}@example.com",
        hashed_password=get_password_hash("wp74-secure"),
        target_language="fr",
        native_language=native,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _mission(user: User) -> RealWorldMission:
    return RealWorldMission(
        user_id=user.id,
        cadence="ad_hoc",
        mission_type="message",
        title="Le colis",
        brief="Répondez au livreur.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[
            {"id": "real_world_task", "label": "Répondre", "target_count": 1, "kind": "communication", "required": True}
        ],
        prompt_payload={"messenger": {"quick_replies": ["Bonjour, je vous écris pour..."]}},
        recap_payload={},
    )


class _NoLLM:
    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        from app.services.llm_service import LLMProviderError

        raise LLMProviderError("grader down")


class _PricedLLM:
    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-correction",
            content=json.dumps(
                {
                    "verdict": "accepted",
                    "score_0_4": 4,
                    "corrected_answer": "Bonjour, j'arrive demain.",
                    "objective_progress": [],
                    "concept_hits": [],
                    "missing_targets": [],
                    "errata": [],
                    "vocabulary_links": [],
                }
            ),
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.0123,
            raw_response={},
        )


# -- 1. the Courrier grader --------------------------------------------------


def test_grader_outage_is_unassessed_not_accepted(db_session) -> None:
    user = _user(db_session)
    mission = _mission(user)
    correction = MissionCorrectionService(db_session, llm_service=_NoLLM()).correct_submission(
        user=user, mission=mission, text="Bonjour, je suis chez moi demain matin, merci beaucoup.", mode="writing"
    )
    assert correction["verdict"] == "unassessed"
    assert correction["verdict"] != "accepted"
    progress = correction["objective_progress"]
    assert progress and all(item["met"] is False and item["assessed"] is False for item in progress)
    # The story neither rewards nor punishes a letter nobody read.
    by_id = {item["id"]: item for item in progress}
    assert courrier.outcome_from_objectives(objectives=mission.objectives, progress_by_id=by_id) == "partial"


def test_debrief_says_unassessed_instead_of_a_score(db_session) -> None:
    user = _user(db_session)
    mission = _mission(user)
    correction = MissionCorrectionService(db_session, llm_service=_NoLLM()).correct_submission(
        user=user, mission=mission, text="Bonjour, je suis chez moi demain matin, merci beaucoup.", mode="writing"
    )
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id, user_id=user.id, mode="writing", answer_payload={"text": "x"},
        correction_payload=correction, verdict=correction["verdict"], score_0_4=0,
    )
    recap = MissionDebriefService().build(
        mission=mission, attempts=[attempt], turns=[], errata_count=0, srs_result={"saved_count": 0}
    )
    assert recap["measured"]["assessed"] is False
    assert recap["objective_results"][0]["assessed"] is False
    assert "pas encore corrigée" in recap["branch_outcome"]["label"].lower()


def test_empty_answer_still_needs_revision(db_session) -> None:
    user = _user(db_session)
    correction = MissionCorrectionService(db_session, llm_service=_NoLLM()).correct_submission(
        user=user, mission=_mission(user), text="   ", mode="writing"
    )
    assert correction["verdict"] == "needs_revision"


# -- 2. mission vocabulary -----------------------------------------------------


def test_missions_never_create_placeholder_or_uncorrected_vocabulary(db_session) -> None:
    user = _user(db_session)
    mission = _mission(user)
    db_session.add(mission)
    db_session.flush()
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id,
        user_id=user.id,
        mode="writing",
        answer_payload={"text": "une photo de mon porte hier"},
        correction_payload={"verdict": "unassessed", "corrected_answer": "une photo de mon porte hier", "errata": []},
        verdict="unassessed",
        score_0_4=0,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(mission)
    before = db_session.query(VocabularyWord).count()

    result = MissionSRSService(db_session).seed_phrase_bank(user=user, mission=mission)
    db_session.commit()

    assert result["saved_count"] == 0
    assert db_session.query(VocabularyWord).count() == before
    assert not db_session.query(VocabularyWord).filter(VocabularyWord.word.like("%mon porte%")).count()


def test_corrected_catalogue_word_is_queued_without_a_fake_review(db_session) -> None:
    user = _user(db_session)
    word = VocabularyWord(language="fr", word="la porte", normalized_word="la porte", english_translation="the door")
    db_session.add(word)
    mission = _mission(user)
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "le porte"},
            correction_payload={
                "verdict": "needs_revision",
                "errata": [{"learner_text": "le porte", "corrected_target": "la porte", "task_error_type": "gender"}],
            },
            verdict="needs_revision",
            score_0_4=2,
        )
    )
    db_session.commit()
    db_session.refresh(mission)

    result = MissionSRSService(db_session).seed_phrase_bank(user=user, mission=mission)
    db_session.commit()

    assert result["saved_count"] == 1
    assert result["phrase_bank"][0]["translation"] == "the door"
    progress = db_session.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id
        )
    ).one()
    assert progress.state == "new"
    assert not (progress.correct_count or 0)
    assert not (progress.times_used_correctly or 0)


def test_gloss_must_be_in_the_learners_language(db_session) -> None:
    user = _user(db_session, native="de")
    db_session.add(VocabularyWord(language="fr", word="la clé", normalized_word="la cle", english_translation="the key"))
    mission = _mission(user)
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id, user_id=user.id, mode="writing", answer_payload={"text": "le clé"},
            correction_payload={"verdict": "partial", "vocabulary_links": [{"target": "la clé", "translation": "key"}]},
            verdict="partial", score_0_4=3,
        )
    )
    db_session.commit()
    db_session.refresh(mission)
    assert MissionSRSService(db_session).seed_phrase_bank(user=user, mission=mission)["saved_count"] == 0


def test_polluted_rows_are_recognised() -> None:
    assert is_polluted_mission_word(
        SimpleNamespace(topic_tags=["real_world"], english_translation="Polished mission dispatch")
    )
    assert is_polluted_mission_word(SimpleNamespace(topic_tags=["mission_phrase"], english_translation="x"))
    assert not is_polluted_mission_word(SimpleNamespace(topic_tags=["core"], english_translation="the door"))


def test_cleanup_script_dry_run_changes_nothing(db_session) -> None:
    from scripts.cleanup_mission_vocabulary import cleanup

    db_session.add(
        VocabularyWord(
            language="fr", word="Je vous remercie par avance...", normalized_word="je vous remercie par avance wp74",
            english_translation="Reusable opening or reply fragment", topic_tags=["mission_phrase"],
        )
    )
    db_session.commit()
    before = db_session.query(VocabularyWord).count()
    report = cleanup(db_session, apply=False)
    assert report["polluted_words"] >= 1
    assert db_session.query(VocabularyWord).count() == before
    cleanup(db_session, apply=True)
    assert not any(is_polluted_mission_word(word) for word in db_session.query(VocabularyWord).all())


# -- 3. «Mots acquis» ----------------------------------------------------------


def test_releve_and_dossier_count_the_same_words(db_session) -> None:
    user = _user(db_session)
    now = datetime.now(UTC)
    for surface, reps in (("wpmota", 6), ("wpmotb", 6), ("wpmotc", 0)):
        word = VocabularyWord(language="fr", word=surface, normalized_word=surface, english_translation="w")
        db_session.add(word)
        db_session.flush()
        db_session.add(
            UserVocabularyProgress(
                user_id=user.id,
                word_id=word.id,
                state="review" if reps else "new",
                reps=reps,
                lapses=0,
                stability=400.0 if reps else None,
                last_review_date=now - timedelta(days=1) if reps else None,
                proficiency_score=95 if reps else 0,
            )
        )
    db_session.commit()

    summary = AnalyticsService(db_session).get_user_summary(user=user)
    dossier = known_word_set(db_session, user=user)
    assert summary["words_mastered"] == dossier.nailed_count == acquired_word_count(db_session, user=user)
    assert summary["words_mastered"] == 2  # the scheduler never writes "mastered"; this used to be 0


# -- 4. cost rows ----------------------------------------------------------------


def test_mission_llm_call_writes_a_cost_row(db_session) -> None:
    user = _user(db_session)
    mission = _mission(user)
    db_session.add(mission)
    db_session.flush()
    MissionCorrectionService(db_session, llm_service=_PricedLLM()).correct_submission(
        user=user, mission=mission, text="Bonjour, j'arrive demain.", mode="writing"
    )
    db_session.commit()
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == MISSION_LLM_COST_EVENT_TYPE)
    ).all()
    assert len(rows) == 1 and abs(rows[0].cost_usd - 0.0123) < 1e-9
    assert rows[0].payload["purpose"] == "correction"


def test_story_image_writes_a_cost_row(db_session, monkeypatch) -> None:
    user = _user(db_session)
    service = StoryVisualizationService(db_session, user_id=user.id)
    monkeypatch.setattr(type(service), "api_key", property(lambda self: "sk-test"), raising=False)

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):  # type: ignore[no-untyped-def]
            return {"data": [{"url": "https://example.test/image.png"}]}

    class _Client:
        async def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return _Response()

    monkeypatch.setattr(type(service), "client", property(lambda self: _Client()), raising=False)
    url = asyncio.run(service._call_dalle("a door"))
    assert url.endswith("image.png")
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == "story_image_cost")
    ).all()
    assert len(rows) == 1 and rows[0].cost_usd > 0


# -- 5. GDPR export --------------------------------------------------------------


def test_every_user_linked_table_is_exported_or_excluded_with_a_reason() -> None:
    tables = user_linked_tables()
    for required in (
        "journal_entries", "real_world_missions", "real_world_mission_turns", "learner_artefacts",
        "rehearsals", "serial_threads", "placement_sessions", "daily_journeys",
    ):
        assert required in tables and required not in EXCLUDED_USER_TABLES
    for name, reason in EXCLUDED_USER_TABLES.items():
        assert name in tables and reason.strip()
    assert set(CHILD_TABLES) >= {"conversation_messages", "daily_journey_steps"}


def test_export_carries_only_this_learners_rows_and_no_secrets(db_session) -> None:
    me = _user(db_session)
    other = _user(db_session)
    db_session.add_all(
        [
            PilotEvent(user_id=me.id, event_type="wp74_mine", payload={}),
            PilotEvent(user_id=other.id, event_type="wp74_theirs", payload={}),
        ]
    )
    db_session.commit()
    export = export_learner_records(db_session, user_id=me.id)
    events = export["tables"]["pilot_events"]["rows"]
    assert {row["event_type"] for row in events} == {"wp74_mine"}
    assert "refresh_tokens" not in export["tables"]
    assert "hash" not in json.dumps(export["tables"]).lower()
    json.dumps(export)  # serialisable


def test_export_endpoint_includes_learner_records(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "wp74-export@example.com", "password": "wp74-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "wp74-export@example.com", "password": "wp74-secure"}
    ).json()["access_token"]
    response = client.get("/api/v1/users/me/export", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    records = response.json()["learner_records"]
    assert "excluded" in records and "refresh_tokens" in records["excluded"]


# -- 6. email change ------------------------------------------------------------------


def test_email_change_duplicate_check_ignores_case(client: TestClient, db_session) -> None:
    _user(db_session, email="Taken.WP74@Example.com")
    client.post(
        "/api/v1/auth/register",
        json={"email": "mover-wp74@example.com", "password": "wp74-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "mover-wp74@example.com", "password": "wp74-secure"}
    ).json()["access_token"]
    response = client.patch(
        "/api/v1/users/me/email",
        json={"current_password": "wp74-secure", "new_email": "  taken.wp74@example.COM "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
