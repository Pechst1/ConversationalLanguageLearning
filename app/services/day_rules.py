"""P3 «La scène corrige ce que le jour enseigne»: the rules a scene's tutor is told.

Walk 17 Nov (B1, days 3–5): on the subjunctive's own day a reply with three missing
subjunctives got one tense flag, and elisions were flagged while «avant que je prends»
passed. The tutor lane was never told what the day teaches. It now reads:

* ``today`` — the unit the day introduces: the page's own rule (``grammar_focus`` on the
  scene), else the unit the learner met in the last day (``introduced_at``);
* ``recent`` — the other units introduced in the last seven days, newest first.

Each as the rule card states it: ``{id, name, rule}``, the name and the one-line rule in
the learner's explanation language. Read-only, never raises: a missing rule costs the
hint, never the turn.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: «The rules introduced in the last seven days.»
RECENT_DAYS = 7
#: An introduction this recent counts as the day's own when the page names none.
TODAY_HOURS = 20
RECENT_LIMIT = 6


def _rule_entry(db: Session, concept: Any, language: str) -> dict[str, Any] | None:
    from app.services.concept_life import _localizations
    from app.services.grammar_units import (
        localized_titles,
        regex_patterns,
        rule_card,
        unit_detectors,
    )

    titles = localized_titles(concept, _localizations(db, concept.id))
    card = rule_card(concept) or {}
    said = card.get("rule") if isinstance(card.get("rule"), dict) else {}
    rule = str(said.get(language) or said.get("en") or "").strip()
    name = str(titles.get(language) or titles.get("en") or titles.get("fr") or "").strip()
    if not rule or not name:
        return None
    return {
        "id": str(concept.external_id or concept.id),
        "name": name,
        "rule": rule,
        # Never sent to a model (``story_lanes.tutor_payload`` leaves it out): what lets
        # the app see for itself that a correction is about this rule.
        "detectors": regex_patterns(unit_detectors(concept)),
    }


def for_turn(
    db: Session,
    user: Any,
    *,
    control_language: str | None,
    focus_unit_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """``{"today": entry | None, "recent": [entry, …]}``, or ``None`` when there is none."""

    from app.db.models.grammar import GrammarConcept, UserGrammarProgress
    from app.services.concept_life import _aware

    if db is None:  # the gold gate builds a turn's prompt offline, without a session
        return None
    language = str(control_language or "en")
    now = _aware(now) or datetime.now(UTC)
    try:
        with db.begin_nested():
            rows = (
                db.query(UserGrammarProgress, GrammarConcept)
                .join(GrammarConcept, UserGrammarProgress.concept_id == GrammarConcept.id)
                .filter(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.introduced_at.isnot(None),
                    UserGrammarProgress.tested_out_at.is_(None),
                    GrammarConcept.active.is_(True),
                )
                .all()
            )
            recent = sorted(
                (
                    (stamp, concept)
                    for progress, concept in rows
                    if (stamp := _aware(progress.introduced_at)) is not None
                    and now - timedelta(days=RECENT_DAYS) < stamp <= now + timedelta(minutes=1)
                ),
                key=lambda row: (row[0], row[1].id),
                reverse=True,
            )
            today_concept = None
            if focus_unit_id not in (None, ""):
                try:
                    today_concept = db.get(GrammarConcept, int(focus_unit_id))
                except (TypeError, ValueError):
                    today_concept = None
            if today_concept is None and recent and recent[0][0] > now - timedelta(hours=TODAY_HOURS):
                today_concept = recent[0][1]
            today = _rule_entry(db, today_concept, language) if today_concept is not None else None
            others = [
                entry
                for _stamp, concept in recent
                if today_concept is None or concept.id != today_concept.id
                if (entry := _rule_entry(db, concept, language)) is not None
            ][:RECENT_LIMIT]
    except Exception:  # pragma: no cover - defensive: a hint is not a turn
        logger.exception("day_rules: the day's rules are unavailable")
        return None
    if today is None and not others:
        return None
    return {"today": today, "recent": others}


def rule_ids(rules: dict | None) -> tuple[str | None, frozenset[str]]:
    """The day's rule id and the recent ones, as the tutor's ``rule_id`` may name them."""

    rules = rules or {}
    today = (rules.get("today") or {}).get("id")
    recent = frozenset(str(entry.get("id")) for entry in rules.get("recent") or [] if entry.get("id"))
    return (str(today) if today else None), recent


def for_model(rules: dict | None) -> dict | None:
    """The rules as the tutor reads them: id, name and rule, no detector."""

    if not rules:
        return None

    def entry(row: Any) -> dict | None:
        return {key: row.get(key) for key in ("id", "name", "rule")} if isinstance(row, dict) else None

    return {"today": entry(rules.get("today")), "recent": [entry(row) for row in rules.get("recent") or []]}


def rule_statement(rules: dict | None, rule_id: str | None, *, text: str, span: str, corrected: str) -> str | None:
    """The one-line rule of ``rule_id``, as the card states it, when the app can see for
    itself that the correction is about that rule: the unit's detector finds the form in
    the corrected sentence, where the correction put it, and not in the learner's.
    ``None`` otherwise: a rule is never put under a correction it does not explain."""

    if not rule_id or not span or not corrected:
        return None
    from app.services.grammar_units import detector_spans

    rules = rules or {}
    entry = next(
        (
            row
            for row in [rules.get("today"), *(rules.get("recent") or [])]
            if isinstance(row, dict) and str(row.get("id")) == str(rule_id) and row.get("rule")
        ),
        None,
    )
    patterns = list((entry or {}).get("detectors") or [])
    at = (text or "").find(span)
    if entry is None or not patterns or at < 0:
        return None
    fixed = text[:at] + corrected + text[at + len(span):]
    found_after = any(start < at + len(corrected) and at < end for start, end in detector_spans(patterns, fixed))
    found_before = any(start < at + len(span) and at < end for start, end in detector_spans(patterns, text))
    return str(entry["rule"]) if found_after and not found_before else None
