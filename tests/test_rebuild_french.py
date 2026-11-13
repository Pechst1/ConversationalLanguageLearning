"""#723: a recall rebuild offers a bank that forms French, and never accepts a non-word.

Live walk 12 Nov (day 31, A1.1): «Write what you said, correctly» over «Im suis au
Mistral, Marin.», a bank of «est», «Im», «au», «Mistral,», «Marin.» and no «Je» or
«Il», and «Im est au Mistral, Marin.» marked Correct. The stored erratum's
correction fixed the verb and kept the non-word («Im»), and every reader of the
row used that correction as the answer key as it was stored: the day's rebuild
(both ways in: the learning queue and the errata targets), the Cahier's repair
card and the conversation's self-repair question.

The 12 Nov attempt (#733) dropped such an erratum from the day instead; review asked
for the key to be repaired: the flagged word is the subject of the corrected verb,
so it becomes the pronoun that agrees with it («est» → «Il»). Only a key that cannot
be repaired leaves the day, and a French control erratum still reaches it.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.error_memory import ErrorMemoryService
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
from app.services.journey_learning import (
    _accepted_answers,
    answer_matches,
    evaluate_recall,
    select_learning_candidates,
)
from app.services.journey_planner import plan_journey
from tests.test_journey_planner import _brief

SHOWN = "Im suis au Mistral, Marin."
STORED_KEY = "Im est au Mistral, Marin."
FRENCH_KEY = "Il est au Mistral, Marin."
RULE = "I am, you are: subject pronouns and être"
PRONOUNS = {"je", "il", "j'", "elle", "on", "tu"}


def _tile_texts(task: RecallTask) -> list[str]:
    return [str(tile.get("text_fr") or "") for tile in task.options or []]


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


def _erratum(db_session, user: User, *, shown: str, stored: str, rule: str = RULE) -> UserError:
    concept = GrammarConcept(
        external_id=f"FR_A1_{uuid4().hex[:8]}",
        language="fr",
        name=rule,
        level="A1",
        category="Verbes",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    error = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        error_pattern="subject_pronoun_etre",
        original_text=shown,
        correction=stored,
        why_wrong="«Il» goes with «est».",
        memory_key=f"rebuild-{uuid4().hex[:8]}",
        state="open",
        occurrences=1,
        lapses=0,
        next_review_date=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(error)
    db_session.flush()
    return error


def _rebuild_of(plan, error: UserError) -> RecallTask:
    """The day's rebuild of ``error``: it must exist (an empty day cannot pass)."""

    for step in plan.steps:
        if (
            step.kind is StepKind.RECALL
            and step.private_task is not None
            and step.target is not None
            and step.target.kind is TargetKind.ERROR
            and step.target.id == str(error.id)
        ):
            return step.private_task
    planned = [(step.kind.value, getattr(step.target, "id", None)) for step in plan.steps]
    raise AssertionError(f"the erratum «{SHOWN}» has no rebuild in the day: {planned}")


def _assert_solvable_in_french(db_session, user: User, task: RecallTask) -> None:
    """The done-when of #723 on the built rebuild."""

    tiles = _tile_texts(task)
    folded = {text.strip(" ,.").casefold() for text in tiles}
    assert folded & PRONOUNS, f"the bank has no subject pronoun to build the sentence with: {tiles}"
    assert "im" not in folded, f"the bank offers the non-word «Im»: {tiles}"

    accepted = _accepted_answers(task)
    assert not answer_matches(STORED_KEY, accepted), f"«{STORED_KEY}» (not French) is accepted: {accepted}"
    assert answer_matches(FRENCH_KEY, accepted), f"«{FRENCH_KEY}» is not accepted: {accepted}"

    by_text = {text: tile["id"] for text, tile in zip(tiles, task.options or [], strict=True)}
    in_order = [by_text[word] for word in FRENCH_KEY.split()]
    met = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=in_order),
        assistance=AssistanceLevel.NONE,
    )
    assert met.outcome is TaskOutcome.MET, f"«{FRENCH_KEY}» built from the bank is not MET"
    typed = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=STORED_KEY),
        assistance=AssistanceLevel.NONE,
    )
    assert typed.outcome is not TaskOutcome.MET, f"«{STORED_KEY}» was judged correct"


