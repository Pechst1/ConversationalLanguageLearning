"""Pydantic schemas for vocabulary endpoints."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VocabularyWordRead(BaseModel):
    """Representation of a vocabulary word."""

    id: int
    language: str = Field(max_length=10)
    word: str
    normalized_word: str
    part_of_speech: Optional[str] = None
    gender: Optional[str] = None
    frequency_rank: int
    english_translation: str
    definition: Optional[str] = None
    example_sentence: Optional[str] = None
    example_translation: Optional[str] = None
    usage_notes: Optional[str] = None
    difficulty_level: int
    topic_tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class VocabularyListResponse(BaseModel):
    """Paginated vocabulary response payload."""

    total: int
    items: list[VocabularyWordRead]
