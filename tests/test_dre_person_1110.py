"""#1110: the basic check passed «Je ne vend pas» (and «Je le vend», «Tu ne prend pas»).

Walk 27 Nov (`a2-en`, day 2): «… Je ne vend pas maintenant. …» was never marked, while
«Je vend peut-etre» the day before got «vends». The -dre person rule read only the word
right before the verb (``prev.low in {"je", "j", "tu"}``), so «ne», «n'» or an object
pronoun between the subject and the verb hid it. The person rule for être/avoir/aller
read the subject through ``_subject_person`` and stepped over «ne», but no object
pronoun, so «Je lui a dit» was passed the same way.

Done when: the «-s» edit stands for the walk's sentence, «Je le vend demain.», «Tu ne
prend pas ?», «Je n'attend pas.» and «Je n attend pas.», on the verb only, and never for
«Il ne vend pas.» or «Elle le vend.»; the scene card for such a reply lists «vends».
"""

from __future__ import annotations

import pytest

from app.services import correction_contract
from app.services import story_lanes as lanes


def _edits(text: str) -> list[tuple[str, str]]:
    return [(e.span, e.replacement) for e in correction_contract.deterministic_edits(text)]


@pytest.mark.parametrize(
    ("text", "verb", "right"),
    [
        ("Je ne vend pas maintenant.", "vend", "vends"),
        ("Je le vend demain.", "vend", "vends"),
        ("Tu ne prend pas ?", "prend", "prends"),
        ("Je n'attend pas.", "attend", "attends"),
        ("Je n attend pas.", "attend", "attends"),
        ("Je ne le prend pas.", "prend", "prends"),
        ("Tu m'attend ?", "attend", "attends"),
        ("Je vous attend.", "attend", "attends"),
    ],
)
def test_dre_s_through_ne_and_object(text, verb, right):
    edits = _edits(text)
    assert (verb, right) in edits, f"«{text}»: the -dre verb after «ne»/an object pronoun is unmarked: {edits}"
    hit = next(e for e in correction_contract.deterministic_edits(text) if e.replacement == right)
    assert text[hit.start : hit.end] == verb, "the edit's span is the verb only"


@pytest.mark.parametrize(
    "text", ["Il ne vend pas.", "Elle le vend.", "La femme le vend.", "Qui me vend ça ?", "Il ne me prend pas."]
)
def test_third_person_left_alone(text):
    assert not any(rep.endswith(("ds", "ps")) for _span, rep in _edits(text)), _edits(text)


def test_avoir_person_through_object_pronoun():
    # The same subject reading serves the être/avoir person rule.
    assert ("a", "ai") in _edits("Je lui a dit non."), _edits("Je lui a dit non.")
    for right in ("Je les ai vus.", "Ils nous ont vus.", "Il y a un chat.", "Marie et elle les ont vus.",
                  "Tu l'as vu.", "Nous nous sommes vus."):
        assert _edits(right) == [], (right, _edits(right))


def _payload(text: str) -> dict:
    return {
        "learner_text": text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": "neutral"}, "level": "A2", "commitments": [], "control_language": "en"},
        "targets": [],
        "turn_plan": {},
    }


def test_scene_card_lists_vends():
    text = "Mon grand-pere avait une maison. Je ne vend pas maintenant."
    verdict = lanes.TutorVerdict.model_validate(
        {
            "outcome": "met",
            "evidence_quotes": ["Je ne vend pas maintenant"],
            "corrections": [
                {
                    "span_fr": "grand-pere",
                    "corrected_fr": "grand-père",
                    "note_native": "« grand-père » takes a grave accent.",
                    "rule_id": None,
                }
            ],
        }
    )
    lanes.validate_tutor(verdict, _payload(text))
    shown = [(c.span_fr, c.corrected_fr) for c in verdict.corrections]
    assert ("vend", "vends") in shown, f"the scene card leaves «Je ne vend pas» unmarked: {shown}"
