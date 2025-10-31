"""Service helpers for vocabulary endpoints."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.vocabulary import VocabularyWord


class VocabularyNotFoundError(ValueError):
    """Raised when a vocabulary item cannot be located."""


class VocabularyService:
    """Provide querying utilities for vocabulary datasets."""

    def __init__(self, db: Session):
        self.db = db

    def list_words(
        self, *, language: str | None, limit: int, offset: int
    ) -> list[VocabularyWord]:
        """Return a slice of vocabulary ordered by frequency rank."""

        stmt = select(VocabularyWord).order_by(VocabularyWord.frequency_rank).offset(offset).limit(limit)
        if language:
            stmt = stmt.where(VocabularyWord.language == language)
        return list(self.db.scalars(stmt))

    def count_words(self, *, language: str | None) -> int:
        """Return the number of vocabulary items matching the filter."""

        stmt = select(func.count()).select_from(VocabularyWord)
        if language:
            stmt = stmt.where(VocabularyWord.language == language)
        return int(self.db.scalar(stmt) or 0)

    def get_word(self, word_id: int) -> VocabularyWord:
        """Retrieve a single vocabulary word by identifier."""

        word = self.db.get(VocabularyWord, word_id)
        if not word:
            raise VocabularyNotFoundError("Vocabulary word not found")
        return word

    def lookup_word(self, *, term: str, language: str | None = None) -> VocabularyWord:
        """Return the first vocabulary entry matching the supplied surface form."""

        value = term.strip().lower()
        if not value:
            raise VocabularyNotFoundError("Vocabulary word not found")

        stmt = select(VocabularyWord).where(
            func.lower(VocabularyWord.word) == value
        )
        if language:
            stmt = stmt.where(VocabularyWord.language == language)

        word = self.db.scalars(stmt.limit(1)).first()
        if not word:
            stmt = select(VocabularyWord).where(VocabularyWord.normalized_word == value)
            if language:
                stmt = stmt.where(VocabularyWord.language == language)
            word = self.db.scalars(stmt.limit(1)).first()
        if not word:
            raise VocabularyNotFoundError("Vocabulary word not found")
        return word
