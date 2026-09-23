"""Unified learner error memory and scheduling service."""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.error_concepts import get_concept_for_category, get_concept_for_pattern
from app.core.srs.schedule import ScheduleState, schedule_next
from app.db.models.atelier import AtelierAttempt
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.grammar import GrammarConcept
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.grammar_feedback import infer_grammar_profile, profile_search_terms
from app.services.learner_copy import learner_text
from app.services.progress import ProgressService


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize(value)).strip("_") or "unknown"


def _normalize_review_answer(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize(value)).strip()


#: Words whose swap, insertion or removal is a determiner choice (WP-L1): a
#: correction that changes only these is about articles and determiners.
_DETERMINER_TOKENS = frozenset(
    {
        "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux",
        "ce", "cet", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
        "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs",
    }
)


#: WP-24 lifecycle. Three states, and every legacy label folds onto one of them.
#:
#: ``open``       recorded, never repaired since it was last made.
#: ``repairing``  repaired at least once, not yet proven; a recurrence lands here.
#: ``mastered``   MASTERY_REQUIRED_REPAIRS spaced correct repairs, no recurrence
#:                in between. The only state that leaves the errata queue.
ERROR_STATE_OPEN = "open"
ERROR_STATE_REPAIRING = "repairing"
ERROR_STATE_MASTERED = "mastered"
ERROR_STATES = (ERROR_STATE_OPEN, ERROR_STATE_REPAIRING, ERROR_STATE_MASTERED)

#: Rows written before WP-24 carry the FSRS-ish vocabulary. They are read, not
#: rewritten: a migration relabels what exists and this map covers anything that
#: escaped it (a replica lagging, a fixture, a row a rollback restored).
_LEGACY_STATES = {
    "new": ERROR_STATE_OPEN,
    "learning": ERROR_STATE_OPEN,
    "relearning": ERROR_STATE_REPAIRING,
    # "review" is a *scheduled* row, not a proven one. Mapping it to mastered
    # would retire errata the learner never repaired.
    "review": ERROR_STATE_REPAIRING,
}

#: Spaced correct repairs required before an erratum is retired. Spaced means
#: on distinct days: three repairs in one sitting prove recall, not retention.
MASTERY_REQUIRED_REPAIRS = 3


def normalize_error_state(value: Any) -> str:
    """The lifecycle state of a row, whichever vocabulary it was written in."""

    text = str(value or "").strip().lower()
    if text in ERROR_STATES:
        return text
    return _LEGACY_STATES.get(text, ERROR_STATE_OPEN)


def _severity_to_int(value: Any) -> int:
    if isinstance(value, int):
        return max(1, min(4, value))
    text = str(value or "").lower()
    if text in {"critical", "high", "severe"}:
        return 4
    if text in {"medium", "moderate"}:
        return 3
    if text in {"low", "minor"}:
        return 2
    return 2


