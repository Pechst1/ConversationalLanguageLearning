"""#174, #250, #333: one verdict shape, read from what each surface already stores.

The fixtures are the walks' own sentences. The surfaces' API tests assert the block is on
the wire (test_atelier, test_daily_journey_api, test_missions, test_journal_api).
"""
from __future__ import annotations

import pytest

from app.core.verdict import (
    Call,
    CheckedBy,
    Failure,
    Outcome,
    apply_edits,
    locate_edits,
    make_verdict,
)
from app.schemas.verdict import VerdictView
from app.services import verdicts
from app.services.journey_contracts import Correction, TaskOutcome


def _erratum(wrong: str, right: str, why: str = "") -> dict[str, str]:
    return {"learner_text": wrong, "corrected_target": right, "why_wrong": why}


@pytest.mark.parametrize("call", [Call.FAILED, Call.EMPTY, Call.PENDING, Call.NOT_CALLED])
@pytest.mark.parametrize("outcome", [Outcome.RIGHT, Outcome.PARTLY, Outcome.NOT_YET])
def test_a_model_that_did_not_answer_gives_no_verdict(call, outcome):
    verdict = make_verdict(outcome=outcome, checked_by=CheckedBy.MODEL, call=call)
    assert verdict.outcome is Outcome.NOT_CHECKED
    assert verdict.checked_by is CheckedBy.NONE
    assert verdict.counts is False


@pytest.mark.parametrize("outcome", [Outcome.RIGHT, Outcome.PARTLY, Outcome.NOT_YET])
def test_rules_can_add_fixes_but_never_a_verdict(outcome):
    verdict = make_verdict(
        outcome=outcome,
        checked_by=CheckedBy.RULES,
        call=Call.FAILED,
        failure=Failure.TIMEOUT,
        retryable=True,
        text="Je suis tres content.",
        proposed=[{"span": "tres", "replacement": "très", "by": "rules"}],
    )
    assert verdict.outcome is Outcome.NOT_CHECKED
    assert verdict.checked_by is CheckedBy.RULES
    assert verdict.counts is False
    assert verdict.corrected == "Je suis très content."
    assert verdict.retryable is True


def test_rules_that_found_nothing_are_no_check_at_all():
    verdict = make_verdict(
        outcome=Outcome.NOT_CHECKED, checked_by=CheckedBy.RULES, call=Call.FAILED, text="Je pas ai beaucoup bagages"
    )
    assert verdict.checked_by is CheckedBy.NONE
    assert verdict.corrected is None


@pytest.mark.parametrize(
    "checked_by, call, outcome, counts",
    [
        (CheckedBy.KEY, Call.NOT_CALLED, Outcome.RIGHT, True),
        (CheckedBy.KEY, Call.NOT_CALLED, Outcome.NOT_YET, True),
        (CheckedBy.KEY, Call.FAILED, Outcome.RIGHT, True),  # #471: the key's right survives a failed second look
        (CheckedBy.MODEL, Call.OK, Outcome.PARTLY, True),
        (CheckedBy.MODEL, Call.OK, Outcome.NOT_CHECKED, False),
    ],
)
def test_counts_is_derived_and_only_from_the_key_or_a_model(checked_by, call, outcome, counts):
    assert make_verdict(outcome=outcome, checked_by=checked_by, call=call).counts is counts


def test_the_corrected_line_is_built_from_the_listed_edits_only():
    """#250, walk of 20 Oct: nothing but the listed changes reaches the line."""

    text = "Je vais sonné à la porte et je vend le gâteau."
    verdict = make_verdict(
        outcome=Outcome.NOT_YET,
        checked_by=CheckedBy.MODEL,
        call=Call.OK,
        text=text,
        proposed=[
            {"span": "vend", "replacement": "vends", "note": "je vends"},
            {"span": "sonné", "replacement": "sonner", "note": "après aller"},
        ],
    )
    assert verdict.corrected == "Je vais sonner à la porte et je vends le gâteau."
    assert [edit.span for edit in verdict.edits] == ["sonné", "vend"]
    for edit in verdict.edits:
        assert text[edit.start : edit.end] == edit.span


@pytest.mark.parametrize(
    "text, span",
    [
        ("Odile est parti parce que la restaurant est fermé.", "tu"),
        ("Je garde la table et les livre.", "absent"),
        ("Mon chat dort.", "a"),  # a span that sits inside another word («chat») is not that word
        ("Je garde la table.", ""),
    ],
)
def test_an_edit_naming_words_the_learner_did_not_write_is_left_out(text, span):
    assert locate_edits(text, [{"span": span, "replacement": "sont"}]) == ()


def test_a_span_is_found_whichever_apostrophe_it_quotes():
    edits = locate_edits("Je n’ai pas l’appartement.", [{"span": "l'appartement", "replacement": "la maison"}])
    assert apply_edits("Je n’ai pas l’appartement.", edits) == "Je n’ai pas la maison."


