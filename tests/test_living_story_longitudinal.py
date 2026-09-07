"""WP-14F — independent longitudinal QA of the living-story engine.

Every test here drives the **assembled** daily-journey API (real router, real
state machine, ``build_default_adapters()``) against a real SQLite database with
a controllable clock, exactly like ``tests/test_journey_end_to_end.py``.  The
only stubbed thing is the model: ``engine._client`` is replaced by a scripted
fake, so no credential is ever needed and no request ever leaves the process.
(The repository-root ``conftest.py`` neutralises credentials as well.)

What this file is for, and what it deliberately does not claim:

* it proves **state transitions, provenance and world invariants** across at
  least fourteen simulated days per learner level;
* it proves **nothing at all** about the quality, naturalness or level fit of
  real generated French. The real-provider review remains a separate gate in
  ``docs/implementation/atelier-v2/CONTINUOUS-STORY.md`` (WP-14F).

Assertions here compare durable records against each other — the thread state,
the pinned brief the director actually received, the reader projection and the
recap — never a substring "callback appeared somewhere" check.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread
from app.services import living_story as engine
from tests import test_journey_end_to_end as support

Driver = support.Driver
register = support.register
assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


# ---------------------------------------------------------------------------
# A scripted provider: varied premises, per-day learner outcomes
# ---------------------------------------------------------------------------

# The engine rejects a premise whose content words overlap any of the last five
# situations (Jaccard >= 0.6) and a self-reported novelty_key that repeats one of
# them, so a longitudinal fake must actually vary its situations.
PREMISES = [
    "Romy cherche une idée pour une exposition dans le quartier.",
    "Le four du café est en panne le jour du marché.",
    "Un voisin veut vendre son vieux vélo et demande un prix.",
    "Le facteur a livré un colis pour quelqu'un d'autre.",
    "Une affiche annonce une soirée jeux vendredi.",
    "La pluie a inondé la cave de l'immeuble.",
    "Margaux cherche quelqu'un pour garder son chat ce week-end.",
    "Le gardien demande de descendre les poubelles avant huit heures.",
    "Un chien perdu attend devant la boulangerie depuis ce matin.",
]

# One objective per premise: the engine rejects an objective that overlaps any of the
# last five situations (WP-14F L-2), so a fixed objective would stall on day two.
OBJECTIVES = [
    "Suggest how you can help, or explain that you cannot.",
    "Propose an alternative for the market morning, or decline.",
    "Negotiate a price or say the bike does not interest you.",
    "Explain what happened to the parcel.",
    "Say whether you come on Friday and what you bring.",
    "Ask a neighbour for help, or offer yours.",
    "Accept or decline cat-sitting, and say when you are free.",
    "Agree a time for the bins, or explain why it is impossible.",
    "Describe the dog and decide who should be called.",
]

CAST = {
    "romy": "romy_tremblay",
    "margaux": "margaux_barman",
    "lila": "lila_bonnet",
}


@dataclass
class SceneScript:
    """What the fake director will propose next."""

    character_id: str = CAST["romy"]
    extra_speaker: str | None = None
    premise_index: int | None = None


@dataclass
class TurnScript:
    """What the fake actor/interpreter will return for the next learner turn."""

    outcome: str = "met"
    reply_fr: str = "Merci ! On s'organise pour samedi."
    resolution_fr: str = "Romy note votre réponse."
    summary_native: str = "You answered Romy."
    callback_fr: str = "Vous avez répondu à Romy."
    commitment_text: str | None = None
    commitment_quote: str | None = None
    resolve_open_commitments: bool = False
    close_chapter: bool = False
    needs_clarification: bool = False
    evidence: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class ScriptedProvider:
    """Fake model.  ``scene``/``turn`` are set by the test before each request."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.drafts: list[dict] = []
        self.turns: list[dict] = []
        self.scene_index = 0
        self.scene = SceneScript()
        self.turn = TurnScript()
        self.reject = False
        self.transform = lambda schema, value: value

    # -- context accessors used by assertions ---------------------------
    def director_contexts(self) -> list[dict]:
        return [payload for schema, payload in self.calls if schema == "SceneDraft"]

    def actor_payloads(self) -> list[dict]:
        return [payload for schema, payload in self.calls if schema == "SemanticTurn"]

    # -- the fake itself -------------------------------------------------
    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        self.calls.append((schema, deepcopy(source)))
        if schema == "SceneDraft":
            value = self._draft(source)
            self.drafts.append(deepcopy(value))
            self.scene_index += 1
        elif schema == "SemanticTurn":
            value = self._turn(source)
            self.turns.append(deepcopy(value))
        else:
            value = {"accepted": not self.reject, "issues": ["contradiction"] if self.reject else []}
        return SimpleNamespace(
            content=json.dumps(self.transform(schema, value), ensure_ascii=False),
            model="fake-longitudinal",
            provider="test",
            total_tokens=30,
            cost=0.0,
        )

    def _draft(self, context: dict) -> dict:
        n = self.scene_index if self.scene.premise_index is None else self.scene.premise_index
        chapter = context.get("chapter") or {}
        keeps_chapter = bool(chapter) and not chapter.get("resolved")
        speaker = self.scene.character_id
        dialogue = [{"character_id": speaker, "text_fr": "Vous avez une idée ?"}]
        if self.scene.extra_speaker:
            dialogue.append(
                {"character_id": self.scene.extra_speaker, "text_fr": "Moi j'ai le temps."}
            )
        return {
            "title_fr": f"Le quartier {n}",
            "premise_fr": PREMISES[n % len(PREMISES)],
            "setup_native": "A small neighborhood question needs an answer.",
            "objective_native": OBJECTIVES[n % len(OBJECTIVES)],
            "objective_semantics": "Express an offer, a refusal or a changed plan.",
            "character_id": speaker,
            "location_id": "le_mistral",
            "causal_reason": (
                "Follow up on what the learner actually said last time."
                if context.get("events")
                else "Nothing has happened yet; open the story."
            ),
            "source_event_ids": [e["id"] for e in context.get("events", [])[-1:]],
            "novelty_key": f"quartier-{n}",
            "chapter": {
                key: chapter[key]
                for key in ("title_fr", "dramatic_question", "possible_developments")
            }
            if keeps_chapter
            else {
                "title_fr": f"Chapitre {n}",
                "dramatic_question": f"Que devient le quartier, épisode {n} ?",
                "possible_developments": ["Demander de l'aide.", "Changer de plan."],
            },
            "panels": [
                {
                    "narration_fr": "La pluie glisse sur la vitre.",
                    "dialogue": [],
                    "visual_direction": "Wide shot of the café window at dusk.",
                },
                {
                    "narration_fr": "",
                    "dialogue": dialogue,
                    "visual_direction": "The speaker leans on the zinc counter.",
                },
            ],
            "opening_line_fr": "Vous pouvez nous aider ?",
            "suggested_response_fr": "Je peux apporter les affiches samedi.",
            "hint_native": "Say what you could bring.",
            "translation_native": "Can you help us?",
            "capability_key": None,
        }

    def _turn(self, source: dict) -> dict:
        script = self.turn
        text = source["learner_text"]
        open_ids = [
            c["id"] for c in source["story"]["commitments"] if c.get("status") == "open"
        ]
        commitments = []
        if script.commitment_text:
            quote = script.commitment_quote or text
            commitments.append({"text_fr": script.commitment_text, "source_quote": quote})
        return {
            "outcome": script.outcome,
            "understood_intent": "The learner answered the neighborhood question.",
            "evidence_quotes": script.evidence if script.evidence is not None else [text],
            "reply_fr": script.reply_fr,
            "needs_clarification": script.needs_clarification,
            "resolution_fr": script.resolution_fr,
            "summary_native": script.summary_native,
            "callback_fr": script.callback_fr,
            "commitments": commitments,
            "resolved_commitment_ids": open_ids if script.resolve_open_commitments else [],
            "chapter_resolved": script.close_chapter,
            "demonstrated_target_ids": [],
            **script.extra,
        }


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    fake = ScriptedProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def driver(client, db, *, cefr: str = "A1.1"):
    email = f"wp14f-{uuid.uuid4()}@example.com"
    headers = register(client, email, cefr=cefr)
    result = Driver(client, headers, db=db)
    result.user_id = support.learner_id(db, email)
    return result


