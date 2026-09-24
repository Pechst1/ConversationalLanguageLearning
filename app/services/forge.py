"""La Forge (WP-S3): the séance as the grammar engine — service and interfaces.

The pure engine lives in :mod:`app.core.forge` (staircase, composition,
evidence caps, test-out); this module connects it to the app:

* **State** is kept on the Atelier session, ``quote_payload["forge"]``
  (:meth:`ForgeState.to_dict`), so a resumed séance agrees with itself. A
  rule's rung between séances is ``UserGrammarProgress.forge_rung``.
* **Evidence**: every checked answer becomes one ``apply_grammar_evidence``
  call (a schedule move) or one ``note_concept_evidence`` call (a fold: the
  concept's life and «Tenue» still see it). The end-of-session single evidence
  of the legacy ladder is not written for a forge séance
  (``AtelierSRSService.complete_session``), so nothing is counted twice.

Interfaces for the parallel packages — each has a default adapter that works
on today's code, and is replaced by passing another implementation:

* :class:`ItemProvider` (WP-S2 item bank): ``item_for(concept, rung,
  exclude)`` → a :class:`ForgeItem` with its answer key. Default:
  :class:`PayloadItemProvider`, over today's per-session exercise set.
* :class:`Composer` (WP-S4 picker): ``pick(user, now=…)`` → a list of
  :class:`PickedUnit` ``(concept_id, role: today | due | contrast)``. Default:
  :class:`SelectTodayComposer`, over ``AtelierScheduler.select_today`` plus
  the WP-L4 concept life and the WP-L2 contrast partners.
* **Grading** (WP-S1): the forge consumes a :class:`app.core.forge.Verdict`
  (``correct | partial | incorrect`` + ``checked``). Default:
  :func:`verdict_from_attempt` over the existing submit path's attempt row; a
  correction that carries an explicit ``"checked": bool`` wins. When an
  asynchronous verdict lands later, :meth:`ForgeService.amend_attempt` turns a
  previously unchecked answer into evidence.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Role, Rung, Verdict
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User

FORGE_KEY = "forge"
#: Session status of a running / finished «Épreuve de la règle». Kept apart from
#: ``in_progress`` / ``completed`` so a test-out is never mistaken for the day's
#: séance (the active-session lookup, the day progress, the streak).
TEST_OUT_STATUS = "test_out"
TEST_OUT_DONE_STATUS = "test_out_done"

#: Where each rung's items come from in today's exercise-set payload,
#: in preference order: ``(round, mode)``.
RUNG_POOLS: dict[Rung, tuple[tuple[str, str], ...]] = {
    Rung.RECOGNISE: (("recognize", "fill"),),
    Rung.DISCRIMINATE: (("recognize", "classify"),),
    Rung.BUILD: (("recognize", "word_bank"),),
    Rung.TRANSFORM: (("transform", "rewrite"),),
    Rung.PRODUCE: (("sentence", "sentence"),),
    Rung.FREE_USE: (("conversation", "conversation"),),
}

#: An attempt's ``(round, mode)`` → the rung it is evidence for.
_RUNG_BY_ROUND_MODE: dict[tuple[str, str], Rung] = {
    ("recognize", "fill"): Rung.RECOGNISE,
    ("recognize", "classify"): Rung.DISCRIMINATE,
    ("recognize", "word_bank"): Rung.BUILD,
}
_RUNG_BY_ROUND: dict[str, Rung] = {
    "transform": Rung.TRANSFORM,
    "sentence": Rung.PRODUCE,
    "speak": Rung.PRODUCE,
    "conversation": Rung.FREE_USE,
}

#: Rounds graded by a model; a placeholder verdict there is unchecked.
_MODEL_ROUNDS = frozenset({"sentence", "speak", "conversation", "produce"})


def rung_for_attempt(round_name: str | None, mode: str | None) -> Rung | None:
    round_key = str(round_name or "")
    if round_key == "recognize":
        return _RUNG_BY_ROUND_MODE.get((round_key, str(mode or "")), Rung.RECOGNISE)
    return _RUNG_BY_ROUND.get(round_key)


def verdict_from_attempt(attempt: AtelierAttempt) -> Verdict:
    """The grader's verdict, as the forge reads it (the WP-S1 seam)."""

    correction = attempt.correction_payload if isinstance(attempt.correction_payload, dict) else {}
    confidence = (attempt.answer_payload or {}).get("confidence") if isinstance(attempt.answer_payload, dict) else None
    explicit = correction.get("checked")
    if isinstance(explicit, bool):
        checked = explicit
    else:
        debug = correction.get("correction_debug") if isinstance(correction.get("correction_debug"), dict) else {}
        checked = not (
            correction.get("assessment_status") == "unavailable"
            or attempt.verdict == "needs_review"
            or (str(attempt.round) in _MODEL_ROUNDS and bool(debug.get("fallback_used")))
        )
    verdict = str(attempt.verdict or "")
    if verdict in {"correct", "accepted"}:
        outcome = core.OUTCOME_CORRECT
    elif verdict == "partial":
        outcome = core.OUTCOME_PARTIAL
    else:
        outcome = core.OUTCOME_INCORRECT
    return Verdict(outcome=outcome, checked=checked, confidence=confidence if confidence in {"sure", "unsure"} else None)


