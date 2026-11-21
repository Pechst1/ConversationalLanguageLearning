"""Round 3 (walk 2, 17 Nov 2026) — the drill around the scene deals the learner's own mistakes.

B1 days 4 and 6 dealt «Écris correctement ce que tu as dit» cards built from La
Forge's half-finished edits: «… je les les donne après le travail.», «L'autre jour,
c'était a l'heure du déjeuner …», «Je t'appelle sans de t'expliquer le problème.».
The rows below are the B1 learner's, as stored in the walk database.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.user import User
from app.services.error_memory import ErrorMemoryService
from app.services.fault_quality import learner_own_fault
from app.services.journey_errata import errata_targets_for_user

COPINE_ITEM = {
    "id": "fr2-b11-double-pronouns-repair-c929424cee",
    "type": "rewrite",
    "fix_words": 2,
    "source": "Ta copine attend les billets ? Oui, je lui les donne après le travail.",
    "expected_answer": "Ta copine attend les billets ? Oui, je les lui donne après le travail.",
}
MAIRIE_ITEM = {
    "id": "fr2-b11-narration-repair-14dc127aa3",
    "type": "rewrite",
    "fix_words": 3,
    "source": "L'autre jour, ça a été l'heure du déjeuner quand j'ai appelé la mairie, mais tous les bureaux avaient déjà fermé.",
    "expected_answer": "L'autre jour, c'était l'heure du déjeuner quand j'ai appelé la mairie, mais tous les bureaux avaient déjà fermé.",
}
APPELLE_ITEM = {
    "id": "fr2-b11-prep-infinitive-repair-8e980aa4b9",
    "type": "rewrite",
    "fix_words": 1,
    "source": "Je t'appelle pour de t'expliquer le problème.",
    "expected_answer": "Je t'appelle pour t'expliquer le problème.",
}
JUDGE_ITEM = {"id": "fr2-a11-un-une-classify-a46dc17ade", "type": "classify", "sentence": "Je cherche une lit à l'hôtel."}


# ---------------------------------------------------------------------------
# The check itself, on the walk's stored faults
# ---------------------------------------------------------------------------


def test_a_doubled_word_from_an_edit_is_not_the_learner_s() -> None:
    submitted = "Ta copine attend lui billets ? Oui, je les les donne après le travail."
    assert not learner_own_fault(wrong="les les", correct="les lui", submitted=submitted, item=COPINE_ITEM)


def test_the_item_s_planted_word_left_in_place_is_the_item_s_error() -> None:
    submitted = "L'autre jour, c'était a l'heure du déjeuner quand j'ai appelé la mairie, mais tous les bureaux avaient déjà fermé."
    assert not learner_own_fault(wrong=submitted, correct=MAIRIE_ITEM["expected_answer"], submitted=submitted, item=MAIRIE_ITEM)
    assert not learner_own_fault(
        wrong="sans de", correct="sans", submitted="Je t'appelle sans de t'expliquer le problème.", item=APPELLE_ITEM
    )


def test_a_piece_of_a_word_is_not_a_fault() -> None:
    """Walk 1: «m'me → m'en», a token the learner never wrote."""

    assert not learner_own_fault(wrong="m'me", correct="m'en", submitted="Il m' me a parlé.", item=None)


def test_a_judgement_is_not_french_the_learner_wrote() -> None:
    assert not learner_own_fault(
        wrong="Je cherche une lit à l'hôtel.", correct="Je cherche un lit à l'hôtel.", submitted="Correct", item=JUDGE_ITEM
    )


def test_a_target_that_is_not_french_is_refused() -> None:
    assert not learner_own_fault(wrong="les les", correct="les les lui")
    assert not learner_own_fault(wrong="a", correct="")


def test_genuine_mistakes_stay() -> None:
    # The learner's own line, the planted error fixed, a new slip of their own.
    assert learner_own_fault(
        wrong="lui les",
        correct="les lui",
        submitted="Mon voisin veut les papiers du notaire, alors je lui les donne demain matin.",
    )
    assert learner_own_fault(
        wrong="les donne", correct="les lui donne",
        submitted="Ta copine attend les billets ? Oui, je les donne après le travail.", item=COPINE_ITEM,
    )
    # The scene, a letter, the journal: judged on their own words.
    assert learner_own_fault(wrong="a déjà réservé", correct="avait déjà réservé")
    assert learner_own_fault(wrong="Je suis fatigue", correct="Je suis fatigué")
    assert learner_own_fault(wrong="nous nous levons tard", correct="nous nous sommes levés tard")


# ---------------------------------------------------------------------------
# Write side and read side
# ---------------------------------------------------------------------------


def _user(db_session) -> User:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr", native_language="en")
    db_session.add(user)
    db_session.flush()
    return user


def _attempt(db_session, user: User, *, item: dict, answer: str, errata: list[dict]) -> AtelierAttempt:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="active", quote_payload={}, recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        round="transform",
        mode="rewrite",
        exercise_id=f"FR2_B11_DOUBLE_PRONOUNS:transform:{item['id']}",
        prompt_payload={"mode": "rewrite", "items": [item]},
        answer_payload={"answers": {item["id"]: answer}},
        correction_payload={"verdict": "incorrect", "errata": errata},
        verdict="incorrect",
        score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.flush()
    return attempt


def _erratum(item: dict, wrong: str, correct: str) -> dict:
    return {
        "item_id": item["id"],
        "learner_text": wrong,
        "corrected_target": correct,
        "display_label": "Ordre des pronoms",
        "why_wrong": "Le pronom direct précède le pronom indirect.",
        "task_error_type": "pronoun_choice",
        "severity": 2,
    }


def test_the_write_side_stores_no_half_finished_edit(db_session) -> None:
    user = _user(db_session)
    attempt = _attempt(
        db_session,
        user,
        item=COPINE_ITEM,
        answer="Ta copine attend lui billets ? Oui, je les les donne après le travail.",
        errata=[_erratum(COPINE_ITEM, "les les", "les lui")],
    )
    ErrorMemoryService(db_session).record_atelier_attempt(user=user, attempt=attempt)
    db_session.flush()
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0


def test_the_write_side_keeps_a_real_mistake(db_session) -> None:
    user = _user(db_session)
    attempt = _attempt(
        db_session,
        user,
        item=COPINE_ITEM,
        answer="Ta copine attend les billets ? Oui, je les donne après le travail.",
        errata=[_erratum(COPINE_ITEM, "les donne", "les lui donne")],
    )
    ErrorMemoryService(db_session).record_atelier_attempt(user=user, attempt=attempt)
    db_session.flush()
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 1


def _stored(db_session, user: User, attempt: AtelierAttempt | None, wrong: str, correct: str, *, source: str) -> UserError:
    row = UserError(
        user_id=user.id,
        error_category="grammar",
        original_text=wrong,
        correction=correct,
        display_label="Ordre des pronoms",
        why_wrong="Le pronom direct précède le pronom indirect.",
        source_type=source,
        source_attempt_id=attempt.id if attempt else None,
        review_mode="grammar",
        state="open",
        occurrences=1,
        memory_key=f"r3:{uuid4().hex}",
        error_metadata={"severity": 2, "source_payload": {"erratum_index": 0}},
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_the_drill_refuses_a_stored_half_finished_edit(db_session) -> None:
    """Rows stored before the write-side check are harmless: the drill does not deal them."""

    user = _user(db_session)
    garbled = _attempt(
        db_session,
        user,
        item=COPINE_ITEM,
        answer="Ta copine attend lui billets ? Oui, je les les donne après le travail.",
        errata=[_erratum(COPINE_ITEM, "les les", "les lui")],
    )
    bad = _stored(db_session, user, garbled, "les les", "les lui", source="atelier")
    good = _stored(db_session, user, None, "a déjà réservé", "avait déjà réservé", source="daily_journey")
    ids = {target.error_id for target in errata_targets_for_user(db_session, user, limit=5)}
    assert str(bad.id) not in ids
    assert str(good.id) in ids
