"""#396 / #143 — the day's words, picked once and counted by every screen.

Live walk 31 October: Home said «5 words», the scene's hand-on «Next: 8 words»,
the review opened at 0/8, Home afterwards «10 words — done», the Done screen
«11 Words». Each number was a fresh read of the moment: Home counted the
reviews due and the new words left *before* the scene; the scene then met its
own new words (now due as reviews) and reviewed some old ones (no longer due);
the deck was picked only when the review opened; the end counted every word
touched today.

The day's words are now one plan, stored with the day's drill batch
(:class:`~app.db.models.vocabulary.VocabularyDrillBatch.plan`) at the first read
of the day (Home, or the day deck when it is opened first):

* ``reviews`` — the word ids due at that moment, as many as the day deck holds.
  They stay the day's reviews: one the scene answered meanwhile is still a card
  of the deck, one that comes due later today waits for tomorrow (or «more»).
* ``quota`` / ``share`` — the day's new-word dose and the journey's share of it,
  as they stood. The new words are the scene's (its reservation once planned,
  its share before) and the drill's (what the dose leaves). So the count does
  not move when the journey is planned or when the scene meets its words: the
  scene's words are cards of the deck too, the first ones.
* ``size`` / ``dealt_at`` — once the day deck is dealt, how many cards it holds
  (the scene's words still to come included). A finished step and the Done
  screen say this number; «more» cards appended later do not change it.

Home's count before the deck is dealt is :func:`planned_counts`; the deal is
:func:`deal_items`, from the same plan, so the review opens on the number Home
and the hand-on printed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

PLAN_VERSION = 1
#: The list a scene's word takes in the batch when it was met before the deck.
SCENE_LIST = "due_words"
CARD_DIRECTIONS = {"fr_to_de", "de_to_fr"}
#: The batch item flag (and the payload card's) of a word the learner kept.
KEPT_KEY = "kept_word"
#: A miss in the scene is a journey review graded «Again» (``ProgressService.record_context_credit``).
_SCENE_SOURCE = "daily_journey"
_MISSED_RATING = 0


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def read_plan(batch: Any) -> dict[str, Any] | None:
    """The batch's day plan, or ``None`` (no batch, an old row, another shape)."""

    plan = getattr(batch, "plan", None) if batch is not None else None
    if isinstance(plan, dict) and plan.get("v") == PLAN_VERSION:
        return plan
    return None


def is_dealt(plan: dict[str, Any] | None) -> bool:
    return bool(plan and plan.get("dealt_at"))


def card_direction(user: Any) -> str | None:
    stored = getattr(user, "default_vocab_direction", None)
    return stored if stored in CARD_DIRECTIONS else None


def _scene_done(db: Session, user: Any, *, now: datetime) -> bool:
    """Today's scene is over (any terminal status, a stopped one too)."""

    from app.services.journey_contracts import TERMINAL_JOURNEY_STATUSES
    from app.services.vocabulary_pace import todays_journey

    journey = todays_journey(db, user, now=now)
    return journey is not None and journey.status in {status.value for status in TERMINAL_JOURNEY_STATUSES}


def scene_words(
    db: Session, user: Any, plan: dict[str, Any], *, now: datetime
) -> tuple[bool, set[int], int]:
    """``(planned, reserved, slots)``: the scene's share of the day's new words.

    Once today's journey is planned, its reservation (every reserved word, met
    or not: a word the scene met is a card of the deck). Before, the share the
    dose kept free for it when the plan was made.
    """

    from app.services.vocabulary_pace import journey_reservation

    planned, reserved = journey_reservation(db, user, now=now)
    if planned:
        return True, set(reserved), len(reserved)
    return False, set(), int(plan.get("share") or 0)


@dataclass(frozen=True)
class NewWordSplit:
    """The day deck's new-word slots, split (:func:`new_word_split`)."""

    #: The scene's cards dealt now, ``(word_id, list)``: the ones the scheduler had
    #: due anyway (reviews, no slot of the share), then the share's met and released words.
    scene: list[tuple[int, str]]
    #: The share's words still to come (the scene has not met them yet).
    pending: int
    #: How many of the scheduler's next new words the deck asks for.
    scheduler: int

    @property
    def scene_keep(self) -> int:
        """The scene cards the deck may hold in all, the ones that join later included."""

        return len(self.scene) + self.pending


