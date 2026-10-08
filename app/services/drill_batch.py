"""WP-154 — the word drill's dealt batch survives a reload.

``GET /vocabulary/due-context`` reads current state. Once a learner answered
three new words, a reload found three free «new» slots and filled them with
other words (with the core list present, story words), so the deck the learner
had been dealt was never finished. The drill page now asks with
``drill=session`` (its own deck) or ``drill=more`` (the WP-131 «Encore N mots»
continuation), and this module keeps what was dealt:

* ``session`` — the first request of the learner's app day deals the deck as
  before and stores it (:class:`VocabularyDrillBatch`, one row per learner per
  day). Later requests the same day serve the cards of that deck not yet
  answered, in the order they were dealt. Only when every card is answered is a
  new deck dealt (and stored in its place); a new app day starts over.
* ``more`` — the continuation deals its words as before, never one already in
  the batch, and appends them; the reply is what is left of the batch.

A card counts as answered once the learner's progress row for it was reviewed
at or after the moment it was dealt (``last_review_date >= at``): the review
endpoints already record that, on whichever surface the word was answered.
Other surfaces (La Une, missions, «Encore 5 minutes») send no ``drill`` and keep
the stateless deck.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyDrillBatch

DRILL_SESSION = "session"
DRILL_MORE = "more"
DRILL_MODES = (DRILL_SESSION, DRILL_MORE)

#: The payload's card lists, in the order a deck is dealt.
PAYLOAD_LISTS = ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    try:
        return _aware(datetime.fromisoformat(str(value)))
    except (TypeError, ValueError):
        return None


def load_batch(db: Session, user: User, day: date) -> VocabularyDrillBatch | None:
    """The learner's own batch for ``day`` — never another learner's."""

    return db.scalar(
        select(VocabularyDrillBatch).where(VocabularyDrillBatch.user_id == user.id, VocabularyDrillBatch.day == day)
    )


def items_from_payload(payload: dict[str, Any], at: datetime) -> list[dict[str, Any]]:
    """The dealt deck as stored: one entry per card, each word once, in deal order."""

    stamp = _aware(at).isoformat()
    items: list[dict[str, Any]] = []
    seen: set[int] = set()
    for name in PAYLOAD_LISTS:
        for card in payload.get(name) or []:
            word_id = int(card.get("word_id") or 0)
            if not word_id or word_id in seen:
                continue
            seen.add(word_id)
            items.append({"word_id": word_id, "list": name, "bucket": card.get("bucket"), "at": stamp})
    return items


def answered_word_ids(db: Session, user: User, items: list[dict[str, Any]]) -> set[int]:
    """The batch's cards the learner has answered since they were dealt."""

    dealt = {int(item["word_id"]): _parse(item.get("at")) for item in items}
    if not dealt:
        return set()
    rows = db.execute(
        select(UserVocabularyProgress.word_id, UserVocabularyProgress.last_review_date).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id.in_(list(dealt)),
        )
    ).all()
    answered: set[int] = set()
    for word_id, last_review in rows:
        at = dealt.get(int(word_id))
        reviewed = _aware(last_review)
        if reviewed is not None and (at is None or reviewed >= at):
            answered.add(int(word_id))
    return answered


def remaining_items(
    db: Session,
    user: User,
    items: list[dict[str, Any]],
    *,
    reserved_new: set[int] | None = None,
) -> list[dict[str, Any]]:
    """The cards still to answer, in deal order. A new word today's journey has
    since reserved is the journey's to introduce (WP-L6), so it leaves the deck."""

    answered = answered_word_ids(db, user, items)
    reserved = set(reserved_new or ())
    return [
        item
        for item in items
        if int(item["word_id"]) not in answered
        and not (item.get("list") == "new_words" and int(item["word_id"]) in reserved)
    ]


def merge_items(
    db: Session,
    user: User,
    existing: list[dict[str, Any]],
    dealt: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The batch after a continuation: its cards plus the newly dealt ones.

    A card still to answer is never dealt twice. One already answered that came
    due again (a lapse in its relearning step) is dealt anew at the end.
    """

    answered = answered_word_ids(db, user, existing)
    pending = {int(item["word_id"]) for item in existing if int(item["word_id"]) not in answered}
    fresh = [item for item in dealt if int(item["word_id"]) not in pending]
    again = {int(item["word_id"]) for item in fresh}
    return [item for item in existing if int(item["word_id"]) not in again] + fresh


def save_batch(
    db: Session,
    user: User,
    day: date,
    items: list[dict[str, Any]],
    *,
    new_limit: int,
    new_dealt: int,
    batch: VocabularyDrillBatch | None,
) -> VocabularyDrillBatch | None:
    """Store ``items`` as the learner's batch for ``day`` (replacing ``batch``).

    Two tabs dealing the first deck of the day at once: the second insert loses
    the unique (user, day) race and keeps the first one's row. Both dealt the
    same deck — the deal is deterministic over the same state.
    """

    if batch is not None:
        batch.items = items
        batch.new_limit = int(new_limit)
        batch.new_dealt = int(new_dealt)
        batch.cursor = 0
        db.flush()
        return batch
    # Yesterday's batches are spent: one row per learner is all the table keeps.
    db.query(VocabularyDrillBatch).filter(
        VocabularyDrillBatch.user_id == user.id, VocabularyDrillBatch.day != day
    ).delete(synchronize_session=False)
    row = VocabularyDrillBatch(
        user_id=user.id, day=day, items=items, new_limit=int(new_limit), new_dealt=int(new_dealt), cursor=0
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return load_batch(db, user, day)
    return row


def resumed_new_words_left(room: int | None, batch: VocabularyDrillBatch, remaining_new: int) -> int | None:
    """WP-131's ``new_words_left_today`` for a resumed deck.

    The room already counts the batch's answered words as introduced; what the
    deck still holds is about to be. When the latest deal served fewer new words
    than it was allowed (``new_dealt < new_limit``), the supply ran out and no
    continuation is offered.
    """

    if room is None:
        return None
    if int(batch.new_dealt or 0) < int(batch.new_limit or 0):
        return 0
    return max(0, room - remaining_new)


__all__ = [
    "DRILL_MODES",
    "DRILL_MORE",
    "DRILL_SESSION",
    "PAYLOAD_LISTS",
    "answered_word_ids",
    "items_from_payload",
    "load_batch",
    "merge_items",
    "remaining_items",
    "resumed_new_words_left",
    "save_batch",
]
