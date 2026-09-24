"""The «Règle» step, 2026-09-24 walkthrough regressions (WP-L4).

1. The card's headline: a scene line replaced the authored example of
   FR_A1_NOUN_001 because the borrowed un/une detector matched «un peu» in
   «Je dois bosser encore un peu.» — an adverb, not a noun phrase — and the
   card lost its speaker and its translation.
2. The first guided item asked «Which sentence uses this rule: Gender and number
   basics?» (the English catalogue title) with three sentences that all hold
   nouns, expecting the «un peu» one.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items
from app.services import journey_planner as planner
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from tests.test_journey_planner import _brief

ROMY_LINE = "Je dois bosser encore un peu."
WALKTHROUGH_SCENE = ["Le Mistral est presque vide.", "Je pense partir.", ROMY_LINE]

#: The A1 units whose form is a noun phrase, per catalogue.
NOUN_PHRASE_UNITS = {
    "v1": ["FR_A1_NOUN_001", "FR_A1_ART_001", "FR_A1_ART_002", "FR_A1_DET_001", "FR_A1_DET_002", "FR_A1_ADJ_001"],
    "v2": ["FR2_A11_UN_UNE", "FR2_A11_LE_LA", "FR2_A11_POSSESSIVES", "FR2_A12_DEMONSTRATIVES", "FR2_A11_ADJ_AGREEMENT"],
}


def _unit(db: Session, external_id: str, *, language: str = "en") -> dict:
    version = "v2" if external_id.startswith("FR2_") else "v1"
    FrenchCoreGrammarCatalog(db, version).ensure_catalog()
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()
    return concept_life.concept_brief(db, concept, control_language=language)


# ---------------------------------------------------------------------------
# Bug 1 — the headline
# ---------------------------------------------------------------------------


def test_un_peu_is_not_a_noun_phrase(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    assert brief["noun_phrase"] is True
    assert grammar_items.detector_span(brief["detectors"], ROMY_LINE) is None
    assert grammar_items.rule_span(brief, ROMY_LINE) is None
    for adverbial in ("Attends une fois.", "Je reviens un jour.", "Il reste un moment."):
        assert grammar_items.rule_span(brief, adverbial) is None, adverbial
    assert grammar_items.rule_span(brief, "Je voudrais un café.") is not None


def test_the_walkthrough_line_never_becomes_the_headline(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    speakers = {grammar_items._fold(ROMY_LINE): "romy_tremblay"}
    card = grammar_items.scene_rule_card(brief, WALKTHROUGH_SCENE, speakers=speakers)

    assert card is not None and not card.get("from_scene")
    assert "bosser" not in card["example"]["fr"]
    # The authored card keeps its face and its translation.
    assert card["speaker"] == "margaux_barman"
    assert card["example"]["tr"]["en"]


def test_a_real_noun_phrase_said_by_a_character_is_the_headline(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    line = "Je prends une petite table."
    card = grammar_items.scene_rule_card(
        brief, [*WALKTHROUGH_SCENE, line], speakers={grammar_items._fold(line): "romy_tremblay"}
    )
    assert card["from_scene"] is True
    assert card["speaker"] == "romy_tremblay"
    assert card["example"] == {"fr": "Je prends [une petite] table."}, "no translation of another sentence"


def test_narration_never_takes_the_authored_speaker_away(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    card = grammar_items.scene_rule_card(brief, ["Il y a une petite table."], speakers={})
    assert not card.get("from_scene")
    assert card["speaker"] == "margaux_barman"


def test_a_scene_marks_whole_words() -> None:
    brief = {"detectors": [r"\bl'[aeiouhé]"], "noun_phrase": True, "rule_card": {"example": {"fr": "x"}}}
    card = grammar_items.scene_rule_card(brief, ["Je cherche l'école."])
    assert card["example"]["fr"] == "Je cherche [l'école]."


def test_the_planner_passes_the_speaker_of_a_scene_line(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    scenario = replace(
        _brief(),
        story_context={"draft": {"panels": [{"dialogue": [
            {"character_id": "romy_tremblay", "text_fr": f"Salut. {ROMY_LINE}"},
            {"character_id": "romy_tremblay", "text_fr": "Je garde une petite table."},
        ]}]}},
    )
    speakers = planner.scene_speakers(scenario)
    assert speakers[grammar_items._fold(ROMY_LINE)] == "romy_tremblay"
    card, _cost, _items = planner._introduction_items(
        brief, scenario=scenario, sentences=[ROMY_LINE, "Je garde une petite table."], spt=1.0, multiplier=1.0
    )
    assert card is not None
    assert card["speaker"] == "romy_tremblay"
    assert card["example"]["fr"] == "Je garde [une petite] table."


# ---------------------------------------------------------------------------
# Bug 2 — the recognise item
# ---------------------------------------------------------------------------


def test_the_walkthrough_line_is_never_the_recognise_answer(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    items = grammar_items.guided_items(brief, sentences=WALKTHROUGH_SCENE, language="en")
    assert items
    for task in items:
        assert grammar_items._fold(ROMY_LINE) not in {grammar_items._fold(a) for a in task.accepted_answers}
    recognise = [task for task in items if task.instruction_native == grammar_items._RECOGNISE["en"]]
    for task in recognise:
        texts = [option["text_fr"] for option in task.options]
        assert ROMY_LINE not in texts, "an adverbial «un peu» is ambiguous: never an option"
        assert "Le Mistral est presque vide." not in texts, "a noun phrase is never a distractor"


def test_the_prompt_names_no_catalogue_title(db_session: Session) -> None:
    for language in ("en", "de", "fr"):
        brief = _unit(db_session, "FR_A1_NOUN_001", language=language)
        task = grammar_items.recognise_item(
            brief, sentences=["Je pense partir.", "Tu viens ?"], language=language
        )
        assert task is not None
        assert "Gender and number" not in task.instruction_native
        assert brief["title_native"] not in task.instruction_native
        assert task.instruction_native == grammar_items._RECOGNISE[language]
        # The one-line rule stays behind «La règle», in the learner's language.
        assert task.hint_native == brief["rule_card"]["rule"].get(language, brief["rule_card"]["rule"]["en"])


def test_no_unambiguous_recognise_means_the_essai_starts_with_choose(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    scene = ["Le Mistral est presque vide.", "La porte est ouverte.", ROMY_LINE]
    assert grammar_items.recognise_item(brief, sentences=scene, language="en") is None
    first = grammar_items.guided_items(brief, sentences=scene, language="en")[0]
    assert first.task_type == "choice"
    assert {option["text_fr"] for option in first.options} == {"une petite table", "une petit table"}
    assert first.solution_fr == "une petite table"


@pytest.mark.parametrize(
    "external_id", [unit for units in NOUN_PHRASE_UNITS.values() for unit in units]
)
def test_a_recognise_item_has_exactly_one_option_that_uses_the_rule(db_session: Session, external_id: str) -> None:
    brief = _unit(db_session, external_id)
    scene = [
        *WALKTHROUGH_SCENE,
        "Tu pousses la porte du Mistral.",
        "Je voudrais un café.",
        "Il pleut.",
        "Je reviens une fois.",
        "On y va ?",
        "Ma sœur arrive.",
        "Cette table est libre.",
    ]
    task = grammar_items.recognise_item(brief, sentences=scene, language="en")
    if task is None:
        return  # dropped rather than ambiguous
    hits = [o["text_fr"] for o in task.options if grammar_items.mentions_rule(brief, o["text_fr"])]
    assert hits == [task.solution_fr], (external_id, [o["text_fr"] for o in task.options])
    assert grammar_items.rule_span(brief, task.solution_fr) is not None
    assert grammar_items._fold(task.solution_fr) != grammar_items._fold(ROMY_LINE)
