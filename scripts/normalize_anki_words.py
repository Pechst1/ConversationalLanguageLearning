"""
Normalize existing Anki vocabulary rows in-place.

This maintenance script re-derives the surface `word` for imported Anki cards
from their language-specific translation fields to eliminate noisy or mixed
fronts (e.g., "global, weltweit", "Motor avait"). It keeps IDs stable and
updates the `normalized_word` accordingly.

Usage examples (run inside the API container):

  docker compose -f docker/docker-compose.dev.yml exec api \
    python scripts/normalize_anki_words.py --dry-run

  docker compose -f docker/docker-compose.dev.yml exec api \
    python scripts/normalize_anki_words.py --apply

You can also limit the scope:

  python scripts/normalize_anki_words.py --apply --direction fr_to_de
  python scripts/normalize_anki_words.py --apply --limit 500
"""
from __future__ import annotations

import argparse
from typing import Optional

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.vocabulary import VocabularyWord
from app.services.anki_import import AnkiCardParser


def _derive_surface(parser: AnkiCardParser, row: VocabularyWord) -> str:
    """Return a clean surface form for a vocabulary row."""
    # Choose the language side based on direction
    source = None
    if (row.direction or '').lower() == 'fr_to_de':
        source = row.french_translation or row.word
        return parser.extract_word(source or '', expected_language='french')
    if (row.direction or '').lower() == 'de_to_fr':
        source = row.german_translation or row.word
        return parser.extract_word(source or '', expected_language='german')

    # Fallback to the declared language
    if (row.language or '').lower().startswith('fr'):
        source = row.french_translation or row.word
        return parser.extract_word(source or '', expected_language='french')
    if (row.language or '').lower().startswith('de'):
        source = row.german_translation or row.word
        return parser.extract_word(source or '', expected_language='german')

    # Last resort: generic cleaning
    source = row.word or ''
    return parser.extract_word(source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize existing Anki words in-place")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows processed")
    parser.add_argument(
        "--direction",
        choices=["fr_to_de", "de_to_fr"],
        default=None,
        help="Only normalize rows of the given direction",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stmt = select(VocabularyWord).where(VocabularyWord.is_anki_card.is_(True))
        if args.direction:
            stmt = stmt.where(VocabularyWord.direction == args.direction)
        if args.limit:
            stmt = stmt.limit(args.limit)

        rows = list(db.scalars(stmt))
        total = len(rows)
        if total == 0:
            print("No Anki vocabulary rows found to normalize.")
            return

        print(f"Scanning {total} Anki vocabulary rows…")

        card_parser = AnkiCardParser()
        changed = 0
        for row in rows:
            new_surface = _derive_surface(card_parser, row) or (row.word or '')
            new_surface = new_surface.strip()
            if not new_surface:
                continue
            # If unchanged (case-insensitive, whitespace-insensitive), skip
            if (row.word or '').strip() == new_surface:
                continue
            changed += 1
            print(f"- id={row.id} '{row.word}' -> '{new_surface}' (dir={row.direction})")
            row.word = new_surface
            row.normalized_word = card_parser.normalize_text(new_surface)

        if changed == 0:
            print("Nothing to update. All rows already normalized.")
            return

        if args.apply:
            db.commit()
            print(f"Committed updates. Rows changed: {changed}/{total}")
        else:
            db.rollback()
            print(f"Dry-run only. Rows that would change: {changed}/{total}")
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

