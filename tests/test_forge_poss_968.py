"""#968 — La Forge's «One possible answer» answers the card's own person.

Live walk 21 Nov (A1.1, day 39), La Forge on «Mon, ma, mes»: item 2/6 «Say in French:
"We look for our notebooks."». After the learner's fix «Nous cherchons nos cahiers.»
the sheet said «One possible answer: On cherche ses carnets.» — «ses» (his/her) for
«our», in a card that teaches the possessive's person.

Root cause: the bank wrote the possessive from the owner's *verb* person. «on» conjugates
like «il» (person 3s), so «On cherche …» took «son/sa/ses», although the lexicon's «on»
means «we» and its English says «our». The possessive follows whom it belongs to, not
the verb's ending. And nothing checked the model answer against the card's English: the
answer key, the example, the gap's target («ses carnets») all came out unchecked.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from app.services import item_bank as ib
from app.services import solution_gate

UNIT = "FR2_A11_POSSESSIVES"
WALK = "live walk 21 Nov: «One possible answer: On cherche ses carnets.» for «We look for our notebooks.»"
_THIRD = re.compile(r"\b(?:son|sa|ses)\b", re.IGNORECASE)
_OURS = re.compile(r"\b(?:notre|nos)\b", re.IGNORECASE)


def _items(predicate) -> list[ib.BankItem]:
    bank = ib.default_bank()
    found: dict[str, ib.BankItem] = {}
    for seed in range(12):
        for item in bank.generate(UNIT, 400, seed=f"night-968-{seed}"):
            if predicate(item):
                found.setdefault(item.sentence, item)
    return list(found.values())


def _our_notebooks() -> ib.BankItem:
    items = _items(lambda item: item.en.startswith("We look for our notebooks") and item.sentence.startswith("On "))
    assert items, "the bank no longer writes «on» for «we» in this frame"
    return items[0]


def test_on_takes_nos_in_the_bank():
    items = _items(lambda item: re.search(r"\bour\b", item.en) and re.match(r"On\b", item.sentence))
    assert items, "no «On …» item glossed with «our»"
    for item in items:
        for sentence in (item.sentence, *item.accepted):
            assert not _THIRD.search(sentence), (WALK, item.en, sentence)
            assert _OURS.search(sentence), (WALK, item.en, sentence)
        assert _OURS.search(item.target), (WALK, item.en, item.target)


def test_card_answer_has_no_ses():
    from app.api.v1.endpoints.atelier import _learner_correction

    card = ib.output_item(_our_notebooks(), round_name="sentence", requirement={"label": "possessifs"})
    assert card is not None
    refused = solution_gate.mark(
        {"verdict": "partial", "assessment_status": "checked",
         "errata": [{"learner_text": "notre cahiers", "corrected_target": "nos cahiers", "why_wrong": "pluriel"}]},
        chance=False, language="en",
    )
    attempt = SimpleNamespace(
        round="sentence", verdict="partial", correction_payload=refused,
        answer_payload={"text": "Nous cherchons notre cahiers."},
        prompt_payload={"round": "sentence", "items": [card]},
    )
    shown = _learner_correction(attempt).get("model_answer") or ""
    assert shown, WALK
    assert not _THIRD.search(shown), (WALK, shown)
    assert _OURS.search(shown), (WALK, shown)


def test_stored_card_hides_ses():
    """Cards already dealt keep their stored key: the served answer is checked, not trusted."""

    from app.services.free_card_contract import model_answer

    stored = {
        "items": [{
            "type": "short_sentence",
            "prompt": 'Say in French: "We look for our notebooks."',
            "meaning_l10n": {"en": "We look for our notebooks.", "de": "Wir suchen unsere Notizbücher."},
            "example_answer": "On cherche ses carnets.",
            "accepted_answers": ["On cherche ses carnets.", "On cherche ses cahiers.", "Nous cherchons nos cahiers."],
        }]
    }
    assert model_answer(stored) == "Nous cherchons nos cahiers.", WALK
    stored["items"][0]["accepted_answers"] = ["On cherche ses carnets.", "On cherche ses cahiers."]
    assert model_answer(stored) == "", WALK


def test_answer_takes_learner_noun():
    """The learner wrote «cahiers»: of the right answers, the one in their words is shown."""

    from app.api.v1.endpoints.atelier import _learner_correction

    card = {
        "type": "short_sentence",
        "prompt": 'Say in French: "We look for our notebooks."',
        "meaning_l10n": {"en": "We look for our notebooks."},
        "example_answer": "Nous cherchons nos carnets.",
        "accepted_answers": ["Nous cherchons nos carnets.", "Nous cherchons nos cahiers."],
    }
    refused = solution_gate.mark({"verdict": "partial", "assessment_status": "checked", "errata": []}, chance=False, language="en")
    attempt = SimpleNamespace(
        round="sentence", verdict="partial", correction_payload=refused,
        answer_payload={"text": "Nous cherchons notre cahiers."},
        prompt_payload={"round": "sentence", "items": [card]},
    )
    assert _learner_correction(attempt).get("model_answer") == "Nous cherchons nos cahiers.", WALK


def _possessive_clashes(english: str, french: str) -> list[str]:
    from app.services.item_semantics import sentence_violations

    return [clash.kind for clash in sentence_violations(french, english) if "possessive" in clash.kind]


def test_guard_catches_walk_text():
    assert _possessive_clashes("We look for our notebooks.", "On cherche ses carnets.") == ["possessive_person"], WALK
    assert _possessive_clashes("He looks for his notebook.", "Il cherche ton carnet.") == ["possessive_person"]
    assert _possessive_clashes("We look for our notebooks.", "On cherche nos cahiers.") == []
    assert _possessive_clashes("We look for our notebooks.", "Nous cherchons nos carnets.") == []
    assert _possessive_clashes("You look for your notebook.", "Vous cherchez votre carnet.") == []
    assert _possessive_clashes("You look for your notebook.", "Tu cherches ton carnet.") == []
    assert _possessive_clashes("They look for their notebooks.", "Ils cherchent leurs carnets.") == []
    # «leur» before a verb is a pronoun, not «their»; «her» as an object names no owner.
    assert _possessive_clashes("I give them my book.", "Je leur donne mon livre.") == []
    assert _possessive_clashes("I see her with my brother.", "Je la vois avec mon frère.") == []
    # The French may say it another way: another count of possessives is not read.
    assert _possessive_clashes(
        "Last time I tidied the flat because my parents had said they were coming.",
        "La dernière fois, j'ai rangé l'appartement parce que mes parents avaient annoncé leur visite.",
    ) == []
