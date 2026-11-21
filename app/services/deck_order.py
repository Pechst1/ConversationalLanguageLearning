"""The word deck's mix and order, decided once on the server for every client.

Owner request, 2 November: «Der Wörterstapel soll primär die Wörter abfragen,
die als nächstes durch den Scheduler vorgeschlagen werden … gleichzeitig sollen
auch Wörter aus den Szenen genommen werden … aber lieber die Wörter, die nach
dem Scheduler kommen, weil man so schneller lernt.» PR #465 had put today's
scene words *first*, ahead of the reviews the scheduler said were due.

P7 (pilot, 17 Nov 2026; review finding 4): of about twenty daily words only one
to five came from the scene, the rest a frequency list, and a word the learner
kept never came back. The deck is now made of the story and the learner:

1. **Every word the learner kept** and was not asked yet (``kept_word`` on the
   card, :data:`app.services.day_words.KEPT_KEY`), in the order they were kept.
2. **Every due review**, in the scheduler's order as dealt (the day deck deals
   the words missed in yesterday's and today's scene first among them). A review
   that also appeared in today's scene stays a review (it keeps its scene line
   as example).
3. **All of today's scene words** (``scene_word`` on the card,
   :data:`app.services.scene_deck.SCENE_WORD_KEY`): the owner rule of 2 Nov that
   capped them at a third of the new-word slots is gone. They come out of the
   new-word budget, never on top of it (:func:`app.services.day_words.new_word_split`).
4. **The scheduler's next new words** in its own order (today's slate words,
   «Les mots du jour», first among them), up to the day's dose.

The order is sent as ``deck_order`` (word ids) with the payload; the drill
(``web-frontend/components/lexique/deck-session.ts`` ``deckOrdered``) shows it
and never re-sorts.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.services.day_words import KEPT_KEY as KEPT_WORD_KEY
from app.services.scene_deck import SCENE_WORD_KEY

#: The order the lists are read in (the order the drill always concatenated them).
LIST_ORDER = ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")

#: The buckets the scheduler deals as reviews.
REVIEW_BUCKETS = frozenset({"due", "fragile"})

def _cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    cards: list[dict[str, Any]] = []
    for name in LIST_ORDER:
        for card in payload.get(name) or []:
            word_id = int(card.get("word_id") or 0)
            if word_id and word_id not in seen:
                seen.add(word_id)
                cards.append(card)
    return cards


def deck_order(payload: dict[str, Any], *, slate_ids: Iterable[int] = ()) -> list[int]:
    """The payload's word ids in the order the deck shows them (each id once)."""

    slate_ids = {int(value) for value in slate_ids}
    kept: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    scene: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    for card in _cards(payload):
        if card.get(KEPT_WORD_KEY):
            kept.append(card)
        elif card.get(SCENE_WORD_KEY):
            scene.append(card)
        elif card.get("bucket") in REVIEW_BUCKETS:
            reviews.append(card)
        else:
            fresh.append(card)
    # Today's slate words first among the scheduler's new words (stable otherwise).
    fresh.sort(key=lambda card: int(card.get("word_id") or 0) not in slate_ids)
    ordered = kept + reviews + scene + fresh
    return [int(card["word_id"]) for card in ordered]


__all__ = [
    "KEPT_WORD_KEY",
    "LIST_ORDER",
    "REVIEW_BUCKETS",
    "deck_order",
]
