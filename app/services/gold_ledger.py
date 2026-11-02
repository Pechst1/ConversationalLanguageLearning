"""Package O-1 — the silent gold ledger (l'or, in shadow).

Every answer path hands its server-recorded facts to one function here. The
function turns them into a :class:`app.core.gold.GoldObservation`, reads the
learner's day from the ledger and writes what :func:`app.core.gold.mint` says.
Nothing here is shown to a learner while ``ATELIER_GOLD_MODE`` is ``shadow``:
the nightly report (:mod:`app.services.gold_report`) is the only reader until
O-2 puts l'or on screen.

Two promises, kept the same way at every entry point:

* **Never worth an answer.** Each entry point runs inside a SAVEPOINT
  (:func:`app.db.savepoint.best_effort`). A failure rolls back to it, is
  logged, and the learner's answer goes on as if the ledger did not exist.
* **Never twice.** ``(user_id, source_key)`` is unique and every key names the
  evidence itself (the journey step and target, the reply turn, the Forge
  attempt, the letter, the milestone), so an HTTP retry, a worker retry or a
  replayed relecture finds its entry and writes nothing.

Where the spec (``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §17) and this file
differ, the implementation note in the spec says why.

Reads and writes go through the caller's session; nothing here commits.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core import gold as core
from app.db.models.gold import GoldBalance, GoldLedgerEntry
from app.db.savepoint import best_effort, run_best_effort

_log = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_LIVE = "live"
MODES = (MODE_OFF, MODE_SHADOW, MODE_LIVE)

ENTRY_EARN = "earn"
ENTRY_MILESTONE = "milestone"
ENTRY_BONUS = "bonus"

SOURCE_JOURNEY_TARGET = "journey_target"
SOURCE_JOURNEY_REPLY = "journey_reply"
SOURCE_FORGE_ITEM = "forge_item"
SOURCE_LETTER = "letter"
SOURCE_MILESTONE = "milestone"
#: Owner request, 2 Nov 2026: a new word learned past the day's dose, one the
#: learner asked for («Noch 5 neue Wörter»), earns its gold.
SOURCE_EXTRA_WORD = "extra_word"

VOID_NOT_YET = "not_yet"
VOID_UNREAD = "unread"
VOID_WITHDRAWN = "withdrawn"
VOID_INJECTION = "injection"
#: A relecture's verdict pays, but the rule's best of the day is already paid (R1).
VOID_ALREADY_PAID = "already_paid"

#: §6: a timezone change moves the learner's gold day only once the new zone has
#: been claimed this long, so a change of zone cannot reset the plafond.
ZONE_SETTLES_AFTER = timedelta(days=7)
#: R4 (``concept_life.HELD_SPACED_GAP_HOURS``): the gap that makes a recall delayed.
DELAYED_RECALL_GAP = timedelta(hours=20)
#: A milestone counts from the learner's first ledger entry (less this slack), so
#: switching the ledger on never pays for rules held or épreuves passed before.
MILESTONE_SLACK = timedelta(hours=1)


def gold_mode() -> str:
    """``off`` · ``shadow`` · ``live`` (an unknown value reads as ``off``)."""

    raw = str(getattr(settings, "ATELIER_GOLD_MODE", MODE_SHADOW) or "").strip().lower()
    return raw if raw in MODES else MODE_OFF


def ledger_on() -> bool:
    """Shadow and live both write the ledger; only O-2's live mode will show it."""

    return gold_mode() != MODE_OFF


# ---------------------------------------------------------------------------
# Time, the day and the balance
# ---------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _now(now: datetime | None) -> datetime:
    return _aware(now) or datetime.now(UTC)


