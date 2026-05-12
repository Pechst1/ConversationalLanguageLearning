"""Pydantic schemas for Graphic Novel / Feuilleton practice."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GraphicNovelCreateRequest(BaseModel):
    cadence: str = Field("ad_hoc", pattern="^(ad_hoc|post_session|weekly)$")
    atelier_session_id: UUID | None = None
    mission_id: UUID | None = None
    personal_input_item_id: UUID | None = None
    preferred_concept_ids: list[int] | None = None
    preferred_errata_ids: list[UUID] | None = None
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
    active_scene: dict[str, Any] | None = None
    available_scene: dict[str, Any] | None = None
    recent_completed: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: dict[str, Any] = Field(default_factory=dict)


class GraphicNovelSceneResponse(BaseModel):
    scene: dict[str, Any]


class GraphicNovelAttemptResponse(BaseModel):
    attempt: dict[str, Any]
    correction: dict[str, Any]
    errata: list[dict[str, Any]] = Field(default_factory=list)
    scene: dict[str, Any]


class GraphicNovelCompleteResponse(BaseModel):
    scene: dict[str, Any]
    recap: dict[str, Any]


__all__ = [
    "GraphicNovelAttemptRequest",
    "GraphicNovelAttemptResponse",
    "GraphicNovelCompleteResponse",
    "GraphicNovelCreateRequest",
    "GraphicNovelSceneResponse",
    "GraphicNovelTodayResponse",
]
