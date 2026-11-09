"""#503: «Copy the correction» on a keyed La Forge round takes the line it asks for.

The placeholder says «Type the corrected line…», and the miss card shows the gap
(«Il a invité»). Only the gap passed; the whole corrected line was refused, because
the keyed branch of ``record_micro_repair`` compared the typed text with one stored
string. The model-judged rounds read the answer in place in the learner's line
(``answer_acceptance.judge_repair``). Both paths now go through that one judge.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierCorrectionService

SOURCE = "il a invite Romy au cinéma samedi dernier."
WHOLE = "Il a invité Romy au cinéma samedi dernier."
GAP = "Il a invité"


def _keyed_miss(db_session, answer: str):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="transform", mode="transform",
        exercise_id="forge-503", verdict="incorrect", score_0_4=0,
        answer_payload={"answers": {"i1": answer}},
        correction_payload={
            "assessment_status": "checked",
            "corrected_answer": {"i1": WHOLE},
            "errata": [{"item_id": "i1", "learner_text": "il a invite", "corrected_target": GAP, "task_error_type": "spelling"}],
        },
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


@pytest.mark.parametrize(
    ("typed", "status"),
    [
        (WHOLE, "ok"),
        ("il a invité Romy au cinéma samedi dernier", "ok"),
        (GAP, "ok"),
        ("invité Romy", "ok"),
        (SOURCE, "no"),
        ("il a invite", "no"),
        ("Il a invité Romy au cinéma", "ok"),
        ("Il a invité Marin au cinéma samedi dernier.", "no"),
    ],
)
def test_a_keyed_repair_takes_the_whole_line_or_its_gap(db_session, typed, status):
    attempt = _keyed_miss(db_session, SOURCE)
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=typed, erratum_index=0)
    assert updated.correction_payload["micro_repairs"]["0"]["status"] == status


@pytest.mark.parametrize("typed", [WHOLE, GAP])
def test_the_line_is_right_when_the_learner_only_typed_the_gap(db_session, typed):
    attempt = _keyed_miss(db_session, "il a invite")
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=typed, erratum_index=0)
    assert updated.correction_payload["micro_repairs"]["0"]["status"] == "ok"


# A fill or choice drill: its key and the learner's answer are only the gap, so the line
# the field asks for is nowhere but in the prompt. Graded by the real keyed corrector.
CANAL_LINE = "Avant-hier, je suis descendu vers le canal."
CANAL_GAP = "je suis descendu"
CANAL_ITEM = {
    "id": "i1",
    "prompt": "Avant-hier, ___ vers le canal.",
    "choices": [CANAL_GAP, "j'ai descendu", "je descends"],
    "correct_answer": CANAL_GAP,
}


def _gap_miss(db_session, item: dict, answer: str, *, others: tuple[dict, ...] = ()):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    prompt_payload = {"items": [*others, item]}
    answer_payload = {"answers": {item["id"]: answer}}
    correction = AtelierCorrectionService(db_session)._correct_recognize(None, "fill", {"items": [item]}, answer_payload)
    assert correction["verdict"] == "incorrect"
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="recognize", mode="fill",
        exercise_id="forge-gap", verdict=correction["verdict"], score_0_4=correction["score_0_4"],
        prompt_payload=prompt_payload, answer_payload=answer_payload, correction_payload=correction,
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def _repair_status(db_session, attempt, typed: str) -> str:
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=typed, erratum_index=0)
    return updated.correction_payload["micro_repairs"]["0"]["status"]


@pytest.mark.parametrize(
    ("typed", "status"),
    [
        # The line the placeholder asks for, the reported case.
        (CANAL_LINE, "ok"),
        ("avant-hier, je suis descendu vers le canal", "ok"),
        # The gap stays right, and so does the gap with its neighbours.
        (CANAL_GAP, "ok"),
        ("Je suis descendu vers le canal.", "ok"),
        # Copying is still checked: the learner's miss, or another line, is refused.
        ("Avant-hier, j'ai descendu vers le canal.", "no"),
        ("j'ai descendu", "no"),
        ("Hier, je suis descendu vers le canal.", "no"),
        ("Avant-hier, je suis descendu vers la gare.", "no"),
        ("Avant-hier, je suis déscendu vers le canal.", "no"),
    ],
)
def test_a_gap_repair_takes_the_whole_line_or_the_gap(db_session, typed, status):
    assert _repair_status(db_session, _gap_miss(db_session, CANAL_ITEM, "j'ai descendu"), typed) == status


@pytest.mark.parametrize("apostrophe", ["'", "‘", "’", "ʼ"])
def test_a_whole_line_is_read_whatever_apostrophe_the_keyboard_typed(db_session, apostrophe):
    item = {
        "id": "i1",
        "prompt": "Aujourd’hui, ___ à la gare.",
        "choices": ["j'ai pris le train", "j'ai prendre le train"],
        "correct_answer": "j'ai pris le train",
    }
    attempt = _gap_miss(db_session, item, "j'ai prendre le train")
    typed = f"Aujourd{apostrophe}hui, j{apostrophe}ai pris le train à la gare."
    assert _repair_status(db_session, attempt, typed) == "ok"


@pytest.mark.parametrize(
    "prompt",
    [
        # The bank's gloss, its nested form, a cue beside the blank, a longer blank.
        "Avant-hier, ___ vers le canal. (The day before yesterday I went down to the canal.)",
        "Avant-hier, ___ vers le canal. (You (informal) went down to the canal.)",
        "Avant-hier, ___ (descendre) vers le canal.",
        "Avant-hier, ____ vers le canal.",
    ],
)
def test_what_is_not_the_line_is_not_asked_for(db_session, prompt):
    attempt = _gap_miss(db_session, {**CANAL_ITEM, "prompt": prompt}, "j'ai descendu")
    assert _repair_status(db_session, attempt, CANAL_LINE) == "ok"


def test_the_line_comes_from_the_item_the_erratum_belongs_to(db_session):
    other = {**CANAL_ITEM, "id": "i0", "prompt": "Ce matin, ___ vers la gare."}
    attempt = _gap_miss(db_session, {**CANAL_ITEM, "id": "i1"}, "j'ai descendu", others=(other,))
    assert _repair_status(db_session, attempt, "Ce matin, je suis descendu vers la gare.") == "no"
    assert _repair_status(db_session, attempt, CANAL_LINE) == "ok"


def test_a_relecture_that_lost_the_item_id_still_takes_the_line(db_session):
    attempt = _gap_miss(db_session, CANAL_ITEM, "j'ai descendu")
    correction = dict(attempt.correction_payload)
    correction["errata"] = [{**correction["errata"][0], "item_id": ""}]
    attempt.correction_payload = correction
    db_session.commit()
    assert _repair_status(db_session, attempt, CANAL_LINE) == "ok"


def test_a_prompt_with_no_single_blank_still_takes_the_gap(db_session):
    attempt = _gap_miss(db_session, {**CANAL_ITEM, "prompt": "Avant-hier, ___ vers ___."}, "j'ai descendu")
    assert _repair_status(db_session, attempt, CANAL_GAP) == "ok"
    assert _repair_status(db_session, attempt, "j'ai descendu") == "no"


def test_copying_the_whole_line_changes_no_verdict(db_session):
    attempt = _gap_miss(db_session, CANAL_ITEM, "j'ai descendu")
    before = (attempt.verdict, attempt.score_0_4, attempt.correction_payload["verdict"], attempt.correction_payload["score_0_4"])
    errata = list(attempt.correction_payload["errata"])
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=CANAL_LINE, erratum_index=0)
    assert (updated.verdict, updated.score_0_4, updated.correction_payload["verdict"], updated.correction_payload["score_0_4"]) == before
    assert updated.correction_payload["errata"] == errata
    # What the card printed stays the key of the repair; the typed line is only recorded.
    assert updated.correction_payload["micro_repairs"]["0"]["target"] == CANAL_GAP
    assert updated.correction_payload["micro_repairs"]["0"]["typed"] == CANAL_LINE
