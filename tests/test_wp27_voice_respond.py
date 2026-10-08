"""WP-27 — speaking is the daily journey's default output.

Owner decision, pinned here because it is the kind of thing a later package
would add back in good faith: **speech is never scored for pronunciation.** It
is transcribed and graded as text, exactly like a typed answer.

Three properties:

1. a voice answer is graded identically to the same sentence typed, and the
   evidence records that the capability was demonstrated orally;
2. every transcription call leaves one priced pilot row, declared as an
   estimate rather than passed off as a provider bill;
3. the frontend's spoken path always has a written way out — the fallback is
   source-scanned, because a dead end there is invisible to any API test.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.db.models.pilot_event import PilotEvent
from app.schemas.daily_journey import InputMode
from app.services.journey_contracts import AssistanceLevel, AttemptAnswer
from app.services.journey_learning import classify_observation, is_infrastructure_failure
from app.services.transcription_cost import (
    ASSUMED_BYTES_PER_SECOND,
    MAX_ESTIMATED_SECONDS,
    TRANSCRIPTION_EVENT_TYPE,
    estimate_audio_seconds,
    estimate_transcription_cost_usd,
    record_transcription_cost,
)

REPO = Path(__file__).resolve().parents[1]
JOURNEY = REPO / "web-frontend" / "components" / "atelier-v2" / "journey"


# --------------------------------------------------------------------------
# 1. Voice is a modality, never a second rubric
# --------------------------------------------------------------------------

class _Target:
    kind = "vocab"
    id = "cafe"
    label_fr = "un café"


def _observation(modality: InputMode):
    return classify_observation(
        target=_Target(),
        opportunity="open_production",
        is_correct=True,
        assistance=AssistanceLevel.NONE,
        modality=modality,
        elicited=True,
        learner_text="Je voudrais un café.",
    )


def test_a_spoken_answer_is_graded_exactly_like_the_typed_one():
    spoken = _observation(InputMode.VOICE)
    typed = _observation(InputMode.TEXT)
    assert spoken.evidence_kind == typed.evidence_kind
    assert spoken.learner_text == typed.learner_text
    # The one and only difference is which modality it was demonstrated in.
    assert spoken.modality is InputMode.VOICE
    assert typed.modality is InputMode.TEXT


def test_the_transcript_itself_is_what_the_evidence_keeps():
    """No audio, no score, no pronunciation field — the words, as text."""

    spoken = _observation(InputMode.VOICE)
    assert spoken.learner_text == "Je voudrais un café."
    assert not any(
        "pronunciation" in field or "accent" in field
        for field in getattr(spoken, "model_fields", {})
    )


def test_a_voice_attempt_that_carried_no_words_is_infrastructure_not_a_mistake():
    empty = AttemptAnswer(mode=InputMode.VOICE, text="")
    assert is_infrastructure_failure(empty) is True
    typed_blank = AttemptAnswer(mode=InputMode.TEXT, text="")
    assert is_infrastructure_failure(typed_blank) is False


def test_no_pronunciation_scoring_exists_on_the_journey_voice_path():
    banned = ("pronunciation_score", "accent_score", "phoneme", "pronunciationScore")
    sources = [
        REPO / "app" / "services" / "transcription_cost.py",
        REPO / "app" / "api" / "v1" / "endpoints" / "audio.py",
        JOURNEY / "voice-answer.ts",
        JOURNEY / "useVoiceAnswer.ts",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} scores pronunciation"


# --------------------------------------------------------------------------
# 2. The transcription call is on the ledger, as an estimate
# --------------------------------------------------------------------------

def test_the_estimate_is_derived_from_the_one_thing_measured():
    assert estimate_audio_seconds(ASSUMED_BYTES_PER_SECOND * 10) == 10.0
    assert estimate_audio_seconds(0) == 0.0
    # One oversized upload cannot distort a day's ledger.
    assert estimate_audio_seconds(ASSUMED_BYTES_PER_SECOND * 10_000) == MAX_ESTIMATED_SECONDS
    # Ten seconds of whisper-1 at $0.006/min.
    assert estimate_transcription_cost_usd(ASSUMED_BYTES_PER_SECOND * 10) == 0.001


def test_every_transcription_leaves_one_priced_row_that_declares_its_basis(db_session):
    user_id = uuid4()
    record_transcription_cost(
        db_session,
        user_id=user_id,
        byte_count=ASSUMED_BYTES_PER_SECOND * 30,
        content_type="audio/webm",
        surface="journey_respond",
    )
    db_session.flush()

    row = (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.event_type == TRANSCRIPTION_EVENT_TYPE,
            PilotEvent.user_id == user_id,
        )
        .one()
    )
    assert row.payload["surface"] == "journey_respond"
    assert row.payload["bytes"] == ASSUMED_BYTES_PER_SECOND * 30
    assert row.payload["estimated"] is True
    assert "cost_basis" in row.payload
    assert row.cost_usd > 0.0, "a paid call is never a free row"


def test_telemetry_never_costs_a_learner_their_transcript(db_session):
    record_transcription_cost(
        db_session, user_id="not-a-uuid", byte_count=-1, surface="journey_respond"
    )  # must not raise


def test_the_digest_says_the_money_is_an_estimate(db_session):
    import sys
    from datetime import UTC, datetime

    sys.path.insert(0, str(REPO / "scripts"))
    from pilot_digest import format_transcription_line

    # The digest buckets by the stored UTC date: one timestamp for the rows and
    # the queried day, never the host's local `date.today()` (a day ahead of UTC
    # just after local midnight).
    stamp = datetime.now(UTC)
    user_id = uuid4()
    record_transcription_cost(
        db_session,
        user_id=user_id,
        byte_count=ASSUMED_BYTES_PER_SECOND * 60,
        surface="journey_respond",
    )
    for row in (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == TRANSCRIPTION_EVENT_TYPE)
        .all()
    ):
        row.occurred_at = stamp
    db_session.flush()

    line = format_transcription_line(db_session, stamp.date(), str(user_id))
    assert line.startswith("Transcriptions: 1 calls")
    assert "estimated from upload size" in line
    assert "journey_respond 1" in line


def test_the_transcribe_endpoint_writes_the_row(db_session):
    source = (REPO / "app" / "api" / "v1" / "endpoints" / "audio.py").read_text("utf-8")
    assert "record_transcription_cost" in source
    # After the provider call: a failed request is not billed.
    assert source.index("llm_service.transcribe_audio") < source.index(
        "record_transcription_cost("
    )


# --------------------------------------------------------------------------
# 3. The written way out is always on screen
# --------------------------------------------------------------------------

def test_every_voice_failure_has_a_french_sentence_of_its_own():
    copy = (JOURNEY / "journey-copy.ts").read_text(encoding="utf-8")
    machine = (JOURNEY / "voice-answer.ts").read_text(encoding="utf-8")
    for reason in ("permission", "unsupported", "offline", "empty", "failed"):
        assert f"'{reason}'" in machine or f"{reason}:" in machine
        assert f"voice_{reason}" in copy or reason == "failed"
    french = copy.split("const FR", 1)[1]
    assert "Écrire plutôt" in french
    assert "Parler" in french
    for marker in ("réglages", "Sans connexion", "Répondez par écrit"):
        assert marker in french, f"the French chrome is missing: {marker}"


def test_the_respond_step_keeps_a_written_path_out_of_every_voice_state():
    steps = (JOURNEY / "JourneySteps.tsx").read_text(encoding="utf-8")
    # A refused or unsupported microphone puts the learner on text and
    # remembers it, rather than asking again every turn.
    assert "writeAnswerMode('text')" in steps
    assert "micRefusalExplained()" in steps
    assert "copy.use_text" in steps
    # The transcript is a draft the learner sends, never an auto-submission.
    assert "voice_transcript_hint" in steps
    assert "onSubmit({ mode: submittedMode(voiceState, text), text })" in steps


def test_the_transcript_is_never_submitted_by_the_microphone_itself():
    hook = (JOURNEY / "useVoiceAnswer.ts").read_text(encoding="utf-8")
    assert "submitAnswer" not in hook
    assert "onSubmit" not in hook, "the capture hook must not be able to send an answer"
