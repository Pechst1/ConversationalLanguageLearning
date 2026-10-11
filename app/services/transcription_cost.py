"""WP-27 — the price of speaking, on the ledger.

Making speech the journey's default output makes `POST /audio/transcribe` a
paid endpoint on the learner's main path, and it had no cost telemetry at all:
``PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD`` did not cover it and
``scripts/pilot_digest.py`` had nothing to print. One row per real transcription
call, on the same terms as :mod:`app.services.atelier_correction_cost`.

**The cost here is an estimate, and every row says so.** Whisper is billed per
minute of audio, and its response carries neither a duration nor a usage block —
so unlike the correction row, this one cannot report what the provider charged.
Rather than write a 0.0 that would read as "free", the row prices the request
from the one measurement the endpoint does have, the upload size, against a
declared bitrate, and stamps ``estimated: true`` with the basis beside it. A
reader can tell an estimate from a bill; nobody can mistake this for either
zero or a receipt.
"""
from __future__ import annotations

from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.services.pilot_events import PilotEventService

#: The pilot-ledger event type. `scripts/pilot_digest.py` reads it by name.
TRANSCRIPTION_EVENT_TYPE = "audio_transcription"

#: OpenAI `whisper-1`, US$0.006 per minute of audio (2026-09).
USD_PER_MINUTE = 0.006

#: The recorders in this app capture Opus in WebM or AAC in MP4 and ask for
#: 32 kbit/s (`RECORDER_AUDIO_BITS_PER_SECOND` in web-frontend/lib/audio-recording.ts)
#: — 4,000 bytes per second of audio. Their defaults are not this: Chrome records
#: Opus at 128 kbit/s stereo when nothing is asked. It is the assumption the
#: estimate stands on, so it is written down rather than buried in a magic number.
ASSUMED_BYTES_PER_SECOND = 4000

#: AAC in MP4 when its length cannot be read: AAC encoders ignore the 32 kbit/s the
#: recorder asks for (measured 2026-10-09: Chrome 13.7 kB/s, iOS 26 Safari 20 kB/s).
AAC_ASSUMED_BYTES_PER_SECOND = 20000

#: The fastest any recorder writes (iOS 26 Safari's default Opus: 21.8 kB/s), with
#: room. A length read from the container is never taken below ``bytes / this``,
#: so a large file cannot declare itself short.
MAX_PLAUSIBLE_BYTES_PER_SECOND = 32000
_AAC_CONTENT_TYPES = frozenset({"audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac"})

#: Nothing a learner says in one journey turn runs longer than this. A file that
#: implies more is a long upload, not a long turn, and the estimate is capped so
#: one large request cannot distort a day's ledger.
MAX_ESTIMATED_SECONDS = 300.0


def assumed_bytes_per_second(content_type: str | None = None) -> int:
    """The byte rate an upload of this content type is sized at."""

    mime = (content_type or "").partition(";")[0].strip().lower()
    return AAC_ASSUMED_BYTES_PER_SECOND if mime in _AAC_CONTENT_TYPES else ASSUMED_BYTES_PER_SECOND


def estimate_audio_seconds(
    byte_count: int, content_type: str | None = None, *, measured_seconds: float | None = None
) -> float:
    """Seconds of audio in an upload of ``byte_count`` bytes.

    ``measured_seconds`` is the length read from the container
    (:func:`app.services.audio_duration.audio_seconds`); without it the bytes are
    sized at the content type's assumed rate."""

    bytes_ = max(0, int(byte_count))
    if measured_seconds is not None:
        seconds = max(float(measured_seconds), bytes_ / float(MAX_PLAUSIBLE_BYTES_PER_SECOND))
    else:
        seconds = bytes_ / float(assumed_bytes_per_second(content_type))
    return min(seconds, MAX_ESTIMATED_SECONDS)


def estimate_transcription_cost_usd(
    byte_count: int, content_type: str | None = None, *, measured_seconds: float | None = None
) -> float:
    """The declared estimate, in dollars, for one transcription request."""

    seconds = estimate_audio_seconds(byte_count, content_type, measured_seconds=measured_seconds)
    return round(seconds * USD_PER_MINUTE / 60.0, 6)


def record_transcription_cost(
    db: Session,
    *,
    user_id: UUID | None,
    byte_count: int,
    content_type: str | None = None,
    measured_seconds: float | None = None,
    surface: str = "unknown",
    entity_type: str = "audio_upload",
    entity_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """One pilot-cost row per real transcription call.

    ``surface`` names where the learner was speaking — ``journey_respond`` for
    WP-27's default output — so the digest can tell the daily Séance's spend
    from the Studio's. Telemetry must never cost a learner their answer, so a
    failure to write the row is logged and swallowed. The caller's transaction
    owns the commit; nothing is committed here.

    WP-158: a spoken story reply books its row against the turn
    (``entity_type="journey_turn"``, ``entity_id="<step>:<turn>"``) so the
    per-turn cost ceiling can be summed; ``extra`` adds its references.
    """

    try:
        PilotEventService(db).record(
            TRANSCRIPTION_EVENT_TYPE,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload={
                **(extra or {}),
                "surface": str(surface or "unknown"),
                "content_type": str(content_type or ""),
                "bytes": max(0, int(byte_count)),
                "estimated_seconds": round(
                    estimate_audio_seconds(byte_count, content_type, measured_seconds=measured_seconds), 3
                ),
                # The two fields that keep this row honest: the price is a
                # model, not a bill, and the model is named.
                "estimated": True,
                "cost_basis": (
                    f"container·${USD_PER_MINUTE}/min"
                    if measured_seconds is not None
                    else f"bytes@{assumed_bytes_per_second(content_type)}Bps·${USD_PER_MINUTE}/min"
                ),
            },
            cost_usd=estimate_transcription_cost_usd(
                byte_count, content_type, measured_seconds=measured_seconds
            ),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Transcription cost row could not be written")


__all__ = [
    "AAC_ASSUMED_BYTES_PER_SECOND",
    "ASSUMED_BYTES_PER_SECOND",
    "MAX_PLAUSIBLE_BYTES_PER_SECOND",
    "assumed_bytes_per_second",
    "MAX_ESTIMATED_SECONDS",
    "TRANSCRIPTION_EVENT_TYPE",
    "USD_PER_MINUTE",
    "estimate_audio_seconds",
    "estimate_transcription_cost_usd",
    "record_transcription_cost",
]
