"""#240 / #146: a miss is framed by what the item asked, not by its answer being French.

Walk 2026-10-19: «Which sentence uses today's rule?» (passé composé). Tapping
«Vous allez vraiment vendre l'appartement d'Odile ?» came back as «One thing to
fix: Vous allez vraiment vendre… → Il a dit ça ?». The two are different
sentences: that frame says the first should be rewritten into the second.

``Correction`` carried only (span, corrected, note), so every wrong tap was a
«fix A → B» whether B is A corrected («Ils est» → «Ils sont») or simply the other
card. The correction now says which it is (``kind``): ``edit`` keeps the arrow,
``pick`` names the sentence that carries the rule.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import grammar_items
from tests.test_recall_miss_feedback_shape import _choice_task, _public, _wrong_option
from tests.test_rule_step_regressions import _unit


def _kind(public) -> str:
    return getattr(public, "kind", "edit")


def test_a_wrong_tap_on_find_the_sentence_is_a_pick_not_a_correction(db_session: Session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    task = grammar_items.recognise_item(
        brief, sentences=["Je pense partir.", "Tu viens ?", "Il pleut."], language="en"
    )
    assert task is not None
    assert task.instruction_native == grammar_items._RECOGNISE_USE["en"]
    public = _public(task, _wrong_option(task))
    assert public is not None
    assert public.corrected_fr == task.solution_fr, "the rule-carrying sentence is named"
    assert _kind(public) == "pick", "two different sentences are not «fix A → B»"


def test_a_variant_choice_keeps_the_correction_frame() -> None:
    task = _choice_task("Après si, le verbe reste au présent.")
    public = _public(task, _wrong_option(task))
    assert public is not None
    assert _kind(public) == "edit"
    assert public.span_fr != public.corrected_fr


def test_a_stored_find_the_sentence_item_is_still_a_find_after_a_reload(db_session: Session) -> None:
    """The task is stored with the step and read back for the answer."""
    from app.services.daily_journey import _recall_task_from_json, _recall_task_to_json

    brief = _unit(db_session, "FR_A1_NOUN_001")
    task = grammar_items.recognise_item(
        brief, sentences=["Je pense partir.", "Tu viens ?", "Il pleut."], language="en"
    )
    assert task is not None and task.options_kind == "sentences"
    assert _recall_task_from_json(_recall_task_to_json(task)).options_kind == "sentences"
    # An item stored before the field existed reads as the old kind: a correction.
    stored = _recall_task_to_json(task)
    stored.pop("options_kind")
    assert _recall_task_from_json(stored).options_kind == "variants"


def test_the_pick_kind_survives_the_public_schema() -> None:
    from app.schemas.daily_journey import JourneyCorrection

    pick = JourneyCorrection(span_fr="a", corrected_fr="b", note_native="n", kind="pick")
    assert pick.model_dump()["kind"] == "pick"
    assert JourneyCorrection(span_fr="a", corrected_fr="b", note_native="n").kind == "edit"
