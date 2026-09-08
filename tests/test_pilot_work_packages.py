from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.services.audio_session_service import AudioSessionService
from app.services.pilot_events import PilotEventService, format_daily_digest
from app.services.recommendation_reasons import recommendation_reason

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_pilot_daily_rollup_combines_activity_cost_and_failures(db_session):
    day = date(2026, 7, 23)
    occurred_at = datetime(2026, 7, 23, 9, 30, tzinfo=UTC)
    user = User(
        id=uuid4(),
        email="pilot-ledger@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.flush()
    thread = SerialThread(
        user_id=user.id,
        status="active",
        world_bible={},
        state={},
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="Épisode pilote",
        brief="Une scène.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "estimated_cost": {
                "story_generation_usd": 0.02,
                "image_generation_usd": 0.1,
                "total_estimated_usd": 0.12,
            },
        },
        recap_payload={},
        cache_key="pilot-ledger-scene",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
        created_at=occurred_at,
    )
    db_session.add(scene)
    service = PilotEventService(db_session)
    started = service.record("plan_started", user_id=user.id, entity_type="atelier")
    started.occurred_at = occurred_at
    crash = service.record("client_crash", user_id=user.id, entity_type="client", cost_usd=0.01)
    crash.occurred_at = occurred_at
    db_session.commit()

    report = service.daily_rollup(day, user_id=user.id)

    assert report["totals"] == {
        "learners": 1,
        "events": 2,
        "failures": 1,
        "cost_usd": 0.13,
    }
    assert report["users"][0]["events"] == {"client_crash": 1, "plan_started": 1}
    assert report["users"][0]["story_usd"] == 0.02
    assert report["users"][0]["image_usd"] == 0.1
    digest = format_daily_digest(report)
    assert "pilot-ledger@example.com" in digest
    assert "failures 1" in digest
    assert "$0.1300" in digest


def test_voice_call_updates_canonical_serial_relationship_memory(db_session):
    user = User(
        id=uuid4(),
        email="cast-call@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.flush()
    thread = SerialThread(
        user_id=user.id,
        status="active",
        world_bible={
            "cast": [
                {
                    "id": "romy_tremblay",
                    "name": "Romy",
                    "role": "journaliste",
                    "dynamic_with_user": "une complicité prudente",
                },
            ],
            "visual_design": {
                "characters": {
                    "romy_tremblay": {"accent_colour": "#1d3a8a"},
                },
            },
        },
        state={
            "relationships": {
                "romy_tremblay": {
                    "closeness": 1,
                    "register": "tu",
                    "callbacks": ["le café"],
                },
            },
        },
        news_seed={},
        current_episode_index=0,
    )
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=5,
        scenario="romy_tremblay",
        status="in_progress",
    )
    db_session.add_all([thread, session])
    db_session.flush()
    message = ConversationMessage(
        session_id=session.id,
        sender="user",
        content="Je peux venir demain après le travail.",
        sequence_number=1,
    )
    db_session.add(message)
    db_session.flush()

    result = AudioSessionService(db_session, initialize_llm=False).complete_serial_call(
        user=user,
        session=session,
        user_messages=[message],
    )
    db_session.commit()
    db_session.refresh(thread)

    relationship = thread.state["relationships"]["romy_tremblay"]
    assert result is not None
    assert relationship["closeness"] == 2
    assert relationship["register"] == "tu"
    assert "demain après le travail" in relationship["last_summary"]
    assert thread.state["voice_calls"][-1]["character_id"] == "romy_tremblay"


def test_recommendation_reasons_keep_the_named_personalization_signals():
    review = recommendation_reason(
        "review",
        bucket="fragile",
        lapses=3,
        retrievability=0.42,
    )
    mission = recommendation_reason(
        "mission",
        serial_thread_id="thread-1",
        target_errata_count=2,
    )
    panel = recommendation_reason(
        "panel_task",
        concept_id=18,
        target_vocabulary_count=1,
    )

    assert "fragile" in review["text"]
    assert review["signals"] == {
        "bucket": "fragile",
        "lapses": 3,
        "retrievability": 0.42,
    }
    assert mission["signals"]["serial_thread_id"] == "thread-1"
    assert panel["signals"] == {"concept_id": 18, "target_vocabulary_count": 1}


def test_onboarding_preferences_persist_to_the_user(client, db_session):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "onboarding-pilot@example.com",
            "password": "verysecure",
            "native_language": "en",
            "target_language": "fr",
            "learning_motivation": "travel",
            "speaking_comfort": "warming_up",
            "grammar_correction_level": "lenient",
            "daily_goal_minutes": 8,
        },
    )

    assert response.status_code == 201
    user = db_session.query(User).filter(User.email == "onboarding-pilot@example.com").one()
    assert user.learning_motivation == "travel"
    assert user.speaking_comfort == "warming_up"
    assert user.grammar_correction_level == "lenient"
    assert user.daily_goal_minutes == 8