def _parse_instant(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return _aware(raw)
    if not raw:
        return None
    try:
        return _aware(datetime.fromisoformat(str(raw)))
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value is not None else None


def is_delayed_recall(previous_contact_at: datetime | None, *, now: datetime) -> bool:
    """R4: ≥ 20 h since the learner's last contact. No recorded contact is a
    first meeting, never a delayed recall."""

    previous = _aware(previous_contact_at)
    return previous is not None and _now(now) - previous >= DELAYED_RECALL_GAP


def _pinned_zone(db: Session, user: Any, now: datetime) -> tuple[str, dict[str, Any]]:
    """§6: the zone the learner's gold day is counted in, and what to remember about it.

    The zone of the learner's latest entry stays until a different profile zone
    has been claimed for :data:`ZONE_SETTLES_AFTER`; the claim is carried on each
    entry's evidence (``tz``, ``tz_claimed``, ``tz_claimed_since``), so this needs
    no column of its own.
    """

    from app.services.streak import user_timezone, valid_timezone

    claimed = user_timezone(user)
    last = (
        db.query(GoldLedgerEntry.evidence)
        .filter(GoldLedgerEntry.user_id == user.id)
        .order_by(GoldLedgerEntry.created_at.desc())
        .first()
    )
    evidence = dict((last[0] if last else None) or {})
    pinned = valid_timezone(evidence.get("tz"))
    if pinned is None or pinned == claimed:
        since = evidence.get("tz_claimed_since") if pinned == claimed else None
        return claimed, {"tz": claimed, "tz_claimed": claimed, "tz_claimed_since": since or now.isoformat()}
    since = _parse_instant(evidence.get("tz_claimed_since")) if evidence.get("tz_claimed") == claimed else None
    since = since or now
    zone = claimed if now - since >= ZONE_SETTLES_AFTER else pinned
    return zone, {"tz": zone, "tz_claimed": claimed, "tz_claimed_since": since.isoformat()}


@dataclass
class _Day:
    """The learner's gold day, read once per entry point and advanced as it writes."""

    local_date: date
    week_id: str
    zone: dict[str, Any]
    state: core.DayState


def _day_state(db: Session, *, user_id: Any, local_date: date) -> core.DayState:
    """R1 and R8 from the day's live earn entries (pending ones included)."""

    rows = (
        db.query(GoldLedgerEntry)
        .filter(
            GoldLedgerEntry.user_id == user_id,
            GoldLedgerEntry.local_date == local_date,
            GoldLedgerEntry.entry_kind == ENTRY_EARN,
            GoldLedgerEntry.state != core.STATE_VOID,
        )
        .all()
    )
    earned = 0
    best: dict[str, int] = {}
    for row in rows:
        breakdown = dict(row.breakdown or {})
        earned += int(breakdown.get("earned") or 0)
        value = int(breakdown.get("value") or 0)
        keys = list((row.evidence or {}).get("lifts") or [])
        if isinstance(row.target, dict) and row.target.get("kind") is not None:
            keys.append(core.target_key(row.target.get("kind"), row.target.get("id")))
        for key in keys:
            best[str(key)] = max(best.get(str(key), 0), value)
    return core.DayState(earned=earned, best=best)


#: How long a gold writer waits for the learner's credit lock: long enough to ride
#: out another request finishing, well under PostgreSQL's ``deadlock_timeout`` (1 s).
#: See :func:`_hold_credit`.
CREDIT_LOCK_TIMEOUT = "300ms"


def _hold_credit(db: Session, user: Any) -> None:
    """The learner's credit lock (``journey_learning.lock_learning_credit``), waited for
    at most :data:`CREDIT_LOCK_TIMEOUT`.

    Every writer reads the day and writes it under this lock (R1, R8). A journey answer
    already holds it, taken before its evidence rows. La Forge and its relecture get
    here with the answer's own rows written a moment before (the savepoint's flush), the
    reverse order: waiting without a bound could close a cycle with a journey answer
    that holds the learner and waits for one of those rows, and PostgreSQL's detector
    (1 s into the journey's wait) could abort the journey's statement. Giving up first
    makes the gold entry the casualty instead: its savepoint rolls back (undoing this
    timeout too) and the warning names it. SQLite (the tests) has no row locks.
    """

    from app.services.journey_learning import lock_learning_credit

    if db.get_bind().dialect.name != "postgresql":
        lock_learning_credit(db, user)
        return
    previous = db.execute(text("SELECT current_setting('lock_timeout')")).scalar()
    db.execute(text("SELECT set_config('lock_timeout', :value, true)"), {"value": CREDIT_LOCK_TIMEOUT})
    lock_learning_credit(db, user)
    db.execute(text("SELECT set_config('lock_timeout', :value, true)"), {"value": previous})


def _open_day(db: Session, user: Any, *, when: datetime, now: datetime) -> _Day:
    """Lock the learner's credit (as every evidence writer does), then read the day of ``when``."""

    _hold_credit(db, user)
    zone, zone_evidence = _pinned_zone(db, user, now)
    local = core.local_date(when, zone)
    return _Day(
        local_date=local,
        week_id=core.week_id(when),
        zone=zone_evidence,
        state=_day_state(db, user_id=user.id, local_date=local),
    )


def _bump_balance(db: Session, *, user_id: Any, earned: int, now: datetime) -> None:
    """The livret follows every settled change (a cache; :func:`recompute_balance` rebuilds it)."""

    if not earned:
        return
    row = db.get(GoldBalance, user_id)
    if row is None:
        row = GoldBalance(user_id=user_id, balance=0, earned_total=0, spent_total=0)
        db.add(row)
    row.balance = int(row.balance or 0) + int(earned)
    row.earned_total = int(row.earned_total or 0) + int(earned)
    row.updated_at = now
    db.flush([row])


def recompute_balance(db: Session, *, user_id: Any, now: datetime | None = None) -> GoldBalance:
    """Rebuild the livret from the settled ledger (the nightly job keeps the cache honest)."""

    now = _now(now)
    rows = (
        db.query(GoldLedgerEntry.amount)
        .filter(GoldLedgerEntry.user_id == user_id, GoldLedgerEntry.state == core.STATE_SETTLED)
        .all()
    )
    earned = sum(int(amount) for (amount,) in rows if int(amount) > 0)
    spent = -sum(int(amount) for (amount,) in rows if int(amount) < 0)
    row = db.get(GoldBalance, user_id)
    if row is None:
        row = GoldBalance(user_id=user_id)
        db.add(row)
    row.balance = earned - spent
    row.earned_total = earned
    row.spent_total = spent
    row.updated_at = now
    db.flush([row])
    return row


def _existing(db: Session, *, user_id: Any, source_key: str) -> GoldLedgerEntry | None:
    return (
        db.query(GoldLedgerEntry)
        .filter(GoldLedgerEntry.user_id == user_id, GoldLedgerEntry.source_key == source_key)
        .first()
    )


def _write_entry(
    db: Session,
    *,
    user_id: Any,
    day: _Day,
    amount: int,
    state: str,
    entry_kind: str,
    source_kind: str,
    source_key: str,
    target: dict[str, Any] | None,
    evidence: dict[str, Any],
    breakdown: dict[str, Any],
    now: datetime,
) -> GoldLedgerEntry | None:
    """Insert one entry unless its source key is already there (``None`` then)."""

    if _existing(db, user_id=user_id, source_key=source_key) is not None:
        return None
    entry = GoldLedgerEntry(
        user_id=user_id,
        amount=int(amount),
        entry_kind=entry_kind,
        state=state,
        source_kind=source_kind,
        source_key=source_key[:255],
        target=target,
        evidence={**evidence, **day.zone},
        breakdown=breakdown,
        rule_version=core.RULE_VERSION,
        local_date=day.local_date,
        week_id=day.week_id,
        created_at=now,
        settled_at=now if state == core.STATE_SETTLED else None,
    )
    db.add(entry)
    db.flush([entry])
    if state == core.STATE_SETTLED:
        _bump_balance(db, user_id=user_id, earned=int(amount), now=now)
    return entry


def _mint_and_write(
    db: Session,
    *,
    user_id: Any,
    day: _Day,
    observation: core.GoldObservation,
    source_kind: str,
    source_key: str,
    target: dict[str, Any] | None,
    evidence: dict[str, Any],
    now: datetime,
) -> GoldLedgerEntry | None:
    """One observation through the table; the day advances when an entry is written."""

    minted = core.mint(observation, day.state)
    if minted is None:
        return None
    entry = _write_entry(
        db,
        user_id=user_id,
        day=day,
        amount=minted.amount,
        state=minted.state,
        entry_kind=ENTRY_EARN,
        source_kind=source_kind,
        source_key=source_key,
        target=target,
        evidence={**evidence, "lifts": list(observation.lifts)} if observation.lifts else evidence,
        breakdown=minted.breakdown,
        now=now,
    )
    if entry is not None:
        day.state = core.advance(day.state, observation, minted)
    return entry


def _void(db: Session, entry: GoldLedgerEntry, *, reason: str, now: datetime) -> None:
    """Pilonné: a pending entry whose verdict paid nothing (or, for abuse, any entry)."""

    if entry.state == core.STATE_VOID:
        return
    if entry.state == core.STATE_SETTLED:
        _bump_balance(db, user_id=entry.user_id, earned=-int(entry.amount or 0), now=now)
    entry.state = core.STATE_VOID
    entry.voided_at = now
    entry.void_reason = reason
    db.add(entry)
    db.flush([entry])


def _target_json(kind: Any, target_id: Any) -> dict[str, str]:
    return {"kind": str(kind), "id": str(target_id)}


def _outcome_of(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


# ---------------------------------------------------------------------------
# The journey: recall items (§17 «journey targets»)
# ---------------------------------------------------------------------------


def snapshot_contacts(db: Session, *, user: Any, evaluation: Any) -> dict[str, datetime | None]:
    """R4: each target's last contact *before* this answer is credited.

    Taken before ``apply_learning_evidence`` stamps the targets with now. Only a
    met answer can be doubled, so anything else reads nothing.
    """

    if not ledger_on() or _outcome_of(getattr(evaluation, "outcome", None)) != core.OUTCOME_MET:
        return {}
    observations = list(getattr(evaluation, "observations", None) or [])
    if not observations:
        return {}
    return run_best_effort(
        db,
        "gold: last contacts",
        lambda: _last_contacts(db, user_id=user.id, targets=[obs.target for obs in observations]),
        default={},
        log=_log,
    )


def _last_contacts(db: Session, *, user_id: Any, targets: Iterable[Any]) -> dict[str, datetime | None]:
    from app.db.models.error import UserError
    from app.db.models.grammar import UserGrammarProgress
    from app.db.models.progress import UserVocabularyProgress

    contacts: dict[str, datetime | None] = {}
    for target in targets:
        kind = _outcome_of(getattr(target, "kind", None))
        target_id = str(getattr(target, "id", "") or "")
        key = core.target_key(kind, target_id)
        previous = None
        if kind == "vocabulary" and target_id.isdigit():
            row = (
                db.query(UserVocabularyProgress.last_review_date)
                .filter(UserVocabularyProgress.user_id == user_id, UserVocabularyProgress.word_id == int(target_id))
                .first()
            )
            previous = row[0] if row else None
        elif kind == "grammar" and target_id.isdigit():
            row = (
                db.query(UserGrammarProgress.last_review)
                .filter(UserGrammarProgress.user_id == user_id, UserGrammarProgress.concept_id == int(target_id))
                .first()
            )
            previous = row[0] if row else None
        elif kind == "error":
            try:
                error_id = UUID(target_id)
            except ValueError:
                error_id = None
            if error_id is not None:
                row = (
                    db.query(UserError.last_review_date)
                    .filter(UserError.user_id == user_id, UserError.id == error_id)
                    .first()
                )
                previous = row[0] if row else None
        contacts[key] = _aware(previous)
    return contacts


def _before_the_scene(journey: Any, step: Any) -> bool:
    """A warm-up: posed before the day showed anything (its scene, its reading).

    Only such an item can be a *delayed* recall: the items after the scene ask
    about words and rules the learner has just read there, minutes ago.
    """

    shown = {"scene", "read", "resolution"}
    firsts = [int(other.ordinal) for other in getattr(journey, "steps", None) or [] if str(other.kind) in shown]
    return not firsts or int(step.ordinal) < min(firsts)


def record_journey_recall(
    db: Session,
    *,
    user: Any,
    journey: Any,
    step: Any,
    task: Any,
    evaluation: Any,
    assistance: Any,
    retry: bool,
    contacts: dict[str, datetime | None] | None = None,
    now: datetime | None = None,
) -> None:
    """One answered recall item (a Rappel, a Règle item, a retry). Never raises."""

    if not ledger_on():
        return
    with best_effort(db, "gold: journey recall", log=_log):
        _record_journey_recall(
            db, user=user, journey=journey, step=step, task=task, evaluation=evaluation,
            assistance=assistance, retry=retry, contacts=contacts or {}, now=_now(now),
        )


def _record_journey_recall(
    db: Session,
    *,
    user: Any,
    journey: Any,
    step: Any,
    task: Any,
    evaluation: Any,
    assistance: Any,
    retry: bool,
    contacts: dict[str, datetime | None],
    now: datetime,
) -> None:
    outcome = _outcome_of(evaluation.outcome)
    if outcome not in core.PAYING_OUTCOMES or getattr(evaluation, "pending", False):
        return
    fmt = str(getattr(task, "evidence_format", None) or getattr(task, "task_type", None) or "")
    # A retry is the repair step (R7's exception): the solution was shown after the
    # miss, so the record says «solution»; the gold reads the learner's own help.
    category = core.Category.REPAIR if retry else core.category_for_format(fmt)
    help_used = _outcome_of(assistance) or "none"
    accent = getattr(evaluation, "slip_kind", None) == "accent"
    warmup = _before_the_scene(journey, step)
    base_evidence = {
        "category": str(category),
        "format": fmt,
        "outcome": outcome,
        "assistance": help_used,
        "accent_slip": accent,
        "retry": bool(retry),
        "warmup": warmup,
        "journey_id": str(journey.id),
        "step_id": str(step.id),
    }
    observations = [
        obs
        for obs in getattr(evaluation, "observations", None) or []
        if _outcome_of(obs.evidence_kind) not in {"not_yet", "unscored"}
    ]
    day = _open_day(db, user, when=now, now=now)
    if not observations:
        # «Qui a dit ça ?», a dictation whose line holds no tracked word: graded,
        # scheduling nothing. It pays as itself, once (the step is the unit).
        _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=core.GoldObservation(
                category=category, outcome=outcome, assistance=help_used, accent_slip=accent,
            ),
            source_kind=SOURCE_JOURNEY_TARGET,
            source_key=f"gold:journey:{journey.id}:{step.id}:unit",
            target=None,
            evidence={**base_evidence, "unit": fmt or "recall"},
            now=now,
        )
        return
    for observation in observations:
        kind = _outcome_of(observation.target.kind)
        target_id = str(observation.target.id)
        key = core.target_key(kind, target_id)
        evidence_kind = _outcome_of(observation.evidence_kind)
        # WP-130 B: a displayed sentence typed back keeps «supported» with no help.
        copy = (
            not retry
            and evidence_kind == "produced_supported"
            and _outcome_of(observation.assistance) == "none"
        )
        previous = contacts.get(key)
        delayed = not retry and warmup and is_delayed_recall(previous, now=now)
        _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=core.GoldObservation(
                category=category,
                outcome=outcome,
                assistance=help_used,
                accent_slip=accent,
                copy=copy,
                delayed_recall=delayed,
                target=key,
            ),
            source_kind=SOURCE_JOURNEY_TARGET,
            source_key=f"gold:journey:{journey.id}:{step.id}:{kind}:{target_id}",
            target=_target_json(kind, target_id),
            evidence={
                **base_evidence,
                "evidence_kind": evidence_kind,
                "copy": copy,
                "delayed_recall": delayed,
                "previous_contact_at": _iso(previous),
            },
            now=now,
        )


