"""#174 (and #193): a repair in the audio studio is filed only when the learner's own
words prove it.

The studio's corrections come from the error detector, model-written free text. Only
«does the suggestion differ from the span?» was checked, so a repair of a span the
learner never said, one that leans on a subject the sentence does not have («est → es,
after 'tu'» on «Ma grand-mère est mort», #193), or one right word swapped for another
(«mais sans mon nom» → «mais pas mon nom», «Vous êtes disponible ?» → «Êtes-vous
disponible ?», #93) went onto the recap and into the learner's mistakes. The studio now
runs the two checks the story lane runs on the tutor's corrections.

Review on #440: the person check of ``correction_is_grounded`` dropped a repair that
changes the verb, not its person («Tu es faim» → «Tu as faim», «Elle a partie» → «Elle est
partie»), because «es» is right for «tu». A verb change is now judged by its replacement
alone, in the studio and in the story lane.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.core.error_detection.rules import DetectedError
from app.db.models.session import ConversationMessage, LearningSession
from app.services.answer_acceptance import correction_is_grounded
from app.services.audio_session_service import AudioSessionService
from tests.test_audio_story_regressions import StubLLMService, _user


@pytest.mark.parametrize(
    ("said", "span", "suggestion", "note", "kept"),
    [
        # #193: no «tu» in the sentence, and «Ma grand-mère est» is right.
        ("Ma grand-mère est mort.", "est", "es", "After 'tu' you must use 'es'.", False),
        ("Ma grand-mère est mort.", "mort", "morte", "Grand-mère is feminine: morte.", True),
        # Preference swaps (#93, agency walk run 3): both are right.
        ("Je pars, mais sans mon nom.", "mais sans mon nom", "mais pas mon nom", "", False),
        (
            "Vous êtes disponible jeudi matin ?",
            "Vous êtes disponible jeudi matin ?",
            "Êtes-vous disponible jeudi matin ?",
            "",
            False,
        ),
        # A span the learner never said.
        ("Hier je allais au marché.", "tu vas", "tu allais", "", False),
        # Real repairs stand, #201's among them («Toi est → es» needs no bare «tu»).
        ("Hier je allais au marché.", "je allais", "j'allais", "Élision devant une voyelle.", True),
        ("Toi est gentil.", "Toi est", "Toi es", "", True),
        ("Je aller au marché.", "je aller", "je vais", "Conjuguez le verbe.", True),
        # A repair of the verb itself, not its person (review on #440).
        ("Tu es faim.", "Tu es faim", "Tu as faim", "On dit avoir faim.", True),
        ("Elle a partie hier.", "a", "est", "Partir prend être au passé composé.", True),
    ],
)
def test_a_studio_repair_must_be_about_what_was_said(said, span, suggestion, note, kept) -> None:
    assert AudioSessionService._is_grounded(said, span, suggestion, note) is kept


@pytest.mark.parametrize(
    ("said", "span", "suggestion", "kept"),
    [
        # être ↔ avoir ↔ aller: the form was right for its subject, the verb was not.
        ("Tu es faim.", "es", "as", True),
        ("Je suis faim.", "suis", "ai", True),
        ("Nous avons allés au marché.", "avons", "sommes", True),
        ("Marin est faim.", "est", "a", True),
        # The replacement must still fit the subject.
        ("Elle est contente.", "est", "as", False),
        ("Ma grand-mère est mort.", "est", "ai", False),
        # A subject the sentence does not name: «as» needs a «tu» or a «toi».
        ("Marin est faim.", "est", "as", False),
    ],
)
def test_a_verb_change_is_judged_by_its_replacement(said, span, suggestion, kept) -> None:
    assert correction_is_grounded(said, span, suggestion) is kept


def test_the_turn_files_and_shows_only_the_grounded_repair(db_session, monkeypatch) -> None:
    said = "Ma grand-mère est mort, mais sans son nom."
    errors = [
        DetectedError(code="verb_conjugation", message="After 'tu' you must use 'es'.", span="est",
                      suggestion="es", category="grammar", severity="medium", confidence=0.9),
        DetectedError(code="word_choice", message="Plus naturel.", span="mais sans son nom",
                      suggestion="mais pas son nom", category="grammar", severity="medium", confidence=0.9),
        DetectedError(code="gender_agreement", message="Grand-mère is feminine: morte.", span="mort",
                      suggestion="morte", category="grammar", severity="medium", confidence=0.9),
    ]

    class Detector:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def analyze(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(errors=list(errors))

    filed: list[str] = []

    def record(_self, *, user, detected_error, **kwargs):  # type: ignore[no-untyped-def]
        filed.append(f"{detected_error.span} → {detected_error.suggestion}")
        return {"action": "created"}

    monkeypatch.setattr("app.core.error_detection.detector.ErrorDetector", Detector)
    monkeypatch.setattr("app.services.audio_session_service.ErrorMemoryService.record_detected_error", record)
    user = _user(db_session, "audio-grounded@example.com")
    session = LearningSession(user_id=user.id, planned_duration_minutes=5, status="in_progress", xp_earned=0)
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ConversationMessage(session_id=session.id, sender="ai", content="Bonjour !", sequence_number=1,
                            generation_prompt="trusted server prompt")
    )
    db_session.commit()

    result = asyncio.run(
        AudioSessionService(db_session, StubLLMService()).process_user_response(
            session_id=session.id, user_id=user.id, user_text=said, conversation_history=[],
        )
    )

    assert [(error["span"], error["correction"]) for error in result["detected_errors"]] == [("mort", "morte")]
    assert filed == ["mort → morte"]
