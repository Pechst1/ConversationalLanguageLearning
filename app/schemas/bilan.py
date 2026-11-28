"""Wire schemas for «Le bilan» (``GET /bilan``, ``GET /bilan/card``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _BilanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BilanDay(_BilanModel):
    date: str
    played: bool
    future: bool


class BilanLine(_BilanModel):
    text_fr: str
    date: str
    source: str


class BilanWord(_BilanModel):
    word: str
    gloss: str


class BilanWords(_BilanModel):
    new_count: int
    reviewed_count: int
    held_count: int
    shown: list[BilanWord]


class BilanRule(_BilanModel):
    concept_id: int
    title: str
    title_fr: str
    from_stage: str
    from_label: str | None = None
    stage: str
    stage_label: str | None = None


class BilanEpisode(_BilanModel):
    date: str
    title_fr: str


class BilanDecision(_BilanModel):
    date: str
    label_fr: str
    kind: Literal["choice", "promise", "resolved"]


class BilanStory(_BilanModel):
    episodes: list[BilanEpisode]
    decisions: list[BilanDecision]
    next_fr: str | None = None


class BilanWeekRef(_BilanModel):
    week_start: str
    days_played: int


class Bilan(_BilanModel):
    week_start: str
    week_end: str
    timezone: str
    is_current: bool
    closed: bool
    language: Literal["en", "de", "fr"]
    level: str
    days: list[BilanDay]
    days_played: int
    lines: list[BilanLine]
    words: BilanWords
    rules: list[BilanRule]
    story: BilanStory
    weeks: list[BilanWeekRef]
    previous_week_start: str | None = None
    next_week_start: str | None = None


class BilanCard(_BilanModel):
    week_start: str | None = None
    days_played: int
