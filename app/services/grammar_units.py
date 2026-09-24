"""WP-L4 — what the day needs to know about one grammar unit.

A *unit brief* is a small JSON-safe dict the journey planner can build items
from without touching the database (the planner is a pure function): the
unit's titles, its rule card, its example sentences, its ✗/✓ contrast pairs
and its detectors. It is built here, once, from the catalogue row
(:class:`~app.db.models.grammar.GrammarConcept`) and its localizations.

Sources, in order of preference:

* **Rule card** — the authored WP-L10 card (``app/data/grammar_rule_cards.json``,
  keyed by v1 external id). A unit without one (every v2 unit, most v1
  concepts) gets a card built from its catalogue fields: the x-ray sentence as
  the example with its x-ray tokens marked, the one-sentence rule per locale
  (v2 ``rule_short``), the anchors as pattern rows and the first ✗/✓ trap as
  the contrast pair.
* **Detectors** — v2 units carry one (``regex:`` or ``llm:``). A v1 concept
  borrows the regex detectors of the v2 units that replace it
  (``templates/french_core_grammar_v1_to_v2.tsv``). ``llm:`` detectors are not
  run: such a unit's reply evidence comes from corrections only.
* **Contrast pairs** — the authored card's pair, then every ``✗ … → ✓ …`` trap
  of the unit (a v1 concept reads its v2 replacements' traps).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.services.grammar_catalog import (
    FRENCH_CORE_CATALOG_V2_VERSION,
    catalog_rows,
    concept_syllabus,
    load_v1_to_v2_mapping,
)
from app.services.grammar_items import detector_span, fold_apostrophes, plain
from app.services.rule_cards import rule_card_for

#: ``✗ Je es français. → ✓ Je suis français.``
_TRAP_PAIR = re.compile(r"✗\s*(?P<wrong>.+?)\s*(?:→|->)\s*✓\s*(?P<right>.+)$")

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "de", "fr")


def _split(value: str | None, separator: str = " | ") -> list[str]:
    return [item.strip() for item in str(value or "").split(separator) if item.strip()]


@lru_cache(maxsize=1)
def _v2_rows_by_external_id() -> dict[str, dict[str, Any]]:
    return {row["external_id"]: row for row in catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)}


def _v2_rows_for(concept: Any) -> list[dict[str, Any]]:
    """The v2 catalogue rows that stand for this concept: itself, or its replacements."""

    external_id = str(getattr(concept, "external_id", "") or "")
    rows = _v2_rows_by_external_id()
    if external_id in rows:
        return [rows[external_id]]
    return [rows[item] for item in load_v1_to_v2_mapping().get(external_id, []) if item in rows]


def unit_detectors(concept: Any) -> list[dict[str, str]]:
    """Every detector that recognises this unit in free text (regex and llm)."""

    own = concept_syllabus(concept).get("detector")
    if isinstance(own, dict) and own.get("kind"):
        return [dict(own)]
    detectors: list[dict[str, str]] = []
    for row in _v2_rows_for(concept):
        detector = (row.get("syllabus") or {}).get("detector")
        if isinstance(detector, dict) and detector.get("kind"):
            detectors.append(dict(detector))
    return detectors


def regex_patterns(detectors: list[dict[str, Any]] | None) -> list[str]:
    return [
        str(item["pattern"])
        for item in detectors or []
        if isinstance(item, dict) and item.get("kind") == "regex" and item.get("pattern")
    ]


def contrast_pairs(concept: Any) -> list[dict[str, str]]:
    """Every ✗/✓ pair known for the unit, the authored card's first, plain text."""

    pairs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(wrong: str, right: str) -> None:
        wrong, right = plain(wrong), plain(right)
        key = (wrong.casefold(), right.casefold())
        if not wrong or not right or key[0] == key[1] or key in seen:
            return
        seen.add(key)
        pairs.append({"wrong": wrong, "right": right})

    card = rule_card_for(getattr(concept, "external_id", None)) or {}
    contrast = card.get("contrast") if isinstance(card, dict) else None
    if isinstance(contrast, dict):
        add(str(contrast.get("wrong") or ""), str(contrast.get("right") or ""))
    trap_sources = [str(getattr(concept, "main_traps", "") or "")]
    if not concept_syllabus(concept):
        trap_sources.extend(str(row.get("main_traps") or "") for row in _v2_rows_for(concept))
    for source in trap_sources:
        for trap in _split(source):
            match = _TRAP_PAIR.match(trap)
            if match:
                add(match.group("wrong"), match.group("right"))
    return pairs


def _xray(concept: Any) -> tuple[str, list[str]]:
    refs = getattr(concept, "source_refs", None) or {}
    seed = refs.get("blueprint_seed") if isinstance(refs, dict) else None
    xray = (seed or {}).get("sentence_xray") if isinstance(seed, dict) else None
    if not isinstance(xray, dict):
        return "", []
    tokens = [
        str(mark.get("token") or "").strip()
        for mark in xray.get("marks") or []
        if isinstance(mark, dict)
    ]
    return str(xray.get("sentence") or "").strip(), [token for token in tokens if token]


def examples(concept: Any) -> list[str]:
    """French sentences that use the unit: x-ray sentence, anchors, card example."""

    found: list[str] = []
    sentence, _tokens = _xray(concept)
    card = rule_card_for(getattr(concept, "external_id", None)) or {}
    for value in (
        sentence,
        *_split(getattr(concept, "anchor_examples", None)),
        plain((card.get("example") or {}).get("fr") if isinstance(card, dict) else ""),
    ):
        text = plain(value)
        if text and text.casefold() not in {item.casefold() for item in found}:
            found.append(text)
    return found