# ---------------------------------------------------------------------------
# ItemProvider — WP-S2's item bank replaces the default adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ForgeItem:
    """One item to pose: what the Épreuve renders and how it is checked."""

    concept_id: int
    rung: int
    round: str
    mode: str
    item_id: str
    item_index: int
    #: Stable identity for "never the same item twice" (reprise, variety).
    fingerprint: str
    payload: dict[str, Any] = field(default_factory=dict)
    #: The expected answer when the provider knows it (WP-S2 always does).
    answer_key: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "rung": self.rung,
            "rung_name": core.rung_name(self.rung),
            "round": self.round,
            "mode": self.mode,
            "item_id": self.item_id,
            "item_index": self.item_index,
            "fingerprint": self.fingerprint,
        }


class ItemProvider(Protocol):
    def item_for(self, *, concept_id: int, rung: int, exclude: set[str]) -> ForgeItem | None:
        """An item of this rule at this rung that is not in ``exclude``.

        May answer with a neighbouring rung when the asked one has nothing
        left; the returned item's ``rung`` is the rung actually posed.
        """


def fingerprint_for(concept_id: int, round_name: str, mode: str, item_id: str) -> str:
    return f"{int(concept_id)}:{round_name}:{mode}:{item_id}"


def _payload_items(payload: dict[str, Any], round_name: str, mode: str) -> list[dict[str, Any]]:
    if round_name == "recognize":
        container = ((payload.get("recognize") or {}).get(mode) or {})
    elif round_name == "transform":
        container = payload.get("transform") or {}
    else:
        container = ((payload.get("output_ladder") or {}).get(round_name) or {})
    items = container.get("items") if isinstance(container, dict) else None
    return [item for item in (items or []) if isinstance(item, dict)]


def _rung_search_order(rung: int) -> list[int]:
    """The asked rung, then downwards, then upwards: never harder by surprise."""

    rung = core.clamp_rung(rung)
    below = list(range(rung - 1, -1, -1))
    above = list(range(rung + 1, int(core.TOP_RUNG) + 1))
    return [rung, *below, *above]


class PayloadItemProvider:
    """Default :class:`ItemProvider`: today's per-session exercise set.

    Each rung draws from its round/mode of the concept's payload (fill →
    recognise, classify → discriminate, word bank → build, transform,
    sentence → produce, conversation → free use).
    """

    def __init__(self, payloads: dict[int, dict[str, Any]]) -> None:
        self.payloads = payloads

    @classmethod
    def for_session(cls, db: Session, *, user: User, session: AtelierSession) -> PayloadItemProvider:
        from app.services.atelier import AtelierExerciseGenerationError, session_exercise_set

        payloads: dict[int, dict[str, Any]] = {}
        concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
        concepts = {c.id: c for c in db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()}
        for concept_id in concept_ids:
            concept = concepts.get(concept_id)
            if concept is None:
                continue
            try:
                exercise_set = session_exercise_set(db, user=user, session=session, concept=concept, fast_path=True)
            except AtelierExerciseGenerationError:  # pragma: no cover - fallback always exists
                continue
            payloads[concept_id] = dict(exercise_set.payload or {})
        return cls(payloads)

    def item_for(self, *, concept_id: int, rung: int, exclude: set[str]) -> ForgeItem | None:
        payload = self.payloads.get(int(concept_id))
        if not payload:
            return None
        for candidate_rung in _rung_search_order(rung):
            for round_name, mode in RUNG_POOLS[Rung(candidate_rung)]:
                for index, item in enumerate(_payload_items(payload, round_name, mode)):
                    item_id = str(item.get("id") or f"{round_name}-{index}")
                    fingerprint = fingerprint_for(concept_id, round_name, mode, item_id)
                    if fingerprint in exclude:
                        continue
                    return ForgeItem(
                        concept_id=int(concept_id),
                        rung=int(candidate_rung),
                        round=round_name,
                        mode=mode,
                        item_id=item_id,
                        item_index=index,
                        fingerprint=fingerprint,
                        payload=item,
                        answer_key=item.get("answer") or item.get("expected_answer") or item.get("correct_answer"),
                    )
        return None


