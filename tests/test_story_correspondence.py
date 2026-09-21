"""WP-64 — Le Courrier vit dans l'histoire.

What these tests hold down is the coupling the Courrier never had: a finished
letter is a fact in the living story, the story is a fact in the next letter, and
neither depends on ``SERIAL_WORLD_ENABLED``. Everything here runs on the fake
model path (``_safe_llm`` returns ``None``) — no provider is called and nothing
is spent.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import story_correspondence as courrier
from app.services.living_story import STATE_KEY, story_context
from app.services.missions import MissionGenerator, MissionScheduler

#: Fixed learner identities. The dice are seeded on these, so a run in September
#: 2026 and a run in CI next year deal the same hands.
#: Hex letters on purpose: SQLite gives an all-digit TEXT column numeric affinity,
#: so an id like "1111…" comes back as a float and the UUID no longer round-trips.
SEEDS = [
    UUID("aaaaaaaa-1111-4111-8111-1111111111a1"),
    UUID("bbbbbbbb-2222-4222-8222-2222222222b2"),
    UUID("cccccccc-3333-4333-8333-3333333333c3"),
    UUID("dddddddd-4444-4444-8444-4444444444d4"),
]


def _user(db_session, *, user_id: UUID | None = None) -> User:
    user = User(
        id=user_id or uuid4(),
        email=f"courrier-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _living_thread(
    db_session, user: User, *, moods: dict | None = None, thread_id: UUID | None = None
) -> SerialThread:
    """A learner with a living story but no legacy serial episodes."""

    thread = SerialThread(
        id=thread_id or uuid4(),
        user_id=user.id,
        status="active",
        world_bible={
            "logline": "Une vie parisienne.",
            "cast": [
                {"id": "samira", "name": "Samira", "role": "boulangère"},
                {"id": "romy_tremblay", "name": "Romy", "role": "journaliste"},
            ],
            "setting": {"recurring_locations": [{"id": "le_mistral", "name_fr": "Le Mistral"}]},
        },
        state={
            STATE_KEY: {
                "events": [],
                "commitments": [],
                "moods": dict(moods or {}),
            }
        },
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()
    return thread


def _letter(
    db_session,
    user: User,
    *,
    correspondent_id: str = "samira",
    contact_name: str = "Samira",
    domain: str = "food_dining",
    met: bool = True,
    text: str = "Bonjour Samira, je vais passer demain matin prendre le pain aux céréales.",
    **columns,
) -> RealWorldMission:
    mission = RealWorldMission(
        user_id=user.id,
        status="in_progress",
        cadence="ad_hoc",
        mission_type="message",
        title="Le pain de demain",
        brief="Répondez à la boulangère.",
        correspondent_id=correspondent_id,
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[{"id": "real_world_task", "label": "Dire ce que vous voulez", "required": True}],
        prompt_payload={
            "messenger": {"contact_name": contact_name, "contact_role": "boulangère", "thread_title": "Le pain de demain"},
            "variety": {"domain": domain, "contact": contact_name, "channel": "counter_chat"},
        },
        recap_payload={},
        **columns,
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": text},
            correction_payload={
                "score_0_4": 4 if met else 1,
                "objective_progress": [
                    {"id": "real_world_task", "label": "Dire ce que vous voulez", "met": met, "note": ""}
                ],
            },
            verdict="accepted" if met else "needs_revision",
            score_0_4=4 if met else 1,
        )
    )
    db_session.commit()
    db_session.refresh(mission)
    return mission


# ---------------------------------------------------------------------------
# 1. The writeback
# ---------------------------------------------------------------------------


def test_a_finished_letter_is_in_tomorrows_story_context(db_session, monkeypatch):
    """The whole package in one assertion: what was written reaches the next scene."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    thread = _living_thread(db_session, user, moods={"samira": {"mood": 0, "trust": 2}})
    mission = _letter(db_session, user)

    MissionScheduler(db_session).complete(user=user, mission=mission)

    context = story_context(db_session, user)
    event = next(item for item in context["events"] if item.get("source") == "courrier")
    assert event["id"] == f"courrier:{mission.id}"
    assert event["witnesses"] == ["samira"]
    assert event["outcome"] == "kept"
    assert "Samira" in event["summary_fr"]
    # The promise the learner actually made is an open commitment the story holds.
    assert any("passer demain matin" in item["text_fr"] for item in context["commitments"])
    # And the baker feels better about them than she did this morning.
    assert context["moods"]["samira"]["mood"] == 1
    assert context["moods"]["samira"]["trust"] == 3
    assert mission.outcome == "kept"
    assert mission.recap_payload["courrier_outcome"] == "kept"

    db_session.refresh(thread)
    assert any("Samira" in line for line in thread.state["story_so_far"])


