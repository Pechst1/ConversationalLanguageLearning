"""WP-123b — the word drill's workload over a year, per level and learner quality.

The life walk plays 30 days; the drill's due pile is a long-horizon question. This
simulation runs **365 days** of one learner's vocabulary on the app's own rules:

* **the scheduler** — every card goes through ``VocabularyFSRS`` (FSRS-4.5, target
  retention ``settings.VOCAB_TARGET_RETENTION``), the scheduler ``/anki/review``
  uses: a new card is met as a self-rated flashcard («Good»), a review is typed
  (right → «Good», wrong → «Again», back the next day);
* **the drill** — as the walk drives ``pages/vocabulary/review.tsx``: one session a
  day (the struggling learner every other day) of at most :data:`DUE_PER_SESSION`
  due cards and :data:`NEW_PER_SESSION` new ones. Due cards beyond the session's
  cap wait for the next session — the *true* due count is everything due that
  morning, the cap only limits what one session shows;
* **intake** — new words a session × the app's own intake throttle
  (``intake_throttle.decide`` / ``intake_factor``: the backlog against one day of
  Régulier review capacity, and the graded 7-day accuracy);
* **the WP-127 credit** — a placed learner's top-down vocabulary check credits the
  passed sub-band (sampled + inferred) and every sub-band below it on day 1, with
  ``band_check.credit_schedule``: the light check falls 20–90 / 40–180 / 90–365
  days out by distance below the learner's band, the stability keeps the word
  known until then. Which sub-band each quality passes is what the 15-life walk
  measured (strong/average: one below; struggling: lower);
* **retention** — two assumptions, reported side by side:

  - ``walk`` (default): the life walk's answer accuracy, fixed per quality —
    drill 92 / 80 / 62 %, a credited word's light check 97 / 92 / 78 % (the
    walk's band-check accuracy);
  - ``fsrs``: the probability of recall is FSRS's own retrievability at the
    review, × 1.0 / 0.92 / 0.75 for strong / average / struggling.

**Not modelled** (each makes the real pile *smaller* than this one): words
reviewed inside the daily journey's practice items and La Forge; grammar units,
errata and conjugations (they live in the Rappel, not the drill).

Seconds per drill card are the walk's measured means (Wave 2, 15 lives): 8.6 s
strong, 9.8 s average, 12.5 s struggling.

Run from the repository root::

    python -m scripts.simulate_workload_365                 # Markdown tables
    python -m scripts.simulate_workload_365 --json out.json # every day, every life

Pure: no database, no model call.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("SECRET_KEY", "simulate-workload-365")

DAYS = 365
MONTH_DAYS = 30
LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1")
QUALITIES: tuple[str, ...] = ("strong", "average", "struggling")

#: The walk's drill request (``tests/experience_walk.drill``): ``due_limit`` and ``new_limit``.
DUE_PER_SESSION = 30
NEW_PER_SESSION = 8
#: The walk's typed-review accuracy, and its band-check accuracy for credited words.
DRILL_ACCURACY = {"strong": 0.92, "average": 0.80, "struggling": 0.62}
CHECK_ACCURACY = {"strong": 0.97, "average": 0.92, "struggling": 0.78}
#: ``fsrs`` retention: retrievability × this.
RECALL_FACTOR = {"strong": 1.0, "average": 0.92, "struggling": 0.75}
#: Seconds a drill card takes (the walk's measured mean per card).
SECONDS_PER_CARD = {"strong": 8.6, "average": 9.8, "struggling": 12.5}
#: The learner's own sub-band after placement (``band_check.SUB_BANDS`` index).
LEARNER_SUB_BAND = {"A1": 0, "A2": 2, "B1": 4, "B2": 6, "C1": 8}
#: The highest sub-band each quality passes in the walk's check (index), or None.
PASSED_SUB_BAND: dict[tuple[str, str], int | None] = {
    **{("A1", q): None for q in QUALITIES},
    ("A2", "strong"): 1, ("A2", "average"): 1, ("A2", "struggling"): 0,
    ("B1", "strong"): 3, ("B1", "average"): 3, ("B1", "struggling"): 2,
    ("B2", "strong"): 5, ("B2", "average"): 5, ("B2", "struggling"): 2,
    ("C1", "strong"): 7, ("C1", "average"): 7, ("C1", "struggling"): 4,
}
START = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.UTC)


@dataclass
class Card:
    credited: bool
    stability: float = 0.0
    difficulty: float = 5.0
    reps: int = 0
    lapses: int = 0
    state: str = "new"
    last: int | None = None
    due: int = 0


@dataclass
class Day:
    day: int
    due: int
    due_credited: int
    reviewed: int
    new: int
    right: int
    review_seconds: float
    drill_day: bool
    factor: float


@dataclass
class Life:
    level: str
    quality: str
    retention: str
    credit: bool
    cap: int | None
    credited_cards: int
    days: list[Day] = field(default_factory=list)


def credit_plan(level: str, quality: str) -> list[tuple[int, int]]:
    """``[(cards, distance), …]`` the day-1 check credits (empty below A2)."""

    from app.services import band_check

    passed = PASSED_SUB_BAND[(level, quality)]
    if passed is None:
        return []
    learner = LEARNER_SUB_BAND[level]
    return [
        (len(band_check._pool(band_check.SUB_BANDS[index])), learner - index)
        for index in range(passed, -1, -1)
    ]


def _recall(card: Card, day: int, *, quality: str, retention: str, rng: random.Random) -> bool:
    from app.services.vocab_fsrs import retrievability

    if retention == "fsrs":
        elapsed = float(day - (card.last if card.last is not None else day))
        chance = retrievability(card.stability, elapsed) * RECALL_FACTOR[quality]
    else:
        chance = (CHECK_ACCURACY if card.credited and card.lapses == 0 and card.reps <= 2 else DRILL_ACCURACY)[quality]
    return rng.random() < chance


def simulate_life(
    level: str,
    quality: str,
    *,
    retention: str = "walk",
    credit: bool = True,
    cap: int | None = DUE_PER_SESSION,
    days: int = DAYS,
    seed: int = 20261006,
) -> Life:
    """One learner's year. ``cap``: due cards one drill session takes (``None``: the
    learner clears the whole pile every drill day — the review time keeping up costs)."""
    from app.services.band_check import credit_schedule
    from app.services.intake_throttle import ThrottleSignals, decide, intake_factor
    from app.services.srs import SchedulerState
    from app.services.vocab_fsrs import VocabularyFSRS
    from app.services.vocabulary_pace import SECONDS_PER_REVIEW

    scheduler = VocabularyFSRS()
    rng = random.Random(f"workload:{seed}:{level}:{quality}:{retention}:{credit}")  # noqa: S311 - seeded
    cards: list[Card] = []
    if credit:
        for count, distance in credit_plan(level, quality):
            stability, window = credit_schedule(distance)
            for _ in range(count):
                cards.append(
                    Card(credited=True, stability=stability, difficulty=4.0, reps=2, state="review",
                         last=0, due=rng.randint(*window))
                )
    life = Life(level=level, quality=quality, retention=retention, credit=credit, cap=cap,
                credited_cards=len(cards))
    # One day of Régulier review capacity (intake_throttle.review_capacity_seconds).
    capacity = 0.35 * 600 + 10 * 10 * SECONDS_PER_REVIEW
    log: list[tuple[int, bool]] = []
    active, since, episode = False, None, ()
    new_credit = 0.0

    def schedule(card: Card, day: int, rating: int) -> None:
        now = START + dt.timedelta(days=day)
        outcome = scheduler.review(
            state=SchedulerState(stability=card.stability, difficulty=card.difficulty, reps=card.reps,
                                 lapses=card.lapses, scheduled_days=0, state=card.state),
            rating=rating,
            last_review_at=None if card.last is None else START + dt.timedelta(days=card.last),
            now=now,
        )
        card.stability, card.difficulty, card.state = outcome.stability, outcome.difficulty, outcome.state
        card.reps += 1
        if rating == 0:
            card.lapses += 1
        card.last = day
        card.due = day + max(1, outcome.scheduled_days)  # «Again» relearns: back the next session

    for day in range(days):
        now = START + dt.timedelta(days=day)
        due = sorted((c for c in cards if c.due <= day), key=lambda c: c.due)
        recent = [ok for (at, ok) in log if day - 7 < at <= day]
        accuracy = (sum(recent) / len(recent)) if len(recent) >= 20 else None
        signals = ThrottleSignals(
            backlog_seconds=int(len(due) * SECONDS_PER_REVIEW), capacity_seconds=int(capacity),
            backlog_days=len(due) * SECONDS_PER_REVIEW / capacity, due_counts={"vocab": len(due)},
            accuracy=accuracy, reviews=len(recent),
        )
        was = active
        active, reasons = decide(signals, was_active=was, since=since, now=now)
        episode = reasons if active and not was else (episode if was else ())
        factor = intake_factor(signals, active=active, backlog_episode="backlog" in (*episode, *reasons))
        if active != was:
            since = now if active else None
        drill_day = quality != "struggling" or day % 2 == 0
        reviewed = right = new = 0
        if drill_day:
            for card in due if cap is None else due[:cap]:
                ok = _recall(card, day, quality=quality, retention=retention, rng=rng)
                schedule(card, day, 2 if ok else 0)
                log.append((day, ok))
                reviewed += 1
                right += ok
            new_credit += NEW_PER_SESSION * factor
            while new_credit >= 1.0 - 1e-9:
                new_credit -= 1.0
                card = Card(credited=False)
                schedule(card, day, 2)  # met as a flashcard, turned, «Good»
                cards.append(card)
                new += 1
        life.days.append(
            Day(day=day + 1, due=len(due), due_credited=sum(1 for c in due if c.credited), reviewed=reviewed,
                new=new, right=right, review_seconds=reviewed * SECONDS_PER_CARD[quality],
                drill_day=drill_day, factor=factor)
        )
    return life


def _p(values: list[float], share: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, math.ceil(share * len(ordered)) - 1))]


def month_summary(life: Life) -> list[dict[str, Any]]:
    """Per 30-day month (month 12 is days 331–365): due median / p90 / max, review
    minutes median / p90 (drill days only), share of reviews right, new words."""

    out: list[dict[str, Any]] = []
    for month in range(12):
        lo = month * MONTH_DAYS
        hi = len(life.days) if month == 11 else (month + 1) * MONTH_DAYS
        window = life.days[lo:hi]
        if not window:
            break
        drills = [d for d in window if d.drill_day] or window
        reviews = sum(d.reviewed for d in window)
        out.append({
            "month": month + 1,
            "due_median": statistics.median(d.due for d in window),
            "due_p90": _p([d.due for d in window], 0.9),
            "due_max": max(d.due for d in window),
            "credited_due_median": statistics.median(d.due_credited for d in window),
            "minutes_median": round(statistics.median(d.review_seconds for d in drills) / 60, 1),
            "minutes_p90": round(_p([d.review_seconds for d in drills], 0.9) / 60, 1),
            "right": round(sum(d.right for d in window) / reviews, 2) if reviews else None,
            "new_words": sum(d.new for d in window),
            "over_cap_days": sum(1 for d in window if d.due > DUE_PER_SESSION),
        })
    return out


#: The reported scenarios: (retention, credit, cap).
SCENARIOS: tuple[tuple[str, bool, int | None], ...] = (
    ("walk", True, DUE_PER_SESSION),
    ("walk", True, None),
    ("walk", False, DUE_PER_SESSION),
    ("fsrs", True, DUE_PER_SESSION),
)


def run_all(
    *, retention: str = "walk", credit: bool = True, cap: int | None = DUE_PER_SESSION, days: int = DAYS
) -> list[Life]:
    return [simulate_life(level, quality, retention=retention, credit=credit, cap=cap, days=days)
            for level in LEVELS for quality in QUALITIES]


def render(lives: list[Life], *, title: str) -> str:
    lines = [f"### {title}", "", "True due words a day — median / p90 / max, by month:", ""]
    head = "| Life | credited | " + " | ".join(f"M{m}" for m in range(1, 13)) + " |"
    lines += [head, "|" + "---|" * 14]
    summaries = {(life.level, life.quality): month_summary(life) for life in lives}
    for life in lives:
        cells = [f"{m['due_median']:.0f} / {m['due_p90']:.0f} / {m['due_max']}" for m in summaries[(life.level, life.quality)]]
        lines.append(f"| {life.level} {life.quality} | {life.credited_cards} | " + " | ".join(cells) + " |")
    cap = lives[0].cap if lives else None
    session = f"one session of at most {cap} due" if cap else "the whole pile"
    lines += ["", f"Review minutes on a drill day ({session}) — median / p90, and share right:", ""]
    lines += ["| Life | " + " | ".join(f"M{m}" for m in range(1, 13)) + " | right (year) | new words (year) |",
              "|" + "---|" * 15]
    for life in lives:
        months = summaries[(life.level, life.quality)]
        reviews = sum(d.reviewed for d in life.days)
        right = sum(d.right for d in life.days) / reviews if reviews else 0.0
        cells = [f"{m['minutes_median']:.1f} / {m['minutes_p90']:.1f}" for m in months]
        lines.append(f"| {life.level} {life.quality} | " + " | ".join(cells)
                     + f" | {right:.0%} | {sum(d.new for d in life.days)} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--json", type=Path, default=None, help="write every day of every life here")
    args = parser.parse_args(argv)
    blocks: list[str] = []
    dump: dict[str, Any] = {}
    for retention, credit, cap in SCENARIOS:
        lives = run_all(retention=retention, credit=credit, cap=cap, days=args.days)
        title = (f"retention `{retention}`, " + ("with the WP-127 credit" if credit else "without the credit")
                 + (f", drill session of {cap} due" if cap else ", every due card reviewed"))
        blocks.append(render(lives, title=title))
        dump[f"{retention}:{'credit' if credit else 'no-credit'}:{cap or 'all'}"] = [
            {**{k: v for k, v in asdict(life).items() if k != "days"},
             "months": month_summary(life), "days": [asdict(d) for d in life.days]}
            for life in lives
        ]
    print("\n\n".join(blocks))
    if args.json:
        args.json.write_text(json.dumps(dump, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
