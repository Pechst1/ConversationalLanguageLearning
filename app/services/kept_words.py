"""WP-78 — «Garder» : a word tapped in the story joins the learner's Lexique.

The story reader already lets a learner tap a word for its meaning
(``WordHelpSheet``). This module is the second half of that gesture: *keep it*.

What keeping writes, and where
------------------------------

* **One learner-scoped example.** A :class:`WordInteraction` row
  (``interaction_type="kept_from_story"``) holding the scene sentence the word
  was tapped in (``context_sentence``), the surface form as printed
  (``user_response``) and the gloss in the learner's language
  (``correction``, which is what the word biography shows as the example's
  translation). It belongs to the learner and names their learning session.
* **One learner-scoped progress row.** A :class:`UserVocabularyProgress` for
  the word, created ``new`` and due now when the learner has none, stamped
  ``provenance="kept_from_story"``. A card the learner already has keeps its
  schedule — keeping a word never resets weeks of work.
* **Nothing shared.** The catalogue row (:class:`VocabularyWord`) is read, never
  written: no example sentence, no gloss and no placeholder lands on a row
  other learners read (the WP-74 rule). A word the catalogue does not know, or
  knows only in another language than the learner's, is not kept — the sheet
  says so rather than inventing a meaning.

Who reads it
------------

* ``journey_learning.select_learning_candidates`` marks kept words, ranks them
  first and hands the planner the kept sentence, so tomorrow's quick items
  bring the word back — rebuilt from the very sentence it was kept with.
* :func:`kept_words_for` is the story engine's hook: the words a learner chose
  to keep, with the sentence and the gloss, for the director to reuse.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.glosses import normalize_language, resolve_gloss
from app.services.vocabulary import VocabularyNotFoundError, VocabularyService

KEPT_INTERACTION_TYPE = "kept_from_story"
KEPT_PROVENANCE = "kept_from_story"
#: A kept word is a planner preference for this long; after that it is an
#: ordinary card in the learner's queue.
KEPT_RECENT_DAYS = 14
#: The sentence is what the learner read. Bounded so a runaway client cannot
#: store a chapter.
MAX_SENTENCE_CHARS = 400
MAX_TERM_CHARS = 80
#: The session a keep is filed under when it happens outside a journey (the
#: standalone Feuilleton reader).
KEEP_SESSION_STYLE = "story_reader"


class KeepRefused(ValueError):
    """The word cannot be kept honestly. ``reason`` is a stable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class KeptWord:
    word_id: int
    word: str
    surface: str
    gloss: str
    gloss_language: str
    example_fr: str
    kept_at: datetime | None
    already_kept: bool = False

    def as_public(self) -> dict[str, Any]:
        return {
            "word_id": self.word_id,
            "word": self.word,
            "surface": self.surface,
            "gloss": self.gloss,
            "gloss_language": self.gloss_language,
            "example_fr": self.example_fr,
            "kept_at": self.kept_at.isoformat() if self.kept_at else None,
            "already_kept": self.already_kept,
        }


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _session_for(db: Session, user: User, journey_id: UUID | None) -> LearningSession:
    """The learning session a keep is filed under: the journey's own when the
    word was tapped inside today's scene, else the learner's reader session."""

    if journey_id is not None:
        from app.db.models.daily_journey import DailyJourney

        journey = db.get(DailyJourney, journey_id)
        if journey is not None and journey.user_id == user.id and journey.learning_session_id:
            session = db.get(LearningSession, journey.learning_session_id)
            if session is not None:
                return session
    session = db.scalars(
        select(LearningSession)
        .where(
            LearningSession.user_id == user.id,
            LearningSession.conversation_style == KEEP_SESSION_STYLE,
        )
        .order_by(LearningSession.created_at.desc())
        .limit(1)
    ).first()
    if session is None:
        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=0,
            topic="story_reader:kept_words",
            conversation_style=KEEP_SESSION_STYLE,
            status="in_progress",
        )
        db.add(session)
        db.flush([session])
    return session


