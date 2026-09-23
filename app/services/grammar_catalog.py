"""Curated grammar catalog import and archival utilities.

Two curated catalogues exist (WP-L2):

* ``french_core_grammar_v1`` — ``templates/french_core_grammar_v1.tsv``, 54 coarse concepts.
  The live product; the default.
* ``fr-core-v2`` — ``templates/french_core_grammar_v2.tsv``, about 150 teachable units A1–B2,
  each tagged to a sub-band (A1.1 … B2.2) with prerequisites, contrast partners, a detector spec
  and a one-sentence rule in en / de / fr.

``settings.ATELIER_GRAMMAR_CATALOG_VERSION`` ("v1" or "v2") picks the one that is seeded and
served. Switching to v2 seeds v2, archives every other active French row (v1 included, with the
replacing v2 unit recorded on the archive row) and copies learners' v1 progress onto v2 — see
:meth:`FrenchCoreGrammarCatalog.migrate_progress_to_v2` for the rule. Nothing is deleted, so
switching back to v1 reactivates v1 with its progress untouched.
"""
from __future__ import annotations

import copy
import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptArchive,
    GrammarConceptLocalization,
    UserGrammarProgress,
)

FRENCH_CORE_CATALOG_VERSION = "french_core_grammar_v1"
FRENCH_CORE_CATALOG_V2_VERSION = "fr-core-v2"

#: catalog_version label -> TSV file under templates/
CATALOG_FILES: dict[str, str] = {
    FRENCH_CORE_CATALOG_VERSION: "french_core_grammar_v1.tsv",
    FRENCH_CORE_CATALOG_V2_VERSION: "french_core_grammar_v2.tsv",
}
#: Short setting values ("v1"/"v2") -> catalog_version label.
CATALOG_SETTING_ALIASES: dict[str, str] = {
    "v1": FRENCH_CORE_CATALOG_VERSION,
    "v2": FRENCH_CORE_CATALOG_V2_VERSION,
    FRENCH_CORE_CATALOG_VERSION: FRENCH_CORE_CATALOG_VERSION,
    FRENCH_CORE_CATALOG_V2_VERSION: FRENCH_CORE_CATALOG_V2_VERSION,
}
V1_TO_V2_MAPPING_FILE = "french_core_grammar_v1_to_v2.tsv"

SUB_BANDS: tuple[str, ...] = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2")
RULE_LOCALES: tuple[str, ...] = ("en", "de", "fr")

# Legacy rows spell the language every which way ("fr", "French", "Français").
# Archival used to match "fr" exactly, so two pre-catalog rows stored as
# "French" stayed active forever: /grammar/summary counted 56 concepts while the
# Cahier index (which filters on the catalog version) listed 54, and Le Relevé
# printed "N / 56" against an index of 54.
FRENCH_LANGUAGE_ALIASES: tuple[str, ...] = ("fr", "fra", "fre", "french", "francais", "français")

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
    "Adverbs": "Adverbien",
    "Agreement": "Kongruenz",
    "Articles": "Artikel",
    "Comparison": "Vergleich",
    "Conditionals": "Bedingungssätze",
    "Connectors": "Konnektoren",
    "Determiners": "Begleiter",
    "Negation": "Verneinung",
    "Numbers": "Zahlen und Zeit",
    "Prepositions": "Präpositionen",
    "Pronouns": "Pronomen",
    "Relative clauses": "Relativsätze",
    "Syntax": "Satzbau",
    "Tenses": "Zeiten",
    "Verbs": "Verben",
}