# ---------------------------------------------------------------------------
# The journey: reply turns (§17 «reply turns») and «Joli !»
# ---------------------------------------------------------------------------


def reply_source_key(journey_id: Any, step_id: Any, turn_position: int) -> str:
    from app.services.journey_contracts import effect_source_key

    return effect_source_key(journey_id=journey_id, effect=f"gold:reply:{step_id}:{int(turn_position)}")


def _reply_prefix(journey_id: Any, step_id: Any) -> str:
    return reply_source_key(journey_id, step_id, 0)[: -len("0")]


def record_journey_reply(
    db: Session,
    *,
    user: Any,
    journey: Any,
    step: Any,
    task: Any,
    evaluation: Any,
    assistance: Any,
    turn_position: int,
    turn_index: int,
    consumed_before: int,
    previous_outcome: str | None,
    now: datetime | None = None,
) -> None:
    """One reply turn of the scene. Never raises.

    ``turn_position`` is the turn's place in the thread (free turns included: the
    key), ``turn_index`` the evaluator's (free turns excluded: the repair slot).
    """

    if not ledger_on():
        return
    with best_effort(db, "gold: journey reply", log=_log):
        _record_journey_reply(
            db, user=user, journey=journey, step=step, task=task, evaluation=evaluation,
            assistance=assistance, turn_position=turn_position, turn_index=turn_index,
            consumed_before=consumed_before, previous_outcome=previous_outcome, now=_now(now),
        )


