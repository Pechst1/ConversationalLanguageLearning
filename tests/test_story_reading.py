"""Phase 2 «Folge in Akten», PR 4: the story's words a day read, counted.

The phase's own number (``story_reading``): each opened act's page, its character's
lines in the reply and its ending, in whitespace words as the planner prices a page
(``journey_planner.scene_texts``). It stands on the Fertig screen (the today
envelope's ``session.tally``) and in the weekly dossier. Here it is checked against
what the app itself put on the screen: the published pages, the reply's thread and the
ending, as the learner's screens read them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.services.journey_contracts import StepKind, step_act
from app.services.story_reading import StoryReading, day_reading
from tests import test_story_acts_day as acts_day
from tests import test_story_acts_morning as morning

assembled_client = morning.assembled_client
clock = morning.clock
journey_enabled = morning.journey_enabled
season_on = morning.season_on
acts_writer = morning.acts_writer

ANSWER = acts_day.ANSWER


def _words(*texts: str | None) -> int:
    return sum(len(str(text or "").split()) for text in texts)


# ---------------------------------------------------------------------------
# What counts: what reached the screen
# ---------------------------------------------------------------------------


def _brief(opening: str, panels: list[dict]) -> dict:
    return {"scenario_key": "reading-test", "opening_line_fr": opening, "panels": panels}


def _step(ordinal: int, kind: StepKind, *, act: int = 1, started: bool = True, status: str = "completed",
          private: dict | None = None, prompt: dict | None = None) -> DailyJourneyStep:
    step = DailyJourneyStep(
        ordinal=ordinal,
        kind=kind.value,
        status=status,
        private_task={**(private or {}), **({"act": act} if act > 1 else {})},
        public_prompt=dict(prompt or {}),
    )
    step.started_at = datetime(2026, 11, 2, 9, tzinfo=UTC) if started else None
    return step


PAGE_1 = [
    {"narration_fr": "Le café est plein ce matin.", "dialogue": [{"character_id": "margaux", "text_fr": "Bonjour, vous désirez ?"}]},
    {"narration_fr": "", "dialogue": [{"character_id": "margaux", "text_fr": "Il reste une table au fond."}]},
]
OPENING_1 = "Et pour vous, ce sera quoi ?"
PAGE_2 = [
    {"narration_fr": "Le soir tombe sur la place.", "dialogue": [{"character_id": "jules", "text_fr": "Tu as entendu la radio ?"}]},
]
OPENING_2 = "Tu as entendu la radio ?"  # printed on the page: read once


def _day() -> DailyJourney:
    return DailyJourney(
        steps=[
            _step(0, StepKind.RECALL, private={"answer": "un mot d'exercice"}, prompt={"question_fr": "Un exercice ne compte pas."}),
            # An older day: its steps finished before they kept their start time.
            _step(1, StepKind.SCENE, started=False, private={"scenario_brief": _brief(OPENING_1, PAGE_1)}),
            _step(2, StepKind.RESPOND, started=False, private={"turns": [
                {"learner": "Un café, s'il vous plaît.", "character": "Très bien, un café."},
                {"learner": "Merci beaucoup !", "character": "Voilà, monsieur."},
            ]}),
            _step(3, StepKind.RESOLUTION, started=False, prompt={"character_line_fr": "Margaux sourit : à demain !"}),
            _step(4, StepKind.SCENE, act=2, private={"act_brief": _brief(OPENING_2, PAGE_2)}),
            _step(5, StepKind.RESPOND, act=2, status="skipped", private={"turns": [
                {"learner": "Oui, une chanson triste.", "character": "Ah, c'est la même chanson qu'hier."},
            ]}),
            # The story lane is still writing this ending: whatever line the prompt
            # still carries is not on the screen.
            _step(6, StepKind.RESOLUTION, act=2, status="active",
                  prompt={"character_line_fr": "Une ligne du plan.", "story_pending": True}),
            # The day ended before «À côté»: its page was never opened.
            _step(7, StepKind.SCENE, act=3, started=False, status="skipped",
                  private={"act_brief": _brief("Qui frappe à la porte ?", PAGE_1)}),
            _step(8, StepKind.RESPOND, act=3, started=False, status="skipped"),
            _step(9, StepKind.RESOLUTION, act=3, started=False, status="skipped",
                  prompt={"character_line_fr": "Une fin jamais lue."}),
        ]
    )


def _texts(panels: list[dict]) -> list[str]:
    return [
        text
        for panel in panels
        for text in [panel["narration_fr"], *(line["text_fr"] for line in panel["dialogue"])]
        if text
    ]


def test_what_counts_is_each_opened_act_s_page_its_character_s_lines_and_its_ending():
    day = _day()
    first = (
        _words(*_texts(PAGE_1), OPENING_1)  # the page, and the question it does not print
        + _words("Très bien, un café.", "Voilà, monsieur.")  # what the character said, not the learner
        + _words("Margaux sourit : à demain !")
    )
    second = _words(*_texts(PAGE_2)) + _words("Ah, c'est la même chanson qu'hier.")
    assert [step_act(step) for step in day.steps if step.kind == "scene"] == [1, 2, 3]
    assert day_reading(day) == StoryReading(acts=2, words=first + second), (
        "the exercise, the learner's own lines, a pending ending and an act never opened count nothing"
    )

    # The ending counts once it stands on the screen.
    ending = day.steps[6]
    ending.public_prompt = {"character_line_fr": "La radio se tait. Jules éteint la lampe.", "story_pending": False}
    assert day_reading(day) == StoryReading(acts=2, words=first + second + _words("La radio se tait. Jules éteint la lampe."))


def test_a_day_that_never_opened_its_page_read_nothing_of_the_story():
    day = _day()
    for step in day.steps:
        step.started_at, step.status = None, "pending"
    day.steps[0].status = "completed"
    assert day_reading(day) == StoryReading()
    assert day_reading(None) == StoryReading()


# ---------------------------------------------------------------------------
# Played days: the count is what the app showed
# ---------------------------------------------------------------------------


def _printed(d, scene_id: str) -> list[str]:
    """What the reader prints of a page: each panel's narration, then its lines."""

    response = d.client.get(f"/api/v1/story-engine/episodes/{scene_id}", headers=d.headers)
    assert response.status_code == 200, response.text
    texts: list[str] = []
    for panel in response.json()["panels"]:
        texts.append(str(panel.get("narration_fr") or ""))
        texts.extend(str(line.get("text_fr") or "") for line in panel.get("dialogue") or [])
    return [text.strip() for text in texts if text.strip()]


