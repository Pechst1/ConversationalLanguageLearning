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
  :class:`BankItemProvider`: the session's exercise set, topped up from the
  item bank when a rung runs dry (:class:`PayloadItemProvider` alone reads the
  set).
* :class:`Composer` (WP-S4 picker): ``pick(user, now=…)`` → a list of
  :class:`PickedUnit` ``(concept_id, role: today | due | contrast)``. Default:
  :class:`ForgePlanComposer`, WP-S4's one picker
  (:func:`app.services.forge_picker.forge_plan`), read back from the plan the
  séance start stored in ``quote_payload["forge"]``.
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
from app.services.forge_coaches import coach_for_concept, coach_mood

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
    """The grader's verdict, as the forge reads it (the WP-S1 seam).

    WP-S1's semantics, in order:

    * an explicit ``correction["checked"]`` wins (a test-out's local grade);
    * ``assessment_status``: ``checked`` — the key (recognise, transform) or a
      model that actually read the answer decided, so it counts at once;
      ``provisional`` — free production's instant local check, a hint until
      the relecture lands (then :meth:`ForgeService.amend_attempt` counts it,
      once); ``unavailable`` — nobody could read it, it never counts;
    * rows without a status (older clients): a placeholder verdict of a
      model-graded round is unchecked.
    """

    correction = attempt.correction_payload if isinstance(attempt.correction_payload, dict) else {}
    confidence = (attempt.answer_payload or {}).get("confidence") if isinstance(attempt.answer_payload, dict) else None
    explicit = correction.get("checked")
    status = correction.get("assessment_status")
    if isinstance(explicit, bool):
        checked = explicit
    elif status in {"provisional", "unavailable"} or correction.get("evidence_hold"):
        checked = False
    elif status == "checked":
        checked = attempt.verdict != "needs_review"
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
    local: str | None = None
    if not checked:
        local_check = correction.get("local_check") if isinstance(correction.get("local_check"), dict) else {}
        if local_check.get("detector") == "hit":
            local = core.OUTCOME_CORRECT
        elif local_check.get("detector") == "miss":
            local = core.OUTCOME_INCORRECT
    return Verdict(
        outcome=outcome,
        checked=checked,
        confidence=confidence if confidence in {"sure", "unsure"} else None,
        local=local,
    )


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

    def item_at(self, *, concept_id: int, rung: int, exclude: set[str]) -> ForgeItem | None:
        """An unused item of exactly this rung, or ``None``."""

        payload = self.payloads.get(int(concept_id))
        if not payload:
            return None
        rung = core.clamp_rung(rung)
        for round_name, mode in RUNG_POOLS[Rung(rung)]:
            for index, item in enumerate(_payload_items(payload, round_name, mode)):
                item_id = str(item.get("id") or f"{round_name}-{index}")
                fingerprint = fingerprint_for(concept_id, round_name, mode, item_id)
                if fingerprint in exclude:
                    continue
                return ForgeItem(
                    concept_id=int(concept_id),
                    rung=int(rung),
                    round=round_name,
                    mode=mode,
                    item_id=item_id,
                    item_index=index,
                    fingerprint=fingerprint,
                    payload=item,
                    answer_key=item.get("answer") or item.get("expected_answer") or item.get("correct_answer"),
                )
        return None

    def item_for(self, *, concept_id: int, rung: int, exclude: set[str]) -> ForgeItem | None:
        if not self.payloads.get(int(concept_id)):
            return None
        for candidate_rung in _rung_search_order(rung):
            item = self.item_at(concept_id=concept_id, rung=candidate_rung, exclude=exclude)
            if item is not None:
                return item
        return None


#: Session-owned copies of a shared exercise set (copy-on-write for a top-up).
FORGE_SESSION_SET_SOURCE = "forge_session"


