"""WP-36 — the character prompts self-repair before it corrects.

Explicit correction produced uptake in 50 % of cases against 31 % for a recast
(Lyster & Ranta 1997), and *output-pushing* prompts beat input-providing
feedback for accuracy (Lyster & Saito 2010; Li 2010; Brown 2016). The product
consequence, and what this file pins:

1. **The question comes first.** A learner who repeats one of their own recorded
   mistakes is asked about it — « Pardon, un ou une café ? » — not handed the
   answer. The correction is what a *failed* repair earns.
2. **The loop closes.** A repair that works is booked against WP-24's lifecycle
   through ``review_error``; a repair that fails becomes the explicit
   correction, chosen by WP-05's own ``select_foreground_correction``.
3. **It is bounded.** One prompt per scene, never on the last turn, never for a
   mistake the learner has never been shown an explanation for — and nothing at
   all changes for a learner who has no errata.

Everything here is deterministic: ``ATELIER_LLM_ENABLED`` is false in
``tests/conftest.py`` and no test in this file reaches a provider.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.user import User
from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services import pragmatics
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_OPEN,
    ErrorMemoryService,
)
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    Correction,
    InputMode,
    TaskOutcome,
)
from app.services.learner_copy import LEARNER_COPY, SUPPORTED_COPY_LANGUAGES

WRONG = "une café"
RIGHT = "un café"
LABEL = "Le genre des noms"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _user(db_session: Session, *, native: str = "en") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@wp36.test",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _brief(db_session: Session, user: User, key=CapabilityKey.ORDER_AT_CAFE):
    return jc_content.resolve_scenario_brief(db_session, user=user, scenario_key=key)


def record(
    db_session: Session,
    user: User,
    *,
    wrong: str = WRONG,
    right: str = RIGHT,
    label: str = LABEL,
    why: str = "café is masculine",
    source_type: str = "daily_journey",
    foreground: bool = True,
    task_type: str | None = None,
) -> UserError:
    """One mistake, recorded the way the product records one."""

    ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "display_label": label,
            "learner_text": wrong,
            "corrected_target": right,
            "why_wrong": why,
            "repair_hint": right,
            "task_error_type": task_type or label,
            "severity": 2,
        },
        source_type=source_type,
        source_payload={"foreground": foreground} if foreground else None,
    )
    db_session.commit()
    error = (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.display_label == label)
        .order_by(UserError.created_at.desc())
        .first()
    )
    assert error is not None
    error.state = ERROR_STATE_OPEN
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()
    db_session.refresh(error)
    return error


def evaluate(db_session, user, brief, text, *, turn_index=0, history=None, task=None):
    return jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=task or brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        turn_index=turn_index,
        assistance=AssistanceLevel.NONE,
        history=history,
    )


def exchange(learner: str, character: str) -> list[dict]:
    """One stored turn pair, exactly as ``daily_journey`` persists it."""

    return [{"learner": learner, "character": character}]


# ---------------------------------------------------------------------------
# 1. The prompt
# ---------------------------------------------------------------------------


def test_a_repeated_mistake_is_asked_about_instead_of_being_corrected(db_session):
    """The evidence's whole point: elicit the form, do not supply it."""

    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)

    result = evaluate(db_session, user, brief, "Bonjour, je voudrais une café, s'il vous plaît.")

    assert result.character_reply_fr.endswith("Pardon, un ou une café ?")
    assert result.needs_repair is True, "the scene must keep a turn for the repair"
    assert result.correction is None, "a correction here would hand over the answer"
    assert result.consequence is None, "a scene that just asked a question has not ended"
    assert result.turn_consumed is True


