"""Each surface's stored result, read as the one verdict shape (:mod:`app.core.verdict`).

These adapters read the fields surfaces already store, so rows written before the shape
existed read the same as new ones. They only read: what a failed check is allowed to do
to a level or to gold is decided elsewhere.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from loguru import logger

from app.core.verdict import Call, CheckedBy, Failure, Outcome, Verdict, make_verdict
from app.services.correction_contract import is_about_the_line
from app.services.journey_contracts import Correction, TaskOutcome

_TASK_OUTCOMES = {
    TaskOutcome.MET: Outcome.RIGHT,
    TaskOutcome.PARTIALLY_MET: Outcome.PARTLY,
    TaskOutcome.NOT_YET: Outcome.NOT_YET,
    TaskOutcome.UNSCORED: Outcome.NOT_CHECKED,
}

#: What the grading surfaces store as a verdict word (La Forge, Le Courrier, the Journal).
_WORDS = {
    "correct": Outcome.RIGHT,
    "accepted": Outcome.RIGHT,
    "partial": Outcome.PARTLY,
    "wrong": Outcome.NOT_YET,
    "incorrect": Outcome.NOT_YET,
    "needs_revision": Outcome.NOT_YET,
}


def failure_class(reason: Any) -> Failure:
    """A stored failure reason or exception text, as one failure class."""

    text = str(reason or "").lower()
    if "no_check_target" in text:
        return Failure.NO_CHECK_TARGET
    if "no_model" in text or "not configured" in text:
        return Failure.NO_MODEL
    if "timeout" in text or "timed out" in text:
        return Failure.TIMEOUT
    if any(word in text for word in ("json", "invalid", "schema", "validation", "empty")):
        return Failure.INVALID_OUTPUT
    return Failure.PROVIDER_ERROR


def _errata_as_proposed(errata: Iterable[Any], *, by: str) -> list[dict[str, Any]]:
    """Stored corrections as proposed edits: an erratum's fields, or the Journal's card fields."""

    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in errata or []:
        if not isinstance(item, dict) or not is_about_the_line(item):
            continue
        span = item.get("learner_text") or item.get("span_fr")
        replacement = item.get("corrected_target") or item.get("corrected_fr")
        if (span, replacement) in seen:
            continue
        seen.add((span, replacement))
        rows.append(
            {
                "span": span,
                "replacement": replacement,
                "note": item.get("why_wrong") or item.get("note_native") or "",
                "by": by,
                "rule_id": item.get("rule_id") or None,
            }
        )
    return rows


def _correction_as_proposed(correction: Correction | None, *, by: str) -> list[dict[str, Any]]:
    """An «A → B» correction. A pick, a meaning or a model example changes no text of the learner's."""

    if correction is None or str(getattr(correction, "kind", "edit") or "edit") != "edit":
        return []
    return [
        {
            "span": correction.span_fr,
            "replacement": correction.corrected_fr,
            "note": correction.note_native or "",
            "by": by,
        }
    ]


def from_recall(
    *,
    outcome: TaskOutcome,
    correction: Correction | None = None,
    text: str = "",
    pending: bool = False,
) -> Verdict:
    """A drill: the key decides. Only a grade error leaves it unchecked."""

    if pending or outcome is TaskOutcome.UNSCORED:
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=Call.FAILED,
            failure=Failure.PROVIDER_ERROR,
            retryable=True,
        )
    return make_verdict(
        outcome=_TASK_OUTCOMES[outcome],
        checked_by=CheckedBy.KEY,
        call=Call.NOT_CALLED,
        text=text,
        proposed=_correction_as_proposed(correction, by="key"),
    )


def from_scene(
    *,
    outcome: TaskOutcome,
    correction: Correction | None = None,
    text: str = "",
    failure_reason: str | None = None,
    check_failure: str | None = None,
) -> Verdict:
    """A scene reply. ``check_failure`` is the model that did not read it (WP-58's ending).

    A scripted scene is graded by its own authored signals, like a key, even when a model
    wrote the reply line; only the free story's model turn is the model's verdict.
    """

    if check_failure or outcome is TaskOutcome.UNSCORED:
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=Call.FAILED,
            failure=failure_class(check_failure),
            text=text,
            proposed=_correction_as_proposed(correction, by="rules"),
        )
    by_model = failure_reason == "reply_source:model"
    return make_verdict(
        outcome=_TASK_OUTCOMES[outcome],
        checked_by=CheckedBy.MODEL if by_model else CheckedBy.KEY,
        call=Call.OK if by_model else Call.NOT_CALLED,
        text=text,
        proposed=_correction_as_proposed(correction, by="model" if by_model else "key"),
    )


