"""Live walk, 17-18 Oct 2026: the scene record (#194) and the closing panel (#212).

* #194 — Nº 5 and Nº 6 were both «Une habitude au zinc»; the pre-scene header read
  «Votre appartement» while every other word the app says to the learner is «tu».
  The director's scene title was checked against nothing: not against the earlier
  scenes' titles (``recent_situations`` never kept them), and the place names the
  header prints were not in the app's own register.
* #212 — the closing panel and the scene-finished card had Lila say «pour voir Lila»
  (herself, third person) and called her «a little cross» after «D'accord, je ne te
  force pas». The ending was never checked against who is speaking, and the mood
  label was the model's word with no check against what the character said.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes
from tests.test_living_story import (  # noqa: F401  (fixtures)
    LOCATIONS,
    _scene_context,
    assembled_client,
    clock,
    draft,
    driver,
    journey_enabled,
    one_exchange,
    provider,
)

LEARNER_1 = "Je reste à Paris parce que je veux voir ma amie Lila et le boulangerie de ma grand-mère."
LEARNER_2 = "Non, Lila. Je ne veux pas parler à l'agent. Mais regarde, il y a un chien … avec un chapeau !"


def _lila_payload(learner_text: str = LEARNER_2) -> dict:
    return {
        "learner_text": learner_text,
        "history": [{"learner": LEARNER_1, "character": "Tu restes pour la boulangerie ?"}],
        "scene": {"character_id": "lila_bonnet", "opening_line_fr": "Tu as parlé à l'agent ?"},
        "story": {
            "learner": {"address": "neutral"},
            "level": "A2",
            "commitments": [],
            "world": {
                "cast": [
                    {"id": "lila_bonnet", "name": "Lila Bonnet"},
                    {"id": "marin_leveque", "name": "Marin Lévêque"},
                ]
            },
        },
        "targets": [],
        "turn_plan": {},
    }


def _closing_turn(**overrides) -> engine.SemanticTurn:
    base = {
        "outcome": "not_yet",
        "understood_intent": "The learner declines to talk to the airline and points at a dog.",
        "evidence_quotes": [],
        "reply_fr": "D'accord, je ne te force pas. Je sais que tu restes pour voir Lila et la boulangerie.",
        "needs_clarification": False,
        "resolution_fr": "Tu veux rester à Paris pour voir Lila et la boulangerie de ta grand-mère.",
        "summary_native": "Lila lets it go and looks at the dog with you.",
        "callback_fr": "Lila a laissé tomber l'agent.",
        "feeling_shift": "colder",
    }
    return engine.SemanticTurn.model_validate({**base, **overrides})


# ---------------------------------------------------------------------------
# #212 · nobody names themselves
# ---------------------------------------------------------------------------


def test_the_closing_panel_never_has_lila_say_lila():
    """The exact exchange of the walk: Lila answers «pour voir Lila»."""

    turn = _closing_turn(resolution_fr="Je comprends. À demain.")
    with pytest.raises(engine.StoryUnavailable, match="speaker_names_self") as refused:
        engine._validate_turn(turn, _lila_payload())
    assert "Lila" in refused.value.hint and "moi" in refused.value.hint


def test_the_scene_finished_card_never_has_lila_say_lila():
    turn = _closing_turn(reply_fr="D'accord, je ne te force pas.")
    # The reply was already shown: only the ending is judged again on the story lane.
    with pytest.raises(engine.StoryUnavailable, match="speaker_names_self"):
        lanes.validate_story(turn, _lila_payload())


def test_the_voice_lane_refuses_the_same_reply():
    voice = lanes.VoiceReply(
        reply_fr="Je sais que tu restes pour voir Lila et la boulangerie.",
        understood_intent="The learner stays in Paris for a friend and the bakery.",
        needs_clarification=False,
    )
    with pytest.raises(engine.StoryUnavailable, match="speaker_names_self"):
        lanes.validate_voice(voice, _lila_payload(LEARNER_1))


@pytest.mark.parametrize(
    "line",
    [
        "Je sais que tu restes pour me voir, moi et la boulangerie.",
        "Moi, c'est Lila. On se tutoie ?",
        "Je suis Lila, la colocataire de Marin.",
        "Tu restes pour Marin et la boulangerie ?",
    ],
)
def test_an_introduction_or_another_name_is_fine(line):
    turn = _closing_turn(reply_fr=line, resolution_fr="À demain, alors.", feeling_shift="steady")
    engine._validate_turn(turn, _lila_payload())


def test_a_character_may_name_the_learner_and_the_others():
    turn = _closing_turn(
        reply_fr="Marin dit que tu restes.", resolution_fr="Lucas, on se voit demain.", feeling_shift="steady"
    )
    engine._validate_turn(turn, _lila_payload())


# ---------------------------------------------------------------------------
# #212 · the mood label follows the last exchange
# ---------------------------------------------------------------------------


def test_a_character_who_lets_it_go_is_not_cross():
    turn = _closing_turn(
        reply_fr="D'accord, je ne te force pas. Regarde ce chien !",
        resolution_fr="Ça va, on le laisse tranquille. À demain.",
    )
    assert turn.feeling_shift == "colder"
    engine._validate_turn(turn, _lila_payload())
    assert turn.feeling_shift == "steady"


def test_the_voice_lane_does_not_keep_cross_after_dautord():
    voice = lanes.VoiceReply(
        reply_fr="D'accord, je ne te force pas.",
        understood_intent="The learner declines to talk to the agent.",
        needs_clarification=False,
        feeling_shift="colder",
    )
    lanes.validate_voice(voice, _lila_payload())
    assert voice.feeling_shift == "steady"


@pytest.mark.parametrize(
    "reply",
    [
        "D'accord. Mais franchement, tant pis pour toi.",
        "Tu aurais pu me le dire avant. Je suis vexée.",
        "Non. Je ne suis pas contente du tout.",
    ],
)
def test_a_character_who_is_really_cold_stays_cold(reply):
    turn = _closing_turn(reply_fr=reply, resolution_fr="Bon. À demain.")
    engine._validate_turn(turn, _lila_payload())
    assert turn.feeling_shift == "colder"


# ---------------------------------------------------------------------------
# #194 · a scene has its own title
# ---------------------------------------------------------------------------


def _titled(title: str, n: int = 0) -> engine.SceneDraft:
    context = _scene_context()
    return engine.SceneDraft.model_validate({**draft(context, n), "title_fr": title})


def test_a_scene_title_that_an_earlier_scene_already_wears_is_not_served_twice():
    earlier = {"novelty_key": "other", "premise_fr": "Le facteur a livré un colis.", "title_fr": "Une habitude au zinc"}
    proposal = _titled("Une habitude au zinc")
    with pytest.raises(engine.SoftRejection, match="repeated_scene_title") as refused:
        engine._validate_scene(proposal, _scene_context(recent_situations=[earlier]))
    # The one retry is told which title is taken; if it repeats, the repaired one is served.
    assert "Une habitude au zinc" in refused.value.hint
    served = refused.value.proposal
    assert served.title_fr != "Une habitude au zinc"
    assert served.title_fr.startswith("Une habitude au zinc")


def test_a_taken_title_is_compared_without_case_or_punctuation():
    earlier = {"novelty_key": "other", "premise_fr": "Le facteur a livré un colis.", "title_fr": "La même chose ?"}
    with pytest.raises(engine.SoftRejection, match="repeated_scene_title"):
        engine._validate_scene(_titled("la même chose"), _scene_context(recent_situations=[earlier]))


def test_a_repaired_title_never_collides_with_a_repaired_one():
    taken = [
        {"novelty_key": "a", "premise_fr": "Un colis.", "title_fr": "Une habitude au zinc"},
        {"novelty_key": "b", "premise_fr": "Un chat.", "title_fr": "Une habitude au zinc, II"},
    ]
    with pytest.raises(engine.SoftRejection) as refused:
        engine._validate_scene(_titled("Une habitude au zinc"), _scene_context(recent_situations=taken))
    assert refused.value.proposal.title_fr == "Une habitude au zinc, III"


def test_a_new_title_and_scenes_without_stored_titles_pass():
    legacy = [{"novelty_key": "old", "premise_fr": "Le facteur a livré un colis."}]
    engine._validate_scene(_titled("Une habitude au zinc"), _scene_context(recent_situations=legacy))
    titled = [{"novelty_key": "old", "premise_fr": "Le facteur a livré un colis.", "title_fr": "La même chose ?"}]
    engine._validate_scene(_titled("Une habitude au zinc"), _scene_context(recent_situations=titled))


def test_the_published_scene_keeps_its_title_for_the_next_one(
    assembled_client, db_session, journey_enabled, clock, provider  # noqa: F811
):
    """``recent_situations`` is what the next director call is checked against."""

    d = driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    clock.advance(days=1)
    d.create()
    contexts = [p for schema, p in provider.calls if schema == "SceneDraft"]
    recent = contexts[-1]["recent_situations"]
    assert recent and recent[-1].get("title_fr") == "Les affiches 0", recent


def test_the_learners_own_place_is_named_in_the_apps_register():
    """The app says tu to the learner (#144); the header's place said «Votre»."""

    assert engine.LOCATION_NAMES_FR["user_apartment"] == "Ton appartement"
    stored = {"id": "user_apartment", "name": "Your apartment", "name_fr": "Votre appartement"}
    assert engine.location_display_name(stored) == "Ton appartement"


def test_the_scene_record_is_never_made_with_a_taken_title():
    """Whatever path served the draft (a soft rejection accepted after its retry included),
    the brief the learner's day is built from carries a title no earlier scene wears."""

    taken = [{"novelty_key": "a", "premise_fr": "Un colis.", "title_fr": "Une habitude au zinc"}]
    context = _scene_context(recent_situations=taken, thread_id="t", control_language="en", level="A1")
    context["world"]["cast"] = [
        {"id": "romy_tremblay", "name": "Romy Tremblay"},
        {"id": "lila_bonnet", "name": "Lila Bonnet"},
    ]
    context["world"]["locations"] = [{"id": location, "name": location} for location in LOCATIONS]
    brief = engine._brief(_titled("Une habitude au zinc"), context, usage=[])
    assert brief.title_fr == "Une habitude au zinc, II"
    assert brief.story_context["draft"]["title_fr"] == "Une habitude au zinc, II"
