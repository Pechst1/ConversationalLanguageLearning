"""Public reader/audio DTOs, documented without changing the story router.

The reader projection remains in story_engine.public_scene. These models describe
its output for OpenAPI; E-5 tests validate actual projections against them.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProjectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GrammarMarkRead(ProjectionModel):
    unit_id: str | int
    start: int
    end: int


class StoryDialogueRead(ProjectionModel):
    character_id: str
    character_name: str | None = None
    text_fr: str
    grammar_marks: list[GrammarMarkRead] | None = None


class StoryPanelRead(ProjectionModel):
    id: str
    index: int
    narration_fr: str
    dialogue: list[StoryDialogueRead]
    image_url: str | None
    image_status: Literal["panel_art", "rendering", "setting_reference", "unavailable"]
    alt_native: str | None = None


class GrammarFocusRead(ProjectionModel):
    unit_id: str
    title_fr: str
    title_native: str
    woven: bool


class StoryChapterRead(ProjectionModel):
    id: str
    title_fr: str
    shape: str | None = None
    letter_beat: str | None = None
    finale: bool | None = None
    interlude: bool | None = None


class StoryResolutionRead(ProjectionModel):
    text_fr: str | None
    summary_native: str | None


class StoryEpisodeRead(ProjectionModel):
    id: str
    scene_id: str
    serial_thread_id: str
    serial_episode_id: str | None
    journey_id: str | None
    title_fr: str
    status: Literal["available", "completed", "abandoned"]
    chapter: StoryChapterRead | None
    panel_index: int
    panels: list[StoryPanelRead]
    resolution: StoryResolutionRead | None
    grammar_focus: GrammarFocusRead | None


class StoryEpisodePageRead(ProjectionModel):
    episodes: list[StoryEpisodeRead]
    next_cursor: str | None


class StoryPositionRead(ProjectionModel):
    scene_id: str
    panel_index: int


class EpisodeAudioClipRead(ProjectionModel):
    id: str
    line_key: str
    ordinal: int
    character_id: str
    voice: str
    content_type: str
    char_count: int
    text_fr: str


class EpisodeAudioManifestRead(ProjectionModel):
    status: Literal["disabled", "absent", "empty", "ready", "failed"]
    revision: str
    clips: list[EpisodeAudioClipRead]
    truncated: bool
    reason: str