def test_two_edits_never_overlap_and_a_repeated_span_takes_the_next_place():
    text = "la table et la chaise"
    edits = locate_edits(
        text, [{"span": "la", "replacement": "LA"}, {"span": "la", "replacement": "LE"}, {"span": "la table", "replacement": "x"}]
    )
    assert apply_edits(text, edits) == "LA table et LE chaise"


# --- Each surface's stored rows ---------------------------------------------------------


def test_courrier_a_rules_only_partial_is_not_a_verdict():
    """#333, walk of 25 Oct: «Partly · Agent Moreau is neutral» on a letter no model read."""

    verdict = verdicts.from_courrier(
        {"verdict": "partial", "errata": [_erratum("tres", "très")], "correction_debug": {"fallback_used": True}},
        text="Je suis tres content de venir chez toi samedi soir avec mon ami Marin.",
    )
    assert verdict.outcome is Outcome.NOT_CHECKED
    assert verdict.checked_by is CheckedBy.RULES
    assert verdict.call is Call.FAILED
    assert verdict.counts is False
    assert verdict.retryable is True
    assert verdict.corrected == "Je suis très content de venir chez toi samedi soir avec mon ami Marin."


def test_courrier_nothing_found_with_no_model_is_not_checked():
    """#333: «No corrections found.» for «Je pas ai beaucoup bagages»."""

    verdict = verdicts.from_courrier(
        {"verdict": "unassessed", "errata": [], "correction_debug": {"fallback_used": True}},
        text="Je pas ai beaucoup bagages aujourd'hui, mais je viens chez toi samedi soir.",
    )
    assert verdict.outcome is Outcome.NOT_CHECKED
    assert verdict.checked_by is CheckedBy.NONE
    assert verdict.corrected is None
    assert verdict.counts is False


@pytest.mark.parametrize(
    "word, outcome", [("accepted", Outcome.RIGHT), ("partial", Outcome.PARTLY), ("needs_revision", Outcome.NOT_YET)]
)
def test_courrier_a_model_verdict_counts(word, outcome):
    verdict = verdicts.from_courrier(
        {"verdict": word, "errata": [], "correction_debug": {"fallback_used": False, "model": "m"}}, text="Bonjour."
    )
    assert (verdict.outcome, verdict.checked_by, verdict.call, verdict.counts) == (outcome, CheckedBy.MODEL, Call.OK, True)


def test_courrier_a_row_with_no_payload_is_not_checked():
    assert verdicts.from_courrier(None).outcome is Outcome.NOT_CHECKED


def test_forge_second_look_pending_is_no_verdict_yet():
    verdict = verdicts.from_forge({"assessment_status": "provisional", "verdict": "partial", "local_status": "checking"})
    assert (verdict.outcome, verdict.call, verdict.counts) == (Outcome.NOT_CHECKED, Call.PENDING, False)


def test_forge_an_accepted_answer_is_right_by_the_key_while_the_second_look_runs():
    verdict = verdicts.from_forge({"assessment_status": "provisional", "verdict": "correct", "local_status": "right"})
    assert (verdict.outcome, verdict.checked_by, verdict.counts) == (Outcome.RIGHT, CheckedBy.KEY, True)


def test_forge_a_failed_second_look_is_not_checked_and_says_why():
    """#333, walk of 25 Oct: «Answer saved, not checked yet. The second check stopped.»"""

    verdict = verdicts.from_forge(
        {
            "assessment_status": "unavailable",
            "verdict": "needs_review",
            "ai_review": {"status": "failed", "error": "Timeout after 30s"},
        }
    )
    assert verdict.outcome is Outcome.NOT_CHECKED
    assert verdict.failure is Failure.TIMEOUT
    assert verdict.retryable is True
    assert verdict.counts is False


def test_forge_no_model_at_all_is_not_a_failed_call():
    verdict = verdicts.from_forge({"assessment_status": "unavailable", "verdict": "needs_review"})
    assert (verdict.call, verdict.retryable) == (Call.NOT_CALLED, False)


def test_forge_a_keyed_answer_counts_with_no_model():
    verdict = verdicts.from_forge({"assessment_status": "checked", "correction_debug": {"fallback_used": True}}, verdict="correct")
    assert (verdict.outcome, verdict.checked_by, verdict.call, verdict.counts) == (
        Outcome.RIGHT, CheckedBy.KEY, Call.NOT_CALLED, True,
    )


def test_forge_a_model_verdict_lists_its_edits():
    verdict = verdicts.from_forge(
        {
            "assessment_status": "checked",
            "verdict": "partial",
            "correction_debug": {"model": "m", "fallback_used": False},
            "errata": [_erratum("achete", "acheté", "accent")],
        },
        text="Elle a achete un livre.",
    )
    assert (verdict.outcome, verdict.checked_by, verdict.counts) == (Outcome.PARTLY, CheckedBy.MODEL, True)
    assert verdict.corrected == "Elle a acheté un livre."


