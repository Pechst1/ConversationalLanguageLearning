"""#314: a day has ONE issue number, and a re-read day says it is a re-read up front.

Live walk 24 Oct 2026: Home called the day «Nº 13 · La clé d'Odile», the Feuilleton
archive printed «Nº 12» for both 23 Oct and the re-read of 24 Oct, and only the
closing panel said «A re-read … The story did not move on today.».

Why: the number was recomputed on every read from two unrelated sequences (a serial
episode's index for a written day, the count of the learner's days for a scene-less
day), and Home headlined the *planned* tentpole for a day that had become a re-read.
"""

from __future__ import annotations

import json
import uuid

from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialEpisode
from app.services import living_story as engine
from tests import test_journey_end_to_end as support
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_wp96_story_archive import _archive, _days

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def _director_fails(provider, monkeypatch) -> None:
    original = provider.generate_chat_completion

    def refused(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "SceneDraft":
            raise engine.StoryUnavailable("guard: gendered_agreement")
        return original(messages, **kwargs)

    monkeypatch.setattr(provider, "generate_chat_completion", refused)


def _play_day(d, answer: str) -> dict:
    d.create()
    d.play(answer=answer)
    assert d.finish("complete").status_code == 200
    return d.journey


def test_a_reread_day_has_one_issue_number_on_home_reader_and_archive(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    d = support.Driver(
        assembled_client, support.register(assembled_client, f"n314-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session
    )
    previous: list[dict] = []
    for answer in ("Odile, c'est ma grand-mère.", "Oui, je reste une semaine.", "Je voudrais un café, s'il vous plaît."):
        previous.append(_play_day(d, answer))
        clock.advance(days=1)

    # The live learner's episode indexes ran ahead of their day count (lost days
    # re-read a page and bind no episode): the last written day is Nº 12 on day 3.
    episode = db_session.get(SerialEpisode, uuid.UUID(db_session.get(DailyJourney, uuid.UUID(previous[-1]["id"])).serial_episode_id))
    episode.episode_index = 11
    db_session.commit()

    with monkeypatch.context() as failing:
        _director_fails(season_on, failing)
        announced = d.today()["headline"]["edition_no"]
        today = d.create()
        assert today["scenario"]["scenario_key"].startswith("season_reprise:"), "the lost day is a re-read"
        headline = d.today()["headline"]
        journey_no = today["edition_no"]
        scene = next(step for step in today["steps"] if step["kind"] == "scene")
        d.play(answer="Oui. Je vends et je rentre.")
        assert d.finish("complete").status_code == 200
        archive_days = {day["journey_id"]: day for day in _days(_archive(assembled_client, d))}
        archive_no = archive_days[today["id"]]["edition_no"]

        numbers = [archive_days[row["id"]]["edition_no"] for row in previous] + [archive_no]
        assert headline["edition_no"] == journey_no == archive_no, (headline["edition_no"], journey_no, archive_no)
        assert len(set(numbers)) == len(numbers), f"two days share a Nº: {numbers}"
        assert numbers == sorted(numbers), numbers
        assert announced == journey_no, f"Home announced Nº {announced} before the day, the day is Nº {journey_no}"
        assert headline["title_fr"] == today["scenario"]["title_fr"], "Home headlines the page that is re-read"
        assert scene["prompt"].get("reread_native"), "the re-read is announced before panel 1"
        assert archive_days[today["id"]]["reread"] is True
