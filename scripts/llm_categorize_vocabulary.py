#!/usr/bin/env python
"""Re-categorize the 5000-word deck with an LLM (reliable POS + topic).

spacy single-word POS and keyword category matching left most words mis-tagged
(nouns as 'verbs', most 'uncategorized'). This pass asks the LLM, in batches, for
each word's part of speech and — for nouns — its thematic category, then writes
`part_of_speech` and `topic_tags` to both direction rows. Idempotent; safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

from app.db.session import SessionLocal
from app.db.models.vocabulary import VocabularyWord
from app.services.llm_service import LLMService
from app.config import settings

NOUN_CATEGORIES = [
    "people_relationships", "body_health", "food_drink", "home_objects", "clothing",
    "time_calendar", "transport_travel", "places_infrastructure", "nature_weather",
    "work_money", "education", "technology_media", "society_politics",
    "emotions_abstract", "arts_leisure", "communication",
]
POS_VALUES = ["noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "determiner", "number", "interjection", "other"]

RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "vocab_categorization",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "i": {"type": "integer"},
                            "pos": {"type": "string", "enum": POS_VALUES},
                            "topic": {"type": "string", "enum": [*NOUN_CATEGORIES, "none"]},
                        },
                        "required": ["i", "pos", "topic"],
                    },
                }
            },
            "required": ["items"],
        },
    },
}

SYSTEM = (
    "You are a French lexicographer. For each numbered French word (its German/English gloss is given to disambiguate), "
    "return its part of speech and, ONLY if it is a concrete noun, the single best thematic category from the allowed list. "
    "For non-nouns or abstract nouns with no clear theme, set topic to 'none'. Judge the word's most common everyday meaning. "
    "Return one item per input index."
)


def category_for(pos: str, topic: str) -> str:
    if pos == "verb":
        return "verbs"
    if pos in {"adjective", "adverb"}:
        return "adjectives_adverbs"
    if pos in {"pronoun", "preposition", "conjunction", "determiner"}:
        return "function_words"
    if pos == "noun" and topic in NOUN_CATEGORIES:
        return topic
    return "uncategorized"


def run(*, batch_size: int, limit: int | None, dry_run: bool) -> None:
    db = SessionLocal()
    llm = LLMService()
    try:
        query = db.query(VocabularyWord).filter(VocabularyWord.direction == "fr_to_de").order_by(VocabularyWord.id.asc())
        if limit:
            query = query.limit(limit)
        rows = query.all()
        print(f"Categorizing {len(rows)} French words in batches of {batch_size} with {settings.ATELIER_EXERCISE_LLM_MODEL}.")
        pos_counts: dict[str, int] = {}
        cat_counts: dict[str, int] = {}
        changed = 0
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            payload = {
                "allowed_topics": NOUN_CATEGORIES,
                "words": [
                    {"i": idx, "fr": w.word, "gloss": (w.german_translation or w.english_translation or "")[:60]}
                    for idx, w in enumerate(chunk)
                ],
            }
            try:
                result = llm.generate_chat_completion(
                    messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    system_prompt=SYSTEM,
                    response_format=RESPONSE_FORMAT,
                    temperature=0.0,
                    max_tokens=8000,
                    model=settings.ATELIER_EXERCISE_LLM_MODEL,
                    reasoning_effort="minimal",
                    request_timeout=90.0,
                )
                items = json.loads(result.content).get("items") or []
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {start} failed: {exc}")
                continue
            by_index = {int(it.get("i")): it for it in items if isinstance(it, dict)}
            for idx, word in enumerate(chunk):
                it = by_index.get(idx)
                if not it:
                    continue
                pos = str(it.get("pos") or "other")
                category = category_for(pos, str(it.get("topic") or "none"))
                pos_counts[pos] = pos_counts.get(pos, 0) + 1
                cat_counts[category] = cat_counts.get(category, 0) + 1
                for row in [word, *db.query(VocabularyWord).filter(VocabularyWord.linked_word_id == word.id).all()]:
                    row.part_of_speech = pos
                    row.topic_tags = [category]
                    db.add(row)
                changed += 1
            if not dry_run:
                db.commit()
            print(f"  {min(start + batch_size, len(rows))}/{len(rows)} done")
        if dry_run:
            db.rollback()
        print(f"changed={changed} dry_run={dry_run}")
        print("pos_counts:", dict(sorted(pos_counts.items(), key=lambda kv: -kv[1])))
        print("category_counts:", dict(sorted(cat_counts.items(), key=lambda kv: -kv[1])))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-categorize the vocabulary deck.")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(batch_size=args.batch_size, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
