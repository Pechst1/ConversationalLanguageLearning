"""WP-103 «Retour d'essai» — the story engine half (T4, T5). Fake provider only.

The owner's own test of day 2 (English-speaking A1 learner, 2026-09-29):

* T4 — the objective read «Ask Romy if she wants to sit with you» while Marin, with
  Marin's face, answered. The person the objective addresses IS the addressed
  character: refused once with a precise hint, then re-addressed deterministically.
* T5 — the learner wrote «Oui, ton place est libre pour moi?» and Marin answered in
  43 words. Engine replies: A1 ≤ 15 words in one or two short sentences, A2 ≤ 25;
  one retry with the reason, then trimmed at a sentence boundary — never a lost turn.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes
from tests import test_living_story as story
from tests.test_journey_end_to_end import step_of
from tests.test_living_story import (  # noqa: F401 - fixtures
    assembled_client,
    clock,
    driver,
    journey_enabled,
    one_exchange,
    provider,
)

CAST = [
    {"id": "marin_leveque", "name": "Marin Lévêque", "gender": "m"},
    {"id": "lila_bonnet", "name": "Lila Bonnet", "gender": "f"},
    {"id": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt", "gender": "m"},
    {"id": "romy_tremblay", "name": "Romane « Romy » Tremblay", "gender": "f"},
    {"id": "margaux_barman", "name": "Margaux", "gender": "f"},
]

#: The owner's day 2: Marin at Le Mistral, and an objective about Romy.
OWNER_OBJECTIVE = "Ask Romy if she wants to sit with you"
OWNER_LEARNER_LINE = "Oui, ton place est libre pour moi?"
#: Marin's reply as the owner saw it: 43 words to an A1 learner.
OWNER_MARIN_REPLY = (
    "Oui, bien sûr, la place est libre, et c'est ta place maintenant ! Je t'attendais, "
    "tu sais, parce que Romy m'a dit ce matin que tu viendrais peut-être au Mistral avec "
    "tes nouvelles affiches. Tu veux un café ou un thé avant de commencer ?"
)


def _owner_scene(context: dict) -> dict:
    value = story.draft(context, 0)
    value.update(
        {
            "character_id": "marin_leveque",
            "location_id": "le_mistral",
            "objective_native": OWNER_OBJECTIVE,
            "objective_semantics": "Ask Romy whether she wants to sit with the learner.",
            "hint_native": "Ask Romy about the free seat.",
            "suggested_response_fr": "Romy, tu veux t'asseoir avec moi ?",
            "opening_line_fr": "Tiens, tu es là ! Il reste une place à ma table.",
        }
    )
    for panel in value["panels"]:
        for line in panel.get("dialogue") or []:
            line["character_id"] = "marin_leveque"
    return value


# ---------------------------------------------------------------------------
# T4 — the addressee rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("objective", "character_id", "expected"),
    [
        (OWNER_OBJECTIVE, "marin_leveque", "Ask Marin if he wants to sit with you"),
        ("Ask Romy if her seat is free.", "marin_leveque", "Ask Marin if his seat is free."),
        (
            "Demande à Romy si elle veut s'asseoir avec toi.",
            "marin_leveque",
            "Demande à Marin s'il veut s'asseoir avec toi.",
        ),
        ("Invite Gus to the party.", "lila_bonnet", "Invite Lila to the party."),
        # Not a mismatch: the addressed character is the one spoken to …
        ("Tell Marin that Romy is late.", "marin_leveque", None),
        # … or nobody is spoken to by name, or only a possession is named.
        ("Ask whether Romy is coming.", "marin_leveque", None),
        ("Invite Romy's friend to the party.", "marin_leveque", None),
        ("Ask Marin if he has a free seat.", "marin_leveque", None),
    ],
)
def test_the_objectives_addressee_is_the_addressed_character(objective, character_id, expected):
    mismatch = engine.objective_addressee_mismatch(objective, character_id, CAST)
    if expected is None:
        assert mismatch is None
        return
    other, word = mismatch
    addressed = next(member for member in CAST if member["id"] == character_id)
    assert engine.readdress(objective, word, other, addressed, pronouns=True) == expected


def test_the_owners_scene_is_refused_with_a_precise_hint_and_re_addressed():
    context = story._scene_context(world={"cast": CAST, "locations": [{"id": "le_mistral"}]})
    draft = engine.SceneDraft.model_validate(_owner_scene(context))
    with pytest.raises(engine.SoftRejection) as refused:
        engine._check_addressee(draft, context)
    assert str(refused.value) == "objective_addresses_other_character"
    hint = refused.value.hint
    assert "Romy" in hint and "Marin" in hint and "marin_leveque" in hint
    assert "IS the addressed character" in hint
    repaired = refused.value.proposal
    assert repaired.objective_native == "Ask Marin if he wants to sit with you"
    assert repaired.hint_native == "Ask Marin about the free seat."
    assert repaired.suggested_response_fr == "Marin, tu veux t'asseoir avec moi ?"
    assert repaired.character_id == "marin_leveque"
    # The draft the model wrote is untouched: the retry is told, not overruled.
    assert draft.objective_native == OWNER_OBJECTIVE


def test_the_owners_day_two_is_never_lost_to_the_addressee(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """E-7-style fixture: the director writes the owner's scene twice. The first draft
    is refused with the hint; the retry repeats the mistake and is served re-addressed."""

    provider.transform = lambda schema, output: (
        _owner_scene(provider.calls[-1][1]) if schema == "SceneDraft" else output
    )
    d = driver(assembled_client, db_session)
    journey = d.create()

    directed = [payload for schema, payload in provider.calls if schema == "SceneDraft"]
    assert len(directed) == 2, "one refusal, one retry — never more for this"
    retry = directed[1]["previous_rejections"]
    assert any(item.startswith("objective_addresses_other_character:") for item in retry)
    respond = step_of(journey, "respond")
    assert respond["prompt"]["character_id"] == "marin_leveque"
    assert respond["prompt"]["objective_native"] == "Ask Marin if he wants to sit with you"


# ---------------------------------------------------------------------------
# T5 — reply length at A1/A2, and the word budget
# ---------------------------------------------------------------------------


def test_the_owners_43_word_reply_is_above_the_a1_line():
    assert engine.reply_words(OWNER_MARIN_REPLY) == 43
    issue = engine.reply_length_issue(OWNER_MARIN_REPLY, "A1")
    assert issue and "43 words" in issue and "at most 15" in issue
    trimmed = engine.trim_reply(OWNER_MARIN_REPLY, "A1")
    assert engine.reply_length_issue(trimmed, "A1") is None
    assert engine.reply_words(trimmed) <= 15
    # Cut at a sentence boundary: the sentence that answers the learner stays.
    assert trimmed == "Oui, bien sûr, la place est libre, et c'est ta place maintenant !"
    # With room for it, the question that moves the scene on is kept too.
    shorter = "Oui, la place est libre ! Je t'attendais, tu sais, depuis ce matin. Tu veux un café ?"
    assert engine.trim_reply(shorter, "A1") == "Oui, la place est libre ! Tu veux un café ?"


@pytest.mark.parametrize(
    ("level", "words", "rejected"),
    [("A1", 15, False), ("A1", 16, True), ("A2", 25, False), ("A2", 26, True), ("B1", 85, False)],
)
def test_reply_caps_per_band(level, words, rejected):
    reply = " ".join(["mot"] * words) + "."
    assert (engine.reply_length_issue(reply, level) is not None) is rejected


def test_an_a1_reply_is_one_or_two_short_sentences():
    three = "Ta place est libre. Je range la table. Tu prends un café ?"
    assert engine.reply_words(three) <= 15
    assert "sentences" in engine.reply_length_issue(three, "A1")
    assert engine.trim_reply(three, "A1") == "Ta place est libre. Tu prends un café ?"
    # An interjection is not a sentence.
    assert engine.reply_length_issue("Oui ! Ta place est libre. Tu prends un café ?", "A1") is None
    # A2 has no sentence cap, only its 25 words.
    assert engine.reply_length_issue(three, "A2") is None


def _voice_payload(level: str = "A1") -> dict:
    return {
        "learner_text": OWNER_LEARNER_LINE,
        "history": [],
        "targets": [],
        "turn_plan": {"keep_talking": True},
        "story": {"level": level, "learner": {"address": "neutral"}, "commitments": []},
        "scene": {"character_id": "marin_leveque", "opening_line_fr": "Tiens, tu es là !", "panels": []},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(
        reply_fr=reply, understood_intent="The learner asks if the seat is free.",
        needs_clarification=False,
    )


class _ScriptedLane:
    """``engine._json_call`` for one lane: the scripted replies in order."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def __call__(self, system, payload, schema, on_usage=None, **kwargs):
        self.requests.append(payload)
        return _voice(self.replies.pop(0)), {}


