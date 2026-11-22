"""#992 (root cause #146): a La Forge miss on a verb form gave the rule card's gloss.

Live walk 22 Nov 2026 (A1.1, «Je voudrais…, vous voulez… ?»): «Je voudrai» typed for
«Je voudrais» read «You wrote “Je voudrai”. Offer with vous voulez… ?», and a built
«Tu veut monter à Montmartre ?» read «Not this answer · Rule: Je voudrais…». The same
day in German on être: «est» chosen in «Tu ___ beau ?», «et» and «somme» typed, «au»
left out of the tiles were all answered «Être heißt sein.», and «On est froid ce soir.»
only with the right sentence.

Why the code allowed it: the slip classifier named a verb form of another person only,
and its note named the wrong and the right form in one sentence. While the solution
waits (``solution_gate.learner_view``) every clause naming the right form is scrubbed,
so that sentence went whole, and what was left was the gloss with its answer-bearing
clause gone («Je voudrais … is the polite way to ask; offer with vous voulez… ?»).
A note now says what is wrong with the form written in a sentence of its own, and a
tense, a non-form or another verb are named too.
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import solution_gate

VOUDRAIS = ("FR2_A11_JE_VOUDRAIS", "Je voudrais…, vous voulez… ? (polite asking)")
ETRE = ("FR2_A11_ETRE", "Être")
AVOIR = ("FR2_A11_AVOIR", "Avoir")
#: the rule card's gloss, as the bank item quotes it (``item_miss_reason``)
GLOSS = "Je voudrais (I would like) is the polite way to ask; offer with vous voulez… ?"


def _miss(db_session, unit, language, mode, item, learner, target, drill=None):
    """``(shown, withheld)``: the why once the solution is shown, and what is served
    while it waits for the second chance."""

    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id=unit[0], name=unit[1], level="A1", category="Verbs")
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    service._posed_drill = drill
    item = {**item, "lesson_external_id": unit[0]}
    erratum = service._recognize_erratum(concept, mode, item, learner, target)
    correction = solution_gate.mark(
        {"verdict": "incorrect", "errata": [erratum], "corrected_answer": {item["id"]: target}},
        chance=True,
        language=language,
    )
    view = solution_gate.learner_view(
        correction, answer_payload={"answers": {item["id"]: learner}}, context=solution_gate.task_text(item)
    )
    return erratum["why_wrong"], view["errata"][0]["why_wrong"]


def test_je_voudrai(db_session) -> None:
    item = {
        "id": "gap", "prompt": "___ du fromage, s'il vous plaît.", "explanation": GLOSS,
        "choices": ["Je voudrai", "Je voudrait", "Je voudrais"], "correct_answer": "Je voudrais",
    }
    shown, waiting = _miss(db_session, VOUDRAIS, "en", "fill", item, "Je voudrai", "Je voudrais", "typed")
    assert "vous voulez" not in waiting, f"the gloss's other half is the reason for a missing -s: {waiting!r}"
    assert "«voudrai»" in waiting and "future" in waiting, f"nothing says what «voudrai» is: {waiting!r}"
    assert "voudrais" not in waiting, f"the answer is given before the second chance: {waiting!r}"
    assert "«voudrai»" in shown and "«voudrais»" in shown and "conditional" in shown, shown


def test_tu_veut(db_session) -> None:
    item = {
        "id": "bank", "prompt": "Do you (informal) want to go up to Montmartre?",
        "tokens": ["Tu", "veut", "veux", "monter", "à", "Montmartre", "?"], "answer": "Tu veux monter à Montmartre ?",
    }
    shown, waiting = _miss(
        db_session, VOUDRAIS, "en", "word_bank", item, "Tu veut monter à Montmartre ?", "Tu veux monter à Montmartre ?"
    )
    assert "«veut» goes with il/elle/on, not with «tu»" in waiting, f"only the rule's name is left: {waiting!r}"
    assert "With «tu», «vouloir» is «veux»" in shown, shown


@pytest.mark.parametrize(
    ("mode", "item", "learner", "target", "drill", "reason", "named"),
    [
        # Day 1, choice «Tu ___ beau ?», «est» chosen
        ("fill", {"id": "g", "prompt": "Tu ___ beau ?", "choices": ["suis", "est", "es"], "correct_answer": "es"},
         "est", "es", None, "«est» gehört zu il/elle/on, nicht zu «tu»", "Mit «tu» heißt «être» «es»"),
        # Day 1, typed gap «Tu ___ anglaise ?», «et» typed
        ("fill", {"id": "g", "prompt": "Tu ___ anglaise ?", "choices": ["suis", "est", "es"], "correct_answer": "es"},
         "et", "es", "typed", "«et» ist keine Form von «être»", "Mit «tu» heißt «être» «es»"),
        # Day 2, typed gap «Nous ___ au marché du canal», «somme» typed
        ("fill", {"id": "g", "prompt": "Nous ___ au marché du canal.", "choices": ["sommes", "sont", "est"],
                  "correct_answer": "sommes"},
         "somme", "sommes", "typed", "«somme» ist keine Form von «être»", "Mit «nous» heißt «être» «sommes»"),
        # Day 1, tiles «Ich bin im Supermarkt.», «au» left out
        ("word_bank", {"id": "b", "prompt": "Ich bin im Supermarkt.", "tokens": ["Je", "suis", "au", "supermarché", "."],
                       "answer": "Je suis au supermarché."},
         "Je suis supermarché.", "Je suis au supermarché.", None, "Ein Wort fehlt", "«au»"),
    ],
    ids=["est", "et", "somme", "au"],
)
def test_etre(db_session, mode, item, learner, target, drill, reason, named) -> None:
    shown, waiting = _miss(db_session, ETRE, "de", mode, item, learner, target, drill)
    assert reason in waiting, f"the rule's gloss, not why «{learner}» is wrong: {waiting!r}"
    assert "sein" not in waiting, f"«Être heißt sein» is no reason for this slip: {waiting!r}"
    assert named in shown, f"the shown note does not name the right form: {shown!r}"


def test_on_est_froid(db_session) -> None:
    """Day 2, a choice between two sentences (no second chance): the right sentence alone
    is the answer, not the reason."""

    item = {
        "id": "c", "prompt": "Welcher Satz sagt: „Uns ist kalt heute Abend.“?",
        "choices": ["On est froid ce soir.", "On a froid ce soir."], "correct_answer": "On a froid ce soir.",
    }
    shown, _waiting = _miss(db_session, AVOIR, "de", "choice", item, "On est froid ce soir.", "On a froid ce soir.")
    assert "«est» kommt von «être»" in shown and "braucht «avoir»" in shown, shown


def test_slip_reasons() -> None:
    """The cause, guarded where it lives: each slip note says something without the right
    form, so the scrub that withholds the answer never leaves only the rule's gloss."""

    from app.services.learner_copy import LEARNER_COPY

    class Fields(dict):
        def __missing__(self, key: str) -> str:
            return {"learner": "wrongform", "target": "rightform"}.get(key, key)

    for key, texts in LEARNER_COPY.items():
        if not (key.startswith("forge.slip.") and key.endswith(".why")):
            continue
        for language, text in texts.items():
            filled = text.format_map(Fields())
            left = solution_gate.scrub_hint(filled, ["rightform"], {"rightform"})
            assert left, f"{key} ({language}) says nothing once «rightform» is withheld: {filled!r}"
