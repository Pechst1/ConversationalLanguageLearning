"""WP-31 — «Répétition»: rehearse a real upcoming situation, then debrief it.

Everything else in this app is fiction. This is not. The learner declares
something that is actually going to happen to them — *"call the landlord about
the heating, Tuesday"* — rehearses it once, does it for real, and then says how
it went.

Why it exists, and what the evidence actually supports: transfer from task
rehearsal is under-evidenced in general but positive for the lowest-proficiency
learners (Benson 2016), and needs-analysis relevance is what drives adult
engagement (Huang 2022). So the package is deliberately narrow: one rehearsal of
the learner's *own* declared need, and the number that judges it is **the
debrief**, not the rehearsal score. A learner who rehearsed beautifully and then
did not make the call has not been helped.

The boundary this module exists to hold
---------------------------------------

``docs/implementation/atelier-v2/CONTINUOUS-STORY.md``: *distinguish fictional
roleplay facts from real learner biography*. A rehearsal is biography. Therefore:

* nothing here is ever written into ``SerialThread``, ``SerialEpisode`` or any
  other store the continuing story reads — this module imports no serial
  service and calls no story-outcome function, and
  ``test_rehearsal.py::test_rehearsal_never_writes_serial_memory`` scans this
  source to keep it that way;
* the :class:`ScenarioBrief` this module builds carries an **empty**
  ``story_context``, which is also what keeps
  :func:`~app.services.journey_conversation.evaluate_response` on its
  deterministic path instead of delegating to the living story;
* no world-bible character may appear in a rehearsal. The learner's landlord is
  not Margaux, and Margaux must not turn up in the learner's real Tuesday.
  :func:`scene_mentions_fiction` is the guard, applied to generated scenes *and*
  to the corrections the conversation module hands back.

What is reused rather than rebuilt
----------------------------------

* **Content**: the journey content adapter's contracts (:class:`ScenarioBrief`,
  :class:`ResponseTask`), its per-band length envelope (``BAND_LIMITS``) and its
  level read (``learner_level_band``). Its *validator* is not reusable here —
  ``validate_scenario_brief`` requires world-bible cast and locations, which a
  rehearsal by definition does not have — so :func:`validate_rehearsal_scene`
  applies the same rules to the shape a rehearsal actually has.
* **Conversation**: every turn is graded by
  :func:`~app.services.journey_conversation.evaluate_response`. The 3–6 turn
  bound of WP-31 is wider than that module's own two-turn journey budget, so
  **this** module owns the bound and tells the conversation module only whether
  a follow-up remains (:func:`conversation_turn_index`).
* **Evidence**: :func:`~app.services.journey_learning.classify_evidence` — the
  one rubric. Asking for the useful phrases is assistance, so it costs
  independence exactly as a revealed solution does in the daily journey.

Honest under failure: a provider that does not answer leaves the rehearsal in
``not_prepared``. The learner is told «Répétition non préparée» and offered a
retry; they are never shown an invented scene with their real situation in it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.rehearsal import REHEARSAL_OUTCOMES, Rehearsal
from app.db.models.user import User
from app.services.journey_content import BAND_LIMITS, learner_level_band
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    Correction,
    InputMode,
    ResponseTask,
    ScenarioBrief,
    TaskOutcome,
    normalize_control_language,
)
from app.services.journey_conversation import evaluate_response, reply_source
from app.services.journey_learning import classify_evidence, fold_for_comparison
from app.services.llm_service import LLMProviderError, LLMService
from app.services.pilot_events import PilotEventService

REHEARSAL_VERSION = "rehearsal-v1"

#: Pilot-ledger event types. ``scripts/pilot_digest.py`` reads them by name, the
#: same way it reads ``atelier_correction`` and ``placement_grading``.
PREPARE_EVENT_TYPE = "rehearsal_prepare"
TURN_EVENT_TYPE = "rehearsal_turn"
DEBRIEF_EVENT_TYPE = "rehearsal_debrief"

#: WP-31 §2. Three turns is the floor for a situation with a shape (open, ask,
#: settle); six is the ceiling before a rehearsal stops being a rehearsal.
MIN_TURNS = 3
MAX_TURNS = 6

#: Two generation attempts, exactly as the journey content adapter allows.
MAX_PREPARE_ATTEMPTS = 2

#: Bounds on learner-controlled text reaching a paid endpoint.
DECLARATION_MAX_CHARS = 600
FREE_LINE_MAX_CHARS = 600
ANSWER_MAX_CHARS = 1200

#: How far ahead a declared date may be resolved. Anything further is kept as
#: the learner's own words and no date is claimed.
MAX_EVENT_HORIZON_DAYS = 180

REGISTERS: tuple[str, ...] = ("tu", "vous")

#: Points a scene may require, and cues per point. Two is the floor for a
#: situation worth rehearsing; four is the ceiling before it stops being one
#: speech act at a time.
MIN_POINTS = 2
MAX_POINTS = 4

#: Endings the scene may reach. One is a rail, four is a menu.
MIN_ENDINGS = 2
MAX_ENDINGS = 3

_TU_MARKERS = re.compile(r"\b(tu|toi|te|ton|ta|tes)\b|\bt'", re.IGNORECASE)
_VOUS_MARKERS = re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE)
_OUTCOME_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RehearsalRefused(Exception):
    """A refusal the learner should read, not a 500.

    ``code`` is stable and machine-readable; the French sentence lives in the
    router, next to every other sentence the learner sees.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# The fiction / biography boundary
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _world_names() -> tuple[str, ...]:
    """Every world-bible character name, and its first name, folded.

    Read-only, from the same file the serial reads. A rehearsal that named one
    of these would be exactly the confusion CONTINUOUS-STORY forbids: the
    learner's real landlord dressed as a character, or a character walking into
    the learner's real Tuesday.
    """

    from app.services.serial import WORLD_BIBLE_PATH

    names: set[str] = set()
    try:
        payload = json.loads(Path(WORLD_BIBLE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - the bible ships with the app
        return ()
    for member in payload.get("cast") or []:
        if not isinstance(member, dict):
            continue
        raw = str(member.get("name") or "").strip()
        if not raw:
            continue
        names.add(fold_for_comparison(raw))
        first = raw.split()[0].strip("«»\"' ")
        # One-letter or particle-only fragments would match everything.
        if len(first) >= 4:
            names.add(fold_for_comparison(first))
    return tuple(sorted(names))


def mentions_fiction(*texts: str | None) -> str | None:
    """The first world-bible name found in ``texts``, or ``None``."""

    for text in texts:
        folded = f" {fold_for_comparison(text)} "
        for name in _world_names():
            if name and f" {name} " in folded:
                return name
    return None


def scene_mentions_fiction(scene: dict[str, Any]) -> str | None:
    """Whether a generated rehearsal scene names anyone from the story."""

    return mentions_fiction(*_scene_texts(scene))


# ---------------------------------------------------------------------------
# 1. The declaration, structured
# ---------------------------------------------------------------------------


def normalize_declaration(value: str | None) -> str:
    """One line of the learner's own words, bounded for a paid request."""

    text = " ".join(str(value or "").split()).strip()
    return text[:DECLARATION_MAX_CHARS]


_WEEKDAYS_FR: dict[str, int] = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}
_WEEKDAYS_EN: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_WEEKDAYS_DE: dict[str, int] = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
    "freitag": 4, "samstag": 5, "sonntag": 6,
}
_TOMORROW_WORDS = ("demain", "tomorrow", "morgen")


