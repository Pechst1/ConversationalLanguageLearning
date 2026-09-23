"""WP-68 — La preuve: six packages, one life, a hundred and twenty-six days.

WP-62..67 landed on the same day in the same checkout, each with its own suite.
Nothing yet played them **together** over a horizon long enough for the seams to
show. This file is that run.

Two learners, 126 simulated days each, through the assembled system: the real
daily-journey router and state machine, the real planner and its day shapes, the
real living-story engine, and the real Courrier — scheduling, chains, soft
deadlines, ignored letters, and the writeback into tomorrow's scene. The only
stubbed things are

* the **model** (``living_story._client`` is a scripted fake, and
  ``missions._safe_llm`` returns ``None``, so the Courrier takes its own authored
  fallback path) — no credential is needed and no request leaves the process;
* the **clock** — ``daily_journey._utcnow`` and the two ``datetime`` names the
  Courrier reads are pointed at one controllable clock, so a simulated week is a
  week to every package at once.

One thing the clock cannot reach: ``real_world_missions.created_at`` is a SQL
``func.now()`` server default, so a letter is stamped with the wall clock while
its soft deadline is judged against the simulated one. In production those are
the same clock; here they are not, so :func:`_align_letter_to_the_clock`
restamps a freshly created letter. That is harness bookkeeping, not a change of
behaviour: ``expiry_for`` is seeded on the user and the mission, so the letter
gets exactly the deadline production would have given it.

Nothing here judges the quality of French. It judges that the record of two long
lives survives, stays bounded, diverges between learners, and that each package's
output is visible to the next one.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.api.v1.endpoints.daily_journey import get_journey_adapters
from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.mission import RealWorldMission
from app.main import create_app
from app.services import daily_journey as daily_journey_service
from app.services import error_memory as error_memory_module
from app.services import journey_errata as journey_errata_module
from app.services import journey_learning as journey_learning_module
from app.services import living_story as engine
from app.services import missions as missions_module
from app.services import progress as progress_module
from app.services import story_correspondence as courrier
from app.services import unified_srs as unified_srs_module
from app.services import vocabulary_credit as vocabulary_credit_module
from app.services.daily_journey_adapters import build_default_adapters
from app.services.journey_contracts import RECALL_FORMATS, DayShape
from app.services.journey_day_shapes import choose_day_shape
from tests import test_journey_end_to_end as support
from tests import test_living_story_longitudinal as story

#: Modules whose module-level ``datetime``/``date`` name is the wall clock the
#: harness has to move: when a letter expires, when an erratum is due again, when
#: a word comes back, which ISO week a letter belongs to.
_CLOCK_READERS = (
    missions_module,
    courrier,
    error_memory_module,
    journey_errata_module,
    journey_learning_module,
    unified_srs_module,
    # WP-78: the SRS that reschedules a practised word. Left on the wall clock,
    # every word the run practises is next due in the real month of the run
    # (months past the simulated one), so the queue drained on day two and the
    # remaining four months measured an empty queue rather than a learner's.
    progress_module,
    vocabulary_credit_module,
)

#: Long enough for a season to end and a second one to begin, and for a fact
#: from week one to be a hundred days old.
HORIZON_DAYS = 126

#: The one sentence this run follows from one end of a life to the other. It is
#: said inside the first five days and nowhere else.
FIRST_WEEK_FACT = "Vous avez vidé la cave inondée avec deux seaux."

#: A Monday, so the ISO weeks the Courrier keys its letters on line up with the
#: weeks the day-shape dice are dealt for.
START = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)

#: Vocabulary that can honestly be posed in more than one format: nouns stored
#: with their article (gender classify), phrases that unambiguously tutoient or
#: vouvoient (address classify and the directed rewrite), multi-word phrases
#: (word bank and tiles) and a bare word (choice and short answer).
HORIZON_WORDS: tuple[tuple[str, str], ...] = (
    ("un café", "a coffee"),
    ("la clé", "the key"),
    ("tu viens demain", "you are coming tomorrow"),
    ("vous partez déjà", "you are leaving already"),
    ("à tout à l'heure", "see you shortly"),
    ("on se voit bientôt", "we will see each other soon"),
    ("de rien merci", "you are welcome, thanks"),
    ("brouillard", "fog"),
    ("volet", "shutter"),
    ("escalier", "staircase"),
)


#: WP-86. What a compliant director teaches: one word out of each premise, and
#: three of the four words the fixture's panels always print. Glossed in the
#: harness learner's language (English); nouns carry their gender.
PREMISE_WORDS: dict[str, tuple[str, str, str, str | None]] = {
    "exposition": ("exposition", "exhibition", "noun", "f"),
    "four": ("four", "oven", "noun", "m"),
    "vélo": ("vélo", "bike", "noun", "m"),
    "colis": ("colis", "parcel", "noun", "m"),
    "affiche": ("affiche", "poster", "noun", "f"),
    "cave": ("cave", "cellar", "noun", "f"),
    "chat": ("chat", "cat", "noun", "m"),
    "poubelles": ("poubelle", "bin", "noun", "f"),
    "chien": ("chien", "dog", "noun", "m"),
}
PANEL_WORDS: tuple[dict[str, Any], ...] = (
    {"surface_fr": "pluie", "lemma": "pluie", "gloss_native": "rain", "part_of_speech": "noun", "gender": "f", "line_ref": "panel:0:narration"},
    {"surface_fr": "vitre", "lemma": "vitre", "gloss_native": "window pane", "part_of_speech": "noun", "gender": "f", "line_ref": "panel:0:narration"},
    {"surface_fr": "idée", "lemma": "idée", "gloss_native": "idea", "part_of_speech": "noun", "gender": "f", "line_ref": "panel:1:line:0"},
    {"surface_fr": "aider", "lemma": "aider", "gloss_native": "to help", "part_of_speech": "verb", "gender": None, "line_ref": "opening"},
)


def _with_lexicon(schema: str, value: dict[str, Any]) -> dict[str, Any]:
    """The fake director's draft, plus the lexicon a compliant one writes."""

    if schema != "SceneDraft":
        return value
    premise = str(value.get("premise_fr") or "")
    lexicon: list[dict[str, Any]] = [
        {"surface_fr": surface, "lemma": lemma, "gloss_native": gloss,
         "part_of_speech": pos, "gender": gender, "line_ref": "premise"}
        for surface, (lemma, gloss, pos, gender) in PREMISE_WORDS.items()
        if surface in premise.split() or surface + "." in premise.split()
    ][:1]
    turn = len(premise) % len(PANEL_WORDS)
    lexicon += [PANEL_WORDS[(turn + index) % len(PANEL_WORDS)] for index in range(3)]
    return {**value, "lexicon": lexicon}


