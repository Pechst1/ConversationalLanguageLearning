"""Package V stage 2: the verdict ledger. A verdict is a stored fact, not a re-reading.

**Writing.** Every time a stored answer the level, l'or or a token reads is written or
changed (a Forge attempt, a Courrier attempt or message, a Feuilleton attempt, a Journal
entry), :func:`record_flush` judges it once (:func:`app.services.judge.judge`) and appends
a :class:`VerdictRecord`. It runs from the session's ``before_flush`` event
(:mod:`app.db.verdict_listener`), so no write path can skip it, now or later. A record
whose verdict is the one already live (the same judge, the same result) is not written
again; a different one supersedes it.

**Reading.** :class:`Counting` answers «does this row count?» for the four reads that
decide a level, gold and a token:

1. a row stored before the verdict stack (stage 1's cut-over) keeps what it counted for;
2. a row with a live record counts as its record says, whatever today's judge would say;
3. a row stored after the ledger cut-over with no record is judged once more and logged
   (``verdict_ledger_missing``): it should not exist, and the log says where;
4. a row from between the two cut-overs is judged on read, as stage 1 did.

**Paying.** :func:`supersede` takes a ``payer``: the gold a record is due is minted once
per chain under a key the ledger names; a later record that no longer counts voids it,
and one that counts again mints under the next key. Superseding twice pays once.
"""

from __future__ import annotations

import uuid
import weakref
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified, get_history

from app.config import settings
from app.core.verdict import Verdict
from app.db.models.verdict_record import VerdictRecord
from app.services import verdict_cutover, verdicts
from app.services.judge import Reading, Task, judge, judge_version

__all__ = [
    "SUBJECTS",
    "Counting",
    "counting",
    "live_record",
    "pay",
    "record_flush",
    "recording",
    "supersede",
]


def _text(payload: Any, *keys: str) -> str:
    values = payload if isinstance(payload, dict) else {}
    for key in keys:
        if values.get(key):
            return str(values[key])
    return ""


@dataclass(frozen=True)
class Subject:
    """One kind of stored answer the ledger keeps: how to read it, and what change re-judges it."""

    subject_type: str
    surface: str
    fields: tuple[str, ...]
    read: Callable[[Any], verdicts.Read | None]


def _forge(row: Any) -> verdicts.Read | None:
    if not row.correction_payload:
        return None
    text = _text(row.answer_payload, "answer", "text", "answer_text")
    return verdicts.read_forge(row.correction_payload, text=text, verdict=row.verdict)


def _courrier_attempt(row: Any) -> verdicts.Read | None:
    if not row.correction_payload:
        return None
    return verdicts.read_courrier(row.correction_payload, verdict=row.verdict, text=_text(row.answer_payload, "text"))


def _courrier_turn(row: Any) -> verdicts.Read | None:
    # A message never sent for correction (the correspondent's, an opening) has no verdict.
    if row.role != "user" or not row.correction_payload:
        return None
    return verdicts.read_courrier(row.correction_payload, text=row.text or "")


def _feuilleton(row: Any) -> verdicts.Read | None:
    if not row.correction_payload:
        return None
    text = _text(row.answer_payload, "answer", "text")
    return verdicts.read_feuilleton(row.correction_payload, verdict=row.verdict, text=text)


def _journal(row: Any) -> verdicts.Read | None:
    if not row.correction:
        return None
    return verdicts.read_journal(row.correction, text=row.entry_text or "")


def _subjects() -> dict[type, Subject]:
    from app.db.models.atelier import AtelierAttempt
    from app.db.models.graphic_novel import GraphicNovelAttempt
    from app.db.models.journal import JournalEntry
    from app.db.models.mission import RealWorldMissionAttempt, RealWorldMissionTurn

    return {
        AtelierAttempt: Subject("forge_attempt", "forge", ("correction_payload", "verdict"), _forge),
        RealWorldMissionAttempt: Subject(
            "courrier_attempt", "courrier", ("correction_payload", "verdict"), _courrier_attempt
        ),
        RealWorldMissionTurn: Subject("courrier_turn", "courrier", ("correction_payload", "text"), _courrier_turn),
        GraphicNovelAttempt: Subject("feuilleton_attempt", "feuilleton", ("correction_payload", "verdict"), _feuilleton),
        JournalEntry: Subject("journal_entry", "journal", ("correction", "entry_text"), _journal),
    }


