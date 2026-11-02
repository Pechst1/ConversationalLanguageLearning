"""Package O-2 — l'or on screen: what the counter, the day's seal and «D'où vient ton or» read.

``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §16. Read-only: every amount comes from
the ledger (:mod:`app.services.gold_ledger` writes it), nothing here mints. Who
sees it is :func:`app.services.gold_ledger.gold_visible`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core import gold as core
from app.db.models.gold import GoldBalance, GoldLedgerEntry
from app.services import gold_ledger

#: The weeks «D'où vient ton or» can open: ``2026-W45``.
WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value else None


def _rhythm(user: Any) -> str:
    from app.services.journey_rhythm import rhythm_for_minutes

    rhythm = str(rhythm_for_minutes(getattr(user, "daily_goal_minutes", None)))
    return rhythm if rhythm in core.JOURNEE_PLEINE_MARK else "regulier"


def _delayed(breakdown: dict[str, Any]) -> bool:
    return any(str(factor.get("name")) == "rappel_differe" for factor in breakdown.get("factors") or [])


def _subjects(db: Session, entries: list[GoldLedgerEntry]) -> dict[str, str]:
    """The word or the rule each entry paid for (``vocabulary:12`` → «le chat»)."""

    from app.db.models.grammar import GrammarConcept
    from app.db.models.vocabulary import VocabularyWord

    ids: dict[str, set[int]] = defaultdict(set)
    for entry in entries:
        target = entry.target if isinstance(entry.target, dict) else None
        if target and str(target.get("id") or "").isdigit():
            ids[str(target.get("kind"))].add(int(target["id"]))
    subjects: dict[str, str] = {}
    if ids.get("vocabulary"):
        for word_id, word in db.query(VocabularyWord.id, VocabularyWord.word).filter(
            VocabularyWord.id.in_(ids["vocabulary"])
        ):
            subjects[core.target_key("vocabulary", word_id)] = str(word)
    if ids.get("grammar"):
        for concept_id, name in db.query(GrammarConcept.id, GrammarConcept.name).filter(
            GrammarConcept.id.in_(ids["grammar"])
        ):
            subjects[core.target_key("grammar", concept_id)] = str(name)
    return subjects


def _entry(entry: GoldLedgerEntry, subjects: dict[str, str]) -> dict[str, Any]:
    breakdown = dict(entry.breakdown or {})
    evidence = dict(entry.evidence or {})
    target = entry.target if isinstance(entry.target, dict) else None
    key = core.target_key(target.get("kind"), target.get("id")) if target else None
    return {
        "id": str(entry.id),
        "amount": int(entry.amount or 0),
        "state": str(entry.state),
        "entry_kind": str(entry.entry_kind),
        "source_kind": str(entry.source_kind),
        "category": breakdown.get("category") or evidence.get("category"),
        "reason_fr": str(breakdown.get("reason_fr") or ""),
        "subject": subjects.get(key) if key else None,
        "delayed_recall": _delayed(breakdown),
        "plafond_cut": int(breakdown.get("amount", entry.amount) or 0) < int(breakdown.get("earned") or 0),
        "local_date": entry.local_date.isoformat(),
        "created_at": _iso(entry.created_at),
        "settled_at": _iso(entry.settled_at),
        "voided_at": _iso(entry.voided_at),
        "void_reason": entry.void_reason,
    }


class _DayTotals:
    __slots__ = ("settled", "earn_settled", "pending", "earned_before_plafond")

    def __init__(self) -> None:
        self.settled = 0
        self.earn_settled = 0
        self.pending = 0
        self.earned_before_plafond = 0

    def add(self, entry: GoldLedgerEntry) -> None:
        if entry.state == core.STATE_VOID:
            return
        amount = int(entry.amount or 0)
        if entry.state == core.STATE_PENDING:
            self.pending += amount
        elif entry.state == core.STATE_SETTLED:
            self.settled += amount
            if entry.entry_kind == gold_ledger.ENTRY_EARN:
                self.earn_settled += amount
        if entry.entry_kind == gold_ledger.ENTRY_EARN:
            self.earned_before_plafond += int((entry.breakdown or {}).get("earned") or 0)


def _plafond_state(earned_before_plafond: int) -> str:
    """R8 as the learner meets it: ``open``, ``half`` (past 90) or ``closed`` (150)."""

    if earned_before_plafond >= core.PLAFOND_STOPS_AT:
        return "closed"
    if earned_before_plafond > core.PLAFOND_FULL_RATE_UP_TO:
        return "half"
    return "open"


def _today(db: Session, user: Any, now: datetime) -> date:
    zone, _evidence = gold_ledger._pinned_zone(db, user, now)
    return core.local_date(now, zone)


def week_bounds(week_id: str) -> tuple[date, date] | None:
    """Monday and Sunday of ``2026-W45`` (``None`` for a malformed week)."""

    match = WEEK_PATTERN.match(str(week_id or ""))
    if not match:
        return None
    try:
        monday = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
    except ValueError:
        return None
    return monday, monday + timedelta(days=6)


def build_gold_view(db: Session, *, user: Any, now: datetime | None = None) -> dict[str, Any]:
    """``GET /api/v1/gold``: the livret, the day and the week."""

    if not gold_ledger.gold_visible(user):
        return {"visible": False}
    now = _aware(now) or datetime.now(UTC)
    today = _today(db, user, now)
    week_id = core.week_id(now)
    rhythm = _rhythm(user)
    mark = core.JOURNEE_PLEINE_MARK[rhythm]
    monday = today - timedelta(days=today.weekday())
    rows = (
        db.query(GoldLedgerEntry)
        .filter(
            GoldLedgerEntry.user_id == user.id,
            GoldLedgerEntry.local_date >= min(monday, today - timedelta(days=1)),
        )
        .order_by(GoldLedgerEntry.created_at.asc())
        .all()
    )
    days: dict[date, _DayTotals] = defaultdict(_DayTotals)
    week = _DayTotals()
    for row in rows:
        days[row.local_date].add(row)
        if row.week_id == week_id:
            week.add(row)
    day = days[today]
    todays = [row for row in rows if row.local_date == today]
    subjects = _subjects(db, todays)
    balance = db.get(GoldBalance, user.id)
    week_days = [monday + timedelta(days=offset) for offset in range(7)]
    pleines = sum(1 for local in week_days if days[local].earn_settled >= mark)
    return {
        "visible": True,
        "mode": gold_ledger.gold_mode(),
        "balance": int(balance.balance) if balance is not None else 0,
        "today": {
            "local_date": today.isoformat(),
            "settled": day.settled,
            "earn_settled": day.earn_settled,
            "pending": day.pending,
            "earned_before_plafond": day.earned_before_plafond,
            "plafond": _plafond_state(day.earned_before_plafond),
            "plafond_full_rate_up_to": core.PLAFOND_FULL_RATE_UP_TO,
            "plafond_stops_at": core.PLAFOND_STOPS_AT,
            "rhythm": rhythm,
            "mark": mark,
            "pleine": day.earn_settled >= mark,
        },
        "week": {
            "week_id": week_id,
            "settled": week.settled,
            "journees_pleines": pleines,
            "journees_pleines_goal": 5,
            "days": [
                {
                    "local_date": local.isoformat(),
                    "settled": days[local].settled,
                    "pleine": days[local].earn_settled >= mark,
                }
                for local in week_days
            ],
        },
        "entries": [_entry(row, subjects) for row in reversed(todays)],
    }


def build_gold_ledger(db: Session, *, user: Any, week: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """``GET /api/v1/gold/ledger?week=``: «D'où vient ton or», one week of entries."""

    if not gold_ledger.gold_visible(user):
        return {"visible": False}
    now = _aware(now) or datetime.now(UTC)
    week_id = week or core.week_id(now)
    if week_bounds(week_id) is None:
        raise ValueError(f"not an ISO week: {week_id!r}")
    rows = (
        db.query(GoldLedgerEntry)
        .filter(GoldLedgerEntry.user_id == user.id, GoldLedgerEntry.week_id == week_id)
        .order_by(GoldLedgerEntry.created_at.desc())
        .limit(500)
        .all()
    )
    mark = core.JOURNEE_PLEINE_MARK[_rhythm(user)]
    days: dict[date, _DayTotals] = defaultdict(_DayTotals)
    total = _DayTotals()
    for row in rows:
        days[row.local_date].add(row)
        total.add(row)
    subjects = _subjects(db, rows)
    return {
        "visible": True,
        "week_id": week_id,
        "settled": total.settled,
        "pending": total.pending,
        "mark": mark,
        "days": [
            {
                "local_date": local.isoformat(),
                "settled": totals.settled,
                "pending": totals.pending,
                "pleine": totals.earn_settled >= mark,
            }
            for local, totals in sorted(days.items(), reverse=True)
        ],
        "entries": [_entry(row, subjects) for row in rows],
    }


__all__ = ["WEEK_PATTERN", "build_gold_ledger", "build_gold_view", "week_bounds"]
