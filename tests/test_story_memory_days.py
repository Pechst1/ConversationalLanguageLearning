"""Story engine Phase 3: what the learner said carries from one day to the next.

Walks found the story forgetting the learner overnight: Gus asked again who they were,
Camille's «non» was gone the next morning, a question the learner asked (Pablo, the
cat) fell away with the day, and a «Fin de secours» page knew nothing a learner had
told anyone (#145, #79, #132, #171). The cause was structural: nothing kept what the
learner SAID where a later day could read it; a later day saw only lines a model had
written about it. ``story_memory`` is that record (``live["memory"]``), written once
per settled day, read by the page writers with who knows what, and by each character
narrowed to what they heard.

Every test drives the assembled daily-journey API with a fake model, then reads the
durable records (the thread's memory, the pinned briefs) and the payloads the models
were actually sent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.config import settings
from app.services import living_story as engine
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from tests.test_living_story_longitudinal import (  # noqa: F401 - fixtures
    CAST,
    SceneScript,
    TurnScript,
    assembled_client,
    clock,
    driver,
    journey_enabled,
    live_state,
    pinned_draft,
    play_day,
    provider,
)
from tests.test_season_one import season_on  # noqa: F401 - fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture
def one_exchange(monkeypatch):
    """One reply ends a generated scene (the longitudinal tests' rule)."""

    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)


def _lanes(monkeypatch, on: bool) -> None:
    """Production's three-lane turn (tutor, voice, then the story lane run inline), or
    the one-actor turn the suite keeps as the rollback path."""

    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", on)
    if on:
        from app.services import story_lanes

        monkeypatch.setattr(story_lanes, "dispatcher", lambda job: story_lanes.run_story_job(job))


def _memory(db, d) -> dict:
    return dict(live_state(db, d).get("memory") or {})


# ---------------------------------------------------------------------------
# #145 «Done when»: the fake provider's «non» and «oui» lead to different next lines
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lanes", [False, True], ids=["one-actor", "lanes"])
def test_a_non_and_a_oui_on_day_two_lead_to_different_next_lines(
    lanes, monkeypatch, assembled_client, db_session, journey_enabled, clock, one_exchange  # noqa: F811
):
    """The walks' own fake provider (scripts/dev_story_engine_server.py) reads the
    memory the way a model does: the person the learner said «non» to comes back to it
    the next day and cites the line; after a «oui» the story moves on to someone else."""

    import dev_story_engine_server as dev

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    _lanes(monkeypatch, lanes)

    def life(day_two: str) -> tuple[list[dict], dict]:
        fake = dev.FakeStoryProvider()
        monkeypatch.setattr(engine, "_client", lambda: fake)
        d = driver(assembled_client, db_session, cefr="A2.1")
        drafts = []
        for answer in ("Oui, je peux vous aider samedi.", day_two, "D'accord, merci."):
            d.create()
            assert d.journey["status"] == "active", d.journey
            d.play(answer=answer)
            assert d.finish("complete").status_code == 200
            drafts.append(pinned_draft(db_session, d.journey["id"]))
            clock.advance(days=1)
        return drafts, live_state(db_session, d)

    refused, after_no = life("Non, désolé, je ne peux pas cette fois.")
    accepted, after_yes = life("Oui, avec plaisir, à samedi.")

    assert all(draft["title_fr"].startswith("Scène") for draft in refused + accepted), "every page is the fake's"
    assert [draft["opening_line_fr"] for draft in refused[:2]] == [draft["opening_line_fr"] for draft in accepted[:2]]
    assert refused[2]["opening_line_fr"] != accepted[2]["opening_line_fr"], (
        "day 3 reads the same whatever the learner answered on day 2"
    )
    # «non»: the person who heard it leads again, comes back to it, and cites the line.
    said = after_no["memory"]["said"]
    assert [row["quote"] for row in said[:2]] == ["Oui, je peux vous aider samedi.", "Non, désolé, je ne peux pas cette fois."]
    assert said[1]["to"] == refused[1]["character_id"] and said[1]["meant"] == "The learner declines."
    assert refused[2]["character_id"] == refused[1]["character_id"]
    assert refused[2]["opening_line_fr"] == "La dernière fois, vous avez dit non. Vous pouvez m'aider aujourd'hui ?"
    assert refused[2]["callback_ref"] == said[1]["id"]
    provenance = engine.ledger_row(after_no, refused[2]["callback_ref"])
    assert provenance and provenance["quote"] == "Non, désolé, je ne peux pas cette fois."
    # «oui»: the story moves on, and the new lead heard nothing to come back to.
    assert accepted[2]["character_id"] != accepted[1]["character_id"]
    assert accepted[2]["opening_line_fr"] == "Vous pouvez m'aider ?"
    assert after_yes["memory"]["said"][1]["meant"] == "The learner offers help."