SUBJECTS: dict[type, Subject] = {}


def _subject_of(obj: Any) -> Subject | None:
    if not SUBJECTS:
        SUBJECTS.update(_subjects())
    return SUBJECTS.get(type(obj))


def subject_type_of(model: type) -> str:
    if not SUBJECTS:
        SUBJECTS.update(_subjects())
    return SUBJECTS[model].subject_type


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

_HAS_TABLE: weakref.WeakKeyDictionary[Any, bool] = weakref.WeakKeyDictionary()


def _enabled(session: Session) -> bool:
    if not bool(getattr(settings, "VERDICT_LEDGER_ENABLED", True)):
        return False
    try:
        engine = session.get_bind().engine
    except Exception:  # noqa: BLE001 - an unbound session writes nothing here
        return False
    known = _HAS_TABLE.get(engine)
    if known is None:
        known = inspect(engine).has_table(VerdictRecord.__tablename__)
        _HAS_TABLE[engine] = known
    return known


def _shown(verdict: Verdict) -> dict[str, Any]:
    return verdict.to_dict()


def _pending_live(session: Session) -> dict[tuple[str, str], VerdictRecord]:
    return session.info.setdefault("verdict_ledger_live", {})


def live_record(session: Session, subject_type: str, subject_id: Any) -> VerdictRecord | None:
    """The record nobody superseded for this subject, written or still pending in ``session``."""

    key = (subject_type, str(subject_id))
    pending = _pending_live(session).get(key)
    if pending is not None and pending.superseded_by_id is None:
        return pending
    with session.no_autoflush:
        return session.scalars(
            select(VerdictRecord)
            .where(
                VerdictRecord.subject_type == subject_type,
                VerdictRecord.subject_id == str(subject_id),
                VerdictRecord.superseded_by_id.is_(None),
            )
            .order_by(VerdictRecord.created_at.desc())
            .limit(1)
        ).first()


def _chain_payment(previous: VerdictRecord | None) -> dict[str, Any]:
    paid = dict(previous.paid or {}) if previous is not None else {}
    return {
        "root": paid.get("root") or (str(previous.id) if previous is not None else None),
        "generation": int(paid.get("generation") or 0),
        "gold_key": paid.get("gold_key"),
    }


def _settle_gold(
    session: Session,
    *,
    record: VerdictRecord,
    previous: VerdictRecord | None,
    payer: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """What ``record`` pays or takes back, against what its chain already paid."""

    from app.db.models.gold import GoldLedgerEntry
    from app.services import gold_ledger

    chain = _chain_payment(previous)
    root = chain["root"] or str(record.id)
    paid: dict[str, Any] = {"root": root, "generation": chain["generation"], "level": bool(record.counts), "gold": 0}
    entry = None
    if chain["gold_key"]:
        entry = session.scalars(
            select(GoldLedgerEntry).where(
                GoldLedgerEntry.user_id == record.user_id, GoldLedgerEntry.source_key == chain["gold_key"]
            )
        ).first()
    standing = entry is not None and entry.state != "void"
    if record.counts and standing:
        paid["gold_key"] = chain["gold_key"]  # already paid on this chain: nothing again
    elif record.counts and payer is not None:
        key = f"gold:verdict:{root}:{chain['generation']}"
        minted = payer(key)
        paid["gold_key"] = key
        paid["gold"] = int(getattr(minted, "amount", 0) or 0)
    elif not record.counts and standing:
        gold_ledger.void_verdict_payment(session, entry=entry, reason=f"verdict_superseded:{record.id}")
        paid["gold"] = -int(entry.amount or 0)
        paid["gold_key"] = None
        paid["generation"] = chain["generation"] + 1  # a later payment needs a fresh key
    else:
        paid["gold_key"] = chain["gold_key"] if standing else None
    return paid


def supersede(
    session: Session,
    *,
    user_id: Any,
    surface: str,
    subject_type: str,
    subject_id: Any,
    answer: str,
    reading: Reading,
    task: Task | None = None,
    payer: Callable[[str], Any] | None = None,
    now: datetime | None = None,
) -> VerdictRecord | None:
    """Judge ``answer`` and append its record, superseding the live one when it differs.

    Returns the new record, or ``None`` when the live record already says the same thing.
    ``payer(source_key)`` mints the gold this record is due (see :func:`_settle_gold`).
    """

    verdict = judge(task or Task(surface), answer, reading=reading)
    shown = _shown(verdict)
    version = judge_version()
    previous = live_record(session, subject_type, subject_id)
    if previous is not None and (previous.verdict or {}).get("shown") == shown and previous.judge_version == version:
        return None
    record = VerdictRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        surface=surface,
        subject_type=subject_type,
        subject_id=str(subject_id),
        answer_text=answer or "",
        verdict={"shown": shown, "reading": reading.to_dict()},
        counts=verdict.counts,
        judge_version=version,
        supersedes_id=previous.id if previous is not None else None,
        settled_at=(now or datetime.now(UTC)) if verdict.counts else None,
    )
    if previous is not None:
        previous.superseded_by_id = record.id
        session.add(previous)
    record.paid = _settle_gold(session, record=record, previous=previous, payer=payer)
    session.add(record)
    _pending_live(session)[(subject_type, str(subject_id))] = record
    return record