def keep_word(
    db: Session,
    *,
    user: User,
    term: str,
    sentence: str,
    surface: str | None = None,
    journey_id: UUID | None = None,
    now: datetime | None = None,
) -> KeptWord:
    """Keep one tapped word. Idempotent per (learner, word, sentence).

    Flushes, never commits: the endpoint owns the transaction.
    """

    now = now or datetime.now(UTC)
    term = _clean(term, MAX_TERM_CHARS)
    sentence = _clean(sentence, MAX_SENTENCE_CHARS)
    surface = _clean(surface or term, MAX_TERM_CHARS)
    if not term:
        raise KeepRefused("empty_term")
    if not sentence:
        # The example *is* the point: a kept word comes back in its sentence.
        raise KeepRefused("no_sentence")
    language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    try:
        word = VocabularyService(db).lookup_word(term=term, language=language)
    except VocabularyNotFoundError as exc:
        raise KeepRefused("not_in_lexicon") from exc
    native = normalize_language(getattr(user, "native_language", None))
    gloss, gloss_language = resolve_gloss(word, native)
    if not gloss or gloss_language != native:
        # A meaning in another language than the learner's would be a
        # placeholder by another name.
        raise KeepRefused("no_gloss_in_learner_language")

    existing = db.scalars(
        select(WordInteraction)
        .where(
            WordInteraction.user_id == user.id,
            WordInteraction.word_id == word.id,
            WordInteraction.interaction_type == KEPT_INTERACTION_TYPE,
            WordInteraction.context_sentence == sentence,
        )
        .limit(1)
    ).first()
    already = existing is not None
    if existing is None:
        session = _session_for(db, user, journey_id)
        existing = WordInteraction(
            session_id=session.id,
            user_id=user.id,
            word_id=word.id,
            interaction_type=KEPT_INTERACTION_TYPE,
            context_sentence=sentence,
            user_response=surface,
            correction=gloss,
            was_suggested=False,
            created_at=now,
        )
        db.add(existing)
        db.flush([existing])

    progress = db.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word.id,
        )
    ).first()
    if progress is None:
        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            state="new",
            phase="new",
            scheduler="fsrs",
            due_at=now,
            next_review_date=now,
            due_date=now.date(),
            provenance=KEPT_PROVENANCE,
            provenance_ref=str(existing.id),
        )
        db.add(progress)
    elif not progress.provenance:
        # Only an unlabelled card gains the label; a word the learner brought
        # in from their own document stays theirs-by-document.
        progress.provenance = KEPT_PROVENANCE
        progress.provenance_ref = str(existing.id)
    db.flush()
    return KeptWord(
        word_id=int(word.id),
        word=str(word.word),
        surface=surface,
        gloss=gloss,
        gloss_language=str(gloss_language),
        example_fr=sentence,
        kept_at=getattr(existing, "created_at", None) or now,
        already_kept=already,
    )


def kept_words_for(
    db: Session,
    *,
    user_id: UUID,
    since: datetime | None = None,
    limit: int = 20,
) -> list[KeptWord]:
    """The words this learner kept, newest first, one row per word.

    The story engine's hook (WP-78 → Codex): the director may bring these back
    into a scene. Read-only, learner-scoped, and it never reads a sentence
    another learner kept.
    """

    stmt = (
        select(WordInteraction, VocabularyWord)
        .join(VocabularyWord, VocabularyWord.id == WordInteraction.word_id)
        .where(
            WordInteraction.user_id == user_id,
            WordInteraction.interaction_type == KEPT_INTERACTION_TYPE,
        )
        .order_by(WordInteraction.created_at.desc(), WordInteraction.id)
        .limit(max(1, limit) * 3)
    )
    kept: list[KeptWord] = []
    seen: set[int] = set()
    for interaction, word in db.execute(stmt).all():
        if int(word.id) in seen:
            continue
        # Compared here rather than in SQL: SQLite stores these naive.
        if since is not None and _aware(interaction.created_at) < _aware(since):
            continue
        seen.add(int(word.id))
        kept.append(
            KeptWord(
                word_id=int(word.id),
                word=str(word.word),
                surface=str(interaction.user_response or word.word),
                gloss=str(interaction.correction or ""),
                gloss_language="",
                example_fr=str(interaction.context_sentence or ""),
                kept_at=interaction.created_at,
                already_kept=True,
            )
        )
        if len(kept) >= limit:
            break
    return kept