def test_the_writeback_ignores_the_serial_world_flag(db_session, monkeypatch):
    """A living-story thread is written to whether or not the legacy serial is on."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    monkeypatch.setattr(missions_module.settings, "SERIAL_WORLD_ENABLED", False)
    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _letter(db_session, user)

    MissionScheduler(db_session).complete(user=user, mission=mission)

    assert any(
        item.get("source") == "courrier" for item in story_context(db_session, user)["events"]
    )


def test_a_missed_letter_cools_without_taking_trust(db_session, monkeypatch):
    """Consequences, not punishment: the mood drops, the slow number does not."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": 1, "trust": 3}})
    mission = _letter(db_session, user, met=False, text="Bonjour.")

    MissionScheduler(db_session).complete(user=user, mission=mission)

    moods = story_context(db_session, user)["moods"]
    assert moods["samira"] == {
        "mood": 0,
        "trust": 3,
        "last_shift": "colder",
        "last_event_id": f"courrier:{mission.id}",
        "last_source": "courrier",
    }


def test_the_writeback_is_idempotent(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user)
    mission = _letter(db_session, user)
    scheduler = MissionScheduler(db_session)

    scheduler.complete(user=user, mission=mission)
    courrier.record_letter(db_session, user=user, mission=mission, outcome="kept", learner_text="x")

    events = [item for item in story_context(db_session, user)["events"] if item.get("source") == "courrier"]
    assert len(events) == 1


def test_a_learner_without_a_living_story_still_completes(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    mission = _letter(db_session, user)

    completed = MissionScheduler(db_session).complete(user=user, mission=mission)

    assert completed.status == "completed"
    assert completed.outcome == "kept"
    assert "story_event" not in completed.recap_payload


# ---------------------------------------------------------------------------
# 2. Outcome from the corrector's flags
# ---------------------------------------------------------------------------


def test_outcome_comes_from_objective_flags_not_keywords():
    objectives = [
        {"id": "a", "required": True},
        {"id": "b", "required": True},
        {"id": "c", "required": False},
    ]
    both = {"a": {"met": True}, "b": {"met": True}}
    one = {"a": {"met": True}, "b": {"met": False}}
    optional_only = {"c": {"met": True}}

    assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=both) == "kept"
    assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=one) == "partial"
    assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=optional_only) == "partial"
    assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id={}) == "missed"
    assert (
        courrier.outcome_from_objectives(objectives=objectives, progress_by_id=both, had_submission=False)
        == "missed"
    )


def test_promises_are_quoted_from_the_letter_never_inferred():
    text = (
        "Bonjour Madame. Le chauffage est froid depuis hier. "
        "Je passerai lundi matin pour ouvrir la porte. "
        "Je voudrais un créneau avant midi."
    )
    promises = courrier.promises_in(text)

    assert [item["text_fr"] for item in promises] == ["Je passerai lundi matin pour ouvrir la porte."]
    # The conditional is politeness, not an undertaking the story may hold them to.
    assert not any("voudrais" in item["text_fr"] for item in promises)
    assert courrier.promises_in("Bonjour.") == []


# ---------------------------------------------------------------------------
# 3. Correspondent threads
# ---------------------------------------------------------------------------


