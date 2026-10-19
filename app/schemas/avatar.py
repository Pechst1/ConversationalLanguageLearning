"""Pydantic schemas for the learner's avatar (``/avatar``)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, WithJsonSchema

#: What an avatar config looks like on the wire: a flat object of part ids,
#: colour ids, numbers and switches. ``app.services.avatar.validate_avatar``
#: holds the full rules.
AVATAR_CONFIG_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": {
        "anyOf": [{"type": "boolean"}, {"type": "integer"}, {"type": "string"}],
    },
}

AvatarConfig = dict[str, bool | int | str]


class AvatarRewardRead(BaseModel):
    """One avatar item an achievement unlocks, and how close the learner is."""

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


class AvatarState(BaseModel):
    """The learner's avatar, the items they have unlocked, and every reward."""

    #: ``null`` until the learner makes one.
    avatar: AvatarConfig | None
    #: The reward items the learner may wear, in catalogue order.
    unlocked: list[str]
    #: Every reward item, in catalogue order, locked or not.
    rewards: list[AvatarRewardRead]


class AvatarUpdate(BaseModel):
    """``PUT /avatar``: the whole avatar config, replacing the stored one.

    Typed loosely on purpose: the service validates the shape, so every refusal
    is one 422 with a readable ``detail``.
    """

    avatar: Annotated[Any, WithJsonSchema(AVATAR_CONFIG_JSON_SCHEMA)]


__all__ = [
    "AVATAR_CONFIG_JSON_SCHEMA",
    "AvatarConfig",
    "AvatarRewardRead",
    "AvatarState",
    "AvatarUpdate",
]
