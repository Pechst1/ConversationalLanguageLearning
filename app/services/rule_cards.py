"""WP-L10: the rule card v2 — authored per concept, every learner language at once.

The card replaces the English-only «La règle» panel: a French example (with the
part that carries the rule marked), a one-sentence rule in the learner's own
language, the pattern as rows or a small conjugation table, one wrong/right
pair and a longer «Why?». Markup inside French strings: ``[x]`` is the part
that carries the rule, ``{x}`` is written but silent. The client picks the
learner's language; a concept without an authored card gets ``None`` and keeps
the legacy panel.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULE_CARDS_PATH = Path(__file__).resolve().parents[1] / "data" / "grammar_rule_cards.json"
#: 2026-10-03 content program: one reviewed card per fr-core-v2 unit, per band
#: (``fr2_A1.json`` … ``fr2_C1.json``). Same schema plus ``how``, ``examples``,
#: ``traps`` and ``contrast_with``; a v2 id never collides with a v1 one.
RULE_CARDS_V2_DIR = Path(__file__).resolve().parents[1] / "data" / "rule_cards"


def _read_cards(path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    cards = payload.get("cards") if isinstance(payload, dict) else None
    return {str(k): v for k, v in cards.items() if isinstance(v, dict)} if isinstance(cards, dict) else {}


@lru_cache(maxsize=1)
def _cards() -> dict[str, dict[str, Any]]:
    cards = _read_cards(RULE_CARDS_PATH)
    if RULE_CARDS_V2_DIR.is_dir():
        for path in sorted(RULE_CARDS_V2_DIR.glob("fr2_*.json")):
            cards.update(_read_cards(path))
    return cards


def rule_card_for(external_id: str | None) -> dict[str, Any] | None:
    """The authored card for a concept, or ``None`` when it has none yet."""

    if not external_id:
        return None
    card = _cards().get(str(external_id))
    return dict(card) if isinstance(card, dict) else None
