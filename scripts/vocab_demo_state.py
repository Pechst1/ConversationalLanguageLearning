#!/usr/bin/env python
"""Give a TEST learner a believable vocabulary history (WP-115), so the owner can see
the new word learning on the test copy without waiting weeks for it to build up.

    venv/bin/python scripts/vocab_demo_state.py \\
        --database-url postgresql://localhost/atelier_e2e_0926 \\
        --email saison1-test-2026-09-30@example.com --apply

Every card below is made due now, so «Cahier → Révisions» shows the ladder at once:

* ``clé`` — kept from Margaux's line «Elle ne donnait jamais cette clé.», seen once:
  the **scene** rung (its own line, blanked);
* ``porte`` — six lapses: the **rescue** rung (first letter and length);
* ``vendre``, ``monter`` — hard words (3 and 2 lapses): the ones the **story** carries
  on a generated day and the **weekly letter** asks for;
* ``lettre`` / ``café`` / ``appartement`` / ``valise`` — recognition, production,
  audio and cloze strengths;
* past review logs with the scheduler's prediction, so
  ``scripts/vocab_retention_report.py`` has a curve to draw.

Refuses the owner's live ``language_learning`` database; prints what it would write
without ``--apply``.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

#: lemma → (stability days, lapses, reps, difficulty, context)
CARDS: dict[str, tuple[float, int, int, float, dict | None]] = {
    "clé": (2.0, 0, 1, 5.0, {
        "sentence_fr": "Elle ne donnait jamais cette clé.",
        "speaker_id": "margaux_barman",
        "met_on": "2026-09-30",
    }),
    "porte": (0.6, 6, 9, 9.0, None),
    "vendre": (1.2, 3, 5, 7.6, None),
    "monter": (1.5, 2, 4, 7.1, None),
    "lettre": (1.0, 0, 2, 5.0, None),
    "café": (4.5, 0, 3, 4.5, None),
    "appartement": (12.0, 0, 4, 4.0, None),
    "valise": (35.0, 0, 6, 3.5, None),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if "language_learning" in args.database_url:
        raise SystemExit("Refusing the owner's live language_learning database.")
    os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models.progress import ReviewLog, UserVocabularyProgress
    from app.db.models.user import User
    from app.db.models.vocabulary import VocabularyWord
    from app.services.kept_words import KEPT_PROVENANCE
    from app.services.vocab_fsrs import retrievability

    url = args.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    now = datetime.now(UTC)
    with Session(create_engine(url)) as db:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(f"no user {args.email}")
        for lemma, (stability, lapses, reps, difficulty, context) in CARDS.items():
            word = db.scalars(
                select(VocabularyWord)
                .where(VocabularyWord.language == "fr", VocabularyWord.word == lemma)
                .order_by(VocabularyWord.is_anki_card.desc(), VocabularyWord.english_translation.is_(None))
            ).first()
            if word is None:
                print(f"skip {lemma}: not in the catalogue")
                continue
            progress = db.scalar(
                select(UserVocabularyProgress).where(
                    UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id
                )
            )
            if progress is None:
                progress = UserVocabularyProgress(user_id=user.id, word_id=word.id)
                db.add(progress)
            elapsed = max(1.0, stability * 1.4)
            progress.scheduler = "fsrs"
            progress.state = "reviewing"
            progress.phase = "review"
            progress.stability = stability
            progress.difficulty = difficulty
            progress.reps = reps
            progress.lapses = lapses
            progress.last_review_date = now - timedelta(days=elapsed)
            progress.due_at = now - timedelta(hours=1)
            progress.next_review_date = progress.due_at
            progress.due_date = progress.due_at.date()
            if context:
                progress.context = context
                progress.provenance = KEPT_PROVENANCE
            db.flush()
            # A little past: one delayed review per card, as the scheduler logs them.
            db.add(
                ReviewLog(
                    progress_id=progress.id,
                    rating=0 if lapses >= 2 else 2,
                    review_date=now - timedelta(days=elapsed),
                    source="drill",
                    format="typed",
                    predicted_r=round(retrievability(max(stability, 0.5), 7.0), 4),
                    elapsed_days_exact=7.0,
                )
            )
            print(f"{lemma:<12} stability {stability:>5}  lapses {lapses}  reps {reps}  → due now")
        if not args.apply:
            db.rollback()
            print("(dry run: add --apply to write)")
            return 0
        db.commit()
        print(f"{args.email}: vocabulary history written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