# ---------------------------------------------------------------------------
# One clock for six packages
# ---------------------------------------------------------------------------


class _FrozenDateTime(datetime):
    """``datetime`` whose ``now()`` is the harness clock.

    The Courrier reads the wall clock in five places (the ISO week a letter
    belongs to, a chain step's queue time, a lapse, a completion, an event's
    timestamp). Pointing the name at the same clock the journey uses is what
    makes «this letter lapsed while the learner was away» a thing this run can
    actually produce.
    """

    clock: Any = None

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        moment = cls.clock.moment
        return moment if tz is not None else moment.replace(tzinfo=None)


class _FrozenDate(date):
    @classmethod
    def today(cls) -> date:  # type: ignore[override]
        return _FrozenDateTime.clock.moment.date()


def _align_letter_to_the_clock(db, *, user, mission: RealWorldMission, clock) -> None:
    """Restamp a freshly created letter onto the simulated clock. See the module
    docstring: ``created_at`` is a SQL server default the harness cannot reach."""

    mission.created_at = clock.moment
    if mission.chain_id and mission.cadence != "weekly":
        mission.expires_at = courrier.expiry_for(
            user=user,
            mission_id=mission.id,
            created_at=clock.moment,
            stakes_level=int(getattr(mission, "stakes_level", None) or 1),
        )
    db.add(mission)
    db.commit()


# ---------------------------------------------------------------------------
# What one day of one life left behind
# ---------------------------------------------------------------------------


@dataclass
class DayRecord:
    ordinal: int
    local_date: date
    played: bool
    #: The shape the learner's plan was actually built as, and why — read back
    #: off ``plan_selection``, which is what the client is served.
    day_shape: str = ""
    shape_reason: str = ""
    #: The shape the seeded dice *dealt*, before the planner had to build it. The
    #: two differ when a shape could not be filled (``shape_needs_a_recall_step``,
    #: ``letter_withdrawn``): the no-repeat rule is a promise of the dice, and
    #: this run is what shows how often the plan has to break it.
    dealt_shape: str = ""
    dealt_reason: str = ""
    eligible: tuple[str, ...] = ()
    recall_formats: list[str] = field(default_factory=list)
    recall_target_kinds: list[str] = field(default_factory=list)
    letter_mission_id: str | None = None
    #: The exact ``DayShapeInputs`` the planner rolled for this day (spied on the
    #: production call), so the deal can be replayed.
    dice_inputs: Any = None
    #: The director context this day was generated from (WP-62/63's projections).
    context: dict[str, Any] = field(default_factory=dict)
    #: What the Courrier did on this day, outside the journey.
    courrier: list[str] = field(default_factory=list)


@dataclass
class LifeRecord:
    label: str
    user_id: str
    thread_id: str
    days: list[DayRecord]
    contexts: list[dict[str, Any]]
    live: dict[str, Any]
    courrier_state: dict[str, Any]
    world_bible: dict[str, Any]
    chapters: list[dict[str, Any]]
    letters: list[dict[str, Any]]

    @property
    def played(self) -> list[DayRecord]:
        return [row for row in self.days if row.played]

    def shapes(self) -> list[str]:
        return [row.day_shape for row in self.played]

    def dealt(self) -> list[str]:
        return [row.dealt_shape for row in self.played if row.dealt_shape]

    def formats(self) -> list[str]:
        return [item for row in self.played for item in row.recall_formats]

    def context_on(self, ordinal: int) -> dict[str, Any]:
        return next(row.context for row in self.played if row.ordinal == ordinal)


@dataclass
class Horizon:
    lives: list[LifeRecord]
    dice: list[tuple[Any, Any]]

    @property
    def first(self) -> LifeRecord:
        return self.lives[0]

    @property
    def second(self) -> LifeRecord:
        return self.lives[1]


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _turn_for(day: int) -> story.TurnScript:
    """What the fake actor returns on this day.

    The rhythm is the same for both learners on purpose: everything that differs
    between the two lives has to come from their seeded dice, not from a script
    that treated them differently.
    """

    return story.TurnScript(
        callback_fr=(
            FIRST_WEEK_FACT if day <= 5 else f"Vous avez répondu le jour {day}."
        ),
        summary_native=f"You answered on day {day}.",
        commitment_text=f"Passer voir le voisin, jour {day}." if day % 9 == 1 else None,
        resolve_open_commitments=day % 9 == 3,
        extra={
            "development_index": 1 + day % 2,
            "feeling_shift": "colder" if day % 6 == 0 else "warmer",
        },
    )


def _recall_formats_of(journey: dict[str, Any]) -> list[str]:
    return [
        str((step.get("prompt") or {}).get("task_type") or "")
        for step in journey.get("steps") or []
        if step.get("kind") == "recall"
    ]


