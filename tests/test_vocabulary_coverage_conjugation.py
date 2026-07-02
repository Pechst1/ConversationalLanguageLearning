"""Coverage map and conjugation drill regressions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import UserConjugationProgress, VerbConjugation, VocabularyWord
from app.services.conjugation import ConjugationService, build_conjugation_rows, upsert_conjugation_rows
from app.services.missions import MissionGenerator
from app.services.vocabulary_coverage import primary_category


def _auth_user(client: TestClient, db_session, *, email: str | None = None) -> tuple[str, User]:
    address = email or f"coverage-{uuid4().hex}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": address,
            "password": "strongpass",
            "target_language": "fr",
            "native_language": "en",
        },
    )
    login = client.post("/api/v1/auth/login", json={"email": address, "password": "strongpass"})
    user = db_session.query(User).filter(User.email == address).one()
    return login.json()["access_token"], user


def test_coverage_endpoint_rolls_up_vocabulary_grammar_and_conjugation(client: TestClient, db_session) -> None:
    token, user = _auth_user(client, db_session)
    now = datetime.now(timezone.utc)
    apple = VocabularyWord(
        language="fr",
        word="pomme",
        normalized_word="pomme",
        part_of_speech="noun",
        topic_tags=["food_drink"],
        frequency_rank=40,
        difficulty_level=1,
        direction="fr_to_de",
        german_translation="Apfel",
        is_anki_card=True,
    )
    verb = VocabularyWord(
        language="fr",
        word="venir",
        normalized_word="venir",
        part_of_speech="verb",
        frequency_rank=80,
        difficulty_level=2,
        direction="fr_to_de",
        german_translation="kommen",
        is_anki_card=True,
    )
    inferred_person = VocabularyWord(
        language="fr",
        word="sœur",
        normalized_word="1558",
        frequency_rank=1558,
        difficulty_level=3,
        direction="fr_to_de",
        german_translation="Schwester",
        is_anki_card=True,
    )
    inferred_verb = VocabularyWord(
        language="fr",
        word="abaisser",
        normalized_word="3209",
        frequency_rank=3209,
        difficulty_level=4,
        direction="fr_to_de",
        german_translation="senken",
        is_anki_card=True,
    )
    generated_phrase = VocabularyWord(
        language="fr",
        word="Bonjour, je voulais vous prévenir que...",
        normalized_word="mission-phrase",
        difficulty_level=2,
        direction="fr_to_de",
        english_translation="Reusable opening fragment",
        topic_tags=["mission_phrase", "real_world"],
        is_anki_card=False,
    )
    concept = GrammarConcept(
        external_id=f"FR_A2_TENSE_{uuid4().hex[:8]}",
        language="fr",
        name="Passé composé",
        level="A2",
        category="Tenses",
        active=True,
    )
    grammar = GrammarConcept(
        external_id=f"FR_A1_ART_{uuid4().hex[:8]}",
        language="fr",
        name="Articles",
        level="A1",
        category="Articles",
        active=True,
    )
    db_session.add_all([apple, verb, inferred_person, inferred_verb, generated_phrase, concept, grammar])
    db_session.flush()
    assert primary_category(inferred_person) == "people_relationships"
    assert primary_category(inferred_verb) == "verbs"
    db_session.add_all(
        [
            UserVocabularyProgress(
                user_id=user.id,
                word_id=apple.id,
                state="mastered",
                reps=3,
                proficiency_score=95,
                mastered_date=now,
                last_review_date=now - timedelta(days=1),
                stability=8,
            ),
            UserVocabularyProgress(
                user_id=user.id,
                word_id=verb.id,
                state="reviewing",
                reps=1,
                proficiency_score=50,
            ),
            UserGrammarProgress(
                user_id=user.id,
                concept_id=concept.id,
                score=9,
                reps=3,
                state="gemeistert",
            ),
            UserGrammarProgress(
                user_id=user.id,
                concept_id=grammar.id,
                score=4,
                reps=1,
                state="in_arbeit",
            ),
        ]
    )
    upsert_conjugation_rows(db_session, build_conjugation_rows("venir", cefr_band="A2"))
    db_session.add(
        UserConjugationProgress(
            user_id=user.id,
            verb_lemma="venir",
            normalized_lemma="venir",
            tense="present",
            cefr_band="A2",
            state="mastered",
            reps=2,
            proficiency_score=92,
            mastered_date=now,
        )
    )
    db_session.commit()

    response = client.get("/api/v1/vocabulary/coverage", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["cefr_bar"]
    food = next(item for item in payload["categories"] if item["id"] == "food_drink")
    assert food["nailed"] == 1
    assert food["total"] == 1
    assert all(item["id"] != "uncategorized" for item in payload["categories"])
    people = next(item for item in payload["categories"] if item["id"] == "people_relationships")
    assert "sœur" in people["example_words"]
    assert "Bonjour, je voulais vous prévenir que..." not in [
        word
        for item in payload["categories"]
        for word in item.get("example_words", [])
    ]
    verb_lexicon = next(item for item in payload["verb_tracks"] if item["id"] == "verb_lexicon")
    assert verb_lexicon["total"] >= 2
    irregulars = next(item for item in payload["verb_tracks"] if item["id"] == "irregular_forms")
    assert irregulars["nailed"] >= 1
    assert payload["grammar_tracks"]
    assert payload["next_best_set"]["href"]


def test_conjugation_review_queue_and_rating(client: TestClient, db_session) -> None:
    token, user = _auth_user(client, db_session)
    upsert_conjugation_rows(db_session, build_conjugation_rows("venir", cefr_band="A2"))
    db_session.commit()

    queue = client.get("/api/v1/vocabulary/conjugation/review", headers={"Authorization": f"Bearer {token}"})

    assert queue.status_code == 200
    item = queue.json()["items"][0]
    assert item["lemma"] == "venir"
    assert item["answer"]
    assert item["table"]

    review = client.post(
        "/api/v1/vocabulary/conjugation/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"lemma": item["lemma"], "tense": item["tense"], "rating": 3},
    )

    assert review.status_code == 200
    payload = review.json()
    assert payload["lemma"] == "venir"
    assert payload["reps"] == 1
    progress = (
        db_session.query(UserConjugationProgress)
        .filter(UserConjugationProgress.user_id == user.id, UserConjugationProgress.normalized_lemma == "venir")
        .first()
    )
    assert progress is not None
    assert progress.next_review_date is not None


def test_conjugation_rows_canonicalize_accent_stripped_irregulars() -> None:
    rows = build_conjugation_rows("etre")

    present = [row for row in rows if row["tense"] == "present"]
    assert present[0]["lemma"] == "être"
    assert present[0]["normalized_lemma"] == "etre"
    assert present[0]["is_irregular"] is True
    assert [row["form"] for row in present[:6]] == ["suis", "es", "est", "sommes", "êtes", "sont"]


def test_conjugation_generation_prefers_accented_vocabulary_surface(db_session) -> None:
    word = VocabularyWord(
        language="fr",
        word="être",
        normalized_word="etre",
        part_of_speech="verb",
        frequency_rank=1,
        difficulty_level=1,
        direction="fr_to_de",
    )
    db_session.add(word)
    db_session.commit()

    changed = ConjugationService(db_session).ensure_verb_rows_from_vocabulary()
    db_session.flush()
    row = (
        db_session.query(VerbConjugation)
        .filter(
            VerbConjugation.normalized_lemma == "etre",
            VerbConjugation.tense == "present",
            VerbConjugation.person == "je",
        )
        .one()
    )

    assert changed > 0
    assert row.lemma == "être"
    assert row.form == "suis"


def test_conjugation_review_cefr_filter_applies_to_due_progress(client: TestClient, db_session) -> None:
    token, user = _auth_user(client, db_session)
    now = datetime.now(timezone.utc)
    upsert_conjugation_rows(db_session, build_conjugation_rows("venir", cefr_band="A2"))
    upsert_conjugation_rows(db_session, build_conjugation_rows("connaître", cefr_band="B2"))
    db_session.add_all(
        [
            UserConjugationProgress(
                user_id=user.id,
                verb_lemma="venir",
                normalized_lemma="venir",
                tense="present",
                cefr_band="A2",
                state="reviewing",
                next_review_date=now - timedelta(days=1),
                due_date=(now - timedelta(days=1)).date(),
            ),
            UserConjugationProgress(
                user_id=user.id,
                verb_lemma="connaître",
                normalized_lemma="connaitre",
                tense="present",
                cefr_band="B2",
                state="reviewing",
                next_review_date=now - timedelta(days=1),
                due_date=(now - timedelta(days=1)).date(),
            ),
        ]
    )
    db_session.commit()

    queue = client.get(
        "/api/v1/vocabulary/conjugation/review?cefr_band=A2&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert queue.status_code == 200
    lemmas = {item["lemma"] for item in queue.json()["items"]}
    assert "venir" in lemmas
    assert "connaître" not in lemmas


def test_mission_generator_prefers_recently_nailed_vocabulary(db_session) -> None:
    user = User(
        id=uuid4(),
        email=f"mission-nailed-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    nailed = VocabularyWord(
        language="fr",
        word="marché",
        normalized_word="marche",
        part_of_speech="noun",
        topic_tags=["food_drink"],
        frequency_rank=75,
        german_translation="Markt",
        direction="fr_to_de",
        is_anki_card=True,
    )
    fallback = VocabularyWord(
        language="fr",
        word="administration",
        normalized_word="administration",
        part_of_speech="noun",
        topic_tags=["society_politics"],
        frequency_rank=900,
        german_translation="Verwaltung",
        direction="fr_to_de",
        is_anki_card=True,
    )
    db_session.add_all([user, nailed, fallback])
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=nailed.id,
            state="mastered",
            reps=3,
            proficiency_score=96,
            mastered_date=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    selected = MissionGenerator(db_session)._select_vocabulary(user=user, limit=1)

    assert selected[0]["word_id"] == nailed.id
    assert selected[0]["bucket"] == "recently_nailed"