# ---------------------------------------------------------------------------
# Composer — WP-S4's picker replaces the default adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PickedUnit:
    concept_id: int
    role: str  # Role.TODAY | Role.DUE | Role.CONTRAST


class Composer(Protocol):
    def pick(self, user: User, *, now: datetime) -> list[PickedUnit]:
        """The séance's rules and why each is there."""


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


_LEGACY_ROLE_TO_FORGE = {"new": Role.TODAY.value, "fragile": Role.DUE.value, "contrast": Role.CONTRAST.value}


class SelectTodayComposer:
    """Default :class:`Composer`: today's picker, read through the concept life.

    * **today** — the rule the journey introduced today (``introduced_at``
      today, not held), else a requested rule (Cahier «Forge»), else the
      weakest non-held rule of the pick (lowest forge rung);
    * **due** — the pick's «fragile» rules (due or weak);
    * **contrast** — today's rule's WP-L2 contrast partners the learner has
      met (at most one), else the pick's own contrast if not brand-new.
    """

    def __init__(
        self,
        db: Session,
        *,
        selections: list[Any] | None = None,
        preferred_concept_id: int | None = None,
    ) -> None:
        self.db = db
        self.selections = selections
        self.preferred_concept_id = preferred_concept_id

    def _progress(self, user: User, concept_ids: Iterable[int]) -> dict[int, UserGrammarProgress]:
        ids = list({int(item) for item in concept_ids})
        if not ids:
            return {}
        return {
            row.concept_id: row
            for row in self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id.in_(ids))
            .all()
        }

    def pick(self, user: User, *, now: datetime) -> list[PickedUnit]:
        from app.services.concept_life import is_held
        from app.services.unified_srs import contrast_partner_refs

        selections = self.selections
        if selections is None:
            from app.services.atelier import AtelierScheduler

            selections = AtelierScheduler(self.db).select_today(user)
        picked: list[tuple[int, str]] = [
            (int(selection.concept.id), _LEGACY_ROLE_TO_FORGE.get(str(selection.role), Role.DUE.value))
            for selection in selections
        ]
        today_date = (_aware(now) or datetime.now(UTC)).date()
        # The journey's rule of the day, even when the picker did not seat it.
        introduced_today = [
            row.concept_id
            for row in self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.introduced_at.isnot(None))
            .all()
            if (_aware(row.introduced_at) or now).date() == today_date and not is_held(row)
        ]
        progress = self._progress(user, [cid for cid, _ in picked] + introduced_today + (
            [int(self.preferred_concept_id)] if self.preferred_concept_id else []
        ))

        today_id: int | None = None
        if self.preferred_concept_id:
            today_id = int(self.preferred_concept_id)
        elif introduced_today:
            today_id = introduced_today[-1]
        else:
            candidates = [cid for cid, role in picked if role == Role.TODAY.value]
            if not candidates:
                weak = [
                    cid for cid, _role in picked
                    if progress.get(cid) is not None and not is_held(progress[cid])
                ]
                weak.sort(key=lambda cid: (progress[cid].forge_rung if progress[cid].forge_rung is not None else -1))
                candidates = weak[:1]
            today_id = candidates[0] if candidates else None

        units: list[PickedUnit] = []
        if today_id is not None:
            units.append(PickedUnit(today_id, Role.TODAY.value))
        for cid, role in picked:
            if cid == today_id:
                continue
            units.append(PickedUnit(cid, Role.DUE.value if role == Role.TODAY.value else role))

        if today_id is not None:
            concept = self.db.get(GrammarConcept, today_id)
            refs = contrast_partner_refs(concept) if concept is not None else []
            partner_ids: list[int] = []
            for ref in refs:
                if isinstance(ref, int):
                    partner_ids.append(ref)
                else:
                    row = self.db.query(GrammarConcept.id).filter(GrammarConcept.external_id == ref).first()
                    if row:
                        partner_ids.append(int(row[0]))
            met = self._progress(user, partner_ids)
            seated = {unit.concept_id for unit in units}
            partner = next(
                (pid for pid in partner_ids if pid in met and pid not in seated and met[pid].introduced_at is not None),
                None,
            )
            if partner is not None:
                units = [unit for unit in units if unit.role != Role.CONTRAST.value]
                units.append(PickedUnit(partner, Role.CONTRAST.value))
        return units


