"""WP-32 — «Écouter d'abord»: the day's scene as a radio episode.

The evidence this package rests on is *not* "audio helps". Metacognitive
listening instruction — **predict → listen → verify → debrief** — has a
consistent moderate effect, largest for the weakest listeners (Vandergrift &
Tafaghodtari 2010; Vandergrift & Goh 2012). Audio on its own is where most
apps stop, and it is the part of the cycle that does the least. This module
owns only the *listen* stage's raw material: the same scene the reader already
publishes, spoken line by line, one voice per speaker.

Everything here is written to be cheap to be wrong about:

* **The flag gates the first line, not the last.** With
  ``ATELIER_EPISODE_AUDIO_ENABLED`` false nothing is read, nothing is
  synthesized, nothing is billed, and the caller gets ``status="disabled"`` —
  which the frontend renders as the ordinary text scene.
* **Cached per scene revision.** ``scene_revision`` digests the exact text,
  voices and model. A regenerated scene or one corrected line is a new
  revision; a replay of the same revision makes no call and writes no cost row.
* **The price is an estimate and says so.** OpenAI's speech endpoint returns
  audio and no usage block, so — exactly as
  :mod:`app.services.transcription_cost` does for Whisper — the row is priced
  from the character count against a declared rate and stamped
  ``estimated: true`` with its basis beside it. A reader can tell an estimate
  from a bill; nobody can mistake this for either zero or a receipt.
* **Silence is a state, not a half-episode.** If any line fails, the run is
  ``failed`` and the manifest carries no clips: half a scene played aloud is
  a comprehension test the learner cannot pass. Whatever was already paid for
  stays cached, so the retry costs less than the first attempt, not more.

The provider is pinned to OpenAI on purpose — see :data:`TTS_PROVIDER`.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.episode_audio import EpisodeAudioClip
from app.db.models.graphic_novel import GraphicNovelScene
from app.services.pilot_events import PilotEventService

#: The pilot-ledger event type. `scripts/pilot_digest.py` reads it by name.
EPISODE_AUDIO_EVENT_TYPE = "episode_audio_synthesis"

#: The TTS provider this package uses, regardless of ``settings.TTS_PROVIDER``.
#:
#: The deployed configuration names ElevenLabs, whose plan currently answers
#: 402. Every other TTS call site in the app degrades from that to OpenAI *after*
#: a failed request; on the learner's daily path that is a wasted round trip and
#: a silent character. The radio episode asks OpenAI directly. Changing the
#: default provider is a configuration decision and belongs in configuration —
#: this constant only says which path this feature was tested on.
TTS_PROVIDER = "openai"

#: OpenAI's speech voices. ``fable`` is reserved for narration so the narrator
#: is never mistaken for a character.
NARRATOR_VOICE = "fable"
CHARACTER_VOICES: tuple[str, ...] = ("alloy", "echo", "nova", "onyx", "shimmer")

#: The id used for narration lines, in the manifest and in the cache.
NARRATOR_ID = "narrator"

#: The recurring cast, pinned so a character keeps their voice across days —
#: recognising who is speaking before understanding what they said is half of
#: what the listen stage trains. Matching is on the id's first token, so
#: ``marin_leveque`` and ``marin`` are the same person.
#:
#: There are five character voices and the cast can grow past five, so two
#: characters may end up sharing one. That is why the écouter stage shows the
#: speaker's *name* while hiding their words: the voice is a cue, never the
#: only carrier of who is talking.
PINNED_VOICES: dict[str, str] = {
    "romy": "shimmer",
    "lila": "nova",
    "marin": "onyx",
    "marchand": "echo",
    "landlord": "echo",
    "margaux": "alloy",
    "augustin": "alloy",
    "gus": "alloy",
    # The learner's own line in the script.
    "toi": "nova",
    "learner": "nova",
    "you": "nova",
}

#: Nothing shorter than this is worth a request: a stage direction fragment or
#: an empty string costs a round trip and teaches nothing.
MIN_LINE_CHARS = 2


class Synthesizer(Protocol):
    """What this module needs from a text-to-speech provider."""

    def text_to_speech(
        self, text: str, voice: str = ..., model: str | None = ..., provider: str | None = ...
    ) -> bytes: ...


@dataclass(frozen=True)
class EpisodeLine:
    """One line of the episode as it will be spoken."""

    key: str
    ordinal: int
    character_id: str
    voice: str
    text_fr: str

    @property
    def char_count(self) -> int:
        return len(self.text_fr)


@dataclass
class EpisodeAudioResult:
    """The manifest one request produces.

    ``status`` is the whole contract:

    ``disabled``  the flag is off. No read, no call, no row.
    ``empty``     the scene has no speakable line. Not a failure.
    ``ready``     every line has audio.
    ``failed``    at least one line could not be synthesized; ``clips`` is empty.
    """

    status: str
    revision: str = ""
    clips: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    reason: str = ""
    synthesized_lines: int = 0
    synthesized_chars: int = 0
    cached_lines: int = 0

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "revision": self.revision,
            "clips": self.clips,
            "truncated": self.truncated,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Which lines, in which voice
# ---------------------------------------------------------------------------


def voice_for_character(character_id: str | None) -> str:
    """The voice a speaker keeps, for the life of the cast.

    Deterministic in both branches: a pinned id maps by its first token, and
    anything else — a generated cast member — hashes into the same five voices.
    A generated character therefore also keeps one voice across days, which a
    round-robin over the scene's speakers would not.
    """

    raw = str(character_id or "").strip().lower()
    if not raw or raw == NARRATOR_ID:
        return NARRATOR_VOICE
    head = raw.split("_", 1)[0]
    pinned = PINNED_VOICES.get(raw) or PINNED_VOICES.get(head)
    if pinned:
        return pinned
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return CHARACTER_VOICES[digest[0] % len(CHARACTER_VOICES)]


def episode_lines(scene: GraphicNovelScene) -> list[EpisodeLine]:
    """Every speakable line of the scene, in playback order.

    The keys are derived from the panel id and the line's position in the
    panel's *raw* dialogue array — the same two facts the published episode
    carries — so the frontend computes identical keys without an index
    negotiation, and an empty line filtered out of the reader does not shift
    the keys of the lines after it.
    """

    lines: list[EpisodeLine] = []
    panels = sorted(scene.panels or [], key=lambda panel: panel.panel_index)
    for panel in panels:
        overlay = panel.overlay_payload if isinstance(panel.overlay_payload, dict) else {}
        narration = str(overlay.get("narration_fr") or "").strip()
        if len(narration) >= MIN_LINE_CHARS:
            lines.append(
                EpisodeLine(
                    key=f"{panel.id}:n",
                    ordinal=len(lines),
                    character_id=NARRATOR_ID,
                    voice=NARRATOR_VOICE,
                    text_fr=narration,
                )
            )
        dialogue = overlay.get("dialogue")
        if not isinstance(dialogue, list):
            continue
        for index, entry in enumerate(dialogue):
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text_fr") or "").strip()
            if len(text) < MIN_LINE_CHARS:
                continue
            character_id = str(entry.get("character_id") or "").strip()
            lines.append(
                EpisodeLine(
                    key=f"{panel.id}:l{index}",
                    ordinal=len(lines),
                    character_id=character_id,
                    voice=voice_for_character(character_id),
                    text_fr=text,
                )
            )
    return lines


def bound_lines(
    lines: list[EpisodeLine], *, max_chars: int | None = None
) -> tuple[list[EpisodeLine], bool]:
    """Cut the episode to the per-scene character budget.

    Whole lines only: half a spoken sentence is worse than a missing one. The
    truncation is returned rather than hidden, and the caller declares it in the
    manifest so the learner is never told they heard an episode they did not.
    """

    budget = settings.FEUILLETON_AUDIO_MAX_CHARS_PER_SCENE if max_chars is None else max_chars
    budget = max(0, int(budget or 0))
    if not budget:
        return list(lines), False
    kept: list[EpisodeLine] = []
    spent = 0
    for line in lines:
        if spent + line.char_count > budget:
            return kept, True
        kept.append(line)
        spent += line.char_count
    return kept, False


def scene_revision(lines: list[EpisodeLine], *, model: str) -> str:
    """A digest of exactly what would be spoken, and how.

    The cache key. Text, speaker, voice, order and TTS model all enter it, so a
    rewritten line, a re-cast character or a model change all invalidate the
    audio rather than letting yesterday's recording play under today's words.
    """

    digest = hashlib.sha256()
    digest.update(f"episode-audio-v1|{model}|".encode())
    for line in lines:
        digest.update(f"{line.key}|{line.character_id}|{line.voice}|{line.text_fr}\n".encode())
    return digest.hexdigest()[:32]


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def estimate_synthesis_cost_usd(char_count: int) -> float:
    """The declared estimate, in dollars, for ``char_count`` spoken characters."""

    rate = float(settings.FEUILLETON_AUDIO_COST_USD_PER_1K_CHARS or 0.0)
    return round(max(0, int(char_count)) / 1000.0 * rate, 6)


def record_episode_audio_cost(
    db: Session,
    *,
    user_id: UUID | None,
    scene_id: UUID | None,
    revision: str,
    model: str,
    lines: int,
    chars: int,
    cached_lines: int,
    voices: list[str],
    status: str,
) -> None:
    """One priced pilot row per run that actually synthesized something.

    A run served entirely from cache writes nothing: a row with a zero on it
    would read as a free call rather than as no call at all, and the digest's
    cost-per-learner would quietly dilute.

    Telemetry must never cost a learner their episode, so a failure to write is
    logged and swallowed. The caller's transaction owns the commit.
    """

    try:
        PilotEventService(db).record(
            EPISODE_AUDIO_EVENT_TYPE,
            user_id=user_id,
            entity_type="story_scene",
            entity_id=scene_id,
            payload={
                "surface": "journey_episode_radio",
                "provider": TTS_PROVIDER,
                "model": model,
                "revision": revision,
                "lines": int(lines),
                "chars": int(chars),
                "cached_lines": int(cached_lines),
                "voices": sorted(set(voices)),
                "status": status,
                # The two fields that keep this row honest: the speech endpoint
                # returns audio and no usage block, so the price is a model, and
                # the model is named.
                "estimated": True,
                "cost_basis": (
                    f"chars@${settings.FEUILLETON_AUDIO_COST_USD_PER_1K_CHARS}/1k"
                ),
            },
            cost_usd=estimate_synthesis_cost_usd(chars),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Episode audio cost row could not be written")


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


def cached_clips(
    db: Session, *, scene_id: UUID, revision: str
) -> dict[str, EpisodeAudioClip]:
    """Every stored clip for one revision, keyed by line."""

    rows = db.scalars(
        select(EpisodeAudioClip).where(
            EpisodeAudioClip.scene_id == scene_id,
            EpisodeAudioClip.revision == revision,
        )
    )
    return {row.line_key: row for row in rows}


def _manifest_entry(clip: EpisodeAudioClip) -> dict[str, Any]:
    """What crosses the wire for one clip.

    The bytes do not: the manifest carries an id the player fetches, so a scene
    with a dozen lines is a dozen small cacheable responses rather than one
    multi-megabyte JSON body. ``text_fr`` is included because the *vérifier*
    stage reveals exactly what was spoken — the frontend must not have to guess
    which line it just heard.
    """

    return {
        "id": str(clip.id),
        "line_key": clip.line_key,
        "ordinal": int(clip.ordinal),
        "character_id": clip.character_id,
        "voice": clip.voice,
        "content_type": clip.content_type,
        "char_count": int(clip.char_count),
        "text_fr": clip.text_fr,
    }


def episode_audio_manifest(
    db: Session, *, scene: GraphicNovelScene
) -> EpisodeAudioResult:
    """The cached manifest, without ever synthesizing anything.

    The read half of the endpoint: it answers "is this episode already spoken?"
    for a client that would rather show the text path than start a paid call.
    """

    if not settings.ATELIER_EPISODE_AUDIO_ENABLED:
        return EpisodeAudioResult(status="disabled", reason="flag_off")
    lines, truncated = bound_lines(episode_lines(scene))
    if not lines:
        return EpisodeAudioResult(status="empty", reason="no_speakable_line")
    model = settings.FEUILLETON_AUDIO_TTS_MODEL
    revision = scene_revision(lines, model=model)
    stored = cached_clips(db, scene_id=scene.id, revision=revision)
    missing = [line for line in lines if line.key not in stored]
    if missing:
        return EpisodeAudioResult(
            status="absent",
            revision=revision,
            truncated=truncated,
            reason="not_synthesized",
            cached_lines=len(stored),
        )
    return EpisodeAudioResult(
        status="ready",
        revision=revision,
        clips=[_manifest_entry(stored[line.key]) for line in lines],
        truncated=truncated,
        cached_lines=len(stored),
    )


def synthesize_episode_audio(
    db: Session,
    *,
    scene: GraphicNovelScene,
    synthesizer: Synthesizer | None = None,
    llm_factory: Callable[[], Synthesizer] | None = None,
) -> EpisodeAudioResult:
    """Speak the scene, or say honestly that it is not spoken.

    Order of refusals matters and is the cheap-to-be-wrong part: the flag first
    (no read, no call), then the cache (no call), then the budget, and only then
    a provider. Lines already stored for this revision are never re-requested,
    so a retry after a partial failure pays only for what is still missing.
    """

    if not settings.ATELIER_EPISODE_AUDIO_ENABLED:
        return EpisodeAudioResult(status="disabled", reason="flag_off")

    lines, truncated = bound_lines(episode_lines(scene))
    if not lines:
        return EpisodeAudioResult(status="empty", reason="no_speakable_line")

    model = settings.FEUILLETON_AUDIO_TTS_MODEL
    revision = scene_revision(lines, model=model)
    stored = cached_clips(db, scene_id=scene.id, revision=revision)
    missing = [line for line in lines if line.key not in stored]

    if not missing:
        return EpisodeAudioResult(
            status="ready",
            revision=revision,
            clips=[_manifest_entry(stored[line.key]) for line in lines],
            truncated=truncated,
            cached_lines=len(stored),
        )

    provider = synthesizer
    if provider is None:
        try:
            provider = (llm_factory or _default_synthesizer)()
        except Exception as exc:  # pragma: no cover - configuration failure
            logger.warning("Episode audio synthesizer unavailable: {}", exc)
            return EpisodeAudioResult(
                status="failed", revision=revision, reason="tts_unavailable"
            )

    synthesized = 0
    chars = 0
    for line in missing:
        try:
            audio = provider.text_to_speech(
                text=line.text_fr,
                voice=line.voice,
                model=model,
                provider=TTS_PROVIDER,
            )
        except Exception as exc:
            logger.warning(
                "Episode audio synthesis failed",
                scene_id=str(scene.id),
                line=line.key,
                error=str(exc),
            )
            # Whatever was synthesized before the failure is already flushed and
            # paid for; it stays cached so the retry is cheaper. But a partial
            # episode is never *played*: the manifest carries no clips.
            _bill(
                db,
                scene=scene,
                revision=revision,
                model=model,
                lines=synthesized,
                chars=chars,
                cached_lines=len(stored),
                voices=[item.voice for item in missing[:synthesized]],
                status="failed",
            )
            return EpisodeAudioResult(
                status="failed",
                revision=revision,
                reason="tts_failed",
                truncated=truncated,
                synthesized_lines=synthesized,
                synthesized_chars=chars,
                cached_lines=len(stored),
            )
        if not audio:
            _bill(
                db,
                scene=scene,
                revision=revision,
                model=model,
                lines=synthesized,
                chars=chars,
                cached_lines=len(stored),
                voices=[item.voice for item in missing[:synthesized]],
                status="failed",
            )
            return EpisodeAudioResult(
                status="failed",
                revision=revision,
                reason="tts_empty",
                truncated=truncated,
                synthesized_lines=synthesized,
                synthesized_chars=chars,
                cached_lines=len(stored),
            )
        clip = EpisodeAudioClip(
            scene_id=scene.id,
            user_id=scene.user_id,
            revision=revision,
            line_key=line.key,
            ordinal=line.ordinal,
            character_id=line.character_id,
            voice=line.voice,
            model=model,
            text_fr=line.text_fr,
            char_count=line.char_count,
            content_type="audio/mpeg",
            audio=bytes(audio),
        )
        db.add(clip)
        db.flush()
        stored[line.key] = clip
        synthesized += 1
        chars += line.char_count

    _bill(
        db,
        scene=scene,
        revision=revision,
        model=model,
        lines=synthesized,
        chars=chars,
        cached_lines=len(lines) - synthesized,
        voices=[line.voice for line in missing],
        status="ready",
    )
    return EpisodeAudioResult(
        status="ready",
        revision=revision,
        clips=[_manifest_entry(stored[line.key]) for line in lines],
        truncated=truncated,
        synthesized_lines=synthesized,
        synthesized_chars=chars,
        cached_lines=len(lines) - synthesized,
    )


def _bill(
    db: Session,
    *,
    scene: GraphicNovelScene,
    revision: str,
    model: str,
    lines: int,
    chars: int,
    cached_lines: int,
    voices: list[str],
    status: str,
) -> None:
    """Write the cost row only when a paid call was actually made."""

    if lines <= 0:
        return
    record_episode_audio_cost(
        db,
        user_id=scene.user_id,
        scene_id=scene.id,
        revision=revision,
        model=model,
        lines=lines,
        chars=chars,
        cached_lines=cached_lines,
        voices=voices,
        status=status,
    )


def _default_synthesizer() -> Synthesizer:
    from app.services.llm_service import LLMService

    return LLMService()


# ---------------------------------------------------------------------------
# The prediction check — measurement, not a quiz
# ---------------------------------------------------------------------------

#: The pilot-ledger event type for one recorded prediction check. Free.
PREDICTION_EVENT_TYPE = "episode_audio_prediction"

#: What the *vérifier* stage concluded. ``unresolved`` is a real answer: a scene
#: whose stored lines settle neither way must not be scored either way.
PREDICTION_VERDICTS = ("confirmed", "other", "unresolved")


def record_prediction_check(
    db: Session,
    *,
    scene: GraphicNovelScene,
    guess: str,
    verdict: str,
    supported: str | None = None,
) -> dict[str, Any]:
    """Store what the learner predicted and what the scene turned out to say.

    Deliberately **not** a grade and deliberately **not** evidence:

    * it never reaches ``DailyJourneyStep`` or the capability rubric — the
      product's one rubric is scored from what the learner *produces*, and a
      tapped guess is not production. Two rubrics is exactly how
      ``recap.capability_evidence`` and ``GET /capabilities/progress`` once came
      to disagree about the same journey (CONTRACTS §8);
    * it never becomes a right/wrong verdict on screen. WP-32's acceptance says
      comprehension is measured by the prediction check and by the next scene's
      respond evidence, *not by a quiz*.

    It is evidence-*adjacent* metadata: it lives beside the scene, next to the
    reading position the reader already stores there, and it exists so that a
    pilot can ask whether listening-first learners predicted better over two
    weeks. A guess the scene does not settle is stored as ``unresolved`` rather
    than silently dropped — the denominator matters as much as the numerator.
    """

    clean_verdict = str(verdict or "").strip().lower()
    if clean_verdict not in PREDICTION_VERDICTS:
        clean_verdict = "unresolved"
    entry = {
        "guess": str(guess or "").strip()[:40],
        "verdict": clean_verdict,
        "supported": str(supported or "").strip()[:40] or None,
    }
    snapshot = dict(scene.source_snapshot or {})
    radio = dict(snapshot.get("radio") or {})
    radio["prediction"] = entry
    snapshot["radio"] = radio
    scene.source_snapshot = snapshot
    try:
        PilotEventService(db).record(
            PREDICTION_EVENT_TYPE,
            user_id=scene.user_id,
            entity_type="story_scene",
            entity_id=scene.id,
            payload={"surface": "journey_episode_radio", **entry},
            cost_usd=0.0,
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Episode prediction row could not be written")
    return entry


__all__ = [
    "CHARACTER_VOICES",
    "EPISODE_AUDIO_EVENT_TYPE",
    "PREDICTION_EVENT_TYPE",
    "PREDICTION_VERDICTS",
    "record_prediction_check",
    "EpisodeAudioResult",
    "EpisodeLine",
    "MIN_LINE_CHARS",
    "NARRATOR_ID",
    "NARRATOR_VOICE",
    "PINNED_VOICES",
    "TTS_PROVIDER",
    "bound_lines",
    "cached_clips",
    "episode_audio_manifest",
    "episode_lines",
    "estimate_synthesis_cost_usd",
    "record_episode_audio_cost",
    "scene_revision",
    "synthesize_episode_audio",
    "voice_for_character",
]
