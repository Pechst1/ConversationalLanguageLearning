"""The word deck's order, decided once on the server for every client.

The due-context payload is split into lists (due, fragile, linked, topic, new),
and the drill (``web-frontend/pages/vocabulary/review.tsx``) used to put the
cards back in order on the device with tiers of its own. A deck's order was
therefore nowhere on the server, and anything the server wanted first (owner
request, 1 November: today's scene words) was re-sorted away on the device.

:func:`deck_order` is now the deck's one order, sent as ``deck_order`` (word ids)
with the payload. The tiers, first to last:

0. today's scene words (:data:`app.services.scene_deck.SCENE_WORD_KEY`, the day deck);
1. a word that keeps failing (``ladder == "rescue"``);
2. a story word on its own line (``ladder == "scene"``);
3. reviews (``due`` / ``fragile``) — before new words, as in Anki (WP-115b);
4. today's slate words («Les mots du jour»);
5. the rest.

Inside a tier the cards keep the payload's order: the lists in
:data:`LIST_ORDER`, each in the order it was dealt.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.services.scene_deck import SCENE_WORD_KEY

#: The order the lists are read in (the order the drill always concatenated them).
LIST_ORDER = ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")


def _tier(card: dict[str, Any], slate_ids: set[int]) -> int:
    if card.get(SCENE_WORD_KEY):
        return 0
    ladder = card.get("ladder")
    if ladder == "rescue":
        return 1
    if ladder == "scene":
        return 2
    if card.get("bucket") in {"due", "fragile"}:
        return 3
    if int(card.get("word_id") or 0) in slate_ids:
        return 4
    return 5


def deck_order(payload: dict[str, Any], *, slate_ids: Iterable[int] = ()) -> list[int]:
    """The payload's word ids in the order the deck shows them (each id once)."""

    slate = {int(value) for value in slate_ids}
    seen: set[int] = set()
    cards: list[dict[str, Any]] = []
    for name in LIST_ORDER:
        for card in payload.get(name) or []:
            word_id = int(card.get("word_id") or 0)
            if word_id and word_id not in seen:
                seen.add(word_id)
                cards.append(card)
    ranked = sorted(enumerate(cards), key=lambda pair: (_tier(pair[1], slate), pair[0]))
    return [int(card["word_id"]) for _index, card in ranked]


__all__ = ["LIST_ORDER", "deck_order"]