def initial_rung(progress: UserGrammarProgress | None) -> int:
    """A rule's rung before the forge first saw it, from its memory."""

    if progress is None:
        return int(Rung.RECOGNISE)
    if progress.forge_rung is not None:
        return core.clamp_rung(progress.forge_rung)
    stability = float(progress.stability or 0.0)
    if int(progress.reps or 0) <= 0 or stability < 1:
        return int(Rung.RECOGNISE)
    if stability < 3:
        return int(Rung.DISCRIMINATE)
    if stability < 7:
        return int(Rung.BUILD)
    if stability < 15:
        return int(Rung.TRANSFORM)
    return int(Rung.PRODUCE)


def forge_units(db: Session, user: User, picked: Iterable[PickedUnit], *, now: datetime) -> list[ForgeUnit]:
    """Picked rules → the engine's units: rung, novelty, the «Tenue» need."""

    from app.services.concept_life import HELD_SPACED_AFTER_DAYS, is_held

    picked = list(picked)
    rows = {
        row.concept_id: row
        for row in db.query(UserGrammarProgress)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.concept_id.in_([unit.concept_id for unit in picked] or [-1]),
        )
        .all()
    }
    now = _aware(now) or datetime.now(UTC)
    units: list[ForgeUnit] = []
    for unit in picked:
        progress = rows.get(unit.concept_id)
        rung = initial_rung(progress)
        is_new = progress is None or (int(progress.reps or 0) <= 0 and progress.introduced_at is None)
        introduced = _aware(progress.introduced_at) if progress is not None else None
        needs_spaced = bool(
            progress is not None
            and not is_held(progress)
            and introduced is not None
            and now - introduced >= timedelta(days=HELD_SPACED_AFTER_DAYS)
            and progress.spaced_success_at is None
        )
        if unit.role == Role.DUE.value:
            rung = max(0, rung - 1)  # a warm-up step after the spacing
        elif unit.role == Role.CONTRAST.value:
            rung = min(rung, int(Rung.DISCRIMINATE))  # minimal pairs first
        units.append(ForgeUnit(unit.concept_id, unit.role, rung, is_new=is_new, needs_spaced=needs_spaced))
    return units


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Selection:
    concept: GrammarConcept
    role: str


def _stored_selections(db: Session, session: AtelierSession) -> list[_Selection]:
    """The session's seated concepts with the roles stored at creation."""

    concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
    concepts = {c.id: c for c in db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids or [-1])).all()}
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    roles = quote.get("concept_roles") if isinstance(quote.get("concept_roles"), dict) else {}
    return [
        _Selection(concepts[cid], str(roles.get(str(cid)) or ("fragile" if index < 2 else "contrast")))
        for index, cid in enumerate(concept_ids)
        if cid in concepts
    ]


def forge_state_of(session: AtelierSession) -> ForgeState | None:
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    raw = quote.get(FORGE_KEY) if isinstance(quote, dict) else None
    return ForgeState.from_dict(raw) if isinstance(raw, dict) and raw.get("tracks") is not None else None


def is_forge_session(session: AtelierSession) -> bool:
    return forge_state_of(session) is not None