def test_journal_a_rules_only_row_is_not_checked_even_though_its_status_says_so():
    """#333: «No corrections found.» for «je ne était» after a failed call."""

    verdict = verdicts.from_journal(
        {"assessment_status": "checked", "checker": "deterministic", "failure_reason": "timeout", "retryable": True, "errata": []},
        text="je ne était",
    )
    assert (verdict.outcome, verdict.checked_by, verdict.failure) == (Outcome.NOT_CHECKED, CheckedBy.NONE, Failure.TIMEOUT)
    assert verdict.retryable is True
    assert verdict.counts is False


def test_journal_no_check_target_cannot_be_retried():
    verdict = verdicts.from_journal(
        {"checker": "deterministic", "failure_reason": "no_check_target", "retryable": False, "errata": [_erratum("tres", "très")]},
        text="Il est tres grand.",
    )
    assert (verdict.failure, verdict.retryable, verdict.checked_by) == (Failure.NO_CHECK_TARGET, False, CheckedBy.RULES)


def test_journal_a_row_from_before_checker_was_stored_reads_as_the_model():
    verdict = verdicts.from_journal(
        {"assessment_status": "checked", "verdict": "partial", "errata": [_erratum("la livre", "le livre")]},
        text="J'ai rapporté la livre à Romy.",
    )
    assert (verdict.outcome, verdict.checked_by, verdict.corrected) == (
        Outcome.PARTLY, CheckedBy.MODEL, "J'ai rapporté le livre à Romy.",
    )


def test_scene_the_authored_fallback_is_not_a_partial_pass():
    """WP-58's ending stays, but nobody read the sentence."""

    verdict = verdicts.from_scene(
        outcome=TaskOutcome.PARTIALLY_MET,
        text="a la scène j ai",
        failure_reason="reply_source:authored",
        check_failure="Timeout after 30s",
    )
    assert (verdict.outcome, verdict.call, verdict.failure, verdict.counts) == (
        Outcome.NOT_CHECKED, Call.FAILED, Failure.TIMEOUT, False,
    )
    assert verdict.retryable is False, "the scene moves on: the reply is not asked again"


def test_scene_a_scripted_scene_is_graded_by_its_own_signals():
    """An authored reply line is not a failure: nothing was asked of a model."""

    verdict = verdicts.from_scene(outcome=TaskOutcome.MET, text="Un café, s'il vous plaît.", failure_reason="reply_source:authored")
    assert (verdict.outcome, verdict.checked_by, verdict.call, verdict.counts) == (
        Outcome.RIGHT, CheckedBy.KEY, Call.NOT_CALLED, True,
    )


def test_scene_a_model_reply_counts_and_lists_its_correction():
    correction = Correction(span_fr="je vend", corrected_fr="je vends", note_native="je → vends")
    verdict = verdicts.from_scene(
        outcome=TaskOutcome.PARTIALLY_MET, correction=correction, text="Non, je vend pas.", failure_reason="reply_source:model"
    )
    assert (verdict.outcome, verdict.checked_by, verdict.counts) == (Outcome.PARTLY, CheckedBy.MODEL, True)
    assert verdict.corrected == "Non, je vends pas."


@pytest.mark.parametrize(
    "task_outcome, outcome",
    [(TaskOutcome.MET, Outcome.RIGHT), (TaskOutcome.PARTIALLY_MET, Outcome.PARTLY), (TaskOutcome.NOT_YET, Outcome.NOT_YET)],
)
def test_a_drill_is_judged_by_the_key(task_outcome, outcome):
    verdict = verdicts.from_recall(outcome=task_outcome)
    assert (verdict.outcome, verdict.checked_by, verdict.call, verdict.counts) == (outcome, CheckedBy.KEY, Call.NOT_CALLED, True)


def test_a_drill_grade_error_is_not_checked():
    verdict = verdicts.from_recall(outcome=TaskOutcome.UNSCORED, pending=True)
    assert (verdict.outcome, verdict.call, verdict.retryable, verdict.counts) == (Outcome.NOT_CHECKED, Call.FAILED, True, False)


def test_a_wrong_pick_changes_no_text_of_the_learners():
    correction = Correction(span_fr="une maison", corrected_fr="un appartement", note_native="", kind="pick")
    verdict = verdicts.from_recall(outcome=TaskOutcome.NOT_YET, correction=correction, text="une maison")
    assert verdict.edits == ()
    assert verdict.corrected is None


def test_the_shape_serialises_with_counts_on_the_wire():
    view = VerdictView.of(verdicts.from_recall(outcome=TaskOutcome.MET))
    assert view.model_dump()["counts"] is True
    assert view.model_dump()["outcome"] == "right"
