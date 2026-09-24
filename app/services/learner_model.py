"""WP-35 — «Votre dossier»: the inspectable, editable-with-a-check learner model.

Open learner models raise self-regulation, and the part of the continuum that
earns the effect is *editable* rather than merely visible (systematic review
2020; meta-synthesis 2025). So this module answers two questions and no others:

1. **What does the app believe, and on whose authority?** The estimated level
   with its source and confidence, the capability rubric's four states, the
   errata by lifecycle state with their next due date, the vocabulary stock, and
   why today's scene is today's scene.
2. **What happens when the learner disagrees?** «Je connais déjà» opens a
   two-item check built from the learner's own records. Passing advances the
   schedule *through the existing SRS APIs*; failing costs nothing. The claim is
   recorded either way, and no path takes the claim's word for it.

Three rules this module keeps, each of which had a cheaper wrong answer:

* **Nothing is re-scored here.** The capability states come from
  :func:`app.services.journey_capabilities.build_capability_summary` verbatim —
  CONTRACTS §8 records what two rubrics did to one journey — the level comes
  from :class:`app.services.cefr_progress.CEFRProgressService`, the errata
  states from :func:`app.services.error_memory.normalize_error_state`, and the
  known-word count from WP-29's :func:`known_word_set`. A dossier that computed
  its own numbers would be a second model of the learner, which is exactly the
  thing this page exists to make inspectable.
* **The page is a read.** ``build_dossier`` never recomputes a CEFR estimate,
  never reschedules anything (reading the errata queue is pinned as
  side-effect-free in WP-24), and never generates content. Only a submitted
  claim writes, and only through :meth:`ErrorMemoryService.review_error` and
  :meth:`VocabularyCreditService.apply` — never by touching a column.
* **Today's «because» is read from the plan, never recomputed.** WP-28 stores
  the payload with the plan precisely so a mistake made *after* the scene was
  planned cannot claim credit for it; recomputing it here would reintroduce the
  bug on a second surface.

Neither ``build_dossier`` nor ``verify_claim`` commits: the router owns the
transaction, as everywhere else in the Atelier.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.error import UserError
from app.db.models.pilot_event import PilotEvent
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.cefr_progress import (
    DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
    CEFRProgressService,
    declared_level_floor,
)
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_OPEN,
    ERROR_STATE_REPAIRING,
    MASTERY_REQUIRED_REPAIRS,
    ErrorMemoryService,
    normalize_error_state,
    serialize_error_memory,
)
from app.services.journey_capabilities import EVIDENCE_READ_LIMIT, build_capability_summary
from app.services.journey_learning import answer_matches, fold_for_comparison, read_journey_evidence
from app.services.pilot_events import PilotEventService
from app.services.vocabulary_coverage import NAILED_RETRIEVABILITY, VocabularyCoverageService
from app.services.vocabulary_credit import VocabularyCreditService

logger = logging.getLogger(__name__)

#: Payload version. Bumped when a field's *meaning* changes, never for an add.
DOSSIER_VERSION = "learner-model-v1"

#: One pilot row per claim, at both stages. ``stage`` separates them.
CLAIM_EVENT_TYPE = "dossier_claim"
CLAIM_STAGE_OPENED = "claimed"
CLAIM_STAGE_CHECKED = "checked"

#: Two items, both correct. One item is a coin toss on a gender claim, and the
#: point of the check is that the schedule moves on evidence, not on a claim.
CLAIM_ITEMS_REQUIRED = 2

#: What the learner may claim to know already.
CLAIM_KIND_ERRATUM = "erratum"
CLAIM_KIND_WORD = "word"
CLAIM_KINDS = (CLAIM_KIND_ERRATUM, CLAIM_KIND_WORD)

#: Verdicts. ``unverifiable`` is not a failure and not a pass: the records do
#: not contain two honest questions about this item, and saying so is better
#: than inventing one or waving the claim through.
VERDICT_VERIFIED = "verified"
VERDICT_NOT_YET = "not_yet"
VERDICT_UNVERIFIABLE = "unverifiable"

#: The rating a passed check reports to the SM-2 scheduler (WP-24 §2: five is a
#: pass everywhere in this product; ``review_error`` takes 0–4 and 4 is "easy").
CLAIM_PASS_RATING = 4

#: How many rows each section shows. The dossier is a page, not an export.
ERRATA_PER_STATE = 12
WORDS_SHOWN = 8
CLAIMS_SHOWN = 10

#: WP-45 (D-3/D-5). «Votre dossier» is a French screen end to end, so every
#: capability carries a French title beside the control-language one rather than
#: printing «Im Café bestellen» under a French label. The strings mirror
#: ``journey_capabilities._TITLES["fr"]``; ``tests/test_wp45_companion.py`` pins
#: the two together so they cannot drift apart silently. ``register`` has no
#: entry there — it is a dimension, not a scenario — and comes from the same
#: copy table the rubric itself uses.
_CAPABILITY_TITLE_FR: dict[str, str] = {
    "order_at_cafe": "Commander au café",
    "arrange_meeting": "Fixer un rendez-vous",
    "explain_delay": "Expliquer un retard",
}

#: Publication French. These are printed verbatim by the page, like the repair
#: card's furniture in ``error_memory``.
_ITEM_COPY: dict[str, dict[str, str]] = {
    "repair": {
        "instruction": "Réécrivez la forme correcte, de mémoire.",
        "placeholder": "La forme correcte",
    },
    "cloze": {
        "instruction": "Complétez la phrase avec le mot qui manque.",
        "placeholder": "Le mot manquant",
    },
    "production": {
        "instruction": "Écrivez le mot en français.",
        "placeholder": "Le mot en français",
    },
    "meaning": {
        "instruction": "Donnez le sens de ce mot.",
        "placeholder": "Le sens",
    },
}

_UNVERIFIABLE_FR = {
    "not_found": "Cet élément n’est plus dans votre dossier.",
    "no_two_items": (
        "Nous ne savons pas poser deux questions honnêtes sur cet élément, "
        "donc nous ne pouvons pas vérifier votre déclaration. Il reste tel quel."
    ),
    "already_mastered": "Cet élément est déjà acquis : il n’y a rien à vérifier.",
}

_VERDICT_FR = {
    VERDICT_VERIFIED: (
        "Vérifié : les deux reprises sont justes. Votre déclaration est prise en compte "
        "et l’échéance avance."
    ),
    VERDICT_NOT_YET: (
        "Pas encore. Rien n’est retiré et rien n’est ajouté : cet élément garde "
        "exactement la place qu’il avait."
    ),
}


# ---------------------------------------------------------------------------
# What the app believes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evidence:
    """Where a number came from. ``journey_id`` whenever a journey produced it."""

    kind: str
    on: date | None = None
    journey_id: str | None = None
    reference: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "on": self.on.isoformat() if self.on else None,
            "journey_id": self.journey_id,
            "reference": self.reference,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class Dossier:
    """Everything the page renders, and nothing it has to compute."""

    version: str
    level: dict[str, Any]
    capabilities: list[dict[str, Any]]
    errata: dict[str, Any]
    vocabulary: dict[str, Any]
    today: dict[str, Any]
    claims: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "level": self.level,
            "capabilities": self.capabilities,
            "errata": self.errata,
            "vocabulary": self.vocabulary,
            "today": self.today,
            "claims": self.claims,
        }


def build_dossier(db: Session, *, user: User, control_language: str | None = None) -> Dossier:
    """The whole model, read-only.

    Every section degrades on its own: a section whose source raises is reported
    as unavailable rather than 500-ing the page, because a learner model that
    cannot be opened is worse than one with a hole in it.
    """

    language = str(control_language or getattr(user, "native_language", None) or "en")
    return Dossier(
        version=DOSSIER_VERSION,
        level=_level_belief(db, user=user),
        capabilities=_capability_beliefs(db, user=user, control_language=language),
        errata=_errata_beliefs(db, user=user),
        vocabulary=_vocabulary_beliefs(db, user=user),
        today=_today_belief(db, user=user),
        claims=_recent_claims(db, user=user),
    )


def _level_belief(db: Session, *, user: User) -> dict[str, Any]:
    """Level, where it came from, how sure it is, and the breakdown behind it.

    ``recompute_if_missing=False``: opening a page must not write a CEFR history
    row, and a learner whose payload is missing is exactly the learner whose
    counters are all zero — the honest answer there is the declaration, which is
    what ``current`` falls back to.
    """

    try:
        service = CEFRProgressService(db)
        payload = service.current(user, recompute_if_missing=False)
        if "breakdown" not in payload:
            # The learner has no stored payload yet. `current(recompute_if_missing=True)`
            # would compute one *and persist it*, writing a CEFR history row for
            # opening a page; `recompute(persist=False)` is the same arithmetic
            # with no write, which is what a read owes the learner.
            payload = service.recompute(user, persist=False)
    except Exception:  # pragma: no cover - a level must never 500 the dossier
        logger.exception("learner_model: the CEFR estimate could not be read")
        return {"available": False, "reason": "level_unavailable"}

    source = str(payload.get("estimate_source") or "measured")
    placement = _placement_record(db, user=user)
    breakdown = dict(payload.get("breakdown") or {})
    signals = dict(payload.get("signals") or {})

    if source == "placement" and placement:
        confidence = placement.get("confidence")
        evidence = Evidence(
            kind="placement",
            on=_as_date(placement.get("taken_at")),
            reference=str(placement.get("id") or ""),
            detail=f"{placement.get('graded_turns') or 0}",
        )
    elif source == "declared":
        # A declaration has no confidence. Reporting one — even a low one —
        # would dress a dropdown up as a measurement.
        confidence = None
        evidence = Evidence(kind="declaration", on=_as_date(getattr(user, "created_at", None)))
    else:
        confidence = None
        evidence = Evidence(
            kind="in_app_counters",
            on=_as_date(payload.get("generated_at")),
            detail=str(int(signals.get("recent_attempt_count") or 0)),
        )

    return {
        "available": True,
        "estimate": payload.get("estimate"),
        "estimate_source": source,
        "declared_level": payload.get("declared_level") or declared_level_floor(user),
        # `unverified` for both `declared` and `placement`: the learner's in-app
        # counters are zero either way, and WP-25 §4.5 forbids drawing those
        # gauges as a verified level.
        "verified": str(breakdown.get("status") or "") == "measured",
        "status": breakdown.get("status"),
        "confidence": confidence,
        # WP-45 (D-5): the page explains what turns «déclaré» into «mesuré», and
        # the number in that sentence is the one the estimator actually uses —
        # never a figure retyped into French copy.
        "evidence_attempts_required": DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
        "evidence_attempts_counted": int(signals.get("recent_attempt_count") or 0),
        "breakdown": breakdown,
        "placement": placement,
        "target": payload.get("target"),
        "next_level": payload.get("next_level"),
        "evidence": evidence.as_dict(),
        # WP-L7: «A1.1 · 60 %» and the numbers behind it — units held, words
        # known, the épreuve — read from the estimator, never recomputed here.
        "level_label": payload.get("level_label"),
        "coverage": payload.get("coverage"),
        "checkpoint": payload.get("checkpoint"),
        # WP-L8: always an estimate (prior before 7 active days, then measured).
        "forecast": payload.get("forecast"),
        # WP-S8: «Your rules: n held, median x days to hold» — measured from the
        # learner's own held rules, shown from three; never a promise.
        "rules_speed": _rules_speed(db, user=user),
    }


def _rules_speed(db: Session, *, user: User) -> dict[str, Any] | None:
    try:
        from app.services.forge_metrics import learner_rule_speed

        return learner_rule_speed(db, user_id=user.id)
    except Exception:  # pragma: no cover - a measured line never 500s the dossier
        logger.exception("learner_model: the rule speed could not be read")
        return None


def _placement_record(db: Session, *, user: User) -> dict[str, Any] | None:
    """The last completed placement, with its id, date and per-dimension means.

    ``latest_placement_prior`` decides whether a placement is worth *trusting*;
    this read is about showing the learner what was measured and when, so it
    reports the session even when its confidence left it out of the estimate —
    labelled with that confidence rather than silently promoted.
    """

    try:
        row = (
            db.query(PlacementSession)
            .filter(
                PlacementSession.user_id == user.id,
                PlacementSession.status == "complete",
                PlacementSession.estimate_level.isnot(None),
            )
            .order_by(PlacementSession.completed_at.desc(), PlacementSession.created_at.desc())
            .first()
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the placement could not be read")
        return None
    if row is None:
        return None
    estimate = dict(row.estimate or {})
    return {
        "id": str(row.id),
        "level": row.estimate_level,
        "confidence": round(float(row.confidence or 0.0), 3),
        "taken_at": row.completed_at.isoformat() if row.completed_at else None,
        "graded_turns": int(estimate.get("graded_turns") or 0),
        "dimensions": dict(estimate.get("dimensions") or {}),
        "dimension_labels": dict(estimate.get("dimension_labels") or {}),
    }


def _capability_beliefs(
    db: Session, *, user: User, control_language: str
) -> list[dict[str, Any]]:
    """The rubric's own answer, plus a journey id per piece of evidence.

    The states are :func:`build_capability_summary`'s, untouched. The only thing
    added here is the link: the summary's evidence carries the date and the
    modality but not the journey, and «every number links to its evidence» needs
    the journey the learner can go and look at.
    """

    try:
        view = build_capability_summary(db, user=user, control_language=control_language)
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the capability summary could not be read")
        return []

    links = _journey_links(db, user=user)
    capabilities: list[dict[str, Any]] = []
    for summary in view.capabilities:
        key = str(summary.capability_key)
        evidence = [
            {
                "on": item.observed_on.isoformat(),
                "modality": str(item.modality),
                "state": str(item.state),
                "context": item.context_native,
                "journey_id": links.get((key, item.observed_on)),
            }
            for item in summary.evidence
        ]
        capabilities.append(
            {
                "key": key,
                "title": summary.title_native,
                # WP-45: the dossier is French chrome; the page prints this and
                # falls back to `title` only when a key has no French name yet.
                "title_fr": _french_capability_title(key),
                "state": str(summary.state),
                "rubric_version": view.rubric_version,
                "modalities": [str(mode) for mode in summary.modalities],
                "latest_qualifying_on": (
                    summary.latest_qualifying_on.isoformat()
                    if summary.latest_qualifying_on
                    else None
                ),
                "evidence": evidence,
            }
        )
    return capabilities


def _french_capability_title(key: str) -> str | None:
    """The French name of one capability, or ``None`` when there is none.

    ``None`` rather than the English title: a page that gets nothing falls back
    to the control-language title it already has, which is the current
    behaviour. Inventing French here would be worse than the mixed chrome.
    """

    if key in _CAPABILITY_TITLE_FR:
        return _CAPABILITY_TITLE_FR[key]
    if key == "register":
        from app.services.learner_copy import learner_text

        return learner_text("capability.register_title", "fr")
    return None


def _journey_links(db: Session, *, user: User) -> dict[tuple[str, date], str]:
    """``(capability, observed date) -> journey id`` for the evidence links.

    A read of the same evidence table the rubric reads, used for nothing but
    naming the journey. It classifies nothing and scores nothing.
    """

    try:
        records = read_journey_evidence(
            db, user=user, include_legacy=False, limit=EVIDENCE_READ_LIMIT
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: journey evidence could not be read")
        return {}
    links: dict[tuple[str, date], str] = {}
    for record in records:
        if record.capability_key is None or record.journey_id is None:
            continue
        links.setdefault((str(record.capability_key), record.observed_on), str(record.journey_id))
    return links


def _errata_beliefs(db: Session, *, user: User) -> dict[str, Any]:
    """Every erratum by WP-24 state, with the next date each one is due.

    Reading the queue reschedules nothing — the property WP-24 pins for the
    planner holds here for the same reason: this is a ``SELECT``.
    """

    try:
        rows = (
            db.query(UserError)
            .filter(UserError.user_id == user.id)
            .order_by(
                UserError.next_review_date.asc().nullsfirst(),
                UserError.occurrences.desc(),
            )
            .limit(ERRATA_PER_STATE * len(("open", "repairing", "mastered")))
            .all()
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the errata queue could not be read")
        return {"available": False, "reason": "errata_unavailable"}

    by_state: dict[str, list[dict[str, Any]]] = {
        ERROR_STATE_OPEN: [],
        ERROR_STATE_REPAIRING: [],
        ERROR_STATE_MASTERED: [],
    }
    for row in rows:
        payload = serialize_error_memory(row, language=getattr(user, "native_language", None))
        state = str(payload.get("state") or ERROR_STATE_OPEN)
        bucket = by_state.setdefault(state, [])
        if len(bucket) >= ERRATA_PER_STATE:
            continue
        bucket.append(
            {
                "id": payload["id"],
                "label": payload["display_label"],
                "state": state,
                "learner_text": payload["learner_text"],
                "corrected_target": payload["corrected_target"],
                "why_wrong": payload["why_wrong"],
                "occurrences": payload["occurrences"],
                "lapses": payload["lapses"],
                "mastery_streak": payload["mastery_streak"],
                "mastery_target": payload["mastery_target"],
                "next_review_date": payload["next_review_date"],
                "claimable": state != ERROR_STATE_MASTERED,
                "evidence": Evidence(
                    kind="erratum",
                    on=_as_date(payload["last_review_date"]) or _as_date(row.created_at),
                    reference=payload["id"],
                    detail=payload["source_label"],
                ).as_dict(),
            }
        )
    return {
        "available": True,
        "mastery_target": MASTERY_REQUIRED_REPAIRS,
        # How many rows this payload *carries*, capped at ERRATA_PER_STATE.
        "counts": {state: len(items) for state, items in by_state.items()},
        # WP-45: how many there actually are. The dossier prints three counters
        # («2 ouvertes · 1 en réparation · 3 maîtrisées»), and a counter drawn
        # from `counts` would silently stop at twelve and read as the truth.
        "totals": _errata_totals(db, user=user),
        "by_state": by_state,
    }


def _errata_totals(db: Session, *, user: User) -> dict[str, int]:
    """Every erratum by WP-24 state, counted — not just the ones shown.

    Read as one column rather than aggregated in SQL on purpose: legacy rows
    carry «new»/«learning»/«review»/«relearning», and only
    :func:`normalize_error_state` folds those onto the three states the loop
    has. A ``GROUP BY state`` would report a fourth bucket nobody can name.
    """

    totals = {ERROR_STATE_OPEN: 0, ERROR_STATE_REPAIRING: 0, ERROR_STATE_MASTERED: 0}
    try:
        rows = db.execute(select(UserError.state).where(UserError.user_id == user.id)).all()
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the errata totals could not be counted")
        return totals
    for (state,) in rows:
        totals[normalize_error_state(state)] += 1
    return totals


def _vocabulary_beliefs(db: Session, *, user: User) -> dict[str, Any]:
    """The stock: how many words the app assumes, and on whose authority.

    WP-29's known-word set is the cheap answer and the honest one — it labels
    its two halves (FSRS-nailed evidence, and the CEFR core list *assumed* from
    the estimate) rather than adding them into one unexplained number. When it
    cannot be built the FSRS counters stand alone, which is a smaller claim.
    """

    known: dict[str, Any] | None = None
    try:
        from app.services.lexical_coverage import known_word_set

        known = known_word_set(db, user=user).as_dict()
    except Exception:  # pragma: no cover - the lexicon is optional data
        logger.warning("learner_model: the known-word set is unavailable", exc_info=True)

    words: list[dict[str, Any]] = []
    try:
        service = VocabularyCoverageService(db)
        for item in service.recently_nailed_vocabulary(user=user, limit=WORDS_SHOWN):
            words.append(
                {
                    "word_id": item.get("word_id") or item.get("id"),
                    "word": item.get("word"),
                    "translation": item.get("translation"),
                    "bucket": item.get("bucket"),
                    "claimable": item.get("bucket") != "recently_nailed",
                    "evidence": Evidence(
                        kind="vocabulary_schedule",
                        on=_as_date(item.get("next_review") or item.get("due_at")),
                        reference=str(item.get("word_id") or ""),
                        detail=str(item.get("bucket") or ""),
                    ).as_dict(),
                }
            )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the vocabulary stock could not be read")

    return {
        "available": known is not None or bool(words),
        "known": known,
        "nailed_rule": {"retrievability": NAILED_RETRIEVABILITY},
        "words": words,
    }


def _today_belief(db: Session, *, user: User) -> dict[str, Any]:
    """Why today's scene is this scene — read from the plan, never recomputed.

    WP-28 §1: the payload is persisted with the plan because the line claims
    something about *the scene the learner has*. Recomputing it from the queue
    here would let a mistake made after the plan was built claim credit for it,
    which is the bug that test pins on the envelope.

    No journey means no plan and therefore no line. The page says so; it does
    not promise what today *will* target.
    """

    journey = _todays_journey(db, user=user)
    if journey is None:
        return {"has_journey": False, "because": None, "journey_id": None, "local_date": None}
    payload = (journey.plan_selection or {}).get("because")
    because: dict[str, Any] | None = None
    if isinstance(payload, dict):
        try:
            from app.schemas.daily_journey import JourneyBecause

            because = JourneyBecause.model_validate(payload).model_dump()
        except Exception:  # pragma: no cover - written through the same schema
            logger.warning("learner_model: the stored because payload is unreadable")
            because = None
    return {
        "has_journey": True,
        "journey_id": str(journey.id),
        "local_date": journey.local_date.isoformat() if journey.local_date else None,
        "status": journey.status,
        "because": because,
        "evidence": Evidence(
            kind="journey",
            on=journey.local_date,
            journey_id=str(journey.id),
        ).as_dict(),
    }


def _todays_journey(db: Session, *, user: User) -> DailyJourney | None:
    """The journey the learner is actually on, newest local date first.

    Deliberately its own read rather than ``DailyJourneyService.get_today``:
    that call needs the content adapters and can describe an *available*
    scenario, and a dossier must not be able to reach anything that generates.
    """

    try:
        stmt = (
            select(DailyJourney)
            .where(DailyJourney.user_id == user.id)
            .order_by(DailyJourney.local_date.desc(), DailyJourney.created_at.desc())
            .limit(1)
        )
        journey = db.execute(stmt).scalars().first()
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: today's journey could not be read")
        return None
    if journey is None:
        return None
    today = datetime.now(UTC).date()
    if journey.local_date and journey.local_date < today:
        # Yesterday's scene is not today's reason. WP-28: no journey, no line.
        return None
    return journey


def _recent_claims(db: Session, *, user: User) -> list[dict[str, Any]]:
    """The learner's own claims, checked and unchecked, newest first."""

    try:
        rows = (
            db.query(PilotEvent)
            .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == CLAIM_EVENT_TYPE)
            .order_by(PilotEvent.occurred_at.desc())
            .limit(CLAIMS_SHOWN)
            .all()
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the claim ledger could not be read")
        return []
    claims: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        claims.append(
            {
                "kind": row.entity_type,
                "target_id": row.entity_id,
                "stage": payload.get("stage"),
                "verdict": payload.get("verdict"),
                "label": payload.get("label"),
                "on": row.occurred_at.isoformat() if row.occurred_at else None,
            }
        )
    return claims