def _store_state(session: AtelierSession, state: ForgeState) -> None:
    quote = dict(session.quote_payload or {})
    quote[FORGE_KEY] = state.to_dict()
    session.quote_payload = quote
    flag_modified(session, "quote_payload")


def seconds_per_item(db: Session, user: User) -> float:
    from app.services.atelier import measured_seconds_per_drill

    try:
        measured = measured_seconds_per_drill(db, user)
    except Exception:  # pragma: no cover - a read never blocks a séance
        measured = None
    return float(measured or core.DEFAULT_SECONDS_PER_ITEM)


def seance_budget_seconds(user: User) -> int:
    from app.services.journey_rhythm import rhythm_of

    rhythm = str(getattr(rhythm_of(user), "value", rhythm_of(user)))
    return core.SEANCE_SECONDS_BY_RHYTHM.get(rhythm, core.SEANCE_SECONDS_BY_RHYTHM["regulier"])


_FORGE_ROLE_TO_LEGACY = {Role.TODAY.value: "new", Role.DUE.value: "fragile", Role.CONTRAST.value: "contrast"}


class ForgeService:
    def __init__(self, db: Session, *, item_provider: ItemProvider | None = None) -> None:
        self.db = db
        self._item_provider = item_provider

    # -- composing ------------------------------------------------------------

    def attach(
        self,
        *,
        user: User,
        session: AtelierSession,
        composer: Composer | None = None,
        now: datetime | None = None,
        keep_concepts: bool = False,
    ) -> ForgeState:
        """Compose a séance onto a fresh session (no attempts yet)."""

        now = now or datetime.now(UTC)
        quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
        if composer is None:
            selections = _stored_selections(self.db, session) if session.selected_concept_ids else None
            composer = SelectTodayComposer(
                self.db,
                selections=selections,
                preferred_concept_id=quote.get("forge_today_concept_id"),
            )
        picked = composer.pick(user, now=now)
        if keep_concepts:
            wanted = [int(cid) for cid in (session.selected_concept_ids or [])]
            by_id = {unit.concept_id: unit for unit in picked}
            picked = [by_id.get(cid) or PickedUnit(cid, Role.TODAY.value if i == 0 else Role.DUE.value)
                      for i, cid in enumerate(wanted)]
        units = forge_units(self.db, user, picked, now=now)
        if keep_concepts:
            # The learner chose these rules: keep every one of them.
            units = [ForgeUnit(u.concept_id, u.role, u.rung, is_new=False, needs_spaced=u.needs_spaced) for u in units]
        length = core.seance_length(seance_budget_seconds(user), seconds_per_item(self.db, user))
        state = ForgeState.seance(units, length=length)
        concept_ids = [track.concept_id for track in state.tracks]
        if concept_ids:
            session.selected_concept_ids = concept_ids
            quote = dict(session.quote_payload or {})
            quote["concept_roles"] = {
                str(track.concept_id): _FORGE_ROLE_TO_LEGACY.get(track.role, "fragile") for track in state.tracks
            }
            session.quote_payload = quote
        _store_state(session, state)
        self.db.add(session)
        return state

    def ensure_attached(self, *, user: User, session: AtelierSession) -> ForgeState | None:
        """A fresh in-progress séance gets the forge (flag on); others keep theirs."""

        from app.config import settings

        state = forge_state_of(session)
        if state is not None:
            return state
        if not settings.ATELIER_FORGE_ENABLED or session.status not in {"in_progress", "prepared"}:
            return None
        has_attempt = (
            self.db.query(AtelierAttempt.id).filter(AtelierAttempt.atelier_session_id == session.id).first()
            is not None
        )
        if has_attempt:
            return None  # a legacy séance already under way finishes as it began
        quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
        state = self.attach(user=user, session=session, keep_concepts=bool(quote.get("forge_keep_concepts")))
        self.db.commit()
        self.db.refresh(session)
        return state

    def start_test_out(self, *, user: User, concept_id: int, now: datetime | None = None) -> AtelierSession:
        """«Épreuve de la règle»: five mixed items, any rule, from day one."""

        concept = self.db.get(GrammarConcept, int(concept_id))
        if concept is None or not concept.active:
            raise LookupError("concept not available")
        state = ForgeState.test_out(concept.id)
        session = AtelierSession(
            user_id=user.id,
            selected_concept_ids=[concept.id],
            quote_payload={"concept_roles": {str(concept.id): "fragile"}, "forge_mode": core.MODE_TEST_OUT},
            status=TEST_OUT_STATUS,
            recap_payload={},
        )
        _store_state(session, state)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    # -- serving --------------------------------------------------------------

    def provider(self, *, user: User, session: AtelierSession) -> ItemProvider:
        return self._item_provider or PayloadItemProvider.for_session(self.db, user=user, session=session)

    def next_item(self, *, user: User, session: AtelierSession) -> dict[str, Any] | None:
        """The item the learner is on (pending) or the next one; stored as pending."""

        state = forge_state_of(session)
        if state is None or state.finished:
            return None
        if state.pending and int(state.pending.get("position", -1)) == state.position:
            return dict(state.pending)
        provider = self.provider(user=user, session=session)
        # ``session_exercise_set`` may commit and refresh the session: re-read.
        state = forge_state_of(session) or state
        exclude = set(state.served_fingerprints)
        for _ in range(len(state.tracks) + 1):
            slot = state.next_slot()
            if slot is None:
                break
            item = provider.item_for(concept_id=slot.concept_id, rung=slot.rung, exclude=exclude)
            if item is not None:
                pending = {
                    **slot.to_dict(),
                    **item.to_dict(),
                    "position": slot.position,
                    "length": state.length,
                    "role": slot.role,
                    "reprise": slot.reprise,
                }
                state.pending = pending
                _store_state(session, state)
                self.db.add(session)
                self.db.commit()
                return dict(pending)
            # Nothing left for this rule: it retires from the séance.
            track = state.track(slot.concept_id)
            if track is None:  # pragma: no cover - slots come from tracks
                break
            track.topped = True
        state.finished = True
        state.pending = None
        _store_state(session, state)
        self.db.add(session)
        self.db.commit()
        return None

    def view(self, *, user: User, session: AtelierSession) -> dict[str, Any]:
        """The forge's part of a session response (empty for a legacy séance)."""

        state = forge_state_of(session)
        if state is None:
            return {}
        upcoming = self.next_item(user=user, session=session)
        state = forge_state_of(session) or state
        return {
            "mode": state.mode,
            "length": state.length,
            "answered": state.position,
            "counted": state.counted_items,
            "finished": state.finished,
            "next": upcoming,
            "result": state.result,
            "rules": [
                {
                    "concept_id": track.concept_id,
                    "role": track.role,
                    "rung": track.rung,
                    "rung_name": core.rung_name(track.rung),
                    "served": track.served,
                    "topped": track.topped,
                }
                for track in state.tracks
            ],
        }

    # -- observing an answer ----------------------------------------------------

    def observe_attempt(
        self,
        *,
        user: User,
        session: AtelierSession,
        attempt: AtelierAttempt,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """One submitted attempt → staircase, evidence, test-out. Commits."""

        state = forge_state_of(session)
        if state is None or attempt.concept_id is None:
            return {}
        if state.finished or ":retest:" in str(attempt.exercise_id or ""):
            return self.view(user=user, session=session)
        rung = rung_for_attempt(attempt.round, attempt.mode)
        if rung is None:
            return self.view(user=user, session=session)
        exercise_key = _exercise_key(attempt)
        if exercise_key in state.served_fingerprints:
            return self.view(user=user, session=session)  # a resubmission: the first answer counted
        fingerprint = fingerprint_for(
            int(attempt.concept_id), str(attempt.round), _pool_mode(attempt), _attempt_item_id(attempt)
        )
        pending = state.pending or {}
        if int(pending.get("concept_id", -1)) == int(attempt.concept_id) and (
            pending.get("fingerprint") == fingerprint or str(pending.get("round")) == str(attempt.round)
        ):
            # The item the forge served: its identity and rung are the forge's.
            fingerprint = str(pending.get("fingerprint") or fingerprint)
            rung = Rung(core.clamp_rung(pending.get("rung", rung)))
        verdict = verdict_from_attempt(attempt)
        decision = state.record(
            concept_id=int(attempt.concept_id),
            rung=int(rung),
            verdict=verdict,
            fingerprint=fingerprint,
        )
        state.served_fingerprints.append(exercise_key)
        state.history[-1]["exercise_key"] = exercise_key
        now = now or datetime.now(UTC)
        self._write_evidence(user=user, state=state, decision=decision, verdict=verdict, attempt=attempt, now=now)
        if state.mode == core.MODE_TEST_OUT and state.finished:
            self._finish_test_out(user=user, session=session, state=state, now=now)
        _store_state(session, state)
        self.db.add(session)
        correction = dict(attempt.correction_payload or {})
        correction["forge"] = {
            "rung": int(rung),
            "rung_name": core.rung_name(rung),
            "new_rung": decision.new_rung,
            "counted": decision.counted,
            "schedule": decision.schedule,
        }
        attempt.correction_payload = correction
        flag_modified(attempt, "correction_payload")
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(session)
        return self.view(user=user, session=session)

    def amend_attempt(self, *, user: User, session: AtelierSession, attempt: AtelierAttempt) -> dict[str, Any]:
        """An asynchronous verdict landed (WP-S1): count a once-unchecked answer.

        Only an answer the forge recorded as unchecked is amended, once; the
        staircase has moved on, so only the evidence is written.
        """

        state = forge_state_of(session)
        if state is None or attempt.concept_id is None:
            return {}
        exercise_key = _exercise_key(attempt)
        entry = next((e for e in state.history if e.get("exercise_key") == exercise_key), None)
        verdict = verdict_from_attempt(attempt)
        if entry is None or entry.get("checked") or not verdict.checked or entry.get("amended"):
            return self.view(user=user, session=session)
        track = state.track(int(attempt.concept_id))
        rung = int(entry["rung"])
        evidence = core.evidence_for(rung, verdict)
        decision = core.EvidenceDecision(
            concept_id=int(attempt.concept_id), rung=rung, evidence=evidence, counted=evidence is not None,
            new_rung=track.rung if track else rung,
        )
        if evidence is not None and track is not None:
            if evidence.correct and rung not in track.scheduled_success_rungs:
                decision.schedule = True
                decision.weight_scale = core.MASSED_WEIGHT_DECAY ** len(track.scheduled_success_rungs)
                track.scheduled_success_rungs.append(rung)
            elif not evidence.correct and not track.scheduled_failure:
                decision.schedule = True
                track.scheduled_failure = True
        entry.update({"amended": True, "outcome": verdict.outcome, **decision.ledger(), "checked": True})
        self._write_evidence(user=user, state=state, decision=decision, verdict=verdict, attempt=attempt,
                             now=datetime.now(UTC), move_rung=False)
        _store_state(session, state)
        self.db.add(session)
        self.db.commit()
        return self.view(user=user, session=session)

    def _write_evidence(
        self,
        *,
        user: User,
        state: ForgeState,
        decision: core.EvidenceDecision,
        verdict: Verdict,
        attempt: AtelierAttempt,
        now: datetime,
        move_rung: bool = True,
    ) -> None:
        from app.services.atelier import atelier_calibration_adjustment
        from app.services.concept_life import note_concept_evidence
        from app.services.grammar import GrammarService, apply_grammar_evidence
        from app.services.journey_learning import journey_credited_today, record_drill_credit

        progress = GrammarService(self.db).get_or_create_progress(user_id=user.id, concept_id=decision.concept_id)
        if move_rung and state.mode == core.MODE_SEANCE:
            progress.forge_rung = int(decision.new_rung)
        evidence = decision.evidence
        if evidence is None:
            self.db.add(progress)
            return
        schedule = decision.schedule
        if schedule and evidence.correct and journey_credited_today(
            self.db, user=user, target_kind="grammar", target_id=str(decision.concept_id)
        ):
            # D-0: the journey moved this rule's schedule today already.
            schedule = False
        if schedule:
            _score, multiplier = atelier_calibration_adjustment(float(attempt.score_0_4 or 0.0), verdict.confidence)
            outcome_score = 10.0 if verdict.correct else 6.0 if verdict.partial else 0.0
            blended = round(0.7 * float(progress.score or 0.0) + 0.3 * outcome_score, 2)
            apply_grammar_evidence(
                progress,
                evidence,
                now=now,
                score=blended,
                interval_multiplier=multiplier,
                weight_scale=decision.weight_scale,
            )
            if evidence.correct:
                record_drill_credit(self.db, user=user, target_kind="grammar", target_id=str(decision.concept_id), now=now)
        else:
            note_concept_evidence(progress, evidence, now=now)
        self.db.add(progress)

    def _finish_test_out(self, *, user: User, session: AtelierSession, state: ForgeState, now: datetime) -> None:
        from app.services.grammar import GrammarService

        result = dict(state.result or {})
        concept_id = state.tracks[0].concept_id
        progress = GrammarService(self.db).get_or_create_progress(user_id=user.id, concept_id=concept_id)
        if progress.introduced_at is None:
            progress.introduced_at = now
        if result.get("passed"):
            progress.tested_out_at = now
            if progress.held_at is None:
                progress.held_at = now  # WP-L4 «Tenue», at once (owner, 2026-09-24)
            progress.forge_rung = int(core.TOP_RUNG)
        else:
            progress.forge_rung = int(result.get("placement_rung") or 0)
        self.db.add(progress)
        session.status = TEST_OUT_DONE_STATUS
        session.completed_at = now
        session.recap_payload = {"test_out": {**result, "concept_id": concept_id}}
        logger.info("Forge test-out finished", user_id=str(user.id), concept_id=concept_id, passed=result.get("passed"))

    # -- reading the forge ------------------------------------------------------

    def state_for_user(self, *, user: User, concept_ids: Iterable[int] | None = None) -> list[dict[str, Any]]:
        """Per rule: current rung, stage, next due, held / tested-out stamps."""

        from app.services.concept_life import concept_stage

        query = (
            self.db.query(UserGrammarProgress, GrammarConcept)
            .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
            .filter(UserGrammarProgress.user_id == user.id)
        )
        if concept_ids is not None:
            ids = [int(item) for item in concept_ids]
            query = query.filter(UserGrammarProgress.concept_id.in_(ids or [-1]))
        rows = []
        for progress, concept in query.order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc()).all():
            rung = initial_rung(progress)
            rows.append(
                {
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "title": concept.name,
                    "rung": rung,
                    "rung_name": core.rung_name(rung),
                    "forged": progress.forge_rung is not None,
                    "stage": concept_stage(progress),
                    "next_due": progress.next_review.isoformat() if progress.next_review else None,
                    "held_at": progress.held_at.isoformat() if progress.held_at else None,
                    "tested_out_at": progress.tested_out_at.isoformat() if progress.tested_out_at else None,
                }
            )
        return rows