# ---------------------------------------------------------------------------
# Durable-record readers — assertions compare records, never prose substrings
# ---------------------------------------------------------------------------


def thread_of(db, driver) -> SerialThread:
    return db.scalar(select(SerialThread).where(SerialThread.user_id == driver.user_id))


def live_state(db, driver) -> dict:
    thread = thread_of(db, driver)
    db.refresh(thread)
    return dict((thread.state or {}).get(engine.STATE_KEY) or {})


def pinned_draft(db, journey_id: str) -> dict:
    """The exact scene draft this journey was published with."""

    for step in db.scalars(
        select(DailyJourneyStep).where(DailyJourneyStep.journey_id == uuid.UUID(journey_id))
    ):
        brief = (step.private_task or {}).get("scenario_brief")
        if brief:
            return brief["story_context"]["draft"]
    raise AssertionError(f"journey {journey_id} has no pinned brief")


def scenes_of(db, driver) -> list[GraphicNovelScene]:
    return list(
        db.scalars(
            select(GraphicNovelScene)
            .where(
                GraphicNovelScene.user_id == driver.user_id,
                GraphicNovelScene.prompt_version == engine.VERSION,
            )
            .order_by(GraphicNovelScene.created_at)
        )
    )


def event_id_for(journey_id: str) -> str:
    return f"journey:{journey_id}:story"


