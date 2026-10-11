"""«Vérification du lexique» — skip the words a learner already knows (2026-10-03).

The owner's goal is progress substantially faster than Duolingo. The level gate
asks for 80 % of each sub-band's core words on a known card; a learner placed at
B1 who already reads A1/A2 French would otherwise spend months re-carding words
they know. After placement, each sub-band *below* the learner's own can be
checked in about two minutes:

* :data:`ITEMS` core words of the sub-band (no grammar words, numerals or
  colloquial words), each a four-way meaning choice in the learner's language,
  plus «je ne sais pas»;
* the sample is seeded by learner, sub-band and day, so a retry the same day
  gets the same questions;
* :data:`PASS_SHARE` correct or better credits the sub-band: every core word of
  it the learner has no card for gets a settled card (``provenance="band_check"``)
  that counts as known now and comes back for a light check over the next weeks
  (:data:`VERIFY_WITHIN_DAYS`). A word missed in the check is not credited — it
  stays in the ordinary new-word supply.

Pure apart from the database reads and the credit write; no model call.

WP-127 (2026-10-04, owner decision 2) — **top-down, bounded, honest**:

* **Top-down ladder** (:func:`ladder`). The check starts at the highest eligible
  sub-band below the learner's own. A pass stops the ladder; a miss steps down
  one sub-band. It used to run every sub-band from A1.1 up — 8 × 24 = 192 items
  for a C1 learner (review F-3).
* **Bounded visits.** At most :data:`MAX_CHECKS_PER_VISIT` checks (2 × 24 = 48
  items) per visit; a visit is the checks graded within :data:`VISIT_HOURS`. The
  learner may stop after any check, and the ladder resumes where it stopped.
* **Inferred credit is marked as such.** On a pass, the sampled words answered
  right are *sampled recognition* (``provenance="band_check"``). The pass's
  unsampled words and every lower sub-band are *inferred* from it
  (``provenance="band_check_inferred"``): neither is productive use nor a CEFR
  claim. Inference never overwrites a weakness: a word with any card, or one
  missed in any check, is never credited, and a lower sub-band that was missed is
  never inferred. The light checks (:func:`credit_schedule`) stay the safety net.
* **Persistent assessment identity.** A check's sample is keyed by the learner,
  the sub-band and the attempt number (graded attempts so far, read from the
  pilot ledger), never by the day: reload, midnight and a retried POST see the
  same answer key, and a replayed submit returns the stored result and credits
  nothing twice.
* **A candidate threshold.** :data:`PASS_CORRECT` = 21 of 24 is a candidate under
  :data:`POLICY_VERSION`, documented in ``WP-127-THRESHOLD.md`` and validated by
  the pilot (WP-133b); each attempt records the policy, the sampled items and the
  misses so the pilot can measure it.
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.vocabulary import VocabularyWord
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon
from app.services.lexical_coverage import load_lexicon

ITEMS = 24
OPTIONS = 4
#: WP-127: the pass rule is a *candidate*, not a settled constant. 21 of 24
#: (87.5 %) halves the false fails of the old 22/24 for a learner who knows 92 % of
#: a band (≈30 % → ≈12 %) at the price of more false passes for one who knows 80 %
#: (≈12 % → ≈26 %). See docs/implementation/atelier-v2/WP-127-THRESHOLD.md.
PASS_CORRECT = 21
PASS_SHARE = PASS_CORRECT / ITEMS
#: Recorded on every attempt so the pilot can tell the rules apart.
POLICY_VERSION = "band-check-v2-topdown-21of24"
#: Directly sampled recognition: the word was on the check and answered right.
PROVENANCE = "band_check"
#: Inferred from a pass: not on the check (the pass's other words, lower bands).
INFERRED_PROVENANCE = "band_check_inferred"
CHECK_PROVENANCES: tuple[str, ...] = (PROVENANCE, INFERRED_PROVENANCE)
#: A visit is at most two checks: 2 × 24 = 48 items.
MAX_CHECKS_PER_VISIT = 2
#: Checks graded within this many hours of now belong to the current visit.
VISIT_HOURS = 12
#: The pilot-ledger event one graded attempt writes (its identity and its record).
ATTEMPT_EVENT = "band_check_attempt"
ATTEMPT_ENTITY = "band_check"
#: The credited card: settled, known now, first light check within these days.
CREDIT_STABILITY_DAYS = 30.0
VERIFY_WITHIN_DAYS = (10, 45)
#: EXPERIENCE-REVIEW 2026-10-04: the light check's window by how far below the
#: learner's own sub-band the credited one lies. A B2 learner credits about 2,800
#: words; all of them checked within 10–45 days came back at ~80 a day, filled the
#: drill (its 30 due a session) for weeks, and the throttle halved new words to 4.
#: Words a learner proved in a band far below their own are trusted longer.
VERIFY_WINDOWS: dict[int, tuple[int, int]] = {1: (20, 90), 2: (40, 180), 3: (90, 365)}


def credit_schedule(distance: int) -> tuple[float, tuple[int, int]]:
    """``(stability, (first, last) day of the light check)`` for a credited sub-band
    ``distance`` sub-bands below the learner's own. The stability keeps the word
    known (retrievability ≥ 0.85) until its check is due."""

    window = VERIFY_WINDOWS.get(max(1, distance)) or VERIFY_WINDOWS[max(VERIFY_WINDOWS)]
    return max(CREDIT_STABILITY_DAYS, window[1] / 1.5), window
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")


def _language(user: Any) -> str:
    native = str(getattr(user, "native_language", "") or "").lower()[:2]
    return native if native in {"en", "de"} else "en"


def _sub_band(level: str | None) -> str:
    """«A2.1» stays itself; a coarse «A2» (a declaration) is its first half."""

    raw = str(level or "").strip().upper()
    if raw in SUB_BANDS:
        return raw
    if raw.startswith("C2"):
        return SUB_BANDS[-1]
    coarse = raw[:2] if raw[:2] in {"A1", "A2", "B1", "B2", "C1"} else "A1"
    return f"{coarse}.1"


def _pool(sub_band: str) -> list[tuple[str, dict[str, Any]]]:
    """The sub-band's checkable core words, in list order."""

    return sorted(
        (
            (lemma, entry)
            for lemma, entry in load_lexicon().lemmas.items()
            if entry.get("sub_band") == sub_band
            and not entry.get("numeral")
            and entry.get("pos") not in {"function", "number"}
            and entry.get("register") != "familier"
            and isinstance(entry.get("gloss"), dict)
        ),
        key=lambda item: int(item[1].get("rank") or 0),
    )


