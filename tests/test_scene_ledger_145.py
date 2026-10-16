"""Root cause #145: the scene ledger and the golden transcripts that fail on the old behaviour.

Every case feeds the exact text quoted in the walk issue. No model call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.correction_guard import drops_question, unlisted_changes
from app.services.living_story import scene_ledger_problems
from app.services.season import scene_ledger as ledger_mod
from app.services.season.levels import iter_says

SEASON = Path(__file__).resolve().parents[1] / "app" / "data" / "season" / "s1"


def _payload(learner: str, spoken: list[str]) -> dict:
    return {
        "learner_text": learner,
        "scene": {"opening_line_fr": spoken[0], "panels": []},
        "history": [{"learner": "", "character": line} for line in spoken[1:]],
    }


# -- #132 · a clear «non» is an answer ------------------------------------------------

LEARNER_132 = "Non, je ne vend pas. Mon chat Bruno aime le appartement. Et qui est Solvel ?"
CAMILLE_132 = "Vous vendez, non ? C'est plus simple pour nous tous."


def test_132_a_non_with_clumsy_french_and_a_side_question_is_a_refusal():
    assert ledger_mod.learner_intent(LEARNER_132) == "no"
    assert ledger_mod.learner_intent("Oui, d'accord.") == "yes"
    assert ledger_mod.learner_intent("Qui est Solvel ?") == "question"


def test_132_camille_does_not_re_ask_after_a_refusal():
    reply = "Solvel est une collègue qui aide pour les visites.\nPardon ? Vous allez vendre, oui ou non ?"
    problems = scene_ledger_problems(reply, _payload(LEARNER_132, [CAMILLE_132]))
    assert any("asks again" in p for p in problems)
    assert any("redefines Solvel" in p for p in problems)


def test_132_solvel_stays_the_buyer():
    assert ledger_mod.redefines_established("Solvel est une collègue qui aide pour les visites.")
    assert ledger_mod.redefines_established("Solvel est l'agence qui veut tout l'immeuble.") is None
    assert ledger_mod.redefines_established("Solvel Immobilier est une société sérieuse.") is None


def test_132_a_reply_that_takes_the_answer_passes():
    reply = "D'accord. Solvel veut tout l'immeuble, voilà pourquoi mon grand-père presse."
    assert scene_ledger_problems(reply, _payload(LEARNER_132, [CAMILLE_132])) == []


def test_171_oui_and_non_lead_to_different_ledgers():
    spoken = ["Tu restes ?"]
    yes = ledger_mod.build_ledger("Oui, je reste.", spoken=spoken)
    no = ledger_mod.build_ledger("Non, je rentre mercredi.", spoken=spoken)
    assert (yes.intent, no.intent) == ("yes", "no")
    assert yes.settled == no.settled == ["Tu restes ?"]
    # The settled question is not asked again, in either wording.
    for ledger in (yes, no):
        assert ledger_mod.reasks_settled_question("Alors, tu restes ?", ledger)
        assert ledger_mod.reasks_settled_question("Tu restes, oui ou non ?", ledger)
        assert ledger_mod.reasks_settled_question("Et Pablo, tu le connais ?", ledger) is None


# -- #114 · the Courrier reply invents a parcel ---------------------------------------

LEARNER_114 = (
    "Salut Marin ! Je pense que Camille est bizarre, elle a une autre clé. Je ne veux plus vendre le "
    "appartement. Et j’ai un chat, Bruno, il dort dans ma valise. Il a faim. Tu as du poisson ?"
)
MARIN_114 = (
    "Salut ! C'est étrange pour Camille d'avoir une autre clé. De mon côté, il y a eu une confusion avec la "
    "porte, j'ai essayé celle de l'appartement voisin par erreur. Au fait, j'ai le numéro de suivi de la "
    "commande, c'est le 123456789. Tu pourrais me confirmer ton adresse ?"
)


def test_114_marins_invented_tracking_number_and_address_request_are_caught():
    ledger = ledger_mod.build_ledger(LEARNER_114, spoken=["Salut ! Une note de Marin."])
    problems = ledger_mod.line_problems(MARIN_114, ledger, context="Le mauvais accueil")
    assert problems and "order" in problems[0]
    assert ledger_mod.invents_logistics("Tu pourrais me confirmer ton adresse ?", LEARNER_114)
    assert ledger_mod.invents_logistics("Le numéro est le 123456789.", LEARNER_114)


def test_114_an_answer_to_what_the_learner_wrote_passes():
    reply = "Une autre clé ? Ça m'inquiète. Pour Bruno, j'ai du poisson : passe au café ce soir."
    ledger = ledger_mod.build_ledger(LEARNER_114, spoken=[])
    assert ledger_mod.line_problems(reply, ledger) == []


def test_114_a_parcel_the_story_really_has_is_allowed():
    ledger = ledger_mod.build_ledger("Où est mon colis ?", spoken=[])
    assert ledger_mod.invents_logistics("Ton colis est chez Margaux.", "Où est mon colis ?") is None
    assert ledger_mod.line_problems("Ton colis est chez Margaux.", ledger) == []


# -- #168 · the engine's recap is internal --------------------------------------------

RECAP_168 = (
    "The notary's news was shared: the papers will take several weeks. The learner says they will "
    "have coffee with Lila, then go to Margaux."
)


@pytest.mark.parametrize(
    "text",
    [RECAP_168, "Der Lernende sagt, er trinkt Kaffee.", "L'apprenant dit qu'il reste."],
)
def test_168_no_recap_in_panel_text(text):
    assert ledger_mod.internal_recap_text(text)


def test_168_an_english_narrator_note_in_a_french_story_is_flagged():
    assert ledger_mod.is_english_recap(RECAP_168)
    assert not ledger_mod.is_english_recap("Lila sourit : « Tu restes pour le café. »")
    assert not ledger_mod.is_english_recap(RECAP_168, story_language="en")


# -- #129 · no bare appointment in the authored bible ---------------------------------


def test_129_a_day_and_hour_alone_is_a_bare_appointment():
    assert ledger_mod.bare_appointment("Jeudi prochain, dix-huit heures.")
    assert ledger_mod.bare_appointment("Demain à 9 h")
    assert not ledger_mod.bare_appointment(
        "Jeudi prochain, dix-huit heures. Pour la visite, avec Solvel."
    )
    assert not ledger_mod.bare_appointment("Mercredi, je n'ai pas classe.")


def test_129_no_authored_line_of_season_one_is_a_bare_appointment():
    bare: list[str] = []
    for path in sorted(SEASON.glob("t*.json")):
        for say in iter_says(json.loads(path.read_text(encoding="utf-8"))):
            if ledger_mod.bare_appointment(say["a2"]):
                bare.append(f"{path.name}: {say['a2']}")
    assert bare == []


# -- #108 · nobody answers for the learner on day 2 ------------------------------------


def test_108_the_café_scene_hands_over_to_the_stairwell_with_a_silent_beat():
    day = json.loads((SEASON / "t1.json").read_text(encoding="utf-8"))
    ids = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("kind") == "panel" and node.get("id"):
                ids.append(node["id"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(day)
    assert "b.r0" in ids and ids.index("b.r0") < ids.index("b.r1") < ids.index("b.r4")
    panel = next(p for p in _panels(day) if p.get("id") == "b.r0")
    assert panel.get("silence") and not panel.get("lines")


def _panels(node):
    if isinstance(node, dict):
        if node.get("kind") == "panel":
            yield node
        for value in node.values():
            yield from _panels(value)
    elif isinstance(node, list):
        for value in node:
            yield from _panels(value)


# -- #133 · the corrected form keeps the question and lists every change ---------------

LEARNER_133 = "Qu est-ce que c est, jeudi a dix-huit heures ?"


def test_133_a_rewritten_question_is_rejected():
    rewritten = "C'est jeudi à dix-huit heures ?"
    errata = [{"learner_text": "a", "corrected_target": "à"}]
    assert drops_question(LEARNER_133, rewritten)
    assert unlisted_changes(LEARNER_133, rewritten, errata)


def test_133_the_faithful_correction_passes_when_every_change_is_listed():
    faithful = "Qu'est-ce que c'est, jeudi à dix-huit heures ?"
    listed = [
        {"learner_text": "Qu est-ce que", "corrected_target": "Qu'est-ce que"},
        {"learner_text": "c est", "corrected_target": "c'est"},
        {"learner_text": "a dix-huit", "corrected_target": "à dix-huit"},
    ]
    assert not drops_question(LEARNER_133, faithful)
    assert unlisted_changes(LEARNER_133, faithful, listed) == []
    # An unlisted change (the «à») is caught.
    assert unlisted_changes(LEARNER_133, faithful, listed[:2])


def test_133_the_deterministic_corrector_lists_apostrophes_and_the_accent():
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    errata, corrected = service._deterministic_errata(LEARNER_133, language="en")
    assert corrected == "Qu'est-ce que c'est, jeudi à dix-huit heures ?"
    assert unlisted_changes(LEARNER_133, corrected, errata) == []
    assert {e["external_id"] for e in errata} == {
        "FR_ORTHO_ELISION_APOSTROPHE",
        "FR_ORTHO_A_ACCENT_TIME",
    }


def test_133_a_provider_rewrite_is_replaced_by_the_listed_repair():
    from app.services.missions import MissionCorrectionService

    text = "Salut Margaux ! Je ne vends pas l'appartement. Qu est-ce que c est, jeudi a dix-huit heures ?"
    correction = {
        "corrected_answer": "Salut Margaux ! Je ne vends pas l'appartement. C'est jeudi à dix-huit heures ?",
        "errata": [
            {"learner_text": "a", "corrected_target": "à", "task_error_type": "orthography"}
        ],
    }
    out = MissionCorrectionService._complete_corrected_answer(text=text, correction=correction)
    assert "Qu est-ce que" in out and "C'est jeudi" not in out


# -- #94 · «Reach the landlord» states the radiator and carries no other contact's P.S. ----


def test_94_the_landlord_task_names_the_radiator_and_keeps_no_neighbour_postscript():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.services.serial import SerialThreadService

    service = SerialThreadService.__new__(SerialThreadService)
    service.db = MagicMock()
    neighbour = {
        "contact_name": "Mme Vidal",
        "twist": "Elle n'est pas contente, mais il y a un petit sourire sous son mot.",
        "success_signal": "Your neighbour feels heard.",
    }
    mission = SimpleNamespace(
        user=SimpleNamespace(proficiency_level="A2"),
        prompt_payload={
            "messenger": neighbour,
            "slim_payload": {
                "twist": neighbour["twist"],
                "frame": "voisine d'en bas",
                "ask": "Merci",
            },
        },
    )
    service._apply_episode_one_mission_contract(mission)
    shown = " ".join(
        [
            mission.brief,
            mission.prompt_payload["messenger"]["twist"],
            str(mission.prompt_payload["slim_payload"]),
        ]
    )
    assert "radiator" in mission.brief.lower() and "Marchand" in mission.brief
    assert "Elle n'est pas contente" not in shown
    assert (
        mission.prompt_payload["slim_payload"]["twist"]
        == mission.prompt_payload["messenger"]["twist"]
    )
