"""#954 — a Regelprüfung's item says the verdict its tally counts.

Walk of 20 Nov 2026 (a1-de-fresh, fake provider): the short «Épreuve de la règle» of
«Ich bin, du bist: Subjektpronomen und être». The learner wrote «Ils sont fatigues.» for
«Ils sont fatigués.»; the item said «Noch nicht · Die Antwort erfüllt die Aufgabe noch
nicht», the result said «3 von 3 richtig, der eigene Satz inklusive».

The rule check's local grade (``_test_out_local_grade``) set the verdict and cleared the
errata, but left the rule-based fallback's ``missing_targets`` on the correction: the forge
counted the verdict, the screen read the list (``seanceAssessment``: «correct» carries no
errata, nothing missing, no lexical gap) and called it a miss. A verdict and the lists it is
read from are now settled together, and the forgiven accent is named on the hit.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService
from app.services.forge import ForgeService, forge_state_of
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from tests.test_atelier import _user
from tests.test_forge_integration import _right

LEARNER = "Ils sont fatigues."
KEY = "Ils sont fatigués."


def client_says_right(correction: dict[str, Any]) -> bool:
    """The item's verdict as the screen reads it (web-frontend/lib/seance-feedback.ts,
    ``seanceAssessment``): a right verdict with nothing listed against it."""

    return (
        correction.get("verdict") in {"correct", "accepted"}
        and not correction.get("errata")
        and not correction.get("missing_targets")
        and not correction.get("lexical_gaps")
    )


def _play_rule_check(db_session, monkeypatch, learner: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    try:
        concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_ETRE").one()
        user = _user(db_session)
        user.native_language = "de"
        db_session.commit()
        forge = ForgeService(db_session)
        session = forge.start_test_out(user=user, concept_id=concept.id, short=True)
        service = AtelierCorrectionService(db_session)
        corrections: list[dict[str, Any]] = []
        while (nxt := forge.next_item(user=user, session=session)) is not None:
            free = nxt["round"] not in {"recognize", "transform"}
            exercise_id = f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}"
            override = None
            if free:
                # The walk's item: «Sag auf Französisch: « Sie (alle) sind müde. »».
                override = service._prompt_payload(concept, nxt["round"], nxt["mode"], exercise_id, user=user, session=session)
                override["items"][0] = {
                    **override["items"][0],
                    "prompt": 'Say in French: "They are tired."',
                    "example_answer": KEY,
                    "accepted_answers": [KEY],
                }
            attempt = service.submit_attempt(
                session=session,
                user=user,
                concept=concept,
                round_name=nxt["round"],
                mode="rewrite" if nxt["round"] == "transform" else nxt["mode"],
                exercise_id=exercise_id,
                answer_payload={"text": learner} if free else _right(nxt["item"], nxt["round"], nxt["mode"]),
                prompt_payload_override=override,
            )
            corrections.append({**attempt.correction_payload, "_free": free})
            forge.observe_attempt(user=user, session=session, attempt=attempt)
        return corrections, forge_state_of(session).result
    finally:
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


def test_the_item_and_the_tally_say_one_verdict_and_the_accent_is_named(db_session, monkeypatch):
    corrections, result = _play_rule_check(db_session, monkeypatch, LEARNER)
    free = next(item for item in corrections if item["_free"])
    shown_right = sum(1 for item in corrections if client_says_right(item))
    assert result["correct"] == shown_right, (
        f"the result says {result['correct']} of {result['total']} right; the items on screen said "
        f"{shown_right} (the own sentence: verdict {free.get('verdict')!r}, "
        f"missing_targets {free.get('missing_targets')!r})"
    )
    # The rule check counts «Ils sont fatigues.» right (the rule is used; the accent is lenient
    # in this unit), so the item says so too, and names the accent it forgave.
    assert client_says_right(free) and result["production_correct"] is True
    assert free["corrected_answer"] == KEY, "the hit shows the sentence with its accent"
    assert free["accent_notes"] == [{"learner_text": LEARNER, "corrected_target": KEY}]
    assert free["slip_note_native"] == "Richtig — achte auf den Akzent: «fatigués»."


def test_a_miss_in_the_rule_check_is_a_miss_on_screen_and_in_the_tally(db_session, monkeypatch):
    corrections, result = _play_rule_check(db_session, monkeypatch, "Ils est fatigués.")
    free = next(item for item in corrections if item["_free"])
    assert not client_says_right(free)
    assert result["production_correct"] is False
    assert result["correct"] == sum(1 for item in corrections if client_says_right(item))