def _record_journey_reply(
    db: Session,
    *,
    user: Any,
    journey: Any,
    step: Any,
    task: Any,
    evaluation: Any,
    assistance: Any,
    turn_position: int,
    turn_index: int,
    consumed_before: int,
    previous_outcome: str | None,
    now: datetime,
) -> None:
    from app.services.journey_contracts import SCENE_QUESTION_GRACE
    from app.services.journey_conversation import is_repair_turn, normal_turns

    outcome = _outcome_of(evaluation.outcome)
    if outcome not in core.PAYING_OUTCOMES or getattr(evaluation, "pending", False):
        return
    if getattr(evaluation, "needs_repair", False) and not getattr(evaluation, "turn_consumed", True):
        # A turn that cost no exchange (the greeting nudge) pays nothing either.
        return
    cap = normal_turns(task) + (1 if getattr(task, "repair_allowed", False) else 0) + SCENE_QUESTION_GRACE
    if consumed_before >= cap:
        return  # R1: per turn, up to what the scene can take
    repair = is_repair_turn(task, turn_index) and previous_outcome not in (None, core.OUTCOME_MET)
    category = core.Category.REPAIR if repair else core.Category.FREE
    help_used = _outcome_of(assistance) or "none"
    lifts: list[str] = []
    for observation in getattr(evaluation, "observations", None) or []:
        if _outcome_of(observation.evidence_kind) in {"not_yet", "unscored"}:
            continue
        lifts.append(core.target_key(_outcome_of(observation.target.kind), observation.target.id))
    concept_evidence = [item for item in getattr(evaluation, "concept_evidence", None) or [] if isinstance(item, dict)]
    used_units = [item for item in concept_evidence if str(item.get("outcome") or "") == "correct"]
    for item in used_units:
        lifts.append(core.target_key("grammar", item.get("concept_id")))
    lifts = list(dict.fromkeys(lifts))
    day = _open_day(db, user, when=now, now=now)
    entry = _mint_and_write(
        db,
        user_id=user.id,
        day=day,
        observation=core.GoldObservation(
            category=category, outcome=outcome, assistance=help_used, lifts=tuple(lifts),
        ),
        source_kind=SOURCE_JOURNEY_REPLY,
        source_key=reply_source_key(journey.id, step.id, turn_position),
        target=None,
        evidence={
            "category": str(category),
            "format": "reply",
            "outcome": outcome,
            "assistance": help_used,
            "turn_position": int(turn_position),
            "turn_index": int(turn_index),
            "repair": repair,
            "feedback_reason": getattr(evaluation, "feedback_reason", None),
            "journey_id": str(journey.id),
            "step_id": str(step.id),
        },
        now=now,
    )
    joli = (
        entry is not None
        and category is core.Category.FREE
        and outcome == core.OUTCOME_MET
        and help_used == "none"
        and getattr(evaluation, "correction", None) is None
        and bool(used_units)
    )
    if joli:
        # «Joli !»: the day's unit used, unaided, without an erratum. Once a day,
        # outside the plafond.
        _write_entry(
            db,
            user_id=user.id,
            day=day,
            amount=core.JOLI_BONUS,
            state=core.STATE_SETTLED,
            entry_kind=ENTRY_BONUS,
            source_kind=SOURCE_JOURNEY_REPLY,
            source_key=f"gold:bonus:joli:{day.local_date.isoformat()}",
            target=None,
            evidence={
                "bonus": "joli",
                "journey_id": str(journey.id),
                "step_id": str(step.id),
                "turn_position": int(turn_position),
                "concept_ids": [str(item.get("concept_id")) for item in used_units],
            },
            breakdown={"base": core.JOLI_BONUS, "amount": core.JOLI_BONUS, "reason_fr": core.JOLI_LABEL_FR},
            now=now,
        )