def _pool_mode(attempt: AtelierAttempt) -> str:
    """The attempt's mode as the item pools name it (transform posts «rewrite»)."""

    round_name = str(attempt.round or "")
    if round_name == "recognize":
        return str(attempt.mode or "fill")
    if round_name == "transform":
        return "rewrite"
    return round_name


def _exercise_key(attempt: AtelierAttempt) -> str:
    return f"ex:{attempt.concept_id}:{attempt.round}:{attempt.mode}:{attempt.exercise_id}"


def _attempt_item_id(attempt: AtelierAttempt) -> str:
    answers = (attempt.answer_payload or {}).get("answers") if isinstance(attempt.answer_payload, dict) else None
    if isinstance(answers, dict) and answers:
        return str(next(iter(answers.keys())))
    prompt = attempt.prompt_payload if isinstance(attempt.prompt_payload, dict) else {}
    items = prompt.get("items") if isinstance(prompt.get("items"), list) else []
    if items and isinstance(items[0], dict) and items[0].get("id"):
        return str(items[0]["id"])
    return str(attempt.exercise_id or attempt.id)


def session_for_user(db: Session, *, user: User, session_id: UUID) -> AtelierSession | None:
    session = db.get(AtelierSession, session_id)
    if session is None or session.user_id != user.id:
        return None
    return session


__all__ = [
    "FORGE_KEY",
    "RUNG_POOLS",
    "TEST_OUT_DONE_STATUS",
    "TEST_OUT_STATUS",
    "Composer",
    "ForgeItem",
    "ForgeService",
    "ItemProvider",
    "PayloadItemProvider",
    "PickedUnit",
    "SelectTodayComposer",
    "fingerprint_for",
    "forge_state_of",
    "forge_units",
    "initial_rung",
    "is_forge_session",
    "rung_for_attempt",
    "verdict_from_attempt",
]
