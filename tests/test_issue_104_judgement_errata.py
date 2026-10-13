"""Issue #104: a judgement miss is filed against its sentence, never its buttons.

Walk 2026-10-13: tapping «Muss korrigiert werden» on the correct «Ils sont sympas,
Margaux.» filed an erratum «À corriger» → «Correct», and day 2 asked the learner to
«Schreib richtig, was du gesagt hast» with «Correct» as the answer.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService, AtelierExerciseGenerator
from app.services.error_memory import ErrorMemoryService
from app.services.seance_curriculum import curriculum

LABELS = {"correct", "à corriger"}


@pytest.fixture(scope="module")
def lila_item() -> ib.BankItem:
    """«Lila cherche une grande affiche.» (frame adj-pre), as in test_wp103_forge."""

    bank = ib.ItemBank()
    frame = next(f for unit in bank.templates for f in bank.frames(unit) if f.frame_id == "adj-pre")
    lex = bank.lex
    bindings = {
        "C": next(entry for entry in lex.pool("cast") if "Lila" in str(entry.get("fr"))),
        "N": next(entry for entry in lex.pool("noun") if entry.get("id") == "affiche"),
        "A": next(entry for entry in lex.pool("adj") if entry.get("id") == "grand"),
    }
    return bank.render(frame, bindings)


def _correct(db_session, item, answer, *, concept=None, language="de"):
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service.correct(
        concept=concept, round_name="recognize", mode="classify", exercise_id=f"X:classify:{item['id']}",
        prompt_payload={"items": [item]}, answer_payload={"answers": {item["id"]: answer}},
    )


def _user(db_session) -> User:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    return user


def _remembered(db_session, user, erratum) -> dict | None:
    return ErrorMemoryService(db_session).record_erratum(user=user, erratum=erratum, source_type="atelier")


def _no_labels(erratum: dict) -> None:
    assert erratum["learner_text"].casefold() not in LABELS
    assert erratum["corrected_target"].casefold() not in LABELS
    assert "À corriger" not in erratum["why_wrong"] and "„Correct“" not in erratum["why_wrong"]


def test_a_right_sentence_sorted_a_corriger_names_the_sentence_and_files_nothing(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=True)
    correction = _correct(db_session, item, "À corriger")

    assert correction["verdict"] == "incorrect"
    [erratum] = correction["errata"]
    _no_labels(erratum)
    assert erratum["learner_text"] == "Lila cherche une grande affiche."
    assert erratum["why_wrong"] == "„Lila cherche une grande affiche.“ stimmt so; hier gibt es nichts zu korrigieren."
    assert correction["notes_native"]

    user = _user(db_session)
    assert _remembered(db_session, user, erratum) is None
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0


def test_a_wrong_sentence_sorted_correct_is_filed_as_the_sentence_and_its_fix(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=False)
    correction = _correct(db_session, item, "Correct", language="en")

    [erratum] = correction["errata"]
    _no_labels(erratum)
    assert erratum["learner_text"] == "Lila cherche une grand affiche."
    assert erratum["corrected_target"] == "Lila cherche une grande affiche."
    assert erratum["why_wrong"] == (
        "“Lila cherche une grand affiche.” is not right; it should be “Lila cherche une grande affiche.”."
    )

    user = _user(db_session)
    assert _remembered(db_session, user, erratum) is not None
    row = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert row.original_text == "Lila cherche une grand affiche."
    assert row.correction == "Lila cherche une grande affiche."


def test_a_curated_judgement_skips_the_label_line_of_its_own_concept(db_session):
    """The walk's path: a séance item whose lesson is the concept took the
    «Du hast „À corriger“ gewählt; hier ist „Correct“ nötig.» branch."""

    key = next(key for key, row in curriculum().items() if row["classify_show_correct"])
    row = curriculum()[key]
    concept = GrammarConcept(id=1, external_id=key, name=row["name_en"], category=row["category"],
                             subskill=row["subskill"], core_rule=row["core_rule"], level=row["cefr_level"], language="fr")
    item = AtelierExerciseGenerator(None)._fallback_payload(concept)["recognize"]["classify"]["items"][0]
    assert item["correct_label"] == "Correct"

    [erratum] = _correct(db_session, item, "À corriger", concept=concept)["errata"]
    _no_labels(erratum)
    assert erratum["learner_text"] == item["prompt"]
    assert erratum["remember"] is False


def test_a_relecture_erratum_quoting_the_buttons_is_replaced(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=True)
    service = AtelierCorrectionService(db_session)
    service.explanation_language = "de"
    model_reading = {
        "verdict": "incorrect",
        "errata": [{"item_id": None, "learner_text": "À corriger", "corrected_target": "Correct", "why_wrong": "…"}],
    }
    updated = service._with_judgement_errata(
        None, model_reading, {"items": [item]}, {"answers": {item["id"]: "À corriger"}}
    )
    [erratum] = updated["errata"]
    _no_labels(erratum)
    assert erratum["remember"] is False


def test_a_right_judgement_adds_no_erratum(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=True)
    correction = _correct(db_session, item, "Correct")
    assert correction["verdict"] == "correct"
    assert correction["errata"] == []


def test_an_erratum_filed_before_the_fix_is_never_a_repair_of_a_button() -> None:
    """Rows already stored as «À corriger» → «Correct» get no day-2 step."""

    from app.services import journey_planner as planner
    from app.services.journey_contracts import TargetKind, TargetRef
    from tests.test_journey_planner import _brief

    target = TargetRef(
        kind=TargetKind.ERROR, id="e-104", label_fr="Correct",
        label_native="Du hast „À corriger“ gewählt; hier ist „Correct“ nötig.",
    )
    task = planner.build_recall_task(
        target=target, scenario=_brief(control_language="de"), affordances=[], optional=False,
        learner_text="À corriger",
    )
    assert task is None