def recording(session: Session) -> bool:
    """Whether this session's database keeps the ledger."""

    return _enabled(session)


def pay(
    session: Session,
    record: VerdictRecord,
    payer: Callable[[str], Any],
    *,
    key: str | None = None,
) -> Any:
    """Package V stage 3: mint the gold a live, counting ``record`` is due, once per chain.

    ``key`` names the entry (the surface's own key, e.g. ``gold:letter:{mission}``); by
    default the chain's ``gold:verdict:{root}:{generation}``. A chain whose entry stands
    pays nothing again. The record notes the key, so a later record that stops counting
    voids it (:func:`_settle_gold`).
    """

    from app.db.models.gold import GoldLedgerEntry

    if not record.counts:
        return None
    paid = dict(record.paid or {})
    root = paid.get("root") or str(record.id)
    generation = int(paid.get("generation") or 0)
    for candidate in {paid.get("gold_key"), key} - {None}:
        entry = session.scalars(
            select(GoldLedgerEntry).where(
                GoldLedgerEntry.user_id == record.user_id, GoldLedgerEntry.source_key == candidate
            )
        ).first()
        if entry is not None and entry.state != "void":
            if paid.get("gold_key") != candidate:
                record.paid = {**paid, "root": root, "generation": generation, "gold_key": candidate}
                flag_modified(record, "paid")
            return None
    key = key or f"gold:verdict:{root}:{generation}"
    minted = payer(key)
    record.paid = {
        **paid,
        "root": root,
        "generation": generation,
        "gold_key": key,
        "gold": int(paid.get("gold") or 0) + int(getattr(minted, "amount", 0) or 0),
    }
    flag_modified(record, "paid")
    session.add(record)
    return minted


def _changed(obj: Any, fields: Iterable[str]) -> bool:
    return any(get_history(obj, name).has_changes() for name in fields)


def record_flush(session: Session) -> int:
    """``before_flush``: a record for every new or changed answer row in ``session``."""

    if not _enabled(session):
        return 0
    written = 0
    candidates = [(obj, True) for obj in session.new] + [(obj, False) for obj in session.dirty]
    for obj, is_new in candidates:
        subject = _subject_of(obj)
        if subject is None or (not is_new and not _changed(obj, subject.fields)):
            continue
        try:
            read = subject.read(obj)
        except Exception as exc:  # noqa: BLE001 - a ledger line is never worth the learner's answer
            logger.warning("verdict_ledger: could not read {} ({})", subject.subject_type, exc)
            continue
        if read is None:
            continue
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        record = supersede(
            session,
            user_id=getattr(obj, "user_id", None),
            surface=subject.surface,
            subject_type=subject.subject_type,
            subject_id=obj.id,
            answer=read.text,
            reading=read.reading,
        )
        if record is not None:
            written += 1
            from app.services import verdict_settle  # stage 3: an unread answer is checked later

            verdict_settle.note_unread(session, record)
            _note_memo(session, obj, subject, record)
    return written


