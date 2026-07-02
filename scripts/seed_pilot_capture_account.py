"""Seed a deterministic signed-in account for mobile pilot visual captures."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401 - register SQLAlchemy models before use
from app.db.models.atelier import AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.progress import UserVocabularyProgress
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.db.session import SessionLocal
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.serial import SerialThreadService


VOCABULARY_FIXTURES = [
    {
        "word": "le radiateur",
        "normalized_word": "radiateur",
        "german_translation": "der Heizkoerper",
        "english_translation": "the radiator",
        "example_sentence": "Le radiateur ne marche plus depuis hier.",
        "example_translation": "The radiator has not worked since yesterday.",
        "topic_tags": ["housing", "repair"],
    },
    {
        "word": "un creneau",
        "normalized_word": "creneau",
        "german_translation": "ein Terminfenster",
        "english_translation": "a time slot",
        "example_sentence": "Vous avez un creneau cette semaine ?",
        "example_translation": "Do you have a slot this week?",
        "topic_tags": ["scheduling", "repair"],
    },
    {
        "word": "confirmer",
        "normalized_word": "confirmer",
        "german_translation": "bestaetigen",
        "english_translation": "to confirm",
        "example_sentence": "Je peux confirmer ma disponibilite.",
        "example_translation": "I can confirm my availability.",
        "topic_tags": ["planning"],
    },
    {
        "word": "disponible",
        "normalized_word": "disponible",
        "german_translation": "verfuegbar",
        "english_translation": "available",
        "example_sentence": "Je suis disponible jeudi matin.",
        "example_translation": "I am available on Thursday morning.",
        "topic_tags": ["planning"],
    },
]

CONCEPT_EXTERNAL_IDS = ("FR_B1_COND_001", "FR_B1_TENSE_001", "FR_A2_NEG_001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _due_at(days: int = 1) -> datetime:
    return datetime.combine(date.today() - timedelta(days=days), time(hour=9), tzinfo=timezone.utc)


def _ensure_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise SystemExit(f"No user found for {email}. Register/login before seeding.")
    user.full_name = user.full_name or "Mobile Capture"
    user.native_language = "de"
    user.target_language = "fr"
    user.proficiency_level = "A2"
    user.cefr_estimate = "A2.1"
    user.cefr_target_level = "B1.1"
    user.daily_goal_minutes = 15
    user.new_words_per_day = 8
    user.theme = "light"
    user.font_size = "medium"
    user.serial_onboarding_seen = False
    user.serial_edition_notifications = True
    user.total_xp = max(int(user.total_xp or 0), 320)
    user.level = max(int(user.level or 1), 4)
    user.current_streak = max(int(user.current_streak or 0), 3)
    user.longest_streak = max(int(user.longest_streak or 0), 5)
    user.last_activity_date = date.today() - timedelta(days=1)
    db.add(user)
    db.flush()
    return user


def _ensure_word(db: Session, payload: dict[str, Any]) -> VocabularyWord:
    word = (
        db.query(VocabularyWord)
        .filter(
            VocabularyWord.language == "fr",
            VocabularyWord.normalized_word == payload["normalized_word"],
        )
        .first()
    )
    if not word:
        word = VocabularyWord(language="fr", word=payload["word"], normalized_word=payload["normalized_word"])
        db.add(word)
    word.word = payload["word"]
    word.part_of_speech = "verb" if payload["word"] == "confirmer" else "noun"
    word.german_translation = payload["german_translation"]
    word.english_translation = payload["english_translation"]
    word.example_sentence = payload["example_sentence"]
    word.example_translation = payload["example_translation"]
    word.difficulty_level = 2
    word.topic_tags = payload["topic_tags"]
    db.flush()
    return word


def _seed_vocabulary(db: Session, user: User) -> list[VocabularyWord]:
    words = [_ensure_word(db, payload) for payload in VOCABULARY_FIXTURES]
    now = _now()
    due = _due_at()
    for index, word in enumerate(words):
        progress = (
            db.query(UserVocabularyProgress)
            .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
            .first()
        )
        if not progress:
            progress = UserVocabularyProgress(user_id=user.id, word_id=word.id)
            db.add(progress)
        progress.scheduler = "fsrs"
        progress.state = "review" if index < 2 else "learning"
        progress.phase = "review" if index < 2 else "learn"
        progress.reps = max(int(progress.reps or 0), 2 + index)
        progress.correct_count = max(int(progress.correct_count or 0), 1 + index)
        progress.incorrect_count = max(int(progress.incorrect_count or 0), 1 if index == 0 else 0)
        progress.proficiency_score = 42 + index * 9
        progress.last_review_date = now - timedelta(days=2 + index)
        progress.next_review_date = due + timedelta(hours=index)
        progress.due_at = due + timedelta(hours=index)
        progress.due_date = date.today() - timedelta(days=1 if index < 3 else 0)
        progress.times_seen = max(int(progress.times_seen or 0), 2 + index)
        progress.times_used_correctly = max(int(progress.times_used_correctly or 0), 1)
        progress.deck_name = "Pilot capture"
        db.add(progress)
    db.flush()
    return words


def _seed_concepts(db: Session, user: User) -> list[GrammarConcept]:
    concepts = FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=False)
    by_external = {concept.external_id: concept for concept in concepts if concept.external_id}
    selected = [by_external[external_id] for external_id in CONCEPT_EXTERNAL_IDS if external_id in by_external]
    if not selected:
        selected = (
            db.query(GrammarConcept)
            .filter(GrammarConcept.language == "fr", GrammarConcept.active.is_(True))
            .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
            .limit(3)
            .all()
        )
    if not selected:
        fallback = GrammarConcept(
            external_id="FR_PILOT_CAPTURE_001",
            language="fr",
            name="Pilot conditionals",
            level="A2",
            category="Tenses",
            subskill="Conditionnel present",
            core_rule="Use the conditional to make a polite request.",
            active=True,
        )
        db.add(fallback)
        db.flush()
        selected = [fallback]

    now = _now()
    for index, concept in enumerate(selected[:3]):
        progress = (
            db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
            .first()
        )
        if not progress:
            progress = UserGrammarProgress(user_id=user.id, concept_id=concept.id)
            db.add(progress)
        progress.score = 3.5 + index
        progress.reps = max(int(progress.reps or 0), 1 + index)
        progress.state = "ausbaufahig" if index == 0 else "in_arbeit"
        progress.notes = "Pilot capture seed: visible due concept."
        progress.last_review = now - timedelta(days=3 + index)
        progress.next_review = _due_at(index + 1)
        db.add(progress)
    db.flush()
    return selected[:3]


def _target_vocabulary(words: list[VocabularyWord]) -> list[dict[str, Any]]:
    return [
        {
            "word_id": word.id,
            "word": word.word,
            "translation": word.german_translation or word.english_translation,
            "example": word.example_sentence,
            "reason": "Pilot capture target vocabulary",
        }
        for word in words[:3]
    ]


def _seed_errata(db: Session, user: User, concepts: list[GrammarConcept], words: list[VocabularyWord]) -> list[UserError]:
    concept = concepts[0] if concepts else None
    word = words[0] if words else None
    existing = (
        db.query(UserError)
        .filter(UserError.user_id == user.id, UserError.memory_key == "pilot-capture-politeness-conditionnel")
        .first()
    )
    if not existing:
        existing = UserError(user_id=user.id, memory_key="pilot-capture-politeness-conditionnel")
        db.add(existing)
    existing.concept_id = concept.id if concept else None
    existing.linked_word_id = word.id if word else None
    existing.error_category = "grammar"
    existing.subcategory = "polite_request"
    existing.display_label = "Polite repair request"
    existing.original_text = "Vous pouvez venir demain ?"
    existing.correction = "Pourriez-vous venir demain ?"
    existing.context_snippet = "A landlord repair message needs a softer conditional request."
    existing.why_wrong = "The direct present tense is understandable but too abrupt for the situation."
    existing.repair_hint = "Use pourriez-vous + infinitive."
    existing.source_type = "pilot_capture"
    existing.review_mode = "grammar"
    existing.state = "review"
    existing.reps = max(int(existing.reps or 0), 1)
    existing.occurrences = max(int(existing.occurrences or 0), 2)
    existing.next_review_date = _due_at()
    db.add(existing)
    db.flush()
    return [existing]


def _ensure_atelier_session(
    db: Session,
    user: User,
    concepts: list[GrammarConcept],
    words: list[VocabularyWord],
) -> AtelierSession:
    session = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == "in_progress")
        .order_by(AtelierSession.created_at.desc())
        .first()
    )
    concept_ids = [concept.id for concept in concepts[:3]]
    if not session:
        session = AtelierSession(user_id=user.id, status="in_progress", selected_concept_ids=concept_ids)
        db.add(session)
    session.selected_concept_ids = concept_ids
    session.quote_payload = {
        "text": "Faire simple, puis precis.",
        "author": "Atelier pilot",
        "target_vocabulary_ids": [word.id for word in words[:3]],
        "target_vocabulary": _target_vocabulary(words),
    }
    session.recap_payload = {}
    db.add(session)
    db.flush()
    return session


def _mission_payload(words: list[VocabularyWord]) -> dict[str, Any]:
    return {
        "mission_format": "chat_message",
        "conversation_opening": "Bonjour, dites-moi ce qui ne fonctionne pas exactement.",
        "target_vocabulary": _target_vocabulary(words),
        "placeholder": "Write the message you would send.",
        "quick_replies": [
            "Le radiateur ne marche plus.",
            "Pourriez-vous proposer un creneau ?",
            "Je suis disponible jeudi matin.",
        ],
        "contact": {
            "contact_name": "Camille",
            "contact_role": "landlord",
            "contact_initials": "CA",
            "presence": "available now",
        },
    }


def _ensure_mission(
    db: Session,
    user: User,
    words: list[VocabularyWord],
    *,
    title: str,
    cadence: str,
    serial_thread_id: Any | None = None,
    episode_index: int | None = None,
    status: str = "in_progress",
) -> RealWorldMission:
    mission = (
        db.query(RealWorldMission)
        .filter(RealWorldMission.user_id == user.id, RealWorldMission.title == title)
        .first()
    )
    if not mission:
        mission = RealWorldMission(user_id=user.id, title=title, brief="")
        db.add(mission)
    mission.status = status
    mission.cadence = cadence
    mission.mission_type = "message"
    mission.stakes_level = 2
    mission.serial_thread_id = serial_thread_id
    mission.episode_index = episode_index
    mission.brief = "Text the landlord about a broken radiator and ask for a repair slot this week."
    mission.target_vocabulary_ids = [word.id for word in words[:3]]
    mission.objectives = [
        {"label": "State the problem", "done": True},
        {"label": "Ask for a repair slot", "done": False},
        {"label": "Confirm availability", "done": False},
    ]
    mission.prompt_payload = _mission_payload(words)
    mission.source_snapshot = {
        "mode": "pilot_capture_seed",
        "category": "housing",
        "reason": "Deterministic pilot smoke state",
    }
    if status == "in_progress" and not mission.started_at:
        mission.started_at = _now() - timedelta(minutes=8)
    db.add(mission)
    db.flush()

    if not mission.turns:
        db.add(
            RealWorldMissionTurn(
                mission_id=mission.id,
                user_id=user.id,
                turn_index=1,
                role="assistant",
                mode="chat",
                text="Bonjour, dites-moi ce qui ne fonctionne pas exactement.",
                correction_payload={},
            )
        )
        db.add(
            RealWorldMissionTurn(
                mission_id=mission.id,
                user_id=user.id,
                turn_index=2,
                role="user",
                mode="chat",
                text="Bonjour, le radiateur ne marche plus depuis hier soir.",
                correction_payload={
                    "verdict": "good",
                    "score_0_4": 3.0,
                    "why": "Clear problem statement. Next, ask for the repair slot.",
                    "errata": [],
                },
            )
        )
    db.flush()
    return mission


def _ensure_scene(
    db: Session,
    user: User,
    concepts: list[GrammarConcept],
    words: list[VocabularyWord],
    *,
    serial_thread: SerialThread | None = None,
    episode_index: int | None = None,
) -> GraphicNovelScene:
    scene = (
        db.query(GraphicNovelScene)
        .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.cache_key == "pilot-capture-feuilleton-v1")
        .first()
    )
    target_vocabulary = _target_vocabulary(words)
    final_prompt = {
        "id": "pilot-final-line",
        "task_type": "short_sentence",
        "label": "Final line",
        "instruction": "Write one polite sentence that asks for a repair slot.",
        "prompt": "Camille attend votre derniere phrase.",
        "prompt_translation": "Camille is waiting for your last sentence.",
        "placeholder": "Pourriez-vous...",
        "expected_features": ["conditionnel", "repair slot"],
        "target_vocabulary": target_vocabulary[:1],
    }
    script_payload = {
        "panel_count": 4,
        "experience_mode": "study",
        "render_mode": "panels",
        "image_quality": "medium",
        "story_quality": "standard",
        "target_vocabulary": target_vocabulary,
        "targets": [
            {"kind": "grammar", "label": concepts[0].name if concepts else "Polite request"},
            {"kind": "vocabulary", "label": words[0].word if words else "radiateur"},
        ],
        "hook": {
            "text": "Camille proposes two repair slots, but one collides with class.",
            "unresolved_question": "Which slot will you confirm?",
            "next_beat_kind": "mission",
        },
        "final_prompt": final_prompt,
    }
    if not scene:
        scene = GraphicNovelScene(user_id=user.id, cache_key="pilot-capture-feuilleton-v1")
        db.add(scene)
    scene.status = "available"
    scene.cadence = "ad_hoc"
    scene.serial_thread_id = serial_thread.id if serial_thread else None
    scene.episode_index = episode_index
    scene.title = "Le radiateur capricieux"
    scene.brief = "A short four-panel repair story for the pilot smoke account."
    scene.selected_concept_ids = [concept.id for concept in concepts[:3]]
    scene.target_vocabulary_ids = [word.id for word in words[:3]]
    scene.source_snapshot = {
        "mode": "pilot_capture_seed",
        "title": "Apartment repair rehearsal",
        "source": "Atelier pilot",
    }
    scene.script_payload = script_payload
    scene.recap_payload = {}
    scene.prompt_version = "pilot-capture-v1"
    scene.image_model = "seeded-placeholder"
    scene.image_quality = "medium"
    scene.started_at = scene.started_at or _now() - timedelta(minutes=15)
    db.add(scene)
    db.flush()

    panel_payloads = [
        {
            "title": "Cold radiator",
            "beat": "The learner notices the cold radiator and opens a message thread.",
            "speech": "Le radiateur ne marche plus.",
            "task": {
                "id": "pilot-panel-1-cloze",
                "task_type": "cloze",
                "label": "Cloze",
                "instruction": "Complete the polite request.",
                "prompt": "Pourriez-vous me proposer un ___ ?",
                "prompt_translation": "Could you offer me a slot?",
                "expected_answer": "creneau",
                "target_word": "un creneau",
            },
        },
        {
            "title": "Two choices",
            "beat": "Camille offers two repair windows and asks for confirmation.",
            "speech": "Jeudi matin ou vendredi soir ?",
            "task": {
                "id": "pilot-panel-2-choice",
                "task_type": "choice",
                "label": "Choice",
                "instruction": "Choose the natural reply.",
                "prompt": "Quelle reponse confirme un creneau ?",
                "prompt_translation": "Which reply confirms a slot?",
                "options": [
                    {"value": "a", "text": "Je confirme jeudi matin.", "en": "I confirm Thursday morning."},
                    {"value": "b", "text": "Je radiateur jeudi.", "en": "I radiator Thursday."},
                ],
                "expected_answer": "a",
            },
        },
        {
            "title": "Calendar",
            "beat": "A calendar reveals the class conflict.",
            "speech": "Le matin, j'ai cours.",
            "task": None,
        },
        {
            "title": "Better ask",
            "beat": "The learner writes a softer conditional request.",
            "speech": "Pourriez-vous passer vendredi ?",
            "task": None,
        },
    ]
    existing_panels = {panel.panel_index: panel for panel in scene.panels or []}
    for index, payload in enumerate(panel_payloads):
        panel = existing_panels.get(index)
        if not panel:
            panel = GraphicNovelPanel(scene_id=scene.id, panel_index=index)
            db.add(panel)
        task = payload["task"]
        panel.title = payload["title"]
        panel.beat = payload["beat"]
        panel.image_prompt = f"Pilot capture placeholder panel {index + 1}: {payload['beat']}"
        panel.image_url = None
        panel.image_payload = {"status": "placeholder", "alt": payload["beat"]}
        panel.overlay_payload = {
            "caption": payload["speech"],
            "translation": payload["beat"],
            "speech_bubbles": [{"fr": payload["speech"], "en": payload["beat"], "x": 50, "y": 18}],
            "tasks": [task] if task else [],
        }
        panel.generation_metadata = {"image_status": "placeholder", "seed": "pilot_capture"}
        db.add(panel)
    db.flush()
    return scene


def _ensure_serial(
    db: Session,
    user: User,
    words: list[VocabularyWord],
    scene: GraphicNovelScene | None = None,
) -> tuple[SerialThread, RealWorldMission]:
    service = SerialThreadService(db)
    thread = (
        db.query(SerialThread)
        .filter(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .first()
    )
    if not thread:
        world = service._load_world_bible()
        thread = SerialThread(
            user_id=user.id,
            status="active",
            world_bible=world,
            state=dict(world.get("initial_state") or {}),
            news_seed={"title": "Pilot repair seed", "summary": "Deterministic pilot serial setup."},
            current_episode_index=1,
        )
        db.add(thread)
        db.flush()
    thread.current_episode_index = 1
    thread.news_seed = thread.news_seed or {"title": "Pilot repair seed", "summary": "Deterministic pilot serial setup."}
    db.add(thread)
    db.flush()

    serial_mission = _ensure_mission(
        db,
        user,
        words,
        title="Serial pilot: ask Camille for a repair slot",
        cadence="ad_hoc",
        serial_thread_id=thread.id,
        episode_index=0,
        status="completed",
    )
    serial_mission.completed_at = serial_mission.completed_at or _now() - timedelta(hours=1)
    db.add(serial_mission)
    db.flush()

    episode_zero = (
        db.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 0)
        .first()
    )
    if not episode_zero:
        episode_zero = SerialEpisode(thread_id=thread.id, episode_index=0, kind="mission")
        db.add(episode_zero)
    episode_zero.kind = "mission"
    episode_zero.mission_id = serial_mission.id
    episode_zero.status = "completed"
    episode_zero.location_id = "atelier"
    episode_zero.completed_at = episode_zero.completed_at or serial_mission.completed_at
    episode_zero.brief_payload = {
        "title": "Ask for the repair slot",
        "summary": "The learner texts Camille about the broken radiator.",
    }
    episode_zero.hook = {
        "text": "Camille offers two possible repair windows.",
        "next_beat_kind": "feuilleton",
        "teaser": "Next: the calendar complicates the reply.",
    }
    db.add(episode_zero)

    if scene is not None:
        scene.serial_thread_id = thread.id
        scene.episode_index = 1
        db.add(scene)
        db.flush()
    episode_one = (
        db.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .first()
    )
    if not episode_one:
        episode_one = SerialEpisode(thread_id=thread.id, episode_index=1, kind="feuilleton")
        db.add(episode_one)
    episode_one.kind = "feuilleton"
    episode_one.scene_id = scene.id if scene else None
    episode_one.status = "available"
    episode_one.location_id = "apartment"
    episode_one.hook_from_previous = episode_zero.hook
    episode_one.brief_payload = {
        "title": "The calendar complication",
        "summary": "A visual beat about confirming the right repair window.",
    }
    episode_one.hook = {
        "text": "The repair slot is nearly confirmed.",
        "next_beat_kind": "mission",
    }
    db.add(episode_one)
    db.flush()
    return thread, serial_mission


def seed(email: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        user = _ensure_user(db, email)
        words = _seed_vocabulary(db, user)
        concepts = _seed_concepts(db, user)
        errata = _seed_errata(db, user, concepts, words)
        session = _ensure_atelier_session(db, user, concepts, words)
        mission = _ensure_mission(
            db,
            user,
            words,
            title="Pilot: text the landlord about heat",
            cadence="ad_hoc",
            status="in_progress",
        )
        scene = _ensure_scene(db, user, concepts, words)
        thread, serial_mission = _ensure_serial(db, user, words, scene=scene)
        db.commit()
        return {
            "user_id": str(user.id),
            "atelier_session_id": str(session.id),
            "mission_id": str(mission.id),
            "serial_thread_id": str(thread.id),
            "serial_mission_id": str(serial_mission.id),
            "feuilleton_scene_id": str(scene.id),
            "concept_ids": [concept.id for concept in concepts],
            "word_ids": [word.id for word in words],
            "errata_ids": [str(error.id) for error in errata],
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Existing user email to seed.")
    args = parser.parse_args()
    print(json.dumps(seed(args.email), sort_keys=True))


if __name__ == "__main__":
    main()
