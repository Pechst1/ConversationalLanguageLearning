"""#697 (child of #146) — a spelling slip carries no grammar rule.

Explore walk 11 Nov: the Courrier's basic check fixed «A bientot» → «A bientôt» in a letter
that practised the passé composé, and the erratum was stored under the passé composé
(`concept_id = 39`). Day 2's recall printed «Rule: Passé composé with avoir» over the accent,
and a right «bientôt» counted as producing that rule unaided and moved its review. The
Courrier fell back on the letter's own rule for any slip it could not name; the scene fell
back on its task's rule the same way. A slip whose fix is only an accent, an apostrophe or
typography (or that is filed as spelling) is now stored with no rule, on every surface.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.error_memory import ErrorMemoryService
from app.services.journey_errata import build_errata_target
from app.services.missions import MissionCorrectionService
from tests.test_missions import _ExplodingMissionLLM, _mission_for_correction


def _passe_compose(db_session) -> GrammarConcept:
    found = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A22_PC_AVOIR").one_or_none()
    if found is not None:
        return found
    unit = GrammarConcept(
        external_id="FR2_A22_PC_AVOIR",
        language="fr",
        name="Passé composé with avoir, regular and irregular participles",
        level="A2",
        category="Verbs",
        active=True,
    )
    db_session.add(unit)
    db_session.commit()
    return unit


def _user(db_session) -> User:
    user = User(id=uuid4(), email=f"spelling-697-{uuid4().hex[:6]}@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.commit()
    return user


def test_a_letters_accent_slip_is_stored_under_no_rule_and_recall_names_none(db_session):
    rule = _passe_compose(db_session)
    user = _user(db_session)
    mission = _mission_for_correction()
    mission.user_id = user.id
    # The letter practises the passé composé, as on 11 Nov.
    mission.selected_concept_ids = [rule.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())

    correction = service.correct_submission(
        user=user,
        mission=mission,
        text="Merci Marin, je passe demain matin. A bientot, Sam",
        mode="letter",
        near_realtime=True,
    )
    by_span = {item["learner_text"].casefold(): item for item in correction["errata"]}
    assert "bientot" in by_span, by_span
    assert by_span["bientot"]["concept_id"] is None, "the accent slip was filed under the letter's rule"

    service.persist_errata(user=user, mission=mission, correction=correction, mode="letter", source_id="letter-697")
    row = db_session.query(UserError).filter_by(user_id=user.id).filter(UserError.original_text.ilike("%bientot%")).one()
    assert row.concept_id is None, f"«bientot» → «bientôt» is stored as a slip in rule {row.concept_id}"
    target = build_errata_target(row)
    assert target is not None
    assert target.rule is None, f"recall prints «Rule: {target.rule}» over an accent"
    assert target.as_candidate().metadata.get("concept_id") is None, "a right «bientôt» would credit the letter's rule"


def test_no_entrance_lends_its_rule_to_a_spelling_slip(db_session):
    """The scene passes its task's rule, the journey its step's: neither is the slip's."""

    rule = _passe_compose(db_session)
    user = _user(db_session)
    memory = ErrorMemoryService(db_session)
    for index, (wrong, right) in enumerate([("tres", "très"), ("jai", "j'ai"), ("A bientot", "A bientôt")]):
        update = memory.record_erratum(
            user=user,
            erratum={
                "learner_text": wrong,
                "corrected_target": right,
                "display_label": "Correction",
                "task_error_type": "grammar_target",
                "severity": 2,
            },
            source_type="graphic_novel",
            concept_id=rule.id,
            source_payload={"scene_id": f"scene-697-{index}"},
        )
        assert update is not None
        assert update["concept_id"] is None, f"«{wrong}» → «{right}» was filed under the scene task's rule"


def test_an_accent_that_is_grammar_keeps_its_rule(db_session):
    rule = _passe_compose(db_session)
    user = _user(db_session)
    update = ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "learner_text": "j'ai mange",
            "corrected_target": "j'ai mangé",
            "display_label": "Correction",
            "task_error_type": "orthography",
            "error_category": "spelling",
            "severity": 2,
        },
        source_type="graphic_novel",
        concept_id=rule.id,
        source_payload={"scene_id": "scene-697-participle"},
    )
    assert update is not None
    assert update["concept_id"] == rule.id, "a participle's «é» is the passé composé, even when called spelling"