def _recall_targets_of(journey: dict[str, Any]) -> list[str]:
    return [
        str(((step.get("prompt") or {}).get("target") or {}).get("kind") or "")
        for step in journey.get("steps") or []
        if step.get("kind") == "recall"
    ]


#: A learner who is mostly right and sometimes not. The second reply is wrong on
#: purpose: the errata queue is what makes «jour de reprise» eligible, and an
#: errata queue nobody earned would be a fixture rather than a run.
_REPLIES = (
    "Bonjour, merci de votre message. Je passerai demain matin et je vous "
    "apporte les affiches. Vous pouvez compter sur moi.",
    "Bonjour, je vais venir demain matin. Je vous apporte les affiche et je "
    "suis très content. Je vous voudrais aider avec le marché samedi.",
    "Bonjour, d'accord pour samedi. Je vous réponds vite et je vous dis tout "
    "ce que je sais. À très bientôt.",
)


def _reply_text(day: int) -> str:
    """Mostly the clean reply; every fourth letter is the flawed one."""

    return _REPLIES[1] if day % 9 == 0 else _REPLIES[0 if day % 2 else 2]


def _answer_letter(db, client, headers, *, mission_id: str, text: str) -> None:
    """Answer a Courrier letter the way the Courrier page does: submit, complete."""

    client.post(
        f"/api/v1/missions/{mission_id}/submit",
        headers=headers,
        json={"text": text, "mode": "writing"},
    )
    client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)


