"""Service layer for user operations."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.schemas.user import UserUpdate


class UserNotFoundError(ValueError):
    """Raised when a user lookup fails."""


class UserService:
    """Encapsulates reusable user-related data access operations."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: uuid.UUID) -> User:
        """Return a user by identifier or raise ``UserNotFoundError``."""

        user = self.db.get(User, user_id)
        if not user:
            raise UserNotFoundError("User not found")
        return user

    def update(self, user: User, payload: UserUpdate) -> User:
        """Persist user profile changes and return the updated entity."""

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(self, limit: int = 50, offset: int = 0) -> list[User]:
        """Return paginated users sorted by creation date."""

        stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))