def new_word_split(
    db: Session,
    user: Any,
    plan: dict[str, Any],
    *,
    now: datetime,
    kept_new: int = 0,
    exclude: set[int] | frozenset[int] = frozenset(),
    release: bool = False,
) -> NewWordSplit:
    """The day deck's new words: the scene's share and the scheduler's, inside the day's intake.

    One function for the deal (:func:`deal_items`) and Home's count before it
    (:func:`planned_counts`), so the two can never disagree.

    * **Intake.** The words the deck may still introduce are the plan's dose
      (``plan["quota"]``, read here only) less today's introductions (the
      scene's met words among them) and the reservations the scene has still
      to introduce, capped at ``DAY_DECK_NEW_WORDS``. A scene word left out of
      the deck frees no intake if the scene introduced it or will: only a word
      the scene left unmet once it is over (released into the deck) does, by
      not being dealt.
    * **The scene's words, all of them** (P7, pilot 17 Nov; the owner rule of
      2 Nov capped them at a third of the new-word slots, and the walk's days
      dealt one to five scene words among twenty): met words, then released
      ones, then the ones still to come. They take the intake first; the
      scheduler's next new words fill what is left. A released word (one the
      scene reserved and left unmet) takes an intake slot, so the day never
      passes its dose because of them. A scene word the scheduler had due anyway
      is one of the day's reviews: always dealt, no slot. Before the journey is
      planned, the share kept free for it is a count, not words: it is held
      whole, as before (the deck dealt then releases it).

    ``exclude``: word ids the deck already holds (the Lexique's cards). ``release``:
    the deck is dealt before any scene was planned, so the share kept free for
    the scene is the deck's.
    """

    from app.services.daily_session import DAY_DECK_NEW_WORDS
    from app.services.vocabulary_pace import introduced_today

    scene, pending = ([], 0) if release else _scene_cards(
        db, user, plan, now=now, scene_done=_scene_done(db, user, now=now)
    )
    due_ids = {int(value) for value in plan.get("reviews") or []}
    scene = [card for card in scene if card[0] not in exclude]
    scene_due = [card for card in scene if card[0] in due_ids]
    met = [card for card in scene if card[0] not in due_ids and card[1] == SCENE_LIST]
    released = [card for card in scene if card[0] not in due_ids and card[1] != SCENE_LIST]
    intake = int(plan.get("quota") or 0) - len(introduced_today(db, user, now=now)) - pending
    allowance = min(DAY_DECK_NEW_WORDS, max(0, intake))
    kept_new = max(0, int(kept_new))
    if not release and not scene_words(db, user, plan, now=now)[0]:
        # No journey planned yet: the share the dose keeps free for it is a count,
        # not words; the scene decides them (and the share applies) once it is planned.
        return NewWordSplit(scene=[], pending=pending, scheduler=max(0, allowance - kept_new))
    # Met words were introduced (and pending ones are held) out of the intake
    # already; a released word takes one of the slots the intake leaves.
    released = released[: max(0, allowance - kept_new)]
    return NewWordSplit(
        scene=scene_due + met + released,
        pending=pending,
        scheduler=max(0, allowance - kept_new - len(released)),
    )


def kept_waiting_ids(db: Session, user: Any) -> list[int]:
    """P7: the words the learner kept («Garder» / «Behalten») and has not been asked
    yet, in the order they were kept.

    A kept word is a progress row ``kept_from_story`` with no review
    (:func:`app.services.kept_words.keep_word`). It is due at once, but the day's
    reviews are frozen at the first read and cut by priority, so «valise», promised
    «es kommt morgen wieder», was in no deck on days 2 to 5. Each one now opens the
    next deck dealt after it was kept, whatever the review list would have cut.
    """

    from sqlalchemy import select

    from app.db.models.progress import UserVocabularyProgress
    from app.services.kept_words import KEPT_PROVENANCE

    if not getattr(user, "id", None):
        return []
    rows = db.execute(
        select(UserVocabularyProgress.word_id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.provenance == KEPT_PROVENANCE,
            UserVocabularyProgress.last_review_date.is_(None),
            (UserVocabularyProgress.reps.is_(None)) | (UserVocabularyProgress.reps == 0),
        )
        .order_by(UserVocabularyProgress.created_at.asc(), UserVocabularyProgress.id.asc())
    ).all()
    return [int(row[0]) for row in rows if row[0] is not None]


