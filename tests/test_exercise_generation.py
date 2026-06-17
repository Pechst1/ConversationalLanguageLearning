from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services.atelier import AtelierScheduler
from app.services.exercise_generation import (
    ExerciseGenerationService,
    validate_atelier_generation_payload,
    validate_brief_grammar_payload,
    validate_error_exercise_payload,
)


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language="en",
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_daily_context_selects_exactly_three_srs_concepts(db_session) -> None:
    user = _user(db_session)
    AtelierScheduler(db_session).ensure_catalog()
    cond = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_COND_001").one()
    tense = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_TENSE_001").one()

    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=cond.id,
            error_category="grammar",
            display_label="Future result",
            original_text="si je viens, je reste",
            correction="si je viens, je resterai",
            state="review",
            lapses=2,
            occurrences=3,
            next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=tense.id,
            score=4.0,
            reps=2,
            state="in_arbeit",
            next_review=datetime.now(timezone.utc) - timedelta(hours=3),
        )
    )
    db_session.commit()

    context = ExerciseGenerationService(db_session).build_daily_context(user=user)

    assert len(context.concepts) == 3
    assert context.concepts[0]["id"] == cond.id
    assert context.concepts[0]["role"] == "errata"
    assert any(item["id"] == tense.id and item["role"] == "fragile" for item in context.concepts)
    assert str(cond.id) in context.concept_blueprints
    assert context.due_errata[0]["concept_id"] == cond.id


def test_strict_payload_validators_reject_incomplete_generation() -> None:
    assert validate_atelier_generation_payload({"recognize": {}})
    assert validate_brief_grammar_payload({"exercises": []}) == [
        "brief grammar payload must contain exactly 3 exercises"
    ]
    assert "error exercise missing correct_answer" in validate_error_exercise_payload(
        {
            "exercise_type": "correction",
            "instruction": "Repair it.",
            "prompt": "Je veux un cafe.",
            "explanation": "Use the target form.",
            "memory_tip": "Short repairs stick.",
        }
    )
