"""#119 — an article left unelided in a Courrier letter is the article rule's slip.

Production, 31 Oct (walk account): «le appartement → l'appartement» from a letter
was filed under «Un, une, des», and «de Odile → d'Odile» likewise, so «Le, la, l',
les» never moved while the learner kept making its most frequent mistake. The
contract's elision rule id (``FR_ELISION``) is no catalogue unit, and the Courrier
filed every such id under the letter's own rule. An article elided by the correction
now lands on «Le, la, l', les», whatever the letter practised and whoever corrected it.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.correction_contract import ARTICLE_ELISION_UNIT, elides_an_article
from app.services.missions import MissionCorrectionService
from tests.test_missions import _ExplodingMissionLLM, _mission_for_correction

_NAMES = {
    ARTICLE_ELISION_UNIT: ("Le, la, l', les : les articles définis", "Articles"),
    "FR2_A11_UN_UNE": ("Un, une, des : les articles indéfinis", "Articles"),
}


def _unit(db_session, external_id: str) -> GrammarConcept:
    found = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one_or_none()
    if found is not None:
        return found
    name, category = _NAMES[external_id]
    unit = GrammarConcept(external_id=external_id, language="fr", name=name, level="A1", category=category, active=True)
    db_session.add(unit)
    db_session.commit()
    return unit


def test_the_pair_says_when_an_article_was_elided():
    assert elides_an_article("le appartement", "l'appartement")
    assert elides_an_article("La amie", "L’amie")
    assert elides_an_article("de Odile", "d’Odile")
    assert elides_an_article("le hôtel", "l'hôtel")
    assert elides_an_article("Je visite le appartement de Odile", "Je visite l'appartement d'Odile")
    # Not the article rule's: an object pronoun, a subject, «que», a gender, another word.
    assert not elides_an_article("je le aime", "je l'aime")
    assert not elides_an_article("Je ai", "J'ai")
    assert not elides_an_article("que il", "qu'il")
    assert not elides_an_article("le table", "la table")
    assert not elides_an_article("la appartement", "l'appartements")


def test_an_object_pronoun_is_told_from_the_article_by_the_letter_itself():
    """Review of #434: the contract quotes only «le aime» → «l'aime», so the subject in
    front of it is in the letter, not in the pair."""

    assert not elides_an_article("le aime", "l'aime", context="Je le aime beaucoup.")
    assert not elides_an_article("le aime", "l'aime")
    assert not elides_an_article("la invite", "l'invite", context="Ce soir, je la invite au cinéma.")
    assert not elides_an_article("le acheter", "l'acheter", context="Je vais le acheter demain.")
    assert not elides_an_article("le a", "l'a", context="Elle me le a donné.")
    # The article keeps its rule, with the letter or without it.
    assert elides_an_article("la école", "l'école", context="Je cherche la école.")
    assert elides_an_article("Le hôtel", "L'hôtel", context="Le hôtel est loin.")
    assert elides_an_article("le ami", "l'ami", context="Elle aime le ami de Paul.")


def test_a_letters_elision_slips_land_on_the_article_rule(db_session):
    le_la = _unit(db_session, ARTICLE_ELISION_UNIT)
    un_une = _unit(db_session, "FR2_A11_UN_UNE")
    user = User(id=uuid4(), email=f"courrier-119-{uuid4().hex[:6]}@example.com", hashed_password="x", proficiency_level="A1")
    db_session.add(user)
    db_session.commit()
    mission = _mission_for_correction()
    mission.user_id = user.id
    # The letter practises «Un, une, des», as on 31 Oct.
    mission.selected_concept_ids = [un_une.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())

    correction = service.correct_submission(
        user=user,
        mission=mission,
        text="Bonjour, je visite le appartement de Odile demain. Je pense que il est grand.",
        mode="letter",
        near_realtime=True,
    )
    by_span = {item["learner_text"].casefold(): item for item in correction["errata"]}
    assert by_span["le appartement"]["concept_id"] == le_la.id
    assert by_span["de odile"]["concept_id"] == le_la.id
    # «que il» elides no article: no catalogue unit is its own, so it keeps its filing.
    assert by_span["que il"]["concept_id"] != le_la.id

    persisted = service.persist_errata(
        user=user, mission=mission, correction=correction, mode="letter", source_id="letter-119"
    )
    assert {item["concept_id"] for item in persisted if item["learner_text"] in {"le appartement", "de Odile"}} == {le_la.id}
    rows = db_session.query(UserError).filter_by(user_id=user.id).all()
    elisions = [row for row in rows if row.concept_id == le_la.id]
    # Both slips are the same mistake in the error memory (one row, two occurrences),
    # and it is the article rule's: the Cahier shows it under «Le, la, l', les».
    assert sum(row.occurrences or 1 for row in elisions) >= 2, [(r.original_text, r.concept_id) for r in rows]
    assert not any(row.concept_id == un_une.id and "appartement" in (row.original_text or "") for row in rows)


def test_a_model_label_does_not_take_an_elision_away_from_the_article_rule(db_session):
    le_la = _unit(db_session, ARTICLE_ELISION_UNIT)
    un_une = _unit(db_session, "FR2_A11_UN_UNE")
    mission = _mission_for_correction()
    mission.selected_concept_ids = [un_une.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    labelled = service._normalize_erratum(
        {
            "learner_text": "le appartement",
            "corrected_target": "l'appartement",
            "why_wrong": "Elision needed before vowel: use l' instead of le.",
            "external_id": "FR2_A11_UN_UNE",
        },
        mission,
    )
    assert labelled["concept_id"] == le_la.id
    other = service._normalize_erratum(
        {"learner_text": "une café", "corrected_target": "un café", "why_wrong": "café is masculine.", "external_id": ""},
        mission,
    )
    assert other["concept_id"] == un_une.id, "any other slip keeps the letter's rule"


def test_a_letters_pronoun_elision_keeps_the_letters_rule(db_session):
    """Review of #434: «je le aime» in a letter on object pronouns is not filed under the article rule."""

    le_la = _unit(db_session, ARTICLE_ELISION_UNIT)
    un_une = _unit(db_session, "FR2_A11_UN_UNE")
    user = User(id=uuid4(), email=f"courrier-119p-{uuid4().hex[:6]}@example.com", hashed_password="x", proficiency_level="A1")
    db_session.add(user)
    db_session.commit()
    mission = _mission_for_correction()
    mission.user_id = user.id
    mission.selected_concept_ids = [un_une.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())

    correction = service.correct_submission(
        user=user,
        mission=mission,
        text="Bonjour Odile, je le aime beaucoup, ton cadeau. Je cherche la école de Paul.",
        mode="letter",
        near_realtime=True,
    )
    by_span = {item["learner_text"].casefold(): item for item in correction["errata"]}
    assert by_span["le aime"]["concept_id"] != le_la.id, by_span["le aime"]
    assert by_span["la école"]["concept_id"] == le_la.id