def play_day(d, provider, *, answer: str, scene=None, turn=None, finish="complete"):
    """One whole learner day; returns the journey id it consumed."""

    provider.scene = scene if scene is not None else SceneScript()
    provider.turn = turn if turn is not None else TurnScript()
    d.create()
    assert d.journey["status"] == "active", d.journey
    journey_id = d.journey["id"]
    d.play(answer=answer)
    response = d.finish(finish)
    assert response.status_code == 200, response.text
    return journey_id


# ---------------------------------------------------------------------------
# 1. Fourteen days per level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cefr", "expected_band"), [("A1.1", "A1"), ("A2.2", "A2"), ("B1.2", "B1")]
)
def test_fourteen_days_stay_one_world_for_each_level(
    assembled_client, db_session, journey_enabled, clock, provider, cefr, expected_band
):
    """14 consecutive days for one learner: causal context, chapters, no repeats.

    The higher-level learner is the WP-14F "suitable content or an honest limit"
    probe: the engine has no supported-level ceiling, so the assertion is that a
    B1 learner is served B1-banded generated content, not an A1 scene.
    """

    d = driver(assembled_client, db_session, cefr=cefr)
    journeys: list[str] = []
    for day in range(14):
        journeys.append(
            play_day(
                d,
                provider,
                answer=f"Je peux aider samedi, jour {day}.",
                turn=TurnScript(
                    close_chapter=day % 5 == 4,
                    callback_fr=f"Vous avez répondu le jour {day}.",
                    summary_native=f"You answered on day {day}.",
                ),
            )
        )
        assert d.journey["scenario"]["level_band"] == expected_band, (
            "a generated scene must carry the learner's own level band"
        )
        clock.advance(days=1)

    contexts = provider.director_contexts()
    assert len(contexts) == 14, "one director call per day, no speculative generation"
    assert all(c["level"] == expected_band for c in contexts)

    # Every day after the first sees the previous days' real, persisted events.
    assert contexts[0]["events"] == [] and contexts[0]["commitments"] == []
    for day in range(1, 14):
        known = {e["id"] for e in contexts[day]["events"]}
        assert {event_id_for(j) for j in journeys[:day]} <= known, (
            f"day {day} lost an earlier event"
        )

    live = live_state(db_session, d)
    assert [e["id"] for e in live["events"]] == [event_id_for(j) for j in journeys]
    assert all(e["outcome"] == "met" for e in live["events"])

    # Fourteen distinct published situations, and chapters that actually close.
    situations = live["recent_situations"]
    assert len({s["novelty_key"] for s in situations}) == len(situations)
    chapter_ids = {(s.source_snapshot or {})["chapter"]["id"] for s in scenes_of(db_session, d)}
    assert len(chapter_ids) == 3, "a resolved chapter must be replaced, never replayed"

    episodes = list(
        db_session.scalars(
            select(SerialEpisode).where(SerialEpisode.thread_id == thread_of(db_session, d).id)
        )
    )
    assert len(episodes) == 14 and {e.status for e in episodes} == {"completed"}
    assert thread_of(db_session, d).current_episode_index == 14