def test_pilot_frontend_contracts_are_pinned():
    studio = _source("pages/audio-session.tsx")
    la_une = _source("components/laune/LaUne.tsx")
    epreuve = _source("components/epreuve/Epreuve.tsx")
    cahiers = _source("components/cahiers/Cahiers.tsx")
    review = _source("pages/vocabulary/review.tsx")
    mission = _source("pages/missions.tsx")
    feuilleton = _source("pages/graphic-novel.tsx")
    resilience = _source("lib/pilot-resilience.ts")
    auth = _source("lib/app-auth.tsx")
    app_shell = _source("pages/_app.tsx")
    settings = _source("pages/settings.tsx")

    for field in (
        "longestAnswerWords",
        "dueWordsReused",
        "producedWords",
        "tomorrowFocus",
        "turns",
    ):
        assert field in studio
    assert "Choose a scene" not in studio
    assert "box-shadow: 5px 5px 0" not in studio
    assert "pulseAppHaptic('complete')" in la_une
    assert "ep-motif-settle" in epreuve
    assert "nc-cta:active" in cahiers
    assert "recommendation_reason" in review
    assert "recommendation_reason" in mission
    assert "recommendation_reason" in feuilleton
    assert "episodic_anchor" in review
    # 2026-09-04: the deck reads its cache through pilot-resilience helpers; the
    # storage key lives there (with a 6 h TTL) rather than inline in the page.
    assert "readReviewContextCache" in review
    assert "REVIEW_CONTEXT_KEY = 'pilot:review-context:v1'" in _source("lib/pilot-resilience.ts")
    assert "pilot:mission-draft:" in mission
    assert "pilot:reader:" in feuilleton
    assert "pilot:resume:v1" in resilience
    assert "clearPilotResilience()" in auth
    assert "recordClientError" in app_shell
    assert "unhandledrejection" in app_shell
    assert "L’administration" in settings
    assert "Receive this edition on this device" not in settings

    # The card direction is derived from the langue d'appui, never hardcoded to
    # the German pair — an English native could not save this page at all while
    # it posted their stored fr_to_en into a German-only schema.
    assert "vocabDirectionOptions(settings.nativeLanguage)" in settings
    assert '<option value="fr_to_de">Français → allemand</option>' not in settings
    # Heading and button read the same words in the profile blocks, so the page
    # text showed "Modifier l’adresse" / "Modifier le mot de passe" twice each.
    assert settings.count("Modifier l’adresse") == 1
    assert settings.count("Modifier le mot de passe") == 1
    assert "Enregistrer la nouvelle adresse" in settings
    assert "Enregistrer le nouveau mot de passe" in settings
    # "Durée habituelle d'une séance" was a slider that no save ever sent and no
    # load ever read; the time budget above it is the real setting.
    assert "preferredSessionLength" not in settings
    # Tailwind palette literals kept light-mode panes under the dark theme.
    for raw_colour in ("bg-green-500", "bg-purple-600", "bg-blue-50", "bg-yellow-50", "bg-red-50"):
        assert raw_colour not in settings

    for leaked_copy in (
        "LOADING FEUILLETON",
        "Story moment",
        "Unfinished panel tasks",
        "OPEN NOTEBOOK",
        "Today's Thread",
    ):
        assert leaked_copy not in feuilleton


def test_auth_pages_speak_one_language_and_wear_the_soft_pill():
    signup = _source("pages/auth/signup.tsx")
    signin = _source("pages/auth/signin.tsx")
    forgot = _source("pages/auth/forgot-password.tsx")

    # Auth is instructional chrome, so it is English throughout. The onboarding
    # fieldset used to be a French island inside an otherwise English form.
    assert "Your first edition" in signup
    for french_island in (
        "Votre première édition",
        "Pourquoi le français ?",
        "Style de correction",
        "À l’oral",
        "Minutes par jour",
    ):
        assert french_island not in signup

    # Endonyms carry their own accents.
    assert "'Français'" in signup and "'Francais'" not in signup

    # Owner's soft-button direction: pills, sentence case, no offset slab.
    assert "border-radius: 999px" in signin
    assert "border-radius: 999px" in forgot
    assert "color: white" not in forgot

    # Theme-aware surfaces only: no fixed rgba() or hex on the auth paper.
    for page in (signup, signin, forgot):
        assert "rgba(20, 17, 13" not in page


def test_no_raw_german_labels_or_offset_shadows_in_journal_components():
    component_paths = [
        "components/laune/LaUne.tsx",
        "components/courrier/Courrier.tsx",
        "components/epreuve/Epreuve.tsx",
        "components/cahiers/Cahiers.tsx",
        "pages/atelier.tsx",
        "pages/missions.tsx",
        "pages/graphic-novel.tsx",
        "pages/notebook.tsx",
        "pages/audio-session.tsx",
    ]
    combined = "\n".join(_source(path) for path in component_paths)

    assert re.search(r"box-shadow:\s*[2-9]\d*px\s+[2-9]\d*px\s+0", combined) is None
    assert 'aria-label="Settings"' not in combined
    for raw_label in ("Gemeistert", "In Arbeit", "Ausbaufähig", ">Neu<"):
        assert raw_label not in combined


def test_testflight_lane_and_production_checklist_exist():
    fastfile = _source("fastlane/Fastfile")
    checklist = (ROOT / "docs" / "testflight-production-flip-checklist.md").read_text(encoding="utf-8")

    assert "lane :archive" in fastfile
    assert "lane :beta" in fastfile
    assert "upload_to_testflight" in fastfile
    assert "APP_ENV=production" in checklist
    assert "PASSWORD_RESET_BASE_URL" in checklist
    assert "APNS_USE_SANDBOX=false" in checklist