# ---------------------------------------------------------------------------
# The journey: the finish (journée parfaite, milestones)
# ---------------------------------------------------------------------------


def record_journey_finish(
    db: Session, *, user: Any, journey: Any, complete: bool, now: datetime | None = None
) -> None:
    """A finished day: the perfect-day milestone, and every milestone reached. Never raises."""

    if not ledger_on():
        return
    now = _now(now)
    with best_effort(db, "gold: journey finish", log=_log):
        _hold_credit(db, user)
        if complete and _perfect_day(db, user=user, journey=journey):
            local = getattr(journey, "local_date", None) or core.local_date(now, _pinned_zone(db, user, now)[0])
            _write_milestone(
                db,
                user=user,
                milestone=core.Milestone.PERFECT_DAY,
                source_key=f"gold:milestone:perfect_day:{local.isoformat()}",
                reached_at=now,
                local=local,
                detail={"journey_id": str(journey.id)},
                now=now,
            )
        _reconcile_milestones(db, user=user, now=now)


def _perfect_day(db: Session, *, user: Any, journey: Any) -> bool:
    """§4.3: every scored step of the day met on the first try, unaided.

    A retry exists only after a miss; a skipped required step was not met; a reply
    step is met when every exchange it consumed was (its gold entries say so).
    """

    from app.services.daily_journey import RETRY_OF_KEY

    scored = 0
    for step in getattr(journey, "steps", None) or []:
        kind = str(step.kind)
        if kind not in {"recall", "respond"}:
            continue
        status = str(step.status)
        if status == "skipped" and getattr(step, "optional", False):
            continue
        if status != "completed":
            return False
        private = dict(step.private_task or {})
        if private.get(RETRY_OF_KEY):
            return False
        if any(str(level) != "none" for level in step.assistance_used or []):
            return False
        if kind == "recall":
            if str((private.get("result") or {}).get("outcome") or "") != core.OUTCOME_MET:
                return False
        else:
            consumed = [turn for turn in private.get("turns") or [] if isinstance(turn, dict) and not turn.get("free")]
            if not consumed:
                return False
            met = sum(
                1
                for entry in _reply_entries(db, user_id=user.id, journey_id=journey.id, step_id=step.id)
                if str((entry.evidence or {}).get("outcome") or "") == core.OUTCOME_MET
                and str((entry.evidence or {}).get("assistance") or "") == "none"
            )
            if met < len(consumed):
                return False
        scored += 1
    return scored > 0


def _reply_entries(db: Session, *, user_id: Any, journey_id: Any, step_id: Any) -> list[GoldLedgerEntry]:
    return (
        db.query(GoldLedgerEntry)
        .filter(
            GoldLedgerEntry.user_id == user_id,
            GoldLedgerEntry.source_key.like(_reply_prefix(journey_id, step_id) + "%"),
            GoldLedgerEntry.state != core.STATE_VOID,
        )
        .all()
    )


def _write_milestone(
    db: Session,
    *,
    user: Any,
    milestone: core.Milestone,
    source_key: str,
    reached_at: datetime,
    detail: dict[str, Any],
    now: datetime,
    local: date | None = None,
    target: dict[str, Any] | None = None,
) -> GoldLedgerEntry | None:
    if _existing(db, user_id=user.id, source_key=source_key) is not None:
        return None
    zone, zone_evidence = _pinned_zone(db, user, now)
    reached_at = _aware(reached_at) or now
    day = _Day(
        local_date=local or core.local_date(reached_at, zone),
        week_id=core.week_id(reached_at),
        zone=zone_evidence,
        state=core.DayState(),
    )
    amount = core.MILESTONE_VALUE[milestone]
    return _write_entry(
        db,
        user_id=user.id,
        day=day,
        amount=amount,
        state=core.STATE_SETTLED,
        entry_kind=ENTRY_MILESTONE,
        source_kind=SOURCE_MILESTONE,
        source_key=source_key,
        target=target,
        evidence={"milestone": str(milestone), "reached_at": reached_at.isoformat(), **detail},
        breakdown={
            "milestone": str(milestone),
            "base": amount,
            "amount": amount,
            "reason_fr": core.MILESTONE_LABEL_FR[milestone],
        },
        now=now,
    )


def reconcile_milestones(db: Session, *, user: Any, now: datetime | None = None) -> None:
    """Every milestone the learner has reached and the ledger has not paid. Never raises."""

    if not ledger_on():
        return
    now = _now(now)
    with best_effort(db, "gold: milestones", log=_log):
        _hold_credit(db, user)
        _reconcile_milestones(db, user=user, now=now)


def _milestone_since(db: Session, *, user_id: Any, now: datetime) -> datetime:
    first = db.query(func.min(GoldLedgerEntry.created_at)).filter(GoldLedgerEntry.user_id == user_id).scalar()
    return (_aware(first) or now) - MILESTONE_SLACK


