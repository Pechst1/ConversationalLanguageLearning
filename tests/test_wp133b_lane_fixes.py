"""WP-133b blocking findings 3 and 4, on the reply and ending lanes (fake provider only).

3. Gender agreement with the learner in a character's reaction («pauvre toi, gelé»)
   and in the day's ending («tu n'es pas encore décidé») — both from the paid C1 read
   of 2026-10-06 — are caught, retried once with the hint, then replaced by the lane's
   authored line; a gender the learner gave keeps its agreement.
4. A reaction that echoes the learner («Merci pour la soupe.» back at them) is caught;
   one that merely shares a word passes; the voice lane is told who said what; the
   deterministic self-repair choice no longer puts the learner's «je» in the
   character's mouth.
"""

from __future__ import annotations

import json

import pytest

from app.services import lane_guards
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.journey_conversation import self_repair_question
from tests import test_wp87_lanes as wp87
from tests.test_living_story import driver
from tests.test_wp87_lanes import _resolution, _respond, _to_respond, _walk_to_end

# The WP-87 lane fixtures: the scripted lane provider, inline/queued story jobs.
assembled_client = wp87.assembled_client
clock = wp87.clock
inline = wp87.inline
jobs = wp87.jobs
journey_enabled = wp87.journey_enabled
one_exchange = wp87.one_exchange
provider = wp87.provider

GELE = "Ah, ça me touche que tu dises ça — pauvre toi, gelé, mais content. Viens, rapproche-toi."
DECIDE = "Tu restes ce soir et tu n'es pas encore décidé. Lila range la photo dans son sac."
SOUPE = "Merci pour la soupe. Oui, j'ai froid, mais ça va mieux."
SOUPE_ECHO = "Merci pour la soupe. Ça me touche que tu me le confies — je vais en prendre soin."


def _payload(address: str = "neutral", learner_text: str = SOUPE, history=None) -> dict:
    return {
        "story": {
            "level": "C1",
            "learner": {"address": address},
            "world": {"cast": [{"id": "lila", "name": "Lila Bonnet"}]},
            "commitments": [],
        },
        "scene": {
            "character_id": "lila",
            "title_fr": "Ce qu'on donne",
            "premise_fr": "Lila t'offre son cactus : «Tiens, garde-le.»",
            "objective_native": "Dites à Lila ce que vous ferez du cactus qu'elle vous donne.",
            "opening_line_fr": "Tiens, prends ça. Mon cactus. Que vas-tu en faire ?",
            "suggested_response_fr": "Je vais le mettre sur ma fenêtre.",
            "panels": [],
            "season_checklist": {
                "change_before": "Lila garde ses affaires encore dans un sac.",
                "change_after": "Un objet de Lila a changé de maison.",
            },
        },
        "history": history or [],
        "learner_text": learner_text,
        "turn_plan": {},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="x", needs_clarification=False)


# --- finding 3: agreement ---------------------------------------------------


def test_the_quoted_gele_reaction_and_decide_resolution_are_caught():
    assert lane_guards.agreement_hits(GELE, "neutral") == ["gelé"]
    assert lane_guards.agreement_hits(DECIDE, "neutral") == ["décidé"]
    with pytest.raises(engine.StoryUnavailable, match="gendered_agreement"):
        lanes.validate_voice(_voice(GELE), _payload())
    turn = lanes.merged_turn(
        lanes.TutorVerdict(outcome="partially_met"),
        _voice("Tu restes ? Ça me soulage."),
        lanes.StoryTurn(resolution_fr=DECIDE, summary_native="You stay tonight."),
    )
    with pytest.raises(engine.StoryUnavailable, match="gendered_agreement"):
        lanes.validate_story(turn, _payload())


def test_a_learner_who_gave_a_gender_keeps_agreement():
    assert lane_guards.agreement_hits(GELE, "masculine") == []
    assert lane_guards.agreement_hits(DECIDE, "masculine") == []
    lanes.validate_voice(_voice(GELE), _payload("masculine"))
    feminine = "Tu n'es pas encore décidée, et tu as l'air gelée."
    assert lane_guards.agreement_hits(feminine, "feminine") == []
    assert lane_guards.agreement_hits(feminine, "masculine") == ["décidée", "gelée"]
    # The learner's own words about themselves may be said back.
    own = lane_guards.learner_own_forms(["Je suis gelé, mais ça va."])
    assert lane_guards.agreement_hits("Tu es gelé ? Viens près du radiateur.", "neutral", own=own) == []


def test_ordinary_lines_pass_the_wider_net():
    for line in (
        "Tu restes ? Ça me soulage.",
        "Tu es en été, au café du coin.",
        "Tu as froid ? Viens, je te passe ma veste.",
        "Chez toi demain ?",
        "Ah, bon — tu l'as aimée, la soupe.",
    ):
        assert lane_guards.agreement_hits(line, "neutral") == [], line


