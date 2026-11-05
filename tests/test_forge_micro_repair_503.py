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
