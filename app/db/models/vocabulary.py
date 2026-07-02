"""Vocabulary database models."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

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
    frequency_rank = Column(Integer, nullable=True, index=True)

    # Support both German (native) and English translations
    english_translation = Column(Text, nullable=True)
    german_translation = Column(Text, nullable=True)
    french_translation = Column(Text, nullable=True)
    definition = Column(Text)

    example_sentence = Column(Text)
    example_translation = Column(Text)
    usage_notes = Column(Text)

    difficulty_level = Column(Integer, default=1)
    topic_tags = Column(StringList, nullable=True)

    # Anki-specific fields
    direction = Column(String(20), nullable=True)  # "fr_to_de", "de_to_fr"
    linked_word_id = Column(Integer, nullable=True)  # Link to reverse card
    deck_name = Column(String(255), nullable=True)
    note_id = Column(String(50), nullable=True)
    card_id = Column(String(50), nullable=True)
    is_anki_card = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyWord word={self.word!r} language={self.language!r} direction={self.direction!r}>"


class VerbConjugation(Base):
    """Precomputed French conjugation forms for verb drills and coverage rollups."""

    __tablename__ = "verb_conjugations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lemma = Column(String(120), nullable=False, index=True)
    normalized_lemma = Column(String(120), nullable=False, index=True)
    tense = Column(String(80), nullable=False, index=True)
    person = Column(String(20), nullable=False)
    form = Column(String(160), nullable=False)
    auxiliary = Column(String(20), nullable=True)
    verb_group = Column(String(20), nullable=True)
    regularity = Column(String(20), nullable=False, default="regular")
    is_irregular = Column(Boolean, default=False, nullable=False, index=True)
    cefr_band = Column(String(10), default="A1", nullable=False, index=True)
    source = Column(String(40), default="deterministic", nullable=False)
    forms_payload = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("normalized_lemma", "tense", "person", name="uq_verb_conjugation_form"),
        Index("ix_verb_conjugations_lemma_tense", "normalized_lemma", "tense"),
    )


class UserConjugationProgress(Base):
    """FSRS-style progress for one user on one verb x tense conjugation item."""

    __tablename__ = "user_conjugation_progress"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    verb_lemma = Column(String(120), nullable=False)
    normalized_lemma = Column(String(120), nullable=False, index=True)
    tense = Column(String(80), nullable=False, index=True)
    cefr_band = Column(String(10), default="A1", nullable=False, index=True)

    stability = Column(Float, default=0.0)
    difficulty = Column(Float, default=5.0)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=1)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    state = Column(String(20), default="new")
    proficiency_score = Column(Integer, default=0)

    last_review_date = Column(DateTime(timezone=True), nullable=True)
    next_review_date = Column(DateTime(timezone=True), nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    mastered_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "normalized_lemma", "tense", name="uq_user_conjugation_progress_item"),
        Index("ix_user_conjugation_progress_due", "user_id", "next_review_date", "due_date"),
    )
