"""Phase 2 «Folge in Akten», PR 4: how much of the story a day read.

The phase's own number (acts doc, «Zählen»): every French word of the story the
learner read or heard — each act's page, its character's lines in the conversation
and its ending — counted the way the planner already prices a page
(``journey_planner.scene_texts``, whitespace words). Exercises do not count, nor do
the learner's own lines, nor the «Lecture» pages around the story. A word heard is a
word read: «Écouter d'abord» reads the same page aloud, so it is counted once.

What counts is what reached the screen: an act once its scene was opened (the step
started, as the archive files it), each line its character said in the reply, and its
ending once it stood there — never while the story lane is still writing it. A day of
one act, every day while ``ATELIER_STORY_ACTS`` is off, is counted the same way.

The number stands on the Fertig screen (``daily_session``) and in the weekly dossier
(``GET /progress/weekly-dossier``), and it is this phase's measure of success.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.services.journey_contracts import StepKind, StepStatus, step_act

logger = logging.getLogger(__name__)

_STORY_KINDS = frozenset({StepKind.SCENE.value, StepKind.RESPOND.value, StepKind.RESOLUTION.value})
_SHOWN = frozenset({StepStatus.ACTIVE.value, StepStatus.COMPLETED.value})


@dataclass(frozen=True, slots=True)
class StoryReading:
    #: The acts whose scene was opened, 0 to 3 on a day.
    acts: int = 0
    #: The story's words read or heard: pages, the characters' lines, endings.
    words: int = 0

    def __add__(self, other: StoryReading) -> StoryReading:
        return StoryReading(acts=self.acts + other.acts, words=self.words + other.words)


def _reached(step: DailyJourneyStep) -> bool:
    """The step was on the learner's screen: it started (WP-L9), or — a step older
    than its start time — it is open or done. A step skipped while on screen counts."""

    return step.started_at is not None or str(step.status) in _SHOWN


def _page_words(journey: DailyJourney, scene: DailyJourneyStep, act: int) -> int:
    """The act's page and its opening line (``scene_texts``), from its pinned brief."""

    from app.services.daily_journey import _brief_from_json
    from app.services.journey_planner import _tokens, scene_texts

    private = scene.private_task if isinstance(scene.private_task, dict) else {}
    payload = private.get("scenario_brief" if act <= 1 else "act_brief")
    if act <= 1 and not isinstance(payload, dict):
        # The first act's brief is pinned on the scene step; an older day may keep it
        # on another step (``DailyJourneyService._pinned_brief`` reads any).
        payload = next(
            (
                (step.private_task or {}).get("scenario_brief")
                for step in journey.steps
                if isinstance((step.private_task or {}).get("scenario_brief"), dict)
            ),
            None,
        )
    if not isinstance(payload, dict):
        return 0
    try:
        brief = _brief_from_json(payload)
    except (KeyError, TypeError, ValueError):
        return 0
    return _tokens(*scene_texts(brief))


def _reply_words(respond: DailyJourneyStep) -> int:
    """Every line the character said in the reply (a many-voiced reply's joined text)."""

    from app.services.journey_planner import _tokens

    private = respond.private_task if isinstance(respond.private_task, dict) else {}
    return _tokens(
        *(str(turn.get("character") or "") for turn in private.get("turns") or [] if isinstance(turn, dict))
    )


def _ending_words(resolution: DailyJourneyStep) -> int:
    """The ending, once it stood on the screen; nothing while the story writes it."""

    from app.services.journey_planner import _tokens

    prompt = resolution.public_prompt if isinstance(resolution.public_prompt, dict) else {}
    if prompt.get("story_pending"):
        return 0
    return _tokens(str(prompt.get("character_line_fr") or ""))


def day_reading(journey: DailyJourney | None) -> StoryReading:
    """What ``journey`` read of its story: the acts it opened and their words."""

    if journey is None:
        return StoryReading()
    by_act: dict[int, dict[str, DailyJourneyStep]] = {}
    for step in sorted(journey.steps, key=lambda item: item.ordinal):
        kind = str(step.kind)
        if kind in _STORY_KINDS:
            by_act.setdefault(step_act(step), {}).setdefault(kind, step)
    reading = StoryReading()
    for act, kinds in sorted(by_act.items()):
        scene = kinds.get(StepKind.SCENE.value)
        if scene is None or not _reached(scene):
            continue
        words = _page_words(journey, scene, act)
        respond = kinds.get(StepKind.RESPOND.value)
        if respond is not None and _reached(respond):
            words += _reply_words(respond)
        resolution = kinds.get(StepKind.RESOLUTION.value)
        if resolution is not None and _reached(resolution):
            words += _ending_words(resolution)
        reading += StoryReading(acts=1, words=words)
    return reading


def period_reading(db: Session, user_id: Any, *, since: datetime) -> StoryReading:
    """Every day started since ``since``, summed (the weekly dossier's window)."""

    journeys = db.scalars(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user_id,
            DailyJourney.started_at.is_not(None),
            DailyJourney.started_at >= since,
        )
        .options(selectinload(DailyJourney.steps))
    ).all()
    reading = StoryReading()
    for journey in journeys:
        reading += day_reading(journey)
    return reading


def safe_day_reading(journey: DailyJourney | None) -> StoryReading:
    """:func:`day_reading` for the today envelope: a fault here costs the Fertig
    screen its count, never the day."""

    try:
        return day_reading(journey)
    except Exception:  # noqa: BLE001 - the envelope must answer
        logger.warning("story_reading: the day's count failed", exc_info=True)
        return StoryReading()


__all__ = ["StoryReading", "day_reading", "period_reading", "safe_day_reading"]
