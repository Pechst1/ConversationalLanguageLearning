"""Document existing untyped projections; do not filter or mutate responses."""

from fastapi import FastAPI
from pydantic import TypeAdapter

from app.schemas.daily_journey import JourneyErrorBody
from app.schemas.story_projection import (
    EpisodeAudioManifestRead,
    StoryEpisodePageRead,
    StoryEpisodeRead,
    StoryPositionRead,
)


def install_projection_schemas(app: FastAPI, prefix: str) -> None:
    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        models = TypeAdapter(tuple[
            StoryEpisodePageRead, StoryEpisodeRead, StoryPositionRead,
            EpisodeAudioManifestRead, JourneyErrorBody,
        ]).json_schema(mode="serialization", ref_template="#/components/schemas/{model}")
        schema["components"]["schemas"].update(models["$defs"])
        projections = (
            ("/story-engine/episodes", "get", StoryEpisodePageRead),
            ("/story-engine/episodes/{scene_id}", "get", StoryEpisodeRead),
            ("/story-engine/episodes/{scene_id}/position", "put", StoryPositionRead),
            ("/story-engine/episodes/{scene_id}/audio", "get", EpisodeAudioManifestRead),
            ("/story-engine/episodes/{scene_id}/audio", "post", EpisodeAudioManifestRead),
        )
        for path, method, model in projections:
            schema["paths"][prefix + path][method]["responses"]["200"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{model.__name__}",
            }
        return schema

    app.openapi = openapi
