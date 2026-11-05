"""#119 (3 Nov re-test): one classifier decides which rule an elision correction is about.

The Courrier asked ``correction_contract.elides_an_article``; the journey path
(scene replies, recall) asked ``ErrorMemoryService.infer_concept_id_for_correction``,
where «de» is a determiner token, the marker became «determiner …» and the article
family's first concept («Un, une, des») won. «de Odile» → «d'Odile» in a scene reply
was filed under «Un, une, des», which then showed «practising» in the Cahier.
Now the filing itself (``record_erratum``) and the journey inference both ask the same
function, so no entrance can file an elision on another article rule.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.user import User
from app.services.correction_contract import ARTICLE_ELISION_UNIT
from app.services.error_memory import ErrorMemoryService
from app.services.journey_contracts import Correction
from tests.test_courrier_elision_119 import _unit


def _setup(db_session):
    le_la = _unit(db_session, ARTICLE_ELISION_UNIT)
    un_une = _unit(db_session, "FR2_A11_UN_UNE")
    # As in the catalogue: «Un, une, des» comes before «Le, la, l', les», so the family inference lands on it.
    un_une.difficulty_order, le_la.difficulty_order = 1, 2
    user = User(id=uuid4(), email=f"elision-119-{uuid4().hex[:6]}@example.com", hashed_password="x", proficiency_level="A1")
    db_session.add(user)
    db_session.commit()
    return user, le_la, un_une


def test_a_journey_correction_that_elides_de_is_the_article_rules(db_session):
    user, le_la, un_une = _setup(db_session)
    memory = ErrorMemoryService(db_session)
    for span, fixed in (("de Odile", "d'Odile"), ("la appartement", "l'appartement"), ("le hôtel", "l’hôtel")):
        assert memory.infer_concept_id_for_correction(learner_text=span, corrected_text=fixed, note="") == le_la.id, span
    # Other article changes keep their family inference; an object pronoun is not the article.
    assert memory.infer_concept_id_for_correction(learner_text="une café", corrected_text="un café", note="") == un_une.id
    assert memory.infer_concept_id_for_correction(learner_text="je le aime", corrected_text="je l'aime", note="") != le_la.id


def test_a_scene_reply_elision_is_filed_on_the_article_rule_whatever_rule_the_step_named(db_session):
    from app.services.journey_contracts import InputMode
    from app.services.journey_learning import (
        _record_correction_erratum,
        ensure_journey_learning_session,
    )

    user, le_la, un_une = _setup(db_session)
    session = ensure_journey_learning_session(db_session, user=user, journey_id=uuid4(), scenario_key="meet_family")
    update = _record_correction_erratum(
        db_session, user=user, session=session,
        correction=Correction(span_fr="de Odile", corrected_fr="d'Odile", note_native="", context_fr="Je suis le petit-fils de Odile."),
        modality=InputMode.TEXT, source_key="scene-1", foreground=True,
        concept_id_hint=un_une.id,
    )
    assert update is not None
    row = db_session.query(UserError).filter_by(user_id=user.id).one()
    assert row.concept_id == le_la.id, "filed on the rule that teaches l' and d'"


def test_every_entrance_files_an_elision_on_the_article_rule(db_session):
    """The filing function itself: a journal or recall erratum arriving with another rule's id."""

    user, le_la, un_une = _setup(db_session)
    memory = ErrorMemoryService(db_session)
    update = memory.record_erratum(
        user=user,
        erratum={
            "learner_text": "la appartement", "corrected_target": "l'appartement",
            "why_wrong": "Elision.", "task_error_type": "grammar_target", "concept_id": un_une.id,
        },
        source_type="journal",
        concept_id=un_une.id,
    )
    assert update is not None
    row = db_session.query(UserError).filter_by(user_id=user.id).one()
    assert row.concept_id == le_la.id
    # A keyed item's own unit keeps its erratum: the item belongs to that rule.
    keyed = memory.record_erratum(
        user=user,
        erratum={
            "item_id": "i1", "learner_text": "de Odile", "corrected_target": "d'Odile",
            "why_wrong": "Elision.", "task_error_type": "grammar_target", "concept_id": un_une.id,
        },
        source_type="atelier",
        concept_id=un_une.id,
    )
    assert keyed is not None
    rows = db_session.query(UserError).filter_by(user_id=user.id).all()
    assert {row.concept_id for row in rows if "Odile" in (row.original_text or "")} == {un_une.id}