FRENCH_CATEGORY_LABELS = {
    "Adverbs": "Adverbes",
    "Agreement": "Accord",
    "Articles": "Articles",
    "Comparison": "Comparaison",
    "Conditionals": "Conditionnelles",
    "Connectors": "Connecteurs",
    "Determiners": "Déterminants",
    "Negation": "Négation",
    "Numbers": "Nombres et temps",
    "Prepositions": "Prépositions",
    "Pronouns": "Pronoms",
    "Relative clauses": "Relatives",
    "Syntax": "Syntaxe",
    "Tenses": "Temps",
    "Verbs": "Verbes",
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


def parse_detector(value: str | None) -> dict[str, str] | None:
    """``"regex:<pattern>"`` or ``"llm:<description>"`` -> ``{"kind", "pattern"|"description"}``."""

    raw = str(value or "").strip()
    if raw.startswith("regex:"):
        return {"kind": "regex", "pattern": raw[len("regex:"):]}
    if raw.startswith("llm:"):
        return {"kind": "llm", "description": raw[len("llm:"):].strip()}
    return None


def detector_matches(detector: dict[str, str] | None, text: str) -> bool | None:
    """Apply a regex detector to French text; ``None`` when the detector is not a regex.

    Apostrophes are folded to ``'`` first: iOS types U+2019 and the patterns are written with
    the ASCII apostrophe.
    """

    if not detector or detector.get("kind") != "regex":
        return None
    folded = re.sub(r"[’ʼ‘]", "'", text or "")
    return re.search(detector["pattern"], folded, re.IGNORECASE) is not None


def active_catalog_version() -> str:
    """The catalog_version label selected by ``ATELIER_GRAMMAR_CATALOG_VERSION`` (default v1)."""

    from app.config import settings

    raw = str(getattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1") or "v1").strip()
    return CATALOG_SETTING_ALIASES.get(raw.casefold(), CATALOG_SETTING_ALIASES.get(raw, FRENCH_CORE_CATALOG_VERSION))


def catalog_path(version: str) -> Path:
    return _repo_root() / "templates" / CATALOG_FILES[version]


@lru_cache(maxsize=4)
def _cached_rows(version: str, mtime_ns: int) -> tuple[dict[str, Any], ...]:
    path = catalog_path(version)
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(
            _normalize_row(row, version)
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("external_id")
        )


def catalog_rows(version: str | None = None) -> list[dict[str, Any]]:
    """Normalized rows of one catalogue (parsed once per file version)."""

    version = version or active_catalog_version()
    path = catalog_path(version)
    if not path.exists():
        return []
    return copy.deepcopy(list(_cached_rows(version, path.stat().st_mtime_ns)))


def load_v1_to_v2_mapping() -> dict[str, list[str]]:
    """Every v1 external_id -> the v2 units that replace it; the first one inherits progress."""

    path = _repo_root() / "templates" / V1_TO_V2_MAPPING_FILE
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["v1_external_id"].strip(): _split(row.get("v2_external_ids"))
            for row in csv.DictReader(handle, delimiter="\t")
            if (row.get("v1_external_id") or "").strip()
        }


def concept_syllabus(concept: GrammarConcept) -> dict[str, Any]:
    """The v2 syllabus block of a concept (empty for v1 rows)."""

    refs = getattr(concept, "source_refs", None) or {}
    syllabus = refs.get("syllabus") if isinstance(refs, dict) else None
    return syllabus if isinstance(syllabus, dict) else {}


def concept_sub_band(concept: GrammarConcept) -> str | None:
    return concept_syllabus(concept).get("sub_band")


def _normalize_row(row: dict[str, str], version: str = FRENCH_CORE_CATALOG_VERSION) -> dict[str, Any]:
    source_codes = _split(row.get("source_refs"))
    source_refs: dict[str, Any] = {
        "catalog_version": version,
        "source_codes": source_codes,
        "urls": [SOURCE_REFERENCE_URLS[code] for code in source_codes if code in SOURCE_REFERENCE_URLS],
        "blueprint_seed": {
            "display_title": row.get("name_en", "").strip(),
            "localized_titles": {
                "de": row.get("name_de", "").strip(),
                "fr": row.get("name_fr", "").strip(),
            },
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
    normalized: dict[str, Any] = {
        "external_id": row.get("external_id", "").strip(),
        "language": row.get("language", "fr").strip() or "fr",
        "level": row.get("cefr_level", "A1").strip() or "A1",
        "category": row.get("category", "").strip() or None,
        "subskill": row.get("subskill", "").strip() or None,
        "name": row.get("name_en", "").strip(),
        "title_de": row.get("name_de", "").strip(),
        "title_fr": row.get("name_fr", "").strip(),
        "difficulty_order": int(row.get("teaching_order") or 0),
        "is_foundation": _parse_bool(row.get("is_foundation")),
        "core_rule": row.get("core_rule", "").strip(),
        "description": row.get("when_to_use", "").strip(),
        "main_traps": " | ".join(_split(row.get("main_traps"))),
        "anchor_examples": " | ".join(_split(row.get("anchor_examples"))),
        "exercise_tags": _split(row.get("exercise_tags")),
        "source_refs": source_refs,
        "catalog_version": version,
        "active": True,
    }
    if version != FRENCH_CORE_CATALOG_VERSION:
        rule_short = {locale: row.get(f"rule_short_{locale}", "").strip() for locale in RULE_LOCALES}
        syllabus = {
            "sub_band": row.get("sub_band", "").strip(),
            "prerequisites": _split(row.get("prerequisites")),
            "contrast_partners": _split(row.get("contrast_partners")),
            "detector": parse_detector(row.get("detector")),
            "rule_short": rule_short,
            "names": {
                "en": normalized["name"],
                "de": normalized["title_de"],
                "fr": normalized["title_fr"],
            },
            "review_status": row.get("review_status", "").strip() or "draft",
        }
        source_refs["syllabus"] = syllabus
        normalized["syllabus"] = syllabus
    return normalized


class FrenchCoreGrammarCatalog:
    """Import the focused French grammar catalog and archive legacy tracker rows."""

    def __init__(self, db: Session, version: str | None = None) -> None:
        self.db = db
        self.version = CATALOG_SETTING_ALIASES.get(version or "", None) or active_catalog_version()

    def catalog_path(self) -> Path:
        return catalog_path(self.version)

    def rows(self) -> list[dict[str, Any]]:
        return catalog_rows(self.version)

    def ensure_catalog(self, archive_legacy: bool = True) -> list[GrammarConcept]:
        rows = self.rows()
        concepts: list[GrammarConcept] = []
        active_external_ids = {row["external_id"] for row in rows}
        existing = {
            concept.external_id: concept
            for concept in self.db.query(GrammarConcept)
            .filter(GrammarConcept.external_id.in_(active_external_ids))
            .all()
        } if active_external_ids else {}
        for row in rows:
            concept = existing.get(row["external_id"])
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
            concept.catalog_version = self.version
            concept.source_refs = row["source_refs"]
            concepts.append(concept)
        self.db.flush()

        localizations: dict[tuple[int, str], GrammarConceptLocalization] = {}
        if concepts:
            for localization in (
                self.db.query(GrammarConceptLocalization)
                .filter(GrammarConceptLocalization.concept_id.in_([concept.id for concept in concepts]))
                .all()
            ):
                localizations[(localization.concept_id, localization.locale)] = localization
        for concept, row in zip(concepts, rows, strict=True):
            self._upsert_localization(concept, row, localizations)

        if self.version == FRENCH_CORE_CATALOG_V2_VERSION:
            self._store_prerequisites(concepts, rows)

        if archive_legacy and rows:  # a missing catalogue file must never archive everything
            self._archive_legacy_concepts(active_external_ids)
        if self.version == FRENCH_CORE_CATALOG_V2_VERSION:
            self.db.flush()
            self.migrate_progress_to_v2()
            self.remap_errata_to_v2()
        else:
            self.restore_errata_to_v1()
        self.db.commit()
        return concepts

    # ------------------------------------------------------------------
    # v2: prerequisites and progress migration
    # ------------------------------------------------------------------

    @staticmethod
    def _store_prerequisites(concepts: list[GrammarConcept], rows: list[dict[str, Any]]) -> None:
        """Store prerequisites as concept ids (the shape ``GrammarService`` graphs already read)."""

        id_by_external = {concept.external_id: concept.id for concept in concepts}
        for concept, row in zip(concepts, rows, strict=True):
            wanted = [
                id_by_external[external_id]
                for external_id in row["syllabus"]["prerequisites"]
                if external_id in id_by_external
            ]
            if list(concept.prerequisites or []) != wanted:
                concept.prerequisites = wanted

    def migrate_progress_to_v2(self) -> int:
        """Copy learners' v1 progress onto v2 so switching catalogues loses nothing.

        The rule (WP-L2):

        * every v1 concept maps to one or more v2 units
          (``templates/french_core_grammar_v1_to_v2.tsv``); the **first** listed unit is the
          foundation child and inherits the learner's v1 progress row (score, reps, state,
          last/next review, notes) — the other children start fresh, because the learner was
          never taught them one by one;
        * when several v1 concepts seed the same v2 unit (a merge, e.g. the A2 «intro» and B1
          rows of imparfait vs passé composé), the strongest row wins: highest score, then most
          reps, then the latest review;
        * a learner who already has progress on the v2 unit keeps it — migration never
          overwrites, so it is idempotent and safe to run on every seed;
        * v1 rows are copied, not moved: switching back to v1 finds them untouched.

        Returns the number of progress rows created.
        """

        mapping = load_v1_to_v2_mapping()
        if not mapping:
            return 0
        v1_concepts: dict[int, str] = dict(
            self.db.query(GrammarConcept.id, GrammarConcept.external_id)
            .filter(GrammarConcept.external_id.in_(list(mapping)))
            .all()
        )
        if not v1_concepts:
            return 0
        seed_targets = {targets[0] for targets in mapping.values() if targets}
        v2_ids = {
            external_id: concept_id
            for concept_id, external_id in self.db.query(GrammarConcept.id, GrammarConcept.external_id)
            .filter(
                GrammarConcept.external_id.in_(seed_targets),
                GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_V2_VERSION,
            )
            .all()
        }
        sources = (
            self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.concept_id.in_(list(v1_concepts)))
            .all()
        )
        if not sources:
            return 0
        existing = {
            (user_id, concept_id)
            for user_id, concept_id in self.db.query(UserGrammarProgress.user_id, UserGrammarProgress.concept_id)
            .filter(UserGrammarProgress.concept_id.in_(list(v2_ids.values())))
            .all()
        }
        best: dict[tuple[Any, int], tuple[UserGrammarProgress, str]] = {}
        for row in sources:
            v1_external = v1_concepts[row.concept_id]
            targets = mapping.get(v1_external) or []
            target_id = v2_ids.get(targets[0]) if targets else None
            if target_id is None:
                continue
            key = (row.user_id, target_id)
            if key in existing:
                continue
            current = best.get(key)
            if current is None or _progress_strength(row) > _progress_strength(current[0]):
                best[key] = (row, v1_external)
        for (user_id, target_id), (row, v1_external) in best.items():
            note = f"[{FRENCH_CORE_CATALOG_V2_VERSION}] progress carried over from {v1_external}"
            self.db.add(
                UserGrammarProgress(
                    user_id=user_id,
                    concept_id=target_id,
                    score=row.score,
                    reps=row.reps,
                    state=row.state,
                    last_review=row.last_review,
                    next_review=row.next_review,
                    # WP-L3's memory travels with the progress it describes.
                    stability=getattr(row, "stability", 0.0) or 0.0,
                    difficulty=getattr(row, "difficulty", 5.0) or 5.0,
                    lapses=getattr(row, "lapses", 0) or 0,
                    notes="\n".join(part for part in (row.notes, note) if part),
                )
            )
        if best:
            self.db.flush()
        return len(best)

    def remap_errata_to_v2(self) -> int:
        """Point every open erratum on a v1 concept at the v2 unit it belongs to (owner, 2026-09-23).

        Without this, a learner's open mistakes vanish from the due list the day v1 is archived.
        Among the v2 units a v1 concept maps to, the erratum goes to the first whose regex
        detector matches the corrected text (else the learner's own text), falling back to the
        first listed unit. The v1 id is kept in ``error_metadata["v1_concept_id"]`` so switching
        back to v1 restores it (:meth:`restore_errata_to_v1`). Retired errata stay where they are.
        Idempotent: an erratum already on a v2 unit is not touched. Returns the number remapped.
        """

        mapping = load_v1_to_v2_mapping()
        if not mapping:
            return 0
        v1_concepts: dict[int, str] = dict(
            self.db.query(GrammarConcept.id, GrammarConcept.external_id)
            .filter(GrammarConcept.external_id.in_(list(mapping)))
            .all()
        )
        if not v1_concepts:
            return 0
        targets = {target for units in mapping.values() for target in units}
        v2_units = {
            concept.external_id: concept
            for concept in self.db.query(GrammarConcept)
            .filter(
                GrammarConcept.external_id.in_(targets),
                GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_V2_VERSION,
            )
            .all()
        }
        errata = (
            self.db.query(UserError)
            .filter(UserError.concept_id.in_(list(v1_concepts)))
            .filter(UserError.state != "mastered")
            .all()
        )
        moved = 0
        for erratum in errata:
            candidates = [v2_units[unit] for unit in mapping.get(v1_concepts[erratum.concept_id]) or [] if unit in v2_units]
            if not candidates:
                continue
            chosen = candidates[0]
            for text in (erratum.correction, erratum.original_text):
                hit = next(
                    (unit for unit in candidates if detector_matches(concept_syllabus(unit).get("detector"), text or "")),
                    None,
                )
                if hit is not None:
                    chosen = hit
                    break
            metadata = dict(erratum.error_metadata or {})
            metadata.setdefault("v1_concept_id", erratum.concept_id)
            erratum.error_metadata = metadata
            erratum.concept_id = chosen.id
            moved += 1
        if moved:
            self.db.flush()
        return moved

    def restore_errata_to_v1(self) -> int:
        """Undo :meth:`remap_errata_to_v2` when the owner switches back to v1."""

        restored = 0
        for erratum in (
            self.db.query(UserError)
            .join(GrammarConcept, GrammarConcept.id == UserError.concept_id)
            .filter(GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_V2_VERSION)
            .all()
        ):
            metadata = dict(erratum.error_metadata or {})
            original = metadata.pop("v1_concept_id", None)
            if original is None:
                continue
            erratum.concept_id = int(original)
            erratum.error_metadata = metadata
            restored += 1
        if restored:
            self.db.flush()
        return restored

    # ------------------------------------------------------------------
    # Localizations
    # ------------------------------------------------------------------

    def _upsert_localization(
        self,
        concept: GrammarConcept,
        row: dict[str, Any],
        cache: dict[tuple[int, str], GrammarConceptLocalization] | None = None,
    ) -> None:
        syllabus = row.get("syllabus")
        if syllabus:
            # v2: every locale gets its own title and its own one-sentence rule.
            rule_short = syllabus["rule_short"]
            for locale, title, category_labels in (
                ("en", row["name"], None),
                ("de", row["title_de"] or row["name"], GERMAN_CATEGORY_LABELS),
                ("fr", row["title_fr"] or row["name"], FRENCH_CATEGORY_LABELS),
            ):
                self._upsert_locale_row(
                    concept,
                    locale=locale,
                    title=title,
                    category_label=(category_labels or {}).get(row["category"] or "", row["category"]),
                    subskill_label=title,
                    short_description=rule_short.get(locale) or row["core_rule"],
                    cache=cache,
                )
            return
        self._upsert_locale_row(
            concept,
            locale="de",
            title=row["title_de"] or row["name"],
            category_label=GERMAN_CATEGORY_LABELS.get(row["category"] or ""),
            subskill_label=row["title_de"] or row["subskill"],
            short_description=row["core_rule"],
            cache=cache,
        )
        self._upsert_locale_row(
            concept,
            locale="fr",
            title=row["title_fr"] or row["name"],
            category_label=FRENCH_CATEGORY_LABELS.get(row["category"] or ""),
            subskill_label=row["title_fr"] or row["subskill"],
            short_description=row["core_rule"],
            cache=cache,
        )

    def _upsert_locale_row(
        self,
        concept: GrammarConcept,
        *,
        locale: str,
        title: str,
        category_label: str | None,
        subskill_label: str | None,
        short_description: str | None,
        cache: dict[tuple[int, str], GrammarConceptLocalization] | None = None,
    ) -> None:
        if cache is not None:
            localization = cache.get((concept.id, locale))
        else:
            localization = (
                self.db.query(GrammarConceptLocalization)
                .filter(
                    GrammarConceptLocalization.concept_id == concept.id,
                    GrammarConceptLocalization.locale == locale,
                )
                .first()
            )
        if not localization:
            localization = GrammarConceptLocalization(concept_id=concept.id, locale=locale, title=title)
            self.db.add(localization)
            if cache is not None:
                cache[(concept.id, locale)] = localization
        localization.title = title
        localization.category_label = category_label
        localization.subskill_label = subskill_label
        localization.short_description = short_description

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    def _archive_legacy_concepts(self, active_external_ids: set[str]) -> None:
        legacy_rows = (
            self.db.query(GrammarConcept)
            .filter(
                func.lower(func.trim(GrammarConcept.language)).in_(FRENCH_LANGUAGE_ALIASES),
                GrammarConcept.active.is_(True),
            )
            .all()
        )
        replacements = load_v1_to_v2_mapping() if self.version == FRENCH_CORE_CATALOG_V2_VERSION else {}
        for concept in legacy_rows:
            if concept.external_id in active_external_ids:
                continue
            if not self._archive_exists(concept):
                replacement = (replacements.get(concept.external_id or "") or [None])[0]
                self.db.add(
                    GrammarConceptArchive(
                        concept_id=concept.id,
                        external_id=concept.external_id,
                        language=concept.language or "fr",
                        archived_from_version=concept.catalog_version,
                        archive_reason="not_in_focused_french_core_catalog",
                        replacement_external_id=replacement,
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


def _progress_strength(row: UserGrammarProgress) -> tuple[float, int, float]:
    last = row.last_review.timestamp() if row.last_review else 0.0
    return (float(row.score or 0.0), int(row.reps or 0), last)