def from_forge(correction: dict[str, Any] | None, *, text: str = "", verdict: str | None = None) -> Verdict:
    """A La Forge answer, from its stored correction payload."""

    payload = correction if isinstance(correction, dict) else {}
    word = str(verdict or payload.get("verdict") or "")
    status = payload.get("assessment_status")
    debug = payload.get("correction_debug") if isinstance(payload.get("correction_debug"), dict) else {}
    review = payload.get("ai_review") if isinstance(payload.get("ai_review"), dict) else {}
    errata = payload.get("errata") or []
    by_key = payload.get("local_status") == "right"
    # A row from before ``assessment_status``: the same reading as seanceAssessment's.
    if (
        not status
        and debug.get("fallback_used")
        and isinstance(payload.get("corrected_answer"), str)
        and payload.get("graded_by") != "local_test_out"
    ):
        return make_verdict(outcome=Outcome.NOT_CHECKED, checked_by=CheckedBy.NONE, call=Call.NOT_CALLED)
    if status == "provisional" and not by_key:
        return make_verdict(outcome=Outcome.NOT_CHECKED, checked_by=CheckedBy.NONE, call=Call.PENDING)
    if status == "unavailable" or word == "needs_review":
        failed = review.get("status") == "failed"
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=Call.FAILED if failed else Call.NOT_CALLED,
            failure=failure_class(review.get("error")) if failed else None,
            retryable=failed,
            text=text,
            proposed=_errata_as_proposed(errata, by="rules"),
        )
    if by_key:
        return make_verdict(outcome=Outcome.RIGHT, checked_by=CheckedBy.KEY, call=Call.NOT_CALLED)
    by_model = bool(debug.get("model")) and not debug.get("fallback_used")
    return make_verdict(
        outcome=_WORDS.get(word, Outcome.NOT_CHECKED),
        checked_by=CheckedBy.MODEL if by_model else CheckedBy.KEY,
        call=Call.OK if by_model else Call.NOT_CALLED,
        text=text,
        proposed=_errata_as_proposed(errata, by="model" if by_model else "key"),
    )


def from_courrier(correction: dict[str, Any] | None, *, verdict: str | None = None, text: str = "") -> Verdict:
    """A Courrier message, from its stored correction payload and, on an attempt, the row's verdict."""

    payload = correction if isinstance(correction, dict) else {}
    if "journey_outcome" in payload:
        # A letter answered in the day's journey: the scene's reading crossed, not a corrector's.
        try:
            read = TaskOutcome(str(payload["journey_outcome"]))
        except ValueError:
            read = TaskOutcome.UNSCORED
        return from_scene(outcome=read, text=text, check_failure=payload.get("journey_check_failure"))
    debug = payload.get("correction_debug") if isinstance(payload.get("correction_debug"), dict) else {}
    errata = payload.get("errata") or []
    word = str(payload.get("verdict") or verdict or "")
    if not debug.get("fallback_used") and word in {"accepted", "partial", "needs_revision"}:
        return make_verdict(
            outcome=_WORDS[word],
            checked_by=CheckedBy.MODEL,
            call=Call.OK,
            text=text,
            proposed=_errata_as_proposed(errata, by="model"),
        )
    reason = debug.get("failure")
    call = {"empty": Call.EMPTY, "no_model": Call.NOT_CALLED}.get(str(reason), Call.FAILED)
    return make_verdict(
        outcome=Outcome.NOT_CHECKED,
        checked_by=CheckedBy.NONE,
        call=call,
        failure=failure_class(reason),
        retryable=call is not Call.NOT_CALLED,
        text=text,
        proposed=_errata_as_proposed(errata, by="rules"),
    )


def from_feuilleton(correction: dict[str, Any] | None, *, verdict: str | None = None, text: str = "") -> Verdict:
    """A stored Feuilleton answer. A branch is a choice nobody can fail to read."""

    payload = correction if isinstance(correction, dict) else {}
    debug = payload.get("correction_debug") if isinstance(payload.get("correction_debug"), dict) else {}
    word = str(verdict or payload.get("verdict") or "")
    if debug.get("fallback_used") or word in {"", "needs_review", "unassessed"}:
        reason = debug.get("failure")
        call = {"empty": Call.EMPTY, "no_model": Call.NOT_CALLED, None: Call.NOT_CALLED}.get(reason, Call.FAILED)
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=call,
            failure=failure_class(reason) if reason else None,
            text=text,
            proposed=_errata_as_proposed(payload.get("errata") or [], by="rules"),
        )
    by_model = bool(debug.get("model"))
    return make_verdict(
        outcome=_WORDS.get(word, Outcome.RIGHT),
        checked_by=CheckedBy.MODEL if by_model else CheckedBy.KEY,
        call=Call.OK if by_model else Call.NOT_CALLED,
        text=text,
        proposed=_errata_as_proposed(payload.get("errata") or [], by="model" if by_model else "key"),
    )