def test_the_owners_reply_is_refused_once_then_trimmed(monkeypatch):
    """Marin's 43 words, twice: the retry is told why, and the second answer is served
    trimmed at a sentence boundary — the learner never loses the turn to it."""

    payload = _voice_payload()
    scripted = _ScriptedLane([OWNER_MARIN_REPLY, OWNER_MARIN_REPLY])
    monkeypatch.setattr(engine, "_json_call", scripted)
    served = lanes._run_lane(
        lanes.VOICE, lanes.voice_payload(payload), lanes.VoiceReply,
        lambda v: lanes.validate_voice(v, payload),
        deadline=time.monotonic() + 30, collected=[], max_tokens=100, window=5, attempts=2,
    )
    assert len(scripted.requests) == 2
    assert any("reply_above_level" in item for item in scripted.requests[1]["previous_rejections"])
    assert engine.reply_length_issue(served.reply_fr, "A1") is None
    assert engine.reply_words(served.reply_fr) <= 15


def test_a_compliant_retry_is_served_as_written(monkeypatch):
    payload = _voice_payload()
    scripted = _ScriptedLane([OWNER_MARIN_REPLY, "Oui, elle est libre. Assieds-toi !"])
    monkeypatch.setattr(engine, "_json_call", scripted)
    served = lanes._run_lane(
        lanes.VOICE, lanes.voice_payload(payload), lanes.VoiceReply,
        lambda v: lanes.validate_voice(v, payload),
        deadline=time.monotonic() + 30, collected=[], max_tokens=100, window=5, attempts=2,
    )
    assert served.reply_fr == "Oui, elle est libre. Assieds-toi !"