def resolve_event_date(value: str | None, *, today: date) -> date | None:
    """A real date from what the learner (or the structurer) named, or ``None``.

    ``None`` is a first-class answer and never a guess: with no resolvable date
    the debrief is simply offered as soon as the rehearsal is done, which is
    honest, rather than nagging the learner on a day nobody named.
    """

    raw = " ".join(str(value or "").split()).strip().lower()
    if not raw:
        return None
    if _ISO_DATE.match(raw):
        try:
            resolved = date.fromisoformat(raw)
        except ValueError:
            return None
        if today <= resolved <= today + timedelta(days=MAX_EVENT_HORIZON_DAYS):
            return resolved
        return None
    folded = fold_for_comparison(raw)
    if any(word in folded for word in _TOMORROW_WORDS):
        return today + timedelta(days=1)
    for table in (_WEEKDAYS_FR, _WEEKDAYS_EN, _WEEKDAYS_DE):
        for name, index in table.items():
            if name in folded:
                ahead = (index - today.weekday()) % 7
                # "Tuesday" said on a Tuesday means next Tuesday, not today:
                # a rehearsal is for something that has not happened yet.
                return today + timedelta(days=ahead or 7)
    return None


def normalize_brief(
    parsed: Any, *, declaration: str, today: date, native_language: str | None = None
) -> dict[str, Any]:
    """The structured situation: goal, counterpart, register, date, facts.

    Every field is bounded and typed here rather than trusted from the model.
    An unusable field falls back to something honest — an unrecognised register
    becomes ``vous`` (the safe one with a stranger), an unresolvable date
    becomes no date at all — and the learner's own words are always kept.
    """

    payload = parsed if isinstance(parsed, dict) else {}
    register = str(payload.get("register") or "").strip().lower()
    if register not in REGISTERS:
        register = "vous"
    facts = [
        " ".join(str(item).split())[:160]
        for item in (payload.get("facts") or [])
        if str(item or "").strip()
    ][:5]
    date_text = " ".join(str(payload.get("date_text") or "").split())[:60]
    resolved = resolve_event_date(payload.get("date_iso"), today=today) or resolve_event_date(
        date_text, today=today
    )
    return {
        "declaration": declaration,
        "goal_fr": " ".join(str(payload.get("goal_fr") or "").split())[:160],
        "goal_native": " ".join(str(payload.get("goal_native") or "").split())[:160],
        "counterpart": " ".join(str(payload.get("counterpart") or "").split())[:80],
        "register": register,
        "date_text": date_text,
        "date_iso": resolved.isoformat() if resolved else None,
        "facts": facts,
        "native_language": normalize_control_language(native_language),
        "structured_by": "model",
    }


def brief_is_usable(brief: dict[str, Any]) -> bool:
    """A structure with no goal and no counterpart structured nothing."""

    return bool(str(brief.get("goal_fr") or "").strip()) and bool(
        str(brief.get("counterpart") or "").strip()
    )


# ---------------------------------------------------------------------------
# 2. The rehearsal scene
# ---------------------------------------------------------------------------


def _clean_line(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def _words(text: str | None) -> int:
    return len([chunk for chunk in str(text or "").split() if chunk])


def normalize_scene(parsed: Any, *, brief: dict[str, Any], level_band: str) -> dict[str, Any]:
    """Shape a generated scene into the stored contract. Never validates."""

    payload = parsed if isinstance(parsed, dict) else {}
    points: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("points") or []):
        if not isinstance(item, dict):
            continue
        cues = [
            fold_for_comparison(cue)
            for cue in (item.get("cues_fr") or [])
            if str(cue or "").strip()
        ]
        points.append(
            {
                "id": _clean_line(item.get("id") or f"point_{index + 1}", 40) or f"point_{index + 1}",
                "label_fr": _clean_line(item.get("label_fr"), 120),
                "cues": [cue for cue in cues if cue][:8],
            }
        )
    phrases: list[dict[str, str]] = []
    for item in payload.get("phrases") or []:
        if not isinstance(item, dict):
            continue
        phrases.append(
            {
                "fr": _clean_line(item.get("fr"), 120),
                "native": _clean_line(item.get("native"), 120),
            }
        )
    endings: dict[str, dict[str, str]] = {}
    for key, item in (payload.get("endings") or {}).items():
        if not isinstance(item, dict):
            continue
        endings[str(key).strip().lower()] = {
            "line_fr": _clean_line(item.get("line_fr"), 200),
            "summary_fr": _clean_line(item.get("summary_fr"), 200),
        }
    turns = int(payload.get("turns") or 0)
    return {
        "version": REHEARSAL_VERSION,
        "level_band": str(level_band),
        "register": str(brief.get("register") or "vous"),
        "counterpart_name": _clean_line(brief.get("counterpart"), 80),
        "title_fr": _clean_line(payload.get("title_fr"), 80),
        "place_fr": _clean_line(payload.get("place_fr"), 80),
        "setup_fr": _clean_line(payload.get("setup_fr"), 400),
        "setup_native": _clean_line(payload.get("setup_native"), 400),
        "objective_fr": _clean_line(payload.get("objective_fr"), 200),
        "objective_native": _clean_line(payload.get("objective_native"), 200),
        "opening_line_fr": _clean_line(payload.get("opening_line_fr"), 200),
        #: The private rubric. Never sent to the client before the rehearsal is
        #: over — ``public_view`` is the only reader that decides that.
        "rubric_native": _clean_line(payload.get("rubric_native"), 400),
        "points": points[:MAX_POINTS],
        "phrases": phrases[:4],
        "endings": endings,
        "turns": min(MAX_TURNS, max(MIN_TURNS, turns or MIN_TURNS)),
        "phrases_revealed_at": None,
    }


def _scene_spoken_lines(scene: dict[str, Any]) -> list[str]:
    lines = [str(scene.get("opening_line_fr") or "")]
    lines.extend(str(item.get("line_fr") or "") for item in (scene.get("endings") or {}).values())
    return [line for line in lines if line.strip()]


