"""Les appels — someone from the story phones the learner.

Once the day's scene is settled, a person who heard the learner rings: Romy if she
has met them, else the one they talked to most recently. The learner picks up and
the two talk for a few turns, out loud: the caller's lines are spoken in their own
voice (:mod:`app.services.line_audio`), the learner answers by holding the button
(``POST /audio/transcribe``, surface ``appel``) or by typing. Nothing is graded and
nothing is pronounced «wrong» (WP-27): a call is listening and speaking under a
little time pressure, with someone who knows you.

What the learner says stays. On hang-up the call is written into the living story
the way a day is: the learner's lines and what they settled go through
:func:`story_memory.after_day` (heard by the caller only), and one ``events[]`` row
(``source: "appel"``) lets tomorrow's page say «quand tu m'as appelée hier…». Like a
finished letter, that moves the story revision; a call only rings after the day's
journey is completed, so the next page is written after it.

A declined call leaves a voicemail: the caller's message, playable, and nothing in
the memory (the learner said nothing).

State lives under ``thread.state["appels"]``, outside the story fingerprint
(``living_story.FINGERPRINT_IGNORED_STATE_KEYS``): a ringing or live call never
invalidates a page.

Money: every model call and transcription is booked on the pilot ledger against
the call (entity ``appel``); past ``ATELIER_CALLS_MAX_USD`` the caller says an
authored goodbye and no provider is called. A provider failure does the same.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import cast_registry, story_memory
from app.services.address import character_register
from app.services.journey_contracts import JourneyStatus

#: Our namespace on ``thread.state`` (never inside ``living_story``).
STATE_KEY = "appels"
#: Stamped on the ``events[]`` row a finished call writes.
EVENT_SOURCE = "appel"
#: The pilot-ledger entity every cost of one call is booked against.
ENTITY_TYPE = "appel"
#: The ledger event of one caller line written by a model.
MODEL_EVENT_TYPE = "appel_model"
#: The transcription surface of a spoken answer on a call.
SURFACE = "appel"
#: Calls kept per life.
MAX_CALLS = 14
#: Who calls, in order of preference, among those who heard the learner. Romy is a
#: journalist who phones people for a living; Lila is the learner's accomplice. Only
#: people with a drawn face and a voice; never Odile, whose succession the story is.
CALLERS = (
    "romy_tremblay",
    "lila_bonnet",
    "marin_leveque",
    "margaux_barman",
    "augustin_de_roncourt",
    "camille_marchand",
    "landlord_marchand",
)
LINE_CHARS = 240
#: The learner's own line is kept whole up to what `/say` accepts.
LEARNER_CHARS = 600

#: What a caller says when no model may speak (the ceiling, an outage).
FALLBACK_OPENING = "Allô ? C'est {name}. Tu as une minute ? Je voulais juste savoir comment tu vas."
FALLBACK_OPENING_VOUS = "Allô ? C'est {name}. Vous avez une minute ? Je voulais savoir comment vous allez."
FALLBACK_VOICEMAIL = "Allô, c'est {name}. Je voulais te parler. Rappelle-moi quand tu peux. Bisous !"
FALLBACK_VOICEMAIL_VOUS = "Bonjour, c'est {name}. Je voulais vous parler. Rappelez-moi quand vous pouvez."
FALLBACK_GOODBYE = "Oh, on m'appelle sur l'autre ligne. Je dois filer ! On se parle bientôt."
FALLBACK_GOODBYE_VOUS = "Oh, excusez-moi, je dois raccrocher. On se parle bientôt."


class CallRefused(Exception):
    """A request the call cannot take: wrong call, wrong state, feature off."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def calls_enabled() -> bool:
    return bool(settings.ATELIER_CALLS_ENABLED)


# ---------------------------------------------------------------------------
# The provider: one JSON call per caller line
# ---------------------------------------------------------------------------


class CallProvider(Protocol):
    name: str

    def opening(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]: ...

    def reply(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]: ...


