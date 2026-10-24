"""Scene guards (#313, #315; root cause #145): one speaker per line, only names the
scene has established, and a decision with at least two answers.

The live walk of 24 Oct 2026 (production, test account A1.1, day 12), in
«L'appartement d'Odile»:

* #313: the speaker row said **Camille**, the text said «Lila : Je demande : combien de
  temps tu restes ?», and after «Pas encore»: Camille, «Lila : Pas encore. D'accord.
  J'aime bien "encore".» The label leaked into the words and Camille spoke for Lila.
* #315: «Decide whether to give Lila a copy of the key.» came with one button.

Exact texts are the ones quoted in the issues. Fake models only: nothing is spent.
"""

from __future__ import annotations

import re

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes
from tests.test_living_story import _scene_context, draft


@pytest.fixture
def offline(monkeypatch):
    """The deterministic matcher reads every reply (no model), no margin correction."""

    from app.services.season import runtime

    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield
    runtime._ROUTE_CACHE.clear()


CAMILLE = {"id": "camille_marchand", "name": "Camille Marchand"}
LILA = {"id": "lila_bonnet", "name": "Lila Bonnet"}

LEAKED_QUESTION = "Lila : Je demande : combien de temps tu restes ?"
LEAKED_ENCORE = 'Lila : Pas encore. D\'accord. J\'aime bien "encore".'


def _payload(learner_text: str, *, speaker: str = "camille_marchand", history=None, opening: str = "Tu restes combien de temps ?") -> dict:
    return {
        "story": {
            "level": "B1",
            "learner": {"address": "neutral"},
            "commitments": [],
            "world": {"cast": [CAMILLE, LILA], "locations": [{"id": "odile_flat", "name_fr": "L'appartement d'Odile"}]},
        },
        "scene": {"character_id": speaker, "opening_line_fr": opening, "panels": []},
        "learner_text": learner_text,
        "history": history or [],
        "targets": [],
        "turn_plan": {},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="The learner answers.", needs_clarification=False)


# ---------------------------------------------------------------------------
# #313: the label is the UI's, never part of the line
# ---------------------------------------------------------------------------


def test_a_reply_that_speaks_for_another_character_is_refused_with_the_reason():
    """«Lila : Je demande : combien de temps tu restes ?» said by Camille."""

    voice = _voice(LEAKED_QUESTION)
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(voice, _payload("Trois jours, pour la clé de Lila."))
    assert str(caught.value) == "reply_speaks_for_other"
    assert "Lila" in caught.value.feedback


def test_the_speakers_own_label_never_reaches_the_learner():
    voice = _voice("Camille : Trois jours, d'accord. Et la clé ?")
    lanes.validate_voice(voice, _payload("Trois jours, pour la clé de Lila."))
    assert voice.reply_fr == "Trois jours, d'accord. Et la clé ?"


def test_a_colon_that_is_not_a_speaker_label_is_left_alone():
    voice = _voice("Attention : trois jours, c'est court. Et la clé ?")
    lanes.validate_voice(voice, _payload("Trois jours, pour la clé de Lila."))
    assert voice.reply_fr.startswith("Attention : trois jours")


def test_a_scene_page_never_gives_a_character_a_line_labelled_with_someone_else():
    context = _scene_context()
    proposal = engine.SceneDraft.model_validate(draft(context, 0))
    proposal.panels[1].dialogue[0].text_fr = "Lila : Vous avez une idée ?"
    with pytest.raises(engine.StoryUnavailable) as caught:
        engine._validate_scene(proposal, context)
    assert str(caught.value) == "dialogue_speaks_for_other"


def test_a_scene_page_strips_the_speakers_own_label():
    context = _scene_context()
    proposal = engine.SceneDraft.model_validate(draft(context, 0))
    proposal.panels[1].dialogue[0].text_fr = "Romy : Vous avez une idée ?"
    engine._validate_scene(proposal, context)
    assert proposal.panels[1].dialogue[0].text_fr == "Vous avez une idée ?"


def test_an_acknowledgement_never_carries_a_speaker_label():
    from app.services.season.turns import clean_ack

    assert clean_ack(LEAKED_ENCORE, learner_text="Pas encore.", address="tu") is None
    assert clean_ack("Merci, Vincent. Bienvenue.", learner_text="Je m'appelle Vincent.", address="tu")


