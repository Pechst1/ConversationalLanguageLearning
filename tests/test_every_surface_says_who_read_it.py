"""#333, #250: the free-text surfaces outside the daily five.

The Feuilleton accepted any four words with a «le» in them when no model answered, and that
score reached the level average. A voice turn nobody read earned a «recovery». A rehearsal
debrief printed the model's sentence as it came. No model call is made in this file.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints.audio_session import AudioSessionMessageRequest, respond_to_audio
from app.core.verdict import Call, CheckedBy, Failure, Outcome
from app.services import correction_contract, verdicts
from app.services.graphic_novel import GraphicNovelCorrectionService, _held_to_sentence
from app.services.llm_service import LLMProviderError
from app.services.placement import next_band
from app.services.rehearsal import RehearsalService, _debrief_view

CLEAN = "Le dossier est sur la table avec les clés."
WITH_A_SLIP = "Je suis tres content de le dossier avec les clés."
TASK = {"task_id": "t1", "task_type": "short_sentence", "concept_id": 7, "prompt": "Continue la scène."}


class _Llm:
    """A model client forced to answer one way."""

    def __init__(self, *, error: Exception | None = None, content: str = "") -> None:
        self.error, self.content = error, content

    def generate_error_detection(self, *_a, **_k):
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content, model="fake-model", provider="fake", raw_response={})


def _service(llm=None) -> GraphicNovelCorrectionService:
    service = GraphicNovelCorrectionService.__new__(GraphicNovelCorrectionService)
    service.llm = llm
    return service


def _answer(service, text):
    return service._correct_short_sentence(task=dict(TASK), answer_payload={"answer": text})


# --- Le Feuilleton ----------------------------------------------------------------------------


def test_feuilleton_no_longer_accepts_a_sentence_nobody_read():
    correction = _answer(_service(), CLEAN)

    assert correction["verdict"] == "unassessed"
    check = verdicts.from_feuilleton(correction, text=CLEAN)
    assert check.outcome is Outcome.NOT_CHECKED and check.counts is False
    assert check.checked_by is CheckedBy.NONE
    assert check.failure is Failure.NO_MODEL


def test_feuilleton_says_a_failed_call_failed_and_keeps_what_the_rules_found():
    correction = _answer(_service(_Llm(error=LLMProviderError("read timed out"))), WITH_A_SLIP)
    check = verdicts.from_feuilleton(correction, text=WITH_A_SLIP)

    assert correction["verdict"] == "unassessed"
    assert check.call is Call.FAILED and check.failure is Failure.TIMEOUT
    assert check.checked_by is CheckedBy.RULES, "rules add fixes, never a verdict"
    assert check.outcome is Outcome.NOT_CHECKED and check.counts is False
    assert "très" in correction["corrected_answer"]
    assert "très" in check.corrected


def test_feuilleton_keeps_the_learners_line_when_the_model_rewrites_it():
    held = _held_to_sentence(
        {
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": "C'est jeudi à dix-huit heures ?",
            "why": "",
            "repair": "",
            "errata": [],
        },
        "Qu est-ce que c est, jeudi a dix-huit heures ?",
    )

    assert "C'est jeudi" not in held["corrected_answer"]
    # The learner's line stays; the rule pass may still restore its apostrophes.
    assert held["corrected_answer"].replace("'", " ").startswith("Qu est-ce que c est")


def test_a_model_read_feuilleton_answer_counts_and_says_so():
    content = json.dumps(
        {"verdict": "accepted", "score_0_4": 4, "corrected_answer": CLEAN, "why": "", "repair": "", "errata": []}
    )
    correction = _answer(_service(_Llm(content=content)), CLEAN)
    check = verdicts.from_feuilleton(correction, text=CLEAN)

    assert check.outcome is Outcome.RIGHT and check.counts is True
    assert check.checked_by is CheckedBy.MODEL


# --- voice ------------------------------------------------------------------------------------


def test_a_voice_turn_nobody_read_says_so_whatever_the_rules_found():
    empty = verdicts.from_voice(text=CLEAN, errors=[], read=False, failure="TimeoutError: read timed out")
    assert empty.outcome is Outcome.NOT_CHECKED and empty.counts is False
    assert empty.failure is Failure.TIMEOUT

    no_model = verdicts.from_voice(text=CLEAN, errors=[], read=False)
    assert no_model.call is Call.NOT_CALLED and no_model.counts is False

    read = verdicts.from_voice(text=CLEAN, errors=[], read=True)
    assert read.outcome is Outcome.RIGHT and read.counts is True


def test_the_voice_route_sends_the_verdict(monkeypatch):
    """The response model is a whitelist: a field it doesn't name never reaches the page."""

    check = verdicts.from_voice(text=CLEAN, errors=[], read=False, failure="timeout").to_dict()

    class Service:
        def __init__(self, *_a) -> None:
            pass

        async def process_user_response(self, **_k):
            return {"ai_response": "Bien.", "check": check}

    monkeypatch.setattr("app.api.v1.endpoints.audio_session.AudioSessionService", Service)
    response = asyncio.run(
        respond_to_audio(
            request=AudioSessionMessageRequest(session_id=str(uuid4()), user_text=CLEAN),
            db=SimpleNamespace(),
            llm_service=SimpleNamespace(),
            current_user=SimpleNamespace(id=uuid4()),
        )
    )
    assert response.model_dump()["check"] == check


