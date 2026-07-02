#!/usr/bin/env python3
"""Enrich imported French vocabulary with POS, topic category, CEFR band, and rank.

The script is intentionally deterministic and idempotent. It prefers spaCy
(`fr_core_news_sm`) for POS/lemma signals and an optional CSV frequency list for ranks.
When either input is unavailable, it falls back to transparent local heuristics so the
application can still build the Coverage Map without network or LLM access.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import or_  # noqa: E402

from app.db.models.vocabulary import VocabularyWord  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.vocabulary_coverage import TAXONOMY_LABELS, normalize_category  # noqa: E402


CEFR_BY_RANK = [(500, 1), (1000, 2), (2000, 3), (3500, 4), (999999, 5)]
POS_MAP = {
    "NOUN": "noun",
    "PROPN": "noun",
    "VERB": "verb",
    "AUX": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
    "PRON": "pronoun",
    "DET": "determiner",
    "ADP": "preposition",
    "CCONJ": "conjunction",
    "SCONJ": "conjunction",
    "NUM": "number",
    "INTJ": "interjection",
}
FUNCTION_WORDS = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "à",
    "au",
    "aux",
    "et",
    "ou",
    "mais",
    "donc",
    "que",
    "qui",
    "ce",
    "cette",
    "ces",
    "je",
    "tu",
    "il",
    "elle",
    "nous",
    "vous",
}
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "food_drink": {"manger", "boire", "pain", "eau", "vin", "café", "restaurant", "marché", "fruit", "légume", "essen", "trinken"},
    "time_calendar": {"temps", "jour", "semaine", "mois", "année", "heure", "matin", "soir", "gestern", "morgen", "uhr"},
    "people_relationships": {"homme", "femme", "ami", "famille", "mère", "père", "enfant", "personne", "freund", "familie"},
    "transport_travel": {"train", "voiture", "métro", "bus", "gare", "voyage", "partir", "arriver", "zug", "reise"},
    "places_infrastructure": {"ville", "rue", "maison", "bureau", "école", "hôtel", "place", "ort", "straße"},
    "body_health": {"corps", "tête", "main", "santé", "malade", "médecin", "douleur", "gesund", "arzt"},
    "home_objects": {"maison", "appartement", "table", "chaise", "porte", "fenêtre", "zimmer", "wohnung"},
    "work_money": {"travail", "argent", "payer", "prix", "client", "entreprise", "arbeit", "geld"},
    "education": {"apprendre", "école", "livre", "étudiant", "cours", "frage", "schule"},
    "technology_media": {"téléphone", "ordinateur", "message", "email", "site", "internet", "computer"},
    "nature_weather": {"arbre", "fleur", "mer", "montagne", "pluie", "soleil", "temps", "wetter"},
    "emotions_abstract": {"aimer", "peur", "joie", "idée", "raison", "envie", "sentiment", "gefühl"},
    "arts_leisure": {"musique", "film", "jeu", "lire", "danser", "kunst", "spiel"},
    "communication": {"dire", "parler", "demander", "répondre", "message", "lettre", "sprechen", "sagen"},
    "society_politics": {"loi", "état", "gouvernement", "société", "politique", "recht"},
    "clothing": {"robe", "chemise", "pantalon", "chaussure", "manteau", "kleid", "schuh"},
}


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def load_spacy():
    try:
        import spacy

        return spacy.load("fr_core_news_sm")
    except Exception:
        return None


def load_frequency(path: str | None) -> dict[str, int]:
    if not path:
        return {}
    frequency_path = Path(path).expanduser()
    if not frequency_path.exists():
        raise FileNotFoundError(f"frequency list not found: {frequency_path}")
    ranks: dict[str, int] = {}
    with frequency_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {name.lower(): name for name in reader.fieldnames or []}
        word_field = fieldnames.get("word") or fieldnames.get("lemma") or fieldnames.get("ortho") or next(iter(fieldnames.values()))
        rank_field = fieldnames.get("rank") or fieldnames.get("frequency_rank")
        frequency_field = (
            fieldnames.get("freq")
            or fieldnames.get("frequency")
            or fieldnames.get("count")
            or fieldnames.get("occurrences")
        )
        frequency_rows: list[tuple[str, float, int]] = []
        for index, row in enumerate(reader, start=1):
            key = normalize(row.get(word_field))
            if not key or key in ranks:
                continue
            if rank_field and row.get(rank_field):
                try:
                    rank = int(float(str(row[rank_field]).replace(",", ".")))
                except ValueError:
                    rank = index
                ranks[key] = rank
            elif frequency_field and row.get(frequency_field):
                try:
                    frequency = float(str(row[frequency_field]).replace(",", "."))
                except ValueError:
                    frequency = 0.0
                frequency_rows.append((key, frequency, index))
            else:
                ranks[key] = index
        for rank, (key, _frequency, _index) in enumerate(
            sorted(frequency_rows, key=lambda item: (-item[1], item[2])),
            start=1,
        ):
            ranks.setdefault(key, rank)
    return ranks


def cefr_difficulty(rank: int | None, fallback: int | None) -> int:
    if rank:
        for threshold, difficulty in CEFR_BY_RANK:
            if rank <= threshold:
                return difficulty
    return max(1, min(5, int(fallback or 1)))


def spacy_guess(nlp: Any, word: str) -> tuple[str | None, str | None]:
    if nlp is None or not word:
        return None, None
    doc = nlp(word)
    token = next((item for item in doc if not item.is_space and not item.is_punct), None)
    if token is None:
        return None, None
    return POS_MAP.get(token.pos_, token.pos_.lower()), token.lemma_.lower() if token.lemma_ else None


def heuristic_pos(word: str) -> str:
    normalized = normalize(word)
    lowered = str(word or "").strip().lower()
    if lowered in FUNCTION_WORDS:
        return "function"
    if lowered.endswith(("er", "ir", "re", "oir")) and len(lowered) > 4:
        return "verb"
    if lowered.endswith("ment"):
        return "adverb"
    if lowered.endswith(("tion", "té", "eur", "euse", "age")):
        return "noun"
    if lowered.endswith(("eux", "euse", "if", "ive", "able", "ible")):
        return "adjective"
    if normalized in {"etre", "avoir", "aller", "faire", "venir", "voir", "dire", "pouvoir", "vouloir"}:
        return "verb"
    return "noun"


def category_for(word: VocabularyWord, *, part_of_speech: str) -> str:
    if part_of_speech == "verb":
        return "verbs"
    if part_of_speech in {"adjective", "adverb"}:
        return "adjectives_adverbs"
    if part_of_speech in {"function", "pronoun", "determiner", "preposition", "conjunction"}:
        return "function_words"
    haystack = " ".join(
        item
        for item in [
            word.word,
            word.normalized_word,
            word.french_translation,
            word.german_translation,
            word.english_translation,
            word.definition,
            word.example_sentence,
        ]
        if item
    ).lower()
    for category, needles in CATEGORY_KEYWORDS.items():
        if any(needle in haystack for needle in needles):
            return category
    for tag in word.topic_tags or []:
        category = normalize_category(tag)
        if category in TAXONOMY_LABELS:
            return category
    return "uncategorized"


def update_row(row: VocabularyWord, *, pos: str, category: str, rank: int, difficulty: int) -> bool:
    changed = False
    if row.part_of_speech != pos:
        row.part_of_speech = pos
        changed = True
    tags = [category]
    if row.topic_tags != tags:
        row.topic_tags = tags
        changed = True
    if row.frequency_rank != rank:
        row.frequency_rank = rank
        changed = True
    if row.difficulty_level != difficulty:
        row.difficulty_level = difficulty
        changed = True
    return changed


def sibling_rows(
    db: Any,
    row: VocabularyWord,
    *,
    reverse_rows: list[VocabularyWord] | None = None,
) -> list[VocabularyWord]:
    """Rows that represent the same French lexical item in another card direction."""

    siblings: list[VocabularyWord] = [row]
    seen_ids = {row.id}
    if row.linked_word_id:
        linked = db.get(VocabularyWord, row.linked_word_id)
        if linked and linked.id not in seen_ids:
            siblings.append(linked)
            seen_ids.add(linked.id)
    if row.normalized_word:
        for sibling in (
            db.query(VocabularyWord)
            .filter(
                VocabularyWord.language == row.language,
                VocabularyWord.normalized_word == row.normalized_word,
            )
            .all()
        ):
            if sibling.id in seen_ids:
                continue
            siblings.append(sibling)
            seen_ids.add(sibling.id)
    for sibling in reverse_rows or []:
        if sibling.id in seen_ids:
            continue
        siblings.append(sibling)
        seen_ids.add(sibling.id)
    return siblings


def enrich(limit: int | None, frequency_csv: str | None, dry_run: bool) -> dict[str, Any]:
    nlp = load_spacy()
    frequency = load_frequency(frequency_csv)
    db = SessionLocal()
    try:
        reverse_by_french: dict[str, list[VocabularyWord]] = {}
        reverse_rows = (
            db.query(VocabularyWord)
            .filter(VocabularyWord.direction == "de_to_fr")
            .filter(VocabularyWord.french_translation.isnot(None))
            .all()
        )
        for reverse in reverse_rows:
            key = normalize(reverse.french_translation)
            if not key:
                continue
            reverse_by_french.setdefault(key, []).append(reverse)
        rows = (
            db.query(VocabularyWord)
            .filter(VocabularyWord.language == "fr")
            .filter(or_(VocabularyWord.direction == "fr_to_de", VocabularyWord.direction.is_(None)))
            .order_by(VocabularyWord.frequency_rank.asc().nullslast(), VocabularyWord.id.asc())
        )
        if limit:
            rows = rows.limit(limit)
        french_rows = rows.all()
        changed = 0
        processed = 0
        pos_counts: Counter[str] = Counter()
        category_counts: Counter[str] = Counter()
        for fallback_rank, row in enumerate(french_rows, start=1):
            surface = row.word or row.normalized_word
            key = normalize(surface)
            pos, lemma = spacy_guess(nlp, row.word)
            pos = pos or heuristic_pos(row.word)
            rank = frequency.get(key) or row.frequency_rank or fallback_rank
            difficulty = cefr_difficulty(rank, row.difficulty_level)
            category = category_for(row, part_of_speech=pos)
            processed += 1
            pos_counts[pos] += 1
            category_counts[category] += 1
            for sibling in sibling_rows(db, row, reverse_rows=reverse_by_french.get(key, [])):
                if update_row(sibling, pos=pos, category=category, rank=rank, difficulty=difficulty):
                    changed += 1
        db.flush()
        total = db.query(VocabularyWord).count()
        populated = {
            "part_of_speech": db.query(VocabularyWord).filter(VocabularyWord.part_of_speech.isnot(None), VocabularyWord.part_of_speech != "").count(),
            "topic_tags": db.query(VocabularyWord).filter(VocabularyWord.topic_tags.isnot(None)).count(),
            "frequency_rank": db.query(VocabularyWord).filter(VocabularyWord.frequency_rank.isnot(None)).count(),
            "difficulty_level": db.query(VocabularyWord).filter(VocabularyWord.difficulty_level.isnot(None)).count(),
        }
        coverage = {
            key: round((value / total) * 100, 2) if total else 0.0
            for key, value in populated.items()
        }
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "processed_unique_french_rows": processed,
            "changed_rows": changed,
            "total_rows": total,
            "coverage_percent": coverage,
            "pos_counts": dict(pos_counts),
            "category_counts": dict(category_counts),
            "spacy_model": "fr_core_news_sm" if nlp is not None else "heuristic_fallback",
            "frequency_source": frequency_csv or "existing_rank_or_stable_order",
            "dry_run": dry_run,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich vocabulary_words for the coverage map.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of French rows to process.")
    parser.add_argument("--frequency-csv", default=None, help="Optional frequency CSV with word/lemma and rank/frequency columns.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and roll back changes.")
    args = parser.parse_args()
    report = enrich(limit=args.limit, frequency_csv=args.frequency_csv, dry_run=args.dry_run)
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