def from_voice(*, text: str, errors: Iterable[dict[str, Any]], read: bool, failure: str | None = None) -> Verdict:
    """A spoken turn. ``read``: a model looked at it. No errors means something only then."""

    found = list(errors)
    proposed = [
        {
            "span": error.get("span"),
            "replacement": error.get("correction"),
            "note": error.get("message") or "",
            "by": "model" if read else "rules",
        }
        for error in found
    ]
    if read:
        return make_verdict(
            outcome=Outcome.NOT_YET if found else Outcome.RIGHT,
            checked_by=CheckedBy.MODEL,
            call=Call.OK,
            text=text,
            proposed=proposed,
        )
    return make_verdict(
        outcome=Outcome.NOT_CHECKED,
        checked_by=CheckedBy.NONE,
        call=Call.FAILED if failure else Call.NOT_CALLED,
        failure=failure_class(failure) if failure else Failure.NO_MODEL,
        text=text,
        proposed=proposed,
    )


def from_rehearsal(debrief: dict[str, Any] | None) -> Verdict:
    """The line a learner wrote after the real event. Nothing moves on it, but it can be read or not."""

    payload = debrief if isinstance(debrief, dict) else {}
    text = str(payload.get("free_line") or "")
    if not payload.get("correction_available"):
        failure = failure_class(payload.get("correction_failure"))
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=Call.NOT_CALLED if failure is Failure.NO_MODEL else Call.FAILED,
            failure=failure,
            retryable=failure is not Failure.NO_MODEL,
        )
    fixes = _errata_as_proposed(payload.get("fixes") or [], by="model")
    return make_verdict(
        outcome=Outcome.RIGHT if payload.get("already_correct") and not fixes else Outcome.NOT_YET,
        checked_by=CheckedBy.MODEL,
        call=Call.OK,
        text=text,
        proposed=fixes,
    )


def from_placement(grading: dict[str, Any] | None, *, failure: str | None = None) -> Verdict:
    """A placement answer. No grading is no measurement, and it holds the ladder (``next_band``)."""

    if not grading:
        return make_verdict(
            outcome=Outcome.NOT_CHECKED,
            checked_by=CheckedBy.NONE,
            call=Call.FAILED,
            failure=failure_class(failure),
        )
    score = float(grading.get("score_0_4") or 0)
    outcome = Outcome.RIGHT if score >= 3 else Outcome.PARTLY if score >= 2 else Outcome.NOT_YET
    return make_verdict(outcome=outcome, checked_by=CheckedBy.MODEL, call=Call.OK)


def from_journal(correction: dict[str, Any] | None, *, text: str = "") -> Verdict:
    """A Journal entry, from its stored correction payload.

    ``checker`` says who looked (#250). A row from before it was stored is the model's
    when its status says checked.
    """

    payload = correction if isinstance(correction, dict) else {}
    # The card's one foreground correction is kept apart from the rest (WP-30).
    errata = [*([payload["foreground"]] if payload.get("foreground") else []), *(payload.get("errata") or [])]
    checker = payload.get("checker")
    by_model = checker == "model" or (checker is None and payload.get("assessment_status") == "checked")
    if by_model:
        word = payload.get("verdict")
        outcome = _WORDS.get(str(word)) if word else (Outcome.NOT_YET if errata else Outcome.RIGHT)
        return make_verdict(
            outcome=outcome or Outcome.NOT_CHECKED,
            checked_by=CheckedBy.MODEL,
            call=Call.OK,
            text=text,
            proposed=_errata_as_proposed(errata, by="model"),
        )
    return make_verdict(
        outcome=Outcome.NOT_CHECKED,
        checked_by=CheckedBy.NONE,
        call=Call.FAILED,
        failure=failure_class(payload.get("failure_reason")),
        retryable=bool(payload.get("retryable")),
        text=text,
        proposed=_errata_as_proposed(errata, by="rules"),
    )


def note_failure(db: Any, *, surface: str, verdict: Verdict, user_id: Any = None) -> None:
    """Log a check that did not run, so the next walk can name it. Never raises."""

    if verdict.counts or verdict.call not in {Call.FAILED, Call.EMPTY}:
        return
    failure = verdict.failure.value if verdict.failure else None
    logger.warning("verdict_check_failed surface={} failure={}", surface, failure)
    try:
        from app.services.pilot_events import PilotEventService

        with db.begin_nested():
            PilotEventService(db).record(
                "verdict_check_failed", user_id=user_id, payload={"surface": surface, "failure": failure}
            )
    except Exception as exc:  # noqa: BLE001 - a log line is never worth the learner's answer
        logger.warning("verdict_check_failed event not stored: {}", exc)


__all__ = [
    "failure_class",
    "from_courrier",
    "from_feuilleton",
    "from_forge",
    "from_journal",
    "from_placement",
    "from_recall",
    "from_rehearsal",
    "from_scene",
    "from_voice",
    "note_failure",
]