_SYSTEM = """You write one character's lines in a phone call, in French, for a language
learner at CEFR level {band}. The character is {name} from the learner's story (an
ongoing serial in Paris's 10th arrondissement); they phoned the learner after today's
scene. Speak as a real person on the phone: short spoken sentences, «allô», small
hesitations, one question at a time, never a lesson and never a correction. Keep every
line at the learner's level ({band}): at A1–A2 short sentences in the present or passé
composé and everyday words. Address the learner with «{register}». """ + story_memory.NAME_NOTE + """
Use only what the input says the character knows about the learner (knows): never
invent something the learner said. Return JSON only."""

_OPENING = """Write the call's first line and the voicemail left if the learner does not
pick up. The call has one small, concrete reason that grows out of the story: an open
question from knows.open, something the learner said (knows.said), or the latest
events. opening_fr: at most 2 sentences, starts like a phone call («Allô ? C'est …»),
ends with a question the learner can answer in one sentence. voicemail_fr: at most 3
sentences, the same reason, asks to be called back. reason_en: one plain English
sentence saying why they call (shown to the learner only after the call).
Return {"opening_fr": str, "voicemail_fr": str, "reason_en": str}."""

_REPLY = """Write the character's next line answering the learner's last line (lines[-1]).
React to what the learner actually said; if it was hard to understand, ask once, simply,
what they mean. turns_left says how many more learner lines the call has: when it is 0,
or the learner says goodbye, say goodbye warmly and set ends true. reply_fr: at most 2
sentences. """ + story_memory.ENDING_REPORT + """ Here «this exchange» is the whole call
(lines). summary_fr (only when ends is true): one French sentence for the story's
ledger, as the story will remember the call, addressed to the learner as «tu»
(«Romy t'a téléphoné : …»), never naming or gendering the learner.
Return {"reply_fr": str, "ends": bool, "learned": [...], "left_open": [...],
"answered_open_ids": [...], "summary_fr": str|null}."""


def _system(context: dict[str, Any]) -> str:
    return _SYSTEM.format(
        band=context.get("band") or "A2",
        name=context.get("caller_name") or "",
        register=context.get("register") or "tu",
    )


class LLMCallProvider:
    """The app's LLM service on the story's live model, one JSON call per line."""

    name = "llm-appel"

    def _ask(self, instructions: str, context: dict[str, Any]) -> tuple[dict[str, Any], float]:
        from app.services.llm_service import LLMService

        model = settings.STORY_LIVE_MODEL or None
        result = LLMService().generate_chat_completion(
            [{"role": "user", "content": f"{instructions}\n\nINPUT:\n{json.dumps(context, ensure_ascii=False)}"}],
            system_prompt=_system(context),
            temperature=0.7,
            max_tokens=1200,
            response_format={"type": "json_object"},
            reasoning_effort="low",
            request_timeout=25.0,
            **({"model": model} if model else {}),
        )
        cost = float(getattr(result, "cost", 0.0) or 0.0)
        data = json.loads(result.content or "")
        if not isinstance(data, dict):
            raise ValueError("appel: not an object")
        return data, cost

    def opening(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]:
        return self._ask(_OPENING, context)

    def reply(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]:
        return self._ask(_REPLY, context)


@dataclass
class FakeCallProvider:
    """Deterministic lines, no network: tests and dev stacks. ``replies`` are consumed
    first, one per reply."""

    name: str = "fake-appel"
    replies: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    cost: float = 0.001

    def opening(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]:
        self.calls.append(("opening", context))
        name = context.get("caller_name") or "Romy"
        return (
            {
                "opening_fr": f"Allô ? C'est {name}. Tu as une minute ? Tu as passé une bonne journée ?",
                "voicemail_fr": f"Allô, c'est {name}. Rappelle-moi quand tu peux !",
                "reason_en": f"{name} wanted to hear how your day went.",
            },
            self.cost,
        )

    def reply(self, context: dict[str, Any]) -> tuple[dict[str, Any], float]:
        self.calls.append(("reply", context))
        if self.replies:
            return self.replies.pop(0), self.cost
        ends = int(context.get("turns_left") or 0) <= 0
        return (
            {
                "reply_fr": "Super, bonne soirée ! À demain." if ends else "Ah oui ? Raconte-moi un peu.",
                "ends": ends,
                "learned": [],
                "left_open": [],
                "answered_open_ids": [],
                "summary_fr": "On t'a téléphoné pour prendre des nouvelles." if ends else None,
            },
            self.cost,
        )