def _scene_texts(scene: dict[str, Any]) -> list[str]:
    texts = [
        str(scene.get("title_fr") or ""),
        str(scene.get("place_fr") or ""),
        str(scene.get("setup_fr") or ""),
        str(scene.get("setup_native") or ""),
        str(scene.get("objective_fr") or ""),
        str(scene.get("objective_native") or ""),
        str(scene.get("rubric_native") or ""),
        *_scene_spoken_lines(scene),
        *(str(item.get("summary_fr") or "") for item in (scene.get("endings") or {}).values()),
        *(str(item.get("fr") or "") for item in (scene.get("phrases") or [])),
        *(str(item.get("label_fr") or "") for item in (scene.get("points") or [])),
    ]
    return [text for text in texts if text]


def _pre_answer_texts(scene: dict[str, Any]) -> list[str]:
    """Everything the learner reads *before* they answer."""

    return [
        str(scene.get("title_fr") or ""),
        str(scene.get("setup_fr") or ""),
        str(scene.get("setup_native") or ""),
        str(scene.get("objective_fr") or ""),
        str(scene.get("objective_native") or ""),
        str(scene.get("opening_line_fr") or ""),
    ]


def validate_rehearsal_scene(scene: dict[str, Any], *, register: str) -> list[str]:
    """Problems with a rehearsal scene. Empty means it may be shown.

    The same guarantees ``journey_content.validate_scenario_brief`` gives an
    authored journey scene, applied to the shape a rehearsal has: nothing empty,
    band-appropriate lengths, one declared register kept in character speech,
    typed ending keys, no fiction, and — the no-spoil gate — no useful phrase
    leaking into anything the learner reads before answering.
    """

    problems: list[str] = []
    limits = BAND_LIMITS.get(str(scene.get("level_band") or ""), BAND_LIMITS["A2"])

    for label in (
        "title_fr",
        "setup_fr",
        "setup_native",
        "objective_fr",
        "objective_native",
        "opening_line_fr",
        "rubric_native",
    ):
        if not str(scene.get(label) or "").strip():
            problems.append(f"{label} is empty")

    if _words(scene.get("setup_fr")) > limits["setup_words"]:
        problems.append(
            f"setup_fr is {_words(scene.get('setup_fr'))} words, over the "
            f"{scene.get('level_band')} limit of {limits['setup_words']}"
        )
    for line in _scene_spoken_lines(scene):
        if _words(line) > limits["line_words"]:
            problems.append(
                f"a spoken line is {_words(line)} words, over the "
                f"{scene.get('level_band')} limit of {limits['line_words']}"
            )

    points = scene.get("points") or []
    if not MIN_POINTS <= len(points) <= MAX_POINTS:
        problems.append(f"{len(points)} rubric points, outside {MIN_POINTS}..{MAX_POINTS}")
    for point in points:
        if not str(point.get("label_fr") or "").strip():
            problems.append("a rubric point has no label")
        if not point.get("cues"):
            problems.append(f"rubric point {point.get('id')!r} has no cue to recognise it by")

    endings = scene.get("endings") or {}
    if not MIN_ENDINGS <= len(endings) <= MAX_ENDINGS:
        problems.append(f"{len(endings)} endings, outside {MIN_ENDINGS}..{MAX_ENDINGS}")
    for key, item in endings.items():
        if not _OUTCOME_KEY.match(str(key)):
            problems.append(f"ending key {key!r} is not a typed snake_case key")
        if not str(item.get("line_fr") or "").strip():
            problems.append(f"ending {key!r} has no line")
        if not str(item.get("summary_fr") or "").strip():
            problems.append(f"ending {key!r} has no summary")

    if not MIN_TURNS <= int(scene.get("turns") or 0) <= MAX_TURNS:
        problems.append(f"turns {scene.get('turns')!r} is outside {MIN_TURNS}..{MAX_TURNS}")

    declared = str(register or "vous")
    opposite = _TU_MARKERS if declared == "vous" else _VOUS_MARKERS
    expected = _VOUS_MARKERS if declared == "vous" else _TU_MARKERS
    spoken = _scene_spoken_lines(scene)
    for line in spoken:
        if opposite.search(line):
            problems.append(f"register break: a {declared} scene contains {line!r}")
    if spoken and not any(expected.search(line) for line in spoken):
        problems.append(f"no line carries the declared {declared} register")

    # No-spoil gate: the phrases are help, and help is on request. A phrase that
    # is already printed in the setup was never held back.
    pre_answer = [fold_for_comparison(text) for text in _pre_answer_texts(scene)]
    for phrase in scene.get("phrases") or []:
        needle = fold_for_comparison(phrase.get("fr"))
        if not needle:
            problems.append("a useful phrase is empty")
            continue
        if any(needle in text for text in pre_answer if text):
            problems.append("a useful phrase leaks into a pre-answer field")
            break

    intruder = scene_mentions_fiction(scene)
    if intruder is not None:
        problems.append(f"the rehearsal names {intruder!r}, who belongs to the story, not to life")

    return problems


# ---------------------------------------------------------------------------
# 3. The bounded conversation
# ---------------------------------------------------------------------------

#: The rehearsal's pseudo-scenario key. Deliberately not a ``CapabilityKey``:
#: a rehearsal is not one of the three certified capabilities, and calling it
#: one would let a private situation claim a public capability state.
REHEARSAL_SCENARIO_KEY = "rehearsal"
REHEARSAL_CHARACTER_ID = "rehearsal_counterpart"
REHEARSAL_LOCATION_ID = "rehearsal_place"
#: The intent the conversation module has no detector for. Its fallback —
#: "an intent this module has no detector for is not a hidden failure" — is
#: exactly right here: the *rubric points* below decide whether the objective
#: was met, and they are checked in this file against the scene's own cues.
REHEARSAL_INTENT = "carry_out_the_declared_goal"


