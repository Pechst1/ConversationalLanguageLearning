"""#398 (live walk 31 Oct, day 19, A1.1): a sentence cut at «M.» was a drill's option.

«Which sentence uses today's rule?» offered «Sur le toit, la lampe de M.»: the scene was
cut into sentences on every full stop, and a title's full stop ends no sentence. The
same cut gave the season lexicon «Sur le seuil, M.» and «L'émissaire de M.» as the
sentences of their words. Every cut of a French text now shares one list of titles and
initials (``app.services.sentence_line``); what is left of a sentence cut at one, or a
signature («— M.»), is no sentence a drill may pose.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items, scene_items, season_lexicon
from app.services import journey_planner as planner
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.sentence_line import ends_sentence, sentences, stops_at_title
from tests.test_journey_planner import _brief

SCENE = "Sur le toit, la lampe de M. Marchand brille. Il ne dort pas. Mme. Odile ne pleure pas."
WHOLE = "Sur le toit, la lampe de M. Marchand brille."
#: An option that ends in a one-letter abbreviation (the done-when's shape).
ONE_LETTER_END = re.compile(r"(?:^|[\s(«\"“'’])[A-ZÀ-ÖØ-Þ]\.[\s»\"”)]*$")
#: A sentence that runs on into a lone «…» («Maman ? …»): the start of the next one.
RUNS_ON = re.compile(r"[.!?]\s+…\s*$")


def test_the_scene_cut_keeps_a_title_inside_its_sentence() -> None:
    assert planner.scene_sentences(SCENE) == [WHOLE, "Il ne dort pas.", "Mme. Odile ne pleure pas."]
    assert sentences(SCENE) == [WHOLE, "Il ne dort pas.", "Mme. Odile ne pleure pas."]


@pytest.mark.parametrize("title", ["M.", "MM.", "Mme.", "Mlle.", "Dr.", "Pr.", "Me.", "St.", "Ste.", "J.", "É."])
def test_a_title_or_an_initial_ends_no_sentence(title: str) -> None:
    text = f"Voici {title} Dupont. Il part."
    assert planner.scene_sentences(text) == [f"Voici {title} Dupont.", "Il part."]
    assert sentences(text) == [f"Voici {title} Dupont.", "Il part."]


def test_a_real_sentence_end_still_ends_one() -> None:
    for word in ("brille.", "brille!", "?", "pas?", "pas…", "«brille.»", "dort.", "Marchand."):
        assert ends_sentence(word), word
    for word in ("M.", "Mme.", "J.", "«M.", "brille,", "Marchand"):
        assert not ends_sentence(word), word
    assert planner.scene_sentences("Il pleut. Tu entres. On y va ?") == ["Il pleut.", "Tu entres.", "On y va ?"]


def test_a_sentence_cut_at_its_title_or_a_signature_is_no_sentence() -> None:
    assert stops_at_title("Sur le toit, la lampe de M.")
    assert stops_at_title("— M.")
    assert not stops_at_title(WHOLE)
    assert not stops_at_title("Tu connais un certain L. ?")
    assert not stops_at_title("Elle s'appelle Emma.")
    # A stored line already cut («… de M.») and a signature are not offered as sentences.
    assert planner.scene_sentences("Sur le toit, la lampe de M.", "Il ne dort pas.") == ["Il ne dort pas."]
    assert planner.scene_sentences("Elle est grande. — M.") == ["Elle est grande."]


def test_a_scene_word_is_taught_in_its_whole_sentence() -> None:
    entry = {"surface_fr": "lampe", "line_ref": "opening"}
    assert scene_items.sentence_of({"opening_line_fr": SCENE}, entry) == WHOLE
    assert season_lexicon._sentence_with(SCENE, "lampe") == WHOLE
    # The old cut is kept otherwise: after «?» a new piece starts, capital or not.
    assert season_lexicon._sentence_with("Maman ? … Viens.", "Maman") == "Maman ?"


def test_no_season_word_is_taught_in_a_sentence_cut_at_a_title() -> None:
    """The generated lexicon (``app/data/season/s1/lexicon.json``) holds whole sentences:
    none cut at a title, ending on an initial or a signature («Elle est grande. — M.»),
    or running on into the next one («Maman ? …»)."""

    cut = []
    for rows in season_lexicon.load("s1")["days"].values():
        for level_rows in rows.values():
            for row in level_rows or []:
                sentence = str(row.get("sentence_fr") or "")
                if sentence and (stops_at_title(sentence) or ONE_LETTER_END.search(sentence) or RUNS_ON.search(sentence)):
                    cut.append(sentence)
    assert not cut, sorted(set(cut))


def _negation(db: Session) -> dict:
    FrenchCoreGrammarCatalog(db, "v1").ensure_catalog()
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A1_NEG_001").one()
    return concept_life.concept_brief(db, concept, control_language="en")


def test_the_rule_drill_never_offers_a_sentence_cut_at_a_title(db_session: Session) -> None:
    brief = _negation(db_session)
    task = grammar_items.recognise_item(brief, sentences=planner.scene_sentences(SCENE), language="en")
    assert task is not None and task.options
    texts = [option["text_fr"] for option in task.options]
    assert all(not ONE_LETTER_END.search(text) for text in texts), texts
    assert "Sur le toit, la lampe de M." not in texts


def test_no_choice_option_of_a_generated_day_ends_in_a_one_letter_abbreviation(db_session: Session) -> None:
    """The done-when, over a whole planned day: a scene with «M. Marchand» in it, and today's rule."""

    scenario = replace(
        _brief(),
        setup_fr="Il pleut sur le canal. Sur le toit, la lampe de M. Marchand brille. Margaux essuie le zinc.",
        opening_line_fr="Tiens, bonjour ! Mme. Odile ne vient pas ce soir ?",
    )
    plan = planner.plan_journey(scenario=scenario, candidates=[], practice=True, introduction=_negation(db_session))
    options = [
        str(option.get("text_fr") or "")
        for step in plan.steps
        for option in (getattr(step.private_task, "options", None) or [])
        if isinstance(option, dict)
    ]
    assert options, "the day poses no choice at all: the check would be vacuous"
    # The rule's «Which sentence uses today's rule?» is posed from this scene, whole sentences.
    assert WHOLE in options, options
    bad = [text for text in options if ONE_LETTER_END.search(text) or stops_at_title(text)]
    assert not bad, bad
