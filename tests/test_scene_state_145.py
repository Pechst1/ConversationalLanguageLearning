"""#145: the scene knows what the learner did with each turn.

Every learner line here is the exact text of a live walk (the issue is named beside it),
because this is the text the ledger has to read: typos, missing accents, a «non» with a
question behind it. No model call and no database.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services import scene_ledger

# #591, live walk 8 Nov 2026.
CAMILLE_OPENING = "L'appartement paie d'abord mon grand-père. Vous êtes d'accord, non ?"
CAMILLE_REFUSED = "Non, je ne suis pas daccord. Pourquoi le appartement paie grand-pere dabord ?"


@pytest.mark.parametrize(
    ("said", "intent", "asks"),
    [
        (CAMILLE_REFUSED, "no", "Pourquoi le appartement paie grand-pere dabord ?"),  # 591
        ("Oui, je savais. Ma grand-mère elle a laissé le Mistral à moi, mais je suis pas sûr de le garder.", "yes", None),  # 556
        ("Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca.", "yes", None),  # 558
        ("Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sais pas. Margaux a raison.", "other", None),  # 535
        ("Je garde la canapé rouge. Le menu, il s'appelle Les Mots sur les cartes.", "other", None),  # 467
        (
            "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut l'appeler Napoléon?",
            "no",
            "Ma grand-mère avait une chat qui s'appelle Napoléon, on peut l'appeler Napoléon?",
        ),  # 467
        ("Oui, je garde Napoléon. Il est dans le canapé. Marin, tu as faim?", "yes", "Marin, tu as faim?"),  # 467
        ("Non, on reste ici! Je fais des pâtes pour nous deux. Tu aimes les pâtes?", "no", "Tu aimes les pâtes?"),  # 467
        ("Margaux, ça va ? Tu es triste parce que la fête est annulé ?", "question", "Margaux, ça va ?"),  # 518
        ("Non, je ne vois pas la lettre. Je veux pas lire. Tu as faim ?", "no", "Tu as faim ?"),  # 518
        ("Mon voisin a un dinosaure dans le jardin. Il mange la lettre !", "other", None),  # 518
        ("Non, je ne partage pas la pizza… tu a menti à Margaux", "no", None),  # 620
        ("Oui Napoleon aime le poisson. Bon, je lis la lettre avec toi, mais dis moi la verité d abord.", "yes", None),  # 620
        ("non, je préfère la photo de mon chat Napoléon", "no", None),  # 500
        ("Non, pas comme ca. Je vais essayer de parler samedi, avec toi.", "no", None),  # 445
        ("Non, je ne vend pas", "no", None),  # 132
    ],
)
def test_a_walks_turn_reads_as_what_it_did(said, intent, asks):
    reading = scene_ledger.read_turn(said)
    assert (reading["intent"], reading["asks"]) == (intent, asks)
    assert reading["read_by"] == "words"


@pytest.mark.parametrize(
    "said",
    [
        "Moi non plus.",
        "Non seulement il pleut, mais il fait froid.",
        "Oui et non.",
        "Si tu veux, on peut parler demain.",
        "Pas mal, le café.",
        "Je ne sais pas.",
        "Peut-être.",
        "Noël arrive bientôt.",
        "Nonante euros.",
    ],
)
def test_what_is_neither_yes_nor_no_stays_unread(said):
    """The reading says «other» rather than guess: nothing downstream may treat these
    as an answer the learner gave."""

    assert scene_ledger.read_turn(said)["intent"] == "other"


@pytest.mark.parametrize(
    ("said", "intent"),
    [
        ("Euh… non.", "no"),
        ("Bien sûr que non.", "no"),
        ("Absolument pas.", "no"),
        ("Je ne peux pas samedi.", "no"),
        ("Je crois que non.", "no"),
        ("Désolé, je ne peux pas.", "no"),
        ("Pas d’accord.", "no"),  # the iPhone's curly apostrophe
        ("Nein.", "no"),
        ("Mais oui !", "yes"),
        ("Bien sûr.", "yes"),
        ("Daccord, mais pas demain.", "yes"),
        ("Si, je veux.", "yes"),
        ("Pourquoi pas ?", "yes"),
    ],
)
def test_a_yes_or_a_no_is_read_however_it_is_typed(said, intent):
    assert scene_ledger.read_turn(said)["intent"] == intent


def test_pourquoi_pas_is_not_a_question_the_character_must_answer():
    assert scene_ledger.learner_question("Pourquoi pas ?") is None
    assert scene_ledger.build(opening_line_fr="Tu viens ?", history=[], learner_text="Pourquoi pas ?")["learner_asked"] is None


def test_the_voice_models_reading_outranks_the_words():
    """«Je ne vends pas» opens with nothing the words can read; a model that read it as
    a refusal is believed on the next turn."""

    said = "Je ne vends pas l'appartement."
    assert scene_ledger.read_turn(said)["intent"] == "other"
    reading = scene_ledger.read_turn(said, heard={"intent": "no"})
    assert (reading["intent"], reading["read_by"]) == ("no", "voice")
    assert scene_ledger.read_turn(said, heard={"intent": "maybe"})["read_by"] == "words"


def test_camilles_scene_knows_the_refusal_the_proposal_and_the_question():
    """#591: what her reply needs to be right is on the record before she answers."""

    ledger = scene_ledger.build(opening_line_fr=CAMILLE_OPENING, history=[], learner_text=CAMILLE_REFUSED)

    assert ledger["last_turn"] == {
        "at": 0,
        "intent": "no",
        "asks": "Pourquoi le appartement paie grand-pere dabord ?",
        "read_by": "words",
        "refuses": "L'appartement paie d'abord mon grand-père.",
    }
    assert ledger["stands"] == [
        {"by": "character", "text_fr": "L'appartement paie d'abord mon grand-père.", "at": 0, "stance": "refused"}
    ]
    assert ledger["learner_asked"] == "Pourquoi le appartement paie grand-pere dabord ?"
    assert [(row["kind"], row["by"]) for row in ledger["still_open"]] == [
        ("question", "learner"),
        ("refused_proposal", "character"),
    ]