def _page(d, brief: dict) -> int:
    """An act's page as the reader printed it, and the opening question when the
    page does not print it."""

    page = _printed(d, brief["story_context"]["scene_id"])
    opening = " ".join(str(brief.get("opening_line_fr") or "").split())
    if opening and not any(opening.casefold() in text.casefold() for text in page):
        page.append(opening)
    return _words(*page)


def _said(results: list[dict]) -> int:
    """Every reply the character gave on screen, the one closing the conversation
    too: what each answer was answered with."""

    replies = [str(result.get("character_reply_fr") or "") for result in results]
    assert any(replies), "the reply was answered"
    return _words(*replies)


def _ending(public_steps: list[dict], act: int) -> int:
    [ending] = [step for step in public_steps if step["kind"] == "resolution" and step.get("act", 1) == act]
    assert ending["prompt"]["character_line_fr"]
    return _words(ending["prompt"]["character_line_fr"])


def _scenes(db_session, d) -> list[DailyJourneyStep]:
    journey = acts_day._journey(db_session, d)
    return [step for step in sorted(journey.steps, key=lambda step: step.ordinal) if step.kind == "scene"]


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_a_day_of_two_acts_says_both_acts_and_their_words_on_the_fertig_screen(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d = acts_day._two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    results = d.play(answer=ANSWER)
    assert d.finish("complete").status_code == 200

    envelope = d.today()
    public = envelope["journey"]["steps"]
    scene1, scene2 = _scenes(db_session, d)
    pages = _page(d, scene1.private_task["scenario_brief"]) + _page(d, scene2.private_task["act_brief"])
    words = pages + _said(results) + _ending(public, 1) + _ending(public, 2)
    tally = envelope["session"]["tally"]
    assert (tally["acts"], tally["story_words"]) == (2, words)
    assert tally["scenes"] == 1, "the day's scene, as the tally always said it"
    assert day_reading(acts_day._journey(db_session, d)) == StoryReading(acts=2, words=words)
    # The second act adds its own page and its own ending to the first's.
    assert _page(d, scene2.private_task["act_brief"]) > 0 and _ending(public, 2) > 0


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_an_act_the_day_never_opened_adds_nothing_to_the_count(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d = acts_day._two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    results: list[dict] = []
    for _ in range(40):  # the first act, up to its ending
        step = d.current()
        if step["kind"] == "resolution":
            break
        if step["kind"] == "respond":
            response = d.attempt({"mode": "text", "text": ANSWER})
            assert response.status_code == 200, response.text
            results.append(response.json())
            if response.json().get("next_turn"):
                continue
        elif step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
        if d.journey.get("current_step_id") == step["id"]:
            d.advance()
    assert d.finish("early").status_code == 200

    envelope = d.today()
    scene1, scene2 = _scenes(db_session, d)
    assert scene2.started_at is None
    first = _page(d, scene1.private_task["scenario_brief"]) + _said(results) + _ending(envelope["journey"]["steps"], 1)
    tally = envelope["session"]["tally"]
    assert (tally["acts"], tally["story_words"]) == (1, first)


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_a_day_of_one_act_is_counted_and_the_week_adds_its_days(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    morning._acts_on(monkeypatch)
    user, d = morning._intensif_learner_on_a_gap_day(assembled_client, db_session)
    from app.services.journey_latency import prefetch_scene_for

    assert prefetch_scene_for(db_session, user) == "prefetched"  # no act after the page
    d.create()
    results = d.play(answer=ANSWER)
    assert d.finish("complete").status_code == 200

    envelope = d.today()
    [scene] = _scenes(db_session, d)
    words = _page(d, scene.private_task["scenario_brief"]) + _said(results) + _ending(envelope["journey"]["steps"], 1)
    tally = envelope["session"]["tally"]
    assert (tally["scenes"], tally["acts"], tally["story_words"]) == (1, 1, words)

    # The weekly dossier sums the days started in its window (the frozen clock started
    # this one in March; it is moved into this week, then out of it).
    journey = db_session.get(DailyJourney, uuid.UUID(str(d.journey["id"])))
    journey.started_at = datetime.now(UTC) - timedelta(days=2)
    db_session.commit()
    dossier = d.client.get("/api/v1/progress/weekly-dossier", headers=d.headers)
    assert dossier.status_code == 200, dossier.text
    assert dossier.json()["stats"]["story_words_read"] == words
    journey.started_at = datetime.now(UTC) - timedelta(days=8)
    db_session.commit()
    dossier = d.client.get("/api/v1/progress/weekly-dossier", headers=d.headers)
    assert dossier.json()["stats"]["story_words_read"] == 0