def scenario_brief_for(rehearsal: Rehearsal) -> ScenarioBrief:
    """The journey content adapter's contract, filled from a rehearsal row.

    ``story_context`` stays empty on purpose. It is what keeps
    :func:`evaluate_response` on its deterministic path rather than delegating
    to the living story — a rehearsal must never reach a module that can write
    story state.
    """

    scene = dict(rehearsal.scene or {})
    endings = scene.get("endings") or {}
    counterpart = str(scene.get("counterpart_name") or "").strip() or "Votre interlocuteur"
    task = ResponseTask(
        objective_native=str(scene.get("objective_native") or ""),
        character_id=REHEARSAL_CHARACTER_ID,
        character_name=counterpart,
        opening_line_fr=str(scene.get("opening_line_fr") or ""),
        # One normal turn plus one repair inside the conversation module; this
        # file owns the 3..6 rehearsal bound (see ``conversation_turn_index``).
        max_turns=1,
        repair_allowed=True,
        targets=[],
        required_intents=[REHEARSAL_INTENT],
        optional_intents=[],
        allowed_outcomes=sorted(endings),
        rubric_native=str(scene.get("rubric_native") or ""),
        suggested_response_fr=None,
        hint_native=None,
        estimated_seconds=120,
    )
    return ScenarioBrief(
        scenario_key=REHEARSAL_SCENARIO_KEY,
        content_version=REHEARSAL_VERSION,
        title_fr=str(scene.get("title_fr") or ""),
        objective_key="rehearsal_objective",
        objective_native=str(scene.get("objective_native") or ""),
        level_band=str(scene.get("level_band") or "A1"),
        character_id=REHEARSAL_CHARACTER_ID,
        character_name=counterpart,
        location_id=REHEARSAL_LOCATION_ID,
        location_name=str(scene.get("place_fr") or ""),
        image_url=None,
        setup_fr=str(scene.get("setup_fr") or ""),
        setup_native=str(scene.get("setup_native") or ""),
        opening_line_fr=str(scene.get("opening_line_fr") or ""),
        response_task=task,
        resolution_lines={key: str(item.get("line_fr") or "") for key, item in endings.items()},
        resolution_summaries={
            key: str(item.get("summary_fr") or "") for key, item in endings.items()
        },
        serial_thread_id=None,
        serial_episode_id=None,
        is_authored_fallback=False,
        story_context={},
    )


def conversation_turn_index(turn: int, total: int) -> int:
    """What the conversation module is told about *this* rehearsal turn.

    That module budgets a journey's two turns; a rehearsal has three to six, and
    this file owns them. The only thing it needs to know per call is whether a
    follow-up is still possible, so it is told ``0`` while turns remain and the
    last index of its own budget on the final turn — after which it stops asking
    for a repair the learner will never be given.
    """

    return 0 if turn < max(0, total - 1) else 1


def covered_point_ids(scene: dict[str, Any], learner_texts: list[str]) -> list[str]:
    """Which rubric points the learner has hit, over the whole rehearsal.

    Cumulative and deterministic: a point made on turn one still counts on turn
    three, because a conversation is not a set of independent questions.
    """

    haystack = " ".join(fold_for_comparison(text) for text in learner_texts if text)
    hit: list[str] = []
    for point in scene.get("points") or []:
        cues = [str(cue) for cue in (point.get("cues") or []) if str(cue).strip()]
        if any(cue in haystack for cue in cues):
            hit.append(str(point.get("id")))
    return hit


def rehearsal_outcome(scene: dict[str, Any], covered: list[str]) -> TaskOutcome:
    """``met`` / ``partially_met`` / ``not_yet`` for the rehearsal as a whole."""

    points = [str(point.get("id")) for point in (scene.get("points") or [])]
    if not points:
        return TaskOutcome.NOT_YET
    if len(covered) >= len(points):
        return TaskOutcome.MET
    return TaskOutcome.PARTIALLY_MET if covered else TaskOutcome.NOT_YET


def ending_for(scene: dict[str, Any], outcome: TaskOutcome) -> str | None:
    """The ending a finished rehearsal lands on.

    Keys are sorted so the choice is deterministic; the *first* key is the one
    the generator is told to make the successful ending, and anything short of
    ``met`` takes the next one rather than claiming a success ending.
    """

    keys = sorted(scene.get("endings") or {})
    if not keys:
        return None
    if outcome is TaskOutcome.MET:
        return keys[0]
    return keys[-1] if len(keys) > 1 else keys[0]


def sanitize_correction(correction: Correction | None, *, register: str) -> Correction | None:
    """Drop a correction that belongs to the story rather than to this learner.

    Two real hazards, both from the shared conversation module:

    * its register rules are declared ``vous`` only, and a rehearsal whose
      counterpart the learner addresses as *tu* would otherwise be "corrected"
      into *vous* — the very register the structurer decided against;
    * one of those rules explains itself by naming a world-bible character.
      A correction that says "Margaux still uses vous with you here" has no
      business in a call to the learner's real landlord.
    """

    if correction is None:
        return None
    if mentions_fiction(correction.note_native, correction.corrected_fr) is not None:
        return None
    if register == "tu":
        swaps_to_vous = _VOUS_MARKERS.search(correction.corrected_fr or "") and _TU_MARKERS.search(
            correction.span_fr or ""
        )
        if swaps_to_vous:
            return None
    return correction


# ---------------------------------------------------------------------------
# 4. The weekly cap
# ---------------------------------------------------------------------------


def weekly_cap() -> int:
    return max(0, int(getattr(settings, "ATELIER_REHEARSAL_WEEKLY_CAP", 0) or 0))


def cap_state(db: Session, user: User, *, now: datetime | None = None) -> dict[str, Any]:
    """How many rehearsals this learner may still start, and when the next frees.

    A rehearsal counts from the moment it is *started*, including one that was
    abandoned: the scene generation was already paid for, and a cap that
    refunded abandonment would be a cap in name only.
    """

    moment = now or datetime.now(UTC)
    window_start = moment - timedelta(days=7)
    rows = list(
        db.scalars(
            select(Rehearsal.created_at)
            .where(Rehearsal.user_id == user.id, Rehearsal.created_at >= window_start)
            .order_by(Rehearsal.created_at.asc())
        )
    )
    limit = weekly_cap()
    used = len(rows)
    next_slot: datetime | None = None
    if limit and used >= limit and rows:
        oldest = rows[max(0, used - limit)]
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        next_slot = oldest + timedelta(days=7)
    return {
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "next_slot_at": next_slot.isoformat() if next_slot else None,
    }


# ---------------------------------------------------------------------------
# 5. Cost
# ---------------------------------------------------------------------------


