#!/usr/bin/env python
"""WP-74 — remove the vocabulary the old mission phrase bank invented.

Before WP-74, completing a Courrier mission wrote the learner's own sentences
(often uncorrected: «une photo de mon porte hier») and quick-reply scaffolds
into the *shared* ``vocabulary_words`` catalogue with a placeholder English
gloss («Polished mission dispatch», «Mission-ready phrase»…), and credited each
one as answered correctly without any review.

This finds those rows (``missions.is_polluted_mission_word``: the
``mission_phrase`` tag or a placeholder gloss) and, with ``--apply``, deletes
them together with the progress, review logs and interactions that hang off
them. Error-memory rows that link to them keep their text; the link is cleared.

Dry run is the default and changes nothing::

    venv/bin/python scripts/cleanup_mission_vocabulary.py          # report only
    venv/bin/python scripts/cleanup_mission_vocabulary.py --apply  # delete
"""
from __future__ import annotations

import argparse
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.db.models.vocabulary import VocabularyWord
from app.services.missions import MISSION_PLACEHOLDER_GLOSSES, is_polluted_mission_word


def find_polluted_words(db: Session) -> list[VocabularyWord]:
    candidates = db.scalars(
        select(VocabularyWord).where(
            or_(
                VocabularyWord.topic_tags.isnot(None),
                VocabularyWord.english_translation.isnot(None),
            )
        )
    ).all()
    return [word for word in candidates if is_polluted_mission_word(word)]


def cleanup(db: Session, *, apply: bool) -> dict[str, Any]:
    words = find_polluted_words(db)
    word_ids = [word.id for word in words]
    progress_ids = (
        list(db.scalars(select(UserVocabularyProgress.id).where(UserVocabularyProgress.word_id.in_(word_ids))))
        if word_ids
        else []
    )
    report = {
        "polluted_words": len(word_ids),
        "progress_rows": len(progress_ids),
        "learners": len(
            set(db.scalars(select(UserVocabularyProgress.user_id).where(UserVocabularyProgress.id.in_(progress_ids))))
        )
        if progress_ids
        else 0,
        "examples": [
            {"id": word.id, "word": word.word, "gloss": word.english_translation} for word in words[:10]
        ],
        "placeholder_glosses": sorted(MISSION_PLACEHOLDER_GLOSSES),
        "applied": apply,
    }
    if apply and word_ids:
        if progress_ids:
            db.execute(delete(ReviewLog).where(ReviewLog.progress_id.in_(progress_ids)))
        db.execute(delete(WordInteraction).where(WordInteraction.word_id.in_(word_ids)))
        db.execute(delete(UserVocabularyProgress).where(UserVocabularyProgress.word_id.in_(word_ids)))
        db.execute(update(UserError).where(UserError.linked_word_id.in_(word_ids)).values(linked_word_id=None))
        db.execute(delete(VocabularyWord).where(VocabularyWord.id.in_(word_ids)))
        db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="delete the rows (default: dry run)")
    args = parser.parse_args()

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        report = cleanup(db, apply=args.apply)
    finally:
        db.close()
    mode = "APPLIED" if report["applied"] else "DRY RUN (nothing changed)"
    print(f"{mode}: {report['polluted_words']} polluted mission words, "
          f"{report['progress_rows']} progress rows across {report['learners']} learner(s)")
    for example in report["examples"]:
        print(f"  #{example['id']}: {example['word']!r} — {example['gloss']!r}")


if __name__ == "__main__":
    main()
