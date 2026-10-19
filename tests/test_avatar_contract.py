"""Ton personnage: the editor's earned pieces (``web-frontend/lib/avatar.ts``) and the server's
(``app/services/achievement.py``) are one table.

The editor shows a padlock on what the server would refuse, so the two lists must name the
same items, in the same slots, won by the same achievements.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.services.achievement import CATALOGUE, REWARD_SLOTS

AVATAR_TS = Path(__file__).resolve().parents[1] / "web-frontend" / "lib" / "avatar.ts"


def _frontend_rewards() -> dict[str, tuple[str, str]]:
    source = AVATAR_TS.read_text(encoding="utf-8")
    block = source.split("export const REWARDS", 1)[1].split("};", 1)[0]
    rows = re.findall(r"(\w+): \{ slot: '(\w+)', achievement: '(\w+)' \}", block)
    assert rows, "REWARDS not found in lib/avatar.ts"
    return {item: (slot, achievement) for item, slot, achievement in rows}


def test_every_earned_piece_matches_the_server() -> None:
    server = {
        defn.reward: (REWARD_SLOTS[defn.reward], defn.key) for defn in CATALOGUE if defn.reward
    }
    assert _frontend_rewards() == server


def test_every_reward_slot_is_worn_by_exactly_one_achievement() -> None:
    rewarded = [defn.reward for defn in CATALOGUE if defn.reward]
    assert sorted(rewarded) == sorted(REWARD_SLOTS)
    assert len(set(rewarded)) == len(rewarded)
