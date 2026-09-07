"""The review deck's rating cycle: what each of the four buttons costs.

Le Lexique prints four French labels — Encore · Dur · Bien · Facile — over
ratings 0..3. Whatever the scheduler underneath, those four must order
monotonically (a card the learner found harder never returns later than one
they found easier) and a rated card must actually leave today's deck.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.enhanced_srs import AnkiSM2Scheduler, AnkiState, EnhancedSRSService
from app.services.progress import vocabulary_due_deadline


def _new_state() -> AnkiState:
    return AnkiState(ease_factor=2.5, interval_days=0, reps=0, lapses=0, phase="new")


def test_new_card_ratings_never_invert() -> None:
    """Dur used to be scheduled ten minutes out while Bien and Facile came back
    in one — the buttons read as a scale but did not behave as one."""

    scheduler = AnkiSM2Scheduler()
    now = datetime.now(UTC)
    outcomes = [
        scheduler.review(state=_new_state(), rating=rating, now=now)
        for rating in (0, 1, 2, 3)
    ]

    dues = [outcome.due_at for outcome in outcomes]
    assert dues == sorted(dues), "harder ratings must not return later than easier ones"
    assert dues[0] == dues[1], "Again and Hard both restart the first learning step"
    assert dues[2] > dues[1], "Good advances past the first step"
    assert outcomes[3].phase == "review", "Easy graduates a new card immediately"
    assert outcomes[3].interval_days == 4


def test_easy_graduates_out_of_the_learning_ladder() -> None:
    scheduler = AnkiSM2Scheduler()
    learning = AnkiState(
        ease_factor=2.5, interval_days=0, reps=1, lapses=0, phase="learn", step_index=0
    )

    outcome = scheduler.review(state=learning, rating=3, now=datetime.now(UTC))

    assert outcome.phase == "review"
    assert outcome.interval_days == 4


def test_a_lapse_keeps_a_share_of_the_pre_lapse_interval() -> None:
    """The relearning step used to read an interval the lapse had just zeroed,
    so a 60-day card came back at one day as if it had never been learned."""

    scheduler = AnkiSM2Scheduler()
    now = datetime.now(UTC)
    mature = AnkiState(
        ease_factor=2.5, interval_days=60, reps=12, lapses=0, phase="review"
    )

    lapsed = scheduler.review(state=mature, rating=0, now=now)
    assert lapsed.phase == "relearn"
    assert lapsed.interval_days == 60

    relearning = AnkiState(
        ease_factor=lapsed.ease_factor,
        interval_days=lapsed.interval_days,
        reps=13,
        lapses=1,
        phase="relearn",
    )
    recovered = scheduler.review(state=relearning, rating=2, now=now)
    assert recovered.phase == "review"
    assert recovered.interval_days == 42  # 70% of the pre-lapse interval


def test_relearning_graduation_orders_with_the_rating() -> None:
    scheduler = AnkiSM2Scheduler()
    now = datetime.now(UTC)
    relearning = AnkiState(
        ease_factor=2.3, interval_days=20, reps=9, lapses=1, phase="relearn"
    )

    intervals = [
        scheduler.review(state=relearning, rating=rating, now=now).interval_days
        for rating in (1, 2, 3)
    ]
    assert intervals == sorted(intervals)


def test_fsrs_review_moves_the_due_deadline_off_the_deck(db_session) -> None:
    """`due_at` is the authoritative clause of the due filter. The FSRS branch
    never touched it, so an imported card credited outside the deck kept a
    stale past deadline and came back due for ever."""

    user = User(
        id=uuid4(),
        email=f"srs-cycle-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
    )
    word = VocabularyWord(
        language="fr",
        word="le radiateur",
        normalized_word="le radiateur",
        german_translation="der Heizkörper",
        english_translation="the radiator",
    )
    db_session.add_all([user, word])
    db_session.flush()

    stale = datetime.now(UTC) - timedelta(days=5)
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        scheduler="fsrs",
        state="reviewing",
        due_at=stale,
        next_review_date=stale,
        last_review_date=stale,
    )
    db_session.add(progress)
    db_session.flush()

    EnhancedSRSService(db_session).process_review(progress=progress, rating=2)
    db_session.flush()

    due_at_deadline, _ = vocabulary_due_deadline(datetime.now(UTC))
    assert progress.due_at == progress.next_review_date
    assert progress.due_at > due_at_deadline, "a card rated Bien must leave today's deck"


def test_a_card_reviewed_today_is_not_re_offered_as_fragile(db_session) -> None:
    """The fragile shelf read no dates, so every card the learner had just
    rated matched it again (a rated card is in a learning phase, or carries a
    lapse) and the deck refilled with the words that had only now left it."""

    from app.services.progress import ProgressService

    user = User(
        id=uuid4(),
        email=f"srs-fragile-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
    )
    word = VocabularyWord(
        language="fr",
        word="inquiétude",
        normalized_word="inquietude",
        german_translation="Unruhe",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
        frequency_rank=120,
    )
    db_session.add_all([user, word])
    db_session.flush()

    now = datetime.now(UTC)
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        scheduler="anki",
        state="reviewing",
        phase="learn",
        lapses=1,
        proficiency_score=20,
        due_at=now + timedelta(days=1),
        next_review_date=now + timedelta(days=1),
        last_review_date=now - timedelta(minutes=2),
    )
    db_session.add(progress)
    db_session.flush()

    service = ProgressService(db_session)
    payload = service.get_vocabulary_due_context(
        user=user, limit=10, due_limit=4, fragile_limit=4, new_limit=0,
        topic_limit=0, linked_limit=0, direction="fr_to_de", now=now,
    )
    assert word.id not in {item["word_id"] for item in payload["fragile_words"]}

    # The same card, last seen a week ago and still not due, is exactly what
    # the fragile shelf is for.
    progress.last_review_date = now - timedelta(days=7)
    db_session.flush()
    payload = service.get_vocabulary_due_context(
        user=user, limit=10, due_limit=4, fragile_limit=4, new_limit=0,
        topic_limit=0, linked_limit=0, direction="fr_to_de", now=now,
    )
    assert word.id in {item["word_id"] for item in payload["fragile_words"]}
