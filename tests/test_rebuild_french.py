"""#723: a recall rebuild never offers a bank that cannot form French, never accepts a non-word.

Live walk 12 Nov (day 31, A1.1): «Write what you said, correctly» over «Im suis au
Mistral, Marin.», a bank of «est», «Im», «au», «Mistral,», «Marin.» and no «Je» or
«Il», and «Im est au Mistral, Marin.» marked Correct. The stored erratum's
correction fixed the verb and kept the non-word («Im»), and the planner turned that
correction into the tile bank and the answer key without asking whether it was
French. The Forge has refused such a key since #348; the two ways a stored\nerratum reaches the day (the learning queue and the errata targets) did not.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    StepKind,
    TargetKind,
    TaskOutcome,
)
from app.services.journey_errata import errata_targets_for_user
from app.services.journey_learning import evaluate_recall, select_learning_candidates
from app.services.journey_planner import plan_journey
from tests.test_journey_planner import _brief

SHOWN = "Im suis au Mistral, Marin."
STORED_KEY = "Im est au Mistral, Marin."
RULE = "I am, you are: subject pronouns and être"
PRONOUNS = {"je", "il", "j'", "elle", "on", "tu"}


def _tile_texts(task: RecallTask) -> list[str]:
    return [str(tile.get("text_fr") or "") for tile in task.options or []]


def _assert_solvable_in_french(db_session, user, task: RecallTask) -> None:
    """The done-when of #723 on one built rebuild: a pronoun tile, no non-word, and
    the non-word answer judged «Not yet»."""

    tiles = _tile_texts(task)
    if task.task_type in {"tiles", "word_bank", "unscramble"}:
        folded = {text.strip(" ,.").casefold() for text in tiles}
        assert folded & PRONOUNS, f"the bank has no subject pronoun to build the sentence with: {tiles}"
        assert "im" not in folded, f"the bank offers a non-word: {tiles}"
    verdict = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=STORED_KEY),
        assistance=AssistanceLevel.NONE,
    )
    assert verdict.outcome is not TaskOutcome.MET, (
        f"«{STORED_KEY}» (not French) was judged correct: accepted {task.accepted_answers}"
    )


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"rebuild-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _stored_erratum(db_session) -> User:
    """The walk's erratum: «Im suis au Mistral, Marin.» stored with the correction
    «Im est au Mistral, Marin.» under the rule of the day, and due."""

    user = _user(db_session)
    concept = GrammarConcept(
        external_id=f"FR_A1_{uuid4().hex[:8]}",
        language="fr",
        name=RULE,
        level="A1",
        category="Verbes",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=concept.id,
            error_category="grammar",
            error_pattern="subject_pronoun_etre",
            original_text=SHOWN,
            correction=STORED_KEY,
            why_wrong="«Il» goes with «est».",
            memory_key=f"rebuild-{uuid4().hex[:8]}",
            state="open",
            occurrences=1,
            lapses=0,
            next_review_date=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.flush()
    return user


def _assert_day_is_french(db_session, user, plan) -> None:
    for step in plan.steps:
        if step.kind is not StepKind.RECALL or step.private_task is None:
            continue
        shown = json.dumps(step.public_prompt, ensure_ascii=False)
        assert "Im" not in _tile_texts(step.private_task), f"a recall offers the non-word «Im»: {shown}"
        if step.target is not None and step.target.kind is TargetKind.ERROR:
            _assert_solvable_in_french(db_session, user, step.private_task)


def test_bad_key_from_the_queue(db_session) -> None:
    """The learning queue's way in: the erratum as a due item of the day's candidates."""

    user = _stored_erratum(db_session)
    scenario = _brief()
    candidates = select_learning_candidates(db_session, user=user, scenario=scenario, limit=3)
    _assert_day_is_french(db_session, user, plan_journey(scenario=scenario, candidates=candidates))


def test_bad_key_from_the_errata(db_session) -> None:
    """The errata's way in (WP-24): the erratum as a target of tomorrow's scene."""

    user = _stored_erratum(db_session)
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    _assert_day_is_french(db_session, user, plan_journey(scenario=_brief(), candidates=[], errata_targets=targets))
