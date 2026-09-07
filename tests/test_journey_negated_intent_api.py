"""R-1 at the assembled API surface: a refusal must not mint success.

The unit regressions in ``tests/test_journey_conversation.py`` pin the grader.
This file pins the *consequences* of the grader's verdict on the surfaces a
learner and the product actually read: the recap's story outcome, the recap's
capability evidence, and ``GET /capabilities/progress``. The defect (R-1) was
that "je ne veux pas de café. je ne veux pas rester en terrasse." was graded
``met`` with the consequence ``served_at_terrace``, which is exactly the input
the evidence rubric and the keepsake minter believe.

Assembled system, real router, no stubbed adapter, no provider: identical setup
to ``tests/test_journey_end_to_end.py``, whose driver and fixtures are reused.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures are used by name
    CAFE_WORDS,
    Clock,
    Driver,
    assembled_client,
    clock,
    journey_enabled,
    learner_id,
    register,
    seed_due_vocabulary,
    step_of,
)

NEGATION = "Je ne veux pas de café. Je ne veux pas rester en terrasse."
REFUSAL = "Je ne veux rien, merci."


def _play(client: TestClient, db: Session, answer: str) -> Driver:
    email = f"r1-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(client, email)
    seed_due_vocabulary(db, learner_id(db, email), CAFE_WORDS)
    driver = Driver(client, headers, db=db)
    driver.create(expect=(201,))
    assert driver.journey["scenario"]["scenario_key"] == "order_at_cafe"
    driver.play(answer=answer)
    driver.finish("complete" if driver.journey["current_step_id"] is None else "early")
    return driver


@pytest.mark.parametrize("answer", [NEGATION, REFUSAL])
def test_a_refusal_mints_no_capability_evidence_and_no_reward(
    assembled_client: TestClient,  # noqa: F811
    journey_enabled: None,  # noqa: F811
    clock: Clock,  # noqa: F811
    db_session: Session,
    answer: str,
) -> None:
    driver = _play(assembled_client, db_session, answer)
    recap = driver.journey["recap"]

    assert recap["objective_outcome"] != "met"
    for evidence in recap["capability_evidence"]:
        assert evidence["state"] not in ("independent_once", "used_again_later"), (
            f"a refused order was credited as {evidence['state']}"
        )
    assert not recap["collectible_ids"], "a refusal must not mint a keepsake"

    progress = driver.capabilities()["capabilities"]
    cafe = next(c for c in progress if c["capability_key"] == "order_at_cafe")
    assert cafe["state"] not in ("independent_once", "used_again_later")


def test_a_refusal_is_never_resolved_as_a_served_order(
    assembled_client: TestClient,  # noqa: F811
    journey_enabled: None,  # noqa: F811
    clock: Clock,  # noqa: F811
    db_session: Session,
) -> None:
    driver = _play(assembled_client, db_session, NEGATION)
    recap = driver.journey["recap"]

    story = recap["story_outcome"] or {}
    assert story.get("outcome_key") in (None, "not_ordered"), story
    assert not story.get("callback_fr"), (
        "a refused order must not leave a grounded callback for tomorrow"
    )

    resolution = step_of(driver.journey, "resolution")
    prompt = resolution["prompt"] if resolution else {}
    for field in ("character_line_fr", "summary_native"):
        text = str(prompt.get(field) or "").lower()
        assert "terrasse" not in text and "terrace" not in text, prompt
