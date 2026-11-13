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


def test_letter_accent_slip(db_session):
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


def test_no_lent_rule(db_session):
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


def test_grammar_accent_kept(db_session):
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


def _er_spelling_unit(db_session) -> GrammarConcept:
    found = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A12_ER_SPELLING").one_or_none()
    if found is not None:
        return found
    unit = GrammarConcept(
        external_id="FR2_A12_ER_SPELLING",
        language="fr",
        name="Les verbes en -er qui changent : nous mangeons, j'achète, j'appelle",
        level="A1",
        category="Verbs",
        active=True,
    )
    db_session.add(unit)
    db_session.commit()
    return unit


def test_stem_change_kept(db_session):
    """#734 review: «j'achete» → «j'achète» is the -er stem-change unit's slip, not spelling."""

    unit = _er_spelling_unit(db_session)
    user = _user(db_session)
    update = ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "learner_text": "j'achete du pain",
            "corrected_target": "j'achète du pain",
            "display_label": "Correction",
            "task_error_type": "grammar_target",
            "concept_id": unit.id,
            "severity": 2,
        },
        source_type="graphic_novel",
        concept_id=unit.id,
        source_payload={"scene_id": "scene-697-achete"},
    )
    assert update is not None
    assert update["concept_id"] == unit.id, "the stem-change unit lost its own slip «j'achete»"


def test_letter_stem_change_kept(db_session):
    """The letter practises the stem-change unit and the corrector named no rule: the
    fallback still files «je préfere» under it, because that accent is the unit."""

    unit = _er_spelling_unit(db_session)
    mission = _mission_for_correction()
    mission.selected_concept_ids = [unit.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    normalized = service._normalize_erratum(
        {"learner_text": "je préfere", "corrected_target": "je préfère", "error_category": "spelling"},
        mission,
    )
    assert normalized["concept_id"] == unit.id, "«je préfere» lost the stem-change unit"


def test_named_stem_unit_wins(db_session):
    unit = _er_spelling_unit(db_session)
    mission = _mission_for_correction()
    mission.selected_concept_ids = [unit.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    normalized = service._normalize_erratum(
        {
            "learner_text": "j'achete",
            "corrected_target": "j'achète",
            "external_id": "FR2_A12_ER_SPELLING",
            "error_category": "grammar",
        },
        mission,
    )
    assert normalized["concept_id"] == unit.id


def test_named_rule_wins(db_session):
    """The guard only blocks the letter's fallback: a named rule (external_id) stands."""

    rule = _passe_compose(db_session)
    other = _er_spelling_unit(db_session)
    mission = _mission_for_correction()
    mission.selected_concept_ids = [other.id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    normalized = service._normalize_erratum(
        {"learner_text": "tres", "corrected_target": "très", "external_id": "FR2_A22_PC_AVOIR", "error_category": "spelling"},
        mission,
    )
    assert normalized["concept_id"] == rule.id
    unnamed = service._normalize_erratum(
        {"learner_text": "tres", "corrected_target": "très", "error_category": "spelling"}, mission
    )
    assert unnamed["concept_id"] is None, "«tres» → «très» borrowed the letter's rule"


def test_stem_changes_are_grammar(db_session):
    rule = _passe_compose(db_session)
    memory = ErrorMemoryService(db_session)
    user = _user(db_session)
    for index, (wrong, right) in enumerate(
        [
            ("j'achete du pain", "j'achète du pain"),
            ("je préfere", "je préfère"),
            ("il préfére", "il préfère"),
            ("je me leve tôt", "je me lève tôt"),
            ("tu esperes", "tu espères"),
        ]
    ):
        update = memory.record_erratum(
            user=user,
            erratum={"learner_text": wrong, "corrected_target": right, "task_error_type": "grammar_target", "severity": 2},
            source_type="graphic_novel",
            concept_id=rule.id,
            source_payload={"scene_id": f"scene-697-stem-{index}"},
        )
        assert update is not None
        assert update["concept_id"] == rule.id, f"«{wrong}» → «{right}» is a verb's stem, not spelling"


def test_scene_no_stamp(db_session):
    """The Feuilleton's model-free pass stamped the task's rule on every slip it found."""

    from app.services.graphic_novel import GraphicNovelCorrectionService

    rule = _passe_compose(db_session)
    service = GraphicNovelCorrectionService.__new__(GraphicNovelCorrectionService)
    service.db = db_session
    result = service._short_sentence_not_read(task={"concept_id": rule.id}, text="A bientot, je suis tres content.")
    accent = [
        item
        for item in result.get("errata") or []
        if any(word in str(item.get("learner_text") or "").casefold() for word in ("bientot", "tres"))
    ]
    assert accent, result.get("errata")
    assert all(item.get("concept_id") is None for item in accent), [
        (item.get("learner_text"), item.get("concept_id")) for item in accent
    ]
