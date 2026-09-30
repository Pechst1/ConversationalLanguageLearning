"""WP-115c «Les mots qui reviennent»: the story carries the words that don't stick.

Owner decisions, 2026-09-30: at most two due words a day are carried by the story, and
they come from the words the learner finds hardest — a word that keeps failing in the
drill needs a *different* encounter, not more of the same one. A generated day's
director gets them as ``story_words``: a character must NEED each word from the learner
(they search for it and describe it in French without saying it), so the learner's reply
is where it is retrieved. The planner makes each one a target the reply is graded on,
and the practice after the ending takes it again if the reply did not.

Hard = at least :data:`HARD_LAPSES` lapses, or FSRS difficulty of at least
:data:`HARD_DIFFICULTY` after :data:`MIN_REPS_FOR_DIFFICULTY` reviews. Only due words
(nothing is pulled forward), only the app's own FSRS cards (an imported Anki deck is the
learner's own business), and only words with a meaning in the learner's language (the
director describes the word from its meaning).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.vocabulary import VocabularyWord

logger = logging.getLogger(__name__)

#: The story's share of the day's due words (owner, 2026-09-30).
MAX_STORY_WORDS = 2
HARD_LAPSES = 2
HARD_DIFFICULTY = 7.0
MIN_REPS_FOR_DIFFICULTY = 3
#: ``story_context`` / director-context key.
STORY_WORDS_KEY = "story_words"


def story_due_words(
    db: Session, *, user: Any, now: datetime | None = None, limit: int = MAX_STORY_WORDS
) -> list[dict[str, Any]]:
    """The learner's hardest due words: ``[{word_id, lemma, gloss_native, sentence_fr}]``."""

    from app.services.glosses import normalize_language, resolve_gloss

    now = now or datetime.now(UTC)
    due = or_(
        UserVocabularyProgress.due_at <= now,
        and_(UserVocabularyProgress.due_at.is_(None), UserVocabularyProgress.next_review_date <= now),
    )
    hard = or_(
        UserVocabularyProgress.lapses >= HARD_LAPSES,
        and_(
            UserVocabularyProgress.difficulty >= HARD_DIFFICULTY,
            UserVocabularyProgress.reps >= MIN_REPS_FOR_DIFFICULTY,
        ),
    )
    rows = db.execute(
        select(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            or_(UserVocabularyProgress.scheduler.is_(None), UserVocabularyProgress.scheduler != "anki"),
            UserVocabularyProgress.reps > 0,
            due,
            hard,
        )
        .order_by(
            UserVocabularyProgress.lapses.desc(),
            UserVocabularyProgress.difficulty.desc(),
            UserVocabularyProgress.due_at.asc().nullslast(),
            VocabularyWord.id.asc(),
        )
        .limit(limit * 4)
    ).all()
    native = normalize_language(getattr(user, "native_language", None))
    words: list[dict[str, Any]] = []
    for progress, word in rows:
        gloss, language = resolve_gloss(word, native)
        if not gloss or language != native or not word.word:
            continue
        context = progress.context if isinstance(progress.context, dict) else {}
        words.append(
            {
                "word_id": int(word.id),
                "lemma": str(word.word),
                "gloss_native": str(gloss),
                "sentence_fr": str(context.get("sentence_fr") or word.example_sentence or "") or None,
                "lapses": int(progress.lapses or 0),
            }
        )
        if len(words) >= limit:
            break
    return words


def spoiled_story_words(texts: list[str], story_words: list[dict[str, Any]]) -> list[str]:
    """The story words a scene prints: printing the word hands the learner the answer."""

    from app.services.living_story import _folded

    folded = f" {_folded(' '.join(text for text in texts if text))} "
    spoiled: list[str] = []
    for row in story_words or []:
        lemma = _folded(str(row.get("lemma") or "")).strip()
        # «la clé» is spoiled by «clé»: the article is not the word.
        head = lemma.split(" ", 1)[1] if lemma.split(" ", 1)[0] in {"le", "la", "les", "l", "un", "une"} and " " in lemma else lemma
        if head and f" {head} " in folded:
            spoiled.append(str(row.get("lemma")))
    return spoiled
