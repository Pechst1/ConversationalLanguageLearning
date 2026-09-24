"""API router for version 1."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.endpoints import (
    achievements,
    analytics,
    anki,
    atelier,
    audio,
    audio_session,
    auth,
    daily_journey,
    dossier,
    episode_audio,
    feedback,
    forge,
    grammar,
    graphic_novel,
    intake,
    journal,
    missions,
    notifications,
    npcs,
    placement,
    progress,
    rehearsal,
    serial,
    sessions,
    sessions_ws,
    stories,
    story_engine,
    users,
    vocabulary,
)
from app.api.v1.endpoints.atelier import get_atelier_user
from app.core.rate_limit import auth_rate_limit, paid_route_guard

# WP-70: the password doors are limited per IP, and every paid route per learner
# (rate + daily spend cap), at the include so the endpoint modules stay as they
# are. Each guard resolves the same user dependency its router's routes already
# use; FastAPI caches it per request, so nothing is resolved twice.
_paid = [Depends(paid_route_guard(get_current_user))]
_paid_atelier = [Depends(paid_route_guard(get_atelier_user))]

api_router = APIRouter()
api_router.include_router(auth.router, dependencies=[Depends(auth_rate_limit)])
api_router.include_router(feedback.router)
api_router.include_router(users.router)
api_router.include_router(progress.router)
api_router.include_router(sessions.router, dependencies=_paid)
api_router.include_router(sessions_ws.router)
api_router.include_router(vocabulary.router)
api_router.include_router(analytics.router)
api_router.include_router(achievements.router)
api_router.include_router(anki.router)
api_router.include_router(audio.router, prefix="/audio", tags=["audio"], dependencies=_paid)
api_router.include_router(grammar.router)
api_router.include_router(atelier.router, dependencies=_paid_atelier)
api_router.include_router(forge.router, dependencies=_paid_atelier)  # WP-S3 La Forge
api_router.include_router(missions.router, dependencies=_paid_atelier)
api_router.include_router(graphic_novel.router, dependencies=_paid_atelier)
api_router.include_router(serial.router, dependencies=_paid_atelier)
api_router.include_router(audio_session.router, dependencies=_paid)
api_router.include_router(stories.router, prefix="/stories", tags=["stories"], dependencies=_paid)
api_router.include_router(npcs.router, prefix="/npcs", tags=["npcs"])
api_router.include_router(notifications.router)
api_router.include_router(daily_journey.router, dependencies=_paid)
api_router.include_router(dossier.router)
api_router.include_router(placement.router, dependencies=_paid)
api_router.include_router(rehearsal.router, dependencies=_paid)
api_router.include_router(journal.router, dependencies=_paid)
api_router.include_router(intake.router, dependencies=_paid_atelier)

api_router.include_router(story_engine.router)
api_router.include_router(episode_audio.router, dependencies=_paid)
