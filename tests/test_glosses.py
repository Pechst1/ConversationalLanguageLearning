"""The learner is shown a translation in a language they actually read.

The vocabulary table has three gloss columns and the payload builders used to
read them in a fixed `german or english or french` order, so the English default
that signup ships with was served German. These tests pin the resolution and the
two learner-facing payloads that carry it.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import select_atelier_vocabulary
from app.services.glosses import (
    gloss_from_map,
    gloss_map,
    gloss_payload,
    normalize_language,
    resolve_gloss,
    word_gloss,
)
from app.services.progress import ProgressService


class _Word:
    def __init__(self, de=None, en=None, fr=None, definition=None):
        self.german_translation = de
        self.english_translation = en
        self.french_translation = fr
        self.definition = definition


def test_gloss_follows_the_learners_language():
    word = _Word(de="die Akte", en="the file", fr="le dossier")
    assert word_gloss(word, "en") == "the file"
    assert word_gloss(word, "de") == "die Akte"
    assert word_gloss(word, "fr") == "le dossier"


def test_gloss_falls_back_rather_than_leaving_a_learner_with_nothing():
    german_only = _Word(de="die Akte")
    gloss, language = resolve_gloss(german_only, "en")
    assert gloss == "die Akte"
    # The surface can label the fallback instead of implying it is English.
    assert language == "de"


def test_missing_gloss_falls_through_to_the_definition():
    assert word_gloss(_Word(definition="a paper record"), "en") == "a paper record"
    assert word_gloss(_Word(), "en") == ""


def test_language_codes_are_normalised():
    assert normalize_language("EN-GB") == "en"
    assert normalize_language("de_DE") == "de"
    assert normalize_language(None) == "en"
    assert normalize_language("  ") == "en"


def test_gloss_payload_keeps_the_raw_map_for_clients():
    word = _Word(de="die Akte", en="the file")
    payload = gloss_payload(word, "en")
    assert payload["translation"] == "the file"
    assert payload["translation_language"] == "en"
    assert payload["translations"] == gloss_map(word)


def test_gloss_from_map_matches_row_resolution():
    translations = {"de": "die Akte", "en": "the file"}
    assert gloss_from_map(translations, "de") == "die Akte"
    assert gloss_from_map(translations, "en") == "the file"
    assert gloss_from_map({}, "en") == ""


def _word_row(db_session, **kwargs) -> VocabularyWord:
    word = VocabularyWord(
        word=kwargs.pop("word", "dossier"),
        normalized_word=kwargs.pop("normalized_word", "dossier"),
        language="fr",
        **kwargs,
    )
    db_session.add(word)
    db_session.flush()
    return word


def _learner(db_session, native_language: str) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="x",
        native_language=native_language,
        target_language="fr",
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_atelier_vocabulary_payload_speaks_the_learners_language(db_session):
    word = _word_row(
        db_session,
        german_translation="die Akte",
        english_translation="the file",
    )
    db_session.commit()

    english_learner = _learner(db_session, "en")
    german_learner = _learner(db_session, "de")

    english_items = select_atelier_vocabulary(
        db_session, user=english_learner, preferred_word_ids=[word.id], limit=1
    )
    german_items = select_atelier_vocabulary(
        db_session, user=german_learner, preferred_word_ids=[word.id], limit=1
    )

    assert english_items[0]["translation"] == "the file"
    assert english_items[0]["translation_language"] == "en"
    assert german_items[0]["translation"] == "die Akte"
    assert german_items[0]["translation_language"] == "de"


def test_review_queue_payload_speaks_the_learners_language(db_session):
    word = _word_row(
        db_session,
        word="rendez-vous",
        normalized_word="rendez-vous",
        german_translation="der Termin",
        english_translation="the appointment",
    )
    db_session.commit()
    learner = _learner(db_session, "en")

    payload = ProgressService(db_session)._serialize_vocabulary_recommendation(
        word=word,
        progress=None,
        bucket="new",
        now=__import__("datetime").datetime.now(__import__("datetime").UTC),
        native_language=learner.native_language,
    )

    assert payload["translation"] == "the appointment"
    assert payload["translations"]["de"] == "der Termin"


def test_correction_explanations_follow_the_learner_not_the_publication(db_session):
    """The fiction is French; an explanation of a mistake is instruction.

    A learner who cannot read the explanation of their own error learns nothing
    from it, so why_wrong/repair_hint follow the profile language while every
    French fragment in the same payload stays French.
    """
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService(db_session)

    # Default before an attempt names a learner.
    assert service.explanation_language == "en"
    assert "in English" in service._correction_system_prompt()

    service.explanation_language = "de"
    prompt = service._correction_system_prompt()
    assert "Write why_wrong, repair_hint and display_label in German." in prompt
    assert "never translate the French itself into German" in prompt

    # An unknown language falls back rather than instructing the model in ""
    service.explanation_language = "xx"
    assert "in English" in service._correction_system_prompt()


def test_correction_payload_reports_its_explanation_language(db_session):
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService(db_session)
    service.explanation_language = "de"
    correction = service.correct(
        concept=None,
        round_name="unknown-round",
        mode="",
        exercise_id="x",
        prompt_payload={},
        answer_payload={},
    )
    assert correction["explanation_language"] == "de"


def test_submitted_attempt_uses_the_learners_explanation_language(db_session):
    """The language is taken from the profile on every attempt, not left at the default."""
    from app.db.models.atelier import AtelierSession
    from app.services.atelier import AtelierCorrectionService

    learner = _learner(db_session, "de")
    session = AtelierSession(user_id=learner.id, selected_concept_ids=[], status="in_progress")
    db_session.add(session)
    db_session.commit()

    service = AtelierCorrectionService(db_session)
    attempt = service.submit_attempt(
        session=session,
        user=learner,
        concept=None,
        round_name="sentence",
        mode="sentence",
        exercise_id="explanation-language",
        answer_payload={"text": "Je ne mange pas."},
    )

    assert service.explanation_language == "de"
    assert (attempt.correction_payload or {}).get("explanation_language") == "de"
