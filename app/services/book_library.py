"""Guided-reading library service for user-uploaded books."""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.library import BookEpisode, UserBook
from app.db.models.user import User
from app.services.book_parser import BookParseResult, BookParserService, ParsedChapter
from app.services.exercise_generation import (
    EXERCISE_ENGINE_VERSION,
    ExerciseGenerationService,
    ExerciseGenerationUnavailable,
)

SUPPORTED_LIBRARY_FORMATS = {"txt", "epub", "pdf", "html", "htm"}

_STOPWORDS = {
    "avec",
    "chez",
    "dans",
    "des",
    "elle",
    "elles",
    "est",
    "les",
    "mais",
    "nous",
    "pas",
    "plus",
    "pour",
    "que",
    "qui",
    "sans",
    "ses",
    "son",
    "sur",
    "une",
    "vous",
}


@dataclass(frozen=True)
class _NoopLLMResult:
    content: str


class _NoopBookAnalysisLLM:
    """Avoid story-RPG LLM analysis when we only need extraction + chapter text."""

    def generate_chat_completion(self, *_args: Any, **_kwargs: Any) -> _NoopLLMResult:
        return _NoopLLMResult(
            content=(
                '{"scenes":[],"characters":[],"vocabulary":[],"themes":[],'
                '"narration_a1":"","narration_b1":""}'
            )
        )