# ---------------------------------------------------------------------------
# The season: T1's evening, the letter, the first day between them
# ---------------------------------------------------------------------------

NAMED = "Je m'appelle Lena. Odile, c'est ma grand-mère."


@pytest.mark.parametrize("season_on", [False, True], ids=["one-actor", "lanes"], indirect=True)
def test_the_name_the_learner_gives_on_the_first_evening_reaches_every_later_reader(
    assembled_client, db_session, journey_enabled, clock, season_on  # noqa: F811
):
    """T1 a: the learner tells Gus and Margaux who they are. The letter (T1 b) and the
    first day between tentpoles know it — each reader only as far as they heard it."""

    fake = season_on
    fake.spoil_once = False
    fake.critic_refusals_left = 0
    fake.routes = {NAMED: "a"}
    d = driver(assembled_client, db_session, cefr="A2.1")

    # Day 1, T1 a: two turns, to Gus then Margaux.
    d.create()
    d.play(answer=NAMED)
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    memory = _memory(db_session, d)
    said = memory["said"]
    assert [(row["to"], row["quote"]) for row in said] == [
        ("augustin_de_roncourt", NAMED),
        ("margaux_barman", NAMED),
    ]
    assert all(row["asked_fr"] for row in said), "each line keeps the question it answered"
    name = next(fact for fact in memory["facts"] if fact["key"] == "name")
    assert name["value"] == "Lena"
    assert {"augustin_de_roncourt", "margaux_barman"} <= set(name["known_by"])
    # What each exchange heard is kept for the memory and never read back to a model.
    second = [payload for schema, payload in fake.calls if schema == "ReplyChoice"][-1]
    assert second["history"] and all("heard" not in row for row in second["history"])

    # Day 2, T1 b: each addressee knows the name only if they heard it.
    before = len(fake.calls)
    d.create()
    d.play(answer="Oui, je veux voir l'appartement.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    readings = [payload for schema, payload in fake.calls[before:] if schema == "ReplyChoice"]
    assert "camille_marchand" in {reading["scene"]["speaker"] for reading in readings}
    for reading in readings:
        if reading["scene"]["speaker"] in name["known_by"]:
            assert reading["known"]["learner_name"] == "Lena", reading["scene"]["speaker"]
        else:
            assert "known" not in reading, reading["scene"]["speaker"]
    assert any("known" in reading for reading in readings), "someone on T1 b heard the name on T1 a"
    # Everyone at the table heard what the learner told Camille — not only those who
    # spoke before her question (the paid read: Lila knew nothing of it the next day).
    told = next(row for row in _memory(db_session, d)["said"] if row["to"] == "camille_marchand")
    assert {"augustin_de_roncourt", "lila_bonnet", "marin_leveque", "margaux_barman"} <= set(told["heard_by"])

    # Day 3: the first generated day. The director reads everything, with who knows it.
    before = len(fake.calls)
    d.create()
    d.play(answer="Oui, je reste encore un peu.")
    assert d.finish("complete").status_code == 200
    calls = fake.calls[before:]
    director = next(payload for schema, payload in calls if schema == "SceneDraft")
    assert director["memory"]["learner_name"]["value"] == "Lena"
    assert [row["quote"] for row in director["memory"]["said"]][:2] == [NAMED, NAMED]
    critic = next(payload for schema, payload in calls if schema == "StoryReview")
    assert critic["memory"]["learner_name"]["value"] == "Lena"
    # #147: every cast row says which pronoun the story uses; Camille's is this life's.
    cast = {row["id"]: row for row in director["world"]["cast"]}
    seeded = effective_flags(load_season("s1"), {}, seed=str(d.user_id))["s1.camille_gender"]
    assert cast["camille_marchand"]["pronoun_fr"] == {"f": "elle", "m": "il"}[seeded]
    assert cast["augustin_de_roncourt"]["pronoun_fr"] == "il" and cast["lila_bonnet"]["pronoun_fr"] == "elle"
    # The day's character knows the name only if they heard it, and then as a plain fact.
    lead = pinned_draft(db_session, d.journey["id"])["character_id"]
    heard = lead in name["known_by"]
    if settings.ATELIER_STORY_TURN_LANES_ENABLED:
        voice = next(payload for schema, payload in calls if schema == "VoiceReply")
        assert (voice.get("memory") or {}).get("learner_name") == ("Lena" if heard else None)
    else:
        actor = next(payload for schema, payload in calls if schema == "SemanticTurn")
        assert ((actor["story"].get("memory") or {}).get("learner_name")) == ("Lena" if heard else None)
    assert heard, f"the fake's first gap day is led by someone from T1 a ({lead})"


# ---------------------------------------------------------------------------
# «Fin de secours»: the authored ending still remembers
# ---------------------------------------------------------------------------


def test_a_fin_de_secours_day_still_remembers_what_the_learner_said(
    monkeypatch, assembled_client, db_session, journey_enabled, clock, one_exchange  # noqa: F811
):
    """The pages the nightly walks collect: when the story lane gives up and today's
    authored ending is served, what the learner said still reaches tomorrow."""

    import uuid

    import dev_story_engine_server as dev
    from sqlalchemy import select

    from app.db.models.daily_journey import DailyJourneyStep
    from app.services import story_lanes

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    _lanes(monkeypatch, True)
    fake = dev.FakeStoryProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    writes = story_lanes.run_story_lane
    monkeypatch.setattr(story_lanes, "run_story_lane", lambda *a, **k: story_lanes.StoryLaneResult(turn=None))
    d = driver(assembled_client, db_session, cefr="A2.1")
    refused = "Non, désolé, je ne peux pas. Je m'appelle Lena."
    d.create()
    d.play(answer=refused)
    assert d.finish("complete").status_code == 200
    first = pinned_draft(db_session, d.journey["id"])
    lanes = [
        (step.private_task or {}).get("story_lane") or {}
        for step in db_session.scalars(
            select(DailyJourneyStep).where(DailyJourneyStep.journey_id == uuid.UUID(d.journey["id"]))
        )
        if str(step.kind) == "resolution"
    ]
    assert [lane.get("status") for lane in lanes] == ["fallback"], "the day ended on the authored fallback"
    clock.advance(days=1)
    memory = _memory(db_session, d)
    assert [(row["to"], row["quote"]) for row in memory["said"]] == [(first["character_id"], refused)]
    name = next(fact for fact in memory["facts"] if fact["key"] == "name")
    assert name["value"] == "Lena" and first["character_id"] in name["known_by"]

    # The next day's lead heard the «non» and the name, and says so.
    monkeypatch.setattr(story_lanes, "run_story_lane", writes)
    d.create()
    d.play(answer="Oui, d'accord.")
    assert d.finish("complete").status_code == 200
    second = pinned_draft(db_session, d.journey["id"])
    assert second["character_id"] == first["character_id"]
    assert second["opening_line_fr"] == "Lena, la dernière fois, vous avez dit non. Vous pouvez m'aider aujourd'hui ?"


# ---------------------------------------------------------------------------
# What a character knows is what they heard
# ---------------------------------------------------------------------------


def test_a_character_knows_only_what_the_learner_told_them_or_said_in_front_of_them(
    assembled_client, db_session, journey_enabled, clock, provider, one_exchange  # noqa: F811
):
    d = driver(assembled_client, db_session)
    told = "Je m'appelle Lena. Je viens de Hambourg pour trois semaines."
    play_day(d, provider, answer=told, scene=SceneScript(character_id=CAST["romy"]))
    clock.advance(days=1)
    play_day(d, provider, answer="Oui, je peux venir samedi.", scene=SceneScript(character_id=CAST["lila"]))
    clock.advance(days=1)
    play_day(d, provider, answer="Avec plaisir.", scene=SceneScript(character_id=CAST["romy"]))

    actors = provider.actor_payloads()
    # Lila did not hear day 1: she knows nothing of it.
    lila = actors[1]["story"].get("memory") or {}
    assert "learner_name" not in lila and told not in [row["quote"] for row in lila.get("said") or []]
    # Romy did: the name, as a plain fact, and the line she heard (no who-heard lists).
    romy = actors[2]["story"]["memory"]
    assert romy["learner_name"] == "Lena"
    assert [row["quote"] for row in romy["said"]] == [told]
    assert all("heard_by" not in row for row in romy["said"])
    # The director reads everything, with who knows it.
    director = provider.director_contexts()[2]["memory"]
    assert director["learner_name"] == {"value": "Lena", "known_by": [CAST["romy"]]}
    assert [row["heard_by"] for row in director["said"]] == [[CAST["romy"]], [CAST["lila"]]]


def test_what_the_ending_says_the_learner_established_is_kept_only_in_their_own_words(
    assembled_client, db_session, journey_enabled, clock, provider, one_exchange  # noqa: F811
):
    d = driver(assembled_client, db_session)
    play_day(
        d,
        provider,
        answer="bonjour, je m'appelle lena et je travaille comme infirmière",
        turn=TurnScript(
            extra={
                "learned": [
                    # A model's own key for the name is still the name.
                    {"key": "Prénom", "fact_fr": "L'apprenant s'appelle Lena.", "quote": "je m'appelle lena", "value": "Lena"},
                    {"key": "job", "fact_fr": "L'apprenant travaille comme infirmière.", "quote": "je travaille comme infirmière", "value": "infirmière"},
                    # Not in the learner's words: never kept.
                    {"key": "from", "fact_fr": "L'apprenant vient de Berlin.", "quote": "Je viens de Berlin", "value": "Berlin"},
                ]
            }
        ),
    )
    facts = {fact["key"]: fact for fact in _memory(db_session, d)["facts"]}
    assert set(facts) == {"name", "job"}
    assert facts["name"]["value"] == "Lena" and facts["job"]["quote"] == "je travaille comme infirmière"


# ---------------------------------------------------------------------------
# Questions stay open across days
# ---------------------------------------------------------------------------


def test_a_question_the_learner_left_open_waits_for_a_later_page_that_answers_it(
    assembled_client, db_session, journey_enabled, clock, provider, one_exchange  # noqa: F811
):
    d = driver(assembled_client, db_session)
    asked = "Oui, je viens samedi. Il s'appelle comment, ton chat ?"
    play_day(d, provider, answer=asked, turn=TurnScript(extra={"left_open": ["Il s'appelle comment, ton chat ?"]}))
    clock.advance(days=1)
    rows = _memory(db_session, d)["open"]
    assert [(row["by"], row["question_fr"], row["status"]) for row in rows] == [
        ("learner", "Il s'appelle comment, ton chat ?", "open")
    ]

    # The next director reads it; a page that comes back to it closes it.
    plain = provider._draft

    def comes_back(context):
        value = plain(context)
        value["returns_to"] = ((context.get("memory") or {}).get("open") or [{}])[0].get("id")
        return value

    provider._draft = comes_back
    journey = play_day(d, provider, answer="Oui, d'accord.")
    clock.advance(days=1)
    assert provider.director_contexts()[1]["memory"]["open"][0]["question_fr"] == "Il s'appelle comment, ton chat ?"
    assert pinned_draft(db_session, journey)["returns_to"] == rows[0]["id"]
    closed = _memory(db_session, d)["open"][0]
    assert closed["status"] == "answered" and closed["closed_by"] == f"journey:{journey}:story"

    # An id nobody holds is dropped, never the page.
    def invents(context):
        value = plain(context)
        value["returns_to"] = "open:99:0"
        return value

    provider._draft = invents
    journey = play_day(d, provider, answer="Avec plaisir.")
    assert pinned_draft(db_session, journey)["returns_to"] is None


def test_a_page_may_keep_its_own_question_open_for_another_day(
    assembled_client, db_session, journey_enabled, clock, provider, one_exchange  # noqa: F811
):
    d = driver(assembled_client, db_session)
    plain = provider._draft
    provider._draft = lambda context: {**plain(context), "carries_over": True}
    play_day(d, provider, answer="Je ne sais pas encore.", turn=TurnScript(outcome="not_yet"))
    clock.advance(days=1)
    rows = _memory(db_session, d)["open"]
    assert [(row["by"], row["to"], row["question_fr"]) for row in rows] == [
        (CAST["romy"], "learner", "Vous pouvez nous aider ?")
    ]
    provider._draft = plain
    play_day(d, provider, answer="Oui, finalement je peux.")
    assert provider.director_contexts()[1]["memory"]["open"][0]["question_fr"] == "Vous pouvez nous aider ?"