def test_the_thread_with_one_person_is_the_last_three_letters(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user)
    scheduler = MissionScheduler(db_session)
    for index in range(4):
        letter = _letter(db_session, user, text=f"Bonjour Samira, message {index}.")
        letter.title = f"Lettre {index}"
        letter.prompt_payload = {
            **letter.prompt_payload,
            "messenger": {**letter.prompt_payload["messenger"], "thread_title": f"Lettre {index}"},
        }
        db_session.add(letter)
        db_session.commit()
        scheduler.complete(user=user, mission=letter)

    history = courrier.thread_history(db_session, user=user, correspondent_id="samira")

    assert len(history) == 3
    assert [item["summary_fr"] for item in history] == ["Lettre 1", "Lettre 2", "Lettre 3"]
    assert all(item["outcome"] == "kept" for item in history)
    # Somebody else's thread is empty, not everybody's letters.
    assert courrier.thread_history(db_session, user=user, correspondent_id="romy_tremblay") == []


def test_the_history_and_the_mood_reach_the_letter(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": 2, "trust": 5}})
    generator = MissionGenerator(db_session)

    payload = asyncio.run(
        generator.build_payload(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            correspondence={
                "correspondent_id": "samira",
                "mood_line": courrier.mood_line(courrier.active_thread(db_session, user), "samira"),
                "thread_history": [{"summary_fr": "Le pain de demain", "outcome": "kept"}],
                "cooling_note": None,
            },
        )
    )

    messenger = payload["prompt_payload"]["messenger"]
    assert "Le pain de demain" in messenger["thread_recap"]
    assert any("written to this person before" in rule for rule in messenger["realism_rules"])
    assert messenger["mood_line"].startswith("Ravi(e)")
    assert payload["prompt_payload"]["correspondence"]["correspondent_id"] == "samira"


# ---------------------------------------------------------------------------
# 4. Chains
# ---------------------------------------------------------------------------


def test_a_three_letter_chain_with_a_missed_middle_letter(db_session, monkeypatch):
    """Letter k shapes letter k+1, and a missed middle letter does not end the affair."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": 0, "trust": 2}})
    scheduler = MissionScheduler(db_session)

    first = _letter(db_session, user, chain_id="affair-1", chain_index=1, chain_total=3, stakes_level=1)
    scheduler.complete(user=user, mission=first)

    step = courrier.pending_chain_step(db_session, user=user)
    assert step["index"] == 2 and step["total"] == 3 and step["after_outcome"] == "kept"
    assert step["stakes_level"] == 2

    second = asyncio.run(scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False))
    assert second.chain_id == "affair-1"
    assert (second.chain_index, second.chain_total) == (2, 3)
    assert second.prompt_payload["messenger"]["contact_name"] == "Samira"
    assert second.prompt_payload["variety"]["domain"] == "food_dining"
    assert "Lettre 2 sur 3" in second.prompt_payload["messenger"]["chain_note"]
    # A chain letter carries a soft deadline; a standalone one does not.
    assert second.expires_at is not None
    # No pending step while letter 2 is the letter on the table.
    assert courrier.pending_chain_step(db_session, user=user) is None

    # The learner answers letter 2 badly: nothing required is settled.
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=second.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "Bonjour."},
            correction_payload={"score_0_4": 1, "objective_progress": []},
            verdict="needs_revision",
            score_0_4=1,
        )
    )
    db_session.commit()
    db_session.refresh(second)
    scheduler.complete(user=user, mission=second)

    assert second.outcome == "missed"
    third_step = courrier.pending_chain_step(db_session, user=user)
    assert third_step["index"] == 3 and third_step["after_outcome"] == "missed"

    third = asyncio.run(scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False))
    assert (third.chain_index, third.chain_total) == (3, 3)
    assert any(
        "essential thing went unsaid" in rule
        for rule in third.prompt_payload["messenger"]["realism_rules"]
    )

    scheduler.complete(user=user, mission=third)
    # Letter 3 of 3 closes the affair rather than queueing a fourth.
    assert courrier.pending_chain_step(db_session, user=user) is None

    moods = story_context(db_session, user)["moods"]
    # kept (+1), missed (-1), missed (-1) → the baker is a little cool, not hostile.
    assert moods["samira"]["mood"] == -1
    assert moods["samira"]["trust"] == 3


def test_an_ignored_letter_cools_the_correspondent_and_is_mentioned_once(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": 1, "trust": 3}})
    stale = _letter(
        db_session,
        user,
        chain_id="affair-2",
        chain_index=1,
        chain_total=2,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    stale.status = "available"
    db_session.add(stale)
    db_session.commit()

    lapsed = courrier.lapse_overdue_letters(db_session, user=user)

    assert [item.id for item in lapsed] == [stale.id]
    db_session.refresh(stale)
    assert stale.status == "lapsed" and stale.outcome == "ignored"
    context = story_context(db_session, user)
    assert context["moods"]["samira"]["mood"] == 0
    event = next(item for item in context["events"] if item["outcome"] == "ignored")
    assert "jamais répondu" in event["summary_fr"]
    note = courrier.cooling_note(courrier.active_thread(db_session, user), "samira")
    assert note and "sans reproche" in note
    # The affair stops chasing a learner who walked away.
    assert courrier.pending_chain_step(db_session, user=user) is None

    # The remark is made once: the next finished letter clears it.
    answered = _letter(db_session, user)
    MissionScheduler(db_session).complete(user=user, mission=answered)
    assert courrier.cooling_note(courrier.active_thread(db_session, user), "samira") is None


def test_only_chain_letters_expire(db_session, monkeypatch):
    """The weekly letter is a standing invitation; it must never lapse."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user)
    weekly = _letter(db_session, user, expires_at=datetime.now(UTC) - timedelta(days=5))
    weekly.status = "available"
    weekly.cadence = "weekly"
    db_session.add(weekly)
    db_session.commit()

    assert courrier.lapse_overdue_letters(db_session, user=user) == []
    db_session.refresh(weekly)
    assert weekly.status == "available"


# ---------------------------------------------------------------------------
# 5. Seeded selection
# ---------------------------------------------------------------------------


def _first_domains(db_session, user_id: UUID, *, count: int = 3) -> tuple[str, ...]:
    user = _user(db_session, user_id=user_id)
    scheduler = MissionScheduler(db_session)
    return tuple(
        asyncio.run(
            scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False)
        ).prompt_payload["variety"]["domain"]
        for _ in range(count)
    )