def test_a_stored_answer_settles_the_question_but_not_the_refused_proposal():
    history = [
        {
            "learner": CAMILLE_REFUSED,
            "character": "Parce qu'il m'a élevée. C'est ma dette.",
        }
    ]
    ledger = scene_ledger.build(opening_line_fr=CAMILLE_OPENING, history=history)
    assert ledger["learner_asked"] is None
    assert [row["kind"] for row in ledger["still_open"]] == ["refused_proposal"]


def test_a_no_turns_down_the_open_question_when_nothing_was_proposed():
    ledger = scene_ledger.build(opening_line_fr="Tu as faim ?", history=[], learner_text="Non, merci.")
    assert ledger["last_turn"]["refuses"] == "Tu as faim ?"
    assert ledger["stands"] == []


def test_a_yes_leaves_nothing_refused():
    ledger = scene_ledger.build(opening_line_fr=CAMILLE_OPENING, history=[], learner_text="Oui, d'accord.")
    assert ledger["last_turn"]["refuses"] is None
    assert ledger["stands"][0]["stance"] == "agreed"
    assert ledger["still_open"] == []


def test_a_tag_on_a_fact_is_not_a_proposal():
    assert scene_ledger.character_proposal("Il fait beau, n'est-ce pas ?") is None
    assert scene_ledger.character_proposal("On partage la pizza, d'accord ?") == "On partage la pizza, d'accord ?"
    assert scene_ledger.character_proposal("Je pars demain.") is None


def test_every_turn_is_kept_so_a_later_surface_cannot_contradict_an_earlier_one():
    """#620: the say-aloud said «Oui, on partage.» after a first reply of «Non…». The
    ledger keeps each turn, not only the last."""

    history = [
        {"learner": "Non, je ne partage pas la pizza… tu a menti à Margaux", "character": "Tu as raison. Et Napoléon ?"},
        {"learner": "Oui Napoleon aime le poisson.", "character": "Bon. Tu lis la lettre avec moi ?"},
    ]
    ledger = scene_ledger.build(opening_line_fr="On partage la pizza ?", history=history)
    assert [turn["intent"] for turn in ledger["turns"]] == ["no", "yes"]
    assert ledger["last_turn"]["at"] == 1


