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


def met_context(*, sentence: str, journey_id: UUID | None, met: dict | None, now: datetime) -> dict:
    """WP-115a: where a word was met — the sentence, who said it, the day's journey,
    the panel and the line's audio key. Only what was sent is kept."""

    fields = {key: str(value)[:120] for key, value in (met or {}).items() if value}
    return {
        "sentence_fr": sentence,
        **({"journey_id": str(journey_id)} if journey_id else {}),
        **fields,
        "met_on": now.date().isoformat(),
    }


def keep_word(
    db: Session,
    *,
    user: User,
    term: str,
    sentence: str,
    surface: str | None = None,
    journey_id: UUID | None = None,
    now: datetime | None = None,
    met: dict | None = None,
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
    if not progress.context:
        # WP-115a: the first meeting is the one a review brings back.
        progress.context = met_context(sentence=sentence, journey_id=journey_id, met=met, now=now)
        # Owner decision 2026-10-08: the form the word had in the line («venez» for
        # «venir») is context, not a new item — the scene card blanks it.
        if surface:
            progress.context = {**progress.context, "surface_fr": surface}
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
#: WP-L6 (§5.1): words the learner drills but does not hold yet, offered to
#: the director so a scene can double as their review.
DIRECTOR_DRILLED_LIMIT = 8
#: Held = memory stability of three weeks (a prior until WP-L3's rule).
DRILLED_HELD_STABILITY_DAYS = 21.0
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
    return {
        "kept_words": kept,
        "lexicon_history": history,
        "drilled_words": drilled_not_held_words(db, user_id=user_id),
    }


def drilled_not_held_words(
    db: Session, *, user_id: UUID, limit: int = DIRECTOR_DRILLED_LIMIT
) -> list[str]:
    """WP-L6: the words this learner has reviewed but does not hold yet,
    most recently reviewed first. Read-only and bounded."""

    rows = db.execute(
        select(VocabularyWord.word)
        .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
        .where(
            UserVocabularyProgress.user_id == user_id,
            UserVocabularyProgress.reps > 0,
            UserVocabularyProgress.stability < DRILLED_HELD_STABILITY_DAYS,
        )
        .order_by(
            UserVocabularyProgress.last_review_date.desc().nullslast(),
            VocabularyWord.id.asc(),
        )
        .limit(limit * 2)
    ).all()
    words: list[str] = []
    for (word,) in rows:
        if word and word not in words:
            words.append(str(word))
        if len(words) >= limit:
            break
    return words


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


# --------------------------------------------------------------------------
# WP-121 — Le Palais de mémoire: words kept in a Papier, tied to a place
# --------------------------------------------------------------------------

REVUE_INTERACTION_TYPE = "kept_from_revue"
REVUE_PROVENANCE = "kept_from_revue"
REVUE_TOPIC_TAG = "revue"
#: How many due cards the palace reads at most (a learner's whole due queue is smaller).
PALACE_SCAN_LIMIT = 1000
_PLACE_FIELDS = ("source", "session_id", "dossier_id", "place_id", "place_label_fr", "week")
_LEADING_ARTICLE = ("le ", "la ", "les ", "un ", "une ", "des ", "du ", "l'", "l’")


@dataclass(frozen=True, slots=True)
class RevueKeep:
    """What :func:`keep_revue_word` did for one word of a Papier."""

    word_id: int
    word: str
    created: bool
    stepped_ahead: bool
    already: bool


@dataclass(frozen=True, slots=True)
class DueWord:
    """One due card, with the Papier place it was (last) met in."""

    progress_id: str
    word_id: int
    word: str
    gloss: str
    sentence_fr: str
    session_id: str
    dossier_id: str
    place_id: str
    place_label_fr: str
    week: str
    met_on: str
    due_at: datetime | None


def _bare_term(term: str) -> str:
    lowered = term.lower()
    for article in _LEADING_ARTICLE:
        if lowered.startswith(article) and len(term) > len(article):
            return term[len(article):].strip()
    return term


def _revue_catalogue_row(db: Session, *, language: str, term: str) -> VocabularyWord | None:
    """The shared row for a Papier word: the phrase as kept, else without its article."""

    row = _catalogue_row(db, language=language, lemma=term)
    if row is None and _bare_term(term) != term:
        row = _catalogue_row(db, language=language, lemma=_bare_term(term))
    return row


def place_entries(context: dict | None) -> list[dict]:
    """The Papier places a card was met in, oldest first (``context["places"]``)."""

    if not isinstance(context, dict):
        return []
    places = [p for p in context.get("places") or [] if isinstance(p, dict) and p.get("place_id")]
    if not places and context.get("source") == "revue" and context.get("place_id"):
        places = [context]
    return places


def latest_place(context: dict | None) -> dict | None:
    """The most recent Papier place of a card (A.1: a word met in several belongs to the last)."""

    places = place_entries(context)
    if not places:
        return None
    indexed = list(enumerate(places))
    return max(indexed, key=lambda pair: (str(pair[1].get("met_on") or ""), pair[0]))[1]


def place_line_fr(context: dict | None) -> str | None:
    """A.4: «vu au marché d'Aligre, semaine 41» for a card met in a Papier, else None."""

    place = latest_place(context)
    if place is None:
        return None
    label = str(place.get("place_name_fr") or place.get("place_label_fr") or "").split(",")[0].strip()
    if not label:
        return None
    week = str(place.get("week") or "")
    number = week.rsplit("W", 1)[-1].lstrip("0") if "W" in week else ""
    return f"vu {_contract_a(label)}" + (f", semaine {number}" if number else "")


def _contract_a(label: str) -> str:
    """«à» + the place: «Le marché d'Aligre» → «au marché d'Aligre»."""

    lowered = label.lower()
    if lowered.startswith("le "):
        return "au " + label[3:]
    if lowered.startswith("les "):
        return "aux " + label[4:]
    if lowered.startswith("la "):
        return "à la " + label[3:]
    if lowered.startswith(("l'", "l’")):
        return "à l'" + label[2:]
    return "à " + label


def keep_revue_word(
    db: Session,
    *,
    user: User,
    term: str,
    gloss: str,
    sentence: str,
    met: dict[str, Any],
    used_correctly: bool = False,
    now: datetime | None = None,
) -> RevueKeep | None:
    """A.0: one word a Papier kept enters the learner's SRS, tied to its place.

    The Papier's own vocabulary carries a gloss in the learner's language, so a word
    the catalogue lacks is entered learner-safely (the WP-86 rule: its only gloss is
    the learner's language, in that language's column) rather than refused. An
    existing catalogue row is reused and never written.

    * the card is created ``new`` and due now (provenance ``kept_from_revue``); a card
      the learner already has keeps its schedule;
    * ``context["places"]`` gains this Papier's place (``met``: ``session_id``,
      ``dossier_id``, ``place_id``, ``place_label_fr``, ``week``) once per session;
    * a word the learner used correctly in the Papier (``used_correctly``) on a card
      this keep created starts one step ahead: one «Bien» through ``EnhancedSRSService``.

    Idempotent per (learner, word, session). Flushes, never commits. ``None`` when the
    word has no text or no gloss in the learner's language.
    """

    now = now or datetime.now(UTC)
    term = _clean(term, MAX_TERM_CHARS)
    sentence = _clean(sentence, MAX_SENTENCE_CHARS)
    gloss = _clean(gloss, MAX_TERM_CHARS * 2)
    session_id = str(met.get("session_id") or "")
    if not term or not session_id:
        return None
    language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    native = normalize_language(getattr(user, "native_language", None))
    word = _revue_catalogue_row(db, language=language, term=term)
    if word is None:
        if not gloss:
            return None
        column = _GLOSS_COLUMN.get(native)
        word = VocabularyWord(
            language=language,
            word=term,
            normalized_word=term.lower(),
            difficulty_level=2,
            topic_tags=[REVUE_TOPIC_TAG],
            usage_notes="Mot gardé dans un Papier de Romy.",
            **({column: gloss} if column else {}),
        )
        db.add(word)
        db.flush([word])
    if not gloss:
        resolved, resolved_language = resolve_gloss(word, native)
        gloss = resolved if resolved and resolved_language == native else ""

    interaction = db.scalars(
        select(WordInteraction)
        .where(
            WordInteraction.user_id == user.id,
            WordInteraction.word_id == word.id,
            WordInteraction.interaction_type == REVUE_INTERACTION_TYPE,
            WordInteraction.context_sentence == (sentence or term),
        )
        .limit(1)
    ).first()
    if interaction is None:
        session = _session_for(db, user, None)
        interaction = WordInteraction(
            session_id=session.id,
            user_id=user.id,
            word_id=word.id,
            interaction_type=REVUE_INTERACTION_TYPE,
            context_sentence=sentence or term,
            user_response=term,
            correction=gloss or None,
            was_suggested=True,
            created_at=now,
        )
        db.add(interaction)
        db.flush([interaction])

    progress = db.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word.id,
        )
    ).first()
    created = progress is None
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
            provenance=REVUE_PROVENANCE,
            provenance_ref=session_id[:64],
            reps=0,
            lapses=0,
            times_seen=0,
            correct_count=0,
            incorrect_count=0,
            proficiency_score=0,
        )
        db.add(progress)
        db.flush([progress])
    elif not progress.provenance:
        progress.provenance = REVUE_PROVENANCE
        progress.provenance_ref = session_id[:64]

    entry = {key: str(met[key])[:200] for key in _PLACE_FIELDS if met.get(key)}
    entry.update(source="revue", sentence_fr=sentence, gloss=gloss, met_on=now.date().isoformat())
    if met.get("place_name_fr"):
        entry["place_name_fr"] = str(met["place_name_fr"])[:200]
    context = dict(progress.context) if isinstance(progress.context, dict) else {}
    places = list(context.get("places") or [])
    already = any(isinstance(p, dict) and p.get("session_id") == session_id for p in places)
    if not already:
        if not context:
            context = met_context(
                sentence=sentence or term,
                journey_id=None,
                met={k: v for k, v in entry.items() if k in _PLACE_FIELDS},
                now=now,
            )
        context["places"] = [*places, entry]
        progress.context = context  # a new dict: JSON columns track assignment

    stepped = False
    if created and used_correctly and not already:
        from app.core.srs.memory import Rating
        from app.services.enhanced_srs import EnhancedSRSService

        EnhancedSRSService(db).process_review(
            progress, int(Rating.GOOD), now=now, source="revue_close", review_format="produce"
        )
        stepped = True
    db.flush()
    return RevueKeep(word_id=int(word.id), word=str(word.word), created=created, stepped_ahead=stepped, already=already)


