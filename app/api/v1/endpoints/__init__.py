"""API endpoint modules for v1."""

from app.api.v1.endpoints import (
    achievements,
    analytics,
    auth,
    progress,
    sessions,
    sessions_ws,
    users,
    vocabulary,
)

__all__ = [
    "achievements",
    "analytics",
    "auth",
    "progress",
    "sessions",
    "sessions_ws",
    "users",
    "vocabulary",
]