def attempt_id(user: Any, sub_band: str, attempt: int) -> str:
    """The persistent identity of one check: learner, sub-band, attempt number.

    Not the day (the 2026-10-03 seed was): a check opened before midnight and
    sent after it is graded against the key it was shown."""

    digest = hashlib.sha256(f"{getattr(user, 'id', '')}:{sub_band}:{int(attempt)}".encode()).hexdigest()
    return f"{sub_band}:{int(attempt)}:{digest[:16]}"


def _seed(user: Any, sub_band: str, attempt: int) -> int:
    return int(attempt_id(user, sub_band, attempt).rsplit(":", 1)[1][:12], 16)


#: EXERCISE-QA: nouns with an aspirated h take «le/la», never «l'» («le haricot»,
#: «la honte», «le héros»). The lexicon does not mark them.
H_ASPIRE: frozenset[str] = frozenset(
    {
        "hache", "haie", "haillon", "haine", "hall", "halle", "halte", "hamac", "hameau", "hamburger",
        "hamster", "hanche", "handball", "handicap", "hangar", "hareng", "haricot", "harnais", "harpe",
        "hasard", "hâte", "hausse", "haut", "hauteur", "havre", "hérisson", "hernie", "héros", "hêtre",
        "hibou", "hiérarchie", "hockey", "homard", "honte", "hoquet", "hotte", "housse", "houx", "hublot",
        "huit", "hurlement", "hutte", "hachis", "haddock", "hachette", "hamecon", "hameçon", "harcèlement",
        "hardiesse", "harem", "hargne", "hennissement", "héron", "hérault", "hollande", "hongrie", "huée",
        "huguenot", "hune", "huppe",
    }
)


