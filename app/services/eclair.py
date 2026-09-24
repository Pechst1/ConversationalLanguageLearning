"""WP-S7 — Éclair: a 60-second minimal-pair sprint between two contrasting rules.

* **Unlocked** once two rules that are each other's contrast partners
  (WP-L2 ``contrast_partners``) are both introduced. A pair is keyed
  ``"<low id>-<high id>"``.
* **Items** come from WP-S2's item bank, read-only: the discriminate rung's
  minimal pair (:func:`app.services.item_bank.pair_item`) of each rule,
  interleaved. The keys travel with the items, so the page grades locally
  (no request per tap); the server grades the same answers again against the
  keys it stored when the round is filed.
* **Storage** — a round is an ``AtelierSession`` with its own status
  (``eclair`` → ``eclair_done``), like the test-out, so it never reads as the
  day's séance. The best score per pair is the best filed round.
* **Evidence** — every graded answer is one discriminate-rung observation,
  through the forge's own caps (:class:`app.core.forge.ForgeState` in
  ``MODE_ECLAIR``): per rule, the first success and the first failure move the
  schedule, the rest fold into the concept's life. A second round of the same
  pair on the same day moves nothing: it folds entirely. An Éclair never moves
  a rule's rung.
"""
from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import ForgeState, RuleTrack, Rung, Verdict
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User

ECLAIR_SECONDS = 60
#: More items than anyone answers in a minute; unanswered ones are never served.
ECLAIR_ITEMS = 40
ECLAIR_STATUS = "eclair"
ECLAIR_DONE_STATUS = "eclair_done"
ECLAIR_KEY = "eclair"
#: Candidates the bank is asked for per rule before it gives up.
_MAX_CANDIDATES = 400


class EclairUnavailable(LookupError):
    """No contrasting pair is unlocked for this learner (or the flag is off)."""


def pair_key(first: int, second: int) -> str:
    low, high = sorted((int(first), int(second)))
    return f"{low}-{high}"


def parse_pair_key(value: str | None) -> tuple[int, int] | None:
    try:
        left, right = str(value or "").split("-", 1)
        low, high = sorted((int(left), int(right)))
    except (TypeError, ValueError):
        return None
    return (low, high) if low != high else None


def eclair_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "ATELIER_ECLAIR_ENABLED", True))


# ---------------------------------------------------------------------------
# Pairs
# ---------------------------------------------------------------------------


def _partner_refs(concept: GrammarConcept) -> list[int | str]:
    """WP-L2's partners: the catalogue attribute / ``source_refs`` (v1 overrides)
    and the v2 syllabus block."""

    from app.services.grammar_catalog import concept_syllabus
    from app.services.unified_srs import contrast_partner_refs

    refs: list[int | str] = list(contrast_partner_refs(concept))
    for value in concept_syllabus(concept).get("contrast_partners") or []:
        if isinstance(value, str) and value.strip() and value.strip() not in refs:
            refs.append(value.strip())
    return refs


def _is_introduced(progress: UserGrammarProgress | None) -> bool:
    if progress is None:
        return False
    return (
        progress.introduced_at is not None
        or int(progress.reps or 0) > 0
        or progress.forge_rung is not None
        or progress.held_at is not None
    )


def _bank_units(concept: GrammarConcept) -> list[str]:
    from app.services import item_bank

    try:
        return item_bank.units_for_external_id(concept.external_id)
    except Exception:  # pragma: no cover - a catalogue without templates
        return []


def _rounds(db: Session, user: User) -> list[AtelierSession]:
    return (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == ECLAIR_DONE_STATUS)
        .all()
    )


def _round_pair(session: AtelierSession) -> str | None:
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    meta = quote.get(ECLAIR_KEY) if isinstance(quote.get(ECLAIR_KEY), dict) else {}
    return str(meta.get("pair") or "") or None