class ErrorMemoryService:
    """Persist, deduplicate, schedule, and retrieve learner mistakes across modes."""

    # Publication French, and every source_type the repair card can carry — an
    # unmapped key used to print raw ("pilot_capture") straight onto the page.
    SOURCE_LABELS = {
        "atelier": "Atelier",
        "audio": "Le studio",
        "conversation": "Conversation",
        "story": "Le feuilleton",
        "serial": "Le feuilleton",
        "feuilleton": "Le feuilleton",
        "brief_exercise": "Exercice",
        "mission": "Le courrier",
        "pilot_capture": "Capture pilote",
        "graphic_novel": "Le roman-photo",
        "vocabulary": "Le lexique",
        "daily_journey": "La séance du jour",
    }

    REVIEW_MODE_COPY: dict[str, dict[str, str]] = {
        "grammar": {
            "label": "Grammaire",
            "instruction": "Réécrivez la forme correcte de mémoire.",
            "prompt": "Reprenez cette faute de grammaire :",
            "placeholder": "La phrase corrigée",
        },
        "vocabulary": {
            "label": "Lexique",
            "instruction": "Écrivez le mot ou l’expression correcte de mémoire.",
            "prompt": "Reprenez ce choix de mot :",
            "placeholder": "Le mot correct",
        },
        "spelling": {
            "label": "Orthographe",
            "instruction": "Réécrivez la forme correcte, accents compris.",
            "prompt": "Reprenez cette orthographe :",
            "placeholder": "L’orthographe correcte",
        },
        "speaking": {
            "label": "À l’oral",
            "instruction": "Tapez la phrase que vous diriez ; la relecture porte sur la langue.",
            "prompt": "Reprenez cette phrase parlée :",
            "placeholder": "La phrase à dire",
        },
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def due_error_records(self, user: User, *, limit: int = 20, review_modes: set[str] | None = None) -> list[UserError]:
        now = datetime.now(UTC)
        query = (
            self.db.query(UserError)
            .filter(
                UserError.user_id == user.id,
                # NULL-safe: `state != 'mastered'` alone drops every row whose
                # state was never written, which is most of the legacy table.
                or_(UserError.state.is_(None), UserError.state != ERROR_STATE_MASTERED),
            )
            .filter((UserError.next_review_date.is_(None)) | (UserError.next_review_date <= now))
            # A row without a stored correction has no target answer: it can never
            # be graded right, so it must never come up for repair (legacy rows
            # from the first corrector hold only an explanation).
            .filter(UserError.correction.isnot(None), func.trim(UserError.correction) != "")
        )
        if review_modes:
            query = query.filter(UserError.review_mode.in_(review_modes))
        return (
            query.order_by(
                UserError.lapses.desc(),
                UserError.occurrences.desc(),
                UserError.next_review_date.asc().nullsfirst(),
            )
            .limit(limit)
            .all()
        )

    def due_errata(self, user: User, *, limit: int = 20, review_modes: set[str] | None = None) -> list[dict[str, Any]]:
        return [serialize_error_memory(row) for row in self.due_error_records(user, limit=limit, review_modes=review_modes)]

    def record_atelier_attempt(
        self,
        *,
        user: User,
        attempt: AtelierAttempt,
        merge_same_attempt: bool = False,
    ) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        correction = attempt.correction_payload or {}
        for index, erratum in enumerate(correction.get("errata") or []):
            update = self.record_erratum(
                user=user,
                erratum=erratum,
                source_type="atelier",
                source_attempt_id=attempt.id,
                concept_id=erratum.get("concept_id") or attempt.concept_id,
                source_payload={
                    "round": attempt.round,
                    "mode": attempt.mode,
                    "exercise_id": attempt.exercise_id,
                    "erratum_index": index,
                },
                merge_same_attempt=merge_same_attempt,
            )
            if update:
                update["erratum_index"] = index
                updates.append(update)
        return updates

    def record_detected_error(
        self,
        *,
        user: User,
        detected_error: Any,
        source_type: str,
        session: LearningSession | UUID | None = None,
        message: ConversationMessage | UUID | None = None,
        source_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if float(getattr(detected_error, "confidence", 0) or 0) < 0.6:
            return None
        code = str(getattr(detected_error, "subcategory", None) or getattr(detected_error, "code", "") or "language_error")
        category = str(getattr(detected_error, "category", None) or "grammar").lower()
        concept_id = self._infer_grammar_concept_id(code=code, category=category)
        # Explanations follow the learner's own language; the French chrome around
        # them does not (docs/design-overhaul-2026-08-31.md §Principles).
        language = getattr(user, "native_language", None)
        erratum = {
            "display_label": self._display_label_for(code=code, category=category, language=language),
            "learner_text": getattr(detected_error, "span", "") or "",
            "corrected_target": getattr(detected_error, "suggestion", "") or "",
            "why_wrong": self._direct_feedback(
                getattr(detected_error, "message", "")
                or learner_text("erratum.form_needs_review", language)
            ),
            "repair_hint": self._repair_hint_for(
                code=code,
                suggestion=getattr(detected_error, "suggestion", ""),
                language=language,
            ),
            "severity": _severity_to_int(getattr(detected_error, "severity", None)),
            "recurring": True,
            "task_error_type": code,
            "concept_id": concept_id,
            "external_id": None,
        }
        session_id = session.id if hasattr(session, "id") else session
        message_id = message.id if hasattr(message, "id") else message
        return self.record_erratum(
            user=user,
            erratum=erratum,
            source_type=source_type,
            learning_session_id=session_id,
            message_id=message_id,
            concept_id=concept_id,
            source_payload=source_payload,
        )

    def record_erratum(
        self,
        *,
        user: User,
        erratum: dict[str, Any],
        source_type: str,
        concept_id: int | None = None,
        source_attempt_id: UUID | None = None,
        learning_session_id: UUID | None = None,
        message_id: UUID | None = None,
        source_payload: dict[str, Any] | None = None,
        merge_same_attempt: bool = False,
    ) -> dict[str, Any] | None:
        if erratum.get("task_error_type") == "task_compliance" and not erratum.get("recurring"):
            return None

        concept_id = concept_id or erratum.get("concept_id")
        task_type = str(erratum.get("task_error_type") or "grammar_target")
        display_label = str(
            erratum.get("display_label")
            or self._display_label_for(
                code=task_type,
                category="grammar",
                language=getattr(user, "native_language", None),
            )
        )[:120]
        category = self._error_category_for_erratum(erratum)
        review_mode = self._review_mode_for(category=category, task_type=task_type, source_type=source_type)
        severity = _severity_to_int(erratum.get("severity"))
        linked_word = self._link_vocabulary_if_needed(user=user, category=category, erratum=erratum)
        memory_key = self._memory_key(
            category=category,
            task_type=task_type,
            display_label=display_label,
            concept_id=concept_id,
            linked_word_id=linked_word.id if linked_word else None,
        )

        if source_attempt_id:
            already_recorded = (
                self.db.query(UserError)
                .filter(
                    UserError.user_id == user.id,
                    UserError.source_attempt_id == source_attempt_id,
                    UserError.memory_key == memory_key,
                )
                .first()
            )
            if already_recorded:
                if merge_same_attempt:
                    self._merge_same_attempt_erratum(
                        already_recorded,
                        erratum=erratum,
                        concept_id=concept_id,
                        source_type=source_type,
                        category=category,
                        task_type=task_type,
                        display_label=display_label,
                        review_mode=review_mode,
                        memory_key=memory_key,
                        linked_word_id=linked_word.id if linked_word else None,
                        metadata={
                            "severity": severity,
                            "external_id": erratum.get("external_id"),
                            "source_payload": source_payload or {},
                        },
                    )
                    return self._serialize_update(already_recorded, action="refined")
                return self._serialize_update(already_recorded, action="already_recorded")

        existing = (
            self.db.query(UserError)
            .filter(UserError.user_id == user.id, UserError.memory_key == memory_key)
            .first()
        )
        if existing is None and concept_id:
            # WP-L1: journey errata used to be keyed without a concept. The same
            # mistake, now recognised as a concept's, reopens that row (and
            # adopts the concept, keeping its key) instead of starting a second
            # one beside it.
            legacy_key = self._memory_key(
                category=category,
                task_type=task_type,
                display_label=display_label,
                concept_id=None,
                linked_word_id=linked_word.id if linked_word else None,
            )
            existing = (
                self.db.query(UserError)
                .filter(UserError.user_id == user.id, UserError.memory_key == legacy_key)
                .first()
            )
            if existing is not None:
                memory_key = legacy_key
        now = datetime.now(UTC)
        next_review = self._next_review(now=now, severity=severity, repeated=bool(existing), source_type=source_type)
        metadata = {
            "severity": severity,
            "external_id": erratum.get("external_id"),
            "source_payload": source_payload or {},
        }
        if existing:
            existing.occurrences = (existing.occurrences or 1) + 1
            existing.lapses = (existing.lapses or 0) + 1
            existing.original_text = erratum.get("learner_text")
            existing.correction = erratum.get("corrected_target")
            existing.context_snippet = erratum.get("why_wrong")
            existing.why_wrong = erratum.get("why_wrong")
            existing.repair_hint = erratum.get("repair_hint")
            existing.concept_id = concept_id or existing.concept_id
            existing.source_attempt_id = source_attempt_id or existing.source_attempt_id
            existing.session_id = learning_session_id or existing.session_id
            existing.message_id = message_id or existing.message_id
            existing.error_category = category
            existing.error_pattern = task_type
            existing.subcategory = erratum.get("external_id") or task_type
            existing.display_label = display_label
            existing.task_error_type = task_type
            existing.source_type = source_type
            existing.review_mode = review_mode
            existing.memory_key = memory_key
            existing.linked_word_id = linked_word.id if linked_word else existing.linked_word_id
            existing.error_metadata = metadata
            existing.next_review_date = next_review
            # A recurrence reopens the erratum, whatever it had reached. The
            # mastery evidence is destroyed rather than paused: three spaced
            # repairs that were followed by the same mistake did not prove it.
            existing.state = ERROR_STATE_REPAIRING
            existing.mastery_streak = 0
            existing.mastered_at = None
            existing.ease_factor = max(1.3, float(existing.ease_factor or 2.5) - 0.2)
            existing.difficulty = min(10.0, (existing.difficulty or 5.0) + 0.4)
            existing.updated_at = now
            self._update_error_concept(user=user, task_type=task_type, category=category)
            return self._serialize_update(existing, action="repeated")

        record = UserError(
            user_id=user.id,
            session_id=learning_session_id,
            message_id=message_id,
            concept_id=concept_id,
            source_attempt_id=source_attempt_id,
            error_category=category,
            error_pattern=task_type,
            subcategory=erratum.get("external_id") or task_type,
            original_text=erratum.get("learner_text"),
            correction=erratum.get("corrected_target"),
            context_snippet=erratum.get("why_wrong"),
            why_wrong=erratum.get("why_wrong"),
            repair_hint=erratum.get("repair_hint"),
            display_label=display_label,
            task_error_type=task_type,
            source_type=source_type,
            review_mode=review_mode,
            memory_key=memory_key,
            linked_word_id=linked_word.id if linked_word else None,
            error_metadata=metadata,
            next_review_date=next_review,
            state=ERROR_STATE_OPEN,
            mastery_streak=0,
            ease_factor=2.5,
        )
        self.db.add(record)
        self.db.flush([record])
        self._update_error_concept(user=user, task_type=task_type, category=category)
        return self._serialize_update(record, action="created")

    def _merge_same_attempt_erratum(
        self,
        error: UserError,
        *,
        erratum: dict[str, Any],
        concept_id: int | None,
        source_type: str,
        category: str,
        task_type: str,
        display_label: str,
        review_mode: str,
        memory_key: str,
        linked_word_id: int | None,
        metadata: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC)
        error.original_text = erratum.get("learner_text")
        error.correction = erratum.get("corrected_target")
        error.context_snippet = erratum.get("why_wrong")
        error.why_wrong = erratum.get("why_wrong")
        error.repair_hint = erratum.get("repair_hint")
        error.concept_id = concept_id or error.concept_id
        error.error_category = category
        error.error_pattern = task_type
        error.subcategory = erratum.get("external_id") or task_type
        error.display_label = display_label
        error.task_error_type = task_type
        error.source_type = source_type
        error.review_mode = review_mode
        error.memory_key = memory_key
        error.linked_word_id = linked_word_id or error.linked_word_id
        error.error_metadata = metadata
        error.updated_at = now
        self.db.add(error)

    def review_error(
        self,
        *,
        user: User,
        error_id: UUID,
        rating: int,
        repaired: bool,
        now: datetime | None = None,
    ) -> UserError | None:
        """Grade one repair, schedule the next one, and retire the erratum if it is done.

        Replaces the old two-branch day table (7 or 14 days on success, 1 on
        failure, forever) with the shared SM-2 scheduler and the mastery exit:

        * a correct repair on a **new day** advances ``mastery_streak``;
        * a second correct repair on the **same day** re-schedules but does not
          advance it — retention is measured across nights, not sittings;
        * ``MASTERY_REQUIRED_REPAIRS`` advances retire the row (``mastered``),
          which is the only state ``due_error_records`` refuses to hand back;
        * anything else puts the row in ``repairing`` and resets the streak.
        """

        error = self.db.query(UserError).filter(UserError.id == error_id, UserError.user_id == user.id).first()
        if not error:
            return None
        now = now or datetime.now(UTC)
        succeeded = bool(repaired) and int(rating) >= 3
        decision = schedule_next(
            now=now,
            quality=max(0, min(4, int(rating))),
            state=ScheduleState(
                reps=int(error.reps or 0),
                lapses=int(error.lapses or 0),
                interval_days=int(error.scheduled_days or 0),
                ease_factor=float(error.ease_factor or 2.5),
                phase="review" if normalize_error_state(error.state) != ERROR_STATE_OPEN else "new",
            ),
            min_interval_days=1,
        )
        error.ease_factor = decision.ease_factor
        error.scheduled_days = decision.interval_days
        error.elapsed_days = self._elapsed_days(error, now)

        if succeeded:
            spaced = self._is_new_day(error.last_correct_date, now)
            if spaced:
                error.mastery_streak = int(error.mastery_streak or 0) + 1
            error.last_correct_date = now
            if int(error.mastery_streak or 0) >= MASTERY_REQUIRED_REPAIRS:
                error.state = ERROR_STATE_MASTERED
                error.mastered_at = now
            else:
                error.state = ERROR_STATE_REPAIRING
                error.mastered_at = None
        else:
            error.state = ERROR_STATE_REPAIRING
            error.mastery_streak = 0
            error.mastered_at = None

        error.mark_review(now, decision.due_at, rating)
        error.updated_at = now
        self.db.add(error)
        return error

    @staticmethod
    def _is_new_day(previous: datetime | None, now: datetime) -> bool:
        """Is this repair on a later day than the last accepted one?"""

        if previous is None:
            return True
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=UTC)
        return previous.astimezone(UTC).date() < now.astimezone(UTC).date()

    @staticmethod
    def _elapsed_days(error: UserError, now: datetime) -> int:
        last = error.last_review_date
        if last is None:
            return 0
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return max(0, (now.astimezone(UTC) - last.astimezone(UTC)).days)

    def build_review_task(self, *, user: User, error_id: UUID) -> dict[str, Any] | None:
        error = self.db.query(UserError).filter(UserError.id == error_id, UserError.user_id == user.id).first()
        if not error:
            return None
        return self._review_task_payload(error)

    def submit_review_attempt(
        self,
        *,
        user: User,
        error_id: UUID,
        answer_text: str,
    ) -> dict[str, Any] | None:
        error = self.db.query(UserError).filter(UserError.id == error_id, UserError.user_id == user.id).first()
        if not error:
            return None

        target = str(error.correction or "").strip()
        answer = str(answer_text or "").strip()
        answer_norm = _normalize_review_answer(answer)
        target_norm = _normalize_review_answer(target)
        is_correct = bool(answer_norm and target_norm) and (
            answer_norm == target_norm or (len(target_norm.split()) >= 2 and target_norm in answer_norm)
        )
        score = 4 if is_correct else (2 if answer_norm else 1)
        reviewed = self.review_error(user=user, error_id=error.id, rating=score, repaired=is_correct)
        if not reviewed:
            return None

        metadata = dict(reviewed.error_metadata or {})
        attempts = list(metadata.get("review_attempts") or [])
        submitted_at = datetime.now(UTC)
        attempts.append(
            {
                "submitted_at": submitted_at.isoformat(),
                "answer_text": answer,
                "target_answer": target,
                "verdict": "repaired" if is_correct else "needs_repair",
                "score_0_4": score,
            }
        )
        metadata["review_attempts"] = attempts[-20:]
        metadata["last_review_task"] = self._review_task_payload(reviewed)
        closure = None
        if is_correct:
            mastered = normalize_error_state(reviewed.state) == ERROR_STATE_MASTERED
            closure = {
                # Publication French, sentence case: the card prints it verbatim.
                "label": "Corrigé · acquis" if mastered else "Corrigé · classé",
                "detail": (
                    "Trois reprises justes, à des jours différents : cet erratum "
                    "quitte le relevé."
                    if mastered
                    else "Cet erratum quitte le jour et revient à sa prochaine date de contrôle."
                ),
                "filed_at": submitted_at.isoformat(),
                "next_review_date": reviewed.next_review_date.isoformat() if reviewed.next_review_date else None,
                "state": normalize_error_state(reviewed.state),
                "mastered": mastered,
                "mastery_streak": int(reviewed.mastery_streak or 0),
                "mastery_target": MASTERY_REQUIRED_REPAIRS,
            }
            closure_events = list(metadata.get("closure_events") or [])
            closure_events.append(closure)
            metadata["closure_events"] = closure_events[-20:]
            metadata["last_closure"] = closure
        reviewed.error_metadata = metadata
        flag_modified(reviewed, "error_metadata")
        self.db.add(reviewed)
        return {
            "verdict": "repaired" if is_correct else "needs_repair",
            "score_0_4": score,
            "is_correct": is_correct,
            "answer_text": answer,
            "target_answer": target,
            "feedback": self._review_feedback(reviewed, is_correct=is_correct),
            "closure": closure,
            "erratum": serialize_error_memory(reviewed),
            "task": self._review_task_payload(reviewed),
        }

    def _serialize_update(self, error: UserError, *, action: str) -> dict[str, Any]:
        payload = serialize_error_memory(error)
        payload["action"] = action
        payload["error_id"] = str(error.id)
        return payload

    def _review_task_payload(self, error: UserError) -> dict[str, Any]:
        """The repair card BEFORE the learner answers.

        Two rules this payload has to keep: the furniture is publication French
        (it is rendered as the card's kicker, prompt and placeholder), and it
        carries no `target_answer` — shipping the answer with the question made
        the whole exercise a copy for anyone reading the response.
        """
        learner = error.original_text or ""
        why_wrong = error.why_wrong or error.context_snippet
        if not learner and not error.why_wrong and _reads_as_learner_wording(error.context_snippet):
            # The first corrector filed the learner's wording in the context
            # column and no explanation at all. Shown as "Pourquoi : un conseils"
            # it is nonsense; shown as the wording to repair it is the task.
            learner = str(error.context_snippet or "").strip()
            why_wrong = None
        review_mode = error.review_mode or "grammar"
        copy = self.REVIEW_MODE_COPY.get(review_mode, self.REVIEW_MODE_COPY["grammar"])
        subject = learner or error.display_label or "cette erreur"
        return {
            "error_id": str(error.id),
            "display_label": error.display_label or "Reprise de langue",
            "review_mode": review_mode,
            "review_mode_label": copy["label"],
            "source_type": error.source_type or "unknown",
            "source_label": self.SOURCE_LABELS.get(error.source_type or "", "Pratique"),
            # The stored reason is a "learner -> target" mapping, i.e. the answer
            # to the very repair being asked; keep only the label half.
            "reason": str(serialize_error_memory(error)["reason"] or "").split("->")[0].split("→")[0].strip(" :"),
            "instruction": copy["instruction"],
            "prompt": f"{copy['prompt']} {subject}",
            "placeholder": copy["placeholder"],
            "learner_text": learner,
            "why_wrong": why_wrong,
            "repair_hint": error.repair_hint,
            "occurrences": error.occurrences or 1,
            "lapses": error.lapses or 0,
            "next_review_date": error.next_review_date.isoformat() if error.next_review_date else None,
        }

    def _review_feedback(self, error: UserError, *, is_correct: bool) -> str:
        # Publication French, and « guillemets » rather than markdown backticks —
        # the card prints this verbatim.
        if is_correct:
            if normalize_error_state(error.state) == ERROR_STATE_MASTERED:
                return "Juste, et pour la troisième fois : cet erratum est acquis, il quitte le relevé."
            remaining = max(0, MASTERY_REQUIRED_REPAIRS - int(error.mastery_streak or 0))
            if error.review_mode == "vocabulary":
                return f"Juste. Ce mot repart en révision ; encore {remaining} reprise(s) justes et il est acquis."
            return f"Juste. Encore {remaining} reprise(s) justes, à des jours différents, et cet erratum est acquis."
        if error.review_mode == "vocabulary":
            return f"Pas encore. La forme visée est « {error.correction} » ; revoyez le sens et reprenez-la bientôt."
        return f"Pas encore. La forme visée est « {error.correction} » ; l’erratum reste à reprendre."

    def _next_review(self, *, now: datetime, severity: int, repeated: bool, source_type: str) -> datetime:
        if repeated:
            return now + timedelta(days=1)
        if source_type in {"audio", "conversation", "story"} and severity >= 3:
            return now + timedelta(hours=12)
        return now + timedelta(days=1 if severity >= 3 else 3)

    def _memory_key(
        self,
        *,
        category: str,
        task_type: str,
        display_label: str,
        concept_id: int | None,
        linked_word_id: int | None,
    ) -> str:
        word_part = f":word-{linked_word_id}" if linked_word_id else ""
        concept_part = f"concept-{concept_id}" if concept_id else "concept-none"
        return f"{_slug(category)}:{concept_part}:{_slug(task_type)}:{_slug(display_label)}{word_part}"[:180]

    def _review_mode_for(self, *, category: str, task_type: str, source_type: str) -> str:
        marker = f"{category} {task_type}".lower()
        if "pronunciation" in marker or "prosody" in marker:
            return "speaking"
        if category == "vocabulary":
            return "vocabulary"
        if category == "spelling":
            return "spelling"
        if source_type in {"audio", "conversation"}:
            return "conversation"
        if source_type == "story":
            return "reading"
        return "grammar"

    def _link_vocabulary_if_needed(self, *, user: User, category: str, erratum: dict[str, Any]) -> VocabularyWord | None:
        if category != "vocabulary":
            return None
        linked_word_id = erratum.get("linked_word_id")
        if linked_word_id:
            try:
                word = self.db.get(VocabularyWord, int(linked_word_id))
            except (TypeError, ValueError):
                word = None
            if word:
                return word
        candidate = self._extract_vocabulary_candidate(erratum)
        if not candidate:
            return None
        lemma, translation = candidate
        language = (user.target_language or "fr").strip() or "fr"
        normalized = _normalize(lemma)
        word = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.language == language, VocabularyWord.normalized_word == normalized)
            .first()
        )
        if not word:
            word = VocabularyWord(
                language=language,
                word=lemma,
                normalized_word=normalized,
                english_translation=translation,
                usage_notes=erratum.get("repair_hint") or erratum.get("why_wrong"),
                topic_tags=["error_memory"],
            )
            self.db.add(word)
            self.db.flush([word])

        progress = ProgressService(self.db).get_or_create_progress(user_id=user.id, word_id=word.id)
        progress.times_seen = (progress.times_seen or 0) + 1
        progress.times_used_incorrectly = (progress.times_used_incorrectly or 0) + 1
        progress.incorrect_count = (progress.incorrect_count or 0) + 1
        progress.lapses = (progress.lapses or 0) + 1
        progress.state = "relearning"
        progress.phase = "relearn"
        progress.next_review_date = datetime.now(UTC) + timedelta(days=1)
        progress.due_date = progress.next_review_date.date()
        existing_types = list(progress.error_types or [])
        marker = str(erratum.get("task_error_type") or erratum.get("display_label") or "lexical_choice")
        if marker not in existing_types:
            existing_types.append(marker)
        progress.error_types = existing_types
        self.db.add(progress)
        return word

    def _extract_vocabulary_candidate(self, erratum: dict[str, Any]) -> tuple[str, str | None] | None:
        text = _normalize(erratum.get("corrected_target") or erratum.get("correction") or "")
        repair = _normalize(erratum.get("repair_hint") or "")
        combined = f"{text} {repair}"
        if "prendre soin" in combined or "prends soin" in combined:
            return ("prendre soin de", "to take care of")
        if re.search(r"\bsoutien(s|t|nent|drai|dras|dra|drons|drez|dront)?\b", combined) or "soutenir" in combined:
            return ("soutenir", "to support / to take care of")
        if "maintenir" in combined or "maintiens" in combined:
            return ("soutenir", "to support / to take care of")

        stopwords = {
            "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "me", "te", "se", "le", "la", "les",
            "un", "une", "des", "de", "du", "d", "a", "as", "est", "suis", "sommes", "sont", "pas", "ne",
        }
        tokens = [token for token in re.findall(r"[a-z']+", text) if len(token) > 2 and token not in stopwords]
        if not tokens:
            return None
        return (tokens[-1], None)

    def _update_error_concept(self, *, user: User, task_type: str, category: str) -> None:
        concept = get_concept_for_pattern(task_type) or get_concept_for_category(category)
        if not concept:
            return
        for pending in self.db.new:
            if (
                isinstance(pending, UserErrorConcept)
                and pending.user_id == user.id
                and pending.concept_id == concept.id
            ):
                pending.increment_occurrence()
                return
        user_concept = (
            self.db.query(UserErrorConcept)
            .filter(UserErrorConcept.user_id == user.id, UserErrorConcept.concept_id == concept.id)
            .first()
        )
        if user_concept:
            user_concept.increment_occurrence()
        else:
            user_concept = UserErrorConcept(
                user_id=user.id,
                concept_id=concept.id,
                total_occurrences=1,
                last_occurrence_date=datetime.now(UTC),
                next_review_date=datetime.now(UTC),
                state="new",
            )
            self.db.add(user_concept)

    def infer_concept_id_for_correction(
        self, *, learner_text: str | None, corrected_text: str | None, note: str | None = None
    ) -> int | None:
        """The grammar concept a free-text correction is about, or ``None``.

        WP-L1: journey corrections carry no error code, only the learner's span,
        the corrected span and a short note. They go through the same inference
        as ``record_detected_error``; the note supplies the family words, and a
        change that only touches determiners names that family itself (the
        note may be in German, or say nothing about grammar at all).
        """

        marker = str(note or "")
        before = _normalize_review_answer(learner_text).split()
        after = _normalize_review_answer(corrected_text).split()
        changed = set(before) ^ set(after)
        if changed and changed <= _DETERMINER_TOKENS:
            marker = f"determiner {marker}"
        return self._infer_grammar_concept_id(code=marker, category="grammar")

    def _infer_grammar_concept_id(self, *, code: str, category: str) -> int | None:
        marker = _normalize(f"{code} {category}")
        profile = infer_grammar_profile(task_text=marker)
        terms = profile_search_terms(profile.key)
        if terms:
            filters = []
            identity_filters = []
            for term in terms:
                like = f"%{term}%"
                identity = [
                    GrammarConcept.external_id.ilike(like),
                    GrammarConcept.category.ilike(like),
                    GrammarConcept.subskill.ilike(like),
                    GrammarConcept.name.ilike(like),
                ]
                identity_filters.extend(identity)
                filters.extend([*identity, GrammarConcept.core_rule.ilike(like)])
            concept = (
                self.db.query(GrammarConcept)
                .filter(GrammarConcept.active.is_(True), or_(*filters))
                # A concept that *is* the family outranks one whose rule text
                # merely mentions it («Gender and number» cites articles).
                .order_by(
                    case((or_(*identity_filters), 0), else_=1),
                    GrammarConcept.difficulty_order.asc(),
                    GrammarConcept.id.asc(),
                )
                .first()
            )
            return concept.id if concept else None
        return None

    def _display_label_for(self, *, code: str, category: str, language: Any = None) -> str:
        marker = _normalize(f"{code} {category}")
        if "pronoun" in marker or " y_en" in marker:
            return learner_text("erratum.label_pronoun_choice", language)
        if "vocab" in marker or "lexical" in marker or "false_friend" in marker:
            return learner_text("erratum.label_vocabulary_choice", language)
        if "spelling" in marker or "accent" in marker:
            return learner_text("erratum.label_spelling", language)
        profile = infer_grammar_profile(task_text=marker)
        if profile.key != "grammar_target":
            return profile.label
        fallback = str(code or category or "").replace("_", " ").strip()
        return fallback.title() or learner_text("erratum.label_language_repair", language)

    def _repair_hint_for(self, *, code: str, suggestion: str, language: Any = None) -> str:
        if suggestion:
            return learner_text("erratum.repair_use_suggestion", language, suggestion=suggestion)
        return infer_grammar_profile(task_text=code).repair

    def _direct_feedback(self, text: str) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return cleaned
        cleaned = re.sub(r"\b[Tt]he learner\b", "you", cleaned)
        cleaned = re.sub(r"\b[Tt]he user\b", "you", cleaned)
        return cleaned

    @staticmethod
    def _error_category_for_erratum(erratum: dict[str, Any]) -> str:
        marker = f"{erratum.get('task_error_type') or ''} {erratum.get('display_label') or ''}".lower()
        if any(token in marker for token in ("vocab", "lexical", "word_choice", "word choice", "false_friend")):
            return "vocabulary"
        if any(token in marker for token in ("pronunciation", "prosody", "liaison")):
            return "pronunciation"
        if any(token in marker for token in ("spelling", "accent", "orthograph")):
            return "spelling"
        return str(erratum.get("error_category") or "grammar").lower()