def _shown(lemma: str, entry: dict[str, Any]) -> str:
    """A noun with its article, so the gender is part of what is recognised."""

    if entry.get("pos") != "noun":
        return lemma
    gender = entry.get("gender")
    if lemma[:1].lower() in "aeéèêiîoôuûh" and lemma.lower() not in H_ASPIRE:
        return f"l'{lemma}"
    return f"{'la' if gender == 'f' else 'le'} {lemma}"


def sample(user: Any, sub_band: str, *, attempt: int = 0, now: datetime | None = None) -> list[dict[str, Any]]:
    """One attempt's check items for a sub-band: ``{id, fr, options[]}`` (no answer key).

    ``now`` is accepted for older callers and ignored: the sample is the attempt's."""

    return [{k: v for k, v in item.items() if k != "answer"} for item in _items(user, sub_band, attempt=attempt)]


def _items(user: Any, sub_band: str, *, attempt: int = 0, now: datetime | None = None) -> list[dict[str, Any]]:
    del now  # WP-127: the key is the attempt's, never the day's
    language = _language(user)
    pool = _pool(sub_band)
    if len(pool) < ITEMS:
        return []
    rng = random.Random(_seed(user, sub_band, attempt))  # noqa: S311 - a seeded sample, not a secret
    picked = rng.sample(pool, ITEMS)
    items: list[dict[str, Any]] = []
    for lemma, entry in picked:
        right = str(entry["gloss"].get(language) or entry["gloss"].get("en") or "")
        same_pos = [
            str(other["gloss"].get(language) or "")
            for other_lemma, other in pool
            if other_lemma != lemma and other.get("pos") == entry.get("pos")
        ]
        distractors = [gloss for gloss in dict.fromkeys(same_pos) if gloss and gloss != right]
        options = [right, *rng.sample(distractors, min(OPTIONS - 1, len(distractors)))]
        rng.shuffle(options)
        items.append({"id": lemma, "fr": _shown(lemma, entry), "options": options, "answer": options.index(right)})
    return items


def _learner_index(db: Session, user: Any) -> int:
    from app.services.lexical_coverage import _cefr_estimate

    level, _source = _cefr_estimate(db, user)
    return SUB_BANDS.index(_sub_band(level))


def checkable(db: Session, user: Any) -> list[dict[str, Any]]:
    """Sub-bands below the learner's own, each with its word count and whether credited.

    Listed lowest first (the shape older clients read); :func:`ladder` says which
    one to check next, top-down."""

    current = _learner_index(db, user)
    kinds = credit_kinds(db, user)
    return [
        {
            "sub_band": band,
            "words": len(_pool(band)),
            "credited": band in kinds,
            "credit_kind": kinds.get(band),
        }
        for band in SUB_BANDS[:current]
        if len(_pool(band)) >= ITEMS
    ]


def credit_kinds(db: Session, user: Any) -> dict[str, str]:
    """sub-band → ``sampled`` (a pass on that band) or ``inferred`` (from a pass above)."""

    rows = db.execute(
        select(UserVocabularyProgress.provenance_ref, UserVocabularyProgress.provenance)
        .where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.provenance.in_(CHECK_PROVENANCES),
        )
        .distinct()
    ).all()
    kinds: dict[str, str] = {}
    for ref, provenance in rows:
        if not ref:
            continue
        if provenance == PROVENANCE:
            kinds[str(ref)] = "sampled"
        else:
            kinds.setdefault(str(ref), "inferred")
    for attempt in attempts(db, user):
        # A pass whose every word already had a card writes no row; it still settles the band.
        if attempt.get("passed"):
            kinds[str(attempt.get("sub_band"))] = "sampled"
            for band in attempt.get("inferred_bands") or []:
                kinds.setdefault(str(band), "inferred")
    return kinds


