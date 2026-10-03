"""Wire schemas for La Radio (WP-122 A): ``GET /revue/radio/week``,
``GET /revue/radio/{dossier_id}``, ``POST /revue/radio/{dossier_id}/dictee`` and
``POST /revue/radio/{dossier_id}/heard``. Snake case, parsed by ``web-frontend/lib/radio-types.ts``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RadioLineRole = Literal["lede", "claim", "uncertainty", "guest", "signoff"]
RadioAudio = Literal["ready", "unavailable", "text_only"]
RadioDicteeOutcome = Literal["met", "partially_met", "not_yet"]


class _RadioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RadioItem(_RadioModel):
    dossier_id: str
    title_fr: str
    topic: str
    evergreen: bool


class RadioWeekView(_RadioModel):
    week: str
    current: RadioItem | None
    queue: list[RadioItem]
    heard: list[str]
    heard_today: bool
    #: La Une's chip: an unheard bulletin and none heard today.
    chip: bool
    #: The estimated length the chip prints («La Radio · 50 s»), rounded to 5 s.
    seconds: int | None = None


class RadioLine(_RadioModel):
    index: int
    speaker: str
    speaker_name: str
    role: RadioLineRole
    text_fr: str
    #: ``/api/v1/daily-journeys/line-audio/{clip_id}`` — the learner's own clip; null unless ``audio`` is ready.
    clip_url: str | None = None
    claim_id: str | None = None


class RadioStage(_RadioModel):
    plate_url: str | None
    place_fr: str


class RadioDictee(_RadioModel):
    line_index: int
    #: How many words the line has (the hint the dictation format gives).
    words: int


class RadioBulletinView(_RadioModel):
    dossier_id: str
    title_fr: str
    topic: str
    band: str
    week: str
    seconds: float
    audio: RadioAudio
    guest_id: str
    lines: list[RadioLine]
    dictee: RadioDictee
    stage: RadioStage


class RadioDicteeRequest(_RadioModel):
    text: str = Field(default="", max_length=600)
    band: str | None = None


class RadioDicteeResult(_RadioModel):
    outcome: RadioDicteeOutcome
    expected_fr: str
    note: str | None = None


class RadioHeardRequest(_RadioModel):
    band: str | None = None
    dictee: RadioDicteeOutcome | None = None
