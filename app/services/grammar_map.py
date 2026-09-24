"""WP-S7 — the grammar map: the syllabus as the four shapes, ghost → ink.

Read-only. One row per active French rule, grouped by sub-band (catalogue v2:
the unit's own ``sub_band``; v1: the CEFR level halved by teaching order, as
WP-L7's coverage does), each with one of four stages:

* ``ghost`` — not introduced (never met);
* ``introduced`` — met and practising, below the produce rung;
* ``proficient`` — the forge's rung (0-based) is ≥ 4 (``produce``/``free use``):
  the learner builds the rule themselves;
* ``held`` — WP-L4's «Tenue» (or a passed test-out).

Also returned: rung, next review, whether a review is due, the tested-out
stamp, the rule card (the map's sheet shows it), the Éclair pairs and the
feature switches.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import Rung
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User

STAGE_GHOST = "ghost"
STAGE_INTRODUCED = "introduced"
STAGE_PROFICIENT = "proficient"
STAGE_HELD = "held"
MAP_STAGES = (STAGE_GHOST, STAGE_INTRODUCED, STAGE_PROFICIENT, STAGE_HELD)

#: «Proficient»: the learner produces the rule (the forge's produce rung).
PROFICIENT_RUNG = int(Rung.PRODUCE)


def map_stage(progress: UserGrammarProgress | None) -> str:
    """One rule's stage on the map."""

    from app.services.concept_life import is_held
    from app.services.forge import initial_rung

    if progress is None:
        return STAGE_GHOST
    if is_held(progress):
        return STAGE_HELD
    met = (
        progress.introduced_at is not None
        or int(progress.reps or 0) > 0
        or progress.forge_rung is not None
    )
    if not met:
        return STAGE_GHOST
    if initial_rung(progress) >= PROFICIENT_RUNG:
        return STAGE_PROFICIENT
    return STAGE_INTRODUCED


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _is_french(concept: GrammarConcept) -> bool:
    return str(getattr(concept, "language", "") or "fr").strip().casefold().startswith(("fr", "français"))


def _bands(concepts: list[GrammarConcept], *, v2: bool) -> list[tuple[str, list[GrammarConcept]]]:
    from app.services.grammar_catalog import concept_sub_band
    from app.services.level_coverage import SUB_BANDS

    if v2:
        grouped: dict[str, list[GrammarConcept]] = {}
        for concept in concepts:
            band = concept_sub_band(concept) or str(concept.level or "").strip().upper()[:2] or "—"
            grouped.setdefault(band, []).append(concept)
        order = {band: index for index, band in enumerate(SUB_BANDS)}
        return sorted(grouped.items(), key=lambda pair: (order.get(pair[0], len(order)), pair[0]))
    # v1: the CEFR level, halved by teaching order (level_coverage.band_unit_ids).
    by_level: dict[str, list[GrammarConcept]] = {}
    for concept in concepts:
        by_level.setdefault(str(concept.level or "").strip().upper()[:2], []).append(concept)
    out: list[tuple[str, list[GrammarConcept]]] = []
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        rows = by_level.get(level) or []
        if not rows:
            continue
        half = math.ceil(len(rows) / 2)
        out.append((f"{level}.1", rows[:half]))
        if rows[half:]:
            out.append((f"{level}.2", rows[half:]))
    return out


def grammar_map(db: Session, user: User, *, now: datetime | None = None) -> dict[str, Any]:
    from app.services.atelier import fr_localizations_by_concept_id
    from app.services.eclair import eclair_enabled, eclair_pairs
    from app.services.forge import forge_features, initial_rung
    from app.services.grammar_catalog import FRENCH_CORE_CATALOG_V2_VERSION, active_catalog_version
    from app.services.rule_cards import rule_card_for

    now = _aware(now) or datetime.now(UTC)
    v2 = active_catalog_version() == FRENCH_CORE_CATALOG_V2_VERSION
    concepts = [
        concept
        for concept in db.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True))
        .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
        .all()
        if _is_french(concept)
    ]
    progress = {
        row.concept_id: row
        for row in db.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id).all()
    }
    fr = fr_localizations_by_concept_id(db, [concept.id for concept in concepts])
    counts = dict.fromkeys(MAP_STAGES, 0)
    bands: list[dict[str, Any]] = []
    for band, rows in _bands(concepts, v2=v2):
        rules = []
        for concept in rows:
            row = progress.get(concept.id)
            stage = map_stage(row)
            counts[stage] += 1
            rung = initial_rung(row)
            next_due = _aware(row.next_review) if row is not None else None
            rules.append(
                {
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "title_fr": (fr[concept.id].title if concept.id in fr else None) or concept.name,
                    "name": concept.name,
                    "level": concept.level,
                    "category": concept.category,
                    "subskill": concept.subskill,
                    "stage": stage,
                    "rung": rung,
                    "rung_name": core.rung_name(rung),
                    "next_due": next_due.isoformat() if next_due else None,
                    "due": bool(stage != STAGE_GHOST and next_due is not None and next_due <= now),
                    "tested_out": bool(row is not None and row.tested_out_at is not None),
                    "rule_card": rule_card_for(concept.external_id),
                    # WP-S5 fills the coach; the page falls back to the card's speaker.
                    "coach": None,
                }
            )
        bands.append({"band": band, "rules": rules})
    features = forge_features()
    pairs = eclair_pairs(db, user) if features["eclair"] and eclair_enabled() else []
    return {
        "catalog": "v2" if v2 else "v1",
        "bands": bands,
        "counts": counts,
        "total": sum(counts.values()),
        "eclair": {"unlocked": bool(pairs), "pairs": pairs},
        "features": features,
    }


__all__ = [
    "MAP_STAGES",
    "PROFICIENT_RUNG",
    "STAGE_GHOST",
    "STAGE_HELD",
    "STAGE_INTRODUCED",
    "STAGE_PROFICIENT",
    "grammar_map",
    "map_stage",
]