def credited_sub_bands(db: Session, user: Any) -> set[str]:
    return set(credit_kinds(db, user))


# ---------------------------------------------------------------------------
# WP-127 — the ledger of attempts, the ladder and the visit
# ---------------------------------------------------------------------------


def _ledger_rows(db: Session, user: Any) -> list[Any]:
    from app.db.models.pilot_event import PilotEvent

    return list(
        db.scalars(
            select(PilotEvent)
            .where(PilotEvent.user_id == user.id, PilotEvent.event_type == ATTEMPT_EVENT)
            .order_by(PilotEvent.occurred_at.asc())
        ).all()
    )


def attempts(db: Session, user: Any) -> list[dict[str, Any]]:
    """Every graded attempt, oldest first: the stored result plus ``graded_at``."""

    rows: list[dict[str, Any]] = []
    for row in _ledger_rows(db, user):
        payload = dict(row.payload or {})
        payload["attempt_id"] = row.entity_id
        payload["graded_at"] = row.occurred_at
        rows.append(payload)
    return rows


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def next_attempt(db: Session, user: Any, sub_band: str) -> int:
    """The attempt number a check of ``sub_band`` opens at now (graded ones so far)."""

    return sum(1 for row in attempts(db, user) if row.get("sub_band") == sub_band)


def visit_checks_used(db: Session, user: Any, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=VISIT_HOURS)
    return sum(1 for row in attempts(db, user) if (_aware(row.get("graded_at")) or now) >= since)


def _missed_bands(rows: list[dict[str, Any]]) -> set[str]:
    """Sub-bands whose latest attempt did not pass."""

    latest: dict[str, bool] = {}
    for row in rows:
        latest[str(row.get("sub_band"))] = bool(row.get("passed"))
    return {band for band, passed in latest.items() if not passed}


def _missed_words(rows: list[dict[str, Any]]) -> set[str]:
    return {str(word) for row in rows for word in row.get("missed") or []}


