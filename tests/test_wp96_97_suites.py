"""WP-96 «Les Cahiers du feuilleton» / WP-97 «Les suites» — the story engine's half.

What the engine writes on every bound scene (``script_payload``) and in its ledgers,
for the archive to print:

* ``chapter`` — which chapter of which season this page belongs to, whether it closed
  it, and the one line the closed chapter is filed under;
* ``previously_fr`` — at most three lines, only facts the ledgers hold;
* ``margin_notes`` — one per stored row the page actually pays back, with provenance;
* ``tutoiement`` — «On se tutoie ?» staged, then accepted or declined by the reply;
* trust (0..5) that can fall — an ignored letter, a broken promise;
* pushes and letters in «tu» once the learner and the character have switched.

Everything runs on fake models: nothing is spent.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.missions as missions_module
from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.services import living_story as engine
from app.services import serial_notifications as pushes
from app.services import story_correspondence as courrier
from app.services.missions import MissionScheduler
from tests import test_living_story_longitudinal as story
from tests import test_story_correspondence as letters
from tests import test_wp80_pushes as wp80

assembled_client = story.assembled_client
clock = story.clock
journey_enabled = story.journey_enabled
provider = story.provider
one_exchange = story.one_exchange

ROMY = story.CAST["romy"]


# ---------------------------------------------------------------------------
# Pure ledger helpers
# ---------------------------------------------------------------------------


def _live() -> dict:
    return {
        "day_index": 12,
        "events": [
            {
                "id": "journey:j1:story",
                "scene_id": "scene-1",
                "witnesses": [ROMY],
                "summary_fr": "Vous avez promis d'aider Romy au marché.",
                "source_quotes": ["Je viens samedi."],
                "at": "2026-03-02T19:00:00+00:00",
                "chapter_id": "ch-2",
            },
            {
                "id": "journey:j2:story",
                "scene_id": "scene-2",
                "witnesses": [ROMY],
                "summary_fr": "Romy a trouvé un stand près du canal.",
                "source_quotes": [],
                "at": "2026-03-03T19:00:00+00:00",
                "chapter_id": "ch-2",
            },
        ],
        "consequences": [
            {
                "id": "journey:j1:story:branch:0",
                "kind": "branch",
                "character_id": ROMY,
                "text_fr": "Romy accepte votre aide au marché.",
                "quote": "vas-y, je viens samedi",
                "weight": 3,
                "day": 4,
                "event_id": "journey:j1:story",
                "chapter_id": "ch-1",
                "last_referenced": None,
                "scene_id": "scene-1",
                "date": "2026-03-02",
            },
            {
                "id": "journey:j9:story:commitment_broken:0",
                "kind": "commitment_broken",
                "character_id": "margaux_barman",
                "text_fr": "Passer voir Margaux au café.",
                "quote": "",
                "weight": 3,
                "day": 9,
                "event_id": "journey:j9:story",
            },
        ],
        "planted": [
            {"id": "p-open", "text_fr": "Un carnet reste ouvert sur la table.", "character_id": ROMY,
             "status": "open", "day": 3, "event_id": "journey:j1:story", "chapter_index": 1},
            {"id": "p-paid", "text_fr": "Une clé sous le paillasson.", "character_id": ROMY,
             "status": "paid", "day": 2, "event_id": "journey:j1:story", "chapter_index": 1},
        ],
        "chronicle": [
            {"kind": "season", "season": 1, "facts": ["j1 · Le premier soir — Vous êtes arrivé au Mistral."],
             "from_day": 1, "to_day": 1},
            {"id": "ch-1", "season": 1, "day": 5, "title_fr": "Le marché", "question": "Romy aura-t-elle un stand ?",
             "resolved_fr": "Romy obtient un stand.", "characters": [ROMY], "quote": "vas-y",
             "event_id": "journey:j1:story"},
        ],
    }


def _draft(**overrides) -> engine.SceneDraft:
    base = story.ScriptedProvider()._draft({})
    base.update(overrides)
    return engine.SceneDraft.model_validate(base)


WORLD = {"cast": [{"id": ROMY, "name": "Romy Tremblay"}, {"id": "margaux_barman", "name": "Margaux"}]}


def test_previously_lines_are_only_facts_the_ledgers_hold():
    live = _live()
    facts = {
        "Vous avez promis d'aider Romy au marché.",
        "Romy a trouvé un stand près du canal.",
        "Le marché : Romy obtient un stand.",
        "Le premier soir — Vous êtes arrivé au Mistral.",
        "Romy accepte votre aide au marché.",
    }
    mid_chapter = engine.previously_lines(live, chapter_id="ch-2")
    assert mid_chapter == [
        "Le marché : Romy obtient un stand.",
        "Vous avez promis d'aider Romy au marché.",
        "Romy a trouvé un stand près du canal.",
    ]
    new_chapter = engine.previously_lines(live, callback_ref="journey:j1:story:branch:0")
    assert 1 <= len(new_chapter) <= 3 and set(new_chapter) <= facts
    assert "Romy accepte votre aide au marché." in new_chapter
    # A life with no past has nothing to recall — and never an invented line.
    assert engine.previously_lines({}) == []
    assert engine.previously_lines({}, callback_ref="nobody-holds-this") == []


def test_margin_notes_only_on_a_real_payback():
    live = _live()
    paid = engine.margin_notes_for(
        _draft(callback_fr="Romy accepte votre aide.", callback_ref="journey:j1:story:branch:0"),
        live,
        world=WORLD,
    )
    assert paid == [
        {
            "text_fr": "Parce que vous avez dit à Romy « vas-y, je viens samedi »",
            "cause_scene_id": "scene-1",
            "cause_date": "2026-03-02",
            "character_id": ROMY,
        }
    ]
    plant = engine.margin_notes_for(_draft(pays_plant_id="p-open"), live, world=WORLD)
    assert plant and plant[0]["text_fr"].startswith("Un détail revient") and plant[0]["cause_scene_id"] == "scene-1"
    # Nothing paid, an id nobody holds, a plant already paid, a ref without a callback.
    assert engine.margin_notes_for(_draft(), live, world=WORLD) == []
    assert engine.margin_notes_for(_draft(callback_fr="x", callback_ref="ghost"), live, world=WORLD) == []
    assert engine.margin_notes_for(_draft(pays_plant_id="p-paid"), live, world=WORLD) == []
    assert engine.margin_notes_for(_draft(callback_ref="journey:j1:story:branch:0"), live, world=WORLD) == []


def test_a_margin_note_is_pinned_to_the_panel_that_plays_the_past():
    live = _live()
    draft = _draft(callback_fr="Romy accepte votre aide au marché.", callback_ref="journey:j1:story:branch:0")
    draft.panels[2].narration_fr = "Romy se souvient : elle accepte votre aide au marché."
    [note] = engine.margin_notes_for(draft, live, world=WORLD)
    assert note["panel_index"] == 2
    # Nowhere in the panels: the note stays in the page margin, unpinned.
    assert "panel_index" not in engine.margin_notes_for(_draft(pays_plant_id="p-open"), live, world=WORLD)[0]


def test_known_about_learner_and_trust_of():
    live = _live()
    live["moods"] = {ROMY: {"mood": 1, "trust": 4}}
    known = engine.known_about_learner({engine.STATE_KEY: live}, ROMY)
    assert [row["text_fr"] for row in known] == ["Romy accepte votre aide au marché."]
    assert known[0]["date"] == "2026-03-02" and known[0]["scene_id"] == "scene-1"
    margaux = engine.known_about_learner(live, "margaux_barman")
    assert margaux[0]["text_fr"] == "Vous aviez promis : Passer voir Margaux au café."
    assert engine.trust_of(live, ROMY) == 4
    assert engine.trust_of(live, "lila_bonnet") is None


def test_a_broken_promise_costs_its_witness_one_trust_once():
    moods = {"margaux_barman": {"mood": 0, "trust": 3}}
    rows = [{"id": "c1", "kind": "commitment_broken", "character_id": "margaux_barman", "event_id": "e9"}]
    after = engine.trust_after_broken_promises(moods, rows, "e9")
    assert after["margaux_barman"]["trust"] == 2
    assert engine.trust_after_broken_promises(after, rows, "e9")["margaux_barman"]["trust"] == 2
    floor = engine.trust_after_broken_promises({"margaux_barman": {"trust": 0}}, rows, "e9")
    assert floor["margaux_barman"]["trust"] == 0


def test_the_tutoiement_candidate_needs_trust_held_and_vous():
    live = {"moods": {ROMY: {"trust": 4}, "landlord_marchand": {"trust": 5}},
            "trust_streak": {ROMY: 3, "landlord_marchand": 9}, "day_index": 20}
    cast = [ROMY, "landlord_marchand"]
    today = date(2026, 3, 20)
    assert engine.tutoiement_candidate(live, {}, cast_ids=cast, today=today) == ROMY
    assert engine.tutoiement_candidate(
        {**live, "trust_streak": {ROMY: 2}}, {}, cast_ids=cast, today=today
    ) is None
    assert engine.tutoiement_candidate(live, {ROMY: {"register": "tu"}}, cast_ids=cast, today=today) is None
    declined = {**live, "tutoiement": {ROMY: {"state": "declined", "declined_on": "2026-03-10"}}}
    assert engine.tutoiement_candidate(declined, {}, cast_ids=cast, today=today) is None
    assert engine.tutoiement_candidate(declined, {}, cast_ids=cast, today=date(2026, 3, 24)) == ROMY
    accepted = {**live, "tutoiement": {ROMY: {"state": "accepted"}}}
    assert engine.tutoiement_candidate(accepted, {}, cast_ids=cast, today=today) is None


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["Oui, avec plaisir !"], "accepted"),
        (["D’accord !"], "accepted"),
        (["Volontiers, et toi ?"], "accepted"),
        (["Ok"], "accepted"),
        (["Non, je préfère le vous pour l'instant."], "declined"),
        (["Je préfère attendre."], "declined"),
        (["Tu as raison, c'est plus simple."], "accepted"),
        (["Je voudrais un café."], None),
    ],
)
def test_the_reply_decides(lines, expected):
    assert engine.tutoiement_decision(lines) == expected


def test_the_serial_closeness_rule_no_longer_switches_to_tu_by_itself():
    state = {
        "relationships": {ROMY: {"closeness": 3, "register": "tu", "register_switch_episode": 4}},
        "pending_register_switch": {"character_id": ROMY, "episode_index": 4},
    }
    live: dict = {}
    result = engine.settle_tutoiement(
        state, live, character_id=ROMY, scene_id="s", learner_lines=["Oui"], reply_fr="",
        registers_before={ROMY: "vous"}, episode_index=3,
    )
    assert result is None
    assert state["relationships"][ROMY]["register"] == "vous"
    assert "pending_register_switch" not in state
    # A register that was already «tu» before this settle is left alone.
    kept = {"relationships": {ROMY: {"register": "tu"}}}
    engine.settle_tutoiement(
        kept, {}, character_id=ROMY, scene_id="s", learner_lines=[], reply_fr="",
        registers_before={ROMY: "tu"}, episode_index=3,
    )
    assert kept["relationships"][ROMY]["register"] == "tu"


def test_margin_note_weeks_counts_full_weeks_after_day_ten():
    start = date(2026, 1, 5)
    rows = [(start + timedelta(days=offset), {"margin_notes": [{}] if offset % 5 == 0 else []}) for offset in range(38)]
    weeks = engine.margin_note_weeks(rows, start=start, days=38)
    assert sorted(weeks) == [0, 1, 2, 3]
    assert all(count >= 1 for count in weeks.values())
    assert engine.margin_note_weeks(rows, start=start, days=20) == {0: weeks[0]}


# ---------------------------------------------------------------------------
# Through the real journey (fake models)
# ---------------------------------------------------------------------------


def _scene_payloads(db, d) -> list[dict]:
    return [dict(scene.script_payload or {}) for scene in story.scenes_of(db, d)]


def test_every_bound_scene_carries_its_chapter_previously_and_margin_notes(
    assembled_client, db_session, journey_enabled, clock, provider
):
    provider.long_memory = True
    d = story.driver(assembled_client, db_session)
    for day in range(1, 9):
        story.play_day(
            d,
            provider,
            answer=f"Je peux aider, jour {day}.",
            scene=story.SceneScript(character_id=[ROMY, story.CAST["margaux"]][day % 2]),
            turn=story.TurnScript(
                callback_fr=f"Vous avez aidé le jour {day}.",
                extra={"development_index": 1, "feeling_shift": "warmer"},
            ),
        )
        clock.advance(days=1)
    payloads = _scene_payloads(db_session, d)
    live = story.live_state(db_session, d)
    assert len(payloads) == 8
    for payload in payloads:
        chapter = payload["chapter"]
        assert set(chapter) == {"index", "title_fr", "closes", "digest_fr", "season"}
        assert chapter["index"] >= 1 and chapter["season"] == 1 and chapter["title_fr"]
        assert (chapter["digest_fr"] is not None) == chapter["closes"]
        assert len(payload["previously_fr"]) <= 3
        assert isinstance(payload["margin_notes"], list)
    assert payloads[0]["previously_fr"] == [] and payloads[0]["margin_notes"] == []
    # Chapters count up within the season, and the closing page names its digest.
    indices = [payload["chapter"]["index"] for payload in payloads]
    assert indices == sorted(indices) and indices[-1] >= 2
    closed = [payload["chapter"] for payload in payloads if payload["chapter"]["closes"]]
    assert closed and all("→" in row["digest_fr"] for row in closed)
    # «Précédemment» only ever repeats what the ledgers hold.
    known = " ".join(
        [str(event.get("summary_fr")) for event in live.get("events") or []]
        + [f"{row.get('title_fr')} : {row.get('resolved_fr')}" for row in live.get("chronicle") or []]
        + [str(row.get("text_fr")) for row in live.get("consequences") or []]
        + [str(row.get("text_fr")) for row in live.get("planted") or []]
    )
    for payload in payloads:
        for line in payload["previously_fr"]:
            assert line.rstrip("…") in known, line
    # Margin notes: only on pages whose draft paid a stored row back, and each points
    # at an earlier page of this very life.
    scene_ids = [str(scene.id) for scene in story.scenes_of(db_session, d)]
    drafts = provider.drafts
    noted = [index for index, payload in enumerate(payloads) if payload["margin_notes"]]
    assert noted, "a compliant director paid nothing back in eight days"
    for index in noted:
        assert drafts[index].get("callback_ref") or drafts[index].get("pays_plant_id")
        for note in payloads[index]["margin_notes"]:
            assert {"text_fr", "cause_scene_id", "cause_date", "character_id"} <= set(note)
            assert set(note) <= {"text_fr", "cause_scene_id", "cause_date", "character_id", "panel_index"}
            if note["cause_scene_id"]:
                assert note["cause_scene_id"] in scene_ids[:index]
                assert note["cause_date"]


def _set_trust(db, d, character_id: str, *, trust: int, streak: int) -> None:
    thread = story.thread_of(db, d)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    live["moods"] = {**(live.get("moods") or {}), character_id: {"mood": 1, "trust": trust}}
    live[engine.TRUST_STREAK_KEY] = {**(live.get(engine.TRUST_STREAK_KEY) or {}), character_id: streak}
    state[engine.STATE_KEY] = live
    thread.state = state
    db.add(thread)
    db.commit()


def _asks_when_told(provider):
    """A compliant director: when ``tutoiement`` names a character, they ask."""

    def transform(schema, value):
        if schema != "SceneDraft":
            return value
        context = provider.director_contexts()[-1]
        asking = (context.get("tutoiement") or {}).get("character_id")
        if asking and value.get("character_id") == asking:
            return {**value, "opening_line_fr": "Au fait… on se tutoie ?"}
        return value

    return transform


def _relationship(db, d, character_id: str) -> dict:
    thread = story.thread_of(db, d)
    db.refresh(thread)
    return dict(((thread.state or {}).get("relationships") or {}).get(character_id) or {})


def test_on_se_tutoie_accepted_switches_the_register_and_the_pushes(
    assembled_client, db_session, journey_enabled, clock, provider
):
    provider.transform = _asks_when_told(provider)
    d = story.driver(assembled_client, db_session)
    romy = story.SceneScript(character_id=ROMY)
    story.play_day(d, provider, answer="Bonjour Romy.", scene=romy)
    clock.advance(days=1)
    assert "tutoiement" not in provider.director_contexts()[-1]
    _set_trust(db_session, d, ROMY, trust=5, streak=3)

    story.play_day(d, provider, answer="Oui, avec plaisir !", scene=story.SceneScript(character_id=ROMY, premise_index=3))

    assert provider.director_contexts()[-1]["tutoiement"]["character_id"] == ROMY
    payload = _scene_payloads(db_session, d)[-1]
    assert payload["tutoiement"] == {"character_id": ROMY, "state": "accepted"}
    relation = _relationship(db_session, d, ROMY)
    assert relation["register"] == "tu" and relation["register_switch_source"] == "tutoiement"
    assert relation["register_switch_episode"] >= 1
    live = story.live_state(db_session, d)
    assert live["tutoiement"][ROMY]["state"] == "accepted"
    # Never asked again.
    clock.advance(days=1)
    story.play_day(d, provider, answer="Salut !", scene=story.SceneScript(character_id=ROMY, premise_index=5))
    assert "tutoiement" not in provider.director_contexts()[-1]
    assert "tutoiement" not in _scene_payloads(db_session, d)[-1]
    assert _relationship(db_session, d, ROMY)["register"] == "tu"

    # Pushes now say «tu» in Romy's voice.
    user = db_session.get(User, d.user_id)
    assert pushes.character_register(db_session, user, ROMY) == "tu"
    assert pushes.character_register(db_session, user, "margaux_barman") == "vous"
    evening = pushes.streak_at_risk_push(db_session, user, days=4)
    assert evening.character_id == ROMY
    assert evening.message == pushes.STREAK_LINES_TU[ROMY]["A"].format(days=4)


def test_on_se_tutoie_declined_stays_vous_and_is_not_asked_again_for_two_weeks(
    assembled_client, db_session, journey_enabled, clock, provider
):
    provider.transform = _asks_when_told(provider)
    d = story.driver(assembled_client, db_session)
    story.play_day(d, provider, answer="Bonjour Romy.", scene=story.SceneScript(character_id=ROMY))
    clock.advance(days=1)
    _set_trust(db_session, d, ROMY, trust=5, streak=3)

    story.play_day(
        d, provider, answer="Non, je préfère le vous pour l'instant.",
        scene=story.SceneScript(character_id=ROMY, premise_index=3),
    )

    assert _scene_payloads(db_session, d)[-1]["tutoiement"] == {"character_id": ROMY, "state": "declined"}
    assert _relationship(db_session, d, ROMY).get("register", "vous") == "vous"
    for offset, premise in ((1, 5), (6, 7)):
        clock.advance(days=offset)
        _set_trust(db_session, d, ROMY, trust=5, streak=5)
        story.play_day(d, provider, answer="Bonsoir.", scene=story.SceneScript(character_id=ROMY, premise_index=premise))
        assert "tutoiement" not in provider.director_contexts()[-1]
    # Fourteen days after the refusal, she may ask once more.
    clock.advance(days=8)
    _set_trust(db_session, d, ROMY, trust=5, streak=5)
    story.play_day(d, provider, answer="D'accord !", scene=story.SceneScript(character_id=ROMY, premise_index=1))
    assert provider.director_contexts()[-1]["tutoiement"]["character_id"] == ROMY
    assert _scene_payloads(db_session, d)[-1]["tutoiement"]["state"] == "accepted"


def test_the_morning_push_says_tu_after_the_switch(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")
    user = wp80._learner(db_session, tz="Europe/Paris", band="B1")
    wp80._journey(db_session, user, date(2026, 9, 21), status="completed")
    before = pushes.daily_journey_morning_push(db_session, user, today=date(2026, 9, 22))
    assert before.message == pushes.MORNING_LINES[ROMY]["B"]
    db_session.add(
        engine.SerialThread(
            id=uuid.uuid4(), user_id=user.id, status="active",
            state={"relationships": {ROMY: {"register": "tu", "closeness": 3}}},
        )
    )
    db_session.commit()
    after = pushes.daily_journey_morning_push(db_session, user, today=date(2026, 9, 22))
    assert after.message == pushes.MORNING_LINES_TU[ROMY]["B"]
    assert " vous" not in after.message.lower() and " votre" not in after.message.lower()


def test_a_story_letter_is_written_in_tu_after_the_switch(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = letters._user(db_session)
    thread = letters._living_thread(db_session, user, thread_id=letters.SEEDS[0])
    for index in range(6):
        letters._journey_event(thread, event_id=f"journey:{index}:story")
    state = dict(thread.state)
    state["relationships"] = {ROMY: {"register": "tu"}}
    thread.state = state
    db_session.add(thread)
    db_session.commit()

    candidate = courrier.story_letter_candidate(db_session, user=user)
    assert candidate["character_id"] == ROMY and candidate["register"] == "tu"
    context = courrier.story_letter_context(candidate)
    assert context["register"].startswith("tu") and "t'écrit" in context["scenario"]
    mission = asyncio.run(
        MissionScheduler(db_session).create(
            user=user, mission_type="message", cadence="ad_hoc", use_news=False, story_letter=candidate
        )
    )
    blob = str(mission.prompt_payload)
    assert "tu / warm informal" in blob
    # And a «vous» correspondent keeps the writer's own inference.
    assert courrier.story_letter_context({**candidate, "register": "vous"})["register"] is None


def test_trust_falls_when_a_letter_is_ignored(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = letters._user(db_session)
    letters._living_thread(db_session, user, moods={"samira": {"mood": 1, "trust": 4}})
    stale = letters._letter(
        db_session, user, chain_id="affair-9", chain_index=1, chain_total=2,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    stale.status = "available"
    db_session.add(stale)
    db_session.commit()

    courrier.lapse_overdue_letters(db_session, user=user)

    thread = courrier.active_thread(db_session, user)
    assert engine.trust_of(thread.state, "samira") == 3


# ---------------------------------------------------------------------------
# Harness level: a life shows at least one margin note a week after day 10
# ---------------------------------------------------------------------------


def test_a_harness_life_prints_a_margin_note_every_week_after_day_ten(db_engine):
    from tests import test_long_horizon_evidence as evidence

    days = 38
    with evidence.horizon_run(db_engine, days=days, labels=("A",)) as record:
        life = record.lives[0]
        from sqlalchemy.orm import sessionmaker

        session = sessionmaker(bind=db_engine)()
        try:
            scenes = session.scalars(
                select(GraphicNovelScene)
                .where(GraphicNovelScene.user_id == uuid.UUID(life.user_id))
                .where(GraphicNovelScene.prompt_version == engine.VERSION)
            ).all()
            dated = []
            for scene in scenes:
                journey_id = (scene.source_snapshot or {}).get("journey_id")
                journey = session.get(DailyJourney, uuid.UUID(journey_id)) if journey_id else None
                if journey is not None:
                    dated.append((journey.local_date, dict(scene.script_payload or {})))
        finally:
            session.close()
    weeks = engine.margin_note_weeks(dated, start=evidence.START.date(), days=days)
    assert weeks and min(weeks.values()) >= 1, weeks