def _round_score(session: AtelierSession) -> int:
    recap = session.recap_payload if isinstance(session.recap_payload, dict) else {}
    meta = recap.get(ECLAIR_KEY) if isinstance(recap.get(ECLAIR_KEY), dict) else {}
    try:
        return int(meta.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def best_scores(db: Session, user: User) -> dict[str, dict[str, int]]:
    """``{pair: {best, plays}}`` over the learner's filed rounds."""

    out: dict[str, dict[str, int]] = {}
    for session in _rounds(db, user):
        key = _round_pair(session)
        if not key:
            continue
        row = out.setdefault(key, {"best": 0, "plays": 0})
        row["plays"] += 1
        row["best"] = max(row["best"], _round_score(session))
    return out


def eclair_pairs(db: Session, user: User) -> list[dict[str, Any]]:
    """Every unlocked pair: two introduced rules that contrast, both with bank items."""

    progress = {
        row.concept_id: row
        for row in db.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id).all()
    }
    introduced_ids = [cid for cid, row in progress.items() if _is_introduced(row)]
    if len(introduced_ids) < 2:
        return []
    active = (
        db.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True))
        .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
        .all()
    )
    by_ref: dict[int | str, GrammarConcept] = {}
    for concept in active:
        by_ref[concept.id] = concept
        if concept.external_id:
            by_ref[concept.external_id] = concept
    introduced = [by_ref[cid] for cid in introduced_ids if cid in by_ref]
    scores = best_scores(db, user)
    seen: set[str] = set()
    pairs: list[dict[str, Any]] = []
    for concept in sorted(introduced, key=lambda item: (item.difficulty_order or 0, item.id)):
        for ref in _partner_refs(concept):
            partner = by_ref.get(ref)
            if partner is None or partner.id == concept.id or partner.id not in progress:
                continue
            if not _is_introduced(progress.get(partner.id)):
                continue
            key = pair_key(concept.id, partner.id)
            if key in seen:
                continue
            if not _bank_units(concept) or not _bank_units(partner):
                continue
            seen.add(key)
            low, high = sorted((concept, partner), key=lambda item: item.id)
            score = scores.get(key, {})
            pairs.append(
                {
                    "pair": key,
                    "concept_ids": [low.id, high.id],
                    "rules": [_rule_view(db, low), _rule_view(db, high)],
                    "best": int(score.get("best", 0)),
                    "plays": int(score.get("plays", 0)),
                }
            )
    return pairs


def _rule_view(db: Session, concept: GrammarConcept) -> dict[str, Any]:
    from app.services.atelier import fr_localizations_by_concept_id

    fr = fr_localizations_by_concept_id(db, [concept.id]).get(concept.id)
    return {
        "concept_id": concept.id,
        "external_id": concept.external_id,
        "title_fr": (fr.title if fr else None) or concept.name,
        "category": concept.category,
        "subskill": concept.subskill,
        "name": concept.name,
    }


def eclair_offer_for(db: Session, *, user: User, concept_ids: Iterable[int]) -> dict[str, Any] | None:
    """The first unlocked pair that has one of these rules, for the séance recap."""

    if not eclair_enabled():
        return None
    wanted = [int(cid) for cid in concept_ids]
    try:
        pairs = eclair_pairs(db, user)
    except Exception as exc:  # pragma: no cover - an offer never breaks a recap
        logger.warning("Éclair offer failed", error=str(exc))
        return None
    for concept_id in wanted:
        for pair in pairs:
            if concept_id in pair["concept_ids"]:
                return pair
    return None


# ---------------------------------------------------------------------------
# A round
# ---------------------------------------------------------------------------


def _items_for_rule(
    db: Session, *, user: User, concept: GrammarConcept, count: int, blocked: set[str], seed: str
) -> list[dict[str, Any]]:
    from app.services import item_bank

    out: list[dict[str, Any]] = []
    bank = item_bank.default_bank()
    for unit in _bank_units(concept):
        stream = bank.sample(
            unit,
            random.Random(f"{seed}:{unit}"),  # noqa: S311 - reproducible variety, not security
            exclude=blocked,
            detector=item_bank.unit_detector(unit),
        )
        for tries, candidate in enumerate(stream):
            if tries >= _MAX_CANDIDATES or len(out) >= count:
                break
            if candidate.fingerprint in blocked:
                continue
            built = item_bank.pair_item(candidate, lesson_external_id=concept.external_id)
            if built is None:
                continue
            blocked.add(candidate.fingerprint)
            out.append(
                {
                    "id": str(built["id"]),
                    "concept_id": concept.id,
                    "prompt": built.get("prompt"),
                    "prompt_l10n": built.get("prompt_l10n") or {},
                    "labels": list(built.get("labels") or []),
                    "correct_answer": built.get("correct_answer"),
                    "fingerprint": candidate.fingerprint,
                    "unit": candidate.unit,
                }
            )
        if len(out) >= count:
            break
    return out


