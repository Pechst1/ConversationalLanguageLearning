"""Package O-1 — the nightly gold report: shadow numbers against the plan's targets.

``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §18 lists what the nightly loop reads,
and §5 the Monte Carlo medians the shadow data has to confirm or replace:

* gold a day by rhythm (median, quartiles) next to §5's weak / average /
  strong medians;
* the share of gold from production (target ≥ 60 %) and from delayed recall;
* plafond hits (target: fewer than 10 % of days) and capped days;
* journées pleines a week (§4.4 marks) and learner-weeks with five of them;
* rushing signals the ledger can see: recognition-only days;
* the ledger's own health: pending entries still waiting for a relecture,
  pulped entries by reason, milestones by kind.

Pure reads; nothing here writes. The nightly task stores the result as a
``gold_shadow_report`` pilot event, and ``GET /analytics/pilot-gold`` returns it
live for the owner.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import mean, median
from typing import Any

from sqlalchemy.orm import Session

from app.core import gold as core
from app.db.models.gold import GoldLedgerEntry
from app.db.models.user import User

#: How long a pending entry may wait for its relecture before the report names it.
STALE_PENDING_AFTER = timedelta(hours=1)
PRODUCTION = {str(category) for category in core.PRODUCTION_CATEGORIES}


@dataclass
class _Day:
    user_id: str
    local_date: date
    week_id: str
    rhythm: str
    earn_settled: int = 0
    pending: int = 0
    milestones: int = 0
    bonus: int = 0
    earned_before_plafond: int = 0
    production: int = 0
    delayed: int = 0
    categories: Counter = field(default_factory=Counter)

    @property
    def settled_total(self) -> int:
        return self.earn_settled + self.milestones + self.bonus

    @property
    def mark(self) -> int:
        return core.JOURNEE_PLEINE_MARK.get(self.rhythm, core.JOURNEE_PLEINE_MARK["regulier"])

    @property
    def pleine(self) -> bool:
        return self.earn_settled >= self.mark


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _quantile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 1)


def _share(part: float, whole: float) -> float | None:
    return round(part / whole, 3) if whole else None


def _delayed(breakdown: dict[str, Any]) -> bool:
    return any(str(factor.get("name")) == "rappel_differe" for factor in breakdown.get("factors") or [])


def _rhythms(db: Session, user_ids: Iterable[Any]) -> dict[str, str]:
    from app.services.journey_rhythm import rhythm_for_minutes

    ids = list(set(user_ids))
    if not ids:
        return {}
    rows = db.query(User.id, User.daily_goal_minutes).filter(User.id.in_(ids)).all()
    return {str(user_id): str(rhythm_for_minutes(minutes)) for user_id, minutes in rows}


def build_gold_report(db: Session, *, days: int = 14, now: datetime | None = None) -> dict[str, Any]:
    """§18 over the last ``days`` local days, every learner with a ledger entry."""

    now = _aware(now) or datetime.now(UTC)
    days = max(1, min(int(days), 120))
    since = now.date() - timedelta(days=days)
    entries = db.query(GoldLedgerEntry).filter(GoldLedgerEntry.local_date > since).all()
    rhythms = _rhythms(db, (entry.user_id for entry in entries))

    by_day: dict[tuple[str, date], _Day] = {}
    categories_amount: Counter = Counter()
    categories_count: Counter = Counter()
    sources_amount: Counter = Counter()
    voids: Counter = Counter()
    milestones_count: Counter = Counter()
    milestones_amount: Counter = Counter()
    stale_pending = 0
    oldest_pending: datetime | None = None
    withdrawn = critic = 0

    for entry in entries:
        user_id = str(entry.user_id)
        day = by_day.setdefault(
            (user_id, entry.local_date),
            _Day(user_id=user_id, local_date=entry.local_date, week_id=entry.week_id,
                 rhythm=rhythms.get(user_id, "regulier")),
        )
        breakdown = dict(entry.breakdown or {})
        evidence = dict(entry.evidence or {})
        if evidence.get("withdrawn"):
            withdrawn += 1
        if evidence.get("critic"):
            critic += 1
        if entry.state == core.STATE_VOID:
            voids[str(entry.void_reason or "unknown")] += 1
            continue
        amount = int(entry.amount or 0)
        if entry.state == core.STATE_PENDING:
            day.pending += amount
            created = _aware(entry.created_at)
            if created is not None and now - created > STALE_PENDING_AFTER:
                stale_pending += 1
                oldest_pending = created if oldest_pending is None else min(oldest_pending, created)
        if entry.entry_kind == "earn":
            category = str(breakdown.get("category") or evidence.get("category") or "unknown")
            day.categories[category] += 1
            day.earned_before_plafond += int(breakdown.get("earned") or 0)
            categories_amount[category] += amount
            categories_count[category] += 1
            sources_amount[str(entry.source_kind)] += amount
            if category in PRODUCTION:
                day.production += amount
            if _delayed(breakdown):
                day.delayed += amount
            if entry.state == core.STATE_SETTLED:
                day.earn_settled += amount
        elif entry.state == core.STATE_SETTLED:
            if entry.entry_kind == "milestone":
                kind = str(breakdown.get("milestone") or evidence.get("milestone") or "unknown")
                milestones_count[kind] += 1
                milestones_amount[kind] += amount
                day.milestones += amount
            elif entry.entry_kind == "bonus":
                day.bonus += amount
                sources_amount["bonus"] += amount

    all_days = list(by_day.values())
    earn_total = sum(day.earn_settled + day.pending for day in all_days)
    production_total = sum(day.production for day in all_days)
    delayed_total = sum(day.delayed for day in all_days)
    touched = [day for day in all_days if day.earned_before_plafond > core.PLAFOND_FULL_RATE_UP_TO]
    capped = [day for day in all_days if day.earned_before_plafond >= core.PLAFOND_STOPS_AT]
    recognition_only = [
        day for day in all_days
        if day.categories and set(day.categories) <= {str(core.Category.RECOGNISED)}
    ]

    by_rhythm: dict[str, Any] = {}
    grouped: dict[str, list[_Day]] = defaultdict(list)
    for day in all_days:
        grouped[day.rhythm].append(day)
    for rhythm in core.JOURNEE_PLEINE_MARK:
        rows = grouped.get(rhythm, [])
        values = [day.earn_settled for day in rows]
        targets = core.CALIBRATION_TARGETS[rhythm]
        med = median(values) if values else None
        by_rhythm[rhythm] = {
            "learners": len({day.user_id for day in rows}),
            "days": len(rows),
            "median": med,
            "p25": _quantile(values, 0.25),
            "p75": _quantile(values, 0.75),
            "mean": round(mean(values), 1) if values else None,
            "targets": targets,
            "median_vs_average_target": round(med / targets["average"], 2) if med is not None else None,
            "journee_pleine_mark": core.JOURNEE_PLEINE_MARK[rhythm],
            "journee_pleine_share": _share(sum(1 for day in rows if day.pleine), len(rows)),
        }

    weeks: dict[tuple[str, str], int] = defaultdict(int)
    for day in all_days:
        weeks[(day.user_id, day.week_id)] += 1 if day.pleine else 0
    pleines = list(weeks.values())

    learners: list[dict[str, Any]] = []
    per_user: dict[str, list[_Day]] = defaultdict(list)
    for day in all_days:
        per_user[day.user_id].append(day)
    for user_id, rows in sorted(per_user.items()):
        values = [day.earn_settled for day in rows]
        learners.append({
            "user_id": user_id,
            "rhythm": rows[0].rhythm,
            "days": len(rows),
            "median": median(values),
            "total_settled": sum(day.settled_total for day in rows),
            "journees_pleines": sum(1 for day in rows if day.pleine),
            "production_share": _share(sum(day.production for day in rows),
                                       sum(day.earn_settled + day.pending for day in rows)),
        })

    production_share = _share(production_total, earn_total)
    touched_share = _share(len(touched), len(all_days))
    checks = [
        {
            "metric": "production_share",
            "value": production_share,
            "target": f">= {core.PRODUCTION_SHARE_TARGET}",
            "ok": None if production_share is None else production_share >= core.PRODUCTION_SHARE_TARGET,
        },
        {
            "metric": "plafond_day_share",
            "value": touched_share,
            "target": f"< {core.PLAFOND_DAY_SHARE_TARGET}",
            "ok": None if touched_share is None else touched_share < core.PLAFOND_DAY_SHARE_TARGET,
        },
        {
            "metric": "stale_pending",
            "value": stale_pending,
            "target": "0",
            "ok": stale_pending == 0,
        },
    ]
    return {
        "report": "gold_shadow",
        "rule_version": core.RULE_VERSION,
        "generated_at": now.isoformat(),
        "window_days": days,
        "since": (since + timedelta(days=1)).isoformat(),
        "entries": len(entries),
        "learners": len(per_user),
        "learner_days": len(all_days),
        "gold_by_rhythm": by_rhythm,
        "production_share": production_share,
        "delayed_recall_share": _share(delayed_total, earn_total),
        "plafond": {
            "touched_day_share": touched_share,
            "capped_day_share": _share(len(capped), len(all_days)),
            "touched_days": len(touched),
            "capped_days": len(capped),
        },
        "journees_pleines": {
            "learner_weeks": len(pleines),
            "mean_per_week": round(mean(pleines), 2) if pleines else None,
            "weeks_with_five": sum(1 for value in pleines if value >= 5),
        },
        "recognition_only_day_share": _share(len(recognition_only), len(all_days)),
        "by_category": {
            category: {"entries": categories_count[category], "gold": categories_amount[category]}
            for category in sorted(categories_count)
        },
        "by_source": dict(sorted(sources_amount.items())),
        "milestones": {
            kind: {"count": milestones_count[kind], "gold": milestones_amount[kind]}
            for kind in sorted(milestones_count)
        },
        "ledger_health": {
            "void_by_reason": dict(sorted(voids.items())),
            "stale_pending": stale_pending,
            "oldest_pending_at": oldest_pending.isoformat() if oldest_pending else None,
            "settled_but_withdrawn": withdrawn,
            "critic_corrected": critic,
        },
        "checks": checks,
        "learners_detail": learners,
    }


def report_markdown(report: dict[str, Any]) -> str:
    """The report as a short page for the owner (the script prints it)."""

    lines = [
        f"# L'or en shadow — {report['generated_at'][:10]} ({report['window_days']} jours)",
        "",
        f"{report['learners']} learners, {report['learner_days']} learner-days, "
        f"{report['entries']} entries ({report['rule_version']}).",
        "",
        "| Rhythm | learners | days | median | p25–p75 | §5 weak / avg / strong | pleine |",
        "|---|---|---|---|---|---|---|",
    ]
    for rhythm, row in report["gold_by_rhythm"].items():
        targets = row["targets"]
        spread = f"{row['p25']}–{row['p75']}" if row["p25"] is not None else "—"
        pleine = row["journee_pleine_share"]
        lines.append(
            f"| {rhythm} | {row['learners']} | {row['days']} | {row['median'] if row['median'] is not None else '—'} "
            f"| {spread} | {targets['weak']} / {targets['average']} / {targets['strong']} "
            f"| {'—' if pleine is None else f'{pleine:.0%}'} |"
        )
    lines += ["", "| Check | value | target | ok |", "|---|---|---|---|"]
    for check in report["checks"]:
        ok = check["ok"]
        lines.append(f"| {check['metric']} | {check['value']} | {check['target']} | {'—' if ok is None else ('✓' if ok else '✗')} |")
    lines += [
        "",
        f"Delayed recall share: {report['delayed_recall_share']} · "
        f"recognition-only days: {report['recognition_only_day_share']} · "
        f"capped days: {report['plafond']['capped_day_share']}",
        f"Milestones: {report['milestones'] or '—'}",
        f"Ledger health: {report['ledger_health']}",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["STALE_PENDING_AFTER", "build_gold_report", "report_markdown"]
