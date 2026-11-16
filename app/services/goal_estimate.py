"""How much sooner more new words a day reach the learner's goal (owner, 2 Nov 2026).

«Gleichzeitig auch dem Lerner sagen, dass man so schneller an sein Sprachziel
kommt.» Where the learner picks their daily number of new words (Réglages) and on
the «Noch 5 neue Wörter» offer, one short line says how much sooner a faster
pace covers the words of their goal level: «Mit 20 Wörtern am Tag hast du den
Wortschatz für A2 etwa 3 Wochen früher.»

The figure is the words' own clock, the same arithmetic the Tempo sheet's
``daily_session.goal_weeks`` uses: the words still missing to the goal level
(``daily_session.goal_gap``: every band from the one in force to the goal's
last, at 80 % of each band's words) over the words kept a day (the pace times
the scheduler's retention, ``daily_session.WORD_RETENTION``). It says
«Wortschatz», not the level: the rules a week have their own clock, which more
words do not move, so the line never promises the level itself sooner.

No goal (none set, or already passed) or nothing left to learn: no figure, and
the client says only that more words a day get there sooner.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

#: The steps Réglages offers for «Neue Wörter pro Tag»: the paces' 10, 20 and 40
#: and the two between them.
WORD_STEPS: tuple[int, ...] = (10, 15, 20, 30, 40)


def days_sooner(*, words_left: int, base_per_day: int, faster_per_day: int) -> int | None:
    """Days sooner the goal's words are covered at ``faster_per_day`` new words a
    day than at ``base_per_day``. ``None`` when there is no honest figure: no
    words left, a pace that is not faster, or a gain under one day.
    """

    from app.services.daily_session import WORD_RETENTION

    words_left = int(words_left or 0)
    base = int(base_per_day or 0)
    faster = int(faster_per_day or 0)
    if words_left <= 0 or base <= 0 or faster <= base:
        return None
    gained = words_left / (base * WORD_RETENTION) - words_left / (faster * WORD_RETENTION)
    days = int(round(gained))
    return days if days >= 1 else None


def learner_goal(db: Session, user: Any, *, now: datetime | None = None) -> tuple[str | None, int]:
    """``(goal_band, words_left)``: the learner's own goal and the words still
    missing to it. ``(None, 0)`` when no goal is set or it is already passed
    (``goal_gap`` would then aim at the next band, a goal the learner never set).
    """

    from app.services.daily_session import goal_gap
    from app.services.level_coverage import band_index

    raw = str(getattr(user, "cefr_target_level", None) or "").strip().upper()
    current = str(getattr(user, "cefr_estimate", None) or "A1.1")
    if not raw or band_index(raw) < band_index(current):
        return None, 0
    goal, words_left, _units_left = goal_gap(db, user, now=now)
    return goal, int(words_left)


def speedups(
    *, goal: str | None, words_left: int, base_per_day: int, options: tuple[int, ...] | list[int]
) -> list[dict[str, Any]]:
    """One ``{"words", "days_sooner"}`` per option, against ``base_per_day``."""

    return [
        {
            "words": int(words),
            "days_sooner": days_sooner(words_left=words_left, base_per_day=base_per_day, faster_per_day=int(words))
            if goal
            else None,
        }
        for words in options
    ]


def new_words_pace(db: Session, user: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """The learner's daily new words, today's extras, the «Noch 5» offer and the
    Réglages steps, each with how much sooner it covers the goal's words
    (``schemas.vocabulary.NewWordsPace``)."""

    from app.services.vocabulary_pace import (
        effective_new_word_cap,
        extra_new_words_today,
        next_extra_step,
        planned_new_words,
    )

    base = planned_new_words(user)
    extra = extra_new_words_today(db, user, now=now)
    # #563: one number for the next tap. The label, the grant and the goal line
    # all take it; the pool decides it, not the step's name.
    step = next_extra_step(db, user, now=now)
    goal, words_left = learner_goal(db, user, now=now)
    more_words = base + extra + step
    (more,) = speedups(goal=goal, words_left=words_left, base_per_day=base, options=[more_words])
    return {
        "words_per_day": base,
        "extra_today": extra,
        "cap_today": effective_new_word_cap(db, user, now=now),
        "step": step,
        "can_add_more": step > 0,
        "goal": goal,
        "words_left": words_left,
        "more": more,
        "steps": speedups(goal=goal, words_left=words_left, base_per_day=base, options=WORD_STEPS),
    }


__all__ = ["WORD_STEPS", "days_sooner", "learner_goal", "new_words_pace", "speedups"]