def default_provider() -> CallProvider:
    if settings.ATELIER_LLM_ENABLED and (
        getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "ANTHROPIC_API_KEY", None)
    ):
        return LLMCallProvider()
    logger.warning("appels: no LLM provider configured; the caller speaks from the fake provider")
    return FakeCallProvider()


# ---------------------------------------------------------------------------
# Reading the story
# ---------------------------------------------------------------------------


def _thread(db: Session, user: User, *, lock: bool = False) -> SerialThread | None:
    from app.services.living_story import STATE_KEY as LIVE_KEY
    from app.services.living_story import _active_thread

    if lock:
        db.execute(select(User.id).where(User.id == user.id).with_for_update())
    thread = _active_thread(db, user, lock=lock)
    if thread and isinstance((thread.state or {}).get(LIVE_KEY), dict):
        return thread
    return None


def _live(thread: SerialThread) -> dict[str, Any]:
    from app.services.living_story import STATE_KEY as LIVE_KEY

    return dict((thread.state or {}).get(LIVE_KEY) or {})


def _calls(thread: SerialThread) -> list[dict[str, Any]]:
    value = (thread.state or {}).get(STATE_KEY)
    rows = value.get("calls") if isinstance(value, dict) else None
    return [dict(row) for row in rows or [] if isinstance(row, dict)]


def _save_calls(thread: SerialThread, calls: list[dict[str, Any]]) -> None:
    state = dict(thread.state or {})
    state[STATE_KEY] = {"calls": calls[-MAX_CALLS:]}
    # A JSON column is noticed only when replaced, never when mutated in place.
    thread.state = state


def _todays_journey(db: Session, user: User, now: datetime | None = None) -> DailyJourney | None:
    from app.services.daily_journey import local_date_for

    journey = db.scalar(
        select(DailyJourney)
        .where(DailyJourney.user_id == user.id)
        .order_by(DailyJourney.local_date.desc(), DailyJourney.created_at.desc())
        .limit(1)
    )
    if journey is None or journey.local_date != local_date_for(journey.timezone or "UTC", now=now):
        return None
    return journey


def heard_by(memory: dict | None) -> set[str]:
    """Everyone the learner has spoken to, by the memory."""

    memory = memory if isinstance(memory, dict) else {}
    people: set[str] = set()
    for row in memory.get("said") or []:
        if isinstance(row, dict):
            people.update(str(who) for who in row.get("heard_by") or [] if who)
    return people


def pick_caller(memory: dict | None) -> str | None:
    """The first of :data:`CALLERS` who heard the learner, or ``None``: nobody calls
    a learner they never spoke with."""

    people = heard_by(memory)
    return next((cast_id for cast_id in CALLERS if cast_id in people), None)


def _caller_view(caller: str) -> dict[str, Any]:
    found = cast_registry.member(caller)
    return {
        "id": caller,
        "name": found.short_name if found else caller,
        "face": found.face if found else None,
    }


# ---------------------------------------------------------------------------
# What the client sees
# ---------------------------------------------------------------------------


def public_view(call: dict[str, Any] | None) -> dict[str, Any] | None:
    if not call:
        return None
    turns_used = sum(1 for turn in call.get("turns") or [] if turn.get("who") == "learner")
    return {
        "id": call["id"],
        "status": call["status"],
        "caller": _caller_view(call["caller"]),
        "turns": [
            {key: turn.get(key) for key in ("who", "text_fr", "clip_id", "mode") if turn.get(key) is not None}
            for turn in call.get("turns") or []
        ],
        "voicemail": (
            {"text_fr": call["voicemail_fr"], "clip_id": call.get("voicemail_clip_id")}
            if call.get("status") == "missed" and call.get("voicemail_fr")
            else None
        ),
        "turns_left": max(0, int(settings.ATELIER_CALLS_MAX_TURNS) - turns_used),
        # Shown only once the call is over: during it, the learner listens.
        "reason_en": call.get("reason_en") if call.get("status") in ("ended", "missed") else None,
    }


