"""Backfill example sentences for imported Anki vocabulary rows.

The early French 5000 import kept the clean word/translation but discarded the
example sentence pairs embedded in the Anki export. This script re-reads the
export and fills `example_sentence` / `example_translation` on matching rows.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models.vocabulary import VocabularyWord
from app.db.session import SessionLocal
from app.services.anki_import import AnkiImportService


DEFAULT_CSV = ROOT / "Anki_cards___2025-11-01T13-09-36.csv"


def _card_identity(importer: AnkiImportService, card: dict) -> tuple[str, str, str, str]:
    front = card["front"]
    back = card["back"]
    front_primary = card.get("front_primary") or front
    back_primary = card.get("back_primary") or back
    front_lang = card["front_language"]
    back_lang = card["back_language"]
    direction_hint = card.get("direction_hint")

    if direction_hint == "fr_to_de":
        direction = "fr_to_de"
        word = importer.parser.extract_word(front_primary, expected_language="french")
        language = "fr"
        french_translation = front_primary
    elif direction_hint == "de_to_fr":
        direction = "de_to_fr"
        word = importer.parser.extract_word(front_primary, expected_language="german")
        language = "de"
        french_translation = back_primary
    elif front_lang == "french" and back_lang in ["german", "mixed"]:
        direction = "fr_to_de"
        word = importer.parser.extract_word(front_primary, expected_language="french")
        language = "fr"
        french_translation = front_primary
    elif front_lang in ["german", "mixed"] and back_lang == "french":
        direction = "de_to_fr"
        word = importer.parser.extract_word(front_primary, expected_language="german")
        language = "de"
        french_translation = back_primary
    elif front_lang == "french":
        direction = "fr_to_de"
        word = importer.parser.extract_word(front_primary, expected_language="french")
        language = "fr"
        french_translation = front_primary
    else:
        direction = "de_to_fr"
        word = importer.parser.extract_word(front_primary, expected_language="german")
        language = "de"
        french_translation = back_primary

    target = word if direction == "fr_to_de" else importer.parser.extract_word(
        french_translation,
        expected_language="french",
    )
    return word, language, direction, target


def _find_word(db, *, card: dict, word: str, language: str, direction: str) -> VocabularyWord | None:
    card_id = str(card.get("card_id") or "").strip()
    if card_id:
        row = db.scalars(select(VocabularyWord).where(VocabularyWord.card_id == card_id)).first()
        if row:
            return row

    note_id = str(card.get("note_id") or "").strip()
    if note_id:
        row = db.scalars(
            select(VocabularyWord).where(
                VocabularyWord.note_id == note_id,
                VocabularyWord.direction == direction,
            )
        ).first()
        if row:
            return row

    return db.scalars(
        select(VocabularyWord).where(
            VocabularyWord.word == word,
            VocabularyWord.language == language,
            VocabularyWord.direction == direction,
        )
    ).first()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Anki vocabulary examples")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--apply", action="store_true", help="Persist updates")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing examples")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    csv_path = args.csv
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    db = SessionLocal()
    try:
        importer = AnkiImportService(db)
        cards = importer._parse_csv_content(csv_path.read_text(encoding="utf-8"))
        if args.limit:
            cards = cards[: args.limit]

        matched = 0
        changed = 0
        with_examples = 0
        for card in cards:
            word, language, direction, target = _card_identity(importer, card)
            example, translation = importer.parser.extract_example_pair(
                f"{card['front']} {card['back']}",
                target,
                direction,
            )
            if not example:
                continue
            with_examples += 1

            row = _find_word(db, card=card, word=word, language=language, direction=direction)
            if not row:
                continue
            matched += 1

            should_update_sentence = args.overwrite or not row.example_sentence
            should_update_translation = args.overwrite or not row.example_translation
            if not should_update_sentence and not should_update_translation:
                continue

            if should_update_sentence:
                row.example_sentence = example
            if should_update_translation and translation:
                row.example_translation = translation
            changed += 1

        if args.apply:
            db.commit()
            action = "Committed"
        else:
            db.rollback()
            action = "Dry run"

        print(
            f"{action}: cards_with_examples={with_examples}, matched={matched}, "
            f"rows_changed={changed}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