def _note_memo(session: Session, obj: Any, subject: Subject, record: VerdictRecord) -> None:
    """Stage 4: a record a memo settled is noted on the memo, so a revoke can take it back."""

    if subject.subject_type != "forge_attempt" or not record.counts:
        return
    payload = getattr(obj, "correction_payload", None) or {}
    debug = payload.get("correction_debug") if isinstance(payload, dict) else None
    memo_id = debug.get("memo") if isinstance(debug, dict) else None
    if not memo_id:
        return
    from app.services import answer_memo

    try:
        answer_memo.note_use(
            session,
            memo_id,
            subject_type=subject.subject_type,
            subject_id=obj.id,
            user_id=getattr(obj, "user_id", None),
            gold_key=f"gold:forge:{obj.id}",
        )
    except Exception as exc:  # noqa: BLE001 - a memo note is never worth the learner's answer
        logger.warning("verdict_ledger: could not note memo use ({})", exc)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Counting:
    """«Does this stored answer count?» for a level, l'or or a token. See the module doc."""

    def __init__(
        self,
        legacy: verdict_cutover.Cutover,
        ledger_at: datetime | None,
        live: dict[tuple[str, str], bool],
    ) -> None:
        self.legacy = legacy
        self.ledger_at = _utc(ledger_at)
        self.live = live

    def counts(
        self, row: Any, *, subject_type: str | None = None, read: Callable[[Any], Verdict] | None = None
    ) -> bool:
        """``row``: a stored answer, or a query row with its ``id`` and ``created_at``."""

        if self.legacy.keeps(row):
            return True
        subject = _subject_of(row)
        kind = subject_type or (subject.subject_type if subject is not None else None)
        key = (kind, str(row.id)) if kind is not None and getattr(row, "id", None) is not None else None
        if key is not None and key in self.live:
            return self.live[key]
        verdict = read(row) if read is not None else _judged_row(row, subject)
        created = _utc(getattr(row, "created_at", None))
        if self.ledger_at is not None and created is not None and created >= self.ledger_at:
            logger.warning(
                "verdict_ledger_missing subject={} id={}", kind or "?", getattr(row, "id", None)
            )
        return bool(verdict is not None and verdict.counts)

    def keeps(self, row: Any) -> bool:
        """The stage 1 question, kept for callers that only filter legacy rows."""

        return self.legacy.keeps(row)


def _judged_row(row: Any, subject: Subject | None) -> Verdict | None:
    if subject is None:
        return None
    read = subject.read(row)
    if read is None:
        return None
    return judge(Task(subject.surface), read.text, reading=read.reading)


def _ledger_at(session: Session | None) -> datetime | None:
    if session is None:
        return None
    from app.db.models.verdict_cutover import VerdictCutover

    try:
        with session.begin_nested():
            return session.scalar(select(VerdictCutover.at).where(VerdictCutover.id == 2))
    except Exception:  # noqa: BLE001 - not migrated yet: no ledger cut-over
        return None


def counting(session: Session | None, rows: Iterable[Any] = (), *, subject_type: str | None = None) -> Counting:
    """A :class:`Counting` for ``rows``: their live records are read in one query per kind.

    ``subject_type`` names the kind for query rows that are not mapped objects.
    """

    legacy = verdict_cutover.cutover(session)
    live: dict[tuple[str, str], bool] = {}
    by_type: dict[str, list[str]] = {}
    for row in rows:
        subject = _subject_of(row)
        kind = subject_type or (subject.subject_type if subject is not None else None)
        if kind is not None and getattr(row, "id", None) is not None:
            by_type.setdefault(kind, []).append(str(row.id))
    if session is not None and by_type and _enabled(session):
        for subject_type, ids in by_type.items():
            for start in range(0, len(ids), 500):
                chunk = ids[start : start + 500]
                with session.no_autoflush:
                    found = session.execute(
                        select(VerdictRecord.subject_id, VerdictRecord.counts).where(
                            VerdictRecord.subject_type == subject_type,
                            VerdictRecord.subject_id.in_(chunk),
                            VerdictRecord.superseded_by_id.is_(None),
                        )
                    ).all()
                live.update({(subject_type, subject_id): bool(counts) for subject_id, counts in found})
        for (subject_type, subject_id), record in _pending_live(session).items():
            if record.superseded_by_id is None:
                live[(subject_type, subject_id)] = bool(record.counts)
    return Counting(legacy, _ledger_at(session), live)
