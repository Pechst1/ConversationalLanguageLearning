"""Pydantic schemas for Atelier practice."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AtelierConceptRead(BaseModel):
    id: int
    external_id: str | None = None
    name: str
    level: str
    category: str | None = None
    subskill: str | None = None
    core_rule: str | None = None
    main_traps: list[str] = Field(default_factory=list)
    anchor_examples: list[str] = Field(default_factory=list)
    exercise_tags: list[str] = Field(default_factory=list)
    is_foundation: bool = False
    role: str | None = None
    mastery: float = 0
    next_review: str | None = None
    due_errata: list[dict[str, Any]] = Field(default_factory=list)
    atelier_blueprint: dict[str, Any] = Field(default_factory=dict)


class AtelierTodayResponse(BaseModel):
    concepts: list[AtelierConceptRead]
    quote: dict[str, Any]
    summary: dict[str, Any]
    atlas: list[dict[str, Any]]
    due_errata: list[dict[str, Any]] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    cefr: dict[str, Any] = Field(default_factory=dict)
    onboarding: dict[str, Any] = Field(default_factory=dict)
    library_episode: dict[str, Any] | None = None
    serial_episode: dict[str, Any] | None = None
    serial: dict[str, Any] | None = None


class AtelierSessionStartRequest(BaseModel):
    concept_ids: list[int] | None = None
    preferred_concept_id: int | None = None
    preferred_vocabulary_ids: list[int] | None = None


class AtelierSessionStartResponse(BaseModel):
    session_id: UUID
    status: str
    concepts: list[AtelierConceptRead]
    quote: dict[str, Any]
    exercise_sets: list[dict[str, Any]]
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    submitted_map: dict[str, bool] = Field(default_factory=dict)
    current_position: dict[str, Any] = Field(default_factory=dict)
    due_errata: list[dict[str, Any]] = Field(default_factory=list)
    target_vocabulary_ids: list[int] = Field(default_factory=list)
    target_vocabulary: list[dict[str, Any]] = Field(default_factory=list)
    recap: dict[str, Any] = Field(default_factory=dict)


class AtelierActiveSessionResponse(BaseModel):
    session: AtelierSessionStartResponse | None = None


class AtelierAttemptRequest(BaseModel):
    concept_id: int | None = None
    round: str = Field(..., pattern="^(recognize|transform|sentence|produce|speak|conversation)$")
    mode: str
    exercise_id: str
    answer_payload: dict[str, Any] = Field(default_factory=dict)
    resubmit: bool = False


class AtelierCollectibleRead(BaseModel):
    id: UUID
    kind: str
    minted_at: str | None = None
    source_kind: str
    source_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    composed: bool = False
    composed_into_id: UUID | None = None


class AtelierPlateRead(AtelierCollectibleRead):
    members: list[AtelierCollectibleRead] = Field(default_factory=list)


class AtelierWorkshopProgressRead(BaseModel):
    target: str
    member_kind: str
    required: int
    available: int
    progress: int
    shortfall: int


class AtelierAlmanacResponse(BaseModel):
    collectibles: dict[str, list[AtelierCollectibleRead]] = Field(default_factory=dict)
    progress: dict[str, AtelierWorkshopProgressRead] = Field(default_factory=dict)
    plates: list[AtelierPlateRead] = Field(default_factory=list)
    totals: dict[str, int] = Field(default_factory=dict)


class AtelierWorkshopComposeRequest(BaseModel):
    target: Literal["plate_semaine", "plate_chapter", "colophon"]


class AtelierWorkshopComposeResponse(BaseModel):
    plate: AtelierCollectibleRead
    members: list[AtelierCollectibleRead] = Field(default_factory=list)
    progress: dict[str, AtelierWorkshopProgressRead] = Field(default_factory=dict)
    minted_collectibles: list[AtelierCollectibleRead] = Field(default_factory=list)


class AtelierAttemptResponse(BaseModel):
    attempt_id: UUID
    verdict: str
    score_0_4: float
    correction: dict[str, Any]
    ai_review: dict[str, Any] = Field(default_factory=dict)
    minted_collectibles: list[AtelierCollectibleRead] = Field(default_factory=list)


class AtelierExerciseReportRequest(BaseModel):
    session_id: UUID | None = None
    concept_id: int | None = None
    exercise_set_id: UUID | None = None
    round: str | None = Field(None, max_length=30)
    mode: str | None = Field(None, max_length=40)
    exercise_id: str | None = Field(None, max_length=160)
    item_id: str | None = Field(None, max_length=120)
    reason: str = Field(..., min_length=3, max_length=500)


class AtelierExerciseReportResponse(BaseModel):
    ok: bool
    event_id: UUID


class AtelierCompleteResponse(BaseModel):
    session_id: UUID
    recap: dict[str, Any]
    minted_collectibles: list[AtelierCollectibleRead] = Field(default_factory=list)


class AtelierErrataReviewRequest(BaseModel):
    rating: int = Field(4, ge=1, le=4)
    repaired: bool = True


class AtelierErrataReviewResponse(BaseModel):
    erratum: dict[str, Any]


class AtelierErrataTaskResponse(BaseModel):
    task: dict[str, Any]


class AtelierErrataAttemptRequest(BaseModel):
    answer_text: str = ""


class AtelierErrataAttemptResponse(BaseModel):
    verdict: str
    score_0_4: float
    is_correct: bool
    answer_text: str
    target_answer: str
    feedback: str
    closure: dict[str, Any] | None = None
    erratum: dict[str, Any]
    task: dict[str, Any]


__all__ = [
    "AtelierAlmanacResponse",
    "AtelierErrataAttemptRequest",
    "AtelierErrataAttemptResponse",
    "AtelierAttemptRequest",
    "AtelierAttemptResponse",
    "AtelierActiveSessionResponse",
    "AtelierCollectibleRead",
    "AtelierCompleteResponse",
    "AtelierConceptRead",
    "AtelierErrataReviewRequest",
    "AtelierErrataReviewResponse",
    "AtelierErrataTaskResponse",
    "AtelierExerciseReportRequest",
    "AtelierExerciseReportResponse",
    "AtelierSessionStartRequest",
    "AtelierSessionStartResponse",
    "AtelierTodayResponse",
    "AtelierWorkshopComposeRequest",
    "AtelierWorkshopComposeResponse",
    "AtelierWorkshopProgressRead",
]
