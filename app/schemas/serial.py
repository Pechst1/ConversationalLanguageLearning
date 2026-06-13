"""Pydantic schemas for the Serial World spine."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorldBibleRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    logline: str | None = None
    setting: dict[str, Any] = Field(default_factory=dict)
    protagonist: dict[str, Any] = Field(default_factory=dict)
    cast: list[dict[str, Any]] = Field(default_factory=list)
    register_map: dict[str, Any] = Field(default_factory=dict)
    season_arcs: list[dict[str, Any]] = Field(default_factory=list)


class SerialStateRead(BaseModel):
    model_config = ConfigDict(extra="allow")


class StateDelta(BaseModel):
    model_config = ConfigDict(extra="allow")

    set: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    source: dict[str, Any] = Field(default_factory=dict)


class ArcStage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    summary: str
    sets: dict[str, Any] = Field(default_factory=dict)
    entry_requires: dict[str, Any] = Field(default_factory=dict)
    tentpole: bool = False


class SeasonArc(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    characters: list[str] = Field(default_factory=list)
    stages: list[ArcStage] = Field(default_factory=list)
    min_episodes_between_stages: int = 3


class ArcStateEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage: str | None = None
    stage_index: int = -1
    advanced_at_episode: int = -1


class RelationshipEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    closeness: int = Field(0, ge=0, le=5)
    register: str = "vous"
    register_switch_episode: int | None = None
    last_summary: str = ""
    callbacks: list[str] = Field(default_factory=list, max_length=5)


class EpisodePlot(BaseModel):
    model_config = ConfigDict(extra="allow")

    arc_id: str | None = None
    stage_id: str | None = None
    stage_summary: str = ""
    characters: list[str] = Field(default_factory=list)


class EpisodeBPlot(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str = "everyday"
    seed: str = ""


class EpisodeBrief(BaseModel):
    model_config = ConfigDict(extra="allow")

    episode_index: int
    beat: Literal["act", "see", "mission", "feuilleton"]
    mission_format: Literal["chat_message", "voicemail_reply", "email_formal", "admin_form", "phone_call"] = "chat_message"
    a_plot: EpisodePlot = Field(default_factory=EpisodePlot)
    b_plot: EpisodeBPlot = Field(default_factory=EpisodeBPlot)
    required_cast: list[str] = Field(default_factory=list)
    location_id: str | None = None
    structure: Literal["ensemble", "two_hander", "bottle", "callback_open", "news_edition"] = "ensemble"
    include_news_panel: bool = False
    include_choice_fork: bool = False
    stakes_level: int = 1
    hook_guidance: str = ""
    tentpole_reference: str | None = None
    next_beat_kind: Literal["mission", "feuilleton"] = "mission"


class HookRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = ""
    unresolved_question: str = ""
    next_beat_kind: Literal["mission", "feuilleton"] = "mission"
    teaser: str = ""


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    thread_id: UUID
    episode_index: int
    kind: Literal["mission", "feuilleton"]
    mission_id: UUID | None = None
    scene_id: UUID | None = None
    hook_from_previous: dict[str, Any] | None = None
    status: Literal["available", "in_progress", "completed"] | str = "available"
    location_id: str | None = None
    brief_payload: dict[str, Any] = Field(default_factory=dict)


class SerialThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: UUID
    user_id: UUID
    status: str = "active"
    world_bible: WorldBibleRead = Field(default_factory=WorldBibleRead)
    state: dict[str, Any] = Field(default_factory=dict)
    news_seed: dict[str, Any] = Field(default_factory=dict)
    current_episode_index: int = 0
    episodes: list[EpisodeRead] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SerialThreadCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    world_bible: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    news_seed: dict[str, Any] | None = None


class SerialAdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    mission_id: UUID | None = None
    scene_id: UUID | None = None
    state_delta: StateDelta | dict[str, Any] | None = None
    hook: HookRead | dict[str, Any] | None = None


class SerialAvatarRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: Literal["avatar", "pov"] = "avatar"
    description: str = Field(default="", max_length=500)
    reference_images: list[str] = Field(default_factory=list, max_length=3)
    avatar_builder: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ArcStage",
    "ArcStateEntry",
    "EpisodeBPlot",
    "EpisodeBrief",
    "EpisodePlot",
    "EpisodeRead",
    "HookRead",
    "RelationshipEntry",
    "SerialAdvanceRequest",
    "SerialAvatarRequest",
    "SerialStateRead",
    "SerialThreadCreateRequest",
    "SerialThreadRead",
    "SeasonArc",
    "StateDelta",
    "WorldBibleRead",
]