def test_the_detector_reports_a_call_that_did_not_answer():
    from app.core.error_detection.detector import ErrorDetector

    detector = ErrorDetector(llm_service=_Llm(error=TimeoutError("read timed out")))
    result = detector.analyze("Je suis content.", use_llm=True)

    assert "timed out" in result.metadata["llm_failure"]
    assert not result.metadata.get("llm_read")


# --- rehearsal --------------------------------------------------------------------------------


def _debriefing(llm) -> tuple[RehearsalService, SimpleNamespace, SimpleNamespace]:
    service = RehearsalService.__new__(RehearsalService)
    service.db = SimpleNamespace(add=lambda *_a: None, flush=lambda: None, commit=lambda: None)
    service._get_llm_service = lambda: llm
    return service, SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4(), brief={"goal_fr": ""})


def test_a_debrief_line_keeps_the_learners_words(monkeypatch):
    monkeypatch.setattr("app.services.rehearsal._record_cost", lambda *_a, **_k: None)
    content = json.dumps({"corrected_fr": "C'est jeudi à dix-huit heures ?", "note_fr": "Plus naturel.", "already_correct": False})
    service, user, rehearsal = _debriefing(_Llm(content=content))

    correction = service._correct_free_line(user, rehearsal, "Qu est-ce que c est, jeudi a dix-huit heures ?")

    assert "C'est jeudi" not in correction["corrected_fr"]
    # The learner's line stays; the rule pass may still restore its apostrophes.
    assert correction["corrected_fr"].replace("'", " ").startswith("Qu est-ce que c est")


def test_a_debrief_with_no_fix_left_drops_the_note_about_the_change(monkeypatch):
    monkeypatch.setattr("app.services.rehearsal._record_cost", lambda *_a, **_k: None)
    content = json.dumps({"corrected_fr": "J'ai une voiture.", "note_fr": "Dis plutôt voiture.", "already_correct": False})
    service, user, rehearsal = _debriefing(_Llm(content=content))

    correction = service._correct_free_line(user, rehearsal, "J'ai un stylo.")

    assert correction["corrected_fr"] == "J'ai un stylo."
    assert correction["note_fr"] == ""


def test_a_debrief_nobody_read_says_so():
    check = verdicts.from_rehearsal({"free_line": CLEAN, "correction_available": False})
    assert check.outcome is Outcome.NOT_CHECKED and check.counts is False

    read = verdicts.from_rehearsal({"free_line": CLEAN, "correction_available": True, "already_correct": True})
    assert read.outcome is Outcome.RIGHT


def test_the_debrief_page_reads_who_read_the_line():
    assert _debrief_view({}) is None
    assert "check" not in _debrief_view({"outcome": "done", "free_line": ""})

    down = _debrief_view({"free_line": CLEAN, "correction_available": False, "correction_failure": "timeout"})
    assert down["check"]["outcome"] == "not_checked"
    assert (down["check"]["call"], down["check"]["failure"]) == ("failed", "timeout")
    assert down["check"]["counts"] is False

    no_model = _debrief_view({"free_line": CLEAN, "correction_available": False, "correction_failure": "no_model"})
    assert no_model["check"]["call"] == "not_called" and no_model["check"]["retryable"] is False


def test_a_debrief_with_a_fix_is_not_right_whatever_the_model_called_it():
    line = "J'ai appele."
    fixes = correction_contract.verify_correction(line, "J'ai appelé.", []).errata
    assert fixes

    check = verdicts.from_rehearsal(
        {"free_line": line, "correction_available": True, "already_correct": True, "fixes": fixes}
    )
    assert check.outcome is Outcome.NOT_YET and check.corrected == "J'ai appelé."


# --- placement --------------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1.1", "A2.1", "B1.1"])
def test_a_placement_answer_nobody_graded_holds_the_ladder(band):
    assert next_band(band, None) == band


def test_a_placement_answer_nobody_graded_is_not_checked():
    check = verdicts.from_placement(None, failure="TimeoutError: read timed out")
    assert check.outcome is Outcome.NOT_CHECKED and check.counts is False
    assert check.failure is Failure.TIMEOUT
    assert verdicts.from_placement({"score_0_4": 3.5}).outcome is Outcome.RIGHT


# --- what the failure log says ----------------------------------------------------------------


def test_each_surface_failure_is_named_in_the_log(db_session):
    from app.db.models.pilot_event import PilotEvent

    failed = verdicts.from_voice(text=CLEAN, errors=[], read=False, failure="TimeoutError: read timed out")
    verdicts.note_failure(db_session, surface="voice", verdict=failed)

    row = db_session.query(PilotEvent).filter(PilotEvent.event_type == "verdict_check_failed").one()
    assert row.payload == {"surface": "voice", "failure": "timeout"}
