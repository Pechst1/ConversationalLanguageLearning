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


# #779: the miss screen asks for one copy per corrected line (``missCorrections`` and
# ``repairState`` in web-frontend/lib/repair-parts.ts). A word-bank miss whose erratum
# came back twice names one line twice; the screen shows one field, under erratum 0, and
# calls the line mended once that copy is accepted. The server must count lines the same
# way, or the delayed retest the copy earns is never queued.
LINE_779 = "Je suis à la rédaction."
ERRATUM_779 = {
    "item_id": "i1",
    "learner_text": "suis la rédaction à Je es.",
    "corrected_target": LINE_779,
    "task_error_type": "word_order",
}


def _miss_779(db_session, errata):
    attempt = _keyed_miss(db_session, "suis la rédaction à Je es.")
    attempt.correction_payload = {
        "assessment_status": "checked",
        "corrected_answer": {"i1": LINE_779},
        "errata": errata,
    }
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_one_copy_of_a_line_named_twice_queues_the_retest(db_session):
    attempt = _miss_779(db_session, [ERRATUM_779, dict(ERRATUM_779)])
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=LINE_779, erratum_index=0)
    payload = updated.correction_payload
    assert payload["micro_repairs"]["0"]["status"] == "ok"
    assert (payload.get("retest") or {}).get("status") == "queued", (
        "the screen calls the line mended after its one copy; the server still waits for a second copy it never asks for"
    )


def test_two_notes_on_one_line_typed_differently_count_as_one_line(db_session):
    # A si-type word bank: two notes on one line, the second with other typography.
    other = {**ERRATUM_779, "corrected_target": "je suis à la rédaction", "task_error_type": "grammar"}
    attempt = _miss_779(db_session, [ERRATUM_779, other])
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=LINE_779, erratum_index=0)
    assert (updated.correction_payload.get("retest") or {}).get("status") == "queued", "one line, one copy"


def test_two_different_lines_still_need_both_copies(db_session):
    second = {**ERRATUM_779, "item_id": "i2", "learner_text": "tu es a Paris", "corrected_target": "Tu es à Paris."}
    attempt = _miss_779(db_session, [ERRATUM_779, second])
    service = AtelierCorrectionService(db_session)
    first = service.record_micro_repair(attempt=attempt, text=LINE_779, erratum_index=0)
    assert not first.correction_payload.get("retest"), "one line of two is not the whole repair"
    both = service.record_micro_repair(attempt=first, text="Tu es à Paris.", erratum_index=1)
    assert both.correction_payload["micro_repairs"]["1"]["status"] == "ok"
    assert (both.correction_payload.get("retest") or {}).get("status") == "queued"


def test_the_server_names_a_line_the_way_the_screen_folds_it():
    # ``fold`` in web-frontend/lib/repair-parts.ts: typography folded, accents kept.
    from app.services.forge_grading import retype_line_key

    assert retype_line_key(LINE_779) == retype_line_key("je suis à la rédaction") == "je suis à la rédaction"
    assert retype_line_key("S’il pleut, je resterai.") == retype_line_key("s'il pleut je resterai")
    assert retype_line_key("« Tu es là ? »") == "tu es là"
    assert retype_line_key("tâches") != retype_line_key("taches")


def test_a_one_word_fix_beside_a_line_does_not_hold_the_retest(db_session):
    # The screen gives a one-word fix no copy field (``isRepairableLine``): the line's copy
    # is the whole repair it asks for, so it is the whole repair the server waits for.
    word = {"item_id": "i2", "learner_text": "taches", "corrected_target": "tâches", "task_error_type": "spelling"}
    attempt = _miss_779(db_session, [ERRATUM_779, word])
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=LINE_779, erratum_index=0)
    assert (updated.correction_payload.get("retest") or {}).get("status") == "queued", (
        "the screen asks for no copy of a one-word fix; the server waits for one"
    )