def words_due_by_place(
    db: Session, *, user_id: UUID, now: datetime | None = None
) -> dict[str, list[DueWord]]:
    """A.1: the learner's due cards met in a Papier, grouped by that Papier's place.

    A word met in several places belongs to the most recent one. Learner-scoped,
    read-only, no model call. Within a place, the most overdue first.
    """

    from app.services.progress import vocabulary_due_filter

    now = now or datetime.now(UTC)
    rows = db.execute(
        select(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
        .where(
            UserVocabularyProgress.user_id == user_id,
            UserVocabularyProgress.context.isnot(None),
            vocabulary_due_filter(now),
        )
        .limit(PALACE_SCAN_LIMIT)
    ).all()
    grouped: dict[str, list[DueWord]] = {}
    for progress, word in rows:
        place = latest_place(progress.context)
        if place is None:
            continue
        due_at = progress.due_at or progress.next_review_date
        grouped.setdefault(str(place["place_id"]), []).append(
            DueWord(
                progress_id=str(progress.id),
                word_id=int(word.id),
                word=str(word.word),
                gloss=str(place.get("gloss") or ""),
                sentence_fr=str(place.get("sentence_fr") or ""),
                session_id=str(place.get("session_id") or ""),
                dossier_id=str(place.get("dossier_id") or ""),
                place_id=str(place["place_id"]),
                place_label_fr=str(place.get("place_label_fr") or ""),
                week=str(place.get("week") or ""),
                met_on=str(place.get("met_on") or ""),
                due_at=due_at,
            )
        )
    for words in grouped.values():
        words.sort(key=lambda w: (_aware(w.due_at), w.word_id))
    return grouped


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
    "DueWord",
    "REVUE_INTERACTION_TYPE",
    "REVUE_PROVENANCE",
    "RevueKeep",
    "keep_revue_word",
    "latest_place",
    "place_entries",
    "place_line_fr",
    "words_due_by_place",
]