class BookLibraryService:
    """Create and process private guided-reading books."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_upload_record(
        self,
        *,
        user: User,
        file_content: bytes,
        filename: str,
        title: str | None = None,
        author: str | None = None,
        target_level: str | None = None,
        task_id: str | None = None,
    ) -> tuple[UserBook, bool]:
        """Create or reuse a durable upload record keyed by owner + source hash."""

        extension = self._extension(filename)
        if extension not in SUPPORTED_LIBRARY_FORMATS:
            raise ValueError(f"Unsupported file format: {extension}. Use TXT, EPUB, PDF, or HTML.")
        source_hash = hashlib.sha256(file_content).hexdigest()
        existing = (
            self.db.query(UserBook)
            .filter(UserBook.user_id == user.id, UserBook.source_hash == source_hash)
            .first()
        )
        if existing and existing.status != "failed":
            return existing, True

        if existing:
            book = existing
            book.status = "queued"
            book.status_message = "Queued for re-processing."
            book.error_message = None
            book.progress_percent = 0
            book.task_id = task_id or book.task_id or str(uuid.uuid4())
            book.completed_episode_indices = []
            book.current_episode_index = 0
            book.episodes.clear()
        else:
            book = UserBook(
                user_id=user.id,
                title=(title or Path(filename).stem.replace("_", " ").replace("-", " ").title()).strip()[:255],
                author=author.strip()[:255] if author else None,
                source_filename=filename[:255],
                source_type=extension,
                source_hash=source_hash,
                target_level=self._normalize_level(target_level),
                status="queued",
                status_message="Queued for parsing.",
                progress_percent=0,
                task_id=task_id or str(uuid.uuid4()),
                completed_episode_indices=[],
                extra_metadata={"ingestion": "guided_reading_library_v1"},
            )
            self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        return book, False

    def process_upload(
        self,
        *,
        book_id: str | uuid.UUID,
        file_content: bytes,
        filename: str,
        title: str | None = None,
        author: str | None = None,
        target_level: str | None = None,
        user: User | None = None,
    ) -> UserBook:
        """Parse a whole uploaded book and build level-sized guided-reading episodes."""

        book_uuid = uuid.UUID(str(book_id))
        book = self.db.get(UserBook, book_uuid)
        if not book:
            raise ValueError(f"UserBook not found: {book_id}")
        if user and book.user_id != user.id:
            raise ValueError("Book does not belong to this user.")

        self._mark(book, status="parsing", message="Extracting readable text.", progress=10)
        try:
            parser = BookParserService(self.db, llm_service=_NoopBookAnalysisLLM())
            parse_result = parser.parse_book_file(
                file_content,
                filename,
                title=title or book.title,
                author=author or book.author,
                max_chapters=None,
            )
            level = self._normalize_level(target_level or book.target_level)
            self._mark(book, status="segmenting", message="Splitting into reading episodes.", progress=35)
            episode_inputs = self._segment_parse_result(parse_result, cefr_level=level)
            if not episode_inputs:
                raise ValueError("No level-sized reading episodes could be created from this file.")

            book.title = parse_result.title[:255]
            book.author = parse_result.author[:255] if parse_result.author else None
            book.source_type = parse_result.source_type
            book.target_level = level
            book.estimated_total_words = parse_result.total_word_count
            book.total_episodes = len(episode_inputs)
            book.current_episode_index = 0
            book.completed_episode_indices = []
            book.episodes.clear()
            self.db.flush()

            for index, item in enumerate(episode_inputs):
                percent = 40 + int((index / max(1, len(episode_inputs))) * 50)
                self._mark(
                    book,
                    status="generating",
                    message=f"Preparing episode {index + 1} of {len(episode_inputs)}.",
                    progress=percent,
                    commit=False,
                )
                exercise_payload = self._exercise_payload(
                    passage=item["passage_text"],
                    title=item["title"],
                    cefr_level=level,
                    vocab_seed=item["vocab_seed"],
                    grammar_seed=item["grammar_seed"],
                    user=user or book.user,
                )
                self.db.add(
                    BookEpisode(
                        user_book_id=book.id,
                        order_index=index,
                        title=item["title"],
                        passage_text=item["passage_text"],
                        est_reading_minutes=item["est_reading_minutes"],
                        cefr_level=level,
                        word_count=item["word_count"],
                        vocab_seed=item["vocab_seed"],
                        grammar_seed=item["grammar_seed"],
                        exercise_payload=exercise_payload,
                        status="ready",
                    )
                )

            self._mark(book, status="ready", message="Ready.", progress=100, commit=False)
            book.ready_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(book)
            return book
        except Exception as exc:
            logger.exception("User book processing failed", book_id=str(book.id), filename=filename)
            self._mark(book, status="failed", message="Processing failed.", progress=100, error=str(exc))
            raise

    def list_books(self, *, user: User) -> list[dict[str, Any]]:
        books = (
            self.db.query(UserBook)
            .filter(UserBook.user_id == user.id)
            .order_by(UserBook.created_at.desc(), UserBook.id.desc())
            .all()
        )
        return [self.serialize_book(book) for book in books]

    def get_book(self, *, user: User, book_id: str | uuid.UUID) -> UserBook:
        book = self.db.get(UserBook, uuid.UUID(str(book_id)))
        if not book or book.user_id != user.id:
            raise ValueError("Book not found.")
        return book

    def get_episode(self, *, user: User, book_id: str | uuid.UUID, order_index: int) -> BookEpisode:
        book = self.get_book(user=user, book_id=book_id)
        episode = (
            self.db.query(BookEpisode)
            .filter(BookEpisode.user_book_id == book.id, BookEpisode.order_index == order_index)
            .first()
        )
        if not episode:
            raise ValueError("Episode not found.")
        return episode

    def next_ready_episode(self, *, user: User) -> tuple[UserBook, BookEpisode] | None:
        """Return the next incomplete ready episode from the user's private library."""

        books = (
            self.db.query(UserBook)
            .filter(UserBook.user_id == user.id, UserBook.status == "ready", UserBook.total_episodes > 0)
            .order_by(UserBook.updated_at.desc(), UserBook.created_at.desc(), UserBook.id.desc())
            .limit(20)
            .all()
        )
        for book in books:
            completed = {int(value) for value in (book.completed_episode_indices or [])}
            next_index = next(
                (index for index in range(int(book.total_episodes or 0)) if index not in completed),
                None,
            )
            if next_index is None:
                continue
            episode = (
                self.db.query(BookEpisode)
                .filter(
                    BookEpisode.user_book_id == book.id,
                    BookEpisode.order_index == next_index,
                    BookEpisode.status == "ready",
                )
                .first()
            )
            if episode:
                return book, episode
        return None

    def complete_episode(self, *, user: User, book_id: str | uuid.UUID, order_index: int) -> UserBook:
        book = self.get_book(user=user, book_id=book_id)
        completed = sorted({int(value) for value in (book.completed_episode_indices or [])} | {order_index})
        book.completed_episode_indices = completed
        book.current_episode_index = min(max(completed) + 1, max(0, int(book.total_episodes or 0) - 1))
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        return book

    def serialize_book(self, book: UserBook, *, include_episodes: bool = False) -> dict[str, Any]:
        completed = [int(value) for value in (book.completed_episode_indices or [])]
        total = int(book.total_episodes or 0)
        payload: dict[str, Any] = {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "source_filename": book.source_filename,
            "source_type": book.source_type,
            "source_hash": book.source_hash,
            "target_level": book.target_level,
            "status": book.status,
            "status_message": book.status_message,
            "error_message": book.error_message,
            "progress_percent": book.progress_percent,
            "total_episodes": total,
            "current_episode_index": book.current_episode_index,
            "completed_episode_indices": completed,
            "completion_percentage": round((len(completed) / total) * 100) if total else 0,
            "estimated_total_words": book.estimated_total_words,
            "task_id": book.task_id,
            "created_at": book.created_at.isoformat() if book.created_at else None,
            "updated_at": book.updated_at.isoformat() if book.updated_at else None,
            "ready_at": book.ready_at.isoformat() if book.ready_at else None,
        }
        if include_episodes:
            payload["episodes"] = [
                self.serialize_episode(episode, completed_indices=set(completed), include_passage=False)
                for episode in book.episodes
            ]
        return payload

    def serialize_episode(
        self,
        episode: BookEpisode,
        *,
        completed_indices: set[int] | None = None,
        include_passage: bool = True,
    ) -> dict[str, Any]:
        completed_indices = completed_indices or set()
        payload: dict[str, Any] = {
            "id": str(episode.id),
            "book_id": str(episode.user_book_id),
            "order_index": episode.order_index,
            "title": episode.title,
            "est_reading_minutes": episode.est_reading_minutes,
            "cefr_level": episode.cefr_level,
            "word_count": episode.word_count,
            "vocab_seed": episode.vocab_seed or [],
            "grammar_seed": episode.grammar_seed or [],
            "exercise_payload": episode.exercise_payload or {},
            "status": episode.status,
            "is_completed": episode.order_index in completed_indices,
        }
        if include_passage:
            payload["passage_text"] = episode.passage_text
        else:
            payload["passage_preview"] = self._compact(episode.passage_text, max_length=220)
        return payload

    def upload_status_payload(self, book: UserBook) -> dict[str, Any]:
        legacy_status = "completed" if book.status == "ready" else "failed" if book.status == "failed" else "processing"
        return {
            "task_id": book.task_id,
            "book_id": str(book.id),
            "library_book_id": str(book.id),
            "status": legacy_status,
            "book_status": book.status,
            "progress": book.progress_percent,
            "message": book.status_message or "",
            "error": book.error_message,
            "total_episodes": book.total_episodes,
            "current_episode_index": book.current_episode_index,
            "user_id": str(book.user_id),
        }

    def _segment_parse_result(self, result: BookParseResult, *, cefr_level: str) -> list[dict[str, Any]]:
        target_words = self._target_episode_words(cefr_level)
        episodes: list[dict[str, Any]] = []
        for chapter in result.chapters:
            for offset, passage in enumerate(self._passage_chunks(chapter, max_words=target_words)):
                words = passage.split()
                if len(words) < 25:
                    continue
                title = chapter.title if offset == 0 else f"{chapter.title} ({offset + 1})"
                vocab_seed = self._vocab_seed(passage)
                grammar_seed = self._grammar_seed(passage)
                episodes.append(
                    {
                        "title": title[:255],
                        "passage_text": passage,
                        "word_count": len(words),
                        "est_reading_minutes": max(1, math.ceil(len(words) / self._reading_wpm(cefr_level))),
                        "vocab_seed": vocab_seed,
                        "grammar_seed": grammar_seed,
                    }
                )
        return episodes

    def _exercise_payload(
        self,
        *,
        passage: str,
        title: str,
        cefr_level: str,
        vocab_seed: list[dict[str, Any]],
        grammar_seed: list[dict[str, Any]],
        user: User | None,
    ) -> dict[str, Any]:
        if settings.ATELIER_LLM_ENABLED:
            try:
                bundle = ExerciseGenerationService(self.db).generate_passage_exercises(
                    passage_text=passage,
                    episode_title=title,
                    cefr_level=cefr_level,
                    user=user,
                    vocab_seed=vocab_seed,
                    grammar_seed=grammar_seed,
                )
                return bundle.payload
            except ExerciseGenerationUnavailable as exc:
                logger.info("Falling back to deterministic passage scaffold", title=title, error=str(exc))
        return self._fallback_exercise_payload(
            passage=passage,
            title=title,
            cefr_level=cefr_level,
            vocab_seed=vocab_seed,
            grammar_seed=grammar_seed,
        )

    def _fallback_exercise_payload(
        self,
        *,
        passage: str,
        title: str,
        cefr_level: str,
        vocab_seed: list[dict[str, Any]],
        grammar_seed: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sentences = self._sentences(passage)
        first = sentences[0] if sentences else self._compact(passage, max_length=180)
        detail = sentences[1] if len(sentences) > 1 else first
        vocab = vocab_seed[:5] or [{"word": "passage", "context_sentence": first, "source": "fallback"}]
        grammar = grammar_seed[:3] or [{"pattern": "phrase du passage", "evidence": first}]
        return {
            "engine_version": EXERCISE_ENGINE_VERSION,
            "source": "deterministic_passage_scaffold",
            "episode_title": title,
            "cefr_level": cefr_level,
            "passage_excerpt": self._compact(passage, max_length=360),
            "comprehension": [
                {
                    "question": "Que se passe-t-il au debut de ce passage ?",
                    "answer": self._compact(first, max_length=220),
                    "evidence": self._compact(first, max_length=180),
                },
                {
                    "question": "Quel detail du passage aide a comprendre la scene ?",
                    "answer": self._compact(detail, max_length=220),
                    "evidence": self._compact(detail, max_length=180),
                },
            ],
            "vocabulary": [
                {
                    "word": item.get("word"),
                    "context_sentence": item.get("context_sentence") or first,
                    "gloss_hint": "Mot important tire du passage.",
                }
                for item in vocab[:5]
                if item.get("word")
            ],
            "grammar": [
                {
                    "pattern": item.get("pattern") or "phrase utile",
                    "prompt": f"Retrouve ce modele dans le passage: {item.get('pattern') or 'phrase utile'}.",
                    "answer": item.get("evidence") or first,
                    "explanation": "Observe la forme dans une phrase authentique du passage.",
                }
                for item in grammar[:3]
            ],
            "production": {
                "prompt": "Ecris deux phrases en francais pour resumer ce passage.",
                "example_answer": self._compact(first, max_length=160),
                "success_criteria": [
                    "Mentionne une action ou un detail du passage.",
                    "Utilise au moins un mot du vocabulaire de cet episode.",
                ],
            },
        }

    def _passage_chunks(self, chapter: ParsedChapter, *, max_words: int) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chapter.content) if p.strip()]
        if not paragraphs:
            paragraphs = [chapter.content]
        chunks: list[str] = []
        current: list[str] = []
        current_words = 0
        for paragraph in paragraphs:
            words = paragraph.split()
            if len(words) > max_words:
                if current:
                    chunks.append("\n\n".join(current).strip())
                    current = []
                    current_words = 0
                chunks.extend(self._split_long_paragraph(paragraph, max_words=max_words))
                continue
            if current and current_words + len(words) > max_words:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_words = 0
            current.append(paragraph)
            current_words += len(words)
        if current:
            chunks.append("\n\n".join(current).strip())
        return chunks

    def _split_long_paragraph(self, paragraph: str, *, max_words: int) -> list[str]:
        sentences = self._sentences(paragraph)
        if not sentences:
            words = paragraph.split()
            return [" ".join(words[start : start + max_words]) for start in range(0, len(words), max_words)]
        chunks: list[str] = []
        current: list[str] = []
        count = 0
        for sentence in sentences:
            words = sentence.split()
            if current and count + len(words) > max_words:
                chunks.append(" ".join(current).strip())
                current = []
                count = 0
            current.append(sentence)
            count += len(words)
        if current:
            chunks.append(" ".join(current).strip())
        return chunks

    def _vocab_seed(self, passage: str) -> list[dict[str, Any]]:
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'-]{4,}", passage.lower())
        counts: dict[str, int] = {}
        first_context: dict[str, str] = {}
        sentences = self._sentences(passage)
        for word in words:
            normalized = word.strip("'-").lower()
            if len(normalized) < 4 or normalized in _STOPWORDS:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            if normalized not in first_context:
                first_context[normalized] = next(
                    (sentence for sentence in sentences if re.search(rf"\b{re.escape(normalized)}\b", sentence, re.I)),
                    "",
                )
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
        return [
            {"word": word, "frequency": count, "context_sentence": self._compact(first_context.get(word), max_length=180)}
            for word, count in ranked
        ]

    def _grammar_seed(self, passage: str) -> list[dict[str, Any]]:
        patterns = [
            ("negation ne ... pas", r"\bne\b[^.!?]{0,80}\bpas\b"),
            ("passe compose", r"\b(?:ai|as|a|avons|avez|ont|suis|es|est|sommes|etes|sont)\b\s+\w+(?:e|i|u|is|it)\b"),
            ("imparfait", r"\b\w+(?:ais|ait|ions|iez|aient)\b"),
            ("futur simple", r"\b\w+(?:rai|ras|ra|rons|rez|ront)\b"),
            ("condition avec si", r"\bsi\s+[^.!?]{3,120}"),
        ]
        seeds: list[dict[str, Any]] = []
        for label, pattern in patterns:
            match = re.search(pattern, passage, flags=re.IGNORECASE)
            if match:
                seeds.append({"pattern": label, "evidence": self._compact(match.group(0), max_length=180)})
        return seeds

    def _mark(
        self,
        book: UserBook,
        *,
        status: str,
        message: str,
        progress: int,
        error: str | None = None,
        commit: bool = True,
    ) -> None:
        book.status = status
        book.status_message = message
        book.progress_percent = max(0, min(100, int(progress)))
        if error is not None:
            book.error_message = error
        self.db.add(book)
        if commit:
            self.db.commit()
            self.db.refresh(book)

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename or "upload.txt").suffix.lower().lstrip(".")

    @staticmethod
    def _normalize_level(level: str | None) -> str:
        raw = (level or "A2").split(",")[0].strip().upper()
        if raw.startswith(("A1", "A2", "B1", "B2", "C1", "C2")):
            return raw[:2]
        return "A2"

    @staticmethod
    def _target_episode_words(cefr_level: str) -> int:
        return {"A1": 150, "A2": 220, "B1": 300, "B2": 380, "C1": 450, "C2": 500}.get(cefr_level[:2], 260)

    @staticmethod
    def _reading_wpm(cefr_level: str) -> int:
        return {"A1": 60, "A2": 75, "B1": 90, "B2": 110, "C1": 130, "C2": 145}.get(cefr_level[:2], 85)

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]

    @staticmethod
    def _compact(value: Any, *, max_length: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "..."


__all__ = ["BookLibraryService", "SUPPORTED_LIBRARY_FORMATS"]