@pytest.mark.parametrize(
    ("cefr", "expected_band"),
    [("A1.1", "A1"), ("A2.2", "A2"), ("B1.2", "B1"), ("B2.1", "B2"), ("C1.1", "B2")],
)
def test_invitation_level_matches_the_generated_scene(
    assembled_client, db_session, journey_enabled, clock, provider, cefr, expected_band
):
    """The invitation states the same supported band as the actual scene."""
    d = driver(assembled_client, db_session, cefr=cefr)
    available = d.today()["available"]
    assert available["level_band"] == expected_band
    assert provider.director_contexts() == [], "an invitation must not generate a scene"
    d.create()
    assert d.journey["scenario"]["level_band"] == available["level_band"]
    assert provider.director_contexts()[0]["level"] == expected_band


# ---------------------------------------------------------------------------
# 2. Proposals, causal chains, superseded facts
# ---------------------------------------------------------------------------


def test_a_learner_proposal_stays_open_until_a_later_day_closes_it(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    proposal = "Je propose une brocante dimanche matin."

    day1 = play_day(
        d,
        provider,
        answer=proposal,
        turn=TurnScript(
            commitment_text="Organiser une brocante dimanche.",
            commitment_quote=proposal,
            callback_fr="Vous organisez une brocante dimanche.",
        ),
    )
    clock.advance(days=1)

    stored = live_state(db_session, d)["commitments"]
    assert len(stored) == 1
    commitment = stored[0]
    assert commitment["status"] == "open"
    assert commitment["source_event_id"] == event_id_for(day1)
    assert commitment["source_quote"] == proposal, "provenance must be the learner's own words"
    assert commitment["text_fr"] == "Organiser une brocante dimanche."

    # Day 2: the director is told about the open commitment, verbatim.
    day2 = play_day(d, provider, answer="Je cherche encore des tables.", turn=TurnScript())
    context_day2 = provider.director_contexts()[1]
    carried = [c for c in context_day2["commitments"] if c["id"] == commitment["id"]]
    assert carried == [commitment], "the open commitment must reach the next day's director"
    clock.advance(days=1)

    # Day 3 resolves it through the model's own resolved_commitment_ids.
    day3 = play_day(
        d,
        provider,
        answer="La brocante est finie, tout est vendu.",
        turn=TurnScript(
            resolve_open_commitments=True,
            callback_fr="La brocante a eu lieu dimanche.",
            close_chapter=True,
        ),
    )
    clock.advance(days=1)

    closed = live_state(db_session, d)["commitments"]
    assert [c["id"] for c in closed] == [commitment["id"]]
    assert closed[0]["status"] == "resolved"
    assert closed[0]["resolved_by"] == event_id_for(day3)
    assert closed[0]["source_quote"] == proposal, "closing must not rewrite the provenance"

    # Day 4: a superseded fact never comes back as an open obligation.
    play_day(d, provider, answer="Bonjour, ça va ?", turn=TurnScript())
    context_day4 = provider.director_contexts()[3]
    revived = [c for c in context_day4["commitments"] if c["id"] == commitment["id"]]
    assert revived and revived[0]["status"] == "resolved"
    assert not [c for c in context_day4["commitments"] if c["status"] == "open"]
    assert day1 != day2 != day3


def test_three_scenes_form_a_causal_chain_with_real_event_provenance(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    journeys = []
    for day in range(3):
        journeys.append(play_day(d, provider, answer=f"Je m'en occupe, jour {day}."))
        clock.advance(days=1)

    events = live_state(db_session, d)["events"]
    assert [e["id"] for e in events] == [event_id_for(j) for j in journeys]

    # Scene 2 cites scene 1's event, scene 3 cites scene 2's — from the pinned
    # brief that was actually published, not from the model's transcript.
    for day in (1, 2):
        draft = pinned_draft(db_session, journeys[day])
        assert draft["source_event_ids"] == [event_id_for(journeys[day - 1])]
        cited = next(e for e in events if e["id"] == draft["source_event_ids"][0])
        assert cited["scene_id"], "a cited event must point at a real published scene"
        assert draft["character_id"] in cited["witnesses"], (
            "a scene may only build on an event its own character witnessed"
        )
    assert pinned_draft(db_session, journeys[0])["source_event_ids"] == []


def test_a_character_cannot_use_an_event_they_did_not_witness(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    day1 = play_day(
        d,
        provider,
        answer="Je viens samedi avec les tables.",
        scene=SceneScript(character_id=CAST["romy"]),
    )
    clock.advance(days=1)
    play_day(
        d,
        provider,
        answer="Je peux passer plus tard.",
        scene=SceneScript(character_id=CAST["margaux"]),
    )

    director = provider.director_contexts()[1]
    assert event_id_for(day1) in {e["id"] for e in director["events"]}, (
        "the director is omniscient about the learner's own canon"
    )
    actor = provider.actor_payloads()[1]
    assert actor["story"]["events"] == [], (
        "Margaux did not witness Romy's scene and must not be told about it"
    )
    assert actor["story"]["commitments"] == []
    assert actor["story"]["recent_situations"] == []
    assert "possible_developments" not in actor["story"]["chapter"]


# ---------------------------------------------------------------------------
# 3. Refusal, changed plans, failed communication, skipped day
# ---------------------------------------------------------------------------


def test_a_refusal_is_recorded_honestly_and_keeps_the_chapter_open(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    refusal = "Non, je ne peux pas venir samedi."
    play_day(
        d,
        provider,
        answer=refusal,
        turn=TurnScript(
            outcome="not_yet",
            reply_fr="Tant pis, une autre fois.",
            resolution_fr="Romy cherchera quelqu'un d'autre.",
            summary_native="You declined; Romy will ask someone else.",
            callback_fr="Vous avez refusé de venir samedi.",
            close_chapter=True,  # the model asks; the engine must not grant it
        ),
    )

    live = live_state(db_session, d)
    assert len(live["events"]) == 1
    assert live["events"][0]["outcome"] == "not_yet"
    assert live["events"][0]["source_quotes"] == [refusal]
    assert live["chapter"]["resolved"] is not True, (
        "a chapter cannot close on an unmet objective"
    )
    assert live.get("commitments", []) == [], "a refusal creates no obligation"

    recap = d.journey["recap"]
    assert recap["capability_evidence"] == []
    assert recap["story_outcome"]["callback_fr"] == "Vous avez refusé de venir samedi."
    assert recap["story_outcome"]["outcome_key"] == "open"

    scene = scenes_of(db_session, d)[0]
    assert scene.status == "completed"
    assert scene.recap_payload["resolution_fr"] == "Romy cherchera quelqu'un d'autre."


def test_a_changed_plan_supersedes_the_earlier_arrangement(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    first = "Je viens samedi à dix heures."
    play_day(
        d,
        provider,
        answer=first,
        turn=TurnScript(commitment_text="Venir samedi à dix heures.", commitment_quote=first),
    )
    clock.advance(days=1)

    changed = "Finalement je viens dimanche, pas samedi."
    day2 = play_day(
        d,
        provider,
        answer=changed,
        turn=TurnScript(
            resolve_open_commitments=True,
            commitment_text="Venir dimanche à la place.",
            commitment_quote=changed,
            callback_fr="Vous venez dimanche, plus samedi.",
        ),
    )

    commitments = live_state(db_session, d)["commitments"]
    open_now = [c for c in commitments if c["status"] == "open"]
    assert [c["text_fr"] for c in open_now] == ["Venir dimanche à la place."]
    assert open_now[0]["source_quote"] == changed
    superseded = next(c for c in commitments if c["status"] == "resolved")
    assert superseded["text_fr"] == "Venir samedi à dix heures."
    assert superseded["resolved_by"] == event_id_for(day2)


def test_failed_communication_never_becomes_success_or_credit(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    d.advance()
    provider.turn = TurnScript(
        outcome="not_yet",
        reply_fr="Je ne comprends pas bien, désolée.",
        resolution_fr="La question reste sans réponse.",
        summary_native="The question stayed unanswered.",
        callback_fr="Vous n'avez pas encore répondu.",
    )
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
    result = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts",
        headers=d.headers,
        json={
            "mutation_id": str(uuid.uuid4()),
            "expected_revision": d.journey["revision"],
            "input": {"mode": "text", "text": "euh le chat bleu table"},
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["task_outcome"] == "not_yet"
    assert body["pending"] is False
    d.journey = body["journey"]
    if d.journey.get("current_step_id") == step["id"]:
        d.advance()
    assert d.current()["kind"] == "resolution"
    d.advance()
    result = d.finish("complete")
    assert result.status_code == 200, result.text

    assert d.journey["recap"]["capability_evidence"] == []
    progress = d.capabilities()
    assert all(
        item["evidence"] == [] and item["state"] != "can_do"
        for item in progress["capabilities"]
    ), "a failed exchange must not move any capability"
    assert live_state(db_session, d)["events"][0]["outcome"] == "not_yet"


def test_a_skipped_day_creates_nothing_and_the_story_resumes(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    day1 = play_day(d, provider, answer="Je peux venir samedi.")

    clock.advance(days=1)
    calls_before = len(provider.calls)
    offered = d.today()
    assert offered["journey"] is None, "a skipped day must not auto-create a journey"
    assert len(provider.calls) == calls_before, "a skipped day costs no generation"
    clock.advance(days=1)

    day3 = play_day(d, provider, answer="Me revoilà, désolé pour hier.")
    context = provider.director_contexts()[1]
    assert [e["id"] for e in context["events"]] == [event_id_for(day1)]
    assert pinned_draft(db_session, day3)["source_event_ids"] == [event_id_for(day1)]
    assert len(live_state(db_session, d)["events"]) == 2
    assert (
        db_session.scalar(
            select(DailyJourney)
            .where(DailyJourney.user_id == d.user_id)
            .order_by(DailyJourney.local_date.desc())
        ).local_date.isoformat()
        == "2026-03-12"
    )


# ---------------------------------------------------------------------------
# 4. Abandoned drafts, concurrency, staleness, duplicates
# ---------------------------------------------------------------------------


def test_an_abandoned_draft_invents_no_ending(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    d.advance()  # read the scene, never answer
    response = d.finish("early")
    assert response.status_code == 200, response.text

    scene = scenes_of(db_session, d)[0]
    db_session.refresh(scene)
    assert scene.status == "abandoned"
    assert not scene.recap_payload
    episode = db_session.get(SerialEpisode, uuid.UUID(d.journey["scenario"]["serial_episode_id"]))
    assert episode.status == "abandoned"
    live = live_state(db_session, d)
    assert live.get("events", []) == []
    assert live.get("commitments", []) == []
    resolution = next(s for s in d.journey["steps"] if s["kind"] == "resolution")
    assert resolution["prompt"].get("character_line_fr") == ""
    assert resolution["prompt"].get("summary_native") == ""
    assert d.journey["recap"]["capability_evidence"] == []

    # The next day starts a fresh scene rather than resuming the abandoned one.
    clock.advance(days=1)
    day2 = play_day(d, provider, answer="Aujourd'hui je peux vraiment aider.")
    scenes = scenes_of(db_session, d)
    assert [s.status for s in scenes] == ["abandoned", "completed"]
    assert live_state(db_session, d)["events"][0]["id"] == event_id_for(day2)


def test_the_legacy_surface_cannot_complete_the_beat_while_the_journey_settles(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    d = driver(assembled_client, db_session)
    d.create()
    scene_id = d.journey["scenario"].get("scene_id") or str(scenes_of(db_session, d)[0].id)
    d.play(answer="Je peux apporter les tables samedi.")

    # The exchange is graded and about to settle; the optional legacy route must
    # not complete the same beat a second time.
    calls = len(provider.calls)
    refused = assembled_client.post(
        f"/api/v1/graphic-novel/scenes/{scene_id}/complete", headers=d.headers, json={}
    )
    assert refused.status_code == 409, refused.text
    assert assembled_client.post(
        "/api/v1/graphic-novel/scenes", json={}, headers=d.headers
    ).status_code == 409
    assert len(provider.calls) == calls, "a refused legacy call must never generate"

    d.finish("complete")
    live = live_state(db_session, d)
    assert len(live["events"]) == 1

    # And again after settlement: replaying the optional route changes nothing.
    after = assembled_client.post(
        f"/api/v1/graphic-novel/scenes/{scene_id}/complete", headers=d.headers, json={}
    )
    assert after.status_code == 409
    assert live_state(db_session, d) == live
    episodes = list(
        db_session.scalars(
            select(SerialEpisode).where(SerialEpisode.thread_id == thread_of(db_session, d).id)
        )
    )
    assert len(episodes) == 1 and episodes[0].status == "completed"
    assert thread_of(db_session, d).current_episode_index == 1


def test_a_stale_generation_cannot_publish_over_newer_canon(
    assembled_client, db_session, journey_enabled, clock, provider
):
    from app.db.models.user import User

    d = driver(assembled_client, db_session)
    play_day(d, provider, answer="Je viens samedi.")
    clock.advance(days=1)

    user = db_session.get(User, d.user_id)
    brief = engine.generate_scene(db_session, user=user, input_mode="text")
    assert isinstance(brief, engine.ScenarioBrief)

    # Canon moves on between generation and publication.
    thread = thread_of(db_session, d)
    state = deepcopy(thread.state)
    state[engine.STATE_KEY]["story_so_far_marker"] = "moved on"
    thread.state = state
    db_session.flush()

    journey = db_session.scalar(
        select(DailyJourney)
        .where(DailyJourney.user_id == d.user_id)
        .order_by(DailyJourney.local_date.desc())
    )
    with pytest.raises(engine.StoryUnavailable, match="story_revision_conflict"):
        engine.bind_journey(db_session, user=user, journey=journey, brief=brief)
    db_session.rollback()

    # The client-facing equivalent: a stale expected_revision is refused.
    d.create()
    stale = d.journey["revision"]
    d.advance()
    conflict = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/advance",
        headers=d.headers,
        json={
            "mutation_id": str(uuid.uuid4()),
            "expected_revision": stale,
            "current_step_id": d.journey["steps"][0]["id"],
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "journey_version_conflict"


def test_duplicate_requests_write_exactly_one_story_event(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    create_id = str(uuid.uuid4())
    body = {
        "mutation_id": create_id,
        "timezone": support.TZ,
        "budget_seconds": 300,
        "preferred_input_mode": "text",
    }
    first = assembled_client.post("/api/v1/daily-journeys", headers=d.headers, json=body)
    second = assembled_client.post("/api/v1/daily-journeys", headers=d.headers, json=body)
    assert first.status_code in (200, 201) and second.status_code in (200, 201)
    assert first.json()["id"] == second.json()["id"]
    assert len(scenes_of(db_session, d)) == 1, "a replayed create must mint one scene"
    drafts = len(provider.director_contexts())
    assert drafts == 1

    d.journey = first.json()
    d.advance()
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
    attempt = {
        "mutation_id": str(uuid.uuid4()),
        "expected_revision": d.journey["revision"],
        "input": {"mode": "text", "text": "Je peux apporter les affiches samedi."},
    }
    route = f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts"
    one = assembled_client.post(route, json=attempt, headers=d.headers)
    two = assembled_client.post(route, json=attempt, headers=d.headers)
    assert one.status_code == 200 and one.json() == two.json()
    assert len(provider.actor_payloads()) == 1, "a replayed attempt must not re-call the model"

    d.journey = one.json()["journey"]
    while d.journey.get("current_step_id"):
        d.advance()
    finish = {
        "mutation_id": str(uuid.uuid4()),
        "expected_revision": d.journey["revision"],
        "finish_kind": "complete",
    }
    a = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/finish", headers=d.headers, json=finish
    )
    b = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/finish", headers=d.headers, json=finish
    )
    assert a.status_code == 200 and b.status_code == 200
    live = live_state(db_session, d)
    assert len(live["events"]) == 1
    assert len(scenes_of(db_session, d)) == 1
    assert len(provider.director_contexts()) == drafts


# ---------------------------------------------------------------------------
# 5. Absent memory and another learner's data
# ---------------------------------------------------------------------------


def test_a_new_learner_has_no_memory_at_all(
    assembled_client, db_session, journey_enabled, clock, provider
):
    from app.db.models.user import User

    d = driver(assembled_client, db_session)
    context = engine.story_context(db_session, db_session.get(User, d.user_id))
    assert context["events"] == []
    assert context["commitments"] == []
    assert context["recent_situations"] == []
    assert context["chapter"] is None
    assert context["story_so_far"] == []
    assert context["thread_id"] is None

    d.create()
    director = provider.director_contexts()[0]
    assert director["events"] == [] and director["commitments"] == []
    assert pinned_draft(db_session, d.journey["id"])["source_event_ids"] == []


def test_another_learners_story_never_leaks_into_this_one(
    assembled_client, db_session, journey_enabled, clock, provider
):
    other = driver(assembled_client, db_session)
    secret = "Je garde le chat de Margaux tout le week-end."
    other_journey = play_day(
        other,
        provider,
        answer=secret,
        turn=TurnScript(
            commitment_text="Garder le chat de Margaux.",
            commitment_quote=secret,
            callback_fr="Vous gardez le chat de Margaux.",
        ),
    )
    other_scene = scenes_of(db_session, other)[0]

    mine = driver(assembled_client, db_session)
    play_day(mine, provider, answer="Je peux venir samedi.")

    director = provider.director_contexts()[1]
    # First scenes are drafted before the canonical threads are created.
    # Ownership must be checked on the published records, not two null draft IDs.
    assert thread_of(db_session, mine).id != thread_of(db_session, other).id
    assert director["events"] == [] and director["commitments"] == []
    blob = json.dumps(director, ensure_ascii=False)
    assert secret not in blob and event_id_for(other_journey) not in blob
    assert "chat de Margaux" not in blob

    my_live = live_state(db_session, mine)
    assert [e["id"] for e in my_live["events"]] != [event_id_for(other_journey)]
    assert my_live.get("commitments", []) == []

    listed = assembled_client.get("/api/v1/story-engine/episodes", headers=mine.headers).json()
    assert str(other_scene.id) not in [item["id"] for item in listed["episodes"]]
    assert len(listed["episodes"]) == 1
    assert (
        assembled_client.get(
            f"/api/v1/story-engine/episodes/{other_scene.id}", headers=mine.headers
        ).status_code
        == 404
    )
    assert (
        assembled_client.put(
            f"/api/v1/story-engine/episodes/{other_scene.id}/position",
            json={"panel_index": 0},
            headers=mine.headers,
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# 6. Unit-level guards the longitudinal flow depends on
# ---------------------------------------------------------------------------


def _turn_payload(text: str, commitments: list[dict] | None = None) -> dict:
    return {
        "learner_text": text,
        "history": [],
        "targets": [],
        "story": {"commitments": commitments or []},
    }


def test_a_resolved_commitment_cannot_be_resolved_again(provider):
    payload = _turn_payload(
        "C'est fait.",
        [
            {"id": "journey:a:story:commitment:0", "status": "resolved"},
            {"id": "journey:b:story:commitment:0", "status": "open"},
        ],
    )
    base = {
        "outcome": "met",
        "understood_intent": "done",
        "evidence_quotes": ["C'est fait."],
        "reply_fr": "Parfait, merci !",
        "needs_clarification": False,
        "resolution_fr": "Tout est réglé.",
        "summary_native": "All settled.",
        "callback_fr": "C'est réglé.",
        "commitments": [],
        "chapter_resolved": False,
        "demonstrated_target_ids": [],
    }
    stale = engine.SemanticTurn.model_validate(
        {**base, "resolved_commitment_ids": ["journey:a:story:commitment:0"]}
    )
    with pytest.raises(engine.StoryUnavailable, match="unknown_commitment"):
        engine._validate_turn(stale, payload)
    engine._validate_turn(
        engine.SemanticTurn.model_validate(
            {**base, "resolved_commitment_ids": ["journey:b:story:commitment:0"]}
        ),
        payload,
    )


def test_a_scene_that_repeats_a_recent_situation_is_refused(provider):
    context = {
        "world": {"cast": [{"id": CAST["romy"]}], "locations": [{"id": "le_mistral"}]},
        "events": [],
        "chapter": None,
        "recent_situations": [
            {"novelty_key": "quartier-0", "premise_fr": PREMISES[0]},
        ],
        "level": "A1",
    }
    fake = ScriptedProvider()
    fake.scene = SceneScript(premise_index=0)
    draft = engine.SceneDraft.model_validate(fake._draft(context))
    with pytest.raises(engine.StoryUnavailable, match="repeated_situation"):
        engine._validate_scene(draft, context)