def ladder(db: Session, user: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Where the top-down check stands for this learner.

    ``next`` is the highest eligible sub-band above every credited one that has
    not been missed: the first check starts at the top, a miss steps down, a pass
    leaves nothing above it to check, so the ladder stops. ``status``: ``open``
    (a check can start now), ``paused`` (this visit's two checks are spent; it
    resumes on the next visit), ``done`` (nothing left to check) or ``none``
    (nothing below the learner's level to check at all)."""

    rows = attempts(db, user)
    bands = checkable(db, user)
    missed = _missed_bands(rows)
    floor = max((SUB_BANDS.index(row["sub_band"]) for row in bands if row["credited"]), default=-1)
    candidates = [
        row["sub_band"]
        for row in sorted(bands, key=lambda row: SUB_BANDS.index(row["sub_band"]), reverse=True)
        if SUB_BANDS.index(row["sub_band"]) > floor and row["sub_band"] not in missed and not row["credited"]
    ]
    used = visit_checks_used(db, user, now=now)
    left = max(0, MAX_CHECKS_PER_VISIT - used)
    upcoming = candidates[0] if candidates else None
    if not bands:
        status = "none"
    elif upcoming is None:
        status = "done"
    elif left == 0:
        status = "paused"
    else:
        status = "open"
    for row in bands:
        row["missed"] = row["sub_band"] in missed and not row["credited"]
    return {
        "policy_version": POLICY_VERSION,
        "status": status,
        "next": upcoming if status == "open" else None,
        "resume_band": upcoming if status == "paused" else None,
        "visit_checks_used": used,
        "visit_checks_left": left,
        "max_checks_per_visit": MAX_CHECKS_PER_VISIT,
        "items_per_check": ITEMS,
        "pass_correct": PASS_CORRECT,
        "bands": sorted(bands, key=lambda row: SUB_BANDS.index(row["sub_band"]), reverse=True),
    }


class VisitFull(Exception):
    """This visit's checks are spent (:data:`MAX_CHECKS_PER_VISIT`)."""


class StaleAttempt(Exception):
    """The client answered an attempt that is neither the current nor a graded one."""


def start(db: Session, user: Any, sub_band: str, *, now: datetime | None = None) -> dict[str, Any]:
    """The check to show for ``sub_band``: the current attempt's items, no key.

    Idempotent: nothing is written, so a reload shows the same items. Refused
    (:class:`VisitFull`) once this visit's checks are spent."""

    if visit_checks_used(db, user, now=now) >= MAX_CHECKS_PER_VISIT:
        raise VisitFull(sub_band)
    attempt = next_attempt(db, user, sub_band)
    return {
        "sub_band": sub_band,
        "items": sample(user, sub_band, attempt=attempt),
        "pass_share": PASS_SHARE,
        "pass_correct": PASS_CORRECT,
        "attempt_id": attempt_id(user, sub_band, attempt),
        "policy_version": POLICY_VERSION,
    }


def submit(
    db: Session,
    user: Any,
    sub_band: str,
    answers: dict[str, int | None],
    *,
    attempt: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Grade one attempt; on a pass credit the sub-band (sampled) and below (inferred).

    ``attempt`` is the ``attempt_id`` the client was shown. Replaying a graded one
    returns the stored result and credits nothing. Flushes, never commits."""

    from app.services.pilot_events import PilotEventService

    now = now or datetime.now(UTC)
    if attempt:
        for row in attempts(db, user):
            if row.get("attempt_id") == attempt:
                return {**_public(row), "replayed": True, **_after(db, user, now=now)}
    number = next_attempt(db, user, sub_band)
    current = attempt_id(user, sub_band, number)
    if attempt and attempt != current:
        raise StaleAttempt(attempt)
    if visit_checks_used(db, user, now=now) >= MAX_CHECKS_PER_VISIT:
        raise VisitFull(sub_band)
    items = _items(user, sub_band, attempt=number)
    if not items:
        raise ValueError(f"no check for {sub_band}")
    previous = attempts(db, user)
    missed = {item["id"] for item in items if answers.get(item["id"]) != item["answer"]}
    dont_know = sorted(item["id"] for item in items if answers.get(item["id"]) is None)
    sampled = [item["id"] for item in items]
    correct = len(items) - len(missed)
    passed = correct >= PASS_CORRECT
    credited_sampled = credited_inferred = 0
    inferred_bands: list[str] = []
    if passed:
        weak = missed | _missed_words(previous)
        right = set(sampled) - missed
        credited_sampled = credit(db, user, sub_band, exclude=weak, only=right, provenance=PROVENANCE, now=now)
        credited_inferred = credit(
            db, user, sub_band, exclude=weak | set(sampled), provenance=INFERRED_PROVENANCE, now=now
        )
        kinds = credit_kinds(db, user)
        missed_bands = _missed_bands(previous)
        for band in reversed(SUB_BANDS[: SUB_BANDS.index(sub_band)]):
            # A lower band the learner missed is a weakness on record: never inferred.
            if band in missed_bands or band in kinds or not _pool(band):
                continue
            credited_inferred += credit(db, user, band, exclude=weak, provenance=INFERRED_PROVENANCE, now=now)
            inferred_bands.append(band)
    record = {
        "policy_version": POLICY_VERSION,
        "sub_band": sub_band,
        "attempt": number,
        "sampled": sampled,
        "missed": sorted(missed),
        "dont_know": dont_know,
        "correct": correct,
        "total": len(items),
        "pass_correct": PASS_CORRECT,
        "passed": passed,
        "credited_sampled": credited_sampled,
        "credited_inferred": credited_inferred,
        "inferred_bands": inferred_bands,
    }
    PilotEventService(db).record(
        ATTEMPT_EVENT,
        user_id=user.id,
        entity_type=ATTEMPT_ENTITY,
        entity_id=current,
        payload=record,
        occurred_at=now,
    )
    db.flush()
    return {**_public({**record, "attempt_id": current}), "replayed": False, **_after(db, user, now=now)}


def _public(row: dict[str, Any]) -> dict[str, Any]:
    sampled = int(row.get("credited_sampled") or 0)
    inferred = int(row.get("credited_inferred") or 0)
    return {
        "sub_band": row.get("sub_band"),
        "correct": int(row.get("correct") or 0),
        "total": int(row.get("total") or 0),
        "passed": bool(row.get("passed")),
        "credited_words": sampled + inferred,
        "credited_sampled": sampled,
        "credited_inferred": inferred,
        "inferred_bands": list(row.get("inferred_bands") or []),
        "missed": list(row.get("missed") or []),
        "pass_correct": int(row.get("pass_correct") or PASS_CORRECT),
        "attempt_id": row.get("attempt_id"),
        "policy_version": row.get("policy_version") or POLICY_VERSION,
    }


def _after(db: Session, user: Any, *, now: datetime) -> dict[str, Any]:
    state = ladder(db, user, now=now)
    return {"next": state["next"], "ladder_status": state["status"], "resume_band": state["resume_band"]}


def credit(
    db: Session,
    user: Any,
    sub_band: str,
    *,
    exclude: set[str] = frozenset(),
    only: set[str] | None = None,
    provenance: str = PROVENANCE,
    now: datetime,
) -> int:
    """Settled, known cards for the sub-band's core words the learner has no card for.

    A word with any card already — a weakness on record, or a word being learnt —
    is never touched: credit only ever adds."""

    ensure_core_lexicon(db)
    lemmas = {lemma for lemma, _entry in _pool(sub_band)} - set(exclude)
    if only is not None:
        lemmas &= set(only)
    if not lemmas:
        return 0
    rows = db.scalars(
        select(VocabularyWord).where(
            VocabularyWord.deck_name == CORE_DECK, VocabularyWord.normalized_word.in_(lemmas)
        )
    ).all()
    have = set(
        db.scalars(
            select(VocabularyWord.normalized_word)
            .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
            .where(UserVocabularyProgress.user_id == user.id)
        )
    )
    distance = _learner_index(db, user) - SUB_BANDS.index(sub_band) if sub_band in SUB_BANDS else 1
    stability, window = credit_schedule(distance)
    written = 0
    for word in rows:
        if word.normalized_word in have:
            continue
        rng = random.Random(f"{getattr(user, 'id', '')}:{word.id}")  # noqa: S311 - a seeded spread
        due = now + timedelta(days=rng.randint(*window))
        db.add(
            UserVocabularyProgress(
                user_id=user.id,
                word_id=word.id,
                stability=stability,
                difficulty=4.0,
                reps=2,
                lapses=0,
                state="review",
                phase="review",
                scheduler="fsrs",
                scheduled_days=(due - now).days,
                interval_days=(due - now).days,
                last_review_date=now,
                next_review_date=due,
                due_at=due,
                due_date=due.date(),
                proficiency_score=80,
                times_seen=1,
                provenance=provenance,
                provenance_ref=sub_band,
            )
        )
        have.add(word.normalized_word)
        written += 1
    db.flush()
    return written


__all__ = [
    "ATTEMPT_EVENT",
    "INFERRED_PROVENANCE",
    "ITEMS",
    "MAX_CHECKS_PER_VISIT",
    "PASS_CORRECT",
    "PASS_SHARE",
    "POLICY_VERSION",
    "PROVENANCE",
    "StaleAttempt",
    "VisitFull",
    "attempt_id",
    "attempts",
    "checkable",
    "credit",
    "credit_kinds",
    "credit_schedule",
    "credited_sub_bands",
    "ladder",
    "next_attempt",
    "sample",
    "start",
    "submit",
]
