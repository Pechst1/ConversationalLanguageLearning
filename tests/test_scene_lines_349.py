"""#349 (root cause #145): one speaker per bubble, no echoed history, no label leak.

Live walk of 27 Oct 2026 (production, real model, day 15 «Deux promesses»), a scene at
Marin's NGO office:

* the thread showed a new Marin bubble that repeated the whole earlier conversation in
  one run-on block, cut mid-word: «Merci. Merci. …Et Gus ? Et il y a un problème. …
  Gus : La fête ? Ton nom est déjà là. En haut. Gus : Marcha»;
* after the third reply Gus's line came out in Marin's bubble: «Marin: Gus : Et s'il
  vient ? Qu'est-ce qu'on dit ?».

The scene handed the model its past as a transcript («Gus : …» inside one string) and
stored what came back as one line, so a copied history or a copied label became the
line. Fake data only: nothing is spent.
"""

from __future__ import annotations

import json

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes

MARIN = {"id": "marin", "name": "Marin"}
GUS = {"id": "gus", "name": "Gus"}

ECHOED_BLOCK = (
    "Merci. Merci. …Et Gus ? Et il y a un problème. … Gus : La fête ? Ton nom est déjà là. "
    "En haut. Gus : Marcha"
)
GUS_IN_MARIN = "Gus : Et s'il vient ? Qu'est-ce qu'on dit ?"

#: What the scene stored for the exchanges so far: Marin's lines, then Gus's (the
#: labelled transcript string the thread keeps, plus the lines per speaker).
HISTORY = [
    {
        "learner": "Bonjour, je suis là pour la fête.",
        "character": "Merci. Merci.",
        "lines": [{"speaker_id": "marin", "speaker_name": "Marin", "text_fr": "Merci. Merci."}],
    },
    {
        "learner": "Qui est Gus ?",
        "character": "…Et Gus ?\nGus : La fête ? Ton nom est déjà là. En haut.",
        "lines": [
            {"speaker_id": "marin", "speaker_name": "Marin", "text_fr": "…Et Gus ?"},
            {"speaker_id": "gus", "speaker_name": "Gus", "text_fr": "La fête ? Ton nom est déjà là. En haut."},
        ],
    },
    {
        "learner": "Il y a un problème ?",
        "character": "Et il y a un problème avec la liste des invités.",
        "lines": [
            {
                "speaker_id": "marin",
                "speaker_name": "Marin",
                "text_fr": "Et il y a un problème avec la liste des invités.",
            }
        ],
    },
]


def _payload(learner_text: str, *, history=None) -> dict:
    return {
        "story": {
            "level": "B1",
            "learner": {"address": "neutral"},
            "commitments": [],
            "world": {"cast": [MARIN, GUS], "locations": []},
        },
        "scene": {"character_id": "marin", "opening_line_fr": "Merci d'être venu.", "panels": []},
        "learner_text": learner_text,
        "history": HISTORY if history is None else history,
        "targets": [],
        "turn_plan": {},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="The learner answers.", needs_clarification=False)


# ---------------------------------------------------------------------------
# No echoed history
# ---------------------------------------------------------------------------


def test_a_reply_that_pastes_the_earlier_thread_is_refused():
    """The earlier lines, unlabelled: the reason names the repetition."""

    reply = (
        "Merci. Merci. …Et Gus ? Et il y a un problème avec la liste des invités. "
        "La fête ? Ton nom est déjà là. En haut."
    )
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(_voice(reply), _payload("Je viens avec Gus."))
    assert str(caught.value) == "reply_repeats_thread"


def test_the_exact_echoed_block_of_the_walk_never_reaches_the_learner():
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(_voice(ECHOED_BLOCK), _payload("Je viens avec Gus."))
    assert str(caught.value) in {"reply_repeats_thread", "reply_speaks_for_other"}


def test_one_earlier_long_sentence_said_again_is_refused():
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(
            _voice("Ton nom est déjà là. En haut. Tu veux voir la liste ?"),
            _payload("Je viens avec Gus."),
        )
    assert str(caught.value) == "reply_repeats_thread"


def test_a_short_repeat_and_a_new_answer_pass():
    """«Merci.» again is a character's habit, not an echo; a fresh answer passes."""

    voice = _voice("Merci. Alors dis-moi, qui d'autre vient avec toi ce soir ?")
    lanes.validate_voice(voice, _payload("Je viens avec Gus."))
    assert voice.reply_fr.startswith("Merci. Alors")


# ---------------------------------------------------------------------------
# No speaker label in the line
# ---------------------------------------------------------------------------


def test_gus_line_under_marin_is_refused_with_the_reason():
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(_voice(GUS_IN_MARIN), _payload("Il vient avec moi."))
    assert str(caught.value) == "reply_speaks_for_other"
    assert "Gus" in caught.value.feedback


def test_the_speakers_own_label_is_cut():
    voice = _voice("Marin : Et s'il vient ? Qu'est-ce qu'on dit ?")
    lanes.validate_voice(voice, _payload("Il vient avec moi."))
    assert voice.reply_fr == "Et s'il vient ? Qu'est-ce qu'on dit ?"


# ---------------------------------------------------------------------------
# The model is not handed a transcript to copy
# ---------------------------------------------------------------------------


def test_the_model_reads_each_earlier_exchange_by_speaker_not_as_a_labelled_transcript():
    sent = lanes.voice_payload(_payload("Il vient avec moi."))["history"]
    blob = json.dumps(sent, ensure_ascii=False)
    assert "Gus :" not in blob, blob
    second = sent[1]
    assert [(row["by"], row["text_fr"]) for row in second["said"]] == [
        ("Marin", "…Et Gus ?"),
        ("Gus", "La fête ? Ton nom est déjà là. En haut."),
    ]
    assert "character" not in second and "lines" not in second


def test_an_exchange_without_lines_is_sent_as_it_was():
    plain = [{"learner": "Bonjour.", "character": "Bonjour ! Tu cherches quelqu'un ?"}]
    assert lanes.voice_payload(_payload("Oui.", history=plain))["history"] == plain