# ---------------------------------------------------------------------------
# Today: ring, or not
# ---------------------------------------------------------------------------


def today(db: Session, user: User, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Today's call, creating it (ringing, no provider call) when one is due.

    Due: the feature is on, today's journey is completed and its scene settled into
    the memory, someone heard the learner, and no call was made today."""

    if not calls_enabled():
        return None
    journey = _todays_journey(db, user, now)
    if journey is None:
        return None
    date_iso = journey.local_date.isoformat()
    thread = _thread(db, user)
    if thread is None:
        return None
    existing = next((row for row in reversed(_calls(thread)) if row.get("date") == date_iso), None)
    if existing is not None:
        return public_view(existing)
    if str(journey.status) != JourneyStatus.COMPLETED.value:
        return None
    memory = _live(thread).get(story_memory.MEMORY_KEY)
    settled = {str(item) for item in (memory or {}).get("days") or []}
    if f"journey:{journey.id}:story" not in settled:
        return None
    caller = pick_caller(memory)
    if caller is None:
        return None
    thread = _thread(db, user, lock=True)
    if thread is None:
        return None
    calls = _calls(thread)
    existing = next((row for row in reversed(calls) if row.get("date") == date_iso), None)
    if existing is not None:
        return public_view(existing)
    call = {
        "id": uuid.uuid4().hex,
        "date": date_iso,
        "caller": caller,
        "status": "ringing",
        "turns": [],
        "rang_at": (now or datetime.now(UTC)).isoformat(),
    }
    _save_calls(thread, [*calls, call])
    db.add(thread)
    db.flush()
    return public_view(call)


def _owned(db: Session, user: User, call_id: str) -> tuple[SerialThread, list[dict[str, Any]], dict[str, Any]]:
    if not calls_enabled():
        raise CallRefused(404, "appel_disabled", "Calls are off.")
    thread = _thread(db, user, lock=True)
    calls = _calls(thread) if thread else []
    call = next((row for row in calls if row.get("id") == str(call_id)), None)
    if thread is None or call is None:
        raise CallRefused(404, "appel_not_found", "Call not found.")
    return thread, calls, call


def _put(thread: SerialThread, calls: list[dict[str, Any]], call: dict[str, Any]) -> None:
    _save_calls(thread, [call if row.get("id") == call["id"] else row for row in calls])


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


def call_spend_usd(db: Session, *, user_id: uuid.UUID, call_id: str) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(PilotEvent.cost_usd), 0.0)).where(
            PilotEvent.user_id == user_id,
            PilotEvent.entity_type == ENTITY_TYPE,
            PilotEvent.entity_id == str(call_id),
        )
    )
    return float(total or 0.0)


def _over_ceiling(db: Session, user: User, call_id: str, extra: float = 0.0) -> bool:
    return call_spend_usd(db, user_id=user.id, call_id=call_id) + extra > float(settings.ATELIER_CALLS_MAX_USD) + 1e-9


def _book_model(db: Session, user: User, call: dict[str, Any], *, stage: str, cost: float, provider: str) -> None:
    from app.services.pilot_events import PilotEventService

    PilotEventService(db).record(
        MODEL_EVENT_TYPE,
        user_id=user.id,
        entity_type=ENTITY_TYPE,
        entity_id=call["id"],
        payload={"stage": stage, "provider": provider, "caller": call["caller"]},
        cost_usd=cost,
    )


def authorize_upload(
    db: Session,
    *,
    user: User,
    call_id: str | None,
    byte_count: int,
    content_type: str | None = None,
    measured_seconds: float | None = None,
) -> str:
    """Every check a spoken line on a call passes before transcription. Returns the
    call id the transcription is booked against."""

    from app.services.transcription_cost import (
        estimate_audio_seconds,
        estimate_transcription_cost_usd,
    )

    if not calls_enabled():
        raise CallRefused(404, "appel_disabled", "Calls are off.")
    thread = _thread(db, user)
    call = next((row for row in _calls(thread) if row.get("id") == str(call_id or "")), None) if thread else None
    if call is None:
        raise CallRefused(404, "appel_not_found", "Call not found.")
    if call.get("status") != "live":
        raise CallRefused(409, "appel_not_live", "This call is not on.")
    seconds = estimate_audio_seconds(byte_count, content_type, measured_seconds=measured_seconds)
    if seconds > float(settings.ATELIER_SPOKEN_REPLY_MAX_SECONDS):
        raise CallRefused(413, "appel_too_long", "One line is at most thirty seconds.")
    cost = estimate_transcription_cost_usd(byte_count, content_type, measured_seconds=measured_seconds)
    if _over_ceiling(db, user, call["id"], cost):
        raise CallRefused(429, "appel_ceiling", "This call has used its spoken lines; please type.")
    return call["id"]


# ---------------------------------------------------------------------------
# The call
# ---------------------------------------------------------------------------


def _clip(text: Any, limit: int = LINE_CHARS) -> str:
    return " ".join(str(text or "").split())[:limit]


def _register(thread: SerialThread, caller: str) -> str:
    return str(character_register(thread.state or {}, caller) or "tu")


def _context(thread: SerialThread, user: User, call: dict[str, Any]) -> dict[str, Any]:
    live = _live(thread)
    memory = live.get(story_memory.MEMORY_KEY)
    knows = story_memory.view(memory, among={call["caller"]}) or {}
    events = [
        _clip(row.get("summary_fr"))
        for row in (live.get("events") or [])[-4:]
        if isinstance(row, dict) and call["caller"] in (row.get("witnesses") or []) and row.get("summary_fr")
    ]
    found = cast_registry.member(call["caller"])
    return {
        "band": str(getattr(user, "cefr_estimate", None) or "A2")[:2],
        "caller_name": found.short_name if found else call["caller"],
        "caller_pronoun": cast_registry.pronoun_for(call["caller"]),
        "register": _register(thread, call["caller"]),
        "knows": knows,
        "events": events,
    }


def _speak(db: Session, user: User, call: dict[str, Any], text: str) -> str | None:
    from app.services.line_audio import StepLine, speak_line

    try:
        outcome = speak_line(db, user=user, line=StepLine(call["caller"], text), surface=SURFACE)
    except Exception as exc:  # pragma: no cover - the line is still shown and read on the device
        logger.warning("appels: speech failed", error=str(exc))
        return None
    return outcome.clip.clip_id if outcome.status == "ready" and outcome.clip is not None else None


def _fallback(kind: str, thread: SerialThread, call: dict[str, Any]) -> str:
    vous = _register(thread, call["caller"]) == "vous"
    name = _caller_view(call["caller"])["name"]
    table = {
        "opening": FALLBACK_OPENING_VOUS if vous else FALLBACK_OPENING,
        "voicemail": FALLBACK_VOICEMAIL_VOUS if vous else FALLBACK_VOICEMAIL,
        "goodbye": FALLBACK_GOODBYE_VOUS if vous else FALLBACK_GOODBYE,
    }
    return table[kind].format(name=name)


def _open(db: Session, user: User, thread: SerialThread, call: dict[str, Any], provider: CallProvider) -> None:
    """The opening line and the voicemail, written once per call."""

    if call.get("opening_fr"):
        return
    data: dict[str, Any] = {}
    if not _over_ceiling(db, user, call["id"]):
        try:
            data, cost = provider.opening(_context(thread, user, call))
            _book_model(db, user, call, stage="opening", cost=cost, provider=provider.name)
        except Exception as exc:
            logger.warning("appels: opening failed", error=str(exc)[:300])
            data = {}
    call["opening_fr"] = _clip(data.get("opening_fr")) or _fallback("opening", thread, call)
    call["voicemail_fr"] = _clip(data.get("voicemail_fr")) or _fallback("voicemail", thread, call)
    call["reason_en"] = _clip(data.get("reason_en")) or None


def answer(db: Session, user: User, call_id: str, *, provider: CallProvider | None = None) -> dict[str, Any]:
    thread, calls, call = _owned(db, user, call_id)
    if call["status"] == "live":
        return public_view(call)  # a second tap, or a retry after a lost response
    if call["status"] != "ringing":
        raise CallRefused(409, "appel_not_ringing", "This call is over.")
    _open(db, user, thread, call, provider or default_provider())
    call["status"] = "live"
    call["answered_at"] = datetime.now(UTC).isoformat()
    call["turns"] = [{"who": "caller", "text_fr": call["opening_fr"], "clip_id": _speak(db, user, call, call["opening_fr"])}]
    _put(thread, calls, call)
    db.add(thread)
    db.flush()
    return public_view(call)


def decline(db: Session, user: User, call_id: str, *, provider: CallProvider | None = None) -> dict[str, Any]:
    """Not now: the caller leaves a voicemail. Nothing goes into the memory."""

    thread, calls, call = _owned(db, user, call_id)
    if call["status"] == "missed":
        return public_view(call)
    if call["status"] != "ringing":
        raise CallRefused(409, "appel_not_ringing", "This call is over.")
    _open(db, user, thread, call, provider or default_provider())
    call["status"] = "missed"
    call["voicemail_clip_id"] = _speak(db, user, call, call["voicemail_fr"])
    _put(thread, calls, call)
    db.add(thread)
    db.flush()
    return public_view(call)


def say(
    db: Session,
    user: User,
    call_id: str,
    text: str,
    *,
    mode: str = "text",
    provider: CallProvider | None = None,
) -> dict[str, Any]:
    """The learner's line, and the caller's answer. The last allowed line, a goodbye
    from the caller, the ceiling or an outage ends the call and settles it."""

    thread, calls, call = _owned(db, user, call_id)
    if call["status"] != "live":
        raise CallRefused(409, "appel_not_live", "This call is not on.")
    line = _clip(text, LEARNER_CHARS)
    if not line:
        raise CallRefused(422, "appel_empty", "Say something first.")
    call["turns"] = [*call.get("turns", []), {"who": "learner", "text_fr": line, "mode": "voice" if mode == "voice" else "text"}]
    used = sum(1 for turn in call["turns"] if turn.get("who") == "learner")
    turns_left = max(0, int(settings.ATELIER_CALLS_MAX_TURNS) - used)
    provider = provider or default_provider()
    data: dict[str, Any] = {}
    if not _over_ceiling(db, user, call["id"]):
        context = _context(thread, user, call)
        context["lines"] = [
            {"who": "learner" if turn["who"] == "learner" else context["caller_name"], "text_fr": turn["text_fr"]}
            for turn in call["turns"]
        ]
        context["turns_left"] = turns_left
        try:
            data, cost = provider.reply(context)
            _book_model(db, user, call, stage="reply", cost=cost, provider=provider.name)
        except Exception as exc:
            logger.warning("appels: reply failed", error=str(exc)[:300])
            data = {}
    reply = _clip(data.get("reply_fr"))
    ends = bool(data.get("ends")) or turns_left <= 0 or not reply
    if not reply:
        reply = _fallback("goodbye", thread, call)
    texts = [turn["text_fr"] for turn in call["turns"] if turn.get("who") == "learner"]
    # What the call settled, kept only when the learner's own words carry it.
    learned = [
        fact.model_dump()
        for fact in story_memory.grounded_facts(story_memory.lenient_facts(data.get("learned")), texts)
    ]
    call["learned"] = [*call.get("learned", []), *learned][-story_memory.MAX_LEARNED:]
    call["left_open"] = [
        quote
        for quote in [*call.get("left_open", []), *story_memory.lenient_lines(data.get("left_open"), story_memory.MAX_LEFT_OPEN)]
        if story_memory.verbatim(quote, texts)
    ][-story_memory.MAX_LEFT_OPEN:]
    known_open = story_memory.open_ids(story_memory.view(_live(thread).get(story_memory.MEMORY_KEY), among={call["caller"]}))
    call["answered_open_ids"] = sorted(
        set(call.get("answered_open_ids", [])) | {str(item) for item in data.get("answered_open_ids") or [] if str(item) in known_open}
    )
    if data.get("summary_fr"):
        call["summary_fr"] = _clip(data.get("summary_fr"))
    call["turns"] = [*call["turns"], {"who": "caller", "text_fr": reply, "clip_id": _speak(db, user, call, reply)}]
    if ends:
        _settle(thread, call)
    _put(thread, calls, call)
    db.add(thread)
    db.flush()
    return public_view(call)


def hang_up(db: Session, user: User, call_id: str) -> dict[str, Any]:
    """The learner hangs up. A call where they said something is settled; one where
    they said nothing ends without a trace in the story."""

    thread, calls, call = _owned(db, user, call_id)
    if call["status"] in ("ended", "missed"):
        return public_view(call)
    if call["status"] == "ringing":
        raise CallRefused(409, "appel_not_live", "This call is not on.")
    _settle(thread, call)
    _put(thread, calls, call)
    db.add(thread)
    db.flush()
    return public_view(call)


def _summary(call: dict[str, Any]) -> str:
    name = _caller_view(call["caller"])["name"]
    first = next((turn["text_fr"] for turn in call.get("turns", []) if turn.get("who") == "learner"), "")
    return _clip(f"{name} t'a téléphoné. Tu as dit : «{first}»") if first else f"{name} t'a téléphoné."


def _settle(thread: SerialThread, call: dict[str, Any]) -> None:
    """Write the finished call into the living story (idempotent per call)."""

    from app.services.living_story import MAX_HISTORY
    from app.services.living_story import STATE_KEY as LIVE_KEY

    call["status"] = "ended"
    call["ended_at"] = datetime.now(UTC).isoformat()
    turns = call.get("turns") or []
    if not any(turn.get("who") == "learner" for turn in turns):
        return
    state = dict(thread.state or {})
    live = dict(state.get(LIVE_KEY) or {})
    event_id = f"appel:{call['id']}"
    events = list(live.get("events") or [])
    if any(isinstance(row, dict) and row.get("id") == event_id for row in events):
        return
    # Each learner line with the caller line it answered (the memory's exchanges).
    exchanges: list[dict[str, Any]] = []
    for index, turn in enumerate(turns):
        if turn.get("who") != "learner":
            continue
        following = next((later["text_fr"] for later in turns[index + 1 :] if later.get("who") == "caller"), "")
        exchanges.append({"learner": turn["text_fr"], "character": following})
    day = int(live.get("day_index") or 0)
    summary = call.get("summary_fr") or _summary(call)
    live[story_memory.MEMORY_KEY] = story_memory.after_day(
        live.get(story_memory.MEMORY_KEY),
        story_memory.Day(
            event_id=event_id,
            day=day,
            date=call.get("date"),
            speaker=call["caller"],
            witnesses=(call["caller"],),
            exchanges=tuple(exchanges),
            opening_fr=call.get("opening_fr") or "",
            learned=tuple(call.get("learned") or ()),
            left_open=tuple(call.get("left_open") or ()),
            answered_open_ids=tuple(call.get("answered_open_ids") or ()),
            not_names=frozenset(member.short_name for member in cast_registry.all_members().values()),
        ),
    )
    event = {
        "id": event_id,
        "scene_id": None,
        "witnesses": [call["caller"]],
        "summary_fr": summary,
        "source_quotes": [exchange["learner"] for exchange in exchanges][:2],
        "outcome": "met",
        "at": call["ended_at"],
        # The director reads ``events[]`` as one list; this says «au téléphone».
        "source": EVENT_SOURCE,
        "chapter_id": (live.get("chapter") or {}).get("id"),
        "date": call.get("date"),
    }
    live["events"] = [*events, event][-MAX_HISTORY:]
    state[LIVE_KEY] = live
    state["story_so_far"] = [*list(state.get("story_so_far") or []), summary][-40:]
    thread.state = state
    call["settled"] = True


__all__ = [
    "CALLERS",
    "ENTITY_TYPE",
    "EVENT_SOURCE",
    "STATE_KEY",
    "SURFACE",
    "CallProvider",
    "CallRefused",
    "FakeCallProvider",
    "LLMCallProvider",
    "answer",
    "authorize_upload",
    "call_spend_usd",
    "calls_enabled",
    "decline",
    "default_provider",
    "hang_up",
    "pick_caller",
    "public_view",
    "say",
    "today",
]
