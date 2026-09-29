"""WP-91 «Les voix» — one line of the learner's day, spoken in its character's voice.

Two doors, one cache:

* ``POST /daily-journeys/{journey_id}/steps/{step_id}/line-audio`` — the
  portrait-as-play-button. The client names a line it is showing; the server
  speaks it only if that exact line appears in that step *for this learner*
  (:func:`step_lines`). Arbitrary text is a 404, never a synthesis: this is a
  voice for the day's characters, not a free text-to-speech endpoint.
* ``GET /daily-journeys/line-audio/{clip_id}`` — the bytes. A clip the learner
  already owns is served as is. A listening item's clip (``listen_tap``,
  ``dictation``), which the planner names by id without paying for it, is
  spoken on its first request (:func:`planned_line`) — so a day costs audio only
  for the items actually opened.

The rules are the radio episode's (:mod:`app.services.episode_audio`), kept on
purpose: OpenAI only (:data:`episode_audio.TTS_PROVIDER`); the flag gates the
first line, not the last (off: nothing read, nothing called, nothing billed —
``disabled`` for the client, which then uses the device's voice); a replay makes
no call and writes no row; every synthesis is priced on the pilot ledger as an
estimate that says so (``estimated: true`` with its basis).

**WP-103 T1 — a clip is «this line, in this voice, spoken this way».** The clip
*id* stays ``{voice}-{digest}`` (the planner names listening clips by it, days in
advance), but the cache row is keyed by the **speech spec** as well
(:attr:`cast_voices.SpeechSpec.cache_key`: model, instructions version, pace, a
digest of the instructions and speed sent), stored in the row's ``model`` column
— so a change of model, wording or band pace means the old clip is simply not
found, and no migration is needed. A clip made before this change (its ``model``
is a bare ``tts-1-hd``) is never served again. If the steerable model errors the
line falls back to ``tts-1-hd`` once (logged) and *that* clip is cached under the
fallback's own key, which is also accepted on lookup: an outage must not mean a
paid call for the same line on every replay.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.line_audio import LineAudioClip
from app.services.cast_voices import (
    FALLBACK_SPEECH_MODEL,
    LINE_AUDIO_PATH_PREFIX,
    NARRATOR_ID,
    SPEECH_INSTRUCTIONS_VERSION,
    cache_key_is_current,
    cast_id_for,
    clip_id_for,
    model_of_cache_key,
    normalize_line_text,
    pace_for_band,
    parse_cache_key,
    voice_for_character,
    voice_of_clip_id,
)
from app.services.episode_audio import (
    TTS_PROVIDER,
    Synthesizer,
    episode_lines,
    estimate_synthesis_cost_usd,
    speak_text,
    spec_for,
)
from app.services.pilot_events import PilotEventService

#: The pilot-ledger event type for one line that was actually synthesized.
LINE_AUDIO_EVENT_TYPE = "line_audio_synthesis"

#: A voice is a pleasure, the day is the product: once a learner's spend today
#: reaches this share of the daily cap, a line that is not already cached is
#: answered ``disabled`` and the device voice reads it. Cached lines still play.
CAP_NEAR_SHARE = 0.9

#: How far back a planned listening clip is looked for (journeys, newest first):
#: today's day, and yesterday's for a learner finishing it after midnight.
PLANNED_CLIP_JOURNEYS = 3

#: Recall formats whose ``audio_url`` names a clip the ``GET`` may speak.
_PLANNED_FORMATS = ("listen_tap", "dictation")


@dataclass(frozen=True, slots=True)
class StepLine:
    """A line the learner can see in a step: who says it, and exactly what."""

    character_id: str
    text_fr: str

    @property
    def voice(self) -> str:
        return voice_for_character(self.character_id)


@dataclass(frozen=True, slots=True)
class LineAudioOutcome:
    """``ready`` with its clip, or ``disabled`` with the reason (never shown)."""

    status: str
    clip: LineAudioClip | None = None
    cached: bool = False
    reason: str = ""

    def as_payload(self) -> dict[str, Any]:
        if self.status != "ready" or self.clip is None:
            return {"status": "disabled"}
        return {
            "status": "ready",
            "clip_id": self.clip.clip_id,
            "content_type": self.clip.content_type or "audio/mpeg",
            "voice": self.clip.voice,
            "cached": bool(self.cached),
        }


# ---------------------------------------------------------------------------
# Which lines a step shows
# ---------------------------------------------------------------------------


def _match_form(text: str | None) -> str:
    """How a requested text is compared with a step's lines: quotes, spaces
    and case folded, surrounding guillemets dropped. Accents are kept."""

    return normalize_line_text(text).strip("«»\"' ").casefold()


def _add(lines: list[StepLine], character_id: Any, text: Any) -> None:
    clean = normalize_line_text(str(text or "")).strip()
    if len(clean) >= 2:
        lines.append(StepLine(str(character_id or NARRATOR_ID), clean))


def _scene_step(journey: DailyJourney) -> DailyJourneyStep | None:
    return next((step for step in journey.steps if step.kind == "scene"), None)


def _brief(journey: DailyJourney) -> dict[str, Any]:
    scene = _scene_step(journey)
    private = scene.private_task if scene is not None and isinstance(scene.private_task, dict) else {}
    brief = private.get("scenario_brief")
    return brief if isinstance(brief, dict) else {}


def _scene_lines(db: Session, journey: DailyJourney, step: DailyJourneyStep) -> list[StepLine]:
    """The bound scene's dialogue and narration, its panels, and what the
    scene step prints (the setup and the character's line)."""

    lines: list[StepLine] = []
    prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
    brief = _brief(journey)
    speaker = brief.get("character_id") or NARRATOR_ID
    _add(lines, speaker, prompt.get("character_line_fr"))
    _add(lines, speaker, brief.get("opening_line_fr"))
    _add(lines, NARRATOR_ID, prompt.get("setup_fr"))
    for panel in [*(prompt.get("panels") or []), *(brief.get("panels") or [])]:
        if not isinstance(panel, dict):
            continue
        _add(lines, NARRATOR_ID, panel.get("narration_fr"))
        for entry in panel.get("dialogue") or []:
            if isinstance(entry, dict):
                _add(lines, entry.get("character_id"), entry.get("text_fr"))
    story = brief.get("story_context") if isinstance(brief.get("story_context"), dict) else {}
    draft = story.get("draft") if isinstance(story.get("draft"), dict) else {}
    _add(lines, draft.get("character_id") or speaker, draft.get("opening_line_fr"))
    for panel in draft.get("panels") or []:
        if not isinstance(panel, dict):
            continue
        _add(lines, NARRATOR_ID, panel.get("narration_fr"))
        for entry in panel.get("dialogue") or []:
            if isinstance(entry, dict):
                _add(lines, entry.get("character_id"), entry.get("text_fr"))
    scene_id = story.get("scene_id")
    if scene_id:
        try:
            scene = db.get(GraphicNovelScene, uuid.UUID(str(scene_id)))
        except (ValueError, TypeError):
            scene = None
        # The scene the day is bound to, and only if it is this learner's.
        if scene is not None and scene.user_id == journey.user_id:
            for line in episode_lines(scene):
                _add(lines, line.character_id, line.text_fr)
    return lines


def step_lines(db: Session, journey: DailyJourney, step: DailyJourneyStep) -> list[StepLine]:
    """Every line the learner can see in this step — the only lines it may speak.

    * scene: the bound scene's dialogue and narration and its panels;
    * respond: the character's line, every reply in the thread, and the
      latest one (the respond prompt's ``character_line_fr``);
    * resolution: the ending's line;
    * rule (WP-92): the scene's line on the card (``scene_example_fr``);
    * read (WP-93): the lines of the page the «Lecture» shows.
    Any other step speaks nothing through this door.
    """

    kind = str(step.kind)
    prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
    if kind == "scene":
        return _scene_lines(db, journey, step)
    lines: list[StepLine] = []
    if kind == "respond":
        speaker = prompt.get("character_id") or _brief(journey).get("character_id")
        _add(lines, speaker, prompt.get("character_line_fr"))
        private = step.private_task if isinstance(step.private_task, dict) else {}
        for turn in private.get("turns") or []:
            if isinstance(turn, dict):
                _add(lines, speaker, turn.get("character"))
        return lines
    if kind == "resolution":
        _add(lines, _brief(journey).get("character_id"), prompt.get("character_line_fr"))
        return lines
    if kind == "rule":
        # WP-92: the scene's own line on the rule card, said by its speaker.
        example = str(prompt.get("scene_example_fr") or "").replace("[", "").replace("]", "")
        _add(lines, prompt.get("scene_example_speaker") or NARRATOR_ID, example)
        return lines
    if kind == "read":
        return _read_lines(db, journey, step)
    return lines


def _read_lines(db: Session, journey: DailyJourney, step: DailyJourneyStep) -> list[StepLine]:
    """WP-93 «Lecture»: the page the READ step may show — yesterday's page it
    named, or today's «Coulisses» once written — and only this learner's."""

    prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
    private = step.private_task if isinstance(step.private_task, dict) else {}
    relecture = private.get("relecture") if isinstance(private.get("relecture"), dict) else {}
    ids = [prompt.get("scene_id"), relecture.get("scene_id")]
    # WP-93: the earlier pages the day named — a READ step shows one of them
    # when «coulisses» gives its place away.
    ids.extend(
        page.get("scene_id")
        for page in private.get("relectures") or []
        if isinstance(page, dict)
    )
    if private.get("variant") == "coulisses" or prompt.get("variant") == "coulisses":
        try:
            from app.services.coulisses import coulisses_scene_for

            side = coulisses_scene_for(db, journey.id)
        except Exception:  # noqa: BLE001 - no «Coulisses», no lines from it
            side = None
        if side is not None:
            ids.append(side.id)
    lines: list[StepLine] = []
    seen: set[str] = set()
    for scene_id in ids:
        if not scene_id or str(scene_id) in seen:
            continue
        seen.add(str(scene_id))
        try:
            scene = db.get(GraphicNovelScene, uuid.UUID(str(scene_id)))
        except (ValueError, TypeError):
            scene = None
        if scene is not None and scene.user_id == journey.user_id:
            for line in episode_lines(scene):
                _add(lines, line.character_id, line.text_fr)
    return lines


def match_line(
    lines: list[StepLine], text_fr: str, character_id: str | None = None
) -> StepLine | None:
    """The step's line the client means, or ``None``.

    Compared on quotes, spacing and case only — never fuzzily: a near miss is
    not the line. When two speakers say the same words the hinted speaker wins;
    the spoken text is always the step's own, never the client's.
    """

    wanted = _match_form(text_fr)
    if not wanted:
        return None
    hits = [line for line in lines if _match_form(line.text_fr) == wanted]
    if not hits:
        return None
    hint = cast_id_for(character_id) or str(character_id or "").strip().lower()
    for line in hits:
        if hint and (cast_id_for(line.character_id) or line.character_id.lower()) == hint:
            return line
    # A character's line before the narrator's reading of the same words.
    return sorted(hits, key=lambda line: line.character_id == NARRATOR_ID)[0]


# ---------------------------------------------------------------------------
# The cache and the call
# ---------------------------------------------------------------------------


def _model() -> str:
    return str(settings.FEUILLETON_AUDIO_TTS_MODEL)


def _learner_band(user: Any) -> str:
    """The band whose pace the learner hears: their CEFR estimate."""

    return str(getattr(user, "cefr_estimate", None) or "")


def _cache_keys(character_id: str | None, band: str | None) -> tuple[str, ...]:
    """The keys a clip of this speaker at this band may be stored under: the
    configured model's, then the fallback's (a clip spoken during an outage)."""

    keys = [spec_for(character_id, band, model=_model()).cache_key]
    fallback = spec_for(character_id, band, model=FALLBACK_SPEECH_MODEL).cache_key
    if fallback not in keys:
        keys.append(fallback)
    return tuple(keys)


def _owned_variant(
    db: Session, *, user_id: uuid.UUID, clip_id: str, keys: tuple[str, ...]
) -> LineAudioClip | None:
    """The learner's clip for this id under exactly one of ``keys`` (first key
    preferred)."""

    rows = list(
        db.scalars(
            select(LineAudioClip).where(
                LineAudioClip.user_id == user_id,
                LineAudioClip.clip_id == clip_id,
                LineAudioClip.model.in_(keys),
            )
        )
    )
    for key in keys:
        hit = next((row for row in rows if row.model == key), None)
        if hit is not None:
            return hit
    return None


def owned_clip(
    db: Session,
    *,
    user_id: uuid.UUID,
    clip_id: str,
    character_id: str | None = None,
    band: str | None = None,
) -> LineAudioClip | None:
    """The learner's own clip for this id, made under *today's* instructions.

    The lenient half of the lookup, for the route that serves bytes: the id says
    the voice and the line but not who was speaking, and a clip the learner was
    just told is ``ready`` must be found. Preferred, in order: the exact speech
    spec for this speaker and band; any clip at the band's pace; any current
    clip. A clip from before WP-103 — or from an older instructions version — is
    never returned: it is the one with the English accent.
    """

    rows = list(
        db.scalars(
            select(LineAudioClip).where(
                LineAudioClip.user_id == user_id, LineAudioClip.clip_id == clip_id
            )
        )
    )
    models = (_model(), FALLBACK_SPEECH_MODEL)
    current = [row for row in rows if cache_key_is_current(row.model, models=models)]
    if not current:
        return None
    if band is None:
        from app.db.models.user import User

        band = _learner_band(db.get(User, user_id))
    speaker = character_id or f"voice:{voice_of_clip_id(clip_id) or ''}"
    for key in _cache_keys(speaker, band):
        hit = next((row for row in current if row.model == key), None)
        if hit is not None:
            return hit
    pace = pace_for_band(band)
    # The configured model's clip before the fallback's, at the same pace first.
    ranked = sorted(
        current,
        key=lambda row: (
            (parse_cache_key(row.model) or ("", "", "", ""))[2] != pace,
            model_of_cache_key(row.model) != _model(),
        ),
    )
    return ranked[0]


def _shared_clip(
    db: Session, *, clip_id: str, keys: tuple[str, ...]
) -> LineAudioClip | None:
    """Another learner's clip of exactly this line under exactly one of ``keys``."""

    rows = list(
        db.scalars(
            select(LineAudioClip)
            .where(LineAudioClip.clip_id == clip_id, LineAudioClip.model.in_(keys))
            .limit(8)
        )
    )
    for key in keys:
        hit = next((row for row in rows if row.model == key), None)
        if hit is not None:
            return hit
    return None


def _cap_near(db: Session, user: Any) -> bool:
    from app.services.spend_guard import daily_cap_usd, learner_zone, spend_today_usd

    cap = daily_cap_usd()
    if cap <= 0:
        return False
    try:
        spent = spend_today_usd(db, user.id, zone=learner_zone(user))
    except Exception:  # pragma: no cover - a ledger read never costs the line
        return False
    return spent >= cap * CAP_NEAR_SHARE


def record_line_audio_cost(
    db: Session,
    *,
    user_id: uuid.UUID,
    clip: LineAudioClip,
    surface: str,
    step_id: uuid.UUID | None,
) -> None:
    """One priced pilot row per line actually synthesized. A cache hit — the
    learner's own clip or a copy of another learner's — writes nothing."""

    model_used = model_of_cache_key(clip.model)
    try:
        PilotEventService(db).record(
            LINE_AUDIO_EVENT_TYPE,
            user_id=user_id,
            entity_type="journey_step",
            entity_id=step_id,
            payload={
                "surface": surface,
                "provider": TTS_PROVIDER,
                "model": model_used,
                # WP-103 T1: how the line was spoken (and whether it fell back).
                "cache_key": clip.model,
                "instructions_version": SPEECH_INSTRUCTIONS_VERSION,
                "pace": (parse_cache_key(clip.model) or ("", "", "", ""))[2],
                "fell_back": model_used != _model(),
                "clip_id": clip.clip_id,
                "voice": clip.voice,
                "character_id": clip.character_id,
                "lines": 1,
                "chars": int(clip.char_count),
                # The speech endpoint returns audio and no usage block: the
                # price is a model, and the model is named.
                "estimated": True,
                "cost_basis": f"chars@${settings.FEUILLETON_AUDIO_COST_USD_PER_1K_CHARS}/1k",
            },
            cost_usd=_line_cost_usd(model_used, int(clip.char_count)),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Line audio cost row could not be written")


def _line_cost_usd(model_used: str, chars: int) -> float:
    """The declared estimate: the configured rate for the configured model, the
    model's own list rate for a clip that fell back to another."""

    if model_used == _model():
        return estimate_synthesis_cost_usd(chars)
    from app.services.llm_service import estimate_tts_cost_usd

    return estimate_tts_cost_usd(model_used, chars)


def _default_synthesizer() -> Synthesizer:
    from app.services.llm_service import LLMService

    return LLMService()


def speak_line(
    db: Session,
    *,
    user: Any,
    line: StepLine,
    surface: str,
    step_id: uuid.UUID | None = None,
    respect_cap: bool = True,
    synthesizer: Synthesizer | None = None,
    llm_factory: Callable[[], Synthesizer] | None = None,
    band: str | None = None,
) -> LineAudioOutcome:
    """The clip for one line: cached if it can be, synthesized if it must be.

    Refusals in the cheap order: the flag (nothing read, nothing called), the
    learner's own cache, another learner's copy of the same line spoken the same
    way (bytes copied, no call, no row), the daily cap, and only then the
    provider. A failed call is ``disabled`` — the device voice reads the line.

    "The same way" is the speech spec (WP-103): the model, the instructions
    version, the pace of ``band`` (default: the learner's CEFR estimate) and the
    speaker's instructions. Clips made under any other spec are not found.
    """

    if not settings.ATELIER_EPISODE_AUDIO_ENABLED:
        return LineAudioOutcome(status="disabled", reason="flag_off")
    voice = line.voice
    clip_id = clip_id_for(voice, line.text_fr)
    model = _model()
    band = _learner_band(user) if band is None else band
    keys = _cache_keys(line.character_id, band)
    mine = _owned_variant(db, user_id=user.id, clip_id=clip_id, keys=keys)
    if mine is not None:
        return LineAudioOutcome(status="ready", clip=mine, cached=True)

    clip = LineAudioClip(
        user_id=user.id,
        clip_id=clip_id,
        voice=voice,
        model=keys[0],
        character_id=str(line.character_id or "")[:80],
        text_fr=line.text_fr,
        char_count=len(line.text_fr),
        content_type="audio/mpeg",
    )
    shared = _shared_clip(db, clip_id=clip_id, keys=keys)
    if shared is not None:
        clip.audio = bytes(shared.audio)
        clip.content_type = shared.content_type or "audio/mpeg"
        clip.model = shared.model
        db.add(clip)
        db.flush()
        return LineAudioOutcome(status="ready", clip=clip, cached=True)

    if respect_cap and _cap_near(db, user):
        return LineAudioOutcome(status="disabled", reason="cap_near")
    provider = synthesizer
    try:
        if provider is None:
            provider = (llm_factory or _default_synthesizer)()
        spoken = speak_text(
            provider,
            text=line.text_fr,
            voice=voice,
            character_id=line.character_id,
            band=band,
            model=model,
        )
        audio = spoken.audio
    except Exception as exc:
        logger.warning("Line audio synthesis failed", clip_id=clip_id, error=str(exc))
        return LineAudioOutcome(status="disabled", reason="tts_failed")
    if not audio:
        return LineAudioOutcome(status="disabled", reason="tts_empty")
    clip.audio = bytes(audio)
    # Stored under the spec of the model that really spoke it.
    clip.model = spoken.spec.cache_key
    db.add(clip)
    db.flush()
    record_line_audio_cost(db, user_id=user.id, clip=clip, surface=surface, step_id=step_id)
    return LineAudioOutcome(status="ready", clip=clip, cached=False)


# ---------------------------------------------------------------------------
# A listening item's clip, named at plan time and spoken on first request
# ---------------------------------------------------------------------------


def planned_line(db: Session, *, user_id: uuid.UUID, clip_id: str) -> tuple[StepLine, uuid.UUID] | None:
    """The line one of this learner's listening items names by ``clip_id``.

    Looked for in the learner's own recent journeys only, in recall steps whose
    public ``audio_url`` is exactly this clip's path. The words come from the
    step's *private* task — a dictation's line, a listen-and-tap item's phrase —
    and must hash back to the id together with the voice it names, so an id can
    never be pointed at other words.
    """

    voice = voice_of_clip_id(clip_id)
    if voice is None:
        return None
    path = LINE_AUDIO_PATH_PREFIX + clip_id
    journeys = db.scalars(
        select(DailyJourney)
        .where(DailyJourney.user_id == user_id)
        .order_by(DailyJourney.local_date.desc(), DailyJourney.created_at.desc())
        .limit(PLANNED_CLIP_JOURNEYS)
    )
    for journey in journeys:
        for step in journey.steps:
            prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
            if step.kind != "recall" or prompt.get("audio_url") != path:
                continue
            private = step.private_task if isinstance(step.private_task, dict) else {}
            task = private.get("recall_task") if isinstance(private.get("recall_task"), dict) else {}
            if task.get("task_type") not in _PLANNED_FORMATS:
                continue
            text = task.get("solution_fr") if task.get("task_type") == "dictation" else task.get("prompt_fr")
            raw = normalize_line_text(str(text or "")).strip()
            # The planner speaks a phrase without its layout quotes.
            for clean in (raw, raw.strip("«»“”\"„ ")):
                if clean and clip_id_for(voice, clean) == clip_id:
                    # The voice is the id's; the speaker is only a label on the row.
                    return StepLine(character_id=f"voice:{voice}", text_fr=clean), step.id
    return None


def speak_planned_clip(
    db: Session, *, user: Any, clip_id: str, synthesizer: Synthesizer | None = None
) -> LineAudioClip | None:
    """``GET``'s lazy half: synthesize a planned listening clip on first request.

    Held to the flag like every line, but not to the soft cap: a dictation
    without its clip is a question the learner cannot answer, and one short
    line costs a fraction of a cent. ``None`` when there is nothing to speak.
    """

    found = planned_line(db, user_id=user.id, clip_id=clip_id)
    if found is None:
        return None
    line, step_id = found
    voice = voice_of_clip_id(clip_id) or line.voice
    outcome = speak_line(
        db,
        user=user,
        line=_VoicedLine(line.character_id, line.text_fr, voice),
        surface="journey_listening_item",
        step_id=step_id,
        respect_cap=False,
        synthesizer=synthesizer,
    )
    return outcome.clip if outcome.status == "ready" else None


@dataclass(frozen=True, slots=True)
class _VoicedLine:
    """A line whose voice was fixed by its clip id rather than by a speaker."""

    character_id: str
    text_fr: str
    voice: str


__all__ = [
    "CAP_NEAR_SHARE",
    "LINE_AUDIO_EVENT_TYPE",
    "LineAudioOutcome",
    "StepLine",
    "match_line",
    "owned_clip",
    "planned_line",
    "record_line_audio_cost",
    "speak_line",
    "speak_planned_clip",
    "step_lines",
]
