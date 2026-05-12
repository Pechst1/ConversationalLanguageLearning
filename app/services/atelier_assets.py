"""Stable Atelier language and concept asset generation."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierConceptBlueprint, AtelierLanguagePack
from app.db.models.grammar import GrammarConcept
from app.services.grammar_feedback import infer_grammar_profile

ATELIER_LANGUAGE_PACK_VERSION = "atelier-language-pack-v1"
ATELIER_BLUEPRINT_VERSION = "atelier-blueprint-v2"
ATELIER_BLUEPRINT_PROMPT_VERSION = "atelier-blueprint-template-v2"
BLUEPRINT_REQUIRED_KEYS = {
    "display_title",
    "pedagogy",
    "sentence_xray",
    "visual_motif",
    "exercise_recipe",
    "correction_rubric",
    "detection_hints",
}
PLACEHOLDER_PHRASES = (
    "use <concept>",
    "use {concept}",
    "use it when the sentence context asks for this grammar relation",
    "in the required context",
    "grammar relation to practice",
    "target grammar relation",
    "marks the grammar relation",
    "no examples yet",
    "no traps logged yet",
    "no contrast note yet",
    "no x-ray prepared yet",
)
RAW_TITLE_REPLACEMENTS = {
    "Häufige Kongruenzfallen": "Common agreement traps",
    "Determiner & Indefinita": "Determiners and indefinites",
    "Korrelationen": "Correlative expressions",
    "Quantoren & Mengen": "Quantity expressions and agreement",
    "Kongruenzregeln": "agreement rules",
    "Negation erweitert": "Extended negation",
    "Restriktiv": "Restriction",
    "Ne-Wegfall mündlich vs. Schriftsprache": "Dropping ne: spoken vs written French",
    "Satzbau": "Syntax",
    "Verben": "Verbs",
    "Allgemein": "General",
    "Kongruenz": "Agreement",
    "mündlich": "spoken",
    "Schriftsprache": "written French",
}


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"\s*[;|]\s*", value) if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item).strip())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _concept_source_hash(concept: GrammarConcept) -> str:
    payload = {
        "external_id": concept.external_id,
        "language": concept.language,
        "level": concept.level,
        "category": concept.category,
        "subskill": concept.subskill,
        "name": concept.name,
        "core_rule": concept.core_rule,
        "main_traps": concept.main_traps,
        "anchor_examples": concept.anchor_examples,
        "exercise_tags": concept.exercise_tags or [],
        "is_foundation": concept.is_foundation,
        "active": concept.active,
        "catalog_version": getattr(concept, "catalog_version", None),
        "source_refs": getattr(concept, "source_refs", None) or {},
    }
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _contains_placeholder(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.casefold()
    for phrase in PLACEHOLDER_PHRASES:
        if phrase.casefold() in lowered:
            return True
    return False


class AtelierAssetService:
    """Create and retrieve reviewable Atelier assets for language concepts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_language_pack(self, language_code: str = "fr") -> AtelierLanguagePack:
        code = (language_code or "fr").lower()
        pack = (
            self.db.query(AtelierLanguagePack)
            .filter(AtelierLanguagePack.language_code == code, AtelierLanguagePack.version == ATELIER_LANGUAGE_PACK_VERSION)
            .first()
        )
        payload = self._language_pack_payload(code)
        metadata = {
            "model": "deterministic-asset-generator",
            "prompt_version": ATELIER_BLUEPRINT_PROMPT_VERSION,
            "asset_kind": "language_pack",
        }
        if pack:
            if not pack.payload:
                pack.payload = payload
                pack.generation_metadata = metadata
                self.db.add(pack)
                self.db.commit()
                self.db.refresh(pack)
            return pack

        pack = AtelierLanguagePack(
            language_code=code,
            version=ATELIER_LANGUAGE_PACK_VERSION,
            review_status="approved",
            payload=payload,
            generation_metadata=metadata,
        )
        self.db.add(pack)
        self.db.commit()
        self.db.refresh(pack)
        return pack

    def ensure_assets_for_catalog(self, language_code: str = "fr") -> None:
        code = (language_code or "fr").lower()
        self.ensure_language_pack(code)
        concepts = (
            self.db.query(GrammarConcept)
            .filter(
                GrammarConcept.language == code,
                GrammarConcept.active.is_(True),
                GrammarConcept.external_id.isnot(None),
                GrammarConcept.external_id != "",
            )
            .all()
        )
        for concept in concepts:
            self.ensure_concept_blueprint(concept)

    def ensure_concept_blueprint(self, concept: GrammarConcept) -> AtelierConceptBlueprint:
        language = (concept.language or "fr").lower()
        existing = (
            self.db.query(AtelierConceptBlueprint)
            .filter(
                AtelierConceptBlueprint.concept_id == concept.id,
                AtelierConceptBlueprint.language == language,
                AtelierConceptBlueprint.asset_version == ATELIER_BLUEPRINT_VERSION,
            )
            .first()
        )
        source_hash = _concept_source_hash(concept)
        payload = self.generate_concept_blueprint_payload(concept)
        quality = self.blueprint_quality(payload)
        if not quality["valid"]:
            raise ValueError(f"Generated blueprint failed quality gate for concept {concept.id}: {quality['issues']}")
        payload["blueprint_quality"] = quality
        payload["blueprint_status"] = "approved"
        metadata = {
            "model": "deterministic-asset-generator",
            "prompt_version": ATELIER_BLUEPRINT_PROMPT_VERSION,
            "language_pack_version": ATELIER_LANGUAGE_PACK_VERSION,
            "source_csv_row_hash": source_hash,
            "schema_validation": "passed",
            "quality_score": quality["score"],
            "motif_signature": quality["motif_signature"],
            "reviewer_notes": "Auto-approved after deterministic quality gate; ready for human copy refinement.",
        }

        if existing and existing.source_hash == source_hash and self.validate_blueprint_payload(existing.payload):
            return existing
        if existing:
            existing.payload = payload
            existing.generation_metadata = metadata
            existing.source_hash = source_hash
            existing.review_status = "approved"
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        blueprint = AtelierConceptBlueprint(
            concept_id=concept.id,
            language=language,
            asset_version=ATELIER_BLUEPRINT_VERSION,
            review_status="approved",
            payload=payload,
            generation_metadata=metadata,
            source_hash=source_hash,
        )
        self.db.add(blueprint)
        self.db.commit()
        self.db.refresh(blueprint)
        return blueprint

    def approved_blueprint_payload(self, concept: GrammarConcept) -> dict[str, Any]:
        blueprint = (
            self.db.query(AtelierConceptBlueprint)
            .filter(
                AtelierConceptBlueprint.concept_id == concept.id,
                AtelierConceptBlueprint.language == (concept.language or "fr").lower(),
                AtelierConceptBlueprint.review_status == "approved",
            )
            .order_by(AtelierConceptBlueprint.created_at.desc())
            .first()
        )
        source_hash = _concept_source_hash(concept)
        if not blueprint or blueprint.source_hash != source_hash or not self.validate_blueprint_payload(blueprint.payload):
            blueprint = self.ensure_concept_blueprint(concept)
        payload = dict(blueprint.payload or {})
        quality = self.blueprint_quality(payload)
        if not quality["valid"]:
            raise ValueError(f"Approved blueprint failed quality gate for concept {concept.id}: {quality['issues']}")
        payload["blueprint_quality"] = quality
        payload["blueprint_status"] = blueprint.review_status
        return payload

    @classmethod
    def validate_blueprint_payload(cls, payload: dict[str, Any] | None) -> bool:
        return bool(cls.blueprint_quality(payload).get("valid"))

    @classmethod
    def blueprint_quality(cls, payload: dict[str, Any] | None) -> dict[str, Any]:
        issues: list[str] = []
        if not isinstance(payload, dict):
            return {"valid": False, "score": 0, "issues": ["payload is not an object"], "motif_signature": None}
        missing = sorted(BLUEPRINT_REQUIRED_KEYS.difference(payload.keys()))
        if missing:
            issues.append(f"missing keys: {', '.join(missing)}")

        title = str(payload.get("display_title") or "").strip()
        if len(title) < 4 or _contains_placeholder(title):
            issues.append("display_title is missing or generic")

        pedagogy = payload.get("pedagogy") or {}
        if not isinstance(pedagogy, dict):
            issues.append("pedagogy is not an object")
            pedagogy = {}
        for key in ("core_rule", "when_to_use", "pattern"):
            value = str(pedagogy.get(key) or "").strip()
            min_length = 8 if key == "pattern" else 18
            if len(value) < min_length or _contains_placeholder(value):
                issues.append(f"pedagogy.{key} is weak")

        traps = [str(item).strip() for item in pedagogy.get("main_traps") or [] if str(item).strip()]
        examples = [str(item).strip() for item in pedagogy.get("micro_examples") or [] if str(item).strip()]
        contrast = [str(item).strip() for item in (pedagogy.get("contrast_rules") or pedagogy.get("contrast_notes") or []) if str(item).strip()]
        if len(traps) < 2:
            issues.append("pedagogy.main_traps needs at least 2 items")
        if len(examples) < 3:
            issues.append("pedagogy.micro_examples needs at least 3 items")
        if not contrast or any(_contains_placeholder(item) for item in contrast):
            issues.append("pedagogy.contrast_rules needs specific contrast guidance")

        xray = payload.get("sentence_xray") or {}
        marks = xray.get("marks") if isinstance(xray, dict) else []
        if not isinstance(xray, dict) or not str(xray.get("sentence") or "").strip():
            issues.append("sentence_xray.sentence is missing")
        if len(str(xray.get("explanation") or "").strip()) < 60:
            issues.append("sentence_xray.explanation needs a teaching sentence")
        if not isinstance(marks, list) or len(marks) < 2:
            issues.append("sentence_xray needs at least 2 token marks")
        elif any(_contains_placeholder(str(mark.get("explanation") or "")) for mark in marks if isinstance(mark, dict)):
            issues.append("sentence_xray marks contain placeholder explanations")

        motif = payload.get("visual_motif") or {}
        primitives = motif.get("primitives") if isinstance(motif, dict) else []
        if not isinstance(motif, dict) or motif.get("style") != "atelier_bauhaus_v1":
            issues.append("visual_motif style is missing")
        if not isinstance(primitives, list) or len(primitives) < 4:
            issues.append("visual_motif needs at least 4 primitives")
        if _contains_placeholder(str(motif.get("concept_metaphor") or "")):
            issues.append("visual_motif metaphor is generic")
        motif_signature = cls.motif_signature(motif) if isinstance(motif, dict) else None

        rubric = payload.get("correction_rubric") or {}
        if not isinstance(rubric, dict) or not rubric.get("why_templates"):
            issues.append("correction_rubric why_templates missing")
        template_text = json.dumps(
            (rubric.get("why_templates") or []) + (rubric.get("repair_templates") or []),
            ensure_ascii=False,
        ).casefold() if isinstance(rubric, dict) else ""
        if "the learner" in template_text or "the user" in template_text:
            issues.append("correction_rubric must address with you")

        flattened = json.dumps(
            {
                "display_title": payload.get("display_title"),
                "pedagogy": pedagogy,
                "sentence_xray": xray,
                "visual_motif": motif,
            },
            ensure_ascii=False,
        )
        if any(phrase.casefold() in flattened.casefold() for phrase in PLACEHOLDER_PHRASES):
            issues.append("payload contains a blocked placeholder phrase")

        score = max(0, 100 - len(issues) * 12)
        return {
            "valid": not issues,
            "score": score,
            "issues": issues,
            "motif_signature": motif_signature,
        }

    @staticmethod
    def motif_signature(motif: dict[str, Any] | None) -> str | None:
        if not isinstance(motif, dict):
            return None
        primitives = motif.get("primitives") if isinstance(motif.get("primitives"), list) else []
        normalized = [
            {
                key: primitive.get(key)
                for key in sorted(primitive.keys())
                if key in {"type", "role", "x", "y", "w", "h", "cx", "cy", "r", "x1", "y1", "x2", "y2", "from", "to", "d", "label", "text"}
            }
            for primitive in primitives
            if isinstance(primitive, dict)
        ]
        data = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    def _language_pack_payload(self, language_code: str) -> dict[str, Any]:
        if language_code == "fr":
            return {
                "language_code": "fr",
                "display_name": "French",
                "supported_levels": ["A1", "A2", "B1", "B2", "C1"],
                "writing_system": "Latin",
                "grammar_categories": [
                    "Articles",
                    "Determiners",
                    "Pronouns",
                    "Verbs",
                    "Tenses",
                    "Conditionals",
                    "Negation",
                    "Syntax",
                    "Agreement",
                ],
                "orthography_rules": [
                    "Keep French apostrophes attached to the elided word.",
                    "Preserve accents in learner-facing examples where source material includes them.",
                    "Use French guillemets only for quoted fragments, not UI labels.",
                ],
                "punctuation_rules": [
                    "Use a space before high punctuation in polished French copy.",
                    "Closed drill normalization may accept missing accents and compact comma spacing.",
                ],
                "correction_style": {
                    "address": "you",
                    "max_why_sentences": 2,
                    "max_repair_sentences": 1,
                    "avoid_phrases": ["the learner", "the user"],
                },
                "atelier_design_language": {
                    "style": "editorial Bauhaus",
                    "motif_constraints": [
                        "use geometric primitives",
                        "use semantic labels sparingly",
                        "no decorative generic icons",
                        "icon must explain the grammar relation",
                    ],
                },
            }
        return {
            "language_code": language_code,
            "display_name": language_code.upper(),
            "supported_levels": ["A1", "A2", "B1", "B2", "C1"],
            "writing_system": "language-specific",
            "grammar_categories": [],
            "orthography_rules": [],
            "punctuation_rules": [],
            "correction_style": {
                "address": "you",
                "max_why_sentences": 2,
                "max_repair_sentences": 1,
                "avoid_phrases": ["the learner", "the user"],
            },
            "atelier_design_language": {
                "style": "editorial Bauhaus",
                "motif_constraints": [
                    "use geometric primitives",
                    "use semantic labels sparingly",
                    "no decorative generic icons",
                    "icon must explain the grammar relation",
                ],
            },
        }

    def generate_concept_blueprint_payload(self, concept: GrammarConcept) -> dict[str, Any]:
        """Generate a concept-specific, reviewable blueprint without showing placeholders."""
        family = self._concept_family(concept)
        seed = self._blueprint_seed(concept)
        display_title = self._display_title(concept, family)
        examples = self._examples_for(concept, family)
        traps = self._traps_for(concept, family)
        motif = self._motif_for(concept, family, display_title)
        motif["signature"] = self.motif_signature(motif)

        payload = {
            "asset_version": ATELIER_BLUEPRINT_VERSION,
            "language": concept.language or "fr",
            "concept_external_id": concept.external_id,
            "display_title": display_title,
            "pedagogy": {
                "core_rule": self._core_rule_for(concept, family, display_title),
                "when_to_use": self._when_to_use_for(concept, family, display_title),
                "pattern": self._pattern_for(concept, family, display_title),
                "main_traps": traps[:5],
                "contrast_rules": self._contrast_rules_for(concept, family, display_title),
                "micro_examples": examples[:5],
            },
            "sentence_xray": self._xray_for(concept, family),
            "visual_motif": motif,
            "exercise_recipe": self._exercise_recipe(concept, family),
            "correction_rubric": self._correction_rubric_for(concept, family),
            "detection_hints": self._detection_hints_for(concept, family, traps),
        }
        payload["blueprint_quality"] = self.blueprint_quality(payload)
        payload["blueprint_status"] = "draft"
        if seed:
            payload["catalog_blueprint_seed"] = {"source": "curated_catalog", "has_seed": True}
        return payload

    def _blueprint_seed(self, concept: GrammarConcept) -> dict[str, Any]:
        refs = getattr(concept, "source_refs", None) or {}
        if isinstance(refs, dict):
            seed = refs.get("blueprint_seed") or {}
            if isinstance(seed, dict):
                return seed
        return {}

    def _exercise_recipe(self, concept: GrammarConcept, family: str | None = None) -> dict[str, Any]:
        return {
            "recognize": {
                "fill": {"subitems": 3, "goal": "choose the form that completes the target frame"},
                "word_bank": {"subitems": 3, "goal": "assemble a scrambled target sentence; tokens must not start in order"},
                "classify": {"subitems": 3, "goal": "identify the grammar role or contrast class"},
            },
            "transform": {
                "directed_rewrite": {"subitems": 1, "goal": "rewrite into the target structure"},
                "contrast_rewrite": {"subitems": 1, "goal": "move from a neighboring contrast into the target"},
                "repair_rewrite": {"subitems": 1, "goal": "fix only the target mistake"},
            },
            "output_ladder": {
                "short_sentence": {"subitems": 1, "goal": "produce one original sentence"},
                "paragraph": {"target_count": 2 if concept.level in {"B1", "B2", "C1"} else 1},
                "spoken_response": {"subitems": 1, "goal": "say and transcribe one response"},
                "conversation_turn": {"subitems": 1, "goal": "use the concept naturally in dialogue"},
            },
            "family": family or self._concept_family(concept),
        }

    def _concept_family(self, concept: GrammarConcept) -> str:
        profile = infer_grammar_profile(concept)
        profile_families = {
            "si_present_result_form": "condition",
            "article_after_negation": "negation",
            "tense_aspect": "tense_aspect",
            "conditional_mood": "condition",
            "mood": "verb_form",
            "relative_pronoun": "relative_clause",
            "pronoun_choice": "pronoun",
            "determiner": "determiner",
            "agreement": "agreement",
            "preposition": "syntax",
            "comparison": "syntax",
        }
        if profile.key in profile_families:
            return profile_families[profile.key]
        text = " ".join(
            str(part or "")
            for part in (concept.external_id, concept.category, concept.subskill, concept.name, concept.core_rule, concept.description)
        ).casefold()
        if "kongruenz" in text or "agreement" in text or "accord" in text:
            return "agreement"
        if "article" in text or "determiner" in text or "détermin" in text or "determiner" in text or "quant" in text or "indefinit" in text:
            return "determiner"
        if "pronoun" in text or "pronom" in text or "y/en" in text:
            return "pronoun"
        if "relative" in text or "dont" in text or "lequel" in text or "qui/que" in text:
            return "relative_clause"
        if "verb" in text or "verben" in text or "subjonctif" in text or "participe" in text or "infinitif" in text:
            return "verb_form"
        return "syntax"

    def _display_title(self, concept: GrammarConcept, family: str) -> str:
        seeded = str(self._blueprint_seed(concept).get("display_title") or "").strip()
        if len(seeded) > 3 and not _contains_placeholder(seeded):
            return seeded
        title = str(concept.name or concept.subskill or concept.category or "Grammar concept").strip()
        for source, replacement in RAW_TITLE_REPLACEMENTS.items():
            title = title.replace(source, replacement)
        title = title.replace(" & ", " and ")
        title = title.replace("...", "...")
        title = re.sub(r"\s+", " ", title).strip(" -")
        if not title or title.casefold() in {"grammar concept", "general", "allgemein"}:
            title = {
                "agreement": "Agreement pattern",
                "negation": "Negation pattern",
                "tense_aspect": "Tense and aspect contrast",
                "determiner": "Determiner pattern",
                "pronoun": "Pronoun choice",
                "relative_clause": "Relative clause link",
                "verb_form": "Verb form pattern",
                "syntax": "Sentence structure pattern",
                "condition": "Condition frame",
            }[family]
        return title[:1].upper() + title[1:]

    def _core_rule_for(self, concept: GrammarConcept, family: str, title: str) -> str:
        seed = self._blueprint_seed(concept)
        seeded_rule = str(seed.get("core_rule") or concept.core_rule or "").strip()
        if len(seeded_rule) > 24 and not _contains_placeholder(seeded_rule):
            return seeded_rule
        seeded = str(concept.core_rule or "").strip()
        if len(seeded) > 24 and not _contains_placeholder(seeded):
            return seeded
        rules = {
            "condition": "In a real si-condition, keep the si-clause in the present and put the consequence in future simple or in the imperative.",
            "tense_aspect": "Use imparfait for the ongoing background, habit, or description; use passe compose for the bounded event that moves the story forward.",
            "negation": "French negation frames the verb, and quantities or indefinite articles usually become de or d' after pas.",
            "agreement": "Agreement follows the controller of the phrase: check number and gender before choosing the verb, determiner, adjective, or participle form.",
            "determiner": "The determiner sets how the noun is counted, identified, or limited, so it must match the noun and the sentence meaning.",
            "pronoun": "A pronoun replaces a known noun phrase, but its form and position depend on whether it stands for a person, thing, place, quantity, or indirect object.",
            "relative_clause": "A relative pronoun links two clauses and carries the role that the repeated noun would have had inside the second clause.",
            "verb_form": "Choose the verb form from the frame around it: subject, trigger, tense, mood, and whether the action is finite or infinitive.",
            "syntax": "French sentence structure depends on the role of each phrase; keep the required slots in order before polishing style.",
        }
        return rules[family]

    def _when_to_use_for(self, concept: GrammarConcept, family: str, title: str) -> str:
        seeded = str(self._blueprint_seed(concept).get("when_to_use") or "").strip()
        if len(seeded) > 24 and not _contains_placeholder(seeded):
            return seeded
        when = {
            "condition": "Use it when a sentence presents a possible condition and a consequence that is still open in the future.",
            "tense_aspect": "Use it whenever a past sentence mixes a scene, habit, or ongoing state with a completed action.",
            "negation": "Use it when a negative sentence changes what exists, how much exists, or whether a noun phrase is still definite.",
            "agreement": "Use it when two parts of the sentence must visibly belong together: subject and verb, noun and adjective, quantity and verb, or noun and participle.",
            "determiner": "Use it before a noun when the sentence needs to show whether you mean a specific item, any item, a quantity, or no quantity.",
            "pronoun": "Use it when the noun is already known and repeating it would sound heavy or unnatural.",
            "relative_clause": "Use it when you want one sentence to identify, define, or add information about a noun without starting a new sentence.",
            "verb_form": "Use it when the surrounding words trigger a specific tense, mood, infinitive, or participle pattern.",
            "syntax": "Use it when the sentence meaning depends on clause order, restriction, emphasis, or a fixed construction.",
        }
        return when[family]

    def _pattern_for(self, concept: GrammarConcept, family: str, title: str) -> str:
        seeded = str(self._blueprint_seed(concept).get("pattern") or "").strip()
        if len(seeded) > 5 and not _contains_placeholder(seeded):
            return seeded
        patterns = {
            "condition": "si + present clause -> future simple or imperative result",
            "tense_aspect": "imparfait = background/habit; passe compose = completed event",
            "negation": "ne/n' + verb + pas + de/d' + noun, unless the noun remains definite or follows etre",
            "agreement": "controller noun/quantity + agreeing form; verify gender and number before the ending",
            "determiner": "determiner + noun; match gender/number and choose specific, indefinite, partitive, or negative quantity",
            "pronoun": "pronoun slot before the conjugated verb; choose le/la/les, lui/leur, y, or en by function",
            "relative_clause": "noun + qui/que/dont/ou/lequel + clause with the missing role filled by the pronoun",
            "verb_form": "trigger + subject + required verb form; keep the same frame while changing only the target form",
            "syntax": "fixed construction + clause slot + complement slot; preserve the frame before changing vocabulary",
        }
        return patterns[family]

    def _contrast_rules_for(self, concept: GrammarConcept, family: str, title: str) -> list[str]:
        seeded = [
            str(item).strip()
            for item in (self._blueprint_seed(concept).get("contrast_rules") or [])
            if str(item).strip() and not _contains_placeholder(str(item))
        ]
        if len(seeded) >= 2:
            return seeded
        if infer_grammar_profile(concept).key == "si_present_result_form":
            return ["Do not put future simple immediately after si.", "Do not replace the requested si frame with quand."]
        contrasts = {
            "condition": ["Si with a real condition is not the same as quand for certainty.", "A conditional result changes the meaning toward hypothesis or politeness."],
            "tense_aspect": ["Imparfait is not a generic past tense; it frames background.", "Passe compose is not only about short actions; it marks a bounded event."],
            "negation": ["Pas de signals negative quantity; ce n'est pas keeps the original article.", "Ne... que means only, not a full negative statement."],
            "agreement": ["Do not agree mechanically with the nearest noun if a quantity or collective expression controls the phrase.", "Spoken shortcuts may hide agreement, but written French still shows it."],
            "determiner": ["Partitive articles express an unspecified amount; definite articles point to a known class or item.", "Indefinite and negative quantity patterns are different after pas."],
            "pronoun": ["En replaces de + noun or a quantity; le/la/les replace direct objects.", "Lui/leur stand for indirect people, not places or quantities."],
            "relative_clause": ["Qui is subject inside the relative clause; que is object.", "Dont replaces de + noun, not every English 'whose/of which' phrasing."],
            "verb_form": ["A trigger can require mood even when the English translation stays unchanged.", "Do not change the whole sentence frame when only the verb form is being tested."],
            "syntax": ["A fixed construction often changes emphasis, not the basic vocabulary.", "Do not translate word-by-word when French requires a structural frame."],
        }
        return contrasts[family]

    def _traps_for(self, concept: GrammarConcept, family: str) -> list[str]:
        seeded = _split_list(concept.main_traps)
        family_traps = {
            "condition": ["using future immediately after si", "replacing the si frame with quand", "using conditional where future simple is required"],
            "tense_aspect": ["using passe compose for the whole past sentence", "using imparfait for a completed event", "missing the background/event cue"],
            "negation": ["keeping du/de la/des after pas", "forgetting ne in formal writing", "applying pas de to the etre exception"],
            "agreement": ["agreeing with the nearest noun only", "missing plural after quantity expressions", "forgetting feminine or plural marks in writing"],
            "determiner": ["choosing an article from English meaning only", "forgetting elision before vowels", "mixing partitive and indefinite quantity"],
            "pronoun": ["using en where le/la/les is needed", "placing the pronoun after the conjugated verb", "using lui/leur for a direct object"],
            "relative_clause": ["using qui when the noun is object", "using que when the noun is subject", "forgetting dont after de"],
            "verb_form": ["changing the whole sentence instead of the target form", "ignoring the trigger word", "mixing infinitive and conjugated forms"],
            "syntax": ["translating the English order directly", "dropping a required frame word", "moving emphasis without keeping the construction"],
        }
        return _dedupe(seeded + family_traps[family])

    def _examples_for(self, concept: GrammarConcept, family: str) -> list[str]:
        seeded = _split_list(concept.anchor_examples) + _split_list(concept.examples)
        fallback = {
            "condition": ["Si tu viens, on ira.", "S'il pleut, prends ton manteau.", "Si elle appelle, je repondrai."],
            "tense_aspect": ["Il pleuvait quand je suis sorti.", "Je lisais quand le telephone a sonne.", "Chaque ete, nous allions a Lyon."],
            "negation": ["Je ne mange pas de viande.", "Ce n'est pas du cafe.", "Il ne vient guere ici."],
            "agreement": ["La plupart des etudiants sont arrives.", "Plus d'un eleve a repondu.", "Nulle personne n'est entree."],
            "determiner": ["Chaque etudiant apporte son livre.", "Je voudrais du pain.", "Je n'ai pas de questions."],
            "pronoun": ["Je lui parle demain.", "J'en prends deux.", "Nous y pensons souvent."],
            "relative_clause": ["C'est le livre dont je parle.", "La femme qui arrive est professeure.", "Le film que tu recommandes est long."],
            "verb_form": ["Il faut que tu viennes.", "Je vais partir demain.", "Nous avons fini le travail."],
            "syntax": ["Ce que je veux, c'est comprendre.", "Il ne lit que le titre.", "Plus il travaille, mieux il ecrit."],
        }
        return _dedupe(seeded + fallback[family])

    def _xray_for(self, concept: GrammarConcept, family: str) -> dict[str, Any]:
        seeded = self._blueprint_seed(concept).get("sentence_xray") or {}
        if isinstance(seeded, dict):
            marks = seeded.get("marks") if isinstance(seeded.get("marks"), list) else []
            sentence = str(seeded.get("sentence") or "").strip()
            explanation = str(seeded.get("explanation") or "").strip()
            if sentence and len(explanation) >= 40 and len(marks) >= 2:
                return {
                    "sentence": sentence,
                    "explanation": explanation,
                    "marks": [
                        {
                            "token": str(mark.get("token") or ""),
                            "role": str(mark.get("role") or "mark"),
                            "explanation": str(mark.get("explanation") or ""),
                            "color": mark.get("color") or "ink",
                            "underline": mark.get("underline") or "solid",
                        }
                        for mark in marks
                        if isinstance(mark, dict) and mark.get("token")
                    ],
                }
        if infer_grammar_profile(concept).key == "si_present_result_form":
            return {
                "sentence": "Si je finis tot, je t'appellerai.",
                "explanation": "The condition itself stays in the present after si. The future meaning is carried by the result clause, so the consequence appears as appellerai.",
                "marks": [
                    {"token": "Si", "role": "condition_trigger", "explanation": "opens a real condition"},
                    {"token": "finis", "role": "present_si_clause", "explanation": "present tense stays after si"},
                    {"token": "appellerai", "role": "future_result", "explanation": "future simple carries the consequence"},
                ],
            }
        xray_payloads = {
            "condition": {
                "sentence": "Si elle appelle, je repondrai.",
                "explanation": "The si-clause names the condition in the present. The result clause carries the future consequence, so only the second verb moves into future simple.",
                "marks": [
                    {"token": "Si elle appelle", "role": "condition", "explanation": "present condition after si"},
                    {"token": "je repondrai", "role": "result", "explanation": "future consequence"},
                ],
            },
            "tense_aspect": {
                "sentence": "Il pleuvait quand je suis sorti.",
                "explanation": "Pleuvait describes the weather already in progress. Suis sorti marks the completed event that happens against that background.",
                "marks": [
                    {"token": "pleuvait", "role": "background", "explanation": "ongoing scene in imparfait"},
                    {"token": "suis sorti", "role": "event", "explanation": "bounded event in passe compose"},
                ],
            },
            "negation": {
                "sentence": "Je ne mange pas de viande.",
                "explanation": "Ne and pas frame the verb. Because the object is a negated quantity, the article collapses to de before the noun.",
                "marks": [
                    {"token": "ne ... pas", "role": "negation_frame", "explanation": "wraps the verb"},
                    {"token": "de viande", "role": "negative_quantity", "explanation": "quantity article becomes de"},
                ],
            },
            "agreement": {
                "sentence": "La plupart des etudiants sont arrives.",
                "explanation": "The quantity phrase points to a plural group. The verb and participle therefore follow the plural agreement rather than the singular-looking head word plupart.",
                "marks": [
                    {"token": "La plupart des etudiants", "role": "controller", "explanation": "plural meaning controls agreement"},
                    {"token": "sont arrives", "role": "agreement", "explanation": "verb and participle show plural form"},
                ],
            },
            "determiner": {
                "sentence": "Je n'ai pas de questions.",
                "explanation": "The determiner tells you what kind of quantity the noun phrase has. After pas, an indefinite quantity becomes de before the plural noun.",
                "marks": [
                    {"token": "pas", "role": "negative_trigger", "explanation": "turns the quantity negative"},
                    {"token": "de questions", "role": "determiner_choice", "explanation": "de replaces des in negative quantity"},
                ],
            },
            "pronoun": {
                "sentence": "Je la vois, mais j'en parle.",
                "explanation": "La replaces a direct object, while en replaces a phrase introduced by de. The pronoun choice depends on the function of the original noun phrase.",
                "marks": [
                    {"token": "la", "role": "direct_object_pronoun", "explanation": "replaces a direct object"},
                    {"token": "en", "role": "de_pronoun", "explanation": "replaces de + noun or a quantity"},
                ],
            },
            "relative_clause": {
                "sentence": "C'est le livre dont je parle.",
                "explanation": "Dont links the noun to a second clause where de is missing. It lets the sentence avoid repeating du livre.",
                "marks": [
                    {"token": "le livre", "role": "antecedent", "explanation": "noun being explained"},
                    {"token": "dont", "role": "de_link", "explanation": "stands for de + noun inside the relative clause"},
                ],
            },
            "verb_form": {
                "sentence": "Il faut que tu viennes demain.",
                "explanation": "The trigger il faut que creates a required form slot. The verb after que must match that frame instead of copying the English tense.",
                "marks": [
                    {"token": "Il faut que", "role": "trigger", "explanation": "opens the required verb frame"},
                    {"token": "viennes", "role": "target_form", "explanation": "verb form chosen by the trigger"},
                ],
            },
            "syntax": {
                "sentence": "Ce que je veux, c'est comprendre la phrase.",
                "explanation": "The construction sets up a fronted idea and then names it after c'est. The meaning depends on keeping both halves of the frame.",
                "marks": [
                    {"token": "Ce que je veux", "role": "fronted_clause", "explanation": "announces the idea to define"},
                    {"token": "c'est comprendre", "role": "focus", "explanation": "states the focused result"},
                ],
            },
        }
        return xray_payloads[family]

    def _motif_for(self, concept: GrammarConcept, family: str, display_title: str) -> dict[str, Any]:
        profile_key = infer_grammar_profile(concept).key
        if profile_key == "si_present_result_form":
            motif = self._si_motif()
        elif profile_key == "tense_aspect":
            motif = self._tense_motif()
        elif profile_key == "article_after_negation":
            motif = self._negation_motif()
        else:
            motif = self._family_motif(concept, family, display_title)
        motif["signature"] = self.motif_signature(motif)
        return motif

    def _family_motif(self, concept: GrammarConcept, family: str, display_title: str) -> dict[str, Any]:
        seed = int(hashlib.sha256(f"{concept.external_id or concept.id}:{display_title}".encode("utf-8")).hexdigest()[:8], 16)
        dx = seed % 7
        dy = (seed // 7) % 7
        accent = ["red", "blue", "yellow"][seed % 3]
        label = self._motif_label(display_title, concept)
        family_builders = {
            "agreement": self._agreement_motif,
            "negation": self._negation_family_motif,
            "tense_aspect": self._tense_family_motif,
            "determiner": self._determiner_motif,
            "pronoun": self._pronoun_motif,
            "relative_clause": self._relative_motif,
            "verb_form": self._verb_motif,
            "condition": self._condition_family_motif,
            "syntax": self._syntax_motif,
        }
        return family_builders[family](label, dx, dy, accent, display_title)

    def _motif_label(self, display_title: str, concept: GrammarConcept) -> str:
        candidates = re.findall(r"[A-Za-zÀ-ÿ]+", display_title)
        if not candidates:
            return (concept.level or "GR")[:4].upper()
        if len(candidates) == 1:
            return candidates[0][:4].upper()
        return "".join(word[0] for word in candidates[:4]).upper()[:4]

    def _agreement_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "controller sends agreement marks to the target form",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "controller", "x": 6 + dx, "y": 14 + dy, "w": 28, "h": 18, "fill": "paper", "stroke": "ink", "label": label[:3]},
                {"type": "line", "role": "number_axis", "x1": 12 + dx, "y1": 54, "x2": 70 - dx, "y2": 54, "stroke": "ink", "stroke_width": 2},
                {"type": "circle", "role": "plural_mark", "cx": 26 + dx, "cy": 54, "r": 5, "fill": accent},
                {"type": "circle", "role": "target_mark", "cx": 58 - dx, "cy": 54, "r": 5, "fill": accent, "stroke": "ink"},
                {"type": "arrow", "role": "agreement_link", "from": [34 + dx, 24 + dy], "to": [56 - dx, 47], "stroke": "ink"},
                {"type": "text", "role": "axis_label", "x": 12, "y": 72, "text": "AGR", "fill": "ink"},
            ],
            "accessibility_label": f"{title}: agreement controller links to the target form",
        }

    def _negation_family_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "negation frame encloses the verb and changes the following slot",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "line", "role": "ne_left", "x1": 10 + dx, "y1": 18, "x2": 10 + dx, "y2": 62, "stroke": accent, "stroke_width": 3, "label": "NE"},
                {"type": "line", "role": "pas_right", "x1": 72 - dx, "y1": 18, "x2": 72 - dx, "y2": 62, "stroke": accent, "stroke_width": 3, "label": "PAS"},
                {"type": "rect", "role": "verb_slot", "x": 27, "y": 28 + dy, "w": 28, "h": 18, "fill": "ink", "label": "V", "label_fill": "paper"},
                {"type": "rect", "role": "article_slot", "x": 22 + dx, "y": 64, "w": 18, "h": 12, "fill": "paper", "stroke": "ink", "label": label[:2]},
                {"type": "arrow", "role": "article_shift", "from": [42 + dx, 70], "to": [58, 70], "stroke": "ink"},
                {"type": "circle", "role": "new_form", "cx": 68, "cy": 70, "r": 6, "fill": "blue"},
            ],
            "accessibility_label": f"{title}: negation frame controls the target slot",
        }

    def _tense_family_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "background duration meets a bounded event",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "path", "role": "background_duration", "d": f"M4 {52-dy} Q22 {34+dy} 42 {52-dy} T80 {52-dy}", "fill": "none", "stroke": "blue", "stroke_width": 2},
                {"type": "line", "role": "event_boundary", "x1": 46 + dx, "y1": 14, "x2": 46 + dx, "y2": 74, "stroke": "ink", "stroke_width": 3},
                {"type": "circle", "role": "event_point", "cx": 46 + dx, "cy": 18 + dy, "r": 5, "fill": accent},
                {"type": "rect", "role": "label_block", "x": 8, "y": 62, "w": 24, "h": 12, "fill": "paper", "stroke": "ink", "label": label[:3]},
                {"type": "text", "role": "event_label", "x": 56, "y": 78, "text": "P.C.", "fill": "ink"},
            ],
            "accessibility_label": f"{title}: background line crossed by event point",
        }

    def _determiner_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "determiner gate defines the noun slot",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "determiner_gate", "x": 8 + dx, "y": 28, "w": 24, "h": 24, "fill": accent, "stroke": "ink", "label": label[:3], "label_fill": "paper"},
                {"type": "arrow", "role": "noun_flow", "from": [34 + dx, 40], "to": [52, 40], "stroke": "ink"},
                {"type": "rect", "role": "noun_slot", "x": 54, "y": 30 + dy, "w": 22, "h": 20, "fill": "paper", "stroke": "ink", "label": "N"},
                {"type": "line", "role": "gender_axis", "x1": 14, "y1": 62, "x2": 72, "y2": 62, "stroke": "ink", "stroke_width": 2},
                {"type": "circle", "role": "match_mark", "cx": 26 + dx, "cy": 62, "r": 4, "fill": "blue"},
                {"type": "circle", "role": "number_mark", "cx": 58 - dx, "cy": 62, "r": 4, "fill": accent},
            ],
            "accessibility_label": f"{title}: determiner gate before noun slot",
        }

    def _pronoun_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "noun phrase is replaced by a pronoun in the verb lane",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "noun_phrase", "x": 5 + dx, "y": 18, "w": 30, "h": 18, "fill": "paper", "stroke": "ink", "label": "N"},
                {"type": "arrow", "role": "replacement", "from": [36 + dx, 27], "to": [52, 27 + dy], "stroke": "ink"},
                {"type": "circle", "role": "pronoun", "cx": 62, "cy": 27 + dy, "r": 11, "fill": accent, "label": label[:2], "label_fill": "paper"},
                {"type": "line", "role": "verb_lane", "x1": 12, "y1": 60, "x2": 76, "y2": 60, "stroke": "ink", "stroke_width": 2},
                {"type": "rect", "role": "verb", "x": 44, "y": 51, "w": 22, "h": 18, "fill": "ink", "label": "V", "label_fill": "paper"},
            ],
            "accessibility_label": f"{title}: pronoun replaces a noun phrase before the verb",
        }

    def _relative_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "relative bridge connects antecedent to clause role",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "antecedent", "x": 7 + dx, "y": 42, "w": 26, "h": 18, "fill": "paper", "stroke": "ink", "label": "N"},
                {"type": "path", "role": "bridge", "d": f"M32 {42} C40 {18+dy}, 54 {18+dy}, 62 {42}", "fill": "none", "stroke": accent, "stroke_width": 3},
                {"type": "rect", "role": "relative_pronoun", "x": 36, "y": 26 + dy, "w": 22, "h": 16, "fill": "ink", "label": label[:3], "label_fill": "paper"},
                {"type": "rect", "role": "clause_slot", "x": 62 - dx, "y": 42, "w": 16, "h": 18, "fill": "paper", "stroke": "ink", "label": "CL"},
                {"type": "circle", "role": "missing_role", "cx": 70 - dx, "cy": 66, "r": 5, "fill": "blue"},
            ],
            "accessibility_label": f"{title}: relative bridge from noun to clause",
        }

    def _verb_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "trigger chooses the verb form slot",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "trigger", "x": 7, "y": 22 + dy, "w": 26, "h": 18, "fill": accent, "stroke": "ink", "label": label[:3], "label_fill": "paper"},
                {"type": "arrow", "role": "form_requirement", "from": [35, 31 + dy], "to": [52 + dx, 31], "stroke": "ink"},
                {"type": "rect", "role": "verb_form", "x": 54 + dx, "y": 22, "w": 22, "h": 18, "fill": "ink", "label": "V", "label_fill": "paper"},
                {"type": "line", "role": "sentence_frame", "x1": 10, "y1": 58, "x2": 76, "y2": 58, "stroke": "ink", "stroke_width": 2},
                {"type": "circle", "role": "mood_marker", "cx": 44, "cy": 58, "r": 5, "fill": "blue"},
            ],
            "accessibility_label": f"{title}: trigger points to required verb form",
        }

    def _condition_family_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        motif = self._si_motif()
        motif["primitives"].append({"type": "text", "role": "variant_label", "x": 7 + dx, "y": 76 - dy, "text": label[:4], "fill": accent})
        motif["accessibility_label"] = f"{title}: condition opens a consequence"
        return motif

    def _syntax_motif(self, label: str, dx: int, dy: int, accent: str, title: str) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "clause blocks lock into a fixed sentence frame",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "frame_start", "x": 8 + dx, "y": 18, "w": 24, "h": 18, "fill": "paper", "stroke": "ink", "label": label[:3]},
                {"type": "line", "role": "spine", "x1": 20, "y1": 44, "x2": 72, "y2": 44, "stroke": "ink", "stroke_width": 2},
                {"type": "rect", "role": "clause_one", "x": 24, "y": 52 - dy, "w": 18, "h": 16, "fill": accent, "stroke": "ink"},
                {"type": "rect", "role": "clause_two", "x": 50 + dx, "y": 52 - dy, "w": 18, "h": 16, "fill": "paper", "stroke": "ink"},
                {"type": "arrow", "role": "frame_order", "from": [42, 60 - dy], "to": [50 + dx, 60 - dy], "stroke": "ink"},
                {"type": "circle", "role": "focus_point", "cx": 72 - dx, "cy": 26 + dy, "r": 6, "fill": "blue"},
            ],
            "accessibility_label": f"{title}: fixed sentence frame with ordered clause blocks",
        }

    def _si_motif(self) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "condition opens consequence",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "rect", "role": "condition", "x": 2, "y": 32, "w": 22, "h": 20, "fill": "paper", "stroke": "ink", "label": "SI"},
                {"type": "arrow", "role": "flow", "from": [24, 42], "to": [42, 42], "stroke": "ink"},
                {"type": "rect", "role": "present", "x": 42, "y": 32, "w": 22, "h": 20, "fill": "ink", "label": "PRES", "label_fill": "paper"},
                {"type": "arrow", "role": "result_flow", "from": [64, 42], "to": [82, 42], "stroke": "ink"},
                {"type": "circle", "role": "future_result", "cx": 76, "cy": 20, "r": 4, "fill": "blue"},
            ],
            "accessibility_label": "Si condition in present leads to future or imperative result",
        }

    def _tense_motif(self) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "background line crossed by event point",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "path", "role": "background", "d": "M2 50 Q20 36 40 50 T82 50", "fill": "none", "stroke": "blue", "stroke_width": 2},
                {"type": "line", "role": "event", "x1": 50, "y1": 14, "x2": 50, "y2": 74, "stroke": "ink", "stroke_width": 3},
                {"type": "circle", "role": "event_point", "cx": 50, "cy": 14, "r": 5, "fill": "ink"},
                {"type": "text", "role": "imparfait_label", "x": 6, "y": 68, "text": "IMPF.", "fill": "blue"},
                {"type": "text", "role": "passe_compose_label", "x": 56, "y": 78, "text": "P.C.", "fill": "ink"},
            ],
            "accessibility_label": "Imparfait background wave crossed by a passe compose event marker",
        }

    def _negation_motif(self) -> dict[str, Any]:
        return {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "negation frame changes quantity article",
            "canvas": {"width": 84, "height": 84},
            "primitives": [
                {"type": "text", "role": "verb", "x": 42, "y": 36, "text": "verbe", "fill": "ink", "font": "serif_italic", "size": 20, "align": "middle"},
                {"type": "line", "role": "ne", "x1": 10, "y1": 20, "x2": 74, "y2": 20, "stroke": "red", "stroke_width": 2, "label": "NE"},
                {"type": "line", "role": "pas", "x1": 10, "y1": 50, "x2": 74, "y2": 50, "stroke": "red", "stroke_width": 2, "label": "PAS"},
                {"type": "rect", "role": "article_before", "x": 18, "y": 66, "w": 18, "h": 12, "fill": "ink", "label": "DU", "label_fill": "paper"},
                {"type": "arrow", "role": "article_change", "from": [39, 72], "to": [57, 72], "stroke": "ink"},
                {"type": "rect", "role": "article_after", "x": 58, "y": 66, "w": 18, "h": 12, "fill": "none", "stroke": "ink", "label": "DE"},
            ],
            "accessibility_label": "Ne pas frame changes du to de after negation",
        }

    def _correction_rubric_for(self, concept: GrammarConcept, family: str) -> dict[str, Any]:
        labels = {
            "condition": ["Si clause frame", "Future result", "Imperative result", "Conditional vs future"],
            "tense_aspect": ["Background vs event", "Bounded event", "Ongoing background", "Habit vs single event"],
            "negation": ["Article after negation", "Negation frame", "Etre exception", "Missing de/d'"],
            "agreement": ["Agreement controller", "Number agreement", "Gender agreement", "Nearest noun trap"],
            "determiner": ["Determiner choice", "Quantity article", "Elision", "Specific vs indefinite"],
            "pronoun": ["Pronoun choice", "Pronoun position", "En vs le/la", "Person vs thing"],
            "relative_clause": ["Relative pronoun", "Antecedent link", "Missing de link", "Subject/object role"],
            "verb_form": ["Verb form needed", "Trigger mismatch", "Mood choice", "Infinitive vs finite"],
            "syntax": ["Frame mismatch", "Clause order", "Restriction frame", "Emphasis structure"],
        }[family]
        return {
            "errata_labels": labels,
            "recurring_rules": [
                "Schedule grammar errata when you misuse, omit, or repeatedly confuse the target concept.",
                "Keep lexical mistakes linked to vocabulary as well as the active grammar concept when they block the target form.",
            ],
            "task_compliance_rules": [
                "Show missing target counts in the session, but do not schedule them unless the grammar form is wrong.",
                "Closed drills use deterministic checks before LLM review.",
            ],
            "why_templates": [
                "You used {learner_text}, but this frame needs {target_relation}.",
                "You changed the requested frame; keep {frame} and adjust only {needed_change}.",
            ],
            "repair_templates": [
                "Use {corrected_target}; then re-read the trigger and result relation.",
                "Keep the sentence frame and change only the target form.",
            ],
            "tone": {"address": "you", "avoid_phrases": ["the learner", "the user"]},
        }

    def _detection_hints_for(self, concept: GrammarConcept, family: str, traps: list[str]) -> dict[str, Any]:
        if infer_grammar_profile(concept).key == "si_present_result_form":
            return {
                "positive_patterns": [r"\bsi\s+\w+", r"\b(ai|as|a|ons|ez|ont)\b"],
                "common_wrong_patterns": [r"\bsi\s+\w+(rai|ras|ra|rons|rez|ront)\b", r"\bsi\b.+\b\w+rais\b"],
                "lexical_links": [],
            }
        family_patterns = {
            "condition": ([r"\bsi\s+\w+"], [r"\bsi\s+\w+(rai|ras|ra|rons|rez|ront)\b"]),
            "tense_aspect": ([r"\b\w+ait\b", r"\b(ai|as|a|avons|avez|ont)\s+\w+"], [r"\b\w+ait\s+(hier|puis)\b"]),
            "negation": ([r"\bne\b.+\bpas\b", r"\bpas\s+d['e]\b"], [r"\bpas\s+(du|de la|des|un|une)\b"]),
            "agreement": ([r"\b(sont|ont|font)\b", r"\b(e|s|es)\b"], traps[:3]),
            "determiner": ([r"\b(le|la|les|un|une|des|du|de la|de)\b"], traps[:3]),
            "pronoun": ([r"\b(le|la|les|lui|leur|y|en)\b"], traps[:3]),
            "relative_clause": ([r"\b(qui|que|dont|ou|lequel)\b"], traps[:3]),
            "verb_form": ([r"\bque\s+\w+", r"\b\w+(er|ir|re)\b"], traps[:3]),
            "syntax": ([r"\bce que\b", r"\bc'est\b", r"\bne\b.+\bque\b"], traps[:3]),
        }
        positive, wrong = family_patterns[family]
        return {
            "positive_patterns": positive,
            "common_wrong_patterns": wrong,
            "lexical_links": [],
        }
