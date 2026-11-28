"""R2 (walk of 17 Nov 2026): the La Forge cards the walk could not solve become cases.

Each case is a card the walk logged with real model output
(``docs/ops/walks/2026-11-17-experience-review/logs/walk-integration-b1.md`` and
``walk-integration-a1.md``; screenshots b1-d5-forge1-refused2, b1-d2-forge8-stuck). The
model's notes are quoted as the learner saw them and replayed as the model's reading: no
model is called here. The pattern is P4's (``test_walk_2026_11_17_wrong_corrections.py``),
in a file of its own.
"""
from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services import solution_gate
from tests.test_r2_forge_cards_are_solvable import (
    _age_ask_item,
    _attempt,
    _service,
    graded_with_reading,
    lila_scene,
)

WALK = "walk 2026-11-17"


def _task_note(text: str, note: str) -> dict:
    return {"item_id": "x", "learner_text": text, "corrected_target": "", "why_wrong": note, "task_error_type": "task_compliance"}


# ---------------------------------------------------------------------------
# 1 · B1 day 5 «La fête des voisins ?» / «La piscine ?» / «Le vide-grenier ?»
#     (b1-d5-forge1-refused, b1-d5-forge1-refused2): five grammatical answers refused
# ---------------------------------------------------------------------------

#: (Lila's line, the learner's answer, the refusal the screen showed) — verbatim.
B1_DAY5 = [
    ("La fête des voisins ?", "Oui, je la leur ai proposée hier, et ils me la rappellent chaque jour.",
     "Relis la demande : quelle information précise ta réponse doit-elle transmettre ?"),
    ("La fête des voisins ?", "Oui, je la leur propose pour samedi soir.",
     "« Je la leur propose » signifie que tu la proposes aux voisins, pas que la voisine t'en a parlé hier."),
    ("La piscine ?", "Oui, la piscine ferme lundi, alors je le leur ai déjà dit.",
     "Relis la consigne : ta réponse confirme-t-elle un rendez-vous ?"),
    ("La piscine ?", "Oui, rendez-vous à la piscine samedi, je te le confirme demain.",
     "Ta réponse change le jour et reporte la confirmation : quel moment la demande précise-t-elle ?"),
    ("Le vide-grenier ?", "Oui, je te le propose pour dimanche matin, si tu veux.",
     "Relis la consigne : qu'est-ce qu'elle te demande d'utiliser ?"),
]


@pytest.mark.parametrize(("line", "answer", "note"), B1_DAY5, ids=[f"b1-d5-{index}" for index in range(len(B1_DAY5))])
def test_b1_day5_a_grammatical_answer_with_the_rule_is_not_refused_for_an_unstated_intent(line, answer, note):
    """Forge · 2026-11-17 · B1 day 5. Each answer uses two object pronouns in the right
    order; the card said only «Lila : « … ? » Réponds en français, avec cette règle.»"""

    scene = lila_scene(line, "Oui, je la leur propose.", "Yes, I'm suggesting it to them.")
    asked = _service("fr", "en")._compact_llm_task({"items": [scene]})["items"][0]
    assert asked.get("own_sentence") is True, WALK
    graded = graded_with_reading(
        _service("fr", "en"), scene, answer, {"verdict": "partial", "score_0_4": 2.0, "errata": [_task_note(answer, note)]}
    )
    assert graded["verdict"] in {"correct", "accepted"}, WALK
    assert not graded["errata"]


# ---------------------------------------------------------------------------
# 2 · B1 day 2 «Ta sœur cherche le rapport ?» (b1-d2-forge8-stuck): the line was mended,
#     an unstated «sent already» intent kept the card «À reprendre» with only «Passer»
# ---------------------------------------------------------------------------

B1_DAY2_LINE = "Oui, elle le cherche, alors je le lui donne ce soir."
B1_DAY2_NOTE = "« je lui le donne ce soir » annonce un don futur, au lieu d'un envoi déjà effectué comme demandé."


def test_b1_day2_the_mended_line_is_not_held_for_an_intent_the_card_never_stated():
    scene = lila_scene("Ta sœur cherche le rapport ?", "Oui, je le lui donne.", "Yes, I'm giving it to her.")
    graded = graded_with_reading(
        _service("fr", "en"), scene, B1_DAY2_LINE,
        {"verdict": "partial", "score_0_4": 2.0, "errata": [_task_note(B1_DAY2_LINE, B1_DAY2_NOTE)]},
    )
    assert graded["verdict"] in {"correct", "accepted"}, WALK


def test_b1_day2_a_refused_free_card_ends_on_one_model_answer():
    """Had the note stood, the card still ends: its solution is a model answer, not «Passer»."""

    from app.api.v1.endpoints.atelier import _learner_correction

    scene = lila_scene("Ta sœur cherche le rapport ?", "Oui, je le lui donne.", "Yes, I'm giving it to her.")
    refused = solution_gate.mark(
        {"verdict": "partial", "assessment_status": "checked", "errata": [_task_note(B1_DAY2_LINE, B1_DAY2_NOTE)]},
        chance=False, language="fr",
    )
    served = _learner_correction(_attempt(refused, scene, B1_DAY2_LINE))
    assert served.get("model_answer") == scene["example_answer"], WALK


# ---------------------------------------------------------------------------
# 3 · A1 day 3 «Marin fragt, wie alt du bist. Ich bin 30 Jahre alt.»: «0 von 5–24 Wörtern»
# ---------------------------------------------------------------------------


def test_a1_day3_the_age_card_takes_its_own_three_word_answer():
    item = _age_ask_item()
    card = ib.output_item(item, round_name="sentence", requirement={"label": "avoir"})
    assert card is not None
    # #1126: the exchange's answer is about the cast now («Elle a trente ans.»), so the
    # floor is that answer's own length, not the learner's «J'ai trente ans.».
    answer = len(item.sentence.split(". ")[-1].split())
    assert card["min_words"] <= answer <= 4, (WALK, card["min_words"], item.sentence)
    served = ib.public_item(dict(card), "de")
    assert served["min_words"] <= answer
