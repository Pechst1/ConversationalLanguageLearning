"""The word deck's mix and order, decided once on the server for every client.

Owner request, 2 November: «Der Wörterstapel soll primär die Wörter abfragen,
die als nächstes durch den Scheduler vorgeschlagen werden … gleichzeitig sollen
auch Wörter aus den Szenen genommen werden … aber lieber die Wörter, die nach
dem Scheduler kommen, weil man so schneller lernt.» PR #465 had put today's
scene words *first*, ahead of the reviews the scheduler said were due.

The rule, in this one place:

1. **Every due review first**, in the scheduler's order (the payload's
   ``due_words`` then ``fragile_words``, each as dealt). A scene word never
   pushes a due review out of the deck or behind a new word. A review that also
   appeared in today's scene stays a review (it keeps its scene line as example).
2. **The new-word slots** hold today's scene words (``scene_word`` on the card,
   :data:`app.services.scene_deck.SCENE_WORD_KEY`) for at most
   :data:`SCENE_SHARE_OF_NEW_WORDS` of the slots (rounded down, but at least one
   when there are scene words and slots: :func:`scene_slots`); the rest are the
   scheduler's next new words in its own order (today's slate words, «Les mots
   du jour», first among them). The scene words are spread through the slots
   (at a third, every third card), not bunched at either end.
3. **The scene's share comes out of the new-word budget**, never on top of it:
   the day deck's deal (:func:`app.services.day_words.deal_items`) sizes the
   scene's cards with :func:`scene_slots` over the deck's new-word budget, and a
   cap on the deck's size applies after this mix.

The order is sent as ``deck_order`` (word ids) with the payload; the drill
(``web-frontend/components/lexique/deck-session.ts`` ``deckOrdered``) shows it
and never re-sorts.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from fractions import Fraction
from math import floor
from typing import Any, TypeVar

from app.services.scene_deck import SCENE_WORD_KEY

#: The order the lists are read in (the order the drill always concatenated them).
LIST_ORDER = ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")

#: The buckets the scheduler deals as reviews.
REVIEW_BUCKETS = frozenset({"due", "fragile"})

#: Owner rule, 2 Nov: today's scene words take at most this share of the deck's
#: new-word slots; the scheduler's next new words take the rest.
SCENE_SHARE_OF_NEW_WORDS = Fraction(1, 3)

T = TypeVar("T")


def scene_slots(new_slots: int, scene_words: int) -> int:
    """How many of ``new_slots`` new-word slots today's scene words may take.

    ``floor(new_slots * SCENE_SHARE_OF_NEW_WORDS)``, but at least one when there
    are scene words and any slot, and never more than there are scene words.
    """

    new_slots, scene_words = max(0, int(new_slots)), max(0, int(scene_words))
    if not new_slots or not scene_words:
        return 0
    share = max(1, floor(new_slots * SCENE_SHARE_OF_NEW_WORDS))
    return min(share, scene_words)


def mix_new_words(scheduler: Sequence[T], scene: Sequence[T]) -> list[T]:
    """The new-word slots, filled: the scheduler's words with the scene's share spread through.

    The slots are ``len(scheduler) + len(scene)`` (the new-word budget dealt).
    At most :func:`scene_slots` of them are scene words, each placed as soon as
    the share allows it and no sooner (at a third: the 3rd, 6th, 9th… card); the
    rest keep the scheduler's order. Scene words beyond the share follow at the
    end, so every card keeps a place; the day deck's deal never leaves any (it
    sizes the scene's cards with the same :func:`scene_slots`).
    """

    share = scene_slots(len(scheduler) + len(scene), len(scene))
    picked, extra = list(scene[:share]), list(scene[share:])
    queue = list(scheduler)
    mixed: list[T] = []
    placed = 0
    while queue or picked:
        allowed = (placed + 1) <= (len(mixed) + 1) * SCENE_SHARE_OF_NEW_WORDS
        if picked and (allowed or not queue):
            mixed.append(picked.pop(0))
            placed += 1
        else:
            mixed.append(queue.pop(0))
    return mixed + extra


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
    reviews: list[dict[str, Any]] = []
    scene: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    for card in _cards(payload):
        if card.get(SCENE_WORD_KEY):
            scene.append(card)
        elif card.get("bucket") in REVIEW_BUCKETS:
            reviews.append(card)
        else:
            fresh.append(card)
    # Today's slate words first among the scheduler's new words (stable otherwise).
    fresh.sort(key=lambda card: int(card.get("word_id") or 0) not in slate_ids)
    ordered = reviews + mix_new_words(fresh, scene)
    return [int(card["word_id"]) for card in ordered]


__all__ = [
    "LIST_ORDER",
    "REVIEW_BUCKETS",
    "SCENE_SHARE_OF_NEW_WORDS",
    "deck_order",
    "mix_new_words",
    "scene_slots",
]