def _interleave(first: list[dict[str, Any]], second: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """Mix the two rules evenly, never more than two of one rule in a row.

    Both rules get the same share (the longer list is cut to the shorter one),
    so the sprint is a contrast, not one rule with a guest.
    """

    size = min(len(first), len(second))
    queues = [list(first[:size]), list(second[:size])]
    out: list[dict[str, Any]] = []
    last: list[int] = []
    while queues[0] or queues[1]:
        live = [index for index, queue in enumerate(queues) if queue]
        if len(last) >= 2 and last[-1] == last[-2] and len(live) == 2:
            pick = 1 - last[-1]
        elif len(live) == 2 and len(queues[0]) != len(queues[1]):
            # The rule behind catches up first, so the tail never bunches.
            pick = 0 if len(queues[0]) > len(queues[1]) else 1
        else:
            pick = rng.choice(live)
        out.append(queues[pick].pop(0))
        last.append(pick)
    return out


def start_round(db: Session, *, user: User, pair: str | None = None, concept_id: int | None = None) -> dict[str, Any]:
    """Open a round: the pair (or the first pair of ``concept_id``), its items."""

    from app.services.atelier import served_fingerprints
    from app.services.pilot_events import PilotEventService

    if not eclair_enabled():
        raise EclairUnavailable("eclair disabled")
    pairs = eclair_pairs(db, user)
    chosen = None
    if pair:
        wanted = parse_pair_key(pair)
        chosen = next((row for row in pairs if wanted and row["pair"] == pair_key(*wanted)), None)
    elif concept_id is not None:
        chosen = next((row for row in pairs if int(concept_id) in row["concept_ids"]), None)
    else:
        chosen = pairs[0] if pairs else None
    if chosen is None:
        raise EclairUnavailable("pair not unlocked")
    concepts = {c.id: c for c in db.query(GrammarConcept).filter(GrammarConcept.id.in_(chosen["concept_ids"])).all()}
    now = datetime.now(UTC)
    blocked = set(served_fingerprints(db, user))
    seed = f"{user.id}:eclair:{chosen['pair']}:{now.isoformat()}"
    per_rule = ECLAIR_ITEMS // 2
    first, second = (
        _items_for_rule(db, user=user, concept=concepts[cid], count=per_rule, blocked=blocked, seed=f"{seed}:{cid}")
        for cid in chosen["concept_ids"]
    )
    if not first or not second:
        raise EclairUnavailable("the bank has no pair items for this pair")
    items = _interleave(first, second, random.Random(seed))  # noqa: S311
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=list(chosen["concept_ids"]),
        quote_payload={
            ECLAIR_KEY: {
                "pair": chosen["pair"],
                "seconds": ECLAIR_SECONDS,
                "items": items,
                "started_at": now.isoformat(),
            }
        },
        status=ECLAIR_STATUS,
        recap_payload={},
    )
    db.add(session)
    db.flush([session])
    PilotEventService(db).record(
        "eclair_started",
        user_id=user.id,
        entity_type="atelier_session",
        entity_id=session.id,
        payload={"pair": chosen["pair"], "items": len(items)},
    )
    db.commit()
    db.refresh(session)
    return {
        "eclair_id": str(session.id),
        "pair": chosen["pair"],
        "concept_ids": chosen["concept_ids"],
        "rules": chosen["rules"],
        "seconds": ECLAIR_SECONDS,
        "best": chosen["best"],
        "plays": chosen["plays"],
        # The keys travel with the items: the page grades each tap at once.
        "items": [
            {key: item[key] for key in ("id", "concept_id", "prompt", "prompt_l10n", "labels", "correct_answer")}
            for item in items
        ],
    }


def _normalize(value: Any) -> str:
    from app.services.item_bank import normalize

    return normalize(value)


