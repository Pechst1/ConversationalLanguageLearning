"""#664: every line of the scene thread keeps the speaker who said it.

Walk 10 Nov 2026 (fake provider, A1, S1 day 1 «Le mauvais accueil»): Gus asks «Alors ?
C'est qui, vous ? Et pourquoi ici ?»; after the first reply the header moves to Margaux
(#594: the next question is hers), and Gus's question was redrawn with Margaux's face and
name.

ROOT CAUSE: who said a line of the respond step had one source, the respond prompt's
``character_id``/``character_name``, and that field means «the person the question now
open is put to». #594 made it move to the next addressee, so every past line read from it
moved too. The exchange now keeps the line it answered with its own speaker (resolved
through the cast registry when it was asked), and the thread and the step's voice read
that, never the prompt.
"""

from __future__ import annotations

import uuid

from tests import test_journey_end_to_end as support
from tests.test_season_one import season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

GUS_ASKS = "Alors ? C'est qui, vous ? Et pourquoi ici ?"
ANSWER = "je suis Lena. je suis ici pour la appartement de ma grand mere"


def _first_reply(d) -> tuple[dict, dict]:
    """Plays day 1 up to its reply, answers once; the step before, and the turn after."""

    d.create()
    step = None
    for _ in range(40):
        step = d.current()
        if step is None or step["kind"] == "respond":
            break
        if step["kind"] == "recall":
            d.attempt(d.recall_answer(step, correct=True))
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
        else:
            d.advance()
    assert step and step["kind"] == "respond", step
    body = d.attempt({"mode": "text", "text": ANSWER}).json()
    return step, body


def test_gus(assembled_client, db_session, journey_enabled, clock, season_on) -> None:  # noqa: F811
    season_on.routes = {ANSWER: "a"}
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"thread-664-{uuid.uuid4()}@example.com", cefr="A1.1"),
        db=db_session,
    )
    before, body = _first_reply(d)
    asked = before["prompt"]
    assert asked["character_id"] == "augustin_de_roncourt" and asked["character_line_fr"] == GUS_ASKS, asked

    prompt = (body.get("next_turn") or {}).get("prompt") or {}
    assert prompt.get("character_id") == "margaux_barman", f"#594: exchange 2 is Margaux's: {prompt}"
    first = (prompt.get("thread") or [{}])[0]
    line = first.get("prompt_line") or {}
    said = (line.get("speaker_id"), line.get("speaker_name"), line.get("text_fr"))
    assert said == ("augustin_de_roncourt", "Gus", GUS_ASKS), (
        f"the thread's opening question is Gus's, while the prompt names Margaux; "
        f"the exchange says {said!r}, so the client can only draw it under the prompt's {prompt.get('character_name')!r}"
    )


def test_voice(assembled_client, db_session, journey_enabled, clock, season_on) -> None:  # noqa: F811
    """The step's voice reads the same line: Gus's question is still spoken, by Gus."""

    from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
    from app.services import line_audio

    season_on.routes = {ANSWER: "a"}
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"voice-664-{uuid.uuid4()}@example.com", cefr="A1.1"),
        db=db_session,
    )
    before, _body = _first_reply(d)
    journey = db_session.get(DailyJourney, uuid.UUID(d.journey["id"]))
    step = db_session.get(DailyJourneyStep, uuid.UUID(before["id"]))
    db_session.refresh(step)
    found = line_audio.match_line(line_audio.step_lines(db_session, journey, step), GUS_ASKS)
    who = found.character_id if found else None
    assert who == "augustin_de_roncourt", f"Gus's question after the first reply is voiced by {who!r}"
