"""WP-93 — a realistic story-engine brief for planner tests and the WP-L9 harness.

A five-panel A1 page, as the story engine writes it (``SceneDraft``): narration
and cast lines, a validated lexicon, the «mots à placer» and recycled words the
director was handed, and a line carrying ``grammar_marks`` (WP-92). Pure data:
no session, no provider.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.services.journey_contracts import ResponseTask, ScenarioBrief

#: The day's new unit, as ``grammar_units.unit_brief`` shapes it (trimmed).
PASSE_COMPOSE_ID = 4242


def engine_draft(**overrides: Any) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "title_fr": "La clé oubliée",
        "premise_fr": "Il pleut. Au Mistral, Lila cherche sa clé partout.",
        "setup_native": "It is raining. At Le Mistral, Lila is looking everywhere for her key.",
        "objective_native": "Tell Lila where you saw her key.",
        "character_id": "lila_bonnet",
        "location_id": "le_mistral",
        "panels": [
            {
                "narration_fr": "Il pleut sur le canal. Le Mistral est plein ce soir.",
                "dialogue": [],
                "visual_direction": "Wide shot of the café in the rain.",
            },
            {
                "narration_fr": "Lila vide son sac sur la table.",
                "dialogue": [
                    {"character_id": "lila_bonnet", "text_fr": "Ma clé ! J'ai perdu ma clé !"},
                    {"character_id": "marin_leveque", "text_fr": "Encore ? Tu as regardé dans ta poche ?"},
                ],
                "visual_direction": "Lila empties her bag.",
            },
            {
                "narration_fr": "Margaux essuie un verre et sourit.",
                "dialogue": [
                    {
                        "character_id": "margaux_barman",
                        "text_fr": "Hier, tu as laissé ton parapluie ici.",
                        "grammar_marks": [{"unit_id": str(PASSE_COMPOSE_ID), "start": 6, "end": 18}],
                    },
                ],
                "visual_direction": "Margaux at the counter.",
            },
            {
                "narration_fr": "Marin cherche sous la chaise.",
                "dialogue": [
                    {"character_id": "marin_leveque", "text_fr": "Pas de clé ici. Juste un croissant."},
                ],
                "visual_direction": "Marin under the chair.",
            },
            {
                "narration_fr": "Lila se tourne vers vous.",
                "dialogue": [
                    {"character_id": "lila_bonnet", "text_fr": "Vous avez vu ma clé, peut-être ?"},
                ],
                "visual_direction": "Lila turns to the learner.",
            },
        ],
        "opening_line_fr": "Vous avez vu ma clé, peut-être ?",
        "lexicon": [
            {"surface_fr": "la clé", "lemma": "clé", "gloss_native": "the key",
             "part_of_speech": "noun", "gender": "f", "line_ref": "panel:1:line:0"},
            {"surface_fr": "le sac", "lemma": "sac", "gloss_native": "the bag",
             "part_of_speech": "noun", "gender": "m", "line_ref": "panel:1:narration"},
            {"surface_fr": "la poche", "lemma": "poche", "gloss_native": "the pocket",
             "part_of_speech": "noun", "gender": "f", "line_ref": "panel:1:line:1"},
            {"surface_fr": "le parapluie", "lemma": "parapluie", "gloss_native": "the umbrella",
             "part_of_speech": "noun", "gender": "m", "line_ref": "panel:2:line:0"},
            {"surface_fr": "la chaise", "lemma": "chaise", "gloss_native": "the chair",
             "part_of_speech": "noun", "gender": "f", "line_ref": "panel:3:narration"},
        ],
        "placed_lemmas": ["clé", "poche", "sac", "chaise", "chercher"],
        "recycled_lemmas": ["parapluie", "croissant", "pluie", "verre"],
    }
    draft.update(overrides)
    return draft


def engine_brief(**overrides: Any) -> ScenarioBrief:
    draft = overrides.pop("draft", None) or engine_draft()
    task = ResponseTask(
        objective_native=draft["objective_native"],
        character_id="lila_bonnet",
        character_name="Lila",
        opening_line_fr=draft["opening_line_fr"],
        max_turns=4,
        repair_allowed=True,
        targets=[],
        required_intents=["say_where_the_key_is"],
        optional_intents=[],
        allowed_outcomes=[],
        rubric_native="Met: the learner tells Lila where the key is.",
        suggested_response_fr="Oui, votre clé est sous la chaise.",
        hint_native="Say where you saw it: « sous… », « sur… ».",
        translation_native="Yes, your key is under the chair.",
        estimated_seconds=120,
    )
    base: dict[str, Any] = {
        "scenario_key": "engine:la-cle-oubliee",
        "content_version": "story-engine-v1",
        "title_fr": draft["title_fr"],
        "objective_key": "engine.objective",
        "objective_native": draft["objective_native"],
        "level_band": "A1",
        "character_id": "lila_bonnet",
        "character_name": "Lila",
        "location_id": "le_mistral",
        "location_name": "Le Mistral",
        "image_url": "/assets/serial/locations/le_mistral-counter.webp",
        "setup_fr": draft["premise_fr"],
        "setup_native": draft["setup_native"],
        "opening_line_fr": draft["opening_line_fr"],
        "response_task": task,
        "story_context": {
            "draft": draft,
            "source": {
                "world": {
                    "cast": [
                        {"id": "lila_bonnet", "name": "Lila"},
                        {"id": "marin_leveque", "name": "Marin"},
                        {"id": "margaux_barman", "name": "Margaux"},
                    ]
                }
            },
        },
        "control_language": "en",
    }
    base.update(overrides)
    return ScenarioBrief(**base)


def without_page(brief: ScenarioBrief) -> ScenarioBrief:
    draft = dict(brief.story_context["draft"])
    draft["panels"] = []
    return replace(brief, story_context={**brief.story_context, "draft": draft})