def grade_answers(items: list[dict[str, Any]], answers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grade the answered items against their stored keys, in answer order.

    Unknown ids and second answers to one item are ignored; an item nobody
    answered is not an error.
    """

    by_id = {str(item.get("id")): item for item in items}
    graded: list[dict[str, Any]] = []
    seen: set[str] = set()
    for answer in answers:
        item_id = str((answer or {}).get("id") or "")
        item = by_id.get(item_id)
        if item is None or item_id in seen:
            continue
        seen.add(item_id)
        correct = _normalize((answer or {}).get("answer")) == _normalize(item.get("correct_answer"))
        graded.append({"id": item_id, "concept_id": int(item["concept_id"]), "correct": correct, "item": item})
    return graded


def _played_today(db: Session, *, user: User, pair: str, exclude_id: Any, now: datetime) -> bool:
    today = now.date()
    for session in _rounds(db, user):
        if session.id == exclude_id or _round_pair(session) != pair or session.completed_at is None:
            continue
        completed = session.completed_at if session.completed_at.tzinfo else session.completed_at.replace(tzinfo=UTC)
        if completed.date() == today:
            return True
    return False


def finish_round(
    db: Session,
    *,
    user: User,
    session: AtelierSession,
    answers: Iterable[dict[str, Any]],
    elapsed_ms: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """File a round: grade by the stored keys, write capped evidence, keep the best."""

    from app.services.atelier import _record_served_items
    from app.services.forge import ForgeService
    from app.services.pilot_events import PilotEventService

    now = now or datetime.now(UTC)
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    meta = dict(quote.get(ECLAIR_KEY) or {})
    pair = str(meta.get("pair") or "")
    if session.status == ECLAIR_DONE_STATUS:
        return dict((session.recap_payload or {}).get(ECLAIR_KEY) or {})
    items = [item for item in meta.get("items") or [] if isinstance(item, dict)]
    graded = grade_answers(items, answers)
    best_before = best_scores(db, user).get(pair, {}).get("best", 0)
    fold_all = _played_today(db, user=user, pair=pair, exclude_id=session.id, now=now)

    concept_ids = [int(cid) for cid in session.selected_concept_ids or []]
    state = ForgeState(
        mode=core.MODE_ECLAIR,
        length=max(1, len(graded)),
        tracks=[RuleTrack(concept_id=cid, role=core.Role.CONTRAST.value, rung=int(Rung.DISCRIMINATE)) for cid in concept_ids],
    )
    forge = ForgeService(db)
    written = scheduled = 0
    for row in graded:
        verdict = Verdict.right() if row["correct"] else Verdict.wrong()
        decision = state.record(
            concept_id=row["concept_id"],
            rung=int(Rung.DISCRIMINATE),
            verdict=verdict,
            fingerprint=row["item"].get("fingerprint"),
        )
        if fold_all:
            decision.schedule = False
        forge._write_evidence(
            user=user,
            state=state,
            decision=decision,
            verdict=verdict,
            attempt=SimpleNamespace(score_0_4=4.0 if row["correct"] else 0.0),
            now=now,
            move_rung=False,
        )
        written += 1 if decision.counted else 0
        scheduled += 1 if decision.schedule else 0
    units: dict[str, list[str]] = {}
    for row in graded:
        units.setdefault(str(row["item"].get("unit") or ""), []).append(str(row["item"].get("fingerprint") or ""))
    for unit, fingerprints in units.items():
        _record_served_items(db, user=user, session=session, fingerprints=[f for f in fingerprints if f], unit=unit or None)

    score = sum(1 for row in graded if row["correct"])
    result = {
        "pair": pair,
        "score": score,
        "answered": len(graded),
        "best_before": int(best_before),
        "best": max(int(best_before), score),
        "new_best": score > int(best_before),
        "evidence_written": written,
        "schedule_moves": scheduled,
        "per_rule": {
            str(cid): {
                "right": sum(1 for row in graded if row["concept_id"] == cid and row["correct"]),
                "answered": sum(1 for row in graded if row["concept_id"] == cid),
            }
            for cid in concept_ids
        },
    }
    session.status = ECLAIR_DONE_STATUS
    session.completed_at = now
    session.recap_payload = {ECLAIR_KEY: result, "evidence": state.history}
    db.add(session)
    PilotEventService(db).record(
        "eclair_finished",
        user_id=user.id,
        entity_type="atelier_session",
        entity_id=session.id,
        payload={
            "pair": pair,
            "score": score,
            "answered": len(graded),
            "best": result["best"],
            "new_best": result["new_best"],
            "elapsed_ms": int(elapsed_ms) if isinstance(elapsed_ms, (int, float)) else None,
        },
    )
    db.commit()
    return result


def round_for_user(db: Session, *, user: User, eclair_id: Any) -> AtelierSession | None:
    session = db.get(AtelierSession, eclair_id)
    if session is None or session.user_id != user.id or session.status not in {ECLAIR_STATUS, ECLAIR_DONE_STATUS}:
        return None
    return session


__all__ = [
    "ECLAIR_DONE_STATUS",
    "ECLAIR_ITEMS",
    "ECLAIR_SECONDS",
    "ECLAIR_STATUS",
    "EclairUnavailable",
    "best_scores",
    "eclair_offer_for",
    "eclair_pairs",
    "finish_round",
    "grade_answers",
    "pair_key",
    "parse_pair_key",
    "round_for_user",
    "start_round",
]