def test_the_question_is_ordered_alphabetically_so_its_shape_never_leaks_the_answer(db_session):
    """Correct-first would teach the learner to always pick the first option."""

    question, kind = jc.self_repair_question(
        wrong_fr="une café", corrected_fr="un café", register="vous"
    )
    assert (question, kind) == ("Pardon, un ou une café ?", "choice")
    # The same pair the other way round: the *wrong* form now comes first, which
    # is exactly what a learner must not be able to rely on.
    question, _kind = jc.self_repair_question(
        wrong_fr="un maison", corrected_fr="une maison", register="vous"
    )
    assert question == "Pardon, un ou une maison ?"


def test_a_difference_wider_than_one_word_asks_for_the_sentence_again(db_session):
    """An alternative question listing two clauses would be a reading exercise."""

    for register, expected in (
        ("vous", "Pardon ? Vous pouvez le redire autrement ?"),
        ("tu", "Pardon ? Tu peux le redire autrement ?"),
    ):
        question, kind = jc.self_repair_question(
            wrong_fr="je suis allé", corrected_fr="j'ai été", register=register
        )
        assert (question, kind) == (expected, "repetition")


def test_un_and_une_are_never_confused_by_a_fuzzy_match(db_session):
    """``answer_matches`` accepts a 0.92 ratio, under which « un » *is* « une »."""

    assert jc._contains_phrase("je voudrais une café", "une café") is True
    assert jc._contains_phrase("je voudrais une café", "un café") is False
    assert jc._contains_phrase("je voudrais un café", "une café") is False
    assert jc._contains_phrase("un CAFÉ, merci", "un cafe") is True


# ---------------------------------------------------------------------------
# 2. The repair, and what it books
# ---------------------------------------------------------------------------


