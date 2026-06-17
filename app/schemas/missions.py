"""Pydantic schemas for real-world scenario missions."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VocabularyCreditSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    seen_context: int = 0
    recognized: int = 0
    produced_correct: int = 0
    produced_incorrect: int = 0
    missed_target: int = 0


class TargetVocabularyRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    word_id: int
    word: str
    translation: str | None = None
    bucket: str | None = None
    scheduler: str | None = None
    priority_score: float | None = None
    example_sentence: str | None = None
    example_translation: str | None = None


class VocabularyEventRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    word_id: int
    event_type: str
    reason: str | None = None


class LinkedVocabularyErratumRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    linked_word_id: int | None = None
    error_category: str | None = None
    review_mode: str | None = None
    task_error_type: str | None = None


class MissionCorrectionRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    errata: list[LinkedVocabularyErratumRead] = Field(default_factory=list)
    vocabulary_events: list[VocabularyEventRead] = Field(default_factory=list)


class MissionRecapRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    vocabulary_credit: VocabularyCreditSummary = Field(default_factory=VocabularyCreditSummary)


class MissionRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    status: str
    cadence: str
    mission_type: str
    mission_format: str = "chat_message"
    stakes_level: int = 1
    atelier_session_id: UUID | None = None
    serial_thread_id: UUID | None = None
    episode_index: int | None = None
    iso_year: int | None = None
    iso_week: int | None = None
    title: str
    brief: str
    selected_concept_ids: list[int] = Field(default_factory=list)
    target_errata_ids: list[UUID] = Field(default_factory=list)
    target_vocabulary_ids: list[int] = Field(default_factory=list)
    target_vocabulary: list[TargetVocabularyRead] = Field(default_factory=list)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    objectives: list[dict[str, Any]] = Field(default_factory=list)
    prompt_payload: dict[str, Any] = Field(default_factory=dict)
    recap: MissionRecapRead = Field(default_factory=MissionRecapRead)
    outcome: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    turns: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class MissionCreateRequest(BaseModel):
    mission_type: str = Field(
        "message",
        pattern="^(message|explain_plan|news_summary|travel_work|conversation)$",
    )
    cadence: str = Field("weekly", pattern="^(weekly|post_session|ad_hoc)$")
    atelier_session_id: UUID | None = None
    serial_thread_id: UUID | None = None
    episode_index: int | None = None
    preferred_concept_ids: list[int] | None = None
    preferred_errata_ids: list[UUID] | None = None
    preferred_vocabulary_ids: list[int] | None = None
    use_news: bool = False
    custom_scenario: str | None = Field(None, max_length=1200)
    desired_outcome: str | None = Field(None, max_length=400)
    relationship: str | None = Field(None, max_length=120)
    target_register: str | None = Field(None, alias="register", max_length=80)
    stakes_level: int | None = Field(None, ge=1, le=3)


class MissionSubmitRequest(BaseModel):
    text: str = Field("", max_length=5000)
    mode: str = Field("writing", pattern="^(writing|chat|voice)$")


class MissionTurnRequest(BaseModel):
    text: str = Field("", max_length=3000)
    mode: str = Field("chat", pattern="^(chat|voice)$")
    transcript_metadata: dict[str, Any] = Field(default_factory=dict)


class MissionTodayResponse(BaseModel):
    weekly_mission: MissionRead | None = None
    post_session_recommendation: MissionRead | None = None
    active_mission: MissionRead | None = None
    recent_completed: list[MissionRead] = Field(default_factory=list)


class MissionResponse(BaseModel):
    mission: MissionRead


class MissionAttemptResponse(BaseModel):
    attempt: dict[str, Any]
    correction: MissionCorrectionRead
    errata: list[LinkedVocabularyErratumRead] = Field(default_factory=list)
    mission: MissionRead


class MissionTurnResponse(BaseModel):
    user_turn: dict[str, Any]
    assistant_turn: dict[str, Any]
    correction: MissionCorrectionRead
    errata: list[LinkedVocabularyErratumRead] = Field(default_factory=list)
    mission: MissionRead
    outcome: dict[str, Any] = Field(default_factory=dict)


class MissionCompleteResponse(BaseModel):
    mission: MissionRead
    recap: MissionRecapRead


__all__ = [
    "MissionAttemptResponse",
    "MissionCompleteResponse",
    "MissionCorrectionRead",
    "MissionCreateRequest",
    "MissionRead",
    "MissionRecapRead",
    "MissionResponse",
    "MissionSubmitRequest",
    "LinkedVocabularyErratumRead",
    "MissionTodayResponse",
    "MissionTurnRequest",
    "MissionTurnResponse",
    "TargetVocabularyRead",
    "VocabularyCreditSummary",
    "VocabularyEventRead",
]