def test_a_failed_retry_still_serves_the_first_reply_trimmed(monkeypatch):
    payload = _voice_payload()
    calls = []

    def flaky(system, request, schema, on_usage=None, **kwargs):
        calls.append(request)
        if len(calls) == 2:
            raise engine.StoryUnavailable("story_provider_failed")
        return _voice(OWNER_MARIN_REPLY), {}

    monkeypatch.setattr(engine, "_json_call", flaky)
    served = lanes._run_lane(
        lanes.VOICE, lanes.voice_payload(payload), lanes.VoiceReply,
        lambda v: lanes.validate_voice(v, payload),
        deadline=time.monotonic() + 30, collected=[], max_tokens=100, window=5, attempts=2,
    )
    assert engine.reply_words(served.reply_fr) <= 15


def test_the_word_budget_applies_to_engine_replies(monkeypatch):
    """WP-89's lexical check, now on the voice lane: one retry with the words named,
    then the reply is served as it is (a word budget never costs a turn)."""

    payload = _voice_payload()
    hint = "Too many words an A1 learner has not met: « subrepticement »."
    lexical = lambda reply: hint if "subrepticement" in reply else None  # noqa: E731
    scripted = _ScriptedLane(["Assieds-toi subrepticement.", "Assieds-toi, elle est libre."])
    monkeypatch.setattr(engine, "_json_call", scripted)
    served = lanes._run_lane(
        lanes.VOICE, lanes.voice_payload(payload), lanes.VoiceReply,
        lambda v: lanes.validate_voice(v, payload, lexical=lexical),
        deadline=time.monotonic() + 30, collected=[], max_tokens=100, window=5, attempts=2,
    )
    assert any("reply_off_lexicon" in item and "subrepticement" in item
               for item in scripted.requests[1]["previous_rejections"])
    assert served.reply_fr == "Assieds-toi, elle est libre."


def test_the_actor_path_trims_too():
    """The single-actor path (lanes off) takes the same rule through ``_approved``'s
    soft rejection: the turn carries the trimmed reply."""

    payload = {
        "learner_text": OWNER_LEARNER_LINE, "history": [], "targets": [],
        "story": {"commitments": [], "level": "A1", "learner": {"address": "neutral"}},
        "scene": {},
    }
    turn = engine.SemanticTurn.model_validate(
        {**story.turn_fixture(OWNER_LEARNER_LINE), "reply_fr": OWNER_MARIN_REPLY}
    )
    with pytest.raises(engine.SoftRejection, match="reply_above_level") as refused:
        engine._validate_turn(turn, payload)
    assert engine.reply_words(refused.value.proposal.reply_fr) <= 15
    # A released reply (the story lane) is not judged again.
    engine._validate_turn(turn, payload, reply_checks=False)


def test_the_lexical_checker_abstains_without_a_known_word_set(monkeypatch):
    from app.services import lexical_coverage

    monkeypatch.setattr(
        lexical_coverage, "known_word_set", lambda db, user: SimpleNamespace(is_assessable=False)
    )
    assert engine.reply_lexical_checker(None, None, _voice_payload()) is None
