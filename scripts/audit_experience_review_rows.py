"""WP-123b — which stored rows did the defects of 2026-10-03/04 leave behind?

Three defects fixed by the experience review (2026-10-04) and its packages wrote
rows that the fixed code would never write. This script finds them **by
provenance** — never by guesswork — and says what a repair would touch:

1. ``band_check_flood`` — review fix 13 / WP-127. The vocabulary check's credited
   cards (``provenance`` ``band_check`` / ``band_check_inferred``) were all given a
   light check 10–45 days out with stability 30, so a B2 learner's ~2,800 credits
   came back at ~80 a day. The fixed schedule (``band_check.credit_schedule``)
   never writes stability 30 (its floor is 60). **Proof:** check provenance,
   stability exactly 30, ``reps`` 2, ``lapses`` 0 and no review log — the card is
   still exactly as the old credit wrote it. **Repair:** the current schedule for
   the sub-band's distance below the learner's band (seeded as ``credit()`` seeds
   it), never earlier than the stored due date.
2. ``letter_omission_errata`` — WP-125A. A suggested word left unused in a
   Courrier letter opened a «vocabulary_missing_target» erratum. **Proof:**
   ``task_error_type`` ``vocabulary_missing_target``, ``source_type`` ``mission``,
   one occurrence (nothing else ever merged into the row), not yet mastered.
   **Repair:** the erratum is removed (backed up first).
3. ``letter_omission_lapses`` — WP-125A. The same omission charged the word's
   card a lapse (a ``mission`` review log rated 0). **Proof:** the learner's
   mission payloads hold a ``missed_target`` event for the word and no
   ``produced_incorrect`` one. **Report only:** the card's stability before the
   lapse is not stored, so it cannot be restored exactly; most such cards have
   been reviewed since. The count says whether the owner needs to decide more.
4. ``practice_miss_vocab_errata`` — review fix 7. A missed *practice item* (a
   tapped card, a tile order) opened a vocabulary erratum. **Proof:**
   ``source_type`` ``daily_journey``, a vocabulary erratum type, one occurrence,
   and the recorded ``task_type`` is a practice format (not ``reply``). Rows
   with no recorded ``task_type`` are not provable and are left alone.
5. ``give_up_correction_errata`` — review fix 7. «je ne sais pas» on a practice
   item came back as «Schreib richtig, was du gesagt hast: …». **Proof:**
   ``task_error_type`` ``journey_correction``, ``source_type`` ``daily_journey``,
   one occurrence, the stored learner text is a give-up
   (``journey_learning.attempted_answer``) and its ``source_key`` names a journey
   step that is a practice item (not a reply). **Repair:** removed (backed up).

Legitimate errors (wrong use, a reply's own French), independent reviews (any
review log on a credited card), imported cards (any other provenance) and every
ambiguous row (merged occurrences, mastered, unprovable) are **never** touched;
the report counts them as «left alone» with the reason.

**Read-only by default.** Without ``--apply`` the script opens one transaction,
marks it read-only (PostgreSQL ``SET TRANSACTION READ ONLY``; SQLite
``PRAGMA query_only``), reads, prints, and rolls back: it cannot write.

    DATABASE_URL=postgresql://… python -m scripts.audit_experience_review_rows
    python -m scripts.audit_experience_review_rows --database-url … --json report.json

``--apply --backup <file.jsonl>`` re-runs the audit inside one write
transaction, writes every row it will change (its full prior state) to the backup
file first, then repairs categories 1, 2, 4 and 5 and commits. A second run finds
nothing more (idempotent). Run the dry run first and read it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("SECRET_KEY", "audit-experience-review-rows")

from sqlalchemy import MetaData, Table, and_, create_engine, delete, select, update  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

#: The old credit's signature: every pre-fix credited card had exactly this stability.
OLD_CREDIT_STABILITY = 30.0
CHECK_PROVENANCES = ("band_check", "band_check_inferred")
VOCAB_ERRATUM_TYPES = ("vocabulary_missing_target", "vocabulary_incorrect_use")
MISSING_EVENTS = {"missed_target", "missing_target", "avoided_target"}
WRONG_EVENTS = {"produced_incorrect", "used_incorrectly", "incorrect", "incorrect_production"}
#: Journey step kinds whose answer is the learner's own French (a reply).
REPLY_STEP_KINDS = {"respond"}
_SOURCE_KEY = re.compile(r"^journey:(?P<journey>[0-9a-fA-F-]{32,36}):(?P<step>[0-9a-fA-F-]{32,36}):")

CATEGORIES = (
    "band_check_flood",
    "letter_omission_errata",
    "letter_omission_lapses",
    "practice_miss_vocab_errata",
    "give_up_correction_errata",
)
REPAIRABLE = {"band_check_flood": "reschedule", "letter_omission_errata": "delete",
              "practice_miss_vocab_errata": "delete", "give_up_correction_errata": "delete"}


@dataclass
class Finding:
    category: str
    table: str
    row_id: str
    user_id: str
    action: str  # reschedule | delete | report
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CategoryReport:
    category: str
    applicable: bool
    reason: str = ""
    affected: list[Finding] = field(default_factory=list)
    left_alone: Counter = field(default_factory=Counter)

    def summary(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "applicable": self.applicable,
            "reason": self.reason,
            "affected": len(self.affected),
            "users": len({f.user_id for f in self.affected}),
            "action": REPAIRABLE.get(self.category, "report"),
            "left_alone": dict(self.left_alone),
        }


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _tables(conn: Connection, names: tuple[str, ...]) -> dict[str, Table] | None:
    from sqlalchemy import inspect

    have = set(inspect(conn).get_table_names())
    if not set(names) <= have:
        return None
    meta = MetaData()
    return {name: Table(name, meta, autoload_with=conn, resolve_fks=False) for name in names}


def _has(table: Table, *columns: str) -> bool:
    return all(column in table.c for column in columns)


def _json(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _aware(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _sub_band_index(level: Any) -> int:
    from app.services.band_check import SUB_BANDS, _sub_band

    return SUB_BANDS.index(_sub_band(str(level or "")))


def audit_band_check_flood(conn: Connection) -> CategoryReport:
    from app.services.band_check import SUB_BANDS, credit_schedule

    report = CategoryReport("band_check_flood", applicable=True)
    tables = _tables(conn, ("user_vocabulary_progress", "review_logs", "users"))
    if tables is None or not _has(tables["user_vocabulary_progress"], "provenance", "provenance_ref"):
        report.applicable, report.reason = False, "no provenance column: the vocabulary check was never deployed here"
        return report
    progress, logs, users = tables["user_vocabulary_progress"], tables["review_logs"], tables["users"]
    reviewed = {str(pid) for pid in conn.execute(select(logs.c.progress_id).distinct()).scalars()}
    level_of = {
        str(row.id): row.cefr_estimate or row.proficiency_level
        for row in conn.execute(select(users.c.id, users.c.cefr_estimate, users.c.proficiency_level))
    }
    rows = conn.execute(select(progress).where(progress.c.provenance.in_(CHECK_PROVENANCES))).mappings().all()
    for row in rows:
        if abs(float(row["stability"] or 0.0) - OLD_CREDIT_STABILITY) > 1e-6:
            report.left_alone["current schedule (stability is not the old credit's 30)"] += 1
            continue
        if str(row["id"]) in reviewed:
            report.left_alone["reviewed since the credit (an independent review)"] += 1
            continue
        if int(row["reps"] or 0) != 2 or int(row["lapses"] or 0) != 0:
            report.left_alone["changed since the credit (reps/lapses)"] += 1
            continue
        credited_at = _aware(row["last_review_date"])
        sub_band = str(row["provenance_ref"] or "")
        if credited_at is None or sub_band not in SUB_BANDS:
            report.left_alone["no credit date or sub-band on record"] += 1
            continue
        learner = _sub_band_index(level_of.get(str(row["user_id"])))
        distance = max(1, learner - SUB_BANDS.index(sub_band))
        stability, window = credit_schedule(distance)
        seeded = random.Random(f"{row['user_id']}:{row['word_id']}")  # noqa: S311 - credit()'s own seed
        recomputed = credited_at + dt.timedelta(days=seeded.randint(*window))
        stored = _aware(row["due_at"]) or _aware(row["next_review_date"]) or credited_at
        due = max(stored, recomputed)  # a repair never pulls a review forward
        report.affected.append(
            Finding(
                "band_check_flood", "user_vocabulary_progress", str(row["id"]), str(row["user_id"]), "reschedule",
                {
                    "word_id": row["word_id"], "provenance": row["provenance"], "sub_band": sub_band,
                    "distance": distance, "due_before": stored.isoformat(), "due_after": due.isoformat(),
                    "stability_after": max(OLD_CREDIT_STABILITY, stability),
                    "days_after": (due - credited_at).days,
                },
            )
        )
    return report


def _errata(conn: Connection) -> Table | None:
    tables = _tables(conn, ("user_errors",))
    return None if tables is None else tables["user_errors"]


def _open(row: Any) -> bool:
    return str(row["state"] or "").strip().lower() != "mastered"


def audit_letter_omission_errata(conn: Connection) -> CategoryReport:
    report = CategoryReport("letter_omission_errata", applicable=True)
    errata = _errata(conn)
    if errata is None or not _has(errata, "task_error_type", "source_type"):
        report.applicable, report.reason = False, "no user_errors.task_error_type column"
        return report
    rows = conn.execute(
        select(errata).where(errata.c.task_error_type == "vocabulary_missing_target")
    ).mappings().all()
    for row in rows:
        if row["source_type"] != "mission":
            report.left_alone[f"source {row['source_type']!r}, not a letter"] += 1
        elif int(row["occurrences"] or 1) != 1:
            report.left_alone["merged with other occurrences (ambiguous)"] += 1
        elif not _open(row):
            report.left_alone["already mastered (out of the queue)"] += 1
        else:
            report.affected.append(
                Finding("letter_omission_errata", "user_errors", str(row["id"]), str(row["user_id"]), "delete",
                        {"linked_word_id": row["linked_word_id"], "display_label": row["display_label"],
                         "created_at": str(row["created_at"])})
            )
    return report


def _mission_word_events(conn: Connection) -> dict[tuple[str, int], set[str]]:
    """``(user_id, word_id) → {"missed", "wrong"}`` from every mission turn and attempt."""

    found: dict[tuple[str, int], set[str]] = {}
    for name in ("real_world_mission_turns", "real_world_mission_attempts"):
        tables = _tables(conn, (name,))
        if tables is None or not _has(tables[name], "correction_payload", "user_id"):
            continue
        table = tables[name]
        for user_id, payload in conn.execute(select(table.c.user_id, table.c.correction_payload)):
            for event in (_json(payload) or {}).get("vocabulary_events") or []:
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("event_type") or "")
                mark = "missed" if kind in MISSING_EVENTS else "wrong" if kind in WRONG_EVENTS else None
                try:
                    word_id = int(event.get("word_id"))
                except (TypeError, ValueError):
                    continue
                if mark:
                    found.setdefault((str(user_id), word_id), set()).add(mark)
    return found


def audit_letter_omission_lapses(conn: Connection) -> CategoryReport:
    report = CategoryReport("letter_omission_lapses", applicable=True)
    tables = _tables(conn, ("review_logs", "user_vocabulary_progress"))
    if tables is None or not _has(tables["review_logs"], "source"):
        report.applicable, report.reason = False, "no review_logs.source column"
        return report
    logs, progress = tables["review_logs"], tables["user_vocabulary_progress"]
    events = _mission_word_events(conn)
    latest = {
        str(pid): stamp
        for pid, stamp in conn.execute(select(logs.c.progress_id, logs.c.review_date).order_by(logs.c.review_date))
    }
    rows = conn.execute(
        select(logs.c.id, logs.c.progress_id, logs.c.review_date, progress.c.user_id, progress.c.word_id)
        .join(progress, progress.c.id == logs.c.progress_id)
        .where(and_(logs.c.source == "mission", logs.c.rating == 0))
    ).mappings().all()
    for row in rows:
        marks = events.get((str(row["user_id"]), int(row["word_id"])), set())
        if "missed" not in marks:
            report.left_alone["no omission event for the word"] += 1
        elif "wrong" in marks:
            report.left_alone["the word was also used wrongly (a real lapse is possible)"] += 1
        else:
            report.affected.append(
                Finding("letter_omission_lapses", "review_logs", str(row["id"]), str(row["user_id"]), "report",
                        {"word_id": row["word_id"], "review_date": str(row["review_date"]),
                         "still_latest_review": str(latest.get(str(row["progress_id"]))) == str(row["review_date"])})
            )
    return report


def _payload(row: Any) -> dict[str, Any]:
    metadata = _json(row["error_metadata"]) or {}
    payload = metadata.get("source_payload") if isinstance(metadata, dict) else None
    return payload if isinstance(payload, dict) else {}


def audit_practice_miss_vocab_errata(conn: Connection) -> CategoryReport:
    report = CategoryReport("practice_miss_vocab_errata", applicable=True)
    errata = _errata(conn)
    if errata is None or not _has(errata, "task_error_type", "source_type", "error_metadata"):
        report.applicable, report.reason = False, "no user_errors metadata columns"
        return report
    rows = conn.execute(
        select(errata).where(and_(errata.c.source_type == "daily_journey", errata.c.task_error_type.in_(VOCAB_ERRATUM_TYPES)))
    ).mappings().all()
    for row in rows:
        task_type = str(_payload(row).get("task_type") or "")
        if not task_type:
            report.left_alone["no task_type recorded (not provable)"] += 1
        elif task_type == "reply":
            report.left_alone["a reply's own French (legitimate)"] += 1
        elif int(row["occurrences"] or 1) != 1:
            report.left_alone["merged with other occurrences (ambiguous)"] += 1
        elif not _open(row):
            report.left_alone["already mastered (out of the queue)"] += 1
        else:
            report.affected.append(
                Finding("practice_miss_vocab_errata", "user_errors", str(row["id"]), str(row["user_id"]), "delete",
                        {"task_type": task_type, "linked_word_id": row["linked_word_id"],
                         "learner_text": row["original_text"]})
            )
    return report


def audit_give_up_correction_errata(conn: Connection) -> CategoryReport:
    from app.services.journey_learning import attempted_answer

    report = CategoryReport("give_up_correction_errata", applicable=True)
    errata = _errata(conn)
    steps_tables = _tables(conn, ("daily_journey_steps",))
    if errata is None or steps_tables is None or not _has(errata, "task_error_type", "error_metadata"):
        report.applicable, report.reason = False, "no user_errors metadata or journey steps"
        return report
    steps = steps_tables["daily_journey_steps"]
    rows = conn.execute(
        select(errata).where(and_(errata.c.source_type == "daily_journey", errata.c.task_error_type == "journey_correction"))
    ).mappings().all()
    for row in rows:
        if attempted_answer(row["original_text"], row["correction"]):
            report.left_alone["an attempt at the answer (legitimate)"] += 1
            continue
        if int(row["occurrences"] or 1) != 1:
            report.left_alone["merged with other occurrences (ambiguous)"] += 1
            continue
        if not _open(row):
            report.left_alone["already mastered (out of the queue)"] += 1
            continue
        match = _SOURCE_KEY.match(str(_payload(row).get("source_key") or ""))
        kind = None
        if match:
            step_id = match.group("step")
            kind = conn.execute(
                select(steps.c.kind).where(steps.c.id.in_([step_id, step_id.replace("-", "")]))
            ).scalar()
        if kind is None:
            report.left_alone["the journey step is not on record (not provable)"] += 1
        elif kind in REPLY_STEP_KINDS:
            report.left_alone["a give-up in a reply (the current policy keeps it)"] += 1
        else:
            report.affected.append(
                Finding("give_up_correction_errata", "user_errors", str(row["id"]), str(row["user_id"]), "delete",
                        {"step_kind": kind, "learner_text": row["original_text"], "display_label": row["display_label"]})
            )
    return report


AUDITS = {
    "band_check_flood": audit_band_check_flood,
    "letter_omission_errata": audit_letter_omission_errata,
    "letter_omission_lapses": audit_letter_omission_lapses,
    "practice_miss_vocab_errata": audit_practice_miss_vocab_errata,
    "give_up_correction_errata": audit_give_up_correction_errata,
}


def audit(conn: Connection) -> list[CategoryReport]:
    """Every category, read only."""

    return [AUDITS[name](conn) for name in CATEGORIES]


# ---------------------------------------------------------------------------
# Repairing (only with --apply)
# ---------------------------------------------------------------------------


def _row_snapshot(conn: Connection, table: Table, row_id: str) -> dict[str, Any] | None:
    row = conn.execute(select(table).where(table.c.id == _id_value(table, row_id))).mappings().first()
    if row is None:
        return None
    return {key: (value.isoformat() if isinstance(value, (dt.datetime, dt.date)) else
                  str(value) if not isinstance(value, (int, float, str, bool, dict, list, type(None))) else value)
            for key, value in row.items()}


def _id_value(table: Table, row_id: str) -> Any:
    import uuid

    python_type = None
    try:
        python_type = table.c.id.type.python_type
    except NotImplementedError:
        python_type = None
    if python_type is uuid.UUID:
        return uuid.UUID(row_id)
    return row_id


def repair(conn: Connection, reports: list[CategoryReport], *, backup: Path) -> dict[str, int]:
    """Apply the repairable findings inside the caller's transaction. Writes the
    prior state of every row it changes to ``backup`` (JSON lines) first."""

    tables = {name: Table(name, MetaData(), autoload_with=conn, resolve_fks=False) for name in ("user_vocabulary_progress", "user_errors")
              if _tables(conn, (name,)) is not None}
    findings = [f for report in reports for f in report.affected if f.action in ("reschedule", "delete")]
    with backup.open("a", encoding="utf-8") as out:
        for finding in findings:
            snapshot = _row_snapshot(conn, tables[finding.table], finding.row_id)
            out.write(json.dumps({"category": finding.category, "table": finding.table, "action": finding.action,
                                  "row": snapshot}, ensure_ascii=False, default=str) + "\n")
    done: Counter = Counter()
    for finding in findings:
        table = tables[finding.table]
        key = table.c.id == _id_value(table, finding.row_id)
        if finding.action == "delete":
            done[finding.category] += conn.execute(delete(table).where(key)).rowcount or 0
            continue
        due = _aware(finding.detail["due_after"])
        values = {
            "stability": float(finding.detail["stability_after"]),
            "scheduled_days": int(finding.detail["days_after"]),
            "interval_days": int(finding.detail["days_after"]),
            "next_review_date": due,
            "due_at": due,
            "due_date": due.date(),
        }
        # The same proof as the audit, re-checked in the statement itself.
        guard = and_(key, table.c.stability == OLD_CREDIT_STABILITY, table.c.reps == 2, table.c.lapses == 0,
                     table.c.provenance.in_(CHECK_PROVENANCES))
        done[finding.category] += conn.execute(update(table).where(guard).values(**values)).rowcount or 0
    return dict(done)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _read_only(conn: Connection) -> None:
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
    elif conn.dialect.name == "sqlite":
        conn.exec_driver_sql("PRAGMA query_only = ON")


def _writable(conn: Connection) -> None:
    if conn.dialect.name == "sqlite":
        conn.exec_driver_sql("PRAGMA query_only = OFF")


def render(reports: list[CategoryReport], *, examples: int = 3) -> str:
    lines = ["| Category | Applicable | Affected rows | Learners | Repair | Left alone |", "|---|---|---:|---:|---|---|"]
    for report in reports:
        s = report.summary()
        alone = "; ".join(f"{reason}: {count}" for reason, count in s["left_alone"].items()) or "—"
        lines.append(f"| {s['category']} | {'yes' if s['applicable'] else 'no — ' + s['reason']} | {s['affected']} "
                     f"| {s['users']} | {s['action']} | {alone} |")
    for report in reports:
        for finding in report.affected[:examples]:
            lines.append(f"- {finding.category} {finding.table}:{finding.row_id} → {finding.action} {finding.detail}")
    return "\n".join(lines)


def run(database_url: str, *, apply: bool = False, backup: Path | None = None) -> tuple[list[CategoryReport], dict[str, int]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            if not apply:
                with conn.begin() as tx:
                    _read_only(conn)
                    reports = audit(conn)
                    tx.rollback()
                if conn.dialect.name == "sqlite":
                    _writable(conn)
                return reports, {}
            if backup is None:
                raise SystemExit("--apply needs --backup <file.jsonl>: every changed row is saved there first")
            with conn.begin():
                _writable(conn)
                reports = audit(conn)
                done = repair(conn, reports, backup=backup)
            return reports, done
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit (and, with --apply, repair) the rows of 2026-10-03/04.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--apply", action="store_true", help="repair the provenance-proven rows (default: read only)")
    parser.add_argument("--backup", type=Path, help="JSON-lines file for the prior state of every changed row")
    parser.add_argument("--json", type=Path, help="write the full report here")
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url (or DATABASE_URL) is required")
    reports, done = run(args.database_url, apply=args.apply, backup=args.backup)
    print(("APPLIED — " if args.apply else "DRY RUN (read only, nothing written) — ") + dt.datetime.now(dt.UTC).isoformat())
    print(render(reports, examples=args.examples))
    if args.apply:
        print(f"repaired: {done}")
    if args.json:
        args.json.write_text(json.dumps(
            {"summary": [r.summary() for r in reports],
             "findings": [asdict(f) for r in reports for f in r.affected], "repaired": done},
            ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
