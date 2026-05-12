"""Curated grammar catalog import and archival utilities."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept, GrammarConceptArchive, GrammarConceptLocalization

FRENCH_CORE_CATALOG_VERSION = "french_core_grammar_v1"

SOURCE_REFERENCE_URLS = {
    "cefr": "https://www.service-public.gouv.fr/particuliers/vosdroits/F34739?lang=en&successfulShare=true",
    "delf": "https://www.france-education-international.fr/en/diplome/delf-tout-public?langue=en",
    "delf_a1": "https://www.france-education-international.fr/diplome/delf-tout-public/niveau-a1/exemples-sujets",
    "delf_a2": "https://www.france-education-international.fr/en/diplome/delf-tout-public?langue=en",
    "delf_b1": "https://www.france-education-international.fr/en/diplome/delf-tout-public?langue=en",
    "delf_b2": "https://www.france-education-international.fr/en/diplome/delf-tout-public?langue=en",
    "delf_c1": "https://www.france-education-international.fr/en/diplome/dalf?langue=en",
    "kwiziq_a1": "https://french.kwiziq.com/revision/grammar/by-cefr-level/cefr-a1",
    "kwiziq_a2": "https://progress.lawlessfrench.com/revision/grammar/by-cefr-level/cefr-a2",
    "kwiziq_b1": "https://progress.lawlessfrench.com/revision/grammar/by-cefr-level/cefr-b1",
    "kwiziq_b2": "https://french.kwiziq.com/revision/grammar/by-cefr-level/cefr-b2",
    "kwiziq_c1": "https://progress.lawlessfrench.com/revision/grammar/by-cefr-level/cefr-c1",
}

GERMAN_CATEGORY_LABELS = {
    "Agreement": "Kongruenz",
    "Articles": "Artikel",
    "Comparison": "Vergleich",
    "Conditionals": "Bedingungssätze",
    "Connectors": "Konnektoren",
    "Determiners": "Begleiter",
    "Negation": "Verneinung",
    "Prepositions": "Präpositionen",
    "Pronouns": "Pronomen",
    "Relative clauses": "Relativsätze",
    "Syntax": "Satzbau",
    "Tenses": "Zeiten",
    "Verbs": "Verben",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _split(value: str | None, separator: str = " | ") -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def _parse_xray_marks(value: str | None) -> list[dict[str, str]]:
    marks: list[dict[str, str]] = []
    for item in _split(value, "||"):
        parts = [part.strip() for part in item.split("=>", 2)]
        if len(parts) == 3:
            token, role, explanation = parts
            marks.append(
                {
                    "token": token,
                    "role": role,
                    "explanation": explanation,
                    "color": _role_color(role),
                    "underline": "solid",
                }
            )
    return marks


def _role_color(role: str) -> str:
    lowered = role.casefold()
    if any(part in lowered for part in ("trigger", "condition", "negative", "concession")):
        return "blue"
    if any(part in lowered for part in ("result", "event", "target", "subjunctive", "agreement")):
        return "red"
    if any(part in lowered for part in ("quantity", "background", "controller", "antecedent")):
        return "yellow"
    return "ink"


class FrenchCoreGrammarCatalog:
    """Import the focused French grammar catalog and archive legacy tracker rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @classmethod
    def catalog_path(cls) -> Path:
        return _repo_root() / "templates" / f"{FRENCH_CORE_CATALOG_VERSION}.tsv"

    @classmethod
    def rows(cls) -> list[dict[str, Any]]:
        path = cls.catalog_path()
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as handle:
            return [cls._normalize_row(row) for row in csv.DictReader(handle, delimiter="\t") if row.get("external_id")]

    @classmethod
    def _normalize_row(cls, row: dict[str, str]) -> dict[str, Any]:
        source_codes = _split(row.get("source_refs"))
        source_refs = {
            "catalog_version": FRENCH_CORE_CATALOG_VERSION,
            "source_codes": source_codes,
            "urls": [SOURCE_REFERENCE_URLS[code] for code in source_codes if code in SOURCE_REFERENCE_URLS],
            "blueprint_seed": {
                "display_title": row.get("name_en", "").strip(),
                "localized_titles": {"de": row.get("name_de", "").strip()},
                "when_to_use": row.get("when_to_use", "").strip(),
                "pattern": row.get("pattern", "").strip(),
                "contrast_rules": _split(row.get("contrast_rules")),
                "sentence_xray": {
                    "sentence": row.get("xray_sentence", "").strip(),
                    "explanation": " ".join(
                        part
                        for part in [row.get("core_rule", "").strip(), row.get("when_to_use", "").strip()]
                        if part
                    ),
                    "marks": _parse_xray_marks(row.get("xray_marks")),
                },
            },
        }
        return {
            "external_id": row.get("external_id", "").strip(),
            "language": row.get("language", "fr").strip() or "fr",
            "level": row.get("cefr_level", "A1").strip() or "A1",
            "category": row.get("category", "").strip() or None,
            "subskill": row.get("subskill", "").strip() or None,
            "name": row.get("name_en", "").strip(),
            "title_de": row.get("name_de", "").strip(),
            "difficulty_order": int(row.get("teaching_order") or 0),
            "is_foundation": _parse_bool(row.get("is_foundation")),
            "core_rule": row.get("core_rule", "").strip(),
            "description": row.get("when_to_use", "").strip(),
            "main_traps": " | ".join(_split(row.get("main_traps"))),
            "anchor_examples": " | ".join(_split(row.get("anchor_examples"))),
            "exercise_tags": _split(row.get("exercise_tags")),
            "source_refs": source_refs,
            "catalog_version": FRENCH_CORE_CATALOG_VERSION,
            "active": True,
        }

    def ensure_catalog(self, archive_legacy: bool = True) -> list[GrammarConcept]:
        rows = self.rows()
        concepts: list[GrammarConcept] = []
        active_external_ids = {row["external_id"] for row in rows}
        for row in rows:
            concept = self.db.query(GrammarConcept).filter(GrammarConcept.external_id == row["external_id"]).first()
            if not concept:
                concept = GrammarConcept(external_id=row["external_id"], name=row["name"], level=row["level"])
                self.db.add(concept)
            concept.language = row["language"]
            concept.name = row["name"]
            concept.level = row["level"]
            concept.category = row["category"]
            concept.subskill = row["subskill"]
            concept.description = row["description"]
            concept.examples = row["anchor_examples"]
            concept.difficulty_order = row["difficulty_order"]
            concept.core_rule = row["core_rule"]
            concept.main_traps = row["main_traps"]
            concept.anchor_examples = row["anchor_examples"]
            concept.exercise_tags = row["exercise_tags"]
            concept.is_foundation = row["is_foundation"]
            concept.active = True
            concept.catalog_version = FRENCH_CORE_CATALOG_VERSION
            concept.source_refs = row["source_refs"]
            concepts.append(concept)
            self.db.flush()
            self._upsert_localization(concept, row)

        if archive_legacy:
            self._archive_legacy_concepts(active_external_ids)
        self.db.commit()
        return concepts

    def _upsert_localization(self, concept: GrammarConcept, row: dict[str, Any]) -> None:
        localization = (
            self.db.query(GrammarConceptLocalization)
            .filter(
                GrammarConceptLocalization.concept_id == concept.id,
                GrammarConceptLocalization.locale == "de",
            )
            .first()
        )
        if not localization:
            localization = GrammarConceptLocalization(concept_id=concept.id, locale="de", title=row["title_de"])
            self.db.add(localization)
        localization.title = row["title_de"] or row["name"]
        localization.category_label = GERMAN_CATEGORY_LABELS.get(row["category"] or "")
        localization.subskill_label = row["title_de"] or row["subskill"]
        localization.short_description = row["core_rule"]

    def _archive_legacy_concepts(self, active_external_ids: set[str]) -> None:
        legacy_rows = (
            self.db.query(GrammarConcept)
            .filter(
                GrammarConcept.language == "fr",
                GrammarConcept.active.is_(True),
            )
            .all()
        )
        for concept in legacy_rows:
            if concept.external_id in active_external_ids:
                continue
            if not self._archive_exists(concept):
                self.db.add(
                    GrammarConceptArchive(
                        concept_id=concept.id,
                        external_id=concept.external_id,
                        language=concept.language or "fr",
                        archived_from_version=concept.catalog_version,
                        archive_reason="not_in_focused_french_core_catalog",
                        replacement_external_id=None,
                        source_refs=concept.source_refs or {},
                        row_snapshot=self._snapshot(concept),
                    )
                )
            concept.active = False

    def _archive_exists(self, concept: GrammarConcept) -> bool:
        return (
            self.db.query(GrammarConceptArchive)
            .filter(
                GrammarConceptArchive.concept_id == concept.id,
                GrammarConceptArchive.archive_reason == "not_in_focused_french_core_catalog",
            )
            .first()
            is not None
        )

    @staticmethod
    def _snapshot(concept: GrammarConcept) -> dict[str, Any]:
        return {
            "id": concept.id,
            "external_id": concept.external_id,
            "language": concept.language,
            "name": concept.name,
            "level": concept.level,
            "category": concept.category,
            "subskill": concept.subskill,
            "description": concept.description,
            "examples": concept.examples,
            "difficulty_order": concept.difficulty_order,
            "core_rule": concept.core_rule,
            "main_traps": concept.main_traps,
            "anchor_examples": concept.anchor_examples,
            "exercise_tags": concept.exercise_tags or [],
            "is_foundation": concept.is_foundation,
            "active": concept.active,
            "catalog_version": concept.catalog_version,
            "source_refs": concept.source_refs or {},
        }
