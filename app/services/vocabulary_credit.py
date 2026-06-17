"""Shared vocabulary credit and errata policy.

This service keeps vocabulary SRS updates consistent across sessions,
missions, Feuilleton, and direct review surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService
from app.services.progress import ProgressService


VOCABULARY_CREDIT_VERSION = "vocab-credit-v1"

SEEN_EVENTS = {"seen_context", "context_seen", "read_context"}
RECOGNITION_EVENTS = {"recognized", "translated", "recognition", "context_translation"}
CORRECT_PRODUCTION_EVENTS = {"produced_correct", "used_correctly", "free_production_correct"}
INCORRECT_PRODUCTION_EVENTS = {
    "produced_incorrect",
    "used_incorrectly",
    "incorrect",
    "incorrect_production",
}
MISSING_TARGET_EVENTS = {"missed_target", "missing_target", "avoided_target"}


@dataclass(slots=True)
class VocabularyCreditResult:
    """Outcome for one applied vocabulary credit event."""

    word_id: int
    event_type: str
    credit_kind: str
    progress_id: str | None
    erratum_id: str | None = None
    erratum_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word_id": self.word_id,
            "event_type": self.event_type,
            "credit_kind": self.credit_kind,
            "progress_id": self.progress_id,
            "erratum_id": self.erratum_id,
            "erratum_action": self.erratum_action,
            "policy_version": VOCABULARY_CREDIT_VERSION,
        }


class VocabularyCreditService:
    """Apply one vocabulary learning policy across product modes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.progress_service = ProgressService(db)
        self.error_memory = ErrorMemoryService(db)

    def apply(
        self,
        *,
        user: User,
        word: VocabularyWord,
        event_type: str,
        source_type: str,
        learner_text: str | None = None,
        corrected_text: str | None = None,
        context: str | None = None,
        explanation: str | None = None,
        repair_hint: str | None = None,
        severity: int = 2,
        session: LearningSession | UUID | None = None,
        message: ConversationMessage | UUID | None = None,
        source_payload: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> VocabularyCreditResult:
        """Apply SRS credit and optionally create a linked vocabulary erratum."""

        normalized_event = str(event_type or "seen_context").strip().lower()
        credit_kind = self._credit_kind(normalized_event)
        progress_event = self._progress_event_for(credit_kind)
        progress = self.progress_service.record_context_credit(
            user=user,
            word=word,
            event_type=progress_event,
            now=now or datetime.now(timezone.utc),
        )
        erratum_update: dict[str, Any] | None = None
        if credit_kind in {"produced_incorrect", "missed_target"}:
            erratum_update = self._record_vocabulary_erratum(
                user=user,
                word=word,
                source_type=source_type,
                event_type=normalized_event,
                credit_kind=credit_kind,
                learner_text=learner_text,
                corrected_text=corrected_text,
                context=context,
                explanation=explanation,
                repair_hint=repair_hint,
                severity=severity,
                session=session,
                message=message,
                source_payload=source_payload,
            )

        return VocabularyCreditResult(
            word_id=word.id,
            event_type=normalized_event,
            credit_kind=credit_kind,
            progress_id=str(progress.id) if progress and progress.id else None,
            erratum_id=erratum_update.get("id") if erratum_update else None,
            erratum_action=erratum_update.get("action") if erratum_update else None,
        )

    def apply_many(
        self,
        *,
        user: User,
        words: list[VocabularyWord],
        event_type: str,
        source_type: str,
        context: str | None = None,
        source_payload: dict[str, Any] | None = None,
    ) -> list[VocabularyCreditResult]:
        return [
            self.apply(
                user=user,
                word=word,
                event_type=event_type,
                source_type=source_type,
                context=context,
                source_payload=source_payload,
            )
            for word in words
        ]

    def summarize(self, results: list[VocabularyCreditResult]) -> dict[str, int]:
        summary: dict[str, int] = {
            "seen_context": 0,
            "recognized": 0,
            "produced_correct": 0,
            "produced_incorrect": 0,
            "missed_target": 0,
            "errata_created": 0,
        }
        for result in results:
            summary[result.credit_kind] = summary.get(result.credit_kind, 0) + 1
            if result.erratum_id:
                summary["errata_created"] += 1
        return summary

    def _record_vocabulary_erratum(
        self,
        *,
        user: User,
        word: VocabularyWord,
        source_type: str,
        event_type: str,
        credit_kind: str,
        learner_text: str | None,
        corrected_text: str | None,
        context: str | None,
        explanation: str | None,
        repair_hint: str | None,
        severity: int,
        session: LearningSession | UUID | None,
        message: ConversationMessage | UUID | None,
        source_payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        learner = (learner_text or "").strip()
        corrected = (corrected_text or word.word or word.french_translation or "").strip()
        translation = word.german_translation or word.english_translation or word.definition or ""
        if credit_kind == "missed_target":
            label = f"Use target word: {word.word}"
            why = explanation or f"The task targeted {word.word}, but your answer did not use it."
            hint = repair_hint or f"Add {word.word} naturally. Meaning: {translation or 'target vocabulary'}."
            task_type = "vocabulary_missing_target"
        else:
            label = f"Vocabulary: {word.word}"
            why = explanation or f"The word {word.word} needs another repair in context."
            hint = repair_hint or f"Use {word.word} for {translation} in a fresh sentence."
            task_type = "vocabulary_incorrect_use"

        session_id = session.id if hasattr(session, "id") else session
        message_id = message.id if hasattr(message, "id") else message
        metadata = {
            "policy_version": VOCABULARY_CREDIT_VERSION,
            "event_type": event_type,
            "word_id": word.id,
            **(source_payload or {}),
        }
        return self.error_memory.record_erratum(
            user=user,
            erratum={
                "display_label": label,
                "learner_text": learner or context or word.word,
                "corrected_target": corrected or word.word,
                "why_wrong": why,
                "repair_hint": hint,
                "severity": max(1, min(int(severity or 2), 3)),
                "recurring": True,
                "task_error_type": task_type,
                "external_id": None,
                "error_category": "vocabulary",
                "linked_word_id": word.id,
            },
            source_type=source_type,
            learning_session_id=session_id,
            message_id=message_id,
            source_payload=metadata,
        )

    @staticmethod
    def _credit_kind(event_type: str) -> str:
        if event_type in CORRECT_PRODUCTION_EVENTS:
            return "produced_correct"
        if event_type in INCORRECT_PRODUCTION_EVENTS:
            return "produced_incorrect"
        if event_type in MISSING_TARGET_EVENTS:
            return "missed_target"
        if event_type in RECOGNITION_EVENTS:
            return "recognized"
        if event_type in SEEN_EVENTS:
            return "seen_context"
        return "seen_context"

    @staticmethod
    def _progress_event_for(credit_kind: str) -> str:
        if credit_kind == "produced_correct":
            return "produced_correct"
        if credit_kind in {"produced_incorrect", "missed_target"}:
            return "produced_incorrect"
        if credit_kind == "recognized":
            return "recognized"
        return "seen_context"