def recent_kept_words(
    db: Session, *, user_id: UUID, now: datetime | None = None, limit: int = 20
) -> dict[int, KeptWord]:
    """``{word_id: KeptWord}`` for the planner's preference window."""

    now = now or datetime.now(UTC)
    rows = kept_words_for(
        db, user_id=user_id, since=now - timedelta(days=KEPT_RECENT_DAYS), limit=limit
    )
    return {row.word_id: row for row in rows}


# --------------------------------------------------------------------------
# WP-86 — the words a scene teaches
# --------------------------------------------------------------------------

SCENE_LEXICON_INTERACTION_TYPE = "scene_lexicon"
SCENE_LEXICON_TAG = "scene_lexicon"
#: How many words of recent scenes the director is reminded of.
DIRECTOR_HISTORY_LIMIT = 15
DIRECTOR_KEPT_LIMIT = 8
_GLOSS_COLUMN = {"de": "german_translation", "en": "english_translation", "fr": "french_translation"}
_BAND_DIFFICULTY = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 5}


def _catalogue_row(db: Session, *, language: str, lemma: str) -> VocabularyWord | None:
    """The shared row for a lemma — never one the old mission bank polluted."""

    from app.services.missions import is_polluted_mission_word

    key = " ".join(lemma.split()).lower()
    rows = db.scalars(
        select(VocabularyWord)
        .where(VocabularyWord.language == language, VocabularyWord.normalized_word == key)
        .order_by(VocabularyWord.frequency_rank.asc().nullslast(), VocabularyWord.id.asc())
        .limit(5)
    ).all()
    return next((row for row in rows if not is_polluted_mission_word(row)), None)


def rank_lookup(db: Session, *, language: str = "fr"):
    """A memoised ``lemma -> French 5000 rank`` for the lexicon's soft band score."""

    cache: dict[str, int | None] = {}

    def rank_of(lemma: str) -> int | None:
        key = " ".join(str(lemma or "").split()).lower()
        if key not in cache:
            row = _catalogue_row(db, language=language, lemma=key) if key else None
            cache[key] = int(row.frequency_rank) if row is not None and row.frequency_rank else None
        return cache[key]

    return rank_of


def director_vocabulary(db: Session, *, user_id: UUID) -> dict[str, list[dict[str, str]]]:
    """What the director may bring back: kept words, and recent scenes' words.

    Learner-scoped reads only; bounded, so the prompt does not grow with a life.
    """

    kept = [
        {"word": row.word, "gloss": row.gloss, "example_fr": row.example_fr}
        for row in kept_words_for(db, user_id=user_id, limit=DIRECTOR_KEPT_LIMIT)
    ]
    rows = db.execute(
        select(WordInteraction.word_id, WordInteraction.user_response, VocabularyWord.word)
        .join(VocabularyWord, VocabularyWord.id == WordInteraction.word_id)
        .where(
            WordInteraction.user_id == user_id,
            WordInteraction.interaction_type == SCENE_LEXICON_INTERACTION_TYPE,
        )
        .order_by(WordInteraction.created_at.desc(), WordInteraction.id)
        .limit(DIRECTOR_HISTORY_LIMIT * 3)
    ).all()
    history: list[str] = []
    for _word_id, _surface, lemma in rows:
        if lemma and lemma not in history:
            history.append(str(lemma))
        if len(history) >= DIRECTOR_HISTORY_LIMIT:
            break
    return {"kept_words": kept, "lexicon_history": history}


@dataclass(frozen=True, slots=True)
class SceneWord:
    """One validated lexicon entry, matched to (or entered in) the catalogue."""

    word_id: int
    lemma: str
    surface: str
    gloss: str
    sentence: str
    part_of_speech: str | None
    gender: str | None
    created: bool
    studied: bool


