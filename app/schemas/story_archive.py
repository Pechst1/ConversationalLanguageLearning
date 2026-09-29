"""WP-96 «Les Cahiers du feuilleton» — ``GET /story-engine/archive``."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.daily_journey import MarginNote


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArchivePanelLine(_Model):
    character_id: str
    character_name: str | None = None
    text_fr: str


class ArchivePanel(_Model):
    """One panel of an authored day's page (the first day, a fallback day)."""

    id: str
    index: int
    narration_fr: str = ""
    dialogue: list[ArchivePanelLine] = Field(default_factory=list)
    image_url: str | None = None


class ArchiveDay(_Model):
    """One planche: a day the learner lived, engine-written or authored."""

    date: str
    journey_id: str
    #: The engine scene (open it in the reader); ``None`` on an authored day.
    scene_id: str | None = None
    title_fr: str
    edition_no: int | None = None
    image_url: str | None = None
    character_id: str | None = None
    #: «La réplique de l'abonné·e» — the learner's own lines, oldest first.
    learner_lines: list[str] = Field(default_factory=list)
    ending_fr: str | None = None
    margin_notes: list[MarginNote] = Field(default_factory=list)
    can_do_id: str | None = None
    special: Literal["epreuve"] | None = None
    #: True for the authored first day and authored fallback days.
    authored: bool = False
    #: An authored day's own page; ``None`` for engine days (use ``scene_id``).
    panels: list[ArchivePanel] | None = None


class ArchiveChapter(_Model):
    index: int
    title_fr: str
    digest_fr: str | None = None
    closed: bool = False
    #: The season's last chapter (its close makes the season a «Tome»).
    finale: bool = False
    #: The days before the story engine's first chapter.
    prologue: bool = False
    days: list[ArchiveDay] = Field(default_factory=list)


class ArchiveSeason(_Model):
    number: int
    title_fr: str
    finished: bool = False
    #: Only the requested season carries its chapters (``?season=N``).
    loaded: bool = False
    day_count: int = 0
    chapters: list[ArchiveChapter] = Field(default_factory=list)


class ArchiveCurrent(_Model):
    season: int
    chapter: int | None = None


class StoryArchive(_Model):
    seasons: list[ArchiveSeason] = Field(default_factory=list)
    current: ArchiveCurrent


__all__ = [
    "ArchiveChapter",
    "ArchiveCurrent",
    "ArchiveDay",
    "ArchivePanel",
    "ArchiveSeason",
    "StoryArchive",
]