def scene_missed_ids(db: Session, user: Any, *, now: datetime) -> list[int]:
    """P7: the words the learner missed in yesterday's and today's scene, most recent first.

    What the journey already records: a missed practice item lapses the word, a
    review logged ``daily_journey`` with the «Again» grade. (A word looked up in the
    reader is not recorded anywhere: ``GET /vocabulary/lookup`` writes nothing, and
    no new tracking is built for it.)
    """

    from datetime import timedelta

    from sqlalchemy import select

    from app.db.models.progress import ReviewLog, UserVocabularyProgress
    from app.services.vocabulary_pace import _local_window

    if not getattr(user, "id", None):
        return []
    start, _end = _local_window(user, now)
    rows = db.execute(
        select(UserVocabularyProgress.word_id, ReviewLog.review_date)
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            ReviewLog.source == _SCENE_SOURCE,
            ReviewLog.rating == _MISSED_RATING,
            ReviewLog.review_date >= start - timedelta(days=1),
            ReviewLog.review_date <= now,
        )
        .order_by(ReviewLog.review_date.desc())
    ).all()
    ordered: list[int] = []
    for word_id, _at in rows:
        if word_id is not None and int(word_id) not in ordered:
            ordered.append(int(word_id))
    return ordered


def _due_review_ids(db: Session, user: Any, *, room: int, now: datetime) -> list[int]:
    from app.services.progress import ProgressService

    if room <= 0:
        return []
    payload = ProgressService(db).get_vocabulary_due_context(
        user=user,
        limit=room,
        due_limit=room,
        fragile_limit=0,
        new_limit=0,
        topic_limit=0,
        linked_limit=0,
        direction=card_direction(user),
        now=now,
    )
    return [int(card["word_id"]) for card in payload.get("due_words") or [] if card.get("word_id")]


def make_plan(db: Session, user: Any, *, now: datetime) -> dict[str, Any]:
    """The day's words as they stand now (pure read)."""

    from app.services.daily_session import DAY_DECK_LIMIT, DAY_DECK_NEW_WORDS, review_room
    from app.services.vocabulary_pace import (
        effective_new_word_cap,
        intake_throttle_factor,
        introduced_today,
        journey_reservation,
        journey_word_share,
        reviews_left_today,
    )

    factor = intake_throttle_factor(db, user, now=now)
    # The one cap (owner, 2 Nov): its dose part. Today's extras are dealt after
    # the day's deck as the learner's continuation, never into its count.
    quota = effective_new_word_cap(db, user, now=now, factor=factor, extras=False)
    planned, _reserved = journey_reservation(db, user, now=now)
    share = 0 if planned else min(quota, journey_word_share(user, factor))
    new_words = min(DAY_DECK_NEW_WORDS, max(0, quota - len(introduced_today(db, user, now=now))))
    room = review_room(new_words, reviews_left=reviews_left_today(db, user, now=now), deck_limit=DAY_DECK_LIMIT)
    reviews = _due_review_ids(db, user, room=room, now=now)
    return {
        "v": PLAN_VERSION,
        "at": _iso(now),
        # The dose as the learner set it: a pace changed before the deck is
        # dealt re-plans the day (the Tempo sheet).
        "dose": _dose(user),
        "quota": int(quota),
        "share": int(share),
        "reviews": reviews,
        "dealt_at": None,
        "size": None,
    }


def _dose(user: Any) -> int:
    from app.services.vocabulary_pace import planned_new_words

    return int(planned_new_words(user))