def _reads_as_learner_wording(text: str | None) -> bool:
    """A short phrase with no sentence punctuation: wording, not an explanation."""

    value = " ".join(str(text or "").split())
    if not value or len(value.split()) > 8:
        return False
    return not any(mark in value for mark in (". ", ": ", " : ", "->", "→", "\n")) and value[-1] not in ".!?"


def serialize_error_memory(error: UserError, *, language: Any = None) -> dict[str, Any]:
    """The stored erratum as a payload. `language` is the learner's native code:
    the stored halves were already authored in it, but the last-resort labels
    here have to be resolved at read time."""
    learner = error.original_text
    corrected = error.correction
    repair_label = learner_text("erratum.label_language_repair", language)
    reason = error.display_label or error.error_pattern or repair_label
    if learner and corrected:
        reason = f"{reason}: {learner} -> {corrected}"
    source_label = ErrorMemoryService.SOURCE_LABELS.get(
        error.source_type or "",
        error.source_type or learner_text("erratum.source_practice", language),
    )
    return {
        "id": str(error.id),
        "concept_id": error.concept_id,
        "source_attempt_id": str(error.source_attempt_id) if error.source_attempt_id else None,
        "display_label": error.display_label or error.error_pattern or repair_label,
        "task_error_type": error.task_error_type or error.error_pattern or "language_repair",
        "error_category": error.error_category,
        "review_mode": error.review_mode or "grammar",
        "source_type": error.source_type or "unknown",
        "source_label": source_label,
        "memory_key": error.memory_key,
        "linked_word_id": error.linked_word_id,
        "learner_text": learner,
        "corrected_target": corrected,
        "why_wrong": error.why_wrong or error.context_snippet,
        "repair_hint": error.repair_hint,
        "reason": reason,
        "next_review_date": error.next_review_date.isoformat() if error.next_review_date else None,
        "last_review_date": error.last_review_date.isoformat() if error.last_review_date else None,
        "occurrences": error.occurrences or 1,
        "lapses": error.lapses or 0,
        "state": normalize_error_state(error.state),
        # The stored label as well, so an operator reading a payload can see a
        # legacy row for what it is instead of wondering why it was relabelled.
        "stored_state": error.state or None,
        "mastery_streak": int(error.mastery_streak or 0),
        "mastery_target": MASTERY_REQUIRED_REPAIRS,
        "mastered": normalize_error_state(error.state) == ERROR_STATE_MASTERED,
        "mastered_at": error.mastered_at.isoformat() if error.mastered_at else None,
        "interval_days": int(error.scheduled_days or 0),
        "ease_factor": round(float(error.ease_factor or 2.5), 3),
        "metadata": error.error_metadata or {},
    }


__all__ = [
    "ERROR_STATES",
    "ERROR_STATE_MASTERED",
    "ERROR_STATE_OPEN",
    "ERROR_STATE_REPAIRING",
    "MASTERY_REQUIRED_REPAIRS",
    "ErrorMemoryService",
    "normalize_error_state",
    "serialize_error_memory",
]
