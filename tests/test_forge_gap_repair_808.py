"""#808: «Copy the correction» after a typed-gap miss takes the corrected line.

The box asks for «the corrected line». On a gap item («L'été dernier, ___ un
article.») the keyed grader stores the gap's answer («tu as écrit») as both the
erratum's target and the item's corrected answer, and the learner's own text is
only what they put in the gap. ``record_micro_repair`` had no line to read the
answer against, so the whole right line was refused and only the gap passed.

The miss here is graded by the séance's own keyed grader (``_correct_recognize``),
so the attempt holds what a real La Forge miss holds.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierCorrectionService

ITEM = {
    "id": "pc-fill-808",
    "prompt": "L'été dernier, ___ un article.",
    "choices": ["tu as écrit", "tu écrivais", "tu écris"],
    "correct_answer": "tu as écrit",
    "accepted_answers": ["tu as écrit"],
    "meaning": "Last summer, you wrote an article.",
}
LINE = "L'été dernier, tu as écrit un article."

WORD_BANK = {
    "id": "pc-build-808",
    "prompt": "Build: Last Saturday, she worked on the editing.",
    "answer_tokens": ["Samedi", "dernier,", "elle", "a", "travaillé", "à", "la", "rédaction."],
    "correct_answer": "Samedi dernier, elle a travaillé à la rédaction.",
}


def _miss(db_session, item: dict, answer: str, mode: str = "fill") -> AtelierAttempt:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    service = AtelierCorrectionService(db_session)
    prompt_payload = {"round": "recognize", "mode": mode, "items": [item], "item_id": item["id"]}
    answer_payload = {"answers": {item["id"]: answer}}
    correction = service._correct_recognize(None, mode, prompt_payload, answer_payload)
    assert correction["verdict"] == "incorrect"
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="recognize", mode=mode,
        exercise_id=f"forge:recognize:{mode}:{item['id']}", verdict="incorrect", score_0_4=0,
        prompt_payload=prompt_payload, answer_payload=answer_payload,
        correction_payload={**correction, "assessment_status": "checked"},
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def _copied(db_session, attempt: AtelierAttempt, typed: str) -> str:
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=typed, erratum_index=0)
    return updated.correction_payload["micro_repairs"]["0"]["status"]


def _status(db_session, item: dict, typed: str, answer: str = "tu as écrivé") -> str:
    return _copied(db_session, _miss(db_session, item, answer), typed)


@pytest.mark.parametrize("typed", [LINE, "L’été dernier, tu as écrit un article.", "tu as écrit"], ids=["line", "curly", "gap"])
def test_line_or_gap_copied(db_session, typed):
    assert _status(db_session, ITEM, typed) == "ok", f"«{typed}» is the corrected line the box asks for"


@pytest.mark.parametrize("typed", ["L'été dernier, tu as écrivé un article.", "tu as écrivé", "L'été dernier, tu écris un article."], ids=["line", "gap", "other"])
def test_wrong_refused(db_session, typed):
    assert _status(db_session, ITEM, typed) == "no"


def test_glossed_gap(db_session):
    """A bank fill may carry its meaning in brackets after the French; that is not the line."""

    glossed = {**ITEM, "id": "pc-fill-808-gloss", "prompt": "L'été dernier, ___ un article. (Last summer, you wrote an article.)"}
    assert _status(db_session, glossed, LINE) == "ok"
    assert _status(db_session, glossed, "tu as écrit") == "ok"


def test_gap_typed_whole(db_session):
    """A learner who typed the whole sentence into the gap is not given a doubled line."""

    assert _status(db_session, ITEM, LINE, answer="L'été dernier, tu as écrivé un article.") == "ok"
    assert _status(db_session, ITEM, "tu as écrit", answer="L'été dernier, tu as écrivé un article.") == "ok"


@pytest.mark.parametrize(
    ("item", "mode", "answer", "whole"),
    [
        (ITEM, "fill", "tu as écrivé", LINE),
        (WORD_BANK, "word_bank", "Samedi dernier, elle a travaillée à la rédaction.", WORD_BANK["correct_answer"]),
    ],
    ids=["fill", "build"],
)
def test_every_box(db_session, item, mode, answer, whole):
    """Guard (#808): whatever keyed item shows the box, its corrected part and the full line both count."""

    part = _miss(db_session, item, answer, mode).correction_payload["errata"][0]["corrected_target"]
    assert _copied(db_session, _miss(db_session, item, answer, mode), whole) == "ok"
    assert _copied(db_session, _miss(db_session, item, answer, mode), part) == "ok"