def test_two_seeds_deal_different_first_letters(db_session, monkeypatch):
    """The catalogue order is gone: whose Courrier this is decides what arrives."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    sequences = {seed: _first_domains(db_session, seed) for seed in SEEDS}

    # Four learners, at least three different openings. With twelve domains and a
    # recency ban, a collision across all four would mean the dice are not dice.
    assert len(set(sequences.values())) >= 3
    # And nobody repeats a domain inside their own three.
    for sequence in sequences.values():
        assert len(set(sequence)) == 3


def test_the_same_seed_deals_the_same_hand(db_session, monkeypatch):
    """Seeded, not random: a replay of one learner is reproducible."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    generator = MissionGenerator(db_session)
    seed = ("learner-a", "2026-W38", 0, "ad_hoc")
    picks = [
        generator._choose_variety(active_category=None, recent_variety=[], fuel_source="vocab", seed=seed)
        for _ in range(3)
    ]

    assert len({item["domain"] for item in picks}) == 1
    other = generator._choose_variety(
        active_category=None, recent_variety=[], fuel_source="vocab", seed=("learner-b", "2026-W38", 0, "ad_hoc")
    )
    assert other["domain"] != picks[0]["domain"] or other["mission_format"] != picks[0]["mission_format"]


def test_fuel_sources_still_cover_all_three_without_a_modulo(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    scheduler = MissionScheduler(db_session)
    sources = [
        asyncio.run(
            scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False)
        ).prompt_payload["variety"]["fuel_source"]
        for _ in range(6)
    ]

    # All three come round, none of them dominates, and never twice running —
    # which is what `count % 3` bought, without handing every learner the same cycle.
    assert set(sources) == {"vocab", "theme", "news_seed"}
    assert all(left != right for left, right in zip(sources, sources[1:], strict=False))
    assert courrier.seeded_order(("a", "b", "c"), "x") != courrier.seeded_order(("a", "b", "c"), "y")


