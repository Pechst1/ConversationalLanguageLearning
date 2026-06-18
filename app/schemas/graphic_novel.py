"""Pydantic schemas for Graphic Novel / Feuilleton practice."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.missions import (
    LinkedVocabularyErratumRead,
    MissionCorrectionRead,
    TargetVocabularyRead,
    VocabularyCreditSummary,
)


class GraphicNovelRecapRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    vocabulary_credit: VocabularyCreditSummary = Field(default_factory=VocabularyCreditSummary)


class GraphicNovelPanelRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    panel_index: int
    title: str
    beat: str
    image_prompt: str
    image_url: str | None = None
    image_payload: dict[str, Any] = Field(default_factory=dict)
    audio_payload: dict[str, Any] = Field(default_factory=dict)
    overlay_payload: dict[str, Any] = Field(default_factory=dict)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class GraphicNovelSceneRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    status: str
    cadence: str
    atelier_session_id: UUID | None = None
    mission_id: UUID | None = None
    serial_thread_id: UUID | None = None
    episode_index: int | None = None
    personal_input_item_id: UUID | None = None
    title: str
    brief: str
    selected_concept_ids: list[int] = Field(default_factory=list)
    target_errata_ids: list[UUID] = Field(default_factory=list)
    target_vocabulary_ids: list[int] = Field(default_factory=list)
    target_vocabulary: list[TargetVocabularyRead] = Field(default_factory=list)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    script_payload: dict[str, Any] = Field(default_factory=dict)
    hook: dict[str, Any] = Field(default_factory=dict)
    recap: GraphicNovelRecapRead = Field(default_factory=GraphicNovelRecapRead)
    cache_key: str
    prompt_version: str
    image_model: str
    image_quality: str
    panels: list[GraphicNovelPanelRead] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class GraphicNovelCreateRequest(BaseModel):
    cadence: str = Field("ad_hoc", pattern="^(ad_hoc|post_session|weekly)$")
    atelier_session_id: UUID | None = None
    mission_id: UUID | None = None
    serial_thread_id: UUID | None = None
    episode_index: int | None = None
    personal_input_item_id: UUID | None = None
    preferred_concept_ids: list[int] | None = None
    preferred_errata_ids: list[UUID] | None = None
    target_vocabulary_ids: list[int] | None = None
    use_news: bool = False
    panel_count: int | None = Field(None, description="Requested Feuilleton length: 4, 6, or 8 panels")
    story_quality: str = Field("standard", pattern="^(standard|premium)$")
    humor_style: str = Field("satirical", pattern="^(dry|satirical|absurd)$")
    experience_mode: str = Field("study", pattern="^(study|reward)$")
    render_mode: str = Field("panels", pattern="^(page|panels)$")
    image_quality: str | None = Field(None, pattern="^(low|medium|high)$")
    public_figure_mode: str = Field("named_context", pattern="^(off|named_context|editorial_caricature)$")
    force_new: bool = False
    refresh_news: bool = False

    @field_validator("panel_count")
    @classmethod
    def validate_panel_count(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value not in {4, 6, 8}:
            raise ValueError("panel_count must be 4, 6, or 8")
        return value


class GraphicNovelAttemptRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=120)
    answer_payload: dict[str, Any] = Field(default_factory=dict)


class GraphicNovelTodayResponse(BaseModel):
    active_scene: GraphicNovelSceneRead | None = None
    available_scene: GraphicNovelSceneRead | None = None
    recent_completed: list[GraphicNovelSceneRead] = Field(default_factory=list)
    recommendation: dict[str, Any] = Field(default_factory=dict)


class GraphicNovelSceneResponse(BaseModel):
    scene: GraphicNovelSceneRead


class GraphicNovelAttemptResponse(BaseModel):
    attempt: dict[str, Any]
    correction: MissionCorrectionRead
    errata: list[LinkedVocabularyErratumRead] = Field(default_factory=list)
    scene: GraphicNovelSceneRead


class GraphicNovelCompleteResponse(BaseModel):
    scene: GraphicNovelSceneRead
    recap: GraphicNovelRecapRead
    next_serial: dict[str, Any] | None = None


__all__ = [
    "GraphicNovelAttemptRequest",
    "GraphicNovelAttemptResponse",
    "GraphicNovelCompleteResponse",
    "GraphicNovelCreateRequest",
    "GraphicNovelPanelRead",
    "GraphicNovelRecapRead",
    "GraphicNovelSceneRead",
    "GraphicNovelSceneResponse",
    "GraphicNovelTodayResponse",
]
