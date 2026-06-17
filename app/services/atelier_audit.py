"""Audit helpers for generated Atelier exercise payloads."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierExerciseSet
from app.db.models.grammar import GrammarConcept
from app.services.atelier import (
    _contains_blank_marker,
    _has_adjacent_duplicate_tokens,
    _join_french_tokens,
    _multiset_subset,
    _normalize,
)
from app.services.grammar_feedback import count_concept_hits

LLM_EXERCISE_SOURCES = ("llm", "llm_user")


def atelier_word_bank_reasons(item: dict[str, Any], concept: GrammarConcept | None) -> list[str]:
    """Return audit reason codes for a generated word-bank item."""

    reasons: list[str] = []
    tokens = item.get("tokens") if isinstance(item.get("tokens"), list) else []
    answer_tokens = item.get("answer_tokens") if isinstance(item.get("answer_tokens"), list) else []
    correct_answer = str(item.get("correct_answer") or "")
    meaning_cue = str(item.get("meaning_cue") or "").strip()

    if not meaning_cue:
        reasons.append("missing_meaning_cue")
    elif _normalize(correct_answer) and _normalize(correct_answer) in _normalize(meaning_cue):
        reasons.append("meaning_cue_exposes_target")
    if _contains_blank_marker(item.get("prompt")) or any(_contains_blank_marker(token) for token in tokens):
        reasons.append("contains_blank")
    if len(tokens) < 3 or len(answer_tokens) < 3:
        reasons.append("too_few_tokens")
    if not _multiset_subset(answer_tokens, tokens):
        reasons.append("answer_tokens_not_subset_of_tokens")
    if _has_adjacent_duplicate_tokens(answer_tokens):
        reasons.append("duplicated_adjacent_answer_token")
    normalized_answer_tokens = [_normalize(token) for token in answer_tokens if _normalize(token)]
    if len(normalized_answer_tokens) <= 4 and len(set(normalized_answer_tokens)) < len(normalized_answer_tokens):
        reasons.append("duplicated_short_answer_token")
    if _normalize(correct_answer) != _normalize(_join_french_tokens(answer_tokens)):
        reasons.append("correct_answer_mismatch")
    if concept and count_concept_hits(concept, correct_answer, task_text=str(item.get("prompt") or "")) <= 0:
        reasons.append("correct_answer_missing_concept_hit")
    return reasons


def audit_atelier_word_banks(
    db: Session,
    *,
    generator_version: str | None = None,
    latest_per_concept: bool = True,
) -> list[dict[str, Any]]:
    """Audit generated LLM word-bank payloads and return flagged rows."""

    query = db.query(AtelierExerciseSet).filter(AtelierExerciseSet.source.in_(LLM_EXERCISE_SOURCES))
    if generator_version:
        query = query.filter(AtelierExerciseSet.generator_version == generator_version)
    rows = query.order_by(
        AtelierExerciseSet.concept_id.asc(),
        AtelierExerciseSet.created_at.desc(),
        AtelierExerciseSet.id.desc(),
    ).all()
    if latest_per_concept:
        latest: dict[int, AtelierExerciseSet] = {}
        for row in rows:
            latest.setdefault(row.concept_id, row)
        rows = list(latest.values())

    flagged: list[dict[str, Any]] = []
    for exercise_set in rows:
        concept = db.get(GrammarConcept, exercise_set.concept_id)
        items = (((exercise_set.payload or {}).get("recognize") or {}).get("word_bank") or {}).get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            for reason in atelier_word_bank_reasons(item, concept):
                flagged.append(
                    {
                        "concept_id": exercise_set.concept_id,
                        "external_id": concept.external_id if concept else None,
                        "exercise_set_id": str(exercise_set.id),
                        "generator_version": exercise_set.generator_version,
                        "source": exercise_set.source,
                        "item_id": item.get("id"),
                        "reason": reason,
                    }
                )
    return flagged


__all__ = ["LLM_EXERCISE_SOURCES", "atelier_word_bank_reasons", "audit_atelier_word_banks"]
