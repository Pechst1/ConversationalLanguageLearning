"""Steering read 2026-10-24: the learner steers their reasons, the season keeps its spine.

Two 17-day paid reads, one learner who wants to stay in Paris and one who wants to
leave, found the generated days moving the season on over the leaver's own words
(«Le billet est déplacé au 2 décembre, mais je t'entends : tu veux partir mercredi»),
asking again what had just been answered, and Gus going on with «te» right after his
panicked return to vous. The ticket days and the gap's settling are covered in
tests/test_gap_day_plan.py; this file covers the lanes and the register guard.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services import story_split
from app.services.season import turns as season_turns
from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

GUS = "augustin_de_roncourt"
# Leaving learner, day 7 (g1.5, «La même chose ?»): the page staged Gus's first
# accidental tu and his panicked return to vous, as the season plans it.
GUS_OPENING = "Alors, au Mistral, c'est quoi, votre commande habituelle ?"
GUS_PANELS = [
    {"narration_fr": "", "dialogue": [{"character_id": GUS, "text_fr": "Alex, tu es... de la maison !"}]},
    {"narration_fr": "", "dialogue": [{"character_id": GUS, "text_fr": "Pardon. Vous êtes de la maison. Ce n'est pas une blague."}]},
]
LEARNER = "C'est simple et ça me réveille. Je ne cherche pas plus loin."
GUS_SLIP = "Règle numéro deux : la simplicité a du panache. Et ce café te réveille vraiment ?"
GUS_KEPT = "Règle numéro deux : la simplicité a du panache. Et ce café vous réveille vraiment ?"


def _gus_payload(season_turn: dict | None) -> dict:
    story = {"level": "B1", "learner": {"address": "neutral"}, "control_language": "en", "commitments": []}
    if season_turn is not None:
        story["season_turn"] = season_turn
    return {
        "story": story,
        "scene": {"character_id": GUS, "opening_line_fr": GUS_OPENING, "objective_native": "", "panels": GUS_PANELS},
        "learner_text": LEARNER,
        "history": [],
        "targets": [],
        "turn_plan": {},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="The learner answered.", needs_clarification=False)


def _reason(callable_, *args, **kwargs) -> str | None:
    try:
        callable_(*args, **kwargs)
    except engine.StoryUnavailable as exc:
        return str(exc)
    return None


@pytest.mark.parametrize(
    "text, register",
    [
        ("Et ce café te réveille vraiment ?", "tu"),
        ("Je t'attends au Mistral.", "tu"),
        ("Je t’attends au Mistral.", "tu"),
        ("Tu prends quoi ?", "tu"),
        ("Vous êtes de la maison.", "vous"),
        ("Il pleut sur le canal. Le temps passe, quelqu'un attend jusqu'au soir.", None),
        ("Pardon. Vous êtes de la maison, je te jure.", None),
    ],
)
def test_te_and_t_apostrophe_address_the_learner_as_tu(text, register):
    assert engine._address_register([text]) == register


def test_gus_goes_on_with_vous_after_his_accidental_tu():
    """The page mixes tu and vous on purpose, so it says nothing about the reply: the
    season does (Gus is on vous until T3)."""

    payload = _gus_payload({"may_set": [], "gate": None, "register": "vous"})
    assert lanes.voice_payload(payload)["register"] == "vous"
    assert _reason(lanes.validate_voice, _voice(GUS_SLIP), payload) == "reply_register_mismatch"
    assert _reason(lanes.validate_voice, _voice(GUS_KEPT), payload) is None


def test_off_a_season_a_page_that_mixes_both_still_leaves_the_reply_free():
    payload = _gus_payload(None)
    assert lanes.voice_payload(payload)["register"] is None
    assert _reason(lanes.validate_voice, _voice(GUS_SLIP), payload) is None


def test_a_page_that_addresses_the_learner_clearly_keeps_its_own_register():
    payload = _gus_payload({"register": "vous"})
    payload["scene"]["panels"] = [{"narration_fr": "", "dialogue": [{"character_id": GUS, "text_fr": "Tu prends quoi ?"}]}]
    payload["scene"]["opening_line_fr"] = "Tu restes ?"
    assert lanes.voice_payload(payload)["register"] == "tu"


def test_the_season_narrator_says_tu_beside_a_stranger_who_says_vous():
    """Both reads lost g2.6 («Un appel de Solvel») and re-read T2 instead: Bastien says
    vous, and each of the six drafts had a caption like this one. The season's own
    pages do the same («Le lendemain. Ton billet de retour est pour mercredi.» beside
    the agent's «Vous voulez changer votre billet ?»)."""

    from tests.test_wp133b_director_fixes import _register_context, _spoken

    context = _register_context()
    page = _spoken(context, "bastien_roux", ("Bonjour, Bastien Roux, de Solvel. Vous avez une minute ?",),
                   "Vous acceptez un café avec moi cette semaine ?")
    page.panels[0].narration_fr = "Il pleut sur les toits de zinc. Ton téléphone vibre sur la table."
    engine._check_scene_address_register(page, context)
    # Off a season the narration still follows the character...
    off_season = {key: value for key, value in context.items() if key != engine.SEASON_TODAY_KEY}
    with pytest.raises(engine.StoryUnavailable, match="mixed_address_register"):
        engine._check_scene_address_register(page, off_season)
    # ...and on a season day a narrator who says vous beside a tu is still refused.
    lila = _spoken(context, "lila_bonnet", ("Tu viens ?",), "Tu restes ?")
    lila.panels[0].narration_fr = "Vous poussez la porte du café."
    with pytest.raises(engine.StoryUnavailable, match="mixed_address_register"):
        engine._check_scene_address_register(lila, context)


def test_a_tentpole_acknowledgement_to_a_vous_character_never_says_te():
    assert season_turns.clean_ack("Je te crois.", learner_text="Je suis là pour ma grand-mère.", address="vous") is None
    assert season_turns.clean_ack("Je vous crois.", learner_text="Je suis là pour ma grand-mère.", address="vous") == "Je vous crois."


def test_the_lanes_are_told_the_learner_owns_their_reasons():
    assert "The learner owns their reasons." in story_split.PLANNER
    # The world moves the ticket; the learner's blessing stays theirs (Marin's «Je peux ?»).
    assert "never asks whether it will happen" in story_split.PLANNER
    assert "a no holds on the page and after" in story_split.PLANNER
    assert "Never ask again what" in lanes.VOICE
    assert "never says the learner agreed or" in lanes.STORY


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_a_generated_day_tells_the_lanes_how_its_speaker_addresses_the_learner(
    assembled_client, db_session, journey_enabled, clock, season_on  # noqa: F811
):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    provider = season_on
    email = f"s1-register-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=3)
    db_session.commit()
    _play(d, provider, clock, "Je reste encore un peu.")
    endings = [payload for schema, payload in provider.calls if schema == "StoryTurn"]
    assert endings, "the story lane wrote the ending"
    season_turn = endings[-1]["story"]["season_turn"]
    speaker = endings[-1]["scene"]["character_id"]
    expected = {"augustin_de_roncourt": "vous"}.get(speaker, "tu")
    assert season_turn["register"] == expected
