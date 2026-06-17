"""Service helpers for vocabulary endpoints."""
from __future__ import annotations

import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.vocabulary import VocabularyWord


class VocabularyNotFoundError(ValueError):
    """Raised when a vocabulary item cannot be located."""


class VocabularyService:
    """Provide querying utilities for vocabulary datasets."""

    def __init__(self, db: Session):
        self.db = db

    def list_words(
        self, *, language: str | None, limit: int, offset: int, search: str | None = None
    ) -> list[VocabularyWord]:
        """Return a slice of vocabulary ordered by frequency rank."""

        stmt = self._filtered_select(language=language, search=search).order_by(
            VocabularyWord.frequency_rank.asc().nullslast(),
            VocabularyWord.id.asc(),
        )
        stmt = stmt.offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    def count_words(self, *, language: str | None, search: str | None = None) -> int:
        """Return the number of vocabulary items matching the filter."""

        stmt = select(func.count()).select_from(VocabularyWord)
        if language:
            stmt = stmt.where(VocabularyWord.language == language)
        search_filter = self._search_filter(search)
        if search_filter is not None:
            stmt = stmt.where(search_filter)
        return int(self.db.scalar(stmt) or 0)

    def _filtered_select(self, *, language: str | None, search: str | None = None):
        stmt = select(VocabularyWord)
        if language:
            stmt = stmt.where(VocabularyWord.language == language)
        search_filter = self._search_filter(search)
        if search_filter is not None:
            stmt = stmt.where(search_filter)
        return stmt

    @staticmethod
    def _search_filter(search: str | None):
        value = (search or "").strip()
        if not value:
            return None
        normalized = _normalize(value)
        like = f"%{value.lower()}%"
        normalized_like = f"%{normalized}%"
        return or_(
            func.lower(VocabularyWord.word).like(like),
            VocabularyWord.normalized_word.like(normalized_like),
            func.lower(func.coalesce(VocabularyWord.german_translation, "")).like(like),
            func.lower(func.coalesce(VocabularyWord.english_translation, "")).like(like),
            func.lower(func.coalesce(VocabularyWord.french_translation, "")).like(like),
            func.lower(func.coalesce(VocabularyWord.definition, "")).like(like),
        )

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


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_form = decomposed.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_form.lower().split())
