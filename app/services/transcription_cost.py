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

#: The recorders in this app capture Opus in WebM or AAC in MP4, both around
#: 32 kbit/s mono at their default settings — 4,000 bytes per second of audio.
#: It is the assumption the estimate stands on, so it is written down rather
#: than buried in a magic number.
ASSUMED_BYTES_PER_SECOND = 4000

#: Nothing a learner says in one journey turn runs longer than this. A file that
#: implies more is a long upload, not a long turn, and the estimate is capped so
#: one large request cannot distort a day's ledger.
MAX_ESTIMATED_SECONDS = 300.0


def estimate_audio_seconds(byte_count: int) -> float:
    """Seconds of audio implied by an upload of ``byte_count`` bytes."""

    seconds = max(0, int(byte_count)) / float(ASSUMED_BYTES_PER_SECOND)
    return min(seconds, MAX_ESTIMATED_SECONDS)


def estimate_transcription_cost_usd(byte_count: int) -> float:
    """The declared estimate, in dollars, for one transcription request."""

    return round(estimate_audio_seconds(byte_count) * USD_PER_MINUTE / 60.0, 6)


def record_transcription_cost(
    db: Session,
    *,
    user_id: UUID | None,
    byte_count: int,
    content_type: str | None = None,
    surface: str = "unknown",
) -> None:
    """One pilot-cost row per real transcription call.

    ``surface`` names where the learner was speaking — ``journey_respond`` for
    WP-27's default output — so the digest can tell the daily Séance's spend
    from the Studio's. Telemetry must never cost a learner their answer, so a
    failure to write the row is logged and swallowed. The caller's transaction
    owns the commit; nothing is committed here.
    """

    try:
        PilotEventService(db).record(
            TRANSCRIPTION_EVENT_TYPE,
            user_id=user_id,
            entity_type="audio_upload",
            entity_id=None,
            payload={
                "surface": str(surface or "unknown"),
                "content_type": str(content_type or ""),
                "bytes": max(0, int(byte_count)),
                "estimated_seconds": round(estimate_audio_seconds(byte_count), 3),
                # The two fields that keep this row honest: the price is a
                # model, not a bill, and the model is named.
                "estimated": True,
                "cost_basis": f"bytes@{ASSUMED_BYTES_PER_SECOND}Bps·${USD_PER_MINUTE}/min",
            },
            cost_usd=estimate_transcription_cost_usd(byte_count),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Transcription cost row could not be written")


__all__ = [
    "ASSUMED_BYTES_PER_SECOND",
    "MAX_ESTIMATED_SECONDS",
    "TRANSCRIPTION_EVENT_TYPE",
    "USD_PER_MINUTE",
    "estimate_audio_seconds",
    "estimate_transcription_cost_usd",
    "record_transcription_cost",
]