def test_established_keeps_only_what_the_learner_wrote():
    """#467: «Napoléon» is the learner's grandmother's cat. A fact stays with a quote
    copied from that reply; a quote nobody wrote is dropped (#378, #620)."""

    said = "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut l'appeler Napoléon?"
    history = [
        {
            "learner": said,
            "character": "Napoléon ? Pour le menu ?",
            "heard": {
                "learned": [
                    {"key": "chat", "fact_fr": "Sa grand-mère avait un chat, Napoléon.", "quote": "une chat qui s'appelle Napoléon", "value": "Napoléon"},
                    {"key": "vente", "fact_fr": "L'apprenant vend la bouillotte.", "quote": "je vais vendre la bouillotte"},
                ]
            },
        }
    ]
    ledger = scene_ledger.build(opening_line_fr="Tu gardes le canapé ?", history=history)
    assert ledger["established"] == [
        {
            "key": "chat",
            "fact_fr": "Sa grand-mère avait un chat, Napoléon.",
            "quote": "une chat qui s'appelle Napoléon",
            "at": 0,
            "value": "Napoléon",
        }
    ]


def test_in_the_room_is_the_scene_and_nobody_else():
    """#558: Marin and Lila spoke in a scene at Le Mistral with Gus, Margaux and Odile."""

    draft = {
        "character_id": "margaux_barman",
        "panels": [
            {"dialogue": [{"character_id": "augustin_de_roncourt", "text_fr": "Là."}]},
            {"dialogue": [{"character_id": "margaux_barman", "text_fr": "Oui."}]},
            {"dialogue": []},
        ],
    }
    assert scene_ledger.room_of(draft) == ["margaux_barman", "augustin_de_roncourt"]
    assert scene_ledger.room_of(None) == []
    ledger = scene_ledger.build(opening_line_fr="Oui.", history=[], in_the_room=scene_ledger.room_of(draft))
    assert ledger["in_the_room"] == ["margaux_barman", "augustin_de_roncourt"]
    assert "lila_bonnet" not in ledger["in_the_room"]


def test_the_ledger_before_the_learner_has_spoken_says_so():
    ledger = scene_ledger.build(opening_line_fr="Tu viens ?", history=[])
    assert ledger["last_turn"] is None
    assert ledger["turns"] == []
    assert ledger["open_for_learner"] == "Tu viens ?"


# ---------------------------------------------------------------------------
# #145 «Done when»: the fake provider branches on the same reading, so a free walk
# shows a «non», a «oui», a question and an off-script reply taken differently.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake():
    path = Path(__file__).resolve().parents[1] / "scripts" / "dev_story_engine_server.py"
    spec = importlib.util.spec_from_file_location("dev_story_engine_server_145", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _voice(fake, said: str, *, keep: bool = True) -> dict:
    """The fake voice answering ``said``, through the schema call the lanes make."""

    import json

    ledger = scene_ledger.build(opening_line_fr=CAMILLE_OPENING, history=[], learner_text=said)
    message = json.dumps(
        {
            "output_schema": {"title": "VoiceReply"},
            "data": {"learner_text": said, "turn_plan": {"keep_talking": keep}, "history": [], "ledger": ledger},
        }
    )
    answer = fake.FakeStoryProvider().generate_chat_completion([{"content": message}])
    return json.loads(answer.content)


def test_the_fake_voice_takes_each_reading_differently(fake):
    replies = {
        said: _voice(fake, said)["reply_fr"]
        for said in (
            "Oui, je suis d'accord.",
            "Non, je ne suis pas d'accord.",
            "Pourquoi cet appartement ?",
            "Mon voisin a un dinosaure dans le jardin. Il mange la lettre !",
        )
    }
    assert len(set(replies.values())) == 4, replies


def test_the_fake_voice_reads_a_no_the_old_substring_test_got_wrong(fake):
    """«non» used to be found inside any word: «sinon» read as a refusal, so a free walk
    could not tell the two apart."""

    assert not fake._refuses("Oui, Sinon je viens samedi.")
    assert fake._refuses("Non, je ne peux pas.")


def test_the_fake_voice_prefers_the_ledgers_reading_over_the_words(fake):
    """A model's reading stored with the turn drives the fake too."""

    assert fake._intent_of({"learner_text": "Je ne vends pas.", "ledger": {"last_turn": {"intent": "no"}}}) == "no"
    assert fake._intent_of({"learner_text": "Non."}) == "no"