def _reconcile_milestones(
    db: Session, *, user: Any, now: datetime, epreuves: bool = True, capabilities: bool = True
) -> None:
    """§4.3, once each: a rule held, an épreuve passed, a capability confirmed.

    Each is read from the record that decides it, so the ledger can never pay a
    milestone the learner's own pages do not show.
    """

    from app.db.models.cefr import UserLevelCheckpoint
    from app.db.models.grammar import UserGrammarProgress

    since = _milestone_since(db, user_id=user.id, now=now)
    held = (
        db.query(UserGrammarProgress.concept_id, UserGrammarProgress.held_at, UserGrammarProgress.tested_out_at)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.held_at.isnot(None))
        .all()
    )
    for concept_id, held_at, tested_out_at in held:
        held_at, tested_out_at = _aware(held_at), _aware(tested_out_at)
        if held_at is None or held_at < since:
            continue
        if tested_out_at is not None and abs((tested_out_at - held_at).total_seconds()) < 1:
            # A test-out pass places the rule at the top; it was not held through
            # practice, and La Forge already marks it with its own token.
            continue
        _write_milestone(
            db,
            user=user,
            milestone=core.Milestone.RULE_HELD,
            source_key=f"gold:milestone:rule_held:{concept_id}",
            reached_at=held_at,
            detail={"concept_id": str(concept_id)},
            target=_target_json("grammar", concept_id),
            now=now,
        )
    if not epreuves:
        passed = []
    else:
        passed = (
            db.query(UserLevelCheckpoint.band, UserLevelCheckpoint.passed_at)
            .filter(UserLevelCheckpoint.user_id == user.id, UserLevelCheckpoint.status == "passed")
            .all()
        )
    for band, passed_at in passed:
        passed_at = _aware(passed_at)
        if passed_at is None or passed_at < since:
            continue
        _write_milestone(
            db,
            user=user,
            milestone=core.Milestone.EPREUVE_PASSED,
            source_key=f"gold:milestone:epreuve:{band}",
            reached_at=passed_at,
            detail={"band": str(band)},
            now=now,
        )
    if not capabilities:
        return
    from app.services.journey_capabilities import capability_confirmed_at

    for capability, reached_at in capability_confirmed_at(db, user=user).items():
        reached_at = _aware(reached_at)
        if reached_at is None or reached_at < since:
            continue
        _write_milestone(
            db,
            user=user,
            milestone=core.Milestone.CAPABILITY_CONFIRMED,
            source_key=f"gold:milestone:capability:{capability}",
            reached_at=reached_at,
            detail={"capability": str(capability)},
            now=now,
        )


# ---------------------------------------------------------------------------
# The critic withdrew a released success (§17 «withdrawals»)
# ---------------------------------------------------------------------------


def note_released_grading_corrected(
    db: Session,
    *,
    user: Any,
    journey_id: Any,
    step_id: Any,
    outcome: Any,
    withdrawn_target_ids: Sequence[str],
    reason: str,
    now: datetime | None = None,
) -> None:
    """§3: settled gold stays settled when the grader erred; a pending entry of a
    withdrawn target is voided. Prompt injection voids the step's gold. Never raises."""

    if not ledger_on():
        return
    now = _now(now)
    with best_effort(db, "gold: released grading corrected", log=_log):
        corrected = _outcome_of(outcome)
        codes = {code.strip() for code in str(reason or "").split(",") if code.strip()}
        injection = any("injection" in code for code in codes)
        withdrawn = {str(value) for value in withdrawn_target_ids}
        prefixes = (f"gold:journey:{journey_id}:{step_id}:", _reply_prefix(journey_id, step_id))
        entries = (
            db.query(GoldLedgerEntry)
            .filter(
                GoldLedgerEntry.user_id == user.id,
                GoldLedgerEntry.source_key.like(prefixes[0] + "%") | GoldLedgerEntry.source_key.like(prefixes[1] + "%"),
            )
            .all()
        )
        for entry in entries:
            if entry.state == core.STATE_VOID:
                continue
            if injection:
                _void(db, entry, reason=VOID_INJECTION, now=now)
                continue
            target_id = str((entry.target or {}).get("id") or "")
            evidence = dict(entry.evidence or {})
            if target_id and target_id in withdrawn:
                if entry.state == core.STATE_PENDING:
                    _void(db, entry, reason=VOID_WITHDRAWN, now=now)
                    continue
                evidence["withdrawn"] = {"reason": reason, "at": now.isoformat()}
            elif evidence.get("outcome") and evidence.get("outcome") != corrected:
                evidence["critic"] = {"outcome": corrected, "reason": reason, "at": now.isoformat()}
            else:
                continue
            entry.evidence = evidence
            flag_modified(entry, "evidence")
            db.add(entry)
        db.flush()


# ---------------------------------------------------------------------------
# La Forge (§17 «La Forge»)
# ---------------------------------------------------------------------------


def forge_contact_before(db: Session, *, user: Any, concept_id: Any, rung: int, verdict: Any) -> datetime | None:
    """R4: the rule's last contact before this answer's evidence is written."""

    if not ledger_on() or concept_id is None:
        return None
    if not getattr(verdict, "checked", False) or not getattr(verdict, "correct", False):
        return None
    if core.category_for_rung(rung) not in core.SPACED_CATEGORIES:
        return None
    contacts = run_best_effort(
        db,
        "gold: forge last contact",
        lambda: _last_contacts(db, user_id=user.id, targets=[_Target("grammar", str(concept_id))]),
        default={},
        log=_log,
    )
    return contacts.get(core.target_key("grammar", concept_id))


@dataclass(frozen=True)
class _Target:
    kind: str
    id: str


_FORGE_OUTCOME = {"correct": core.OUTCOME_MET, "partial": core.OUTCOME_PARTIAL}


def _forge_observation(
    *,
    rung: int,
    outcome: str,
    checked: bool,
    reprise: bool,
    below_level: bool,
    delayed: bool,
    concept_id: Any,
) -> core.GoldObservation:
    # «A slip turned right»: the reprise brings the missed rule back and pays the repair.
    category = core.Category.REPAIR if reprise else core.category_for_rung(rung)
    return core.GoldObservation(
        category=category,
        outcome=_FORGE_OUTCOME.get(str(outcome), core.OUTCOME_NOT_YET),
        assistance="none",
        checked=checked,
        delayed_recall=delayed and not reprise,
        below_level=below_level and not reprise,
        target=core.target_key("grammar", concept_id),
    )


