"""The learner's drawn character (avatar) and the items achievements unlock.

``users.avatar`` stores what the editor chose: a flat JSON object of part ids,
colour ids, small numbers and switches, keyed by slot (``hat``, ``neck``,
``wrist``…), with ``"v": 1`` for the config's version. The server does not
know the editor's parts; it checks the shape (:func:`validate_avatar`) and one
rule: an item an achievement unlocks (:data:`app.services.achievement.REWARD_SLOTS`)
may only be worn once that achievement is earned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.achievement import REWARD_SLOTS, AchievementProgress, AchievementService

AVATAR_VERSION = 1
MAX_AVATAR_KEYS = 32
MAX_AVATAR_INT = 1000
_KEY = re.compile(r"[a-zA-Z][a-zA-Z0-9]{0,31}")
_STRING = re.compile(r"[a-z0-9_]{1,40}")

AvatarConfig = dict[str, bool | int | str]


class AvatarInvalidError(ValueError):
    """The avatar config does not have the expected shape (HTTP 422)."""


class AvatarItemLockedError(Exception):
    """The avatar wears an item whose achievement is not earned yet (HTTP 403)."""

    def __init__(self, item: str) -> None:
        super().__init__(item)
        self.item = item


def validate_avatar(raw: Any) -> AvatarConfig:
    """Return ``raw`` as an avatar config, or raise :class:`AvatarInvalidError`."""

    if not isinstance(raw, dict):
        raise AvatarInvalidError("avatar must be a JSON object")
    if len(raw) > MAX_AVATAR_KEYS:
        raise AvatarInvalidError(f"avatar has {len(raw)} keys; at most {MAX_AVATAR_KEYS} are allowed")
    config: AvatarConfig = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise AvatarInvalidError(
                f"avatar key {key!r} must be a letter followed by up to 31 letters or digits"
            )
        if isinstance(value, bool):
            config[key] = value
        elif isinstance(value, int):
            if not 0 <= value <= MAX_AVATAR_INT:
                raise AvatarInvalidError(
                    f"avatar.{key}: a number must be between 0 and {MAX_AVATAR_INT}"
                )
            config[key] = value
        elif isinstance(value, str):
            if not _STRING.fullmatch(value):
                raise AvatarInvalidError(
                    f"avatar.{key}: a text value must be 1 to 40 characters of a-z, 0-9 or _"
                )
            config[key] = value
        else:
            raise AvatarInvalidError(
                f"avatar.{key}: a value must be true/false, a whole number or a text id"
            )
    version = config.get("v")
    if isinstance(version, bool) or version != AVATAR_VERSION:
        raise AvatarInvalidError(f'avatar must contain "v": {AVATAR_VERSION}')
    return config


@dataclass(frozen=True)
class AvatarReward:
    """One avatar item an achievement unlocks, with the learner's progress."""

    item: str
    slot: str
    achievement_key: str
    name: str
    description: str | None
    tier: str
    current: int
    target: int
    unlocked: bool
    unlocked_at: datetime | None


@dataclass(frozen=True)
class AvatarStateData:
    avatar: AvatarConfig | None
    unlocked: list[str]
    rewards: list[AvatarReward]


class AvatarService:
    """Read and save the learner's avatar against the achievements they hold."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.achievements = AchievementService(db)

    def _progress(self, user: User) -> list[AchievementProgress]:
        # Like /achievements/my: whatever the learner earned since the last
        # read is unlocked first, so a fresh reward is wearable at once.
        self.achievements.check_and_unlock(user=user)
        return self.achievements.get_user_achievements(user.id, include_locked=True)

    @staticmethod
    def _state(user: User, progress: list[AchievementProgress]) -> AvatarStateData:
        rewards = [
            AvatarReward(
                item=item.reward_item,
                slot=REWARD_SLOTS[item.reward_item],
                achievement_key=item.achievement_key,
                name=item.name,
                description=item.description,
                tier=item.tier,
                current=item.current_progress,
                target=item.target_progress,
                unlocked=item.completed,
                unlocked_at=item.unlocked_at,
            )
            for item in progress
            if item.reward_item and item.reward_item in REWARD_SLOTS
        ]
        avatar = user.avatar if isinstance(user.avatar, dict) else None
        return AvatarStateData(
            avatar=avatar,
            unlocked=[reward.item for reward in rewards if reward.unlocked],
            rewards=rewards,
        )

    def state(self, user: User) -> AvatarStateData:
        return self._state(user, self._progress(user))

    def save(self, user: User, raw: Any) -> AvatarStateData:
        """Validate and store ``raw`` as the learner's avatar; commit.

        Raises :class:`AvatarInvalidError` for a bad shape and
        :class:`AvatarItemLockedError` for an item not yet earned.
        """

        config = validate_avatar(raw)
        progress = self._progress(user)
        unlocked = {item.reward_item for item in progress if item.completed and item.reward_item}
        for item, slot in REWARD_SLOTS.items():
            if config.get(slot) == item and item not in unlocked:
                raise AvatarItemLockedError(item)
        user.avatar = config
        self.db.add(user)
        self.db.commit()
        return self._state(user, progress)


__all__ = [
    "AVATAR_VERSION",
    "MAX_AVATAR_INT",
    "MAX_AVATAR_KEYS",
    "AvatarInvalidError",
    "AvatarItemLockedError",
    "AvatarReward",
    "AvatarService",
    "AvatarStateData",
    "validate_avatar",
]