def ensure_plan(db: Session, user: Any, *, now: datetime | None = None, commit: bool = True) -> Any:
    """The learner's batch row for today, with the day's plan: made on the first
    read of the day, kept afterwards. Returns the batch (``None`` when it could
    not be made: the counts then fall back to a fresh read)."""

    from app.db.models.vocabulary import VocabularyDrillBatch
    from app.services import drill_batch
    from app.services.streak import local_today

    if not getattr(user, "id", None):
        return None
    now = now or datetime.now(UTC)
    day = local_today(user, now)
    batch = drill_batch.load_batch(db, user, day)
    plan = read_plan(batch)
    if plan is not None and (is_dealt(plan) or plan.get("dose") == _dose(user)):
        return batch
    try:
        with db.begin_nested():
            plan = make_plan(db, user, now=now)
            if batch is None:
                db.query(VocabularyDrillBatch).filter(
                    VocabularyDrillBatch.user_id == user.id, VocabularyDrillBatch.day != day
                ).delete(synchronize_session=False)
                batch = VocabularyDrillBatch(
                    user_id=user.id, day=day, items=[], new_limit=0, new_dealt=0, cursor=0, plan=plan
                )
                db.add(batch)
            else:
                batch.plan = plan
                flag_modified(batch, "plan")
            db.flush()
    except Exception:  # noqa: BLE001 - a plan that cannot be made never costs the day
        logger.warning("day_words: the day's plan could not be made", exc_info=True)
        db.expire_all()
        return drill_batch.load_batch(db, user, day)
    if commit:
        db.commit()
    return batch


def planned_counts(
    db: Session, user: Any, plan: dict[str, Any], *, now: datetime, batch: Any = None
) -> tuple[int, int]:
    """``(new, reviews)`` the day deck will hold, before it is dealt: what
    :func:`deal_items` will deal, counted the same way.

    A word is counted once: a scene word already due is the scene's, not also a
    review. A card a smaller deck dealt earlier today (the Lexique) and left
    unanswered keeps its place in the day deck, so it is counted too.
    """

    from app.services import drill_batch

    _planned, reserved, _slots = scene_words(db, user, plan, now=now)
    review_ids = {int(value) for value in plan.get("reviews") or []} - reserved
    kept_ids: set[int] = set()
    kept_new = 0
    if batch is not None and batch.items:
        kept = drill_batch.remaining_items(db, user, list(batch.items or []), reserved_new=reserved)
        for item in kept:
            word_id = int(item.get("word_id") or 0)
            if not word_id or word_id in kept_ids:
                continue
            kept_ids.add(word_id)
            if item.get("list") == "new_words":
                kept_new += 1
            else:
                review_ids.add(word_id)
    # P7: the kept words and the scene's misses open the deck, whatever the plan cut.
    front = front_counts(db, user, now=now, exclude=kept_ids)
    review_ids |= front
    split = new_word_split(db, user, plan, now=now, kept_new=kept_new, exclude=kept_ids | front)
    scene_ids = {word_id for word_id, _name in split.scene}
    return kept_new + split.scene_keep + split.scheduler, len(review_ids - scene_ids)


def _scene_cards(
    db: Session, user: Any, plan: dict[str, Any], *, now: datetime, scene_done: bool
) -> tuple[list[tuple[int, str]], int]:
    """The scene's words as cards, and how many are still to come.

    A word the scene met is a review card. Once the scene is over, a word it
    reserved and never met is a new card (the day's dose, released). Before,
    the words it has not met are the scene's to introduce (WP-L6): they wait.
    """

    from app.services.vocabulary_pace import introduced_today

    if plan.get("released"):
        return [], 0
    planned, reserved, slots = scene_words(db, user, plan, now=now)
    if not planned:
        return [], slots
    introduced = introduced_today(db, user, now=now)
    cards: list[tuple[int, str]] = [(word_id, SCENE_LIST) for word_id in sorted(reserved & introduced)]
    unmet = sorted(reserved - introduced)
    if scene_done:
        cards.extend((word_id, "new_words") for word_id in unmet)
        return cards, 0
    return cards, len(unmet)