# --- finding 4: echo and roles ---------------------------------------------


def test_the_soupe_echo_is_caught_and_a_shared_word_passes():
    assert lane_guards.echo_hit(SOUPE_ECHO, SOUPE) == "Merci pour la soupe."
    with pytest.raises(engine.StoryUnavailable, match="reply_echoes_learner"):
        lanes.validate_voice(_voice(SOUPE_ECHO), _payload())
    for reply in (
        "Ah, bon — tu as aimé la soupe. Ça me rassure. Tu trembles encore un peu ?",
        "Tu restes ? Ça me fait chaud au cœur.",
        "On commence quand ? Demain, si tu veux.",
    ):
        assert lane_guards.echo_hit(reply, SOUPE) is None, reply
    lanes.validate_voice(_voice("Ah, tu as aimé la soupe ? Ça me rassure."), _payload())
    # A waiter confirming an order is not an echo; the learner's own line is.
    assert lane_guards.echo_hit("Un thé en terrasse, tout de suite.", "Un thé en terrasse.") is None
    assert lane_guards.echo_hit("Un café crème, s'il te plaît ! Bien sûr.", "Un café crème, s'il te plaît.")
    # A question of the learner's own, asked back at them, is caught.
    assert lane_guards.echo_hit("Je peux rester ici ? Bien sûr.", "Je peux rester ici ?")


def test_the_self_repair_choice_never_puts_the_learners_je_in_the_characters_mouth():
    question, kind = self_repair_question(
        wrong_fr="je reste encore un peu", corrected_fr="je resterai encore un peu", register="tu"
    )
    assert (question, kind) == ("Pardon ? Tu peux le redire autrement ?", "repetition")
    assert self_repair_question(wrong_fr="une homme", corrected_fr="un homme", register="tu") == (
        "Pardon, un ou une homme ?",
        "choice",
    )


def test_the_reaction_prompt_carries_who_said_what():
    view = lanes.voice_payload(_payload())
    roles = view["who_is_who"]
    assert roles["you_are"] == "Lila Bonnet"
    assert "learner" in roles["learner_text_and_history_learner_are"]
    assert any("cactus" in fact for fact in roles["scene_facts"])
    assert any("changé de maison" in fact for fact in roles["scene_facts"])
    assert "who_is_who" in lanes.VOICE and "never ask their question back" in lanes.VOICE


# --- end to end: retry, then the lane's authored line; the day is never blocked ---


def _scripted_voice(provider, replies):
    original = provider.generate_chat_completion
    seen: list[dict] = []

    def scripted(messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] == "VoiceReply":
            seen.append(data["data"])
            provider.voice = {"reply_fr": next(replies)}
        return original(messages, **kwargs)

    provider.generate_chat_completion = scripted
    return seen


def test_a_gendered_reaction_is_retried_with_the_hint(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    seen = _scripted_voice(provider, iter([GELE, "Merci ! On prépare la salle ensemble."]))
    d = driver(assembled_client, db_session)
    result = _respond(assembled_client, d, _to_respond(d))[2].json()
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert len(seen) == 2 and any("gelé" in hint for hint in seen[1]["previous_rejections"])
    assert "who_is_who" in seen[0]


def test_a_reaction_that_fails_twice_falls_back_and_the_day_finishes(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    _scripted_voice(provider, iter([GELE, SOUPE_ECHO, GELE, SOUPE_ECHO]))
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    response = _respond(assembled_client, d, step, text=SOUPE)[2]
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["reply_source"] == "authored"
    assert "gelé" not in result["character_reply_fr"]
    assert "Merci pour la soupe" not in result["character_reply_fr"]
    _walk_to_end(d)
    assert d.finish("complete").status_code == 200
    assert d.journey["status"] == "completed"


def test_a_gendered_ending_falls_back_to_the_authored_one(
    assembled_client, db_session, journey_enabled, clock, provider, inline
):
    provider.story = {"resolution_fr": DECIDE}
    d = driver(assembled_client, db_session)
    result = _respond(assembled_client, d, _to_respond(d))[2].json()
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert inline == ["fallback"]
    story_calls = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert len(story_calls) >= 2 and any(
        "décidé" in hint for hint in story_calls[1]["previous_rejections"]
    )
    d.advance()
    shown = _resolution(d.journey)["prompt"]
    assert "décidé" not in shown["character_line_fr"]
    assert "doit partir avant de répondre" in shown["character_line_fr"]
    _walk_to_end(d)
    assert d.finish("complete").status_code == 200
