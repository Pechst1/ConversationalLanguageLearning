"""Pydantic schemas for real-world scenario missions."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MissionCreateRequest(BaseModel):
    mission_type: str = Field(
        "message",
        pattern="^(message|explain_plan|news_summary|travel_work|conversation)$",
    )
    cadence: str = Field("weekly", pattern="^(weekly|post_session|ad_hoc)$")
    atelier_session_id: UUID | None = None
    preferred_concept_ids: list[int] | None = None
    preferred_errata_ids: list[UUID] | None = None
    use_news: bool = False
    custom_scenario: str | None = Field(None, max_length=1200)
    desired_outcome: str | None = Field(None, max_length=400)
    relationship: str | None = Field(None, max_length=120)
    target_register: str | None = Field(None, alias="register", max_length=80)


class MissionSubmitRequest(BaseModel):
    text: str = Field("", max_length=5000)
    mode: str = Field("writing", pattern="^(writing|chat|voice)$")


class MissionTurnRequest(BaseModel):
    text: str = Field("", max_length=3000)
    mode: str = Field("chat", pattern="^(chat|voice)$")
    transcript_metadata: dict[str, Any] = Field(default_factory=dict)


class MissionTodayResponse(BaseModel):
    weekly_mission: dict[str, Any] | None = None
    post_session_recommendation: dict[str, Any] | None = None
    active_mission: dict[str, Any] | None = None
    recent_completed: list[dict[str, Any]] = Field(default_factory=list)


class MissionResponse(BaseModel):
    mission: dict[str, Any]


class MissionAttemptResponse(BaseModel):
    attempt: dict[str, Any]
    correction: dict[str, Any]
    errata: list[dict[str, Any]] = Field(default_factory=list)
    mission: dict[str, Any]


class MissionTurnResponse(BaseModel):
    user_turn: dict[str, Any]
    assistant_turn: dict[str, Any]
    correction: dict[str, Any]
    errata: list[dict[str, Any]] = Field(default_factory=list)
    mission: dict[str, Any]


class MissionCompleteResponse(BaseModel):
    mission: dict[str, Any]
    recap: dict[str, Any]


__all__ = [
    "MissionAttemptResponse",
    "MissionCompleteResponse",
    "MissionCreateRequest",
    "MissionResponse",
    "MissionSubmitRequest",
    "MissionTodayResponse",
    "MissionTurnRequest",
    "MissionTurnResponse",
]