def test_rebuild_from_the_queue_is_french(db_session) -> None:
    """The learning queue's way in: the erratum as a due item of the day's candidates."""

    user = _user(db_session)
    error = _erratum(db_session, user, shown=SHOWN, stored=STORED_KEY)
    scenario = _brief()
    candidates = select_learning_candidates(db_session, user=user, scenario=scenario, limit=3)
    task = _rebuild_of(plan_journey(scenario=scenario, candidates=candidates), error)
    _assert_solvable_in_french(db_session, user, task)


def test_rebuild_from_the_errata_is_french(db_session) -> None:
    """The errata's way in (WP-24): the erratum as a target of the day."""

    user = _user(db_session)
    error = _erratum(db_session, user, shown=SHOWN, stored=STORED_KEY)
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    task = _rebuild_of(plan_journey(scenario=_brief(), candidates=[], errata_targets=targets), error)
    _assert_solvable_in_french(db_session, user, task)


def test_cahier_repair_card_grades_against_the_french_key(db_session) -> None:
    """The Cahier's repair card reads the same row: «Im est …» does not repair it."""

    user = _user(db_session)
    error = _erratum(db_session, user, shown=SHOWN, stored=STORED_KEY)
    service = ErrorMemoryService(db_session)
    wrong = service.submit_review_attempt(user=user, error_id=error.id, answer_text=STORED_KEY)
    assert wrong is not None and wrong["is_correct"] is False, f"«{STORED_KEY}» repaired the erratum: {wrong}"
    assert "Im" not in str(wrong["feedback"]), wrong["feedback"]
    right = service.submit_review_attempt(user=user, error_id=error.id, answer_text=FRENCH_KEY)
    assert right is not None and right["is_correct"] is True, right


def test_conversation_self_repair_asks_for_the_french_key(db_session) -> None:
    from app.services.journey_conversation import _repairable

    user = _user(db_session)
    error = _erratum(db_session, user, shown=SHOWN, stored=STORED_KEY)
    assert _repairable(error) == (SHOWN, FRENCH_KEY)


def test_answer_key_repairs_or_refuses() -> None:
    from app.services.forge_grading import french_answer_key

    assert french_answer_key(STORED_KEY) == FRENCH_KEY
    assert french_answer_key("Im suis au Mistral.") == "Je suis au Mistral."
    assert french_answer_key("Oui, im ai faim.") == "Oui, j'ai faim."
    assert french_answer_key("Im sont là.") == "Ils sont là."
    # A key that is French already is the key.
    assert french_answer_key("Je suis au Mistral, Marin.") == "Je suis au Mistral, Marin."
    # A capitalised name inside the line is not a foreign word (review of #733, note 4).
    assert french_answer_key("Je travaille chez Müller.") == "Je travaille chez Müller."
    assert french_answer_key("Elle habite à Zürich.") == "Elle habite à Zürich."
    # No verb names the subject: no French key can be derived.
    assert french_answer_key("Je suis im café.") is None
    assert french_answer_key("Im war au Mistral.") is None


def test_an_unrepairable_key_leaves_the_day_but_french_errata_stay(db_session) -> None:
    user = _user(db_session)
    bad = _erratum(db_session, user, shown="Ich bin im café.", stored="Je suis im café.", rule="Prépositions")
    control = _erratum(db_session, user, shown="Il sont au café.", stored="Ils sont au café.")
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    ids = {target.error_id for target in targets}
    assert str(bad.id) not in ids, "an answer key with a non-word is still a target"
    assert str(control.id) in ids, "a French erratum is no longer a target"
