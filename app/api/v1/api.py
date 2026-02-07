"""API router for version 1."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    achievements,
    analytics,
    anki,
    audio,
    audio_session,
    auth,
    daily_practice,
    grammar,
    grammar_exercise,
    progress,
    sessions,
    sessions_ws,
    stories,
    users,
    vocabulary,
)


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(progress.router)
api_router.include_router(sessions.router)
api_router.include_router(sessions_ws.router)
api_router.include_router(vocabulary.router)
api_router.include_router(analytics.router)
api_router.include_router(achievements.router)
api_router.include_router(anki.router)
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])
api_router.include_router(grammar.router)
api_router.include_router(grammar_exercise.router)
api_router.include_router(audio_session.router)
api_router.include_router(daily_practice.router)
api_router.include_router(stories.router, prefix="/stories", tags=["stories"])

# Import npcs after stories since it's related
from app.api.v1.endpoints import npcs
from app.api.v1.endpoints import notifications

api_router.include_router(npcs.router, prefix="/npcs", tags=["npcs"])
api_router.include_router(notifications.router)