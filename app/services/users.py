"""Service layer for user operations."""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.services.journey_rhythm import rhythm_of
from app.services.vocabulary_pace import RHYTHM_NEW_WORDS
from app.utils.cache import build_cache_key, cache_backend


class UserNotFoundError(ValueError):
    """Raised when a user lookup fails."""


class UserService:
    """Encapsulates reusable user-related data access operations."""

    def __init__(self, db: Session, *, image_storage: Any | None = None):
        self.db = db
        # Injected in tests; defaults to the configured Feuilleton image store.
        self._image_storage = image_storage

    def get(self, user_id: uuid.UUID) -> User:
        """Return a user by identifier or raise ``UserNotFoundError``."""

        user = self.db.get(User, user_id)
        if not user:
            raise UserNotFoundError("User not found")
        return user

    def update(self, user: User, payload: Any) -> User:
        """Persist user profile changes and return the updated entity."""

        update_data = payload.model_dump(exclude_unset=True)
        if "interests" in update_data and update_data["interests"] is not None:
            parts: list[str] = []
            seen: set[str] = set()
            for item in str(update_data["interests"]).split(","):
                normalized = item.strip().lower()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                parts.append(normalized)
            update_data["interests"] = ",".join(parts[:20])
        # WP-L6: the rhythm is written as its minutes (`User.rhythm`), after any
        # raw minutes in the same payload so the named choice wins.
        rhythm = update_data.pop("rhythm", None)
        if rhythm is not None:
            update_data["rhythm"] = rhythm
        rhythm_before = rhythm_of(user)
        for field, value in update_data.items():
            setattr(user, field, value)
        # 2026-10-03: a new rhythm brings its own daily word intake (Léger 5,
        # Régulier 10, Soutenu 18, Intensif 30) unless this same request sets
        # the number of new words itself.
        if "new_words_per_day" not in update_data and rhythm_of(user) != rhythm_before:
            user.new_words_per_day = RHYTHM_NEW_WORDS[rhythm_of(user)]

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        cache_backend.invalidate("user:profile", key=build_cache_key(user_id=str(user.id)))
        return user

    def delete(self, user: User) -> None:
        """Permanently delete a user and their associated data.

        Relational rows go with the user (ON DELETE CASCADE). The learner's
        personalised artwork lives outside the database (S3 bucket or the local
        image directory), so its scene ids are read first and the stored objects
        are removed after the commit: best effort and logged, never blocking the
        deletion itself.
        """

        user_id = user.id
        scene_ids = list(
            self.db.scalars(select(GraphicNovelScene.id).where(GraphicNovelScene.user_id == user_id))
        )

        # Invalidate cache before deletion
        cache_backend.invalidate("user:profile", key=build_cache_key(user_id=str(user_id)))

        self.db.delete(user)
        self.db.commit()

        self._purge_artwork(user_id, scene_ids)

    def _purge_artwork(self, user_id: uuid.UUID, scene_ids: list[uuid.UUID]) -> None:
        if not scene_ids:
            return
        try:
            storage = self._image_storage
            if storage is None:
                from app.services.graphic_novel_image_storage import GraphicNovelImageStorage

                storage = GraphicNovelImageStorage()
            removed = storage.delete_scene_objects(scene_ids)
        except Exception as exc:  # noqa: BLE001 - the account is already gone; log and move on
            logger.bind(event_name="account_artwork_cleanup_failed", user_id=str(user_id)).warning(
                "Account deleted but its artwork cleanup failed: {}", exc
            )
            return
        logger.bind(
            event_name="account_artwork_cleanup",
            user_id=str(user_id),
            scenes=len(scene_ids),
            objects=removed,
        ).info("Account artwork removed")

    def list_users(self, limit: int = 50, offset: int = 0) -> list[User]:
        """Return paginated users sorted by creation date."""

        stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))