# ---------------------------------------------------------------------------
# «Je connais déjà» — the claim, and the check that stands between it and the
# schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClaimItem:
    """One question. ``accepted`` never crosses the wire."""

    index: int
    kind: str
    instruction_fr: str
    prompt_fr: str
    placeholder_fr: str
    accepted: tuple[str, ...] = ()

    def as_public(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "instruction_fr": self.instruction_fr,
            "prompt_fr": self.prompt_fr,
            "placeholder_fr": self.placeholder_fr,
        }


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    """The two items, or an honest reason there are not two."""

    kind: str
    target_id: str
    label: str
    verifiable: bool
    items: list[ClaimItem] = field(default_factory=list)
    reason: str | None = None
    message_fr: str | None = None

    def as_public(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "label": self.label,
            "verifiable": self.verifiable,
            "items_required": CLAIM_ITEMS_REQUIRED,
            "items": [item.as_public() for item in self.items],
            "reason": self.reason,
            "message_fr": self.message_fr,
        }


@dataclass(frozen=True, slots=True)
class ClaimVerdict:
    """What the check found, and what it changed. ``advanced`` is the only write."""

    kind: str
    target_id: str
    verdict: str
    items_correct: int
    items_total: int
    advanced: bool
    message_fr: str
    next_review_date: str | None = None
    state: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)

    def as_public(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "verdict": self.verdict,
            "items_correct": self.items_correct,
            "items_total": self.items_total,
            "advanced": self.advanced,
            "message_fr": self.message_fr,
            "next_review_date": self.next_review_date,
            "state": self.state,
            "results": self.results,
        }