# ---------------------------------------------------------------------------
# 6. Story-born letters
# ---------------------------------------------------------------------------


def _journey_event(thread: SerialThread, *, event_id: str, witness: str = "romy_tremblay") -> None:
    state = dict(thread.state)
    live = dict(state[STATE_KEY])
    live["events"] = [
        *list(live.get("events") or []),
        {
            "id": event_id,
            "scene_id": str(uuid4()),
            "witnesses": [witness],
            "summary_fr": "Vous avez refusé de signer la pétition de Romy.",
            "source_quotes": ["Je ne signerai pas."],
            "outcome": "met",
            "at": datetime.now(UTC).isoformat(),
        },
    ]
    state[STATE_KEY] = live
    thread.state = state


def test_a_character_writes_about_what_just_happened(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    # A fixed thread id: the story-letter die is seeded on it, so the hand dealt
    # here is the same one every run.
    thread = _living_thread(db_session, user, thread_id=SEEDS[0])
    for index in range(6):
        _journey_event(thread, event_id=f"journey:{index}:story")
    db_session.add(thread)
    db_session.commit()

    candidate = courrier.story_letter_candidate(db_session, user=user)

    assert candidate is not None
    assert candidate["character_id"] == "romy_tremblay"
    assert candidate["character_name"] == "Romy"
    assert "pétition" in candidate["summary_fr"]

    mission = asyncio.run(
        MissionScheduler(db_session).create(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            story_letter=candidate,
        )
    )

    assert mission.correspondent_id == "romy_tremblay"
    assert "pétition" in mission.brief
    assert mission.prompt_payload["correspondence"]["origin"] == "story_born"
    # The same event never produces a second letter.
    assert courrier.story_letter_candidate(db_session, user=user) != candidate


def test_story_born_letters_are_capped_at_two_a_week(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    thread = _living_thread(db_session, user)
    for index in range(10):
        _journey_event(thread, event_id=f"journey:{index}:story")
    state = dict(thread.state)
    state[courrier.CORRESPONDENCE_KEY] = {
        "story_born": [
            {"event_id": "already-1", "character_id": "romy_tremblay", "week": courrier.iso_week_key()},
            {"event_id": "already-2", "character_id": "romy_tremblay", "week": courrier.iso_week_key()},
        ]
    }
    thread.state = state
    db_session.add(thread)
    db_session.commit()

    assert courrier.story_letter_candidate(db_session, user=user) is None


# ---------------------------------------------------------------------------
# 7. The API surface WP-65 renders
# ---------------------------------------------------------------------------


def test_serialized_mission_carries_the_courrier_block(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    _living_thread(db_session, user, moods={"samira": {"mood": -1, "trust": 2}})
    deadline = datetime.now(UTC) + timedelta(days=3)
    mission = _letter(
        db_session, user, chain_id="affair-3", chain_index=2, chain_total=3, expires_at=deadline
    )
    mission.prompt_payload = {
        **mission.prompt_payload,
        "correspondence": {
            "correspondent_id": "samira",
            "mood_line": courrier.mood_line(courrier.active_thread(db_session, user), "samira"),
            "thread_history": [{"summary_fr": "Le pain d'hier", "outcome": "kept"}],
            "origin": "chain",
        },
    }
    db_session.add(mission)
    db_session.commit()
    MissionScheduler(db_session).complete(user=user, mission=mission)

    payload = missions_module.serialize_mission(mission)

    assert payload["chain"] == {"id": "affair-3", "index": 2, "total": 3}
    assert payload["expires_at"] == mission.expires_at.isoformat()
    assert payload["expires_at"].startswith(deadline.strftime("%Y-%m-%dT%H:%M"))
    assert payload["correspondent"]["id"] == "samira"
    assert payload["correspondent"]["name"] == "Samira"
    assert payload["correspondent"]["mood_line"].startswith("Un peu distant")
    assert payload["thread_history"] == [{"summary_fr": "Le pain d'hier", "outcome": "kept"}]
    assert payload["courrier"]["outcome"] == "kept"
    assert payload["courrier"]["origin"] == "chain"