def deal_items(
    db: Session,
    user: Any,
    plan: dict[str, Any],
    *,
    now: datetime,
    context_kwargs: dict[str, Any],
    kept: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """The day deck from the plan: ``(items, new_dealt, pending)``.

    The cards a smaller deck dealt earlier today still holds keep their places
    (``kept``: the Lexique's eight, #143), then (P7) every word the learner kept
    from the story and was not asked yet (:func:`kept_waiting_ids`, flagged
    :data:`KEPT_KEY`: the deck shows them first), the words they missed in
    yesterday's and today's scene (:func:`scene_missed_ids`), the scene's words,
    the plan's reviews and the drill's new words. ``pending`` are the scene's
    words still to come (the deck was opened before the scene met them); they
    join the deck when it is next read.

    The new words are :func:`new_word_split`'s: all of the scene's words and the
    scheduler's next new words, inside the day's intake. The scene's cards are
    recorded as ``scene_keep`` so the words that join later stay inside it.
    """

    from app.db.models.progress import UserVocabularyProgress
    from app.services.progress import ProgressService

    stamp = _iso(now)
    planned, _reserved, _slots = scene_words(db, user, plan, now=now)
    release = not planned
    if release:
        plan["released"] = True
    seen: set[int] = set()
    items: list[dict[str, Any]] = []

    def add(word_id: int, name: str, bucket: str) -> None:
        if word_id in seen:
            return
        seen.add(word_id)
        items.append({"word_id": int(word_id), "list": name, "bucket": bucket, "at": stamp})

    kept_new = 0
    for item in kept or []:
        word_id = int(item.get("word_id") or 0)
        if word_id and word_id not in seen:
            name = str(item.get("list") or "due_words")
            add(word_id, name, str(item.get("bucket") or ("new" if name == "new_words" else "due")))
            kept_new += 1 if name == "new_words" else 0
    # P7: a word the learner kept is in the next deck after it was kept, first,
    # whatever the review list would have cut; then the words the scene saw them miss.
    _front(db, user, items, seen, add, now=now)
    # P7: all of the scene's words, inside the day's intake (new_word_split).
    split = new_word_split(db, user, plan, now=now, kept_new=kept_new, exclude=seen, release=release)
    plan["scene_keep"] = split.scene_keep
    pending = split.pending
    room = split.scheduler
    for word_id, name in split.scene:
        add(word_id, name, "due" if name == SCENE_LIST else "new")
        items[-1]["scene"] = True
    review_ids = [int(value) for value in plan.get("reviews") or []]
    if review_ids:
        owned = {
            int(row[0])
            for row in db.query(UserVocabularyProgress.word_id).filter(
                UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id.in_(review_ids)
            )
        }
        for word_id in review_ids:
            if word_id in owned:
                add(word_id, "due_words", "due")
    new_dealt = kept_new
    if room > 0:
        _planned, reserved, _slots = scene_words(db, user, plan, now=now)
        payload = ProgressService(db).get_vocabulary_due_context(
            **{
                **context_kwargs,
                "limit": room,
                "due_limit": 0,
                "fragile_limit": 0,
                "new_limit": room,
                "topic_limit": 0,
                "linked_limit": 0,
                "exclude_new_word_ids": set(reserved) | seen,
                "now": now,
            }
        )
        for card in payload.get("new_words") or []:
            word_id = int(card.get("word_id") or 0)
            if word_id and word_id not in seen:
                add(word_id, "new_words", str(card.get("bucket") or "new"))
                new_dealt += 1
    return items, new_dealt, pending


def _front(
    db: Session, user: Any, items: list[dict[str, Any]], seen: set[int], add: Any, *, now: datetime
) -> None:
    """Deal the kept words (flagged) and the scene's misses: the deck's front (P7)."""

    from app.db.models.progress import UserVocabularyProgress

    kept_ids = kept_waiting_ids(db, user)
    missed = [word_id for word_id in scene_missed_ids(db, user, now=now) if word_id not in kept_ids]
    owned = (
        {
            int(row[0])
            for row in db.query(UserVocabularyProgress.word_id).filter(
                UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id.in_(missed)
            )
        }
        if missed
        else set()
    )
    for word_id in kept_ids:
        if word_id not in seen:
            add(word_id, "due_words", "due")
        for item in items:
            if int(item["word_id"]) == word_id:
                item[KEPT_KEY] = True
    for word_id in missed:
        if word_id in owned:
            add(word_id, "due_words", "due")


def front_counts(db: Session, user: Any, *, now: datetime, exclude: set[int]) -> set[int]:
    """The kept and missed words :func:`deal_items` deals at the deck's front, less ``exclude``."""

    return (set(kept_waiting_ids(db, user)) | set(scene_missed_ids(db, user, now=now))) - set(exclude)


def mark_kept_cards(batch: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Flag the payload's cards the batch dealt as kept words (:data:`KEPT_KEY`)."""

    from app.services.drill_batch import PAYLOAD_LISTS

    kept = {int(item["word_id"]) for item in getattr(batch, "items", None) or [] if item.get(KEPT_KEY)}
    if not kept:
        return payload
    for name in PAYLOAD_LISTS:
        payload[name] = [
            {**card, KEPT_KEY: True} if int(card.get("word_id") or 0) in kept else card
            for card in payload.get(name) or []
        ]
    return payload


def mark_dealt(batch: Any, plan: dict[str, Any], *, size: int, now: datetime) -> None:
    batch.plan = {**plan, "dealt_at": _iso(now), "size": int(size)}
    flag_modified(batch, "plan")


def join_scene_words(db: Session, user: Any, batch: Any, *, now: datetime) -> int:
    """A deck dealt before the scene met its words takes them on now (their
    places were counted in its size). Returns how many joined."""

    plan = read_plan(batch)
    if not is_dealt(plan):
        return 0
    items = list(batch.items or [])
    present = {int(item["word_id"]) for item in items}
    scene, _pending = _scene_cards(db, user, plan, now=now, scene_done=_scene_done(db, user, now=now))
    stamp = _iso(now)
    joined = [
        {
            "word_id": int(word_id),
            "list": name,
            "bucket": "due" if name == SCENE_LIST else "new",
            "at": stamp,
            "scene": True,
        }
        for word_id, name in scene
        if int(word_id) not in present
    ][: _scene_room(plan, items)]
    if joined:
        batch.items = items + joined
        flag_modified(batch, "items")
        db.flush()
    return len(joined)


def pending_scene_words(db: Session, user: Any, batch: Any, *, now: datetime) -> int:
    """The scene's words a dealt deck still waits for (counted as new)."""

    plan = read_plan(batch)
    if not is_dealt(plan):
        return 0
    if plan.get("released"):
        return 0
    present = {int(item["word_id"]) for item in batch.items or []}
    planned, reserved, _slots = scene_words(db, user, plan, now=now)
    return min(len(reserved - present), _scene_room(plan, list(batch.items or []))) if planned else 0


def _scene_room(plan: dict[str, Any], items: list[dict[str, Any]]) -> int:
    """How many more scene words the dealt deck takes: its ``scene_keep`` less the
    scene cards it holds (a plan dealt before the share was recorded: no limit)."""

    keep = plan.get("scene_keep")
    if keep is None:
        return len(items) + 10_000
    return max(0, int(keep) - sum(1 for item in items if item.get("scene")))


def day_items(batch: Any) -> list[dict[str, Any]]:
    """The batch's cards that are the day's deck: not the «more» cards the
    learner asked for after it."""

    return [item for item in batch.items or [] if not item.get("extra")]


def extra_items(batch: Any) -> list[dict[str, Any]]:
    """The «more» cards the learner asked for after the day's deck (owner, 2 Nov:
    «Noch 5 neue Wörter»), in the order they were dealt. The day deck serves the
    ones still unanswered after its own cards, so a reload of ``?day=1`` keeps
    the continuation; they never count as the day's words (:func:`day_items`)."""

    return [item for item in batch.items or [] if item.get("extra")]


def remaining_reserved(batch: Any, reserved: set[int]) -> set[int]:
    """The reserved words a planned deck's remainder leaves out: never its own
    scene cards (a word the scene left unmet, released into the deck)."""

    own = {int(item["word_id"]) for item in batch.items or [] if item.get("scene")}
    return set(reserved) - own


def dealt_size(batch: Any) -> int | None:
    """The day deck's size once dealt, else ``None``."""

    plan = read_plan(batch)
    if not is_dealt(plan):
        return None
    return int(plan.get("size") or 0) or None


__all__ = [
    "KEPT_KEY",
    "PLAN_VERSION",
    "NewWordSplit",
    "day_items",
    "deal_items",
    "dealt_size",
    "ensure_plan",
    "front_counts",
    "is_dealt",
    "join_scene_words",
    "kept_waiting_ids",
    "make_plan",
    "mark_dealt",
    "mark_kept_cards",
    "new_word_split",
    "pending_scene_words",
    "planned_counts",
    "read_plan",
    "remaining_reserved",
    "scene_missed_ids",
    "scene_words",
]