def _sentence_fingerprints(payload: dict[str, Any]) -> set[str]:
    """Every exercise sentence a concept's set already holds (bank fingerprints)."""

    from app.services.item_bank import fingerprint as bank_fingerprint

    found: set[str] = set(((payload.get("forge") or {}).get("fingerprints") or []) if isinstance(payload.get("forge"), dict) else [])
    containers: list[list[dict[str, Any]]] = []
    for pools in RUNG_POOLS.values():
        for round_name, mode in pools:
            containers.append(_payload_items(payload, round_name, mode))
    containers.append(_payload_items(payload, "speak", "speak"))
    for items in containers:
        for item in items:
            if item.get("bank_fingerprint"):
                found.add(str(item["bank_fingerprint"]))
            for key in ("expected_answer", "example_answer"):
                if item.get(key):
                    found.add(bank_fingerprint(str(item[key])))
            if item.get("correct_answer") and len(str(item["correct_answer"]).split()) > 2:
                found.add(bank_fingerprint(str(item["correct_answer"])))
    return found


class BankItemProvider:
    """The forge's :class:`ItemProvider`: the session's set, topped up from the bank.

    A rule that needs another item at a rung when every item of that rung in
    the session's exercise set is used gets a fresh one from WP-S2's item bank
    (:mod:`app.services.item_bank`), generated in-process:

    * never a sentence the learner saw in the last seven days
      (``atelier_served_items``), never one already in this séance's set, never
      the rule card's own example; the new sentence is recorded as served;
    * the item is **appended to the concept's exercise set of this session**
      (``payload["forge"]["appended"]``), so the ordinary submit path finds it
      by its exercise id and grades it against its key. A set shared with other
      sessions (the curated fallback, a shared LLM set) is copied first
      (copy-on-write), the copy is seated on this session only.

    A concept without templates, or a rung the bank cannot pose, falls back to
    :class:`PayloadItemProvider` (the neighbouring rungs, then retirement).
    """

    #: Candidates tried per top-up before the rung gives up.
    MAX_CANDIDATES = 40

    def __init__(
        self,
        db: Session,
        *,
        user: User,
        session: AtelierSession,
        sets: dict[int, Any],
        concepts: dict[int, GrammarConcept],
    ) -> None:
        self.db = db
        self.user = user
        self.session = session
        self.sets = sets
        self.concepts = concepts
        self.payloads = PayloadItemProvider({cid: dict(item.payload or {}) for cid, item in sets.items()})
        self._story: frozenset[str] | None = None

    @property
    def story(self) -> frozenset[str]:
        """WP-S5: what the learner's story has lately been about (read once)."""

        if self._story is None:
            from app.services.forge_story import story_focus

            self._story = story_focus(self.db, self.user)
        return self._story

    @classmethod
    def for_session(cls, db: Session, *, user: User, session: AtelierSession) -> BankItemProvider:
        from app.services.atelier import AtelierExerciseGenerationError, session_exercise_set

        sets: dict[int, Any] = {}
        concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
        concepts = {c.id: c for c in db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids or [-1])).all()}
        for concept_id in concept_ids:
            concept = concepts.get(concept_id)
            if concept is None:
                continue
            try:
                sets[concept_id] = session_exercise_set(db, user=user, session=session, concept=concept, fast_path=True)
            except AtelierExerciseGenerationError:  # pragma: no cover - fallback always exists
                continue
        return cls(db, user=user, session=session, sets=sets, concepts=concepts)

    def item_for(self, *, concept_id: int, rung: int, exclude: set[str]) -> ForgeItem | None:
        concept_id = int(concept_id)
        item = self.payloads.item_at(concept_id=concept_id, rung=rung, exclude=exclude)
        if item is not None:
            return item
        try:
            topped = self.top_up(concept_id=concept_id, rung=int(core.clamp_rung(rung)))
        except Exception as exc:  # pragma: no cover - the bank never breaks a séance
            logger.warning("La Forge bank top-up failed", concept_id=concept_id, rung=rung, error=str(exc))
            self.db.rollback()
            topped = None
        if topped is not None and topped.fingerprint not in exclude:
            return topped
        return self.payloads.item_for(concept_id=concept_id, rung=rung, exclude=exclude)

    # -- the top-up ---------------------------------------------------------------

    def _build(self, rung: int, candidate: Any, *, concept: GrammarConcept, requirement: dict[str, Any], index: int):
        from app.services import item_bank

        lesson = concept.external_id
        if rung == Rung.RECOGNISE:
            return item_bank.fill_item(candidate, lesson_external_id=lesson)
        if rung == Rung.DISCRIMINATE:
            return item_bank.pair_item(candidate, lesson_external_id=lesson) or item_bank.classify_item(
                candidate, show_correct=index % 2 == 0, lesson_external_id=lesson
            )
        if rung == Rung.BUILD:
            return item_bank.word_bank_item(candidate, lesson_external_id=lesson)
        if rung == Rung.TRANSFORM:
            return item_bank.transform_item(candidate)
        if rung == Rung.PRODUCE:
            return item_bank.output_item(candidate, round_name="sentence", requirement=requirement)
        # WP-S5: free use is a two-line scene with the rule's coach; an item
        # that cannot be one (it names the coach, say) gives way to the next.
        return item_bank.output_item(
            candidate, round_name="conversation", requirement=requirement, coach=coach_for_concept(concept.external_id)
        )

    def _requirement(self, concept: GrammarConcept, payload: dict[str, Any]) -> dict[str, Any]:
        from app.services.atelier import _concept_label

        for round_name in ("sentence", "conversation", "speak"):
            for item in _payload_items(payload, round_name, round_name):
                requirements = item.get("requirements")
                if isinstance(requirements, list) and requirements and isinstance(requirements[0], dict):
                    return dict(requirements[0])
        return {"concept_id": concept.id, "external_id": concept.external_id, "label": _concept_label(concept), "target_count": 1}

    def _owned_set(self, concept: GrammarConcept, exercise_set: Any) -> Any:
        """This session's own copy of the set (copy-on-write for a shared one)."""

        from app.db.models.atelier import AtelierExerciseSet
        from app.services.atelier import (
            ATELIER_ITEM_BANK_SOURCE,
            _payload_hash,
            _store_session_exercise_set_id,
        )

        payload = dict(exercise_set.payload or {})
        forge = payload.get("forge") if isinstance(payload.get("forge"), dict) else {}
        owner = forge.get("owner_session_id")
        if owner == str(self.session.id) or (owner is None and exercise_set.source == ATELIER_ITEM_BANK_SOURCE):
            # Bank sets are built per séance (their hash carries the session).
            return exercise_set
        copy_payload = json_copy(payload)
        copy_payload["forge"] = {**dict(copy_payload.get("forge") or {}), "owner_session_id": str(self.session.id),
                                 "copied_from": str(exercise_set.id)}
        copy = AtelierExerciseSet(
            concept_id=exercise_set.concept_id,
            generator_version=exercise_set.generator_version,
            model=exercise_set.model,
            source=FORGE_SESSION_SET_SOURCE,
            content_hash=_payload_hash({"copied_from": str(exercise_set.id), "session_id": str(self.session.id)}),
            payload=copy_payload,
            validation_notes=f"La Forge: this séance's copy of set {exercise_set.id} (bank top-ups appended).",
        )
        self.db.add(copy)
        self.db.flush([copy])
        _store_session_exercise_set_id(self.session, concept, copy)
        self.db.add(self.session)
        return copy

    def top_up(self, *, concept_id: int, rung: int) -> ForgeItem | None:
        """Generate one more item of this rule at this rung and seat it in the set."""

        import random

        from app.services import item_bank
        from app.services.atelier import _record_served_items, served_fingerprints
        from app.services.grammar_units import examples as unit_examples

        concept = self.concepts.get(concept_id)
        exercise_set = self.sets.get(concept_id)
        if concept is None or exercise_set is None:
            return None
        units = item_bank.units_for_external_id(concept.external_id)
        if not units:
            return None
        payload = dict(exercise_set.payload or {})
        forge_meta = payload.get("forge") if isinstance(payload.get("forge"), dict) else {}
        appended = list(forge_meta.get("appended") or [])
        blocked = (
            served_fingerprints(self.db, self.user)
            | _sentence_fingerprints(payload)
            | item_bank._rule_card_sentences(payload, unit_examples(concept))
        )
        requirement = self._requirement(concept, payload)
        bank = item_bank.default_bank()
        seed = f"{self.user.id}:{self.session.id}:{concept_id}:topup:{len(appended)}:{rung}"
        order = units[len(appended) % len(units):] + units[: len(appended) % len(units)]
        built: dict[str, Any] | None = None
        chosen = None
        for unit in order:
            stream = bank.sample(
                unit,
                random.Random(f"{seed}:{unit}"),  # noqa: S311 - reproducible variety, not security
                exclude=blocked,
                detector=item_bank.unit_detector(unit),
                story=self.story,
            )
            for tries, candidate in enumerate(stream):
                if tries >= self.MAX_CANDIDATES:
                    break
                if candidate.fingerprint in blocked:
                    continue
                built = self._build(rung, candidate, concept=concept, requirement=requirement, index=len(appended))
                if built is not None:
                    chosen = candidate
                    break
            if built is not None:
                break
        if built is None or chosen is None:
            return None

        round_name, mode = RUNG_POOLS[Rung(rung)][0]
        owned = self._owned_set(concept, exercise_set)
        new_payload = json_copy(dict(owned.payload or {}))
        container = _payload_container(new_payload, round_name, mode)
        items = container.setdefault("items", [])
        items.append(built)
        meta = dict(new_payload.get("forge") or {})
        meta.setdefault("owner_session_id", str(self.session.id))
        meta["appended"] = [
            *list(meta.get("appended") or []),
            {"id": built["id"], "round": round_name, "mode": mode, "rung": int(rung), "fingerprint": chosen.fingerprint},
        ]
        meta["fingerprints"] = [*list(meta.get("fingerprints") or []), chosen.fingerprint]
        new_payload["forge"] = meta
        owned.payload = new_payload
        flag_modified(owned, "payload")
        self.db.add(owned)
        _record_served_items(self.db, user=self.user, session=self.session, fingerprints=[chosen.fingerprint], unit=chosen.unit)
        self.db.commit()
        self.sets[concept_id] = owned
        self.payloads.payloads[concept_id] = dict(new_payload)
        index = len(items) - 1
        return ForgeItem(
            concept_id=concept_id,
            rung=int(rung),
            round=round_name,
            mode=mode,
            item_id=str(built["id"]),
            item_index=index,
            fingerprint=fingerprint_for(concept_id, round_name, mode, str(built["id"])),
            payload=built,
            answer_key=built.get("expected_answer") or built.get("correct_answer") or built.get("example_answer"),
        )