class ClaimRefused(Exception):
    """A claim about something that is not the learner's, or not a claim kind."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def build_claim_check(db: Session, *, user: User, kind: str, target_id: str) -> ClaimCheck:
    """The two questions this claim has to answer, built from stored records.

    Deterministic in ``(kind, target_id)`` and the stored row, so the verify
    call rebuilds exactly the same items without a session table: the claim
    check is a function of the learner's own data, not of a server-side draft
    that could expire between two taps.
    """

    if kind == CLAIM_KIND_ERRATUM:
        return _erratum_check(db, user=user, target_id=target_id)
    if kind == CLAIM_KIND_WORD:
        return _word_check(db, user=user, target_id=target_id)
    raise ClaimRefused("unknown_claim_kind")


def record_claim_opened(db: Session, *, user: User, check: ClaimCheck) -> None:
    """The claim itself, before any answer. Recorded even if it is abandoned.

    A learner who says «je connais déjà» and then closes the page has still told
    us something; the ledger keeps it, and nothing downstream reads it as
    knowledge.
    """

    _record_claim(
        db,
        user=user,
        kind=check.kind,
        target_id=check.target_id,
        payload={
            "stage": CLAIM_STAGE_OPENED,
            "label": check.label,
            "verifiable": check.verifiable,
            "reason": check.reason,
            "version": DOSSIER_VERSION,
        },
    )


def verify_claim(
    db: Session, *, user: User, kind: str, target_id: str, answers: list[str]
) -> ClaimVerdict:
    """Grade the two items and, only if both are right, advance the schedule.

    The order is the policy: grade first, write second. A failed check must be
    free — no lapse, no ease cost, no reschedule — so nothing is written on the
    way in, and the single advance below is the only write in this module.
    """

    check = build_claim_check(db, user=user, kind=kind, target_id=target_id)
    if not check.verifiable:
        verdict = ClaimVerdict(
            kind=check.kind,
            target_id=check.target_id,
            verdict=VERDICT_UNVERIFIABLE,
            items_correct=0,
            items_total=len(check.items),
            advanced=False,
            message_fr=check.message_fr or _UNVERIFIABLE_FR["no_two_items"],
        )
        _record_verdict(db, user=user, check=check, verdict=verdict)
        return verdict

    given = [str(value or "") for value in answers]
    results: list[dict[str, Any]] = []
    correct = 0
    for item in check.items:
        answer = given[item.index] if item.index < len(given) else ""
        # One checker for every item, the same one the journey's recall steps
        # use. A second matcher here would be a second definition of "right".
        is_correct = answer_matches(answer, list(item.accepted))
        correct += 1 if is_correct else 0
        results.append({"index": item.index, "kind": item.kind, "is_correct": is_correct})

    passed = correct == len(check.items) and len(check.items) >= CLAIM_ITEMS_REQUIRED
    advanced = False
    next_review_date: str | None = None
    state: str | None = None
    if passed:
        advanced, next_review_date, state = _advance_after_pass(
            db, user=user, kind=check.kind, target_id=check.target_id
        )

    verdict = ClaimVerdict(
        kind=check.kind,
        target_id=check.target_id,
        verdict=VERDICT_VERIFIED if passed else VERDICT_NOT_YET,
        items_correct=correct,
        items_total=len(check.items),
        advanced=advanced,
        message_fr=_VERDICT_FR[VERDICT_VERIFIED if passed else VERDICT_NOT_YET],
        next_review_date=next_review_date,
        state=state,
        results=results,
    )
    _record_verdict(db, user=user, check=check, verdict=verdict)
    return verdict


def _advance_after_pass(
    db: Session, *, user: User, kind: str, target_id: str
) -> tuple[bool, str | None, str | None]:
    """The only write. Reached from one place, and only when both items passed.

    Both branches go through the service that owns the schedule —
    ``ErrorMemoryService.review_error`` (WP-24's SM-2 wrapper and mastery
    lifecycle) and ``VocabularyCreditService.apply`` (the one vocabulary credit
    policy). Writing ``next_review_date`` here would be a third scheduler.
    """

    if kind == CLAIM_KIND_ERRATUM:
        service = ErrorMemoryService(db)
        try:
            error = service.review_error(
                user=user,
                error_id=UUID(str(target_id)),
                rating=CLAIM_PASS_RATING,
                repaired=True,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("learner_model: the erratum schedule could not be advanced")
            return False, None, None
        if error is None:
            return False, None, None
        return (
            True,
            error.next_review_date.isoformat() if error.next_review_date else None,
            normalize_error_state(error.state),
        )

    word = _word_row(db, user=user, target_id=target_id)
    if word is None:
        return False, None, None
    try:
        result = VocabularyCreditService(db).apply(
            user=user,
            word=word,
            # Verified production, unassisted: the same event the journey books
            # for an unaided correct answer. Never `produced_incorrect` on the
            # other branch — a failed claim costs the learner nothing.
            event_type="produced_correct",
            source_type="dossier",
            source_payload={"claim": CLAIM_KIND_WORD, "version": DOSSIER_VERSION},
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("learner_model: the vocabulary schedule could not be advanced")
        return False, None, None
    return True, None, str(result.credit_kind)


# ---------------------------------------------------------------------------
# Building the two items
# ---------------------------------------------------------------------------


def _erratum_check(db: Session, *, user: User, target_id: str) -> ClaimCheck:
    """Item 1 repairs the learner's own sentence; item 2 is narrower.

    The second item is a cloze on exactly the tokens that were wrong — built by
    diffing the stored pair, so it asks about the form rather than about the
    sentence. Where no cloze can be derived, a sibling erratum under the same
    memory key stands in. Where neither exists there is no second honest
    question, and the check says so instead of passing the claim on one answer.
    """

    error = _erratum_row(db, user=user, target_id=target_id)
    if error is None:
        return ClaimCheck(
            kind=CLAIM_KIND_ERRATUM,
            target_id=str(target_id),
            label="",
            verifiable=False,
            reason="not_found",
            message_fr=_UNVERIFIABLE_FR["not_found"],
        )
    label = str(error.display_label or error.error_pattern or "Reprise de langue")
    if normalize_error_state(error.state) == ERROR_STATE_MASTERED:
        return ClaimCheck(
            kind=CLAIM_KIND_ERRATUM,
            target_id=str(error.id),
            label=label,
            verifiable=False,
            reason="already_mastered",
            message_fr=_UNVERIFIABLE_FR["already_mastered"],
        )

    correction = str(error.correction or "").strip()
    learner_text = str(error.original_text or "").strip()
    items: list[ClaimItem] = []
    if correction:
        # The repair card's own wording, so the question a learner meets here is
        # the question they meet in the Cahier.
        task = ErrorMemoryService(db).build_review_task(user=user, error_id=error.id) or {}
        items.append(
            ClaimItem(
                index=0,
                kind="repair",
                instruction_fr=str(task.get("instruction") or _ITEM_COPY["repair"]["instruction"]),
                prompt_fr=str(
                    task.get("prompt") or f"Reprenez cette faute : {learner_text or label}"
                ),
                placeholder_fr=str(
                    task.get("placeholder") or _ITEM_COPY["repair"]["placeholder"]
                ),
                accepted=(correction,),
            )
        )

    cloze = _cloze_item(index=1, learner_text=learner_text, correction=correction)
    if cloze is not None:
        items.append(cloze)
    else:
        sibling = _sibling_erratum(db, user=user, error=error)
        if sibling is not None and sibling.correction:
            task = ErrorMemoryService(db).build_review_task(user=user, error_id=sibling.id) or {}
            items.append(
                ClaimItem(
                    index=1,
                    kind="repair",
                    instruction_fr=str(
                        task.get("instruction") or _ITEM_COPY["repair"]["instruction"]
                    ),
                    prompt_fr=str(
                        task.get("prompt")
                        or f"Reprenez cette faute : {sibling.original_text or label}"
                    ),
                    placeholder_fr=str(
                        task.get("placeholder") or _ITEM_COPY["repair"]["placeholder"]
                    ),
                    accepted=(str(sibling.correction).strip(),),
                )
            )

    if len(items) < CLAIM_ITEMS_REQUIRED:
        return ClaimCheck(
            kind=CLAIM_KIND_ERRATUM,
            target_id=str(error.id),
            label=label,
            verifiable=False,
            reason="no_two_items",
            message_fr=_UNVERIFIABLE_FR["no_two_items"],
        )
    return ClaimCheck(
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        label=label,
        verifiable=True,
        items=items,
    )


def _word_check(db: Session, *, user: User, target_id: str) -> ClaimCheck:
    """Produce the word from its gloss, then place it in a sentence.

    Item 2 is the word's own example sentence with the word removed where one is
    stored, and the reverse direction (French → sense) otherwise. A word with
    neither a gloss nor an example cannot be asked about honestly at all.
    """

    word = _word_row(db, user=user, target_id=target_id)
    if word is None:
        return ClaimCheck(
            kind=CLAIM_KIND_WORD,
            target_id=str(target_id),
            label="",
            verifiable=False,
            reason="not_found",
            message_fr=_UNVERIFIABLE_FR["not_found"],
        )
    label = str(word.word or "")
    surface = label.strip()
    gloss = _gloss_for(word, user=user)
    items: list[ClaimItem] = []
    if gloss and surface:
        accepted = [surface]
        if word.normalized_word and str(word.normalized_word) != surface:
            accepted.append(str(word.normalized_word))
        items.append(
            ClaimItem(
                index=0,
                kind="production",
                instruction_fr=_ITEM_COPY["production"]["instruction"],
                prompt_fr=f"Comment dit-on « {gloss} » ?",
                placeholder_fr=_ITEM_COPY["production"]["placeholder"],
                accepted=tuple(accepted),
            )
        )

    example = str(word.example_sentence or "").strip()
    cloze = _cloze_item(index=1, learner_text=None, correction=example, target=surface)
    if cloze is not None:
        items.append(cloze)
    elif gloss and surface:
        items.append(
            ClaimItem(
                index=1,
                kind="meaning",
                instruction_fr=_ITEM_COPY["meaning"]["instruction"],
                prompt_fr=f"Que veut dire « {surface} » ?",
                placeholder_fr=_ITEM_COPY["meaning"]["placeholder"],
                accepted=tuple(_gloss_variants(gloss)),
            )
        )

    if len(items) < CLAIM_ITEMS_REQUIRED:
        return ClaimCheck(
            kind=CLAIM_KIND_WORD,
            target_id=str(word.id),
            label=label,
            verifiable=False,
            reason="no_two_items",
            message_fr=_UNVERIFIABLE_FR["no_two_items"],
        )
    return ClaimCheck(
        kind=CLAIM_KIND_WORD,
        target_id=str(word.id),
        label=label,
        verifiable=True,
        items=items,
    )


def _cloze_item(
    *,
    index: int,
    learner_text: str | None,
    correction: str,
    target: str | None = None,
) -> ClaimItem | None:
    """A gap over the tokens that were actually wrong, or over a known word.

    Two callers, one shape. For an erratum the blanked tokens are the ones the
    correction added — the gender article, the agreement, the tense — which is a
    narrower question than "rewrite the sentence". For a word it is the word
    itself inside its stored example.

    Returns ``None`` whenever the gap would be unfair or empty: a one-token
    sentence, a correction that differs from the learner's text everywhere, or
    an example that does not contain the word at all.
    """

    sentence = " ".join(str(correction or "").split())
    if not sentence:
        return None
    tokens = sentence.split()
    if len(tokens) < 2:
        return None

    if target is not None:
        folded_target = fold_for_comparison(target)
        if not folded_target:
            return None
        positions = [
            position
            for position, token in enumerate(tokens)
            if fold_for_comparison(token) == folded_target
        ]
        missing = [target]
    else:
        known = {fold_for_comparison(token) for token in str(learner_text or "").split()}
        positions = [
            position
            for position, token in enumerate(tokens)
            if fold_for_comparison(token) and fold_for_comparison(token) not in known
        ]
        missing = [tokens[position] for position in positions]

    if not positions or len(positions) > 2 or len(positions) == len(tokens):
        return None
    if positions[-1] - positions[0] != len(positions) - 1:
        # Non-contiguous gaps ask two questions in one box.
        return None

    gapped = list(tokens)
    for position in positions:
        gapped[position] = "…"
    prompt = " ".join(gapped)
    expected = " ".join(missing)
    if not fold_for_comparison(expected):
        return None
    return ClaimItem(
        index=index,
        kind="cloze",
        instruction_fr=_ITEM_COPY["cloze"]["instruction"],
        prompt_fr=f"« {prompt} »",
        placeholder_fr=_ITEM_COPY["cloze"]["placeholder"],
        accepted=(expected,),
    )


# ---------------------------------------------------------------------------
# Rows and small helpers
# ---------------------------------------------------------------------------


def _erratum_row(db: Session, *, user: User, target_id: str) -> UserError | None:
    try:
        identity = UUID(str(target_id))
    except (TypeError, ValueError):
        return None
    return (
        db.query(UserError)
        .filter(UserError.id == identity, UserError.user_id == user.id)
        .first()
    )


def _sibling_erratum(db: Session, *, user: User, error: UserError) -> UserError | None:
    """Another unfinished erratum of the same kind — same memory key or concept."""

    query = db.query(UserError).filter(
        UserError.user_id == user.id,
        UserError.id != error.id,
        UserError.correction.isnot(None),
    )
    if error.memory_key:
        query = query.filter(UserError.memory_key == error.memory_key)
    elif error.concept_id is not None:
        query = query.filter(UserError.concept_id == error.concept_id)
    else:
        return None
    for row in query.order_by(UserError.occurrences.desc()).limit(5).all():
        if normalize_error_state(row.state) != ERROR_STATE_MASTERED:
            return row
    return None


def _word_row(db: Session, *, user: User, target_id: str) -> VocabularyWord | None:
    try:
        identity = int(str(target_id))
    except (TypeError, ValueError):
        return None
    language = str(getattr(user, "target_language", None) or "fr").strip() or "fr"
    word = db.query(VocabularyWord).filter(VocabularyWord.id == identity).first()
    if word is None or str(word.language or "") != language:
        return None
    return word


def _gloss_for(word: VocabularyWord, *, user: User) -> str:
    """The learner's own language first, then the other stored translation."""

    native = str(getattr(user, "native_language", None) or "en").lower()
    ordered = (
        [word.german_translation, word.english_translation]
        if native.startswith("de")
        else [word.english_translation, word.german_translation]
    )
    for candidate in [*ordered, word.definition]:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def _gloss_variants(gloss: str) -> list[str]:
    """A stored gloss is often "die Rechnung, die Quittung"; each half counts."""

    parts = [part.strip() for chunk in gloss.split(";") for part in chunk.split(",")]
    variants = [part for part in parts if part]
    return variants or [gloss]


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _record_verdict(
    db: Session, *, user: User, check: ClaimCheck, verdict: ClaimVerdict
) -> None:
    _record_claim(
        db,
        user=user,
        kind=check.kind,
        target_id=check.target_id,
        payload={
            "stage": CLAIM_STAGE_CHECKED,
            "label": check.label,
            "verdict": verdict.verdict,
            "items_correct": verdict.items_correct,
            "items_total": verdict.items_total,
            "advanced": verdict.advanced,
            "version": DOSSIER_VERSION,
        },
    )


def _record_claim(
    db: Session, *, user: User, kind: str, target_id: str, payload: dict[str, Any]
) -> None:
    """The claim ledger. Never allowed to break the claim it is recording."""

    try:
        PilotEventService(db).record(
            CLAIM_EVENT_TYPE,
            user_id=user.id,
            entity_type=kind,
            entity_id=target_id,
            payload=payload,
        )
    except Exception:  # pragma: no cover - telemetry is never load-bearing
        logger.exception("learner_model: the claim could not be recorded")


__all__ = [
    "CLAIM_EVENT_TYPE",
    "CLAIM_ITEMS_REQUIRED",
    "CLAIM_KINDS",
    "CLAIM_KIND_ERRATUM",
    "CLAIM_KIND_WORD",
    "CLAIM_STAGE_CHECKED",
    "CLAIM_STAGE_OPENED",
    "DOSSIER_VERSION",
    "VERDICT_NOT_YET",
    "VERDICT_UNVERIFIABLE",
    "VERDICT_VERIFIED",
    "ClaimCheck",
    "ClaimItem",
    "ClaimRefused",
    "ClaimVerdict",
    "Dossier",
    "Evidence",
    "build_claim_check",
    "build_dossier",
    "record_claim_opened",
    "verify_claim",
]