def test_a_reply_read_from_the_page_is_drawn_without_labels(offline):
    """The reply to «Pas encore» is Lila's line under Camille's header; it is drawn
    under Lila from ``reply_lines``, so the words themselves carry no «Lila :»."""

    from app.services.season import runtime
    from tests.test_season_story_qa import _page, _record, _say, _scenario

    page = _page("t2", "b", band="A1", language="en")
    scenario = _scenario(page)
    scenario.character_id = "camille_marchand"
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    index = next(i for i, turn in enumerate(turns) if str(turn["id"]).startswith("b.key"))
    history: list[dict] = []
    for exchange in range(index):
        text = str(turns[exchange]["replies"][0]["examples"][0])
        played = _say(scenario, text, history, exchange)
        assert not re.search(r"^\w+ : ", played.character_reply_fr, re.MULTILINE), played.character_reply_fr
        _record(history, text, played)
    evaluation = _say(scenario, "Pas encore", history, index)
    assert evaluation.route["reply"] == "pas_encore"
    assert [line["speaker_id"] for line in evaluation.reply_lines] == ["lila_bonnet"]
    assert "Lila :" not in evaluation.character_reply_fr, evaluation.character_reply_fr
    assert evaluation.character_reply_fr == evaluation.reply_lines[0]["text_fr"]


# ---------------------------------------------------------------------------
# #315: a name the scene never established
# ---------------------------------------------------------------------------


def test_a_titled_person_nobody_introduced_is_refused():
    """Lila's «M. M. … Marchand ?» pattern: a person the thread never named."""

    voice = _voice("Ah, M. Delmas a la clé ? Trois jours, d'accord.")
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(voice, _payload("Trois jours, pour la clé de Lila."))
    assert str(caught.value) == "reply_unintroduced_person"
    assert "Delmas" in caught.value.feedback


def test_a_person_the_cast_the_learner_or_the_thread_named_is_fine():
    payload = _payload("Trois jours. Je vois Mme Diallo demain.", history=[{"learner": "Salut", "character": "Bonjour, je suis avec Bastien."}])
    voice = _voice("Mme Diallo, très bien. Bastien sera là. Lila aussi.")
    lanes.validate_voice(voice, payload)


def test_a_bare_name_nobody_introduced_is_refused_once_then_served():
    voice = _voice("Trois jours, d'accord. Et Fabrice ? Il vient aussi.")
    with pytest.raises(engine.SoftRejection) as caught:
        lanes.validate_voice(voice, _payload("Trois jours, pour la clé de Lila."))
    assert str(caught.value) == "reply_unintroduced_person"


# ---------------------------------------------------------------------------
# #315: a decision has at least two answers
# ---------------------------------------------------------------------------


def _solve(options):
    return {
        "kind": "solve",
        "id": "b.key",
        "mechanic": "choix",
        "to": "lila_bonnet",
        "prompt": {"text_fr": "Tu me prêtes une clé ?", "text_native": None},
        "task_native": "Decide whether to give Lila a copy of the key.",
        "options": options,
        "default": options[0]["id"] if options else None,
    }


def _option(option_id, label):
    return {"id": option_id, "label": {"text_fr": label, "text_native": None}, "sets": {}, "sets_if": [], "beats": []}


def test_a_decision_with_one_option_offers_no_cards_so_the_text_field_shows():
    from app.services.season.page import choice_cards, solve_as_turn

    one = solve_as_turn(_solve([_option("pas_encore", "Pas encore")]))
    assert choice_cards(one) == [], "one button is not a decision"
    two = solve_as_turn(_solve([_option("double", "Lui faire un double"), _option("pas_encore", "Pas encore")]))
    assert [card["id"] for card in choice_cards(two)] == ["double", "pas_encore"]


def test_a_re_read_decision_keeps_the_learners_branch_without_a_lone_button():
    """The walk's one button: a lost day re-reads «L'appartement d'Odile» with the
    learner's own branch of the key decision («Pas encore») and nothing else."""

    from app.services.season.page import choice_cards
    from app.services.season.reprise import pinned_turns
    from app.services.season.runtime import projected_turns
    from tests.test_season_story_qa import _page

    page = _page("t2", "b", band="A1", language="en")
    routing = [{"turn_id": "b.key", "reply_id": "pas_encore"}]
    turns = pinned_turns(projected_turns(page), routing, {})
    key = next(turn for turn in turns if str(turn["id"]).startswith("b.key"))
    assert [reply["id"] for reply in key["replies"]] == ["pas_encore"]
    assert choice_cards(key) == [], "one button is not a decision: the free-text field shows"


def test_a_decision_left_with_one_option_is_not_posed():
    from app.services.season.page import posed_choice

    assert not posed_choice(_solve([_option("pas_encore", "Pas encore")]))
    assert posed_choice(_solve([_option("double", "Lui faire un double"), _option("pas_encore", "Pas encore")]))


def test_no_posed_decision_of_the_season_shows_a_single_button():
    """T7's «Décide ce qu'il advient de l'appartement» keeps one option when the flags
    leave only the story's default: that is not a decision to pose, it is settled."""

    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import choice_cards, resolve_day
    from app.services.season.runtime import projected_turns

    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    posed = 0
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            for band in ("A1", "A2", "B1"):
                page = resolve_day(season, tentpole.id, day.day, flags=flags, band=band, language="en")
                for turn in projected_turns(page):
                    if not turn.get("choice"):
                        continue
                    posed += 1
                    cards = choice_cards(turn)
                    assert len(cards) != 1, (tentpole.id, day.day, band, turn["id"], cards)
    assert posed
