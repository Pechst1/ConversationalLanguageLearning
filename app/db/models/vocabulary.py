"""Vocabulary database models."""
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import StringList


class VocabularyWord(Base):
    """Represents a vocabulary word in the system."""

    __tablename__ = "vocabulary_words"

    id = Column(Integer, primary_key=True)
    language = Column(String(10), nullable=False, index=True)
    word = Column(String(255), nullable=False)
    normalized_word = Column(String(255), nullable=False, index=True)

    part_of_speech = Column(String(50))
    gender = Column(String(10))
    frequency_rank = Column(Integer, nullable=False, index=True)

    english_translation = Column(Text, nullable=False)
    definition = Column(Text)

    example_sentence = Column(Text)
    example_translation = Column(Text)
    usage_notes = Column(Text)

    difficulty_level = Column(Integer, default=1)
    topic_tags = Column(StringList, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyWord word={self.word!r} language={self.language!r}>"
