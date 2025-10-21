"""Seed vocabulary database with top 5000 French words."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.models.vocabulary import VocabularyWord
from app.db.session import SessionLocal


def normalize_word(word: str) -> str:
    """Remove accents and convert to lowercase for matching."""

    import unicodedata

    nfkd = unicodedata.normalize("NFKD", word)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def calculate_difficulty(frequency_rank: int) -> int:
    """Estimate difficulty based on frequency rank."""

    if frequency_rank <= 500:
        return 1
    if frequency_rank <= 1500:
        return 2
    if frequency_rank <= 3000:
        return 3
    if frequency_rank <= 4000:
        return 4
    return 5


def load_vocabulary_from_csv(csv_path: str, language: str = "fr") -> int:
    """Load vocabulary from CSV file into the database."""

    db: Session = SessionLocal()
    loaded = 0

    try:
        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                existing = (
                    db.query(VocabularyWord)
                    .filter(
                        VocabularyWord.language == language,
                        VocabularyWord.word == row["word"],
                    )
                    .first()
                )

                if existing:
                    continue

                topics = [t.strip() for t in row.get("topics", "").split(",") if t.strip()]

                word = VocabularyWord(
                    language=language,
                    word=row["word"],
                    normalized_word=normalize_word(row["word"]),
                    part_of_speech=row.get("part_of_speech"),
                    gender=row.get("gender") or None,
                    frequency_rank=int(row["rank"]),
                    english_translation=row["translation"],
                    definition=row.get("definition"),
                    example_sentence=row.get("example"),
                    example_translation=row.get("example_translation"),
                    topic_tags=topics if topics else None,
                    difficulty_level=calculate_difficulty(int(row["rank"])),
                )

                db.add(word)
                loaded += 1

                if loaded % 100 == 0:
                    db.commit()
                    print(f"Loaded {loaded} words...")

            db.commit()
            return loaded

    except Exception as exc:  # pragma: no cover - CLI feedback
        db.rollback()
        print(f"Error loading vocabulary: {exc}")
        raise
    finally:
        db.close()


def generate_sample_csv(output_path: Path | None = None) -> Path:
    """Generate a sample vocabulary CSV."""

    sample_data = [
        [
            "rank",
            "word",
            "part_of_speech",
            "gender",
            "translation",
            "definition",
            "example",
            "example_translation",
            "topics",
        ],
        [
            "1",
            "le",
            "article",
            "masculine",
            "the",
            "Definite article",
            "Le chat est noir",
            "The cat is black",
            "grammar",
        ],
        [
            "2",
            "de",
            "preposition",
            "",
            "of, from",
            "Preposition indicating possession or origin",
            "La maison de Marie",
            "Mary's house",
            "grammar",
        ],
    ]

    output_path = output_path or Path("vocabulary_fr_sample.csv")

    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(sample_data)

    print(f"Sample CSV generated: {output_path}")
    return output_path


if __name__ == "__main__":  # pragma: no cover - CLI execution
    import argparse

    parser = argparse.ArgumentParser(description="Seed vocabulary database")
    parser.add_argument("--csv", type=str, help="Path to CSV file")
    parser.add_argument("--language", type=str, default="fr", help="Language code")
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate sample CSV",
    )

    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_csv()
    elif args.csv:
        count = load_vocabulary_from_csv(args.csv, args.language)
        print(f"Successfully loaded {count} words")
    else:
        parser.error("Please specify --csv path or --generate-sample")
