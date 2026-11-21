"""#828 (child of #542): a typed La Forge gap miss said «Du hast „est“ gewählt» (chose).

Explore walk 16 Nov 2026 (``a1-de-fresh``, La Forge 2/6, «Eintippen · Ergänze den
Satz»): the learner typed «est» and read «Du hast „est“ gewählt; hier ist „es“ nötig.
Hier braucht es die Form «es» von «être», nicht «est».» The verb came from the
feedback path (the recognize round's «chose» line), not from how the forge posed the
item; and the second sentence said the swap again. Seen again 17 Nov in English
(«You chose “tu as porter”; Most verbs …»).

The forge knows how it posed each item (``state.pending["drill"]`` while it is served,
the history entry once answered, #699); the grader reads it there.
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept

# test_typed_gap_says_wrote / test_choice_gap_says_chose lived here. Main has since
# landed the same «wrote, not chose» fix its own way (the endpoint passes the posed drill,
# ``AtelierCorrectionService._typed_fill``), tested in
# tests/test_typein_retry_first.py::test_a_typed_miss_says_written_not_chosen; and main's
# first-miss view no longer shows a nonsense «zzz» gap answer through the chose/wrote
# line, so the API-level versions here no longer describe main.


@pytest.mark.parametrize(
    ("language", "needs"),
    [("en", "this item needs"), ("de", "nötig"), ("fr", "il faut")],
)
def test_named_slip_says_it_once(db_session: Session, language: str, needs: str) -> None:
    """«est» for «es»: one sentence names what was typed, the next says why; the
    «… needs “es”» clause would say the swap a second time."""

    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id="FR2_A11_ETRE", name="Être", level="A1", category="Verbs")
    item = {
        "id": "gap", "prompt": "___ -tu au Mistral, Marin ?", "choices": ["Es", "Est", "Suis"],
        "correct_answer": "es", "lesson_external_id": "FR2_A11_ETRE",
    }
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    service._posed_drill = "typed"
    erratum = service._recognize_erratum(concept, "fill", item, "est", "es")
    why = erratum["why_wrong"]
    assert needs not in why, f"the swap is said twice: {why!r}"
    assert why.count("«es»") + why.count("« es »") + why.count("„es“") + why.count("“es”") == 1, why


def test_only_the_posed_verb_lines_say_chose() -> None:
    """#828's cause, guarded where it lives: a miss line that says «You chose» says it
    whatever the item was posed as. Only the lines the grader picks by how the item was
    posed (chose / wrote) may name the verb; any other miss line says what does not fit
    («`prendras` does not fit: …»)."""

    from app.services.learner_copy import LEARNER_COPY

    posed = {"atelier.recognize.chose", "atelier.recognize.chose_requires", "atelier.recognize.blank_needs"}
    said = {
        key
        for key, text in LEARNER_COPY.items()
        if key not in posed and re.search(r"\bYou chose\b|\bgewählt\b|\bTu as choisi\b", " ".join(text.values()))
    }
    assert not said, f"miss lines that call any answer «chosen»: {sorted(said)}"