def _mark(sentence: str, tokens: list[str]) -> str:
    """``[x]``-mark the first occurrence of each token (WP-L10 markup)."""

    marked = sentence
    for token in tokens:
        if "..." in token or "…" in token:
            continue
        index = marked.casefold().find(token.casefold())
        if index < 0 or "[" in marked[max(0, index - 1): index + len(token) + 1]:
            continue
        marked = f"{marked[:index]}[{marked[index:index + len(token)]}]{marked[index + len(token):]}"
    return marked


def localized_titles(concept: Any, localizations: dict[str, str] | None = None) -> dict[str, str]:
    """The unit's title per locale: localization rows, then v2 names, then the name."""

    titles: dict[str, str] = {}
    names = concept_syllabus(concept).get("names") or {}
    for locale in SUPPORTED_LOCALES:
        title = (localizations or {}).get(locale) or (names.get(locale) if isinstance(names, dict) else None)
        if title:
            titles[locale] = str(title)
    titles.setdefault("en", str(getattr(concept, "name", "") or ""))
    return titles


def built_rule_card(concept: Any, *, pairs: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
    """A WP-L10 card payload from the catalogue fields, for a unit with no authored card."""

    sentence, tokens = _xray(concept)
    anchors = [plain(item) for item in _split(getattr(concept, "anchor_examples", None))]
    example = sentence or (anchors[0] if anchors else "")
    if not example:
        return None
    rule_short = concept_syllabus(concept).get("rule_short") or {}
    rule = {
        locale: str(text).strip()
        for locale, text in (rule_short.items() if isinstance(rule_short, dict) else [])
        if str(text or "").strip()
    }
    if not rule:
        core = str(getattr(concept, "core_rule", "") or "").strip()
        if core:
            rule = {"en": core}
    if not rule:
        return None
    rows = [
        {"shape": "none", "label": "", "fr": anchor}
        for anchor in anchors
        if anchor.casefold() != plain(example).casefold()
    ][:3]
    pairs = pairs if pairs is not None else contrast_pairs(concept)
    card: dict[str, Any] = {
        "speaker": None,
        "example": {"fr": _mark(example, tokens)},
        "rule": rule,
        "pattern": {"kind": "rows", "rows": rows} if rows else None,
        "contrast": dict(pairs[0]) if pairs else None,
    }
    return card


def rule_card(concept: Any) -> dict[str, Any] | None:
    """The authored card when there is one, else the one built from the catalogue."""

    authored = rule_card_for(getattr(concept, "external_id", None))
    if authored:
        return authored
    return built_rule_card(concept)


def pattern_forms(concept: Any) -> list[str]:
    """``je suis / tu es / il est`` → the paradigm's forms (distractor material)."""

    refs = getattr(concept, "source_refs", None) or {}
    seed = refs.get("blueprint_seed") if isinstance(refs, dict) else None
    pattern = str((seed or {}).get("pattern") or "") if isinstance(seed, dict) else ""
    if " / " not in pattern:
        return []
    return [part.strip() for part in pattern.split(" / ") if 0 < len(part.split()) <= 3]


#: Units whose form is a noun phrase (a determiner and its noun): a scene line
#: only illustrates them where it has one, and a sentence with any noun phrase
#: is never a «does not use this rule» distractor.
NOUN_PHRASE_SUBSKILLS: frozenset[str] = frozenset(
    {
        "gender_number",
        "definite_articles",
        "indefinite_articles",
        "adjective_agreement",
        "possessives",
        "demonstratives",
    }
)


def is_noun_phrase_unit(concept: Any) -> bool:
    subskills = {str(getattr(concept, "subskill", "") or "")}
    subskills.update(str(row.get("subskill") or "") for row in _v2_rows_for(concept))
    return bool(subskills & NOUN_PHRASE_SUBSKILLS)


def unit_brief(
    concept: Any,
    *,
    control_language: str,
    localizations: dict[str, str] | None = None,
    stability: float | None = None,
) -> dict[str, Any]:
    """Everything the planner needs to pose this unit, JSON-safe."""

    titles = localized_titles(concept, localizations)
    detectors = unit_detectors(concept)
    pairs = contrast_pairs(concept)
    rule_short = concept_syllabus(concept).get("rule_short") or {}
    card = rule_card(concept)
    return {
        "concept_id": int(concept.id),
        "external_id": str(getattr(concept, "external_id", "") or ""),
        "catalog_version": str(getattr(concept, "catalog_version", "") or ""),
        "level": str(getattr(concept, "level", "") or ""),
        "title_fr": titles.get("fr") or titles.get("en") or "",
        "title_native": titles.get(control_language) or titles.get("en") or "",
        "rule_short_native": (
            str(rule_short.get(control_language) or "").strip() or None
            if isinstance(rule_short, dict)
            else None
        ),
        "rule_card": card,
        "examples": examples(concept),
        "contrast_pairs": pairs,
        "detectors": regex_patterns(detectors),
        "noun_phrase": is_noun_phrase_unit(concept),
        #: ``llm:`` detectors are never run: evidence from corrections only.
        "llm_detector_only": bool(detectors) and not regex_patterns(detectors),
        "pattern_forms": pattern_forms(concept),
        "stability": float(stability or 0.0),
    }


__all__ = [
    "built_rule_card",
    "contrast_pairs",
    "detector_span",
    "examples",
    "is_noun_phrase_unit",
    "fold_apostrophes",
    "localized_titles",
    "pattern_forms",
    "plain",
    "regex_patterns",
    "rule_card",
    "unit_brief",
    "unit_detectors",
]
