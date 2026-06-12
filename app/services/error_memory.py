"""Unified learner error memory and scheduling service."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.error_concepts import get_concept_for_category, get_concept_for_pattern
from app.db.models.atelier import AtelierAttempt
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.grammar import GrammarConcept
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.grammar_feedback import infer_grammar_profile, profile_search_terms
from app.services.progress import ProgressService


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize(value)).strip("_") or "unknown"


def _normalize_review_answer(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize(value)).strip()


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

    SOURCE_LABELS = {
        "atelier": "Atelier",
        "audio": "Audio conversation",
        "conversation": "Conversation",
        "story": "Story",
        "brief_exercise": "Exercise",
        "mission": "Mission",
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def due_error_records(self, user: User, *, limit: int = 20, review_modes: set[str] | None = None) -> list[UserError]:
        now = datetime.now(timezone.utc)
        query = (
            self.db.query(UserError)
            .filter(UserError.user_id == user.id, UserError.state != "mastered")
            .filter((UserError.next_review_date.is_(None)) | (UserError.next_review_date <= now))
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
        erratum = {
            "display_label": self._display_label_for(code=code, category=category),
            "learner_text": getattr(detected_error, "span", "") or "",
            "corrected_target": getattr(detected_error, "suggestion", "") or "",
            "why_wrong": self._direct_feedback(getattr(detected_error, "message", "") or "This form needs review."),
            "repair_hint": self._repair_hint_for(code=code, suggestion=getattr(detected_error, "suggestion", "")),
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
        display_label = str(erratum.get("display_label") or self._display_label_for(code=task_type, category="grammar"))[:120]
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
        now = datetime.now(timezone.utc)
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
            existing.state = "relearning"
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
            state="new",
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
        now = datetime.now(timezone.utc)
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

    def review_error(self, *, user: User, error_id: UUID, rating: int, repaired: bool) -> UserError | None:
        error = self.db.query(UserError).filter(UserError.id == error_id, UserError.user_id == user.id).first()
        if not error:
            return None
        now = datetime.now(timezone.utc)
        if repaired and rating >= 3:
            delay_days = 14 if rating == 4 else 7
            error.state = "review"
        else:
            delay_days = 1
            error.state = "relearning"
        error.mark_review(now, now + timedelta(days=delay_days), rating)
        error.updated_at = now
        self.db.add(error)
        return error

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
        submitted_at = datetime.now(timezone.utc)
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
            closure = {
                "label": "Corrected. Filed.",
                "detail": "This erratum leaves today and returns on its next review date.",
                "filed_at": submitted_at.isoformat(),
                "next_review_date": reviewed.next_review_date.isoformat() if reviewed.next_review_date else None,
                "state": reviewed.state or "review",
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
        target = error.correction or ""
        learner = error.original_text or ""
        review_mode = error.review_mode or "grammar"
        if review_mode == "vocabulary":
            instruction = "Write the corrected word or phrase from memory."
            prompt = f"Repair the vocabulary choice: {learner or error.display_label}"
            placeholder = "Correct word or phrase"
        elif review_mode == "spelling":
            instruction = "Rewrite the corrected form with spelling and accents fixed."
            prompt = f"Repair the spelling: {learner or error.display_label}"
            placeholder = "Correct spelling"
        elif review_mode == "speaking":
            instruction = "For now, type the phrase you should say. Audio replay can be added later."
            prompt = f"Repair the spoken phrase: {learner or error.display_label}"
            placeholder = "Phrase to say"
        else:
            instruction = "Rewrite the remembered mistake correctly."
            prompt = f"Repair this grammar slip: {learner or error.display_label}"
            placeholder = "Corrected sentence or phrase"
        return {
            "error_id": str(error.id),
            "display_label": error.display_label or "Language repair",
            "review_mode": review_mode,
            "source_type": error.source_type or "unknown",
            "source_label": self.SOURCE_LABELS.get(error.source_type or "", error.source_type or "Practice"),
            "reason": serialize_error_memory(error)["reason"],
            "instruction": instruction,
            "prompt": prompt,
            "placeholder": placeholder,
            "learner_text": learner,
            "why_wrong": error.why_wrong or error.context_snippet,
            "repair_hint": error.repair_hint,
            "target_answer": target,
            "occurrences": error.occurrences or 1,
            "lapses": error.lapses or 0,
            "next_review_date": error.next_review_date.isoformat() if error.next_review_date else None,
        }

    def _review_feedback(self, error: UserError, *, is_correct: bool) -> str:
        if is_correct:
            if error.review_mode == "vocabulary":
                return "Correct. This vocabulary slip moves back into review."
            return "Correct. This erratum is scheduled for a later check."
        if error.review_mode == "vocabulary":
            return f"Not yet. The target phrase is `{error.correction}`; review the meaning and try it again soon."
        return f"Not yet. The target form is `{error.correction}`; the erratum stays due for repair."

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
        progress.next_review_date = datetime.now(timezone.utc) + timedelta(days=1)
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
                last_occurrence_date=datetime.now(timezone.utc),
                next_review_date=datetime.now(timezone.utc),
                state="new",
            )
            self.db.add(user_concept)

    def _infer_grammar_concept_id(self, *, code: str, category: str) -> int | None:
        marker = _normalize(f"{code} {category}")
        profile = infer_grammar_profile(task_text=marker)
        terms = profile_search_terms(profile.key)
        if terms:
            filters = []
            for term in terms:
                like = f"%{term}%"
                filters.extend(
                    [
                        GrammarConcept.external_id.ilike(like),
                        GrammarConcept.category.ilike(like),
                        GrammarConcept.subskill.ilike(like),
                        GrammarConcept.name.ilike(like),
                        GrammarConcept.core_rule.ilike(like),
                    ]
                )
            concept = (
                self.db.query(GrammarConcept)
                .filter(GrammarConcept.active.is_(True), or_(*filters))
                .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
                .first()
            )
            return concept.id if concept else None
        return None

    def _display_label_for(self, *, code: str, category: str) -> str:
        marker = _normalize(f"{code} {category}")
        if "pronoun" in marker or " y_en" in marker:
            return "Pronoun choice"
        if "vocab" in marker or "lexical" in marker or "false_friend" in marker:
            return "Vocabulary choice"
        if "spelling" in marker or "accent" in marker:
            return "Spelling"
        profile = infer_grammar_profile(task_text=marker)
        if profile.key != "grammar_target":
            return profile.label
        return str(code or category or "Language repair").replace("_", " ").title()

    def _repair_hint_for(self, *, code: str, suggestion: str) -> str:
        if suggestion:
            return f"Use `{suggestion}` here, then practise the same contrast in a fresh sentence."
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


def serialize_error_memory(error: UserError) -> dict[str, Any]:
    learner = error.original_text
    corrected = error.correction
    reason = error.display_label or error.error_pattern or "Language repair"
    if learner and corrected:
        reason = f"{reason}: {learner} -> {corrected}"
    source_label = ErrorMemoryService.SOURCE_LABELS.get(error.source_type or "", error.source_type or "Practice")
    return {
        "id": str(error.id),
        "concept_id": error.concept_id,
        "source_attempt_id": str(error.source_attempt_id) if error.source_attempt_id else None,
        "display_label": error.display_label or error.error_pattern or "Language repair",
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
        "state": error.state or "new",
        "metadata": error.error_metadata or {},
    }


__all__ = ["ErrorMemoryService", "serialize_error_memory"]
