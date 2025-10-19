"""API router for version 1."""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, progress, users, vocabulary


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(progress.router)
api_router.include_router(vocabulary.router)
