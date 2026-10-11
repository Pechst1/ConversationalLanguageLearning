"""WP-L4 «Emploi» — what a reply shows about the grammar units it was asked to use.

Runs after the reply is graded (authored, conversation or story engine — the
seam is the same), with no extra model call. For every grammar unit the
respond step targets (the day's new unit, a strong due unit asked for as free
use), the unit's regex detectors (WP-L2) read the learner's reply:

* **correct** — the form is there and no correction touches it → free
  production (the strongest evidence, and the only road to «Tenue»);
* **error** — the form is there (or was reached for) and the turn's
  correction touches it → a lapse, booked **once**: the grammar observation
  carries it, and the correction's erratum is linked to the same unit
  (``journey_learning`` skips the erratum's own concept lapse for a unit the
  step already lapsed, and hands the erratum this unit);
* **avoided** — the form is not there → neutral: no observation at all.

A unit whose only detector is an ``llm:`` description (7 v2 units), or a v1
concept with no v2 replacement carrying a regex, has no deterministic
detector: its reply evidence comes from corrections only (WP-L1's
concept-linked errata), and its outcome is reported as ``undetected``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services.grammar_items import detector_span, fold_apostrophes
from app.services.grammar_units import regex_patterns, unit_detectors
from app.services.journey_contracts import (
    AssistanceLevel,
    EvidenceKind,
    InputMode,
    ResponseTask,
    TargetKind,
    TargetObservation,
    strongest_assistance,
)

OUTCOME_CORRECT = "correct"
OUTCOME_ERROR = "error"
OUTCOME_AVOIDED = "avoided"
OUTCOME_UNDETECTED = "undetected"


def _touches(correction: Any, span: str | None, patterns: list[str]) -> bool:
    """Does the turn's correction concern this unit's form?"""

    if correction is None:
        return False
    wrong = fold_apostrophes(getattr(correction, "span_fr", "") or "").casefold()
    right = fold_apostrophes(getattr(correction, "corrected_fr", "") or "").casefold()
    if span and (span.casefold() in wrong or wrong in span.casefold()) and wrong:
        return True
    # The corrected text uses the form: the learner reached for it and missed.
    return bool(detector_span(patterns, right)) and not detector_span(patterns, wrong)


def classify_reply(patterns: list[str], text: str, correction: Any) -> tuple[str, str | None]:
    """``(outcome, span)`` for one unit in one reply."""

    if not patterns:
        return OUTCOME_UNDETECTED, None
    span = detector_span(patterns, text)
    if _touches(correction, span, patterns):
        return OUTCOME_ERROR, span or getattr(correction, "span_fr", None)
    if span:
        return OUTCOME_CORRECT, span
    return OUTCOME_AVOIDED, None


def with_concept_evidence(
    db: Session,
    *,
    evaluation: Any,
    task: ResponseTask,
    text: str,
    modality: InputMode,
) -> Any:
    """The evaluation with the reply's concept evidence added (and observations)."""

    grammar_targets = [target for target in task.targets if target.kind is TargetKind.GRAMMAR]
    if not grammar_targets or getattr(evaluation, "pending", False):
        return evaluation
    correction = getattr(evaluation, "correction", None)
    assistance = strongest_assistance([getattr(evaluation, "assistance", AssistanceLevel.NONE)])
    targeted = {target.id for target in grammar_targets}
    # The detectors decide for these units: a model's own guess is replaced.
    observations = [
        observation
        for observation in getattr(evaluation, "observations", []) or []
        if not (observation.target.kind is TargetKind.GRAMMAR and observation.target.id in targeted)
    ]
    evidence: list[dict[str, Any]] = []
    for target in grammar_targets:
        try:
            concept = db.get(GrammarConcept, int(target.id))
        except (TypeError, ValueError):
            concept = None
        if concept is None:
            continue
        patterns = regex_patterns(unit_detectors(concept))
        outcome, span = classify_reply(patterns, text, correction)
        evidence.append({"concept_id": concept.id, "outcome": outcome, "span": span})
        if outcome == OUTCOME_CORRECT:
            kind = (
                EvidenceKind.PRODUCED_INDEPENDENT
                if assistance is AssistanceLevel.NONE
                else EvidenceKind.PRODUCED_SUPPORTED
            )
        elif outcome == OUTCOME_ERROR:
            kind = EvidenceKind.NOT_YET
        else:
            continue
        observations.append(
            TargetObservation(
                target=target,
                evidence_kind=kind,
                assistance=assistance,
                modality=modality,
                learner_text=text,
                corrected_text=getattr(correction, "corrected_fr", None)
                if outcome == OUTCOME_ERROR
                else None,
            )
        )
    if not evidence:
        return evaluation
    return replace(evaluation, observations=observations, concept_evidence=evidence)


__all__ = [
    "OUTCOME_AVOIDED",
    "OUTCOME_CORRECT",
    "OUTCOME_ERROR",
    "OUTCOME_UNDETECTED",
    "classify_reply",
    "with_concept_evidence",
]