def record_scene_lexicon(
    db: Session,
    *,
    user: User,
    entries: list[dict[str, Any]],
    sentences: dict[str, str],
    level: str | None = None,
    journey_id: UUID | None = None,
    now: datetime | None = None,
) -> list[SceneWord]:
    """Match a scene's lexicon to the catalogue, learner-safely (the WP-74 rule).

    * An existing row is **reused and never written**: no gloss, example or tag
      lands on a row other learners read.
    * A lemma the catalogue lacks gets a row whose only gloss is the learner's
      language, in that language's column — never an English placeholder for a
      German speaker. A language without a column gets no stored gloss at all.
    * The learner's own record is one :class:`WordInteraction`
      (``scene_lexicon``): the sentence the word was taught in, the surface as
      printed and the gloss in the learner's language. Idempotent per
      (learner, word, sentence). No progress row: a word enters the Lexique once
      it is practised, through the ordinary evidence path.

    Flushes, never commits.
    """

    now = now or datetime.now(UTC)
    language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    native = normalize_language(getattr(user, "native_language", None))
    words: list[SceneWord] = []
    session: LearningSession | None = None
    for entry in entries:
        lemma = _clean(entry.get("lemma") or entry.get("surface_fr"), MAX_TERM_CHARS)
        surface = _clean(entry.get("surface_fr") or lemma, MAX_TERM_CHARS)
        gloss = _clean(entry.get("gloss_native"), MAX_TERM_CHARS * 2)
        sentence = _clean(sentences.get(lemma) or "", MAX_SENTENCE_CHARS)
        if not lemma or not gloss:
            continue
        word = _catalogue_row(db, language=language, lemma=lemma)
        created = word is None
        if word is None:
            column = _GLOSS_COLUMN.get(native)
            word = VocabularyWord(
                language=language,
                word=lemma,
                normalized_word=lemma.lower(),
                part_of_speech=entry.get("part_of_speech") or None,
                gender=entry.get("gender") or None,
                difficulty_level=_BAND_DIFFICULTY.get(str(level or "").upper(), 2),
                topic_tags=[SCENE_LEXICON_TAG],
                usage_notes="Mot appris dans une scène du feuilleton.",
                **({column: gloss} if column else {}),
            )
            db.add(word)
            db.flush([word])
        if sentence:
            exists = db.scalars(
                select(WordInteraction.id).where(
                    WordInteraction.user_id == user.id,
                    WordInteraction.word_id == word.id,
                    WordInteraction.interaction_type == SCENE_LEXICON_INTERACTION_TYPE,
                    WordInteraction.context_sentence == sentence,
                ).limit(1)
            ).first()
            if exists is None:
                session = session or _session_for(db, user, journey_id)
                db.add(
                    WordInteraction(
                        session_id=session.id,
                        user_id=user.id,
                        word_id=word.id,
                        interaction_type=SCENE_LEXICON_INTERACTION_TYPE,
                        context_sentence=sentence,
                        user_response=surface,
                        correction=gloss,
                        was_suggested=True,
                        created_at=now,
                    )
                )
        progress = db.scalars(
            select(UserVocabularyProgress.reps).where(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.word_id == word.id,
            )
        ).first()
        words.append(
            SceneWord(
                word_id=int(word.id),
                lemma=str(word.word),
                surface=surface,
                gloss=gloss,
                sentence=sentence,
                part_of_speech=entry.get("part_of_speech") or None,
                gender=entry.get("gender") or None,
                created=created,
                studied=bool(progress),
            )
        )
    db.flush()
    return words

__all__ = [
    "SCENE_LEXICON_INTERACTION_TYPE",
    "SceneWord",
    "director_vocabulary",
    "rank_lookup",
    "record_scene_lexicon",
    "KEEP_SESSION_STYLE",
    "KEPT_INTERACTION_TYPE",
    "KEPT_PROVENANCE",
    "KEPT_RECENT_DAYS",
    "KeepRefused",
    "KeptWord",
    "keep_word",
    "kept_words_for",
    "recent_kept_words",
]