def record_forge_item(
    db: Session,
    *,
    user: Any,
    attempt: Any,
    rung: int,
    verdict: Any,
    mode: str,
    reprise: bool,
    below_level: bool,
    level_before: int | None,
    contact_before: datetime | None,
    now: datetime | None = None,
) -> None:
    """One answered Forge item (séance or test-out, first submission only). Never raises."""

    if not ledger_on() or getattr(attempt, "concept_id", None) is None:
        return
    with best_effort(db, "gold: forge item", log=_log):
        now = _now(now)
        if verdict.checked:
            if str(verdict.outcome) not in _FORGE_OUTCOME:
                return
            outcome, checked = str(verdict.outcome), True
        elif getattr(verdict, "local", None) == "correct":
            # R6: the instant local reading uses the rule; the relecture decides.
            outcome, checked = "correct", False
        else:
            return
        concept_id = attempt.concept_id
        observation = _forge_observation(
            rung=rung, outcome=outcome, checked=checked, reprise=reprise, below_level=below_level,
            delayed=is_delayed_recall(contact_before, now=now), concept_id=concept_id,
        )
        day = _open_day(db, user, when=now, now=now)
        _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=observation,
            source_kind=SOURCE_FORGE_ITEM,
            source_key=f"gold:forge:{attempt.id}",
            target=_target_json("grammar", concept_id),
            evidence={
                "category": str(observation.category),
                "rung": int(rung),
                "round": str(getattr(attempt, "round", "") or ""),
                "mode": str(mode),
                "outcome": str(verdict.outcome),
                "checked": bool(verdict.checked),
                "local": getattr(verdict, "local", None),
                "reprise": bool(reprise),
                "below_level": bool(below_level),
                "level_before": level_before,
                "delayed_recall": observation.delayed_recall,
                "previous_contact_at": _iso(contact_before),
                "session_id": str(getattr(attempt, "atelier_session_id", "") or ""),
                "attempt_id": str(attempt.id),
            },
            now=now,
        )


def settle_forge_item(
    db: Session,
    *,
    user: Any,
    attempt: Any,
    history_entry: dict[str, Any],
    verdict: Any,
    unread: bool,
    now: datetime | None = None,
) -> None:
    """The relecture landed (R6): settle or void the pending entry, revive an unread
    one, or mint the settled one a provisional miss did not. Never raises."""

    if not ledger_on() or getattr(attempt, "concept_id", None) is None:
        return
    with best_effort(db, "gold: forge relecture", log=_log):
        now = _now(now)
        _hold_credit(db, user)
        source_key = f"gold:forge:{attempt.id}"
        entry = _existing(db, user_id=user.id, source_key=source_key)
        outcome = str(getattr(verdict, "outcome", "") or "")
        pays = bool(getattr(verdict, "checked", False)) and outcome in _FORGE_OUTCOME and not unread
        if entry is not None:
            # Settled stays settled. A pulped entry stays pulped, except one nobody
            # could read: a retried review that does read it still counts, once
            # (the Forge's own rule for an unread answer).
            revivable = entry.state == core.STATE_VOID and entry.void_reason == VOID_UNREAD
            if entry.state != core.STATE_PENDING and not revivable:
                return
            if not pays:
                if entry.state == core.STATE_PENDING:
                    _void(db, entry, reason=VOID_UNREAD if unread else VOID_NOT_YET, now=now)
                return
            evidence = dict(entry.evidence or {})
            observation = _forge_observation(
                rung=int(evidence.get("rung") or 0), outcome=outcome, checked=True,
                reprise=bool(evidence.get("reprise")), below_level=bool(evidence.get("below_level")),
                delayed=False, concept_id=attempt.concept_id,
            )
            if revivable:
                # The day went on without the pulped entry: a later answer may have paid
                # the rule (R1) or spent the plafond (R8). The revival reads the day as it
                # stands now, so the rule's best is paid once and the plafond holds.
                minted = core.mint(observation, _day_state(db, user_id=user.id, local_date=entry.local_date))
            else:
                # A pending entry was part of the day all along (later answers saw it).
                minted = core.resettle(dict(entry.breakdown or {}), observation)
            read = {**evidence, "outcome": outcome, "checked": True}
            if minted is None:
                # The verdict pays, but no more than the day already paid the rule.
                entry.evidence = read
                if entry.state == core.STATE_PENDING:
                    _void(db, entry, reason=VOID_ALREADY_PAID, now=now)
                else:
                    entry.voided_at, entry.void_reason = now, VOID_ALREADY_PAID
                    db.add(entry)
                    db.flush([entry])
                return
            entry.state = core.STATE_SETTLED
            entry.amount = minted.amount
            entry.breakdown = {**minted.breakdown, "provisional_amount": int((entry.breakdown or {}).get("amount") or 0)}
            entry.evidence = {**read, "settled_by": "relecture"}
            entry.settled_at = now
            entry.voided_at = None
            entry.void_reason = None
            db.add(entry)
            db.flush([entry])
            _bump_balance(db, user_id=user.id, earned=minted.amount, now=now)
            return
        if not pays:
            return
        when = _aware(getattr(attempt, "created_at", None)) or now
        observation = _forge_observation(
            rung=int(history_entry.get("rung") or 0), outcome=outcome, checked=True,
            reprise=bool(history_entry.get("reprise")), below_level=bool(history_entry.get("below_level")),
            delayed=False, concept_id=attempt.concept_id,
        )
        zone, zone_evidence = _pinned_zone(db, user, now)
        local = core.local_date(when, zone)
        day = _Day(
            local_date=local,
            week_id=core.week_id(when),
            zone=zone_evidence,
            state=_day_state(db, user_id=user.id, local_date=local),
        )
        _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=observation,
            source_kind=SOURCE_FORGE_ITEM,
            source_key=source_key,
            target=_target_json("grammar", attempt.concept_id),
            evidence={
                "category": str(observation.category),
                "rung": int(history_entry.get("rung") or 0),
                "round": str(getattr(attempt, "round", "") or ""),
                "outcome": outcome,
                "checked": True,
                "reprise": bool(history_entry.get("reprise")),
                "below_level": bool(history_entry.get("below_level")),
                "settled_by": "relecture",
                "session_id": str(getattr(attempt, "atelier_session_id", "") or ""),
                "attempt_id": str(attempt.id),
            },
            now=now,
        )