def json_copy(value: Any) -> Any:
    import json

    return json.loads(json.dumps(value))


def _payload_container(payload: dict[str, Any], round_name: str, mode: str) -> dict[str, Any]:
    """The dict whose ``items`` hold this round/mode's items (created if missing)."""

    if round_name == "recognize":
        recognize = payload.setdefault("recognize", {})
        return recognize.setdefault(mode, {"items": []})
    if round_name == "transform":
        return payload.setdefault("transform", {"items": []})
    ladder = payload.setdefault("output_ladder", {})
    return ladder.setdefault(round_name, {"items": []})


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


#: The keys of WP-S4's plan payload (``ForgePlan.as_payload()`` + the start's
#: ``origin`` / ``journey_step_id``). They share ``quote_payload["forge"]`` with
#: the engine's state (:meth:`ForgeState.to_dict`) — one source of truth for the
#: séance's rules; no key of one names a key of the other.
PLAN_KEYS = ("units", "budget_seconds", "reason", "rhythm", "new_concept_id", "origin", "journey_step_id")


def _plan_payload_of(session: AtelierSession) -> dict[str, Any]:
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    raw = quote.get(FORGE_KEY) if isinstance(quote, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in PLAN_KEYS if key in raw}


class ForgePlanComposer:
    """The :class:`Composer`: WP-S4's one picker (:func:`forge_picker.forge_plan`).

    A séance started through ``POST /atelier/sessions`` already carries the
    plan the start seated (``quote_payload["forge"]``); the composer reads it
    back so the start and the engine can never disagree. A session without one
    (a pregenerated «prepared» row, a service caller) gets a fresh plan, which
    is then stored on the session by :meth:`ForgeService.attach`.
    """

    def __init__(
        self,
        db: Session,
        *,
        plan: dict[str, Any] | None = None,
        preferred_concept_id: int | None = None,
        budget_seconds: int | None = None,
    ) -> None:
        self.db = db
        self.plan = dict(plan) if isinstance(plan, dict) and plan.get("units") is not None else None
        self.preferred_concept_id = preferred_concept_id
        self.budget_seconds = budget_seconds

    def pick(self, user: User, *, now: datetime) -> list[PickedUnit]:
        if self.plan is None:
            from app.services.forge_picker import forge_plan

            fresh = forge_plan(
                self.db,
                user,
                now,
                preferred_concept_id=self.preferred_concept_id,
                budget_seconds=self.budget_seconds,
            )
            self.plan = fresh.as_payload()
        units: list[PickedUnit] = []
        for unit in self.plan.get("units") or []:
            if not isinstance(unit, dict) or unit.get("concept_id") is None:
                continue
            role = str(unit.get("role") or Role.DUE.value)
            if role not in {Role.TODAY.value, Role.DUE.value, Role.CONTRAST.value}:
                role = Role.DUE.value
            units.append(PickedUnit(int(unit["concept_id"]), role))
        return units

    @property
    def budget(self) -> int | None:
        value = (self.plan or {}).get("budget_seconds")
        return int(value) if isinstance(value, (int, float)) and value > 0 else None


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


