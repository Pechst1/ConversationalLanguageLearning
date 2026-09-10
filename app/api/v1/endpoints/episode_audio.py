"""WP-32 — «Écouter d'abord»: the radio episode's four routes.

The scene itself is *not* re-published here. Ownership, the engine-version
filter and the public projection all come from
:mod:`app.api.v1.endpoints.story_engine` by import, so there is exactly one
definition of "a scene this learner may read" and the audio can never address a
scene the reader cannot.

Nothing in this router mutates the story. The one write it does perform — the
prediction check — lands beside the reading position in ``source_snapshot``,
which is where the reader already keeps things that are true about the learner's
passage through a scene rather than about the scene itself.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints.story_engine import owned_scene
from app.db.models.episode_audio import EpisodeAudioClip
from app.db.models.user import User
from app.services.episode_audio import (
    PREDICTION_VERDICTS,
    episode_audio_manifest,
    record_prediction_check,
    synthesize_episode_audio,
)

router = APIRouter(prefix="/story-engine/episodes", tags=["story-engine-audio"])


class PredictionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Which of the two offered guesses the learner tapped.
    guess: str = Field(min_length=1, max_length=40)
    #: What the scene's own lines turned out to support, or nothing.
    verdict: str = Field(min_length=1, max_length=40)
    supported: str | None = Field(default=None, max_length=40)


@router.get("/{scene_id}/audio")
def audio_manifest(
    scene_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What is already spoken. Never starts a paid call.

    A client opens with this so that a learner who has listened before — or on
    a second device — hears the episode without spending anything, and so that
    ``status: "disabled"`` reaches the page as data rather than as a 404.
    """

    scene = owned_scene(db, user, scene_id)
    return episode_audio_manifest(db, scene=scene).as_payload()


@router.post("/{scene_id}/audio")
def synthesize_audio(
    scene_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Speak the episode, or say honestly that it is not spoken.

    Idempotent by revision: the second call for the same scene text returns the
    stored clips and makes no request. The row lock is what keeps two devices —
    or a double tap — from paying twice for the same episode.
    """

    scene = owned_scene(db, user, scene_id, lock=True)
    result = synthesize_episode_audio(db, scene=scene)
    if result.status in {"ready", "failed"}:
        db.commit()
    return result.as_payload()


@router.get("/{scene_id}/audio/{clip_id}")
def audio_clip(
    scene_id: UUID,
    clip_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """One spoken line.

    Authorised through the scene, not through the clip's own ``user_id``: the
    scene is the thing the learner is allowed to read, and deriving the answer
    from it means a clip can never outlive that permission.
    """

    scene = owned_scene(db, user, scene_id)
    clip = db.scalar(
        select(EpisodeAudioClip).where(
            EpisodeAudioClip.id == clip_id,
            EpisodeAudioClip.scene_id == scene.id,
        )
    )
    if clip is None:
        raise HTTPException(404, "Episode audio clip not found")
    return Response(
        content=clip.audio,
        media_type=clip.content_type or "audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=episode-line.mp3",
            # Immutable per revision: a changed line is a new clip id, so the
            # browser may hold this forever without ever playing stale audio.
            "Cache-Control": "private, max-age=86400, immutable",
        },
    )


@router.post("/{scene_id}/audio/prediction")
def prediction(
    scene_id: UUID,
    payload: PredictionCheck,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record what the learner predicted before listening.

    Measurement, not marking: the response carries no score, nothing here
    reaches the capability rubric, and an ``unresolved`` scene is stored as
    unresolved rather than counted as a miss.
    """

    if payload.verdict not in PREDICTION_VERDICTS:
        raise HTTPException(422, "Unknown prediction verdict")
    scene = owned_scene(db, user, scene_id, lock=True)
    entry = record_prediction_check(
        db,
        scene=scene,
        guess=payload.guess,
        verdict=payload.verdict,
        supported=payload.supported,
    )
    db.commit()
    return {"scene_id": str(scene.id), "prediction": entry}