def record_rule_held(db: Session, *, user: Any, now: datetime | None = None) -> None:
    """A Forge answer made a rule held: pay that milestone now, not overnight. Never raises."""

    if not ledger_on():
        return
    now = _now(now)
    with best_effort(db, "gold: rule held", log=_log):
        _hold_credit(db, user)
        _reconcile_milestones(db, user=user, now=now, epreuves=False, capabilities=False)


# ---------------------------------------------------------------------------
# Courrier letters (§17 «letters»)
# ---------------------------------------------------------------------------


def record_letter(db: Session, *, user: Any, mission: Any, attempts: Sequence[Any], now: datetime | None = None) -> None:
    """A completed Courrier letter, judged on its first written attempt (R7). Never raises.

    A letter answered from the journey («jour de lettre») was paid turn by turn as
    the scene's reply; it pays nothing a second time here.
    """

    if not ledger_on():
        return
    with best_effort(db, "gold: letter", log=_log):
        from app.services.story_correspondence import JOURNEY_ANSWER_MODE

        now = _now(now)
        if any(
            str(getattr(attempt, "mode", "") or "") == JOURNEY_ANSWER_MODE
            or str((getattr(attempt, "answer_payload", None) or {}).get("source") or "") == JOURNEY_ANSWER_MODE
            for attempt in attempts
        ):
            return
        written = sorted(
            (attempt for attempt in attempts if getattr(attempt, "created_at", None) is not None),
            key=lambda attempt: _aware(attempt.created_at),
        )
        if not written:
            return
        first = written[0]
        verdict = str(getattr(first, "verdict", "") or "")
        outcome = {"accepted": core.OUTCOME_MET, "partial": core.OUTCOME_PARTIAL}.get(verdict)
        if outcome is None:
            return  # needs_revision, unassessed (R6), needs_review
        day = _open_day(db, user, when=now, now=now)
        _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=core.GoldObservation(category=core.Category.LETTER, outcome=outcome, assistance="none"),
            source_kind=SOURCE_LETTER,
            source_key=f"gold:letter:{mission.id}",
            target=None,
            evidence={
                "category": str(core.Category.LETTER),
                "outcome": outcome,
                "verdict": verdict,
                "assistance": "none",
                "mission_id": str(mission.id),
                "attempt_id": str(first.id),
                "attempts": len(written),
                "mode": str(getattr(first, "mode", "") or ""),
            },
            now=now,
        )


# ---------------------------------------------------------------------------
# Extra new words (owner request, 2 Nov 2026)
# ---------------------------------------------------------------------------


def extra_word_source_key(word_id: Any) -> str:
    return f"gold:extra_word:{int(word_id)}"


def record_extra_word(
    db: Session,
    *,
    user: Any,
    word_id: int,
    passed: bool,
    checked_answer: bool,
    now: datetime | None = None,
) -> GoldLedgerEntry | None:
    """A new word the learner asked for past the day's dose, answered right. Never raises.

    Whether ``word_id`` is such a word is
    :func:`app.services.vocabulary_pace.is_extra_new_word`'s answer, read here.

    Owner request, 2 Nov: «noch mehr Wörter pro Tag … das sollte auch mehr XP
    geben». Each extra word pays once, the first time it is answered right
    (``passed``): a typed answer the server checked pays as typed recall, a card
    the learner turned and rated as recognition. It goes through the table like
    every other entry (:func:`_mint_and_write`): the day's best per word (R1),
    the plafond (R8), the day's earned gold and the livret all count it. A miss
    pays nothing and costs nothing.
    """

    if not ledger_on() or not passed:
        return None
    result: GoldLedgerEntry | None = None
    with best_effort(db, "gold: extra word", log=_log):
        from app.services.vocabulary_pace import is_extra_new_word

        now = _now(now)
        if _existing(db, user_id=user.id, source_key=extra_word_source_key(word_id)) is not None:
            return None  # paid once, the first time it was answered right
        if not is_extra_new_word(db, user, int(word_id), now=now):
            return None
        category = core.Category.TYPED if checked_answer else core.Category.RECOGNISED
        target = core.target_key("vocabulary", int(word_id))
        day = _open_day(db, user, when=now, now=now)
        result = _mint_and_write(
            db,
            user_id=user.id,
            day=day,
            observation=core.GoldObservation(category=category, outcome=core.OUTCOME_MET, target=target),
            source_kind=SOURCE_EXTRA_WORD,
            source_key=extra_word_source_key(word_id),
            target=_target_json("vocabulary", int(word_id)),
            evidence={
                "category": str(category),
                "outcome": core.OUTCOME_MET,
                "assistance": "none",
                "word_id": int(word_id),
                "extra_word": True,
                "checked_answer": bool(checked_answer),
            },
            now=now,
        )
    return result


def day_earned(db: Session, *, user: Any, now: datetime | None = None) -> int:
    """The learner's gold earned on their gold day so far (R8's running total)."""

    now = _now(now)
    zone, _evidence = _pinned_zone(db, user, now)
    return int(_day_state(db, user_id=user.id, local_date=core.local_date(now, zone)).earned)


__all__ = [
    "DELAYED_RECALL_GAP",
    "ENTRY_BONUS",
    "ENTRY_EARN",
    "ENTRY_MILESTONE",
    "MODE_LIVE",
    "MODE_OFF",
    "MODE_SHADOW",
    "SOURCE_EXTRA_WORD",
    "SOURCE_FORGE_ITEM",
    "SOURCE_JOURNEY_REPLY",
    "SOURCE_JOURNEY_TARGET",
    "SOURCE_LETTER",
    "SOURCE_MILESTONE",
    "ZONE_SETTLES_AFTER",
    "forge_contact_before",
    "gold_mode",
    "day_earned",
    "extra_word_source_key",
    "is_delayed_recall",
    "ledger_on",
    "note_released_grading_corrected",
    "recompute_balance",
    "reconcile_milestones",
    "record_extra_word",
    "record_forge_item",
    "record_journey_finish",
    "record_journey_recall",
    "record_journey_reply",
    "record_letter",
    "record_rule_held",
    "reply_source_key",
    "settle_forge_item",
    "snapshot_contacts",
]