def forge_state_of(session: AtelierSession) -> ForgeState | None:
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    raw = quote.get(FORGE_KEY) if isinstance(quote, dict) else None
    return ForgeState.from_dict(raw) if isinstance(raw, dict) and raw.get("tracks") is not None else None


def is_forge_session(session: AtelierSession) -> bool:
    return forge_state_of(session) is not None


def _store_state(session: AtelierSession, state: ForgeState, *, plan: dict[str, Any] | None = None) -> None:
    """Write the engine's state next to the picker's plan (never over it)."""

    quote = dict(session.quote_payload or {})
    merged = {**_plan_payload_of(session), **(plan or {})}
    quote[FORGE_KEY] = {**merged, **state.to_dict()}
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
        """Compose a séance onto a fresh session (no attempts yet).

        The rules come from WP-S4's one picker: the plan the start stored in
        ``quote_payload["forge"]`` (or a fresh one); its ``budget_seconds`` is
        the séance's length (the fold's share of the day, or the rhythm's).
        """

        now = now or datetime.now(UTC)
        quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
        plan = _plan_payload_of(session)
        if composer is None:
            composer = ForgePlanComposer(
                self.db,
                plan=plan or None,
                preferred_concept_id=quote.get("forge_today_concept_id"),
            )
        picked = composer.pick(user, now=now)
        if isinstance(composer, ForgePlanComposer) and composer.plan is not None:
            plan = {**composer.plan, **{key: value for key, value in plan.items() if key in {"origin", "journey_step_id"}}}
        if keep_concepts:
            wanted = [int(cid) for cid in (session.selected_concept_ids or [])]
            by_id = {unit.concept_id: unit for unit in picked}
            picked = [by_id.get(cid) or PickedUnit(cid, Role.TODAY.value if i == 0 else Role.DUE.value)
                      for i, cid in enumerate(wanted)]
            # The plan on the session names what was seated: the learner's list.
            plan = {
                **plan,
                "units": [{"concept_id": unit.concept_id, "role": unit.role, "reason": "chosen"} for unit in picked],
                "reason": "chosen",
            }
        units = forge_units(self.db, user, picked, now=now)
        if keep_concepts:
            # The learner chose these rules: keep every one of them.
            units = [ForgeUnit(u.concept_id, u.role, u.rung, is_new=False, needs_spaced=u.needs_spaced) for u in units]
        budget = plan.get("budget_seconds") if isinstance(plan.get("budget_seconds"), (int, float)) else None
        length = core.seance_length(budget or seance_budget_seconds(user), seconds_per_item(self.db, user))
        state = ForgeState.seance(units, length=length)
        concept_ids = [track.concept_id for track in state.tracks]
        if concept_ids:
            session.selected_concept_ids = concept_ids
            quote = dict(session.quote_payload or {})
            quote["concept_roles"] = {
                str(track.concept_id): _FORGE_ROLE_TO_LEGACY.get(track.role, "fragile") for track in state.tracks
            }
            session.quote_payload = quote
            plan = {**plan, "stages_at_start": self._stages_of(user, concept_ids)}
        _store_state(session, state, plan=plan)
        self.db.add(session)
        return state

    def _stages_of(self, user: User, concept_ids: list[int]) -> dict[str, str]:
        """WP-S6: each rule's life stage when the séance starts, so the recap can
        say what changed today (introduced → practising → held)."""

        from app.services.concept_life import concept_stage

        rows = {
            progress.concept_id: progress
            for progress in self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id.in_(concept_ids or [-1]))
            .all()
        }
        return {str(cid): concept_stage(rows.get(cid)) for cid in concept_ids}

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
        from app.services.pilot_events import PilotEventService

        PilotEventService(self.db).record(
            "forge_test_out_started",
            user_id=user.id,
            entity_type="grammar_concept",
            entity_id=concept.id,
            payload={"concept_id": concept.id, "external_id": concept.external_id},
        )
        self.db.commit()
        self.db.refresh(session)
        return session

    # -- serving --------------------------------------------------------------

    def coach_for(self, concept_id: int) -> dict[str, Any] | None:
        """WP-S5: the rule's coach (cached per service)."""

        cache = self.__dict__.setdefault("_coaches", {})
        if concept_id not in cache:
            concept = self.db.get(GrammarConcept, int(concept_id))
            cache[concept_id] = coach_for_concept(concept.external_id) if concept is not None else None
        return cache[concept_id]

    def provider(self, *, user: User, session: AtelierSession) -> ItemProvider:
        return self._item_provider or BankItemProvider.for_session(self.db, user=user, session=session)

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
                    # The item itself: a bank top-up is not in the exercise
                    # set the client loaded at the start.
                    "item": dict(item.payload or {}),
                    # WP-S5: who teaches this rule.
                    "coach": self.coach_for(slot.concept_id),
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
        combo, best_combo = core.combo_runs(state.history)
        return {
            "mode": state.mode,
            "length": state.length,
            "answered": state.position,
            "counted": state.counted_items,
            "finished": state.finished,
            "next": upcoming,
            "result": state.result,
            # WP-S7: the run of checked right answers (S1 semantics: an unchecked
            # or provisional answer neither extends nor breaks it) and the flags
            # the page reads, so the owner can switch each feature off.
            "combo": {"run": combo, "best": best_combo},
            "features": forge_features(),
            "rules": [
                {
                    "concept_id": track.concept_id,
                    "role": track.role,
                    "rung": track.rung,
                    "rung_name": core.rung_name(track.rung),
                    "served": track.served,
                    "topped": track.topped,
                    "coach": self.coach_for(track.concept_id),
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
        held = self._write_evidence(user=user, state=state, decision=decision, verdict=verdict, attempt=attempt, now=now)
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
            # WP-S5: the rule's coach, and the face they make at this answer.
            "held": held,
            "coach": self.coach_for(int(attempt.concept_id)),
            "coach_mood": coach_mood(correct=verdict.correct, checked=verdict.checked, held=held),
        }
        attempt.correction_payload = correction
        flag_modified(attempt, "correction_payload")
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(session)
        return self.view(user=user, session=session)

    def amend_attempt(
        self, *, user: User, session: AtelierSession, attempt: AtelierAttempt, commit: bool = True
    ) -> dict[str, Any]:
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
            return self.view(user=user, session=session) if commit else {}
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
        if not commit:
            return {"amended": True, "counted": decision.counted, "schedule": decision.schedule}
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
    ) -> bool:
        """Write one answer's evidence; ``True`` when it made the rule held (WP-S5: the coach is moved)."""

        from app.services.atelier import atelier_calibration_adjustment
        from app.services.concept_life import note_concept_evidence
        from app.services.grammar import GrammarService, apply_grammar_evidence
        from app.services.journey_learning import journey_credited_today, record_drill_credit

        progress = GrammarService(self.db).get_or_create_progress(user_id=user.id, concept_id=decision.concept_id)
        was_held = getattr(progress, "held_at", None) is not None
        if move_rung and state.mode == core.MODE_SEANCE:
            progress.forge_rung = int(decision.new_rung)
        evidence = decision.evidence
        if evidence is None:
            self.db.add(progress)
            return False
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
        return not was_held and getattr(progress, "held_at", None) is not None

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
        if result.get("passed"):
            # WP-S7: a rare token for a rule tested out (once per rule), tied to
            # mastery, never to volume.
            token = mint_test_out_token(self.db, user=user, concept_id=concept_id, now=now)
            if token is not None:
                result["token"] = token
                state.result = dict(result)
        session.status = TEST_OUT_DONE_STATUS
        session.completed_at = now
        session.recap_payload = {"test_out": {**result, "concept_id": concept_id}}
        from app.services.pilot_events import PilotEventService

        PilotEventService(self.db).record(
            "forge_test_out_finished",
            user_id=user.id,
            entity_type="grammar_concept",
            entity_id=concept_id,
            payload={
                "concept_id": concept_id,
                "passed": bool(result.get("passed")),
                "correct": result.get("correct"),
                "total": result.get("total"),
                "placement_rung": result.get("placement_rung"),
            },
        )
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


def forge_features() -> dict[str, bool]:
    """WP-S7's switches, as the page reads them (each on by default)."""

    from app.config import settings

    return {
        "combo": bool(getattr(settings, "ATELIER_FORGE_COMBO_ENABLED", True)),
        "eclair": bool(getattr(settings, "ATELIER_ECLAIR_ENABLED", True)),
        "grammar_map": bool(getattr(settings, "ATELIER_GRAMMAR_MAP_ENABLED", True)),
        "mastery_rewards": bool(getattr(settings, "ATELIER_MASTERY_REWARDS_ENABLED", True)),
    }


#: WP-S7: the rare token's source (a new source for the existing logo token,
#: as the daily journey's keepsake is — not a new collectible kind).
TEST_OUT_TOKEN_SOURCE_KIND = "test_out"


def mint_test_out_token(db: Session, *, user: User, concept_id: int, now: datetime) -> dict[str, Any] | None:
    """Mint the rare token for a passed test-out, once per rule. Never commits."""

    if not forge_features()["mastery_rewards"]:
        return None
    from app.services.atelier_rewards import LOGO_TOKEN, AtelierRewardService

    concept = db.get(GrammarConcept, int(concept_id))
    item, created = AtelierRewardService(db)._mint(
        user_id=user.id,
        kind=LOGO_TOKEN,
        source_kind=TEST_OUT_TOKEN_SOURCE_KIND,
        source_ref=str(int(concept_id)),
        metadata={
            "name": "Rule token",
            "rare": True,
            "concept_id": int(concept_id),
            "external_id": getattr(concept, "external_id", None),
            "date": now.date().isoformat(),
        },
        commit=False,
    )
    if not created:
        return None
    return {
        "id": str(item.id),
        "kind": item.kind,
        "source_kind": item.source_kind,
        "concept_id": int(concept_id),
        "rare": True,
    }


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
    "PLAN_KEYS",
    "PickedUnit",
    "ForgePlanComposer",
    "BankItemProvider",
    "fingerprint_for",
    "forge_features",
    "forge_state_of",
    "mint_test_out_token",
    "forge_units",
    "initial_rung",
    "is_forge_session",
    "rung_for_attempt",
    "verdict_from_attempt",
]