def test_a_successful_repair_is_recorded_as_a_correct_repair(db_session):
    user = _user(db_session)
    error = record(db_session, user)
    brief = _brief(db_session, user)
    before = error.next_review_date

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    result = evaluate(
        db_session,
        user,
        brief,
        "Pardon, un café au comptoir, s'il vous plaît.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )

    db_session.refresh(error)
    assert error.mastery_streak == 1, "one repair on one day is one step, not three"
    assert error.state == "repairing"
    assert error.next_review_date > before
    # The repair itself is not a punishment: nothing is corrected, nothing asks
    # for another turn.
    assert result.correction is None
    assert result.needs_repair is False


def test_a_failed_repair_yields_the_explicit_correction(db_session):
    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    result = evaluate(
        db_session,
        user,
        brief,
        "Oui, une café en terrasse.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )

    assert result.correction is not None
    assert result.correction.span_fr == "une café", "the span comes from *this* turn"
    assert result.correction.span_fr in "Oui, une café en terrasse."
    assert result.correction.corrected_fr == "un café"
    assert "un café" in result.correction.note_native
    assert "café is masculine" in result.correction.note_native
    assert result.needs_repair is False, "the prompt is spent; the scene may end"


@pytest.mark.parametrize(
    ("native", "needle"),
    [("en", "it is “un café”"), ("de", "Es heißt „un café“"), ("fr", "on dit « un café »")],
)
def test_the_explicit_correction_is_written_in_the_learners_own_language(
    db_session, native, needle
):
    user = _user(db_session, native=native)
    record(db_session, user, why="")
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    result = evaluate(
        db_session,
        user,
        brief,
        "Une café, oui.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )
    assert result.correction is not None
    assert needle in result.correction.note_native


def test_an_ignored_question_credits_nothing_and_invents_no_correction(db_session):
    """No uptake is a real outcome. It is not a repair and it is not a lapse."""

    user = _user(db_session)
    error = record(db_session, user)
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    result = evaluate(
        db_session,
        user,
        brief,
        "Il fait beau aujourd'hui.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )

    db_session.refresh(error)
    assert error.mastery_streak in (0, None)
    assert result.correction is None


def test_a_replayed_repair_cannot_advance_the_streak_twice(db_session):
    """WP-24 measures retention across nights; two calls in one sitting are one."""

    user = _user(db_session)
    error = record(db_session, user)
    brief = _brief(db_session, user)
    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    history = exchange("Je voudrais une café.", first.character_reply_fr)

    for _ in range(3):
        evaluate(db_session, user, brief, "Un café, merci.", turn_index=1, history=history)

    db_session.refresh(error)
    assert error.mastery_streak == 1


# ---------------------------------------------------------------------------
# 3. The bounds
# ---------------------------------------------------------------------------


def test_at_most_one_prompt_per_scene(db_session):
    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    assert "Pardon" in first.character_reply_fr

    second = evaluate(
        db_session,
        user,
        brief,
        "Une café en terrasse.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )
    assert "Pardon, un ou une café ?" not in (second.character_reply_fr or "")


def test_the_last_turn_is_never_spent_on_a_question(db_session):
    """A question nobody can answer is worse than no question at all."""

    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)
    task = brief.response_task
    last = jc.turn_budget(task) - 1

    result = evaluate(db_session, user, brief, "Une café.", turn_index=last)

    assert jc.remaining_turns(task, last) == 0
    assert "Pardon" not in (result.character_reply_fr or "")
    decision = jc.feedback_decision(
        db_session,
        user=user,
        scenario=brief,
        task=task,
        text="Une café.",
        turn_index=last,
        history=None,
    )
    assert decision.prompt is None and decision.reason == "last_turn"


def test_a_mistake_the_learner_was_never_shown_is_never_prompted_on(db_session):
    """A background transcript scan is not feedback; prompting on it is a quiz."""

    user = _user(db_session)
    silent = record(db_session, user, source_type="audio", foreground=False)
    brief = _brief(db_session, user)

    assert jc._erratum_is_explained(silent) is False
    result = evaluate(db_session, user, brief, "Je voudrais une café.")
    assert "Pardon" not in (result.character_reply_fr or "")

    # Once the learner has actually reviewed the repair card, it is fair game.
    ErrorMemoryService(db_session).review_error(
        user=user, error_id=silent.id, rating=2, repaired=False
    )
    db_session.commit()
    db_session.refresh(silent)
    assert jc._erratum_is_explained(silent) is True
    assert "Pardon, un ou une café ?" in evaluate(
        db_session, user, brief, "Je voudrais une café."
    ).character_reply_fr


def test_an_erratum_with_no_stored_explanation_is_never_prompted_on(db_session):
    user = _user(db_session)
    error = record(db_session, user, why="")
    error.why_wrong = None
    error.context_snippet = None
    error.repair_hint = None
    db_session.commit()
    brief = _brief(db_session, user)

    assert jc._erratum_is_explained(error) is False
    assert "Pardon" not in (
        evaluate(db_session, user, brief, "Je voudrais une café.").character_reply_fr or ""
    )


def test_an_accent_only_erratum_is_skipped_rather_than_asked_about(db_session):
    """Folding drops accents, so both options would read identically."""

    user = _user(db_session)
    record(db_session, user, wrong="a Paris", right="à Paris", label="La préposition")
    brief = _brief(db_session, user)
    result = evaluate(db_session, user, brief, "Un café a Paris.")
    assert "Pardon" not in (result.character_reply_fr or "")


# ---------------------------------------------------------------------------
# 4. A learner with no errata is scored exactly as before
# ---------------------------------------------------------------------------


def test_nothing_changes_for_a_learner_with_no_open_errata(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)
    text = "Bonjour, je voudrais un café en terrasse, s'il vous plaît."

    decision = jc.feedback_decision(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        text=text,
        turn_index=0,
        history=None,
    )
    assert decision.is_empty and decision.reason == "no_open_errata"

    result = evaluate(db_session, user, brief, text)
    # The policy hands the same object straight back — the strongest form of
    # "this turn was not touched" available.
    assert (
        jc.apply_feedback_policy(
            result,
            db_session,
            user=user,
            task=brief.response_task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
            turn_index=0,
            decision=decision,
        )
        is result
    )
    assert result.outcome is TaskOutcome.MET
    assert result.consequence is not None
    assert result.needs_repair is False
    assert "Pardon" not in (result.character_reply_fr or "")


def test_an_erratum_that_did_not_recur_changes_nothing_either(db_session):
    """The grading of two identical answers must not depend on old mistakes."""

    clean = _user(db_session)
    burdened = _user(db_session)
    record(db_session, burdened)
    text = "Bonjour, je voudrais un café en terrasse, s'il vous plaît."

    first = evaluate(db_session, clean, _brief(db_session, clean), text)
    second = evaluate(db_session, burdened, _brief(db_session, burdened), text)

    assert first.outcome is second.outcome
    assert first.character_reply_fr == second.character_reply_fr
    assert first.correction == second.correction
    assert first.needs_repair == second.needs_repair
    assert first.consequence == second.consequence


# ---------------------------------------------------------------------------
# 5. WP-33's advisory findings finally reach the learner
# ---------------------------------------------------------------------------


def test_something_finally_knows_which_turn_is_the_last_one(db_session):
    """WP-33 §7.3: ``assess_register(is_closing_turn=…)`` had no caller."""

    user = _user(db_session)
    brief = _brief(db_session, user)
    task = brief.response_task

    assert jc.is_closing_turn(task, turn_index=0, outcome=TaskOutcome.NOT_YET) is False
    assert jc.is_closing_turn(task, turn_index=0, outcome=TaskOutcome.MET) is True
    assert jc.is_closing_turn(task, turn_index=jc.turn_budget(task) - 1, outcome=None) is True

    closing, _candidates = jc.register_corrections(
        user=user,
        text="Vous avez un café ?",
        scenario=brief,
        task=task,
        history=exchange("Bonjour.", "Bonjour !"),
        is_closing_turn=True,
    )
    assert pragmatics.MISSING_CLOSING in {finding.code for finding in closing.findings}
    mid, _candidates = jc.register_corrections(
        user=user,
        text="Vous avez un café ?",
        scenario=brief,
        task=task,
        history=exchange("Bonjour.", "Bonjour !"),
    )
    assert pragmatics.MISSING_CLOSING not in {finding.code for finding in mid.findings}


def test_a_missing_greeting_is_elicited_in_character(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)

    result = evaluate(db_session, user, brief, "Vous avez un café, s'il vous plaît ?")

    assert result.character_reply_fr.endswith("Bonjour ! On se dit bonjour d’abord ?")
    assert result.needs_repair is True
    assert result.correction is None


def test_the_nudge_never_stacks_on_a_correction(db_session):
    """One thing at a time: a corrected turn is not also nagged about hello."""

    user = _user(db_session)
    brief = _brief(db_session, user)

    result = evaluate(db_session, user, brief, "Tu as un café ?")

    assert result.correction is not None, "the register slip is the one thing owed"
    assert "Bonjour !" not in (result.character_reply_fr or "")


def test_the_softener_nudge_stays_inside_a1_and_a2(db_session):
    """Above B1 a direct question is a style, and a detector cannot tell."""

    assessment = pragmatics.assess_register(
        "Bonjour, vous avez du café ?", expected_register="vous", level_band="A1"
    )
    codes = {finding.code for finding in assessment.findings}
    assert codes == {pragmatics.MISSING_POLITENESS}
    assert jc._pragmatic_elicitation(
        assessment=assessment, register="vous", level_band="A1"
    ) == ("Vous me demandez ça comment ?", pragmatics.MISSING_POLITENESS)
    assert (
        jc._pragmatic_elicitation(assessment=assessment, register="vous", level_band="B1") is None
    )
    assert jc._pragmatic_elicitation(
        assessment=assessment, register="tu", level_band="A2"
    ) == ("Tu me demandes ça comment ?", pragmatics.MISSING_POLITENESS)


def test_a_recurrence_outranks_the_pragmatic_nudge(db_session):
    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)

    result = evaluate(db_session, user, brief, "Vous avez une café ?")

    assert result.character_reply_fr.endswith("Pardon, un ou une café ?")
    assert "Bonjour !" not in result.character_reply_fr


def test_the_nudge_is_bounded_by_the_same_one_per_scene_rule(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Vous avez un café, s'il vous plaît ?")
    second = evaluate(
        db_session,
        user,
        brief,
        "Un café, s'il vous plaît.",
        turn_index=1,
        history=exchange("Vous avez un café, s'il vous plaît ?", first.character_reply_fr),
    )
    assert "Bonjour !" not in (second.character_reply_fr or "")


# ---------------------------------------------------------------------------
# 6. A mastered mistake that resurfaces
# ---------------------------------------------------------------------------


def test_a_mastered_erratum_that_resurfaces_goes_through_the_same_path(db_session):
    """WP-24: a recurrence destroys the evidence. It reaches that through here."""

    user = _user(db_session)
    error = record(db_session, user)
    error.state = ERROR_STATE_MASTERED
    error.mastery_streak = 3
    error.mastered_at = datetime.now(UTC)
    db_session.commit()
    brief = _brief(db_session, user)

    first = evaluate(db_session, user, brief, "Je voudrais une café.")
    assert first.character_reply_fr.endswith("Pardon, un ou une café ?")

    failed = evaluate(
        db_session,
        user,
        brief,
        "Une café, oui.",
        turn_index=1,
        history=exchange("Je voudrais une café.", first.character_reply_fr),
    )
    assert failed.correction is not None
    # The reopening itself is WP-05's one-punishment-per-turn pipeline, which
    # records every correction it foregrounds; this package writes nothing on a
    # failed repair, so the mastery evidence is destroyed exactly once.
    db_session.refresh(error)
    assert error.state == ERROR_STATE_MASTERED


# ---------------------------------------------------------------------------
# 7. Copy
# ---------------------------------------------------------------------------


def test_the_explicit_correction_copy_is_complete_in_three_languages():
    row = LEARNER_COPY["self_repair.explicit_note"]
    assert set(row) == set(SUPPORTED_COPY_LANGUAGES)
    for language, template in row.items():
        assert "{correct}" in template and "{wrong}" in template, language
        assert template.strip().endswith((".", "»", "“", "„")) or template.strip()[-1] in ".!?"


def test_the_characters_own_lines_are_french_and_carry_no_pronunciation_judgement():
    lines = [
        jc.SELF_REPAIR_CHOICE_FR,
        *jc.SELF_REPAIR_REPETITION_FR.values(),
        *[line for group in jc.PRAGMATIC_ELICITATION_FR.values() for line in group.values()],
    ]
    for line in lines:
        lowered = line.lower()
        for banned in ("pronunciation", "prononciation", "aussprache", "accent"):
            assert banned not in lowered, line
    assert jc.SELF_REPAIR_REPETITION_FR["tu"].startswith("Pardon ? Tu")


def test_the_frontend_copy_carries_the_two_new_keys():
    import pathlib

    source = pathlib.Path("web-frontend/components/atelier-v2/journey/journey-copy.ts").read_text(
        encoding="utf-8"
    )
    for key in ("correction_self_repair", "self_repair_hint"):
        # once in the key union, once per language table
        assert source.count(f"{key}:") == 3, key


# ---------------------------------------------------------------------------
# 8. The policy makes no paid call
# ---------------------------------------------------------------------------


def test_the_policy_reaches_no_provider(db_session, monkeypatch):
    from app.services.llm_service import LLMService

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("the self-repair policy must not call a provider")

    monkeypatch.setattr(LLMService, "generate_chat_completion", _boom, raising=False)
    user = _user(db_session)
    record(db_session, user)
    brief = _brief(db_session, user)
    result = evaluate(db_session, user, brief, "Je voudrais une café.")
    assert "Pardon, un ou une café ?" in result.character_reply_fr


def test_the_decision_is_pure_and_writes_nothing(db_session):
    """It is taken *before* the living story pays for a turn, so it must not write."""

    user = _user(db_session)
    error = record(db_session, user)
    brief = _brief(db_session, user)
    before = (error.state, error.mastery_streak, error.next_review_date, error.updated_at)

    decision = jc.feedback_decision(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        text="Je voudrais une café.",
        turn_index=0,
        history=None,
    )
    db_session.refresh(error)
    assert decision.prompt is not None
    assert (error.state, error.mastery_streak, error.next_review_date, error.updated_at) == before


def test_an_explicit_correction_still_goes_through_wp05(db_session):
    """WP-05 owns validation: a span the learner never wrote is refused."""

    user = _user(db_session)
    brief = _brief(db_session, user)
    fabricated = Correction(
        span_fr="une café", corrected_fr="un café", note_native="never written"
    )
    evaluation = evaluate(db_session, user, brief, "Un thé, merci.")
    kept = jc.apply_feedback_policy(
        evaluation,
        db_session,
        user=user,
        task=brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un thé, merci."),
        turn_index=0,
        decision=jc.FeedbackDecision(explicit=fabricated, reason="repair_failed"),
    )
    assert kept.correction is None


def test_a_missing_closing_is_elicited_only_once_the_exchange_has_begun(db_session):
    """« Et on se quitte comme ça ? » after one line is a reprimand for nothing."""

    user = _user(db_session)
    brief = _brief(db_session, user)
    opening = "Bonjour, je voudrais un café au comptoir, s'il vous plaît."

    first = evaluate(db_session, user, brief, opening)
    assert first.outcome is TaskOutcome.MET
    assert "Et on se quitte comme ça ?" not in (first.character_reply_fr or "")

    later = evaluate(
        db_session,
        user,
        brief,
        "Bonjour, je voudrais un café au comptoir, s'il vous plaît.",
        turn_index=1,
        history=exchange("Bonjour.", "Bonjour ! Qu'est-ce que je vous sers ?"),
    )
    assert later.character_reply_fr.endswith("Et on se quitte comme ça ?")
    assert later.needs_repair is True, "the nudge is an elicitation, so it costs a turn"
    # …but the ending the learner earned is not taken back: only a self-repair
    # prompt leaves the scene genuinely unresolved.
    assert later.consequence is not None


# ---------------------------------------------------------------------------
# 9. The living story: the actor is told, and the question still reaches the
#    learner whatever the actor decides
# ---------------------------------------------------------------------------

from tests import test_intake as intake_support  # noqa: E402
from tests import test_living_story as story_support  # noqa: E402

LANDLORD_LETTER = intake_support.LANDLORD_LETTER
_FakeLLM = intake_support._FakeLLM
_letter_reading = intake_support._letter_reading
_service = intake_support._service
intake_user = intake_support._user
enabled_intake = intake_support.enabled_intake

assembled_client = story_support.assembled_client
clock = story_support.clock
journey_enabled = story_support.journey_enabled
provider = story_support.provider

STORY_WRONG = "une homme"
STORY_RIGHT = "un homme"


def _story_turn_payloads(fake) -> list[dict]:
    return [source for schema, source in fake.calls if schema == "SemanticTurn"]


def _walk_to_respond(d) -> dict:
    """Play the plan the way a learner does, up to the respond step.

    Not ``Driver.play``: that one answers the respond step too, and this package
    is about what the answer to *that* step does.
    """

    for _ in range(24):
        step = d.current()
        assert step is not None, "the plan ended before the respond step"
        if step["kind"] == "respond":
            return step
        if step["kind"] == "recall":
            # Which option is right does not matter here; getting past the step
            # does. (The answer key lives in the private task and is deliberately
            # not in the prompt — WP-06 defect D-4.)
            key = d.correct_option_id(step) or step["prompt"]["options"][0]["id"]
            response = d.attempt({"mode": "choice", "option_id": key})
            assert response.status_code == 200, response.text
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
            continue
        d.advance()
    raise AssertionError("no respond step in the plan")


def _respond(d, client, text: str):
    step = d.current()
    assert step is not None and step["kind"] == "respond"
    response = client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts",
        json={
            "mutation_id": str(uuid.uuid4()),
            "expected_revision": d.journey["revision"],
            "input": {"mode": "text", "text": text},
        },
        headers=d.headers,
    )
    if response.status_code == 200:
        d.journey = response.json()["journey"]
    return response


def test_the_story_actor_is_told_the_scene_does_not_end_and_the_learner_gets_the_question(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """The plan reaches the actor; the question reaches the learner regardless.

    The fake actor answers with a *closing* turn — no clarification, a written
    ending, a commitment. That is exactly the model behaviour this package must
    survive: the scene still does not end, and the learner still reads the
    question.
    """

    d = story_support.driver(assembled_client, db_session)
    user = db_session.get(User, d.user_id)
    record(db_session, user, wrong=STORY_WRONG, right=STORY_RIGHT, label="Le genre")
    d.create()
    _walk_to_respond(d)

    response = _respond(d, assembled_client, "Je connais une homme pour les affiches.")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["character_reply_fr"].endswith("Pardon, un ou une homme ?")
    assert body["next_turn"] is not None, "the scene keeps a turn for the repair"
    assert body["correction"] is None

    plan = _story_turn_payloads(provider)[-1]["turn_plan"]
    assert plan["clarify_form_fr"] == "Pardon, un ou une homme ?"
    assert plan["closing_turn"] is False


def test_a_repair_in_the_living_story_closes_the_loop(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story_support.driver(assembled_client, db_session)
    user = db_session.get(User, d.user_id)
    error = record(db_session, user, wrong=STORY_WRONG, right=STORY_RIGHT, label="Le genre")
    d.create()
    _walk_to_respond(d)

    first = _respond(d, assembled_client, "Je connais une homme pour les affiches.")
    assert first.status_code == 200, first.text
    assert first.json()["next_turn"] is not None

    second = _respond(d, assembled_client, "Pardon — un homme, oui.")
    assert second.status_code == 200, second.text
    assert second.json()["next_turn"] is None, "the repair turn ends the scene"

    db_session.expire_all()
    refreshed = db_session.get(UserError, error.id)
    assert refreshed.mastery_streak == 1
    assert refreshed.state == "repairing"


def test_the_story_actor_is_never_told_what_the_learner_is_expected_to_get_wrong(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """WP-28's rule, re-pinned: a grader primed with an expected error is not one.

    WP-36 tells the actor about a mistake the learner has *already made in this
    very sentence*, which the actor can read for itself. It never hands over the
    errata queue, and it never says which form is right.
    """

    import app.services.living_story as living_story

    assert "errata" not in living_story.ACTOR
    assert "turn_plan.clarify_form_fr" in living_story.ACTOR
    assert "do not say which form is right" in living_story.ACTOR

    d = story_support.driver(assembled_client, db_session)
    user = db_session.get(User, d.user_id)
    record(db_session, user, wrong=STORY_WRONG, right=STORY_RIGHT, label="Le genre")
    d.create()
    _walk_to_respond(d)
    assert _respond(d, assembled_client, "Je connais une homme pour les affiches.").status_code == 200
    payload = _story_turn_payloads(provider)[-1]
    serialised = str(payload)
    assert "errata" not in serialised
    assert STORY_RIGHT not in payload["turn_plan"]["clarify_form_fr"].replace(
        "un ou une homme", ""
    )


def test_a_story_turn_with_nothing_recurring_carries_an_empty_plan(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story_support.driver(assembled_client, db_session)
    d.create()
    _walk_to_respond(d)
    response = _respond(d, assembled_client, "Bonjour, je peux apporter les affiches samedi.")
    assert response.status_code == 200, response.text
    assert "Pardon" not in (response.json()["character_reply_fr"] or "")
    plan = _story_turn_payloads(provider)[-1]["turn_plan"]
    assert plan["clarify_form_fr"] is None


# ---------------------------------------------------------------------------
# 10. WP-34's hook: the learner's own words are coverage targets
# ---------------------------------------------------------------------------


def test_learner_sourced_words_are_coverage_targets(db_session, enabled_intake):
    """WP-34 §"hooks owed": the guard filled its targets from errata only.

    A word off the learner's own landlord letter is the most target-like word
    there is; counting it as an accident is the one way this guard could be
    wrong in the learner's own disfavour.
    """

    import app.services.living_story as living_story

    user = intake_user(db_session)
    _service(db_session, _FakeLLM(_letter_reading())).submit_text(user, text=LANDLORD_LETTER)

    targets = living_story.coverage_targets(db_session, user, errata=[])
    assert any("signalement" in target for target in targets)

    other = intake_user(db_session)
    assert not any(
        "signalement" in target
        for target in living_story.coverage_targets(db_session, other, errata=[])
    ), "another learner's document is not this learner's target"


def test_the_target_read_fails_open_when_the_intake_queue_cannot_be_read(
    db_session, monkeypatch
):
    """A target is a lenience. A queue that will not load makes the guard
    stricter, never wronger — and never costs the learner their scene."""

    import app.services.intake as intake
    import app.services.living_story as living_story

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("no")

    monkeypatch.setattr(intake, "learner_sourced_targets", _boom)
    user = _user(db_session)
    assert living_story.coverage_targets(db_session, user, errata=[]) == frozenset()


def test_the_greeting_nudge_never_takes_back_an_ending_the_learner_earned(db_session):
    """The nudge rides along on a continuing turn; it does not buy one.

    A learner who ordered their coffee in one sentence without « bonjour » has
    finished the scene. Holding the ending back to teach them a greeting would
    charge the pragmatics lesson to the objective they just met.
    """

    user = _user(db_session)
    brief = _brief(db_session, user)

    result = evaluate(db_session, user, brief, "Un café au comptoir, s'il vous plaît.")

    assert result.outcome is TaskOutcome.MET
    assert result.consequence is not None
    assert result.needs_repair is False
    assert "Bonjour !" not in (result.character_reply_fr or "")


def test_a_mastered_erratum_really_reopens_when_the_repair_fails(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """WP-24 §1 end to end, through the pipeline that owns the punishment.

    The erratum is labelled the way ``journey_learning._record_correction_erratum``
    labels one, so the explicit correction this package emits lands on the
    *same* memory key: the mastered row is re-opened and its evidence is
    destroyed, rather than a second row being opened beside it.
    """

    d = story_support.driver(assembled_client, db_session)
    user = db_session.get(User, d.user_id)
    error = record(
        db_session,
        user,
        wrong=STORY_WRONG,
        right=STORY_RIGHT,
        label=f"Reprise : {STORY_WRONG}",
        why="homme is masculine",
        task_type="journey_correction",
    )
    error.state = ERROR_STATE_MASTERED
    error.mastery_streak = 3
    error.mastered_at = datetime.now(UTC)
    db_session.commit()
    key = error.memory_key

    d.create()
    _walk_to_respond(d)
    assert _respond(d, assembled_client, "Je connais une homme pour les affiches.").status_code == 200
    second = _respond(d, assembled_client, "Oui, une homme, il peut aider.")
    assert second.status_code == 200, second.text
    assert second.json()["correction"] is not None

    db_session.expire_all()
    rows = (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.memory_key == key)
        .all()
    )
    assert len(rows) == 1, "the recurrence reopens the row, it does not clone it"
    assert rows[0].state == "repairing"
    assert rows[0].mastery_streak == 0
    assert rows[0].mastered_at is None