def _record_cost(
    db: Session,
    event_type: str,
    *,
    user_id: UUID | None,
    rehearsal_id: UUID | None,
    payload: dict[str, Any],
    result: Any = None,
) -> None:
    """One pilot-cost row per real call. Telemetry never breaks a rehearsal."""

    body = dict(payload)
    if result is not None:
        body.update(
            {
                "provider": getattr(result, "provider", None),
                "model": getattr(result, "model", None),
                "prompt_tokens": int(getattr(result, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(result, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
                "cost_known": True,
            }
        )
    try:
        PilotEventService(db).record(
            event_type,
            user_id=user_id,
            entity_type="rehearsal",
            entity_id=rehearsal_id,
            payload=body,
            cost_usd=float(getattr(result, "cost", 0.0) or 0.0),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Rehearsal cost row {} could not be written", event_type)


# ---------------------------------------------------------------------------
# 6. Prompts
# ---------------------------------------------------------------------------

_PREPARE_RESPONSE_FORMAT: dict[str, Any] = {"type": "json_object"}

_PREPARE_SYSTEM_PROMPT = (
    "You prepare ONE rehearsal of a REAL situation a French learner is about to live. "
    "This is not fiction and not a story: the counterpart is a real person in the learner's "
    "life. Never invent a named character, never reuse a name from any story, never invent "
    "facts the learner did not give you.\n"
    "Return one JSON object with exactly these keys:\n"
    '{"brief": {"goal_fr", "goal_native", "counterpart", "register", "date_text", "date_iso", '
    '"facts"}, "scene": {"title_fr", "place_fr", "setup_fr", "setup_native", "objective_fr", '
    '"objective_native", "opening_line_fr", "rubric_native", "points", "phrases", "endings", '
    '"turns"}}\n'
    "brief rules:\n"
    "- goal_fr is the one thing the learner must achieve, in French, max 15 words. "
    "goal_native is the same in the learner's own language.\n"
    "- counterpart is what the learner called them (« le propriétaire », « ma collègue »), "
    "never a first name you made up.\n"
    "- register is exactly 'tu' or 'vous' — 'vous' for anyone official, a stranger, a "
    "landlord, a doctor, an administration; 'tu' only for a friend or a relative.\n"
    "- date_text is the learner's own words for when it happens; date_iso is YYYY-MM-DD when "
    "you can resolve it from the given today's date, otherwise null.\n"
    "- facts: at most 5 short French facts the learner actually gave. No invention.\n"
    "scene rules:\n"
    "- The scene is the real conversation, at the learner's level band. setup_fr is short and "
    "in French; setup_native is the same for a learner who needs it.\n"
    "- opening_line_fr is the counterpart's first line, in the declared register.\n"
    "- objective_fr / objective_native tell the learner what to achieve, never how to say it.\n"
    "- rubric_native is PRIVATE: how you will judge the rehearsal. The learner never reads it.\n"
    "- points: 2 to 4 entries {id, label_fr, cues_fr}. Each is one thing that must be "
    "communicated. cues_fr are 2-6 short French words or phrases that would show it was said. "
    "Cues are for recognition; they are never shown to the learner.\n"
    "- phrases: 2 to 4 entries {fr, native} the learner may ask for. They are HELP, held back "
    "until requested: none of them may appear in setup_fr, in the objective, or in the "
    "opening line.\n"
    "- endings: 2 or 3 entries keyed by snake_case. The FIRST key alphabetically must be the "
    "successful ending. Each is {line_fr, summary_fr}: what the counterpart says, and one "
    "French line summarising what was settled.\n"
    "- turns: how many learner turns this needs, between 3 and 6.\n"
    "- Every French line is at the learner's band: short sentences, common words, no idiom a "
    "beginner has not met."
)

_CORRECTION_RESPONSE_FORMAT: dict[str, Any] = {"type": "json_object"}

_CORRECTION_SYSTEM_PROMPT = (
    "You correct ONE line of French a learner wrote about how a real situation went. "
    'Return one JSON object: {"corrected_fr": string, "note_fr": string, "already_correct": '
    "boolean}.\n"
    "- corrected_fr is their sentence, repaired, keeping their meaning and their words wherever "
    "they were right. Never rewrite it into a better sentence they did not write.\n"
    "- note_fr is ONE short French clause naming what changed, max 20 words. Never a lecture.\n"
    "- already_correct is true when there was nothing to repair; then corrected_fr is their own "
    "sentence unchanged and note_fr says so in French.\n"
    "- Never comment on the real event, never advise, never praise."
)


# ---------------------------------------------------------------------------
# 7. Reading a rehearsal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RehearsalResult:
    """What the stored turns add up to. Derived, never a second source of truth."""

    covered: list[str]
    outcome: TaskOutcome
    ending_key: str | None
    ending_line_fr: str | None
    ending_summary_fr: str | None
    turns_used: int
    turns_total: int


def scored_turns(rehearsal: Rehearsal) -> list[dict[str, Any]]:
    return [turn for turn in (rehearsal.turns or []) if turn.get("scored")]


def rehearsal_result(rehearsal: Rehearsal) -> RehearsalResult:
    scene = dict(rehearsal.scene or {})
    turns = scored_turns(rehearsal)
    covered = covered_point_ids(scene, [str(turn.get("learner_text") or "") for turn in turns])
    outcome = rehearsal_outcome(scene, covered)
    key = ending_for(scene, outcome) if turns else None
    ending = (scene.get("endings") or {}).get(key or "", {})
    return RehearsalResult(
        covered=covered,
        outcome=outcome,
        ending_key=key,
        ending_line_fr=str(ending.get("line_fr") or "") or None,
        ending_summary_fr=str(ending.get("summary_fr") or "") or None,
        turns_used=len(turns),
        turns_total=int(scene.get("turns") or 0),
    )


def debrief_available(rehearsal: Rehearsal, *, today: date) -> bool:
    """Whether "Comment ça s'est passé ?" may be asked yet.

    On or after the declared date. With no date, as soon as the rehearsal is
    done — asking about an event nobody dated is the learner's call, not ours.
    """

    if rehearsal.status != "rehearsed":
        return False
    if rehearsal.event_date is None:
        return True
    return today >= rehearsal.event_date


def public_view(rehearsal: Rehearsal, *, today: date | None = None) -> dict[str, Any]:
    """Everything the client may see — and nothing it may not.

    The private rubric and the recognition cues never cross this line while the
    rehearsal is live: a learner who can read the cues is not rehearsing, they
    are copying. The rubric is released once the rehearsal is over, because by
    then it explains the grade instead of giving it away.
    """

    scene = dict(rehearsal.scene or {})
    result = rehearsal_result(rehearsal)
    finished = rehearsal.status in ("rehearsed", "debriefed")
    revealed = scene.get("phrases_revealed_at") is not None
    brief = dict(rehearsal.brief or {})
    return {
        "version": str(rehearsal.version or REHEARSAL_VERSION),
        "id": str(rehearsal.id),
        "status": str(rehearsal.status),
        "declaration": str(rehearsal.declaration or ""),
        "brief": {
            "goal_fr": brief.get("goal_fr", ""),
            "goal_native": brief.get("goal_native", ""),
            "counterpart": brief.get("counterpart", ""),
            "register": brief.get("register", "vous"),
            "date_text": brief.get("date_text", ""),
            "date_iso": brief.get("date_iso"),
            "facts": list(brief.get("facts") or []),
        },
        "scene": (
            {
                "title_fr": scene.get("title_fr", ""),
                "place_fr": scene.get("place_fr", ""),
                "setup_fr": scene.get("setup_fr", ""),
                "setup_native": scene.get("setup_native", ""),
                "objective_fr": scene.get("objective_fr", ""),
                "objective_native": scene.get("objective_native", ""),
                "opening_line_fr": scene.get("opening_line_fr", ""),
                "register": scene.get("register", "vous"),
                "level_band": scene.get("level_band", ""),
                "turns_total": result.turns_total,
                # Held back until asked for, then kept visible.
                "phrases": list(scene.get("phrases") or []) if revealed else [],
                "phrases_revealed": revealed,
                # Released only when it can no longer be the answer.
                "rubric_native": scene.get("rubric_native", "") if finished else None,
            }
            if scene
            else None
        ),
        "turns": [
            {
                "index": turn.get("index"),
                "learner_text": turn.get("learner_text", ""),
                "mode": turn.get("mode", "text"),
                "reply_fr": turn.get("reply_fr"),
                "reply_source": turn.get("reply_source"),
                "correction": turn.get("correction"),
                "outcome": turn.get("outcome"),
                "evidence_kind": turn.get("evidence_kind"),
                "assistance": turn.get("assistance"),
            }
            for turn in (rehearsal.turns or [])
            if turn.get("scored")
        ],
        "turns_used": result.turns_used,
        "turns_total": result.turns_total,
        "result": {
            "outcome": str(result.outcome),
            "points_total": len(scene.get("points") or []),
            "points_covered": len(result.covered),
            "ending_key": result.ending_key,
            "ending_line_fr": result.ending_line_fr,
            "ending_summary_fr": result.ending_summary_fr,
        }
        if finished
        else None,
        "event_date": rehearsal.event_date.isoformat() if rehearsal.event_date else None,
        "debrief": dict(rehearsal.debrief or {}) or None,
        "outcome": rehearsal.outcome,
        "debrief_available": debrief_available(
            rehearsal, today=today or datetime.now(UTC).date()
        ),
    }


# ---------------------------------------------------------------------------
# 8. The service
# ---------------------------------------------------------------------------


class RehearsalService:
    """Declare, prepare, rehearse, debrief. Never commits."""

    def __init__(self, db: Session, *, llm_service: LLMService | None = None) -> None:
        self.db = db
        self._llm_service = llm_service
        self._llm_unavailable = False

    # -- reading ---------------------------------------------------------

    def latest(self, user: User) -> Rehearsal | None:
        return (
            self.db.query(Rehearsal)
            .filter(Rehearsal.user_id == user.id)
            .order_by(Rehearsal.created_at.desc(), Rehearsal.id.desc())
            .first()
        )

    def open_rehearsal(self, user: User) -> Rehearsal | None:
        """The one the learner is in the middle of, if any."""

        return (
            self.db.query(Rehearsal)
            .filter(
                Rehearsal.user_id == user.id,
                Rehearsal.status.in_(("declared", "ready", "not_prepared", "rehearsing")),
            )
            .order_by(Rehearsal.created_at.desc(), Rehearsal.id.desc())
            .first()
        )

    def awaiting_debrief(self, user: User, *, today: date) -> Rehearsal | None:
        """A finished rehearsal whose real event is due — the debrief queue."""

        rows = (
            self.db.query(Rehearsal)
            .filter(Rehearsal.user_id == user.id, Rehearsal.status == "rehearsed")
            .order_by(Rehearsal.created_at.asc())
            .all()
        )
        for row in rows:
            if debrief_available(row, today=today):
                return row
        return None

    def load(self, user: User, rehearsal_id: UUID) -> Rehearsal | None:
        return (
            self.db.query(Rehearsal)
            .filter(Rehearsal.id == rehearsal_id, Rehearsal.user_id == user.id)
            .first()
        )

    # -- 1. declare ------------------------------------------------------

    def declare(self, user: User, *, declaration: str, now: datetime | None = None) -> Rehearsal:
        """Store the learner's situation and try, once, to prepare it."""

        moment = now or datetime.now(UTC)
        text = normalize_declaration(declaration)
        if not text:
            raise RehearsalRefused("declaration_empty")
        if weekly_cap() <= 0:
            raise RehearsalRefused("rehearsal_disabled")
        state = cap_state(self.db, user, now=moment)
        if state["remaining"] <= 0:
            raise RehearsalRefused("weekly_cap_reached")
        if self.open_rehearsal(user) is not None:
            raise RehearsalRefused("rehearsal_already_open")

        rehearsal = Rehearsal(
            user_id=user.id,
            status="declared",
            version=REHEARSAL_VERSION,
            declaration=text,
            brief={
                "declaration": text,
                "register": "vous",
                "native_language": normalize_control_language(user.native_language),
                "structured_by": "pending",
            },
            scene={},
            turns=[],
            debrief={},
        )
        self.db.add(rehearsal)
        self.db.flush([rehearsal])
        self.prepare(user, rehearsal, now=moment)
        return rehearsal

    # -- 2. prepare ------------------------------------------------------

    def prepare(
        self, user: User, rehearsal: Rehearsal, *, now: datetime | None = None
    ) -> Rehearsal:
        """Structure the declaration and generate the scene, or say it failed."""

        if rehearsal.status not in ("declared", "not_prepared"):
            raise RehearsalRefused("rehearsal_not_preparable")
        moment = now or datetime.now(UTC)
        today = moment.date()
        level_band = learner_level_band(user)

        llm = self._get_llm_service()
        if llm is None:
            self._mark_unprepared(rehearsal, "provider_unavailable")
            return rehearsal

        payload = {
            "declaration": rehearsal.declaration,
            "today": today.isoformat(),
            "learner_level_band": level_band,
            "learner_native_language": normalize_control_language(user.native_language),
        }
        last_reason = "generation_failed"
        for attempt in range(1, MAX_PREPARE_ATTEMPTS + 1):
            try:
                result = llm.generate_chat_completion(
                    [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    system_prompt=_PREPARE_SYSTEM_PROMPT,
                    response_format=_PREPARE_RESPONSE_FORMAT,
                    temperature=0.4,
                    max_tokens=settings.ATELIER_CRITIQUE_LLM_MAX_TOKENS,
                    request_timeout=settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS,
                    disable_retries=True,
                    reasoning_effort=settings.ATELIER_EXERCISE_LLM_REASONING_EFFORT,
                )
            except (LLMProviderError, ValueError, TypeError) as exc:
                logger.warning("Rehearsal preparation call failed: {}", exc)
                last_reason = "provider_failed"
                continue
            _record_cost(
                self.db,
                PREPARE_EVENT_TYPE,
                user_id=user.id,
                rehearsal_id=rehearsal.id,
                payload={"attempt": attempt, "level_band": level_band},
                result=result,
            )
            try:
                parsed = json.loads(result.content)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Rehearsal preparation was unparsable: {}", exc)
                last_reason = "unparsable"
                continue
            if not isinstance(parsed, dict):
                last_reason = "unparsable"
                continue

            brief = normalize_brief(
                parsed.get("brief"),
                declaration=rehearsal.declaration,
                today=today,
                native_language=user.native_language,
            )
            if not brief_is_usable(brief):
                last_reason = "brief_unusable"
                continue
            scene = normalize_scene(
                parsed.get("scene"), brief=brief, level_band=level_band
            )
            problems = validate_rehearsal_scene(scene, register=str(brief["register"]))
            if problems:
                logger.warning("Rehearsal scene rejected: {}", problems[:3])
                last_reason = "scene_invalid"
                continue

            rehearsal.brief = brief
            rehearsal.scene = scene
            rehearsal.event_date = (
                date.fromisoformat(brief["date_iso"]) if brief.get("date_iso") else None
            )
            rehearsal.status = "ready"
            rehearsal.failure_reason = None
            self.db.add(rehearsal)
            return rehearsal

        self._mark_unprepared(rehearsal, last_reason)
        return rehearsal

    def _mark_unprepared(self, rehearsal: Rehearsal, reason: str) -> None:
        """No scene, and it says so. The declaration is never lost."""

        rehearsal.status = "not_prepared"
        rehearsal.scene = {}
        rehearsal.failure_reason = reason[:64]
        self.db.add(rehearsal)
        logger.info(
            "rehearsal_not_prepared", rehearsal_id=str(rehearsal.id), reason=reason
        )

    # -- 3. the phrases, on request --------------------------------------

    def reveal_phrases(self, rehearsal: Rehearsal) -> Rehearsal:
        """Hand over the useful phrases, and book the assistance.

        Help is not free in the evidence rubric: from here on the rehearsal's
        turns are *supported* production, never independent. That is the whole
        reason the phrases are a request rather than a panel.
        """

        if rehearsal.status not in ("ready", "rehearsing"):
            raise RehearsalRefused("rehearsal_not_live")
        scene = dict(rehearsal.scene or {})
        if not scene.get("phrases"):
            raise RehearsalRefused("no_phrases_available")
        if scene.get("phrases_revealed_at") is None:
            scene["phrases_revealed_at"] = len(scored_turns(rehearsal))
            rehearsal.scene = scene
            self.db.add(rehearsal)
        return rehearsal

    # -- 4. the turns ----------------------------------------------------

    def respond(
        self,
        user: User,
        rehearsal: Rehearsal,
        *,
        text: str,
        mode: str = "text",
        turn_index: int,
        now: datetime | None = None,
    ) -> Rehearsal:
        """Grade one rehearsal turn through the journey conversation machinery."""

        if rehearsal.status not in ("ready", "rehearsing"):
            raise RehearsalRefused("rehearsal_not_live")
        moment = now or datetime.now(UTC)
        scene = dict(rehearsal.scene or {})
        total = int(scene.get("turns") or 0)
        history = scored_turns(rehearsal)
        if turn_index < len(history):
            # A replayed submit returns the stored grading and pays nothing.
            return rehearsal
        if turn_index != len(history):
            raise RehearsalRefused("turn_out_of_order")
        if len(history) >= total:
            raise RehearsalRefused("turn_budget_spent")

        assistance = (
            AssistanceLevel.SUGGESTED_RESPONSE
            if scene.get("phrases_revealed_at") is not None
            else AssistanceLevel.NONE
        )
        brief = scenario_brief_for(rehearsal)
        answer = AttemptAnswer(
            mode=InputMode(mode) if mode in tuple(InputMode) else InputMode.TEXT,
            text=str(text or "")[:ANSWER_MAX_CHARS],
        )
        evaluation = evaluate_response(
            self.db,
            user=user,
            scenario=brief,
            task=brief.response_task,
            answer=answer,
            turn_index=conversation_turn_index(len(history), total),
            assistance=assistance,
            history=[
                {"role": "learner", "text": str(turn.get("learner_text") or "")}
                for turn in history
            ],
        )

        records = list(rehearsal.turns or [])
        if evaluation.outcome is TaskOutcome.UNSCORED or evaluation.pending:
            # Infrastructure, not the learner: no turn spent, nothing booked.
            records.append(
                {
                    "index": len(history),
                    "scored": False,
                    "mode": str(answer.mode),
                    "learner_text": answer.text,
                    "failure_reason": evaluation.failure_reason,
                    "at": moment.isoformat(),
                }
            )
            rehearsal.turns = records
            self.db.add(rehearsal)
            return rehearsal

        register = str(scene.get("register") or "vous")
        correction = sanitize_correction(evaluation.correction, register=register)
        reply = str(evaluation.character_reply_fr or "")
        if mentions_fiction(reply) is not None:
            # A reply that named a character would be the story leaking into the
            # learner's real Tuesday. Drop the line rather than show it.
            reply = ""
        provenance = reply_source(evaluation)

        texts = [str(turn.get("learner_text") or "") for turn in history] + [answer.text]
        covered = covered_point_ids(scene, texts)
        outcome = rehearsal_outcome(scene, covered)
        records.append(
            {
                "index": len(history),
                "scored": True,
                "mode": str(answer.mode),
                "learner_text": answer.text,
                "reply_fr": reply or None,
                "reply_source": provenance,
                "correction": (
                    {
                        "span_fr": correction.span_fr,
                        "corrected_fr": correction.corrected_fr,
                        "note_native": correction.note_native,
                    }
                    if correction is not None
                    else None
                ),
                "outcome": str(evaluation.outcome),
                "assistance": str(assistance),
                "evidence_kind": str(
                    classify_evidence(
                        opportunity="open_production",
                        is_correct=outcome is TaskOutcome.MET,
                        assistance=assistance,
                    )
                ),
                "covered_points": covered,
                "at": moment.isoformat(),
            }
        )
        rehearsal.turns = records
        rehearsal.status = "rehearsing"

        used = len(records) - len([turn for turn in records if not turn.get("scored")])
        if used >= total or outcome is TaskOutcome.MET:
            rehearsal.status = "rehearsed"
            rehearsal.rehearsed_at = moment
        self.db.add(rehearsal)

        _record_cost(
            self.db,
            TURN_EVENT_TYPE,
            user_id=user.id,
            rehearsal_id=rehearsal.id,
            payload={
                "turn_index": len(history),
                "outcome": str(evaluation.outcome),
                "assistance": str(assistance),
                "reply_source": provenance,
                # The reply comes from the shared conversation module, which
                # does not price its own provider call. Claiming 0.0 here would
                # be inventing a number: the row says the cost is unknown.
                "cost_known": provenance != "model",
            },
        )
        return rehearsal

    # -- 5. the debrief --------------------------------------------------

    def debrief(
        self,
        user: User,
        rehearsal: Rehearsal,
        *,
        outcome: str,
        free_line: str = "",
        now: datetime | None = None,
    ) -> Rehearsal:
        """"Comment ça s'est passé ?" — the package's success metric."""

        moment = now or datetime.now(UTC)
        if outcome not in REHEARSAL_OUTCOMES:
            raise RehearsalRefused("unknown_outcome")
        if not debrief_available(rehearsal, today=moment.date()):
            raise RehearsalRefused("debrief_not_due")

        line = " ".join(str(free_line or "").split())[:FREE_LINE_MAX_CHARS]
        correction = self._correct_free_line(user, rehearsal, line) if line else None
        rehearsal.debrief = {
            "outcome": outcome,
            "free_line": line,
            "corrected_fr": (correction or {}).get("corrected_fr"),
            "note_fr": (correction or {}).get("note_fr"),
            "already_correct": (correction or {}).get("already_correct"),
            # An uncorrected line is said to be uncorrected. The learner is
            # never shown their own sentence back as if it had been checked.
            "correction_available": correction is not None,
            "recorded_at": moment.isoformat(),
        }
        rehearsal.outcome = outcome
        rehearsal.status = "debriefed"
        rehearsal.debriefed_at = moment
        self.db.add(rehearsal)
        _record_cost(
            self.db,
            DEBRIEF_EVENT_TYPE,
            user_id=user.id,
            rehearsal_id=rehearsal.id,
            payload={
                "outcome": outcome,
                "free_line_words": _words(line),
                "corrected": correction is not None,
                "days_after_event": (
                    (moment.date() - rehearsal.event_date).days
                    if rehearsal.event_date
                    else None
                ),
                "cost_known": True,
            },
        )
        return rehearsal

    def abandon(self, rehearsal: Rehearsal) -> Rehearsal:
        if rehearsal.status in ("debriefed", "abandoned"):
            return rehearsal
        rehearsal.status = "abandoned"
        self.db.add(rehearsal)
        return rehearsal

    # -- provider --------------------------------------------------------

    def _get_llm_service(self) -> LLMService | None:
        if self._llm_service is not None:
            return self._llm_service
        if self._llm_unavailable or not settings.ATELIER_LLM_ENABLED:
            return None
        try:
            self._llm_service = LLMService()
        except Exception as exc:  # pragma: no cover - construction failure
            self._llm_unavailable = True
            logger.info("Rehearsal generator unavailable: {}", exc)
            return None
        return self._llm_service

    def _correct_free_line(
        self, user: User, rehearsal: Rehearsal, line: str
    ) -> dict[str, Any] | None:
        """One paid correction of the debrief line, or ``None``.

        ``None`` means *not corrected*, which the learner is told. It never
        means "correct".
        """

        llm = self._get_llm_service()
        if llm is None:
            return None
        payload = {
            "learner_line": line,
            "context_fr": str((rehearsal.brief or {}).get("goal_fr") or ""),
        }
        try:
            result = llm.generate_error_detection(
                [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=_CORRECTION_SYSTEM_PROMPT,
                response_format=_CORRECTION_RESPONSE_FORMAT,
                temperature=0.0,
                max_tokens=settings.ATELIER_CORRECTION_LLM_MAX_TOKENS,
                model=settings.ATELIER_CORRECTION_LLM_MODEL,
                request_timeout=settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
                reasoning_effort=settings.ATELIER_CORRECTION_LLM_REASONING_EFFORT,
            )
        except (LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Rehearsal debrief correction failed: {}", exc)
            return None
        _record_cost(
            self.db,
            DEBRIEF_EVENT_TYPE + "_correction",
            user_id=user.id,
            rehearsal_id=rehearsal.id,
            payload={"words": _words(line)},
            result=result,
        )
        try:
            parsed = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(parsed, dict):
            return None
        corrected = _clean_line(parsed.get("corrected_fr"), FREE_LINE_MAX_CHARS)
        if not corrected:
            return None
        note = _clean_line(parsed.get("note_fr"), 200)
        if mentions_fiction(corrected, note) is not None:
            return None
        return {
            "corrected_fr": corrected,
            "note_fr": note,
            "already_correct": bool(parsed.get("already_correct")),
        }


# ---------------------------------------------------------------------------
# 9. What the digest reads
# ---------------------------------------------------------------------------


def rehearsal_digest_line(db: Session, *, since: date, until: date | None = None) -> str:
    """One line for ``scripts/pilot_digest.py``: did the real thing happen?

    The rehearsal score is not the metric and never appears here. What appears
    is the only thing WP-31 claims: of the rehearsals whose real event has been
    debriefed, how many the learner actually carried out. A window with no
    debriefs says so rather than printing 0 %.
    """

    end = until or since
    rows = list(
        db.scalars(
            select(Rehearsal).where(
                Rehearsal.status == "debriefed",
                Rehearsal.debriefed_at.is_not(None),
            )
        )
    )
    inside = [
        row
        for row in rows
        if since <= (row.debriefed_at.date() if row.debriefed_at else since) <= end
    ]
    if not inside:
        return "Rehearsals (Répétition): no debriefs in window — nothing to report."
    counts: dict[str, int] = dict.fromkeys(REHEARSAL_OUTCOMES, 0)
    for row in inside:
        key = str(row.outcome or "not_yet")
        counts[key] = counts.get(key, 0) + 1
    total = len(inside)
    done = counts.get("done", 0)
    parts = ", ".join(f"{name}:{counts[name]}" for name in REHEARSAL_OUTCOMES)
    return (
        f"Rehearsals (Répétition, n={total} debriefed): {parts} · "
        f"carried out for real: {done}/{total} ({round(100 * done / total)}%)"
    )


__all__ = [
    "ANSWER_MAX_CHARS",
    "DEBRIEF_EVENT_TYPE",
    "DECLARATION_MAX_CHARS",
    "FREE_LINE_MAX_CHARS",
    "MAX_ENDINGS",
    "MAX_POINTS",
    "MAX_PREPARE_ATTEMPTS",
    "MAX_TURNS",
    "MIN_ENDINGS",
    "MIN_POINTS",
    "MIN_TURNS",
    "PREPARE_EVENT_TYPE",
    "REHEARSAL_CHARACTER_ID",
    "REHEARSAL_SCENARIO_KEY",
    "REHEARSAL_VERSION",
    "REGISTERS",
    "TURN_EVENT_TYPE",
    "RehearsalRefused",
    "RehearsalResult",
    "RehearsalService",
    "brief_is_usable",
    "cap_state",
    "conversation_turn_index",
    "covered_point_ids",
    "debrief_available",
    "ending_for",
    "mentions_fiction",
    "normalize_brief",
    "normalize_declaration",
    "normalize_scene",
    "public_view",
    "rehearsal_digest_line",
    "rehearsal_outcome",
    "rehearsal_result",
    "resolve_event_date",
    "sanitize_correction",
    "scenario_brief_for",
    "scene_mentions_fiction",
    "scored_turns",
    "validate_rehearsal_scene",
    "weekly_cap",
]