def _play_life(
    *,
    label: str,
    client: TestClient,
    db,
    clock,
    provider: story.ScriptedProvider,
    days: int,
) -> LifeRecord:
    start_context = len(provider.director_contexts())
    d = story.driver(client, db, cefr="A2.2")
    # Due on the *simulated* clock. Seeded against the wall clock (September)
    # while the run lives in January–May, these words were never due at all,
    # and the recall variety this file asserts came only from the learner's own
    # uncorrected mission replies that the pre-WP-74 phrase bank queued as
    # vocabulary. The words below are what a real learner's queue holds.
    support.seed_due_vocabulary(db, d.user_id, HORIZON_WORDS, overdue_days=4, now=clock.moment)
    speakers = [story.CAST["romy"], story.CAST["margaux"], story.CAST["lila"]]
    records: list[DayRecord] = []
    courrier_log: list[dict[str, Any]] = []
    #: Letters this life deliberately walks away from, so the Courrier can
    #: produce a lapse — and the ones that actually went cold. A letter left on
    #: the table can still be picked up by a «jour de lettre» the next morning,
    #: so the run keeps walking away from letters until one of them lapses.
    cold: dict[str, set[str]] = {"ignored": set(), "lapsed": set()}

    for day in range(1, days + 1):
        local = clock.moment.date()
        # A missed day, four times over the horizon: «jour court» is offered to
        # somebody coming back, and a lapsed letter needs a gap to lapse in.
        if day % 31 == 0:
            records.append(DayRecord(ordinal=day, local_date=local, played=False))
            clock.advance(days=1)
            continue

        provider.scene = story.SceneScript(character_id=speakers[(day // 2) % len(speakers)])
        provider.turn = _turn_for(day)
        d.create()
        assert d.journey["status"] == "active", d.journey
        record = DayRecord(
            ordinal=day,
            local_date=local,
            played=True,
            day_shape=str(d.journey.get("day_shape") or ""),
            recall_formats=_recall_formats_of(d.journey),
            recall_target_kinds=_recall_targets_of(d.journey),
            context=provider.director_contexts()[-1],
        )
        row = db.get(DailyJourney, uuid.UUID(d.journey["id"]))
        record.shape_reason = str((row.plan_selection or {}).get("shape_reason") or "")
        respond = support.step_of(d.journey, "respond")
        letter = (respond or {}).get("prompt", {}).get("letter")
        if letter:
            record.letter_mission_id = str(letter.get("mission_id"))
        # Every fifth day the learner gets a recall wrong: the errata queue is
        # what makes «jour de reprise» eligible, and it has to be earned.
        d.play(
            answer=f"Je m'en occupe, jour {day}.",
            recall="wrong" if day % 11 == 0 else "correct",
        )
        response = d.finish("complete")
        assert response.status_code == 200, response.text
        records.append(record)

        record.courrier.extend(
            _run_courrier_day(
                client=client,
                db=db,
                clock=clock,
                headers=d.headers,
                user_id=d.user_id,
                day=day,
                log=courrier_log,
                cold=cold,
            )
        )
        clock.advance(days=1)

    live = story.live_state(db, d)
    thread = story.thread_of(db, d)
    letters = [
        {
            "id": str(row.id),
            "cadence": row.cadence,
            "status": row.status,
            "outcome": row.outcome,
            "correspondent_id": row.correspondent_id,
            "chain_id": row.chain_id,
            "chain_index": row.chain_index,
            "chain_total": row.chain_total,
            "title": row.title,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "stakes_level": int(getattr(row, "stakes_level", None) or 1),
            "attempts": len(list(row.attempts or [])),
            "journey_attempts": sum(
                1
                for attempt in (row.attempts or [])
                if attempt.mode == courrier.JOURNEY_ANSWER_MODE
            ),
            "answered_in_journey": any(
                attempt.mode == courrier.JOURNEY_ANSWER_MODE for attempt in (row.attempts or [])
            ),
            "story_event": (row.recap_payload or {}).get("story_event"),
            "measured": (row.recap_payload or {}).get("measured"),
        }
        for row in db.query(RealWorldMission)
        .filter(RealWorldMission.user_id == d.user_id)
        .order_by(RealWorldMission.created_at)
        .all()
    ]
    for entry in courrier_log:
        for row in letters:
            if row["id"] == entry["mission_id"]:
                row.setdefault("events", []).append(entry)
    return LifeRecord(
        label=label,
        user_id=str(d.user_id),
        thread_id=str(thread.id),
        days=records,
        contexts=provider.director_contexts()[start_context:],
        live=live,
        courrier_state=courrier.correspondence_state(thread),
        world_bible=dict(thread.world_bible or {}),
        chapters=story._chapter_rows(db, d),
        letters=letters,
    )


def _run_courrier_day(
    *,
    client,
    db,
    clock,
    headers,
    user_id,
    day: int,
    log: list[dict[str, Any]],
    cold: dict[str, set[str]],
) -> list[str]:
    """Open the Courrier, then answer or ignore what is waiting.

    ``GET /missions/today`` is the same call Home and the Courrier page make, and
    it is where WP-64 materialises the day's second letter — so a run that never
    made it would never see a chain instalment or a story-born letter at all.
    """

    notes: list[str] = []
    from app.db.models.user import User

    user = db.get(User, user_id)
    response = client.get("/api/v1/missions/today", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    for row in db.query(RealWorldMission).filter(
        RealWorldMission.user_id == user_id,
        RealWorldMission.status.in_(["available", "in_progress"]),
    ):
        if row.created_at is None or row.created_at.replace(tzinfo=UTC) <= clock.moment:
            continue
        _align_letter_to_the_clock(db, user=user, mission=row, clock=clock)
        notes.append(f"opened:{row.cadence}:{row.id}")
        log.append({"mission_id": str(row.id), "day": day, "event": "opened"})

    active = payload.get("active_mission")
    if active and active.get("status") in {"available", "in_progress"}:
        chain = (active.get("courrier") or {}).get("chain") or active.get("chain")
        # One letter in an affair is deliberately left to go cold: an ignored
        # letter is a consequence WP-64 has to be able to produce, and the only
        # honest way to produce one is to not answer it — today and every day
        # after, until the correspondent stops waiting.
        if chain and (
            active["id"] in cold["ignored"] or (day >= 12 and not cold["lapsed"])
        ):
            cold["ignored"].add(active["id"])
            notes.append(f"ignored:{active['id']}")
            log.append({"mission_id": active["id"], "day": day, "event": "ignored"})
        elif day % 3 == 1:
            # Left on the table overnight — which is how «jour de lettre» ever
            # becomes eligible: the journey is planned before the Courrier is
            # opened, so only a letter that survived yesterday is waiting.
            notes.append(f"left:{active['id']}")
        else:
            _answer_letter(
                db, client, headers, mission_id=active["id"], text=_reply_text(day)
            )
            notes.append(f"answered:{active['id']}")
            log.append({"mission_id": active["id"], "day": day, "event": "answered"})

    weekly = payload.get("weekly_mission")
    if weekly and weekly.get("status") in {"available", "in_progress"} and day % 7 == 2:
        _answer_letter(
            db,
            client,
            headers,
            mission_id=weekly["id"],
            text=_reply_text(day + 1),
        )
        notes.append(f"answered-weekly:{weekly['id']}")
        log.append({"mission_id": weekly["id"], "day": day, "event": "answered"})

    for row in db.query(RealWorldMission).filter(
        RealWorldMission.user_id == user_id, RealWorldMission.status == "lapsed"
    ):
        if str(row.id) in cold["lapsed"]:
            continue
        cold["lapsed"].add(str(row.id))
        log.append({"mission_id": str(row.id), "day": day, "event": "lapsed"})
        notes.append(f"lapsed:{row.id}")
    return notes


@contextmanager
def horizon_run(
    db_engine, *, days: int = HORIZON_DAYS, labels: Sequence[str] = ("A", "B")
) -> Iterator[Horizon]:
    """Play ``labels`` lives of ``days`` days each and hand back the record.

    A context manager rather than a fixture so that ``scripts/long_horizon_report.py``
    runs **this** harness rather than a second implementation of it — the rule
    ``scripts/review_living_story.py`` already follows for the story engine.
    """

    monkeypatch = pytest.MonkeyPatch()
    session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)()
    clock = support.Clock(START)
    _FrozenDateTime.clock = clock
    provider = story.ScriptedProvider()
    provider.long_memory = True
    provider.season_engine = True
    # WP-86: the fake director also teaches words, as the DIRECTOR prompt asks.
    provider.transform = _with_lexicon

    dice: list[tuple[Any, Any]] = []
    real_choice = daily_journey_service.choose_day_shape

    def spy(inputs):
        decision = real_choice(inputs)
        dice.append((inputs, decision))
        return decision

    try:
        monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
        monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
        monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")
        monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)
        monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
        monkeypatch.setattr(engine, "_client", lambda: provider)
        monkeypatch.setattr(daily_journey_service, "_utcnow", clock)
        monkeypatch.setattr(daily_journey_service, "choose_day_shape", spy)
        monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
        # One clock for every package that schedules something. In production
        # these are all the same wall clock; a run that advances one of them and
        # not the others would produce an errata queue that is never due and a
        # letter that never comes to term, which is a property of the harness and
        # not of the code under test.
        for module in _CLOCK_READERS:
            monkeypatch.setattr(module, "datetime", _FrozenDateTime)
            if hasattr(module, "date"):
                monkeypatch.setattr(module, "date", _FrozenDate)

        app = create_app()

        def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_journey_adapters] = build_default_adapters
        with TestClient(app) as client:
            lives = []
            for label in labels:
                clock.moment = START
                lives.append(
                    _play_life(
                        label=label,
                        client=client,
                        db=session,
                        clock=clock,
                        provider=provider,
                        days=days,
                    )
                )
        # The dice the planner actually rolled, joined back onto the day they
        # decided. Recorded through a spy on the production call rather than
        # re-derived here, so «reproducible» can be tested by replaying the very
        # inputs the learner's day was dealt from.
        rolled = {(str(inputs.user_id), inputs.local_date): (inputs, decision) for inputs, decision in dice}
        for life in lives:
            for row in life.played:
                found = rolled.get((life.user_id, row.local_date))
                if found is None:
                    continue
                row.dice_inputs, decision = found
                row.dealt_shape = str(decision.shape)
                row.dealt_reason = decision.reason
                row.eligible = tuple(str(shape) for shape in decision.eligible)
        yield Horizon(lives=lives, dice=dice)
    finally:
        monkeypatch.undo()
        session.close()


@pytest.fixture(scope="module")
def horizon(db_engine) -> Horizon:
    """Two lives, played once, read by every test in this file."""

    with horizon_run(db_engine) as record:
        yield record


# ---------------------------------------------------------------------------
# 1. WP-62 — the long memory, a hundred days later
# ---------------------------------------------------------------------------


def test_day_one_hundred_still_answers_for_the_first_week(horizon: Horizon) -> None:
    """Both lives, both still carrying a sentence said in week one."""

    for life in horizon.lives:
        seasons = [row for row in life.live["chronicle"] if row.get("kind") == "season"]
        assert seasons, f"life {life.label} folded no season digest"
        assert min(int(row["from_day"]) for row in seasons) <= 5, (
            "the first chapter of this life closed inside week one"
        )
        for ordinal in (100, life.played[-1].ordinal):
            context = life.context_on(ordinal)
            assert FIRST_WEEK_FACT in " ".join(context["chronicle"]), (
                f"life {life.label} lost the first week by day {ordinal}"
            )
            assert (
                sum(len(line) + 1 for line in context["chronicle"])
                <= engine.CHRONICLE_PROMPT_CHARS
            )
            assert len(context["consequences"]) <= engine.CONSEQUENCE_PROMPT_LIMIT
            assert len(context["plants_due"]) <= engine.PLANT_PROMPT_LIMIT


def test_an_early_consequence_is_still_offered_back_after_a_hundred_days(
    horizon: Horizon,
) -> None:
    """WP-62's callback loop, measured at the far end of the horizon.

    The claim is not «a callback happened» but «the past that was offered back on
    a late day is an *early* past» — the thing a flat ``events[-40]`` tail could
    never do.
    """

    for life in horizon.lives:
        late = [
            row.context.get("callback")
            for row in life.played
            if row.ordinal >= 40 and row.context.get("callback")
        ]
        assert late, f"life {life.label} was offered no callback in its second month"
        reach = max(
            row.ordinal - int(row.context["callback"]["day"])
            for row in life.played
            if row.ordinal >= 40 and row.context.get("callback")
        )
        assert reach >= 30, (
            f"life {life.label} was never offered anything older than {reach} days"
        )
        kinds = {str(row.get("kind")) for row in late}
        assert kinds & {"branch", "mood_break", "commitment_kept", "commitment_broken"}, (
            "what the learner made true is among the things offered back"
        )
        # And the branch the learner made true in week one is still on the ledger
        # at the end of the horizon — a consequence that outlived its chapter by
        # four months, which is the whole of WP-62's claim.
        assert any(
            row["kind"] == "branch" and int(row["day"]) <= 20
            for row in life.live["consequences"]
        ), sorted({(row["kind"], int(row["day"])) for row in life.live["consequences"]})
        # And the ledgers the callbacks are drawn from are all in use.
        assert {row["kind"] for row in life.live["consequences"]} >= {
            "branch",
            "mood_break",
        }
        assert any(plant["status"] == "paid" for plant in life.live["planted"])
        assert set(life.live["secrets"].values()) <= set(engine.SECRET_STATES)


# ---------------------------------------------------------------------------
# 2. WP-63 — the season has a horizon
# ---------------------------------------------------------------------------


def test_the_cast_has_a_life_between_the_chapters_and_only_witnesses_hear_it(
    horizon: Horizon,
) -> None:
    for life in horizon.lives:
        offscreen = story.meanwhile(life.live["events"])
        assert offscreen, f"life {life.label} never ticked an agenda"
        for row in offscreen:
            witnesses = row.get("witnesses") or []
            assert witnesses, row
            # `meanwhile:<character>:<step>` — the person whose week it was is
            # never their own witness, so the learner can only hear it from
            # somebody else.
            character = str(row["id"]).split(":")[1]
            assert character not in witnesses, row
        assert any(int(entry.get("step") or 0) > 0 for entry in life.live["agendas"].values())


def test_the_seasons_long_questions_move_through_their_states(horizon: Horizon) -> None:
    for life in horizon.lives:
        states = {row["state"] for row in life.live["threads"].values()}
        assert states, f"life {life.label} moved no season thread"
        assert states <= set(engine.THREAD_STATES)
        assert "developing" in states or "closed" in states
        archive = life.live["threads_archive"]
        assert archive, "season one's questions are kept with their state"
        assert all(row["state"] == "closed" for row in archive), (
            "the finale settles what the season left open"
        )


def test_the_season_ends_then_begins_again_with_the_memory_intact(
    horizon: Horizon,
) -> None:
    for life in horizon.lives:
        phases = [row.context["season"]["phase"] for row in life.played]
        assert set(phases) <= {"running", "finale", "interlude"}
        assert "finale" in phases and "interlude" in phases, phases[-20:]
        assert phases.index("finale") < phases.index("interlude")
        # The brief's rule, over every single day of both lives: the director is
        # never left with no arc and no ending either.
        for row in life.played:
            context = row.context
            assert context["world"]["suggested_arc"] or context["season"]["phase"] != "running", (
                f"life {life.label} day {row.ordinal} had no arc and no ending"
            )
        assert int(life.live["season_index"]) >= 2
        assert int(life.world_bible["season_number"]) >= 2
        # What the learner lived came with them.
        assert 1 in {row["season"] for row in life.live["chronicle"] if row.get("kind") == "season"}
        assert life.live["consequences"] and life.live["secrets"] and life.live["world_flags"]
        # The arcs were gated rather than rubber-stamped: at some point the
        # director was told an arc could not move yet and why.
        assert any(
            arc.get("blocked_by")
            for row in life.played
            for arc in row.context["world"]["arcs"]
        ), "no arc was ever gated over the whole horizon"


def test_chapter_shapes_vary_and_never_twice_in_a_row(horizon: Horizon) -> None:
    for life in horizon.lives:
        shapes = [row.get("shape") for row in life.chapters]
        assert len(set(shapes)) >= 4, shapes
        for previous, current in zip(life.chapters, life.chapters[1:], strict=False):
            if current.get("finale") or current.get("interlude"):
                # Forced shapes: a finale is always an ensemble, an interlude
                # always the quiet standard chapter.
                continue
            assert previous["shape"] != current["shape"], (previous["shape"], current["shape"])


# ---------------------------------------------------------------------------
# 3. WP-64/65 — the Courrier lives in the story
# ---------------------------------------------------------------------------


def _answered_on(life: LifeRecord) -> list[tuple[int, dict[str, Any]]]:
    """Every letter this life finished, with the day it was finished on."""

    pairs: list[tuple[int, dict[str, Any]]] = []
    for row in life.letters:
        finished = [
            entry["day"]
            for entry in row.get("events") or []
            if entry["event"] == "answered"
        ]
        if finished and row["status"] == "completed":
            pairs.append((max(finished), row))
    return pairs


def test_a_finished_letter_is_a_fact_in_the_next_days_scene(horizon: Horizon) -> None:
    """The finding WP-64 exists for: a letter changed nothing about tomorrow."""

    for life in horizon.lives:
        by_ordinal = {row.ordinal: row for row in life.played}
        proven = 0
        for day, letter in _answered_on(life):
            tomorrow = by_ordinal.get(day + 1)
            if tomorrow is None:
                continue
            events = tomorrow.context["events"]
            found = next(
                (
                    item
                    for item in events
                    if item.get("source") == courrier.EVENT_SOURCE
                    and str(item.get("mission_id")) == letter["id"]
                ),
                None,
            )
            if found is None:
                continue
            assert found["witnesses"] == [letter["correspondent_id"]], found
            assert found["summary_fr"], found
            # …and the mood step the same letter wrote is in the same context.
            assert letter["correspondent_id"] in tomorrow.context["moods"], (
                "the letter moved the person who wrote it"
            )
            proven += 1
        assert proven >= 5, (
            f"life {life.label} proved the writeback on only {proven} of its letters"
        )


def test_a_lapsed_letter_cools_the_correspondent_once(horizon: Horizon) -> None:
    for life in horizon.lives:
        lapsed = [row for row in life.letters if row["status"] == "lapsed"]
        assert lapsed, f"life {life.label} never let a letter go cold"
        for row in lapsed:
            assert row["outcome"] == "ignored"
            assert row["attempts"] == 0, "nobody answered it; that is what lapsed means"
        ignored_events = [
            item
            for item in life.live["events"]
            if item.get("source") == courrier.EVENT_SOURCE and item.get("outcome") == "ignored"
        ]
        # One event per lapse and never two for the same letter: the sweep runs
        # on every `/missions/today`, which is every day of the run.
        missions = [str(item.get("mission_id")) for item in ignored_events]
        assert len(missions) == len(set(missions)), missions


def test_a_chain_of_three_letters_progresses(horizon: Horizon) -> None:
    for life in horizon.lives:
        chains: dict[str, list[dict[str, Any]]] = {}
        for row in life.letters:
            if row["chain_id"]:
                chains.setdefault(row["chain_id"], []).append(row)
        long_chains = [
            sorted(rows, key=lambda row: int(row["chain_index"] or 1))
            for rows in chains.values()
            if len(rows) >= 3
        ]
        assert long_chains, f"life {life.label} never ran an affair past two letters"
        for rows in long_chains:
            assert [row["chain_index"] for row in rows] == list(range(1, len(rows) + 1))
            assert len({row["correspondent_id"] for row in rows}) == 1, (
                "an affair is with one person"
            )
            stakes = [row["stakes_level"] for row in rows]
            assert stakes == sorted(stakes) and stakes[-1] > stakes[0], stakes
            # Only the instalments carry a deadline; letter 1 may be the weekly.
            assert all(row["expires_at"] for row in rows[1:])


def test_a_letter_day_finishes_its_letter_exactly_once(horizon: Horizon) -> None:
    answered_in_journey = 0
    for life in horizon.lives:
        letter_days = [row for row in life.played if row.day_shape == str(DayShape.LETTER)]
        assert letter_days, f"life {life.label} was never dealt «jour de lettre»"
        for row in letter_days:
            assert row.letter_mission_id, (
                "a letter day whose respond step carries no letter is the phantom "
                "loop WP-66 refused to ship"
            )
        by_id = {row["id"]: row for row in life.letters}
        for row in letter_days:
            letter = by_id.get(row.letter_mission_id)
            assert letter is not None
            if letter["journey_attempts"]:
                answered_in_journey += 1
                assert letter["journey_attempts"] == 1, letter
                assert letter["status"] == "completed", letter
                assert letter["outcome"] in {"kept", "partial", "missed"}, letter
                assert letter["measured"] is not None, (
                    "a finished letter carries the measured debrief, never a score"
                )
    assert answered_in_journey >= 4, answered_in_journey


# ---------------------------------------------------------------------------
# 4. WP-66 — days that do not resemble each other
# ---------------------------------------------------------------------------


def test_a_horizon_of_days_does_not_repeat_itself(horizon: Horizon) -> None:
    """Four months of days, and the deal behind them.

    The distribution is asserted on the day the learner was **served**; the
    no-repeat rule is asserted on the shape the dice **dealt**, because that is
    whose promise it is. The planner may still have to build a standard day from
    a shape it could not fill, and when it does it says so
    (``shape_needs_a_recall_step``) — the count is printed by
    ``test_the_run_is_written_down`` and discussed in `WP-68-EVIDENCE.md`.
    """

    for life in horizon.lives:
        counted = Counter(life.shapes())
        dealt = Counter(life.dealt())
        assert len(counted) >= 4, counted
        assert len(dealt) >= 4, dealt
        for shape, count in dealt.items():
            assert count / sum(dealt.values()) <= 0.5, (shape, count, dealt)
        for previous, current in zip(life.played, life.played[1:], strict=False):
            if current.local_date - previous.local_date != timedelta(days=1):
                # A day the learner missed: «jour court» is dealt against a gap,
                # not against yesterday.
                continue
            if current.dealt_reason == "seeded_dice_no_alternative":
                # WP-66 §6.5: with one eligible shape the honest answer is a
                # second standard day, and the decision records that it is.
                continue
            if previous.dealt_shape != previous.day_shape:
                # WP-68 finding. Yesterday's shape could not be built and became
                # a standard day, so today's dice exclude *standard* and may deal
                # the shape that already failed yesterday. The no-repeat rule is
                # enforced against the day the learner was served, which is the
                # honest reading — but it means the deal itself can repeat.
                continue
            assert previous.dealt_shape != current.dealt_shape, (
                previous.ordinal,
                previous.dealt_shape,
                current.dealt_reason,
            )
        # Every day the learner was served differently from the deal has a
        # recorded reason for it; no shape is ever silently swapped.
        downgraded = 0
        for row in life.played:
            if row.dealt_shape != row.day_shape:
                downgraded += 1
                assert row.day_shape == str(DayShape.STANDARD), row
                assert row.shape_reason in {
                    "shape_needs_a_recall_step",
                    "letter_withdrawn",
                }, (row.ordinal, row.dealt_shape, row.day_shape, row.shape_reason)
        # The served month differs from the dealt one by exactly the downgrades,
        # and the whole of that difference lands on the standard day — which is
        # why the *served* distribution can pass 50 % where the deal does not.
        assert counted[str(DayShape.STANDARD)] - dealt[str(DayShape.STANDARD)] == downgraded
        for shape, count in counted.items():
            if shape == str(DayShape.STANDARD):
                continue
            assert count / sum(counted.values()) <= 0.5, (shape, count, counted)
        # And a repeated *served* shape is never a silent one: it only ever
        # follows a day whose shape the planner could not build.
        for previous, current in zip(life.played, life.played[1:], strict=False):
            if current.local_date - previous.local_date != timedelta(days=1):
                continue
            if previous.day_shape != current.day_shape:
                continue
            assert previous.dealt_shape != previous.day_shape or (
                current.dealt_shape != current.day_shape
            ), (previous.ordinal, previous.day_shape, current.shape_reason)


def test_every_recall_format_posed_is_one_the_contract_knows(horizon: Horizon) -> None:
    """What the six formats actually come to over a long run.

    This is the assertion WP-68 had to weaken, and the reason is recorded in
    `WP-68-EVIDENCE.md`: under the living-story engine the planner has **no
    affordances** (``scenario_target_affordances`` is keyed on authored scenario
    families and a generated situation matches none), so ``choice`` — which needs
    distractors — and ``word_bank`` — which needs a chip that is not part of the
    answer — cannot be posed honestly at all. Four of the six remain reachable,
    and the three WP-66 added are among them.
    """

    posed = [item for life in horizon.lives for item in life.formats()]
    assert posed
    assert set(posed) <= set(RECALL_FORMATS)
    assert len(set(posed)) >= 3, Counter(posed)
    # The two formats WP-66 added that do not need a scene affordance are really
    # posed to a real learner through the real API, which is the claim that had
    # never been made end to end.
    assert {"classify", "transform"} <= set(posed), Counter(posed)
    for life in horizon.lives:
        assert set(life.formats()) & {"classify", "transform"}


def test_the_listening_day_never_poses_a_format_that_cannot_be_heard(
    horizon: Horizon,
) -> None:
    from app.services.journey_contracts import DICTATION_RECALL_FORMATS

    for life in horizon.lives:
        for row in life.played:
            if row.day_shape != str(DayShape.LISTENING):
                continue
            assert row.recall_formats, "a «jour d'écoute» poses at least one recall"
            for task_type in row.recall_formats:
                assert task_type in DICTATION_RECALL_FORMATS, (row.ordinal, task_type)


# ---------------------------------------------------------------------------
# 5. Two lives, two hands of dice — and each one replayable
# ---------------------------------------------------------------------------


def test_two_lives_diverge(horizon: Horizon) -> None:
    first, second = horizon.first, horizon.second
    assert first.user_id != second.user_id and first.thread_id != second.thread_id
    assert [arc["id"] for arc in first.contexts[0]["world"]["arcs"]] != [
        arc["id"] for arc in second.contexts[0]["world"]["arcs"]
    ], "two lives, two orders of the season's arcs"
    assert first.shapes() != second.shapes(), "two lives, two months"
    assert [row.get("shape") for row in first.chapters] != [
        row.get("shape") for row in second.chapters
    ], "two lives, two hands of chapters"
    assert {row.get("last_day") for row in first.live["agendas"].values()} != {
        row.get("last_day") for row in second.live["agendas"].values()
    }, "the cast's weeks move at different moments"
    assert [row["correspondent_id"] for row in first.letters[:6]] != [
        row["correspondent_id"] for row in second.letters[:6]
    ], "two lives, two first weeks of post"


def test_each_deal_is_reproducible(horizon: Horizon) -> None:
    """Non-deterministic, not random (principle 1).

    The day shapes are replayed through the *production* function with the very
    inputs the planner was called with — recorded by a spy on the real call — and
    the callback dice are re-rolled off the stored ledger.
    """

    for life in horizon.lives:
        replayed = 0
        for row in life.played:
            if row.dice_inputs is None:
                continue
            again = choose_day_shape(row.dice_inputs)
            assert str(again.shape) == row.dealt_shape, (row.ordinal, again, row.dealt_shape)
            assert again.reason == row.dealt_reason
            replayed += 1
        assert replayed >= HORIZON_DAYS - 10, replayed

        drawn = [
            (
                engine.callback_candidate(
                    {**life.live, "resolved_chapter_questions": ["q"] * n},
                    seed=life.thread_id,
                )
                or {}
            ).get("id")
            for n in range(8)
        ]
        assert drawn == [
            (
                engine.callback_candidate(
                    {**life.live, "resolved_chapter_questions": ["q"] * n},
                    seed=life.thread_id,
                )
                or {}
            ).get("id")
            for n in range(8)
        ], "the same life is dealt the same memories"

    assert [
        (
            engine.callback_candidate(
                {**horizon.first.live, "resolved_chapter_questions": ["q"] * n},
                seed=horizon.first.thread_id,
            )
            or {}
        ).get("id")
        for n in range(8)
    ] != [
        (
            engine.callback_candidate(
                {**horizon.second.live, "resolved_chapter_questions": ["q"] * n},
                seed=horizon.second.thread_id,
            )
            or {}
        ).get("id")
        for n in range(8)
    ], "two threads, two sets of dice"


# ---------------------------------------------------------------------------
# 6. The budget the whole thing has to live inside
# ---------------------------------------------------------------------------


def test_the_prompt_does_not_grow_with_the_horizon(horizon: Horizon) -> None:
    """A hundred days of memory must not be a hundred days of prompt."""

    def size(life: LifeRecord, ordinal: int) -> int:
        return len(json.dumps(life.context_on(ordinal), ensure_ascii=False))

    for life in horizon.lives:
        early = size(life, 20)
        for ordinal in (100, life.played[-1].ordinal):
            assert size(life, ordinal) <= early * 1.6, (
                life.label,
                ordinal,
                size(life, ordinal),
                early,
            )
        assert len(life.live["events"]) <= engine.MAX_HISTORY
        assert len(life.live["consequences"]) <= engine.CONSEQUENCE_LEDGER_LIMIT
        assert (
            len([row for row in life.live["planted"] if row["status"] != "paid"])
            <= engine.PLANT_LEDGER_LIMIT
        )


def test_the_median_day_holds_six_graded_interactions(horizon: Horizon) -> None:
    """WP-86: the scene teaches words and the floor builds from its lines, so a
    median day is six things answered (five quick items and the reply) — every
    one of them inside the stated minutes, which the practice day's own
    `PlannedJourney.validate()` refuses to break."""

    for life in horizon.lives:
        graded = sorted(len(row.recall_formats) + 1 for row in life.played)
        assert graded[len(graded) // 2] >= 6, (life.label, Counter(graded))
        # The scene-derived floor is actually dealt, not merely possible.
        assert "who_said" in life.formats(), life.label


def test_the_run_is_written_down(horizon: Horizon, capsys) -> None:
    """The numbers this run actually produced, printed for the evidence note."""

    with capsys.disabled():
        for life in horizon.lives:
            print(f"\n=== life {life.label} ({HORIZON_DAYS} days) ===")
            print("  day shapes      :", dict(Counter(life.shapes())))
            print("  shape reasons   :", dict(Counter(row.shape_reason for row in life.played)))
            print("  recall formats  :", dict(Counter(life.formats())))
            graded = sorted(len(row.recall_formats) + 1 for row in life.played)
            print(
                "  graded per day  :",
                "median",
                graded[len(graded) // 2] if graded else None,
                dict(Counter(graded)),
            )
            print("  chapter shapes  :", dict(Counter(row.get("shape") for row in life.chapters)))
            print(
                "  season phases   :",
                dict(Counter(row.context["season"]["phase"] for row in life.played)),
            )
            print(
                "  letters         :",
                len(life.letters),
                dict(Counter(row["status"] for row in life.letters)),
                dict(Counter(row["outcome"] for row in life.letters)),
            )
            print(
                "  answered in day :",
                sum(1 for row in life.letters if row["answered_in_journey"]),
            )
            print("  season reached  :", life.live.get("season_index"))
            print(
                "  dealt vs built  :",
                dict(Counter(row.dealt_shape for row in life.played)),
                "downgrades:",
                sum(1 for row in life.played if row.dealt_shape != row.day_shape),
            )
            gaps = sorted(
                row.ordinal - int(row.context["callback"]["day"])
                for row in life.played
                if row.context.get("callback") and row.ordinal >= 40
            )
            print("  callback gaps   :", gaps[-6:], "max", gaps[-1] if gaps else None)
            print(
                "  consequence days:",
                sorted({int(row["day"]) for row in life.live["consequences"]})[:6],
            )
            print(
                "  side stories    :",
                sum(
                    1
                    for row in life.live["chronicle"]
                    if row.get("kind") != "season" and row.get("side_story")
                ),
            )
            print(
                "  lapsed          :",
                [
                    (row["id"][:8], row["attempts"], row["outcome"])
                    for row in life.letters
                    if row["status"] == "lapsed"
                ],
            )
