# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""WP-93 «Plus d'histoire, moins d'exercices» (planner/API half) and WP-92's rule card.

* The page is priced by what is on it: its panels, its lines, and their audio.
* Nothing sits between the scene's closing question and the reply (W5): the
  rule card, its guided items and the forge come before the scene; the builds
  come after the reply. Day 1 never drills the taste's words.
* Recall is capped per rhythm, and drills never take the input floor.
* Engine days pose choices and word banks from the scene's lexicon (WP-68 L-1).
* The «Lecture» step (READ): Soutenu/Intensif only, optional, after the ending,
  projected on every read — «coulisses» from the story lane, «relecture» of
  yesterday's page — and its page opens through ``/story-engine/episodes/{id}``.
* The rule card carries a line of today's scene with the form marked (WP-92).
* The word biography says where the story brought a word back.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas.daily_journey import ReadPrompt, RulePrompt
from app.services import journey_planner as planner
from app.services.journey_contracts import (
    RHYTHM_BUDGETS,
    DayShape,
    StepKind,
    is_heard_step,
    rhythm_caps,
)
from app.services.journey_day_shapes import DayShapeInputs
from app.services.living_story import VERSION as ENGINE_VERSION
from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures
    Driver,
    assembled_client,
    clock,
    journey_enabled,
    learner_id,
    register,
)
from tests.test_journey_planner import _brief, _candidate
from tests.test_living_story import provider  # noqa: F401 - fixture
from tests.test_wpl6_rhythm import _queue
from tests.wp93_briefs import PASSE_COMPOSE_ID, engine_brief, engine_draft, without_page

DICE = DayShapeInputs(user_id="learner-wp93", local_date=date(2026, 9, 29))


def _plan(budget: int, scenario=None, **extra):
    return planner.plan_journey(
        scenario=scenario or engine_brief(),
        candidates=_queue(rhythm_caps(budget).candidate_limit),
        budget_seconds=budget,
        practice=True,
        dice=DICE,
        day_shape=extra.pop("day_shape", DayShape.STANDARD),
        **extra,
    )


def _relecture(**overrides) -> dict:
    draft = engine_draft()
    offer = {
        "variant": "relecture",
        "title_fr": "Hier au Mistral",
        "scene_id": str(uuid.uuid4()),
        "status": "ready",
        "audio_available": False,
        "texts_fr": planner.page_texts(draft["panels"]),
        "panel_count": len(draft["panels"]),
    }
    offer.update(overrides)
    return offer


# ---------------------------------------------------------------------------
# 1. The page is priced by what is on it
# ---------------------------------------------------------------------------


def test_the_page_is_priced_by_its_panels_lines_and_audio() -> None:
    kwargs = {"spt": planner.DEFAULT_SECONDS_PER_TOKEN, "multiplier": 1.0}
    paged = planner.scene_seconds(engine_brief(), **kwargs)
    pageless = planner.scene_seconds(without_page(engine_brief()), **kwargs)
    heard = planner.scene_seconds(engine_brief(), audio=True, **kwargs)
    # Five panels and eight lines are read, not glanced at (the 39 s of W-§3).
    # WP-128: a glance is 3 s a panel and 1 s a line now; the words are read.
    assert paged >= 100 > pageless
    assert heard > paged
    # A page-less (legacy) brief keeps the pre-WP-93 price exactly.
    assert planner.scene_seconds(_brief(), **kwargs) == planner.scene_seconds(
        _brief(), audio=True, **kwargs
    )
    # The authored page counts too.
    authored = _brief(panels=list(engine_draft()["panels"]))
    assert planner.scene_seconds(authored, **kwargs) > planner.scene_seconds(_brief(), **kwargs)


# ---------------------------------------------------------------------------
# 2. W5 — never interrupt a question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", RHYTHM_BUDGETS)
@pytest.mark.parametrize(
    "shape", [DayShape.STANDARD, DayShape.LISTENING, DayShape.REPRISE, DayShape.SHORT]
)
@pytest.mark.parametrize("audio", [False, True])
def test_the_reply_answers_the_scene_question_next(budget, shape, audio) -> None:
    for scenario in (engine_brief(), _brief()):
        plan = _plan(budget, scenario, day_shape=shape, audio_available=audio)
        plan.validate()
        kinds = [step.kind for step in plan.steps]
        assert kinds.index(StepKind.RESPOND) == kinds.index(StepKind.SCENE) + 1, kinds


def test_the_validator_refuses_an_item_between_the_question_and_the_reply() -> None:
    plan = _plan(600)
    kinds = [step.kind for step in plan.steps]
    scene_at = kinds.index(StepKind.SCENE)
    after = next(i for i, kind in enumerate(kinds) if i > scene_at + 1 and kind is StepKind.RECALL)
    moved = [*plan.steps]
    item = moved.pop(after)
    moved.insert(scene_at + 1, item)
    moved = [replace(step, ordinal=index) for index, step in enumerate(moved)]
    with pytest.raises(ValueError, match="between the scene and the reply"):
        replace(plan, steps=moved).validate()


def test_day_one_never_drills_the_taste_words_and_waits_for_the_reply() -> None:
    taste = [
        _candidate(identifier=f"t{i}", label_fr=word, label_native=gloss, is_new=True, relevance=1.0)
        for i, (word, gloss) in enumerate(
            [("un café", "a coffee"), ("s'il vous plaît", "please"), ("bonjour", "hello"), ("merci", "thanks")]
        )
    ]
    fresh = _candidate(
        identifier="n1", label_fr="au comptoir", label_native="at the counter", is_new=True, relevance=1.0
    )
    plan = planner.plan_journey(
        scenario=_brief(), candidates=[*taste, fresh], first_day=True, budget_seconds=600
    )
    plan.validate()
    drilled = [step.target.label_fr for step in plan.steps if step.kind is StepKind.RECALL]
    assert drilled == ["au comptoir"]
    kinds = [step.kind for step in plan.steps]
    # The day-1 word is a warm-up, before the page that ends on the question.
    assert kinds == [StepKind.RECALL, StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION]
    assert "taste word" in plan.rationale


# ---------------------------------------------------------------------------
# 3. Recall cap and input floor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("budget", "cap"), [(300, 6), (600, 12), (1200, 20), (1800, 28)])
def test_recall_is_capped_per_rhythm(budget: int, cap: int) -> None:
    assert rhythm_caps(budget).max_recall == cap
    for scenario in (engine_brief(), _brief()):
        assert planner.recall_count(_plan(budget, scenario)) <= cap


def test_drills_never_take_the_input_floor_on_a_paged_day() -> None:
    for budget in RHYTHM_BUDGETS:
        plan = _plan(budget)
        # WP-128: the reply is a conversation — input and output — not a drill;
        # at A1 it is half the day, so the drills are counted as what they are.
        drills = sum(
            step.estimated_seconds
            for step in plan.steps
            if step.kind is StepKind.RECALL and not (step.public_prompt or {}).get("audio_url")
        )
        assert drills <= round(0.65 * budget), (budget, drills, plan.rationale)


# ---------------------------------------------------------------------------
# 4. Engine days pose from the scene's lexicon (WP-68 L-1)
# ---------------------------------------------------------------------------


def test_engine_day_choices_and_word_banks_come_from_the_scene() -> None:
    brief = engine_brief()
    lexicon = {entry["surface_fr"] for entry in engine_draft()["lexicon"]}
    affordances = planner._affordances_for(brief)
    assert lexicon <= set(affordances)
    assert "un chocolat chaud" not in affordances, "no phrases from another scene"
    key = _candidate(identifier="k", label_fr="la clé", label_native="the key")
    choice = planner.build_recall_task(
        target=key.target, scenario=brief, affordances=affordances, optional=False
    )
    assert choice is not None and choice.task_type == "choice"
    assert {o["text_fr"] for o in choice.options} <= set(affordances)
    bank = planner.build_word_bank_task(
        target=_candidate(identifier="p", label_fr="dans ta poche", label_native="in your pocket").target,
        affordances=affordances,
        optional=False,
        control_language="en",
    )
    assert bank is not None
    story_words = {w.casefold() for phrase in affordances for w in phrase.split()}
    extras = [o["text_fr"] for o in bank.options if o["id"].startswith("chip_")]
    assert extras and all(word.casefold() in story_words for word in extras)
    # An authored scene keeps its authored phrases.
    assert "un chocolat chaud" in planner._affordances_for(_brief())


# ---------------------------------------------------------------------------
# 5. «Lecture» — the READ step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", [1200, 1800])
def test_a_long_rhythm_plans_one_optional_lecture_after_the_ending(budget: int) -> None:
    plan = _plan(budget, reading=_relecture())
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert kinds.count(StepKind.READ) == 1 and kinds[-1] is StepKind.READ
    # WP-109: the practice after the ending, then the «Lecture».
    assert all(kind is StepKind.RECALL for kind in kinds[kinds.index(StepKind.RESOLUTION) + 1 : -1])
    read = plan.steps[-1]
    assert read.optional and read.private_task is None
    prompt = ReadPrompt.model_validate(read.public_prompt)
    assert prompt.variant == "relecture" and prompt.status == "ready" and prompt.scene_id
    assert plan.estimated_active_seconds <= budget


@pytest.mark.parametrize("budget", [300, 600])
def test_shorter_rhythms_never_plan_a_lecture(budget: int) -> None:
    plan = _plan(budget, reading=_relecture())
    assert StepKind.READ not in [step.kind for step in plan.steps]


def test_coulisses_is_planned_writing_and_priced_as_todays_page() -> None:
    plan = _plan(1200, reading={"variant": "coulisses", "title_fr": "La clé oubliée"})
    read = plan.steps[-1]
    prompt = ReadPrompt.model_validate(read.public_prompt)
    assert (prompt.variant, prompt.status, prompt.scene_id) == ("coulisses", "writing", None)
    page = engine_draft()["panels"]
    assert read.estimated_seconds >= planner.page_seconds(
        planner.page_texts(page), panels=len(page), spt=planner.DEFAULT_SECONDS_PER_TOKEN,
        multiplier=1.0, audio=False,
    )


def test_the_validator_keeps_the_lecture_single_optional_and_last() -> None:
    plan = _plan(1200, reading=_relecture())
    read = plan.steps[-1]
    with pytest.raises(ValueError, match="optional"):
        replace(plan, steps=[*plan.steps[:-1], replace(read, optional=False)]).validate()
    early = [*plan.steps[:-2], read, plan.steps[-2]]
    early = [replace(step, ordinal=index) for index, step in enumerate(early)]
    with pytest.raises(ValueError, match="resolution|after the ending|comes last|follow the ending"):
        replace(plan, steps=early).validate()
    twice = [*plan.steps, replace(read, ordinal=len(plan.steps))]
    with pytest.raises(ValueError, match="at most 1"):
        replace(plan, steps=twice).validate()
    classic = [s for s in plan.steps if s.kind not in (StepKind.RECALL, StepKind.RULE)]
    classic = [replace(step, ordinal=index) for index, step in enumerate(classic)]
    with pytest.raises(ValueError, match="practice day|end with the resolution"):
        replace(plan, practice=False, steps=classic).validate()


# ---------------------------------------------------------------------------
# 6. WP-92 — the rule card carries today's line
# ---------------------------------------------------------------------------


def test_the_rule_card_quotes_the_scene_line_that_uses_the_unit() -> None:
    unit = {"concept_id": PASSE_COMPOSE_ID, "external_id": "fr.a1.passe-compose"}
    line, speaker = planner.rule_scene_example(unit, engine_brief())
    assert line == "Hier, [tu as laissé] ton parapluie ici."
    assert speaker == "margaux_barman"
    # As the engine keeps them before binding: in the story context's
    # «grammar» outcome, keyed "<panel>:<line>".
    bare = engine_draft()
    for panel in bare["panels"]:
        for entry in panel["dialogue"]:
            entry.pop("grammar_marks", None)
    context = engine_brief(draft=bare).story_context
    outcome = {"grammar": {"marks": {"2:0": [{"unit_id": str(PASSE_COMPOSE_ID), "start": 6, "end": 18}]}},
               "words": {"placed": ["sac"], "recycled": ["croissant", "verre"]}}
    staged = replace(engine_brief(draft=bare), story_context={**context, **outcome})
    assert planner.rule_scene_example(unit, staged) == (
        "Hier, [tu as laissé] ton parapluie ici.", "margaux_barman"
    )
    assert planner.scene_reuse(staged) == (2, 2)  # «croissant», «verre» are printed
    # Without marks, the unit's detector finds the use (and marks it).
    draft = engine_draft()
    for panel in draft["panels"]:
        for entry in panel["dialogue"]:
            entry.pop("grammar_marks", None)
    detector = {"concept_id": 7, "detectors": [r"\bavez vu\b"]}
    line, speaker = planner.rule_scene_example(detector, engine_brief(draft=draft))
    assert line == "Vous [avez vu] ma clé, peut-être ?" and speaker == "lila_bonnet"
    # None when the scene holds no use of the unit; narration never counts.
    assert planner.rule_scene_example({"concept_id": 9}, engine_brief()) == (None, None)
    step = planner._rule_step(
        0,
        brief={"concept_id": PASSE_COMPOSE_ID, "title_fr": "Le passé composé"},
        card={"example": {"fr": "J'[ai mangé]."}, "rule": {"en": "avoir + participle"}},
        cost=30,
        scenario=engine_brief(),
    )
    prompt = RulePrompt.model_validate(step.public_prompt)
    assert prompt.scene_example_fr == "Hier, [tu as laissé] ton parapluie ici."
    assert prompt.scene_example_speaker == "margaux_barman"


def test_reuse_is_measured_on_the_page() -> None:
    asked, found = planner.scene_reuse(engine_brief())
    assert asked == 4 and found >= 2  # «parapluie», «croissant» are printed
    assert planner.scene_reuse(_brief()) == (0, 0)


# ---------------------------------------------------------------------------
# 7. The READ step through the API: «coulisses» and the episode door
# ---------------------------------------------------------------------------


def _soutenu_day(client, db, monkeypatch, *, coulisses_on: bool):
    from app.services import coulisses

    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_COULISSES_ENABLED", coulisses_on)
    jobs: list = []
    monkeypatch.setattr(coulisses, "dispatcher", jobs.append)
    email = f"wp93-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(client, email)
    user = db.get(User, learner_id(db, email))
    user.daily_goal_minutes = 20
    db.commit()
    driver = Driver(client, headers, db=db)
    journey = driver.create()
    return driver, journey, user, jobs


def _read(journey: dict) -> dict | None:
    return next((step for step in journey["steps"] if step["kind"] == "read"), None)


def _store_coulisses(db, *, user, journey_id: str, scene: GraphicNovelScene) -> GraphicNovelScene:
    from app.services import coulisses

    page = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=scene.serial_thread_id,
        title="Du côté de Marin",
        brief="Marin cherche aussi.",
        status="available",
        cadence=coulisses.CADENCE,
        source_snapshot={
            "coulisses_for": str(scene.id),
            "journey_id": journey_id,
            "story_engine": ENGINE_VERSION,
            "pov_character_id": "marin_leveque",
        },
        script_payload={"title": "Du côté de Marin", "coulisses": True},
        cache_key=coulisses.cache_key(journey_id),
        prompt_version=coulisses.COULISSES_VERSION,
        image_model="existing-setting-art",
        image_quality="reference",
    )
    db.add(page)
    db.flush()
    page.panels.append(
        GraphicNovelPanel(
            panel_index=0,
            title="1",
            beat="Marin regarde sous la table.",
            image_prompt="Marin under the table.",
            image_url=None,
            overlay_payload={
                "narration_fr": "Marin regarde sous la table.",
                "dialogue": [{"character_id": "marin_leveque", "text_fr": "Elle perd tout, Lila."}],
            },
        )
    )
    db.commit()
    return page


def test_a_soutenu_story_day_asks_for_coulisses_and_projects_it(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
) -> None:
    driver, journey, user, jobs = _soutenu_day(
        assembled_client, db_session, monkeypatch, coulisses_on=True
    )
    assert journey["budget_seconds"] == 1200
    read = _read(journey)
    assert read is not None, [step["kind"] for step in journey["steps"]]
    kinds = [step["kind"] for step in journey["steps"]]
    assert kinds[-1] == "read" and kinds[-2] == "resolution"
    assert kinds.index("respond") == kinds.index("scene") + 1
    prompt = ReadPrompt.model_validate(read["prompt"])
    assert (prompt.variant, prompt.status, prompt.scene_id) == ("coulisses", "writing", None)
    assert prompt.character_id is None
    assert len(jobs) == 1, "requested at bind time, dispatched after the commit"

    db_session.expire_all()
    scene = db_session.scalar(
        select(GraphicNovelScene).where(
            GraphicNovelScene.user_id == user.id,
            GraphicNovelScene.prompt_version == ENGINE_VERSION,
        )
    )
    page = _store_coulisses(db_session, user=user, journey_id=journey["id"], scene=scene)
    fresh = assembled_client.get(
        f"/api/v1/daily-journeys/{journey['id']}", headers=driver.headers
    ).json()
    prompt = ReadPrompt.model_validate(_read(fresh)["prompt"])
    assert (prompt.status, prompt.scene_id) == ("ready", str(page.id))
    assert prompt.character_id == "marin_leveque"
    assert prompt.title_fr == "Du côté de Marin"

    # The page opens through the episode door, for its owner only.
    opened = assembled_client.get(
        f"/api/v1/story-engine/episodes/{page.id}", headers=driver.headers
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["panels"] and body["panels"][0]["dialogue"][0]["text_fr"] == "Elle perd tout, Lila."
    assert "grammar_focus" in body
    stranger = register(assembled_client, f"wp93-other-{uuid.uuid4().hex[:8]}@example.com")
    assert assembled_client.get(
        f"/api/v1/story-engine/episodes/{page.id}", headers=stranger
    ).status_code == 404
    # Still not a day's episode in the list.
    listed = assembled_client.get("/api/v1/story-engine/episodes", headers=driver.headers).json()
    assert str(page.id) not in [item["id"] for item in listed["episodes"]]

    # The line-audio door speaks the page's lines on the READ step, nothing else.
    from app.services.line_audio import match_line, step_lines

    stored = db_session.get(DailyJourney, uuid.UUID(journey["id"]))
    read_step = next(step for step in stored.steps if step.kind == "read")
    lines = step_lines(db_session, stored, read_step)
    assert match_line(lines, "Elle perd tout, Lila.") is not None
    assert match_line(lines, "Dis quelque chose d'autre.") is None


def test_with_coulisses_off_the_lecture_is_yesterdays_page_or_nothing(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
) -> None:
    driver, journey, user, jobs = _soutenu_day(
        assembled_client, db_session, monkeypatch, coulisses_on=False
    )
    # Day one of the story: no yesterday, no «coulisses» — no «Lecture».
    assert _read(journey) is None
    assert jobs == []


def test_the_relecture_offer_reads_yesterdays_page(db_session, monkeypatch) -> None:
    from app.services.daily_journey import DailyJourneyService

    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_COULISSES_ENABLED", False)
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@wp93.test", hashed_password="x",
        native_language="en", target_language="fr",
    )
    db_session.add(user)
    db_session.flush()
    yesterday = GraphicNovelScene(
        user_id=user.id, title="La clé oubliée", brief="x", status="completed",
        source_snapshot={"journey_id": str(uuid.uuid4())}, script_payload={},
        cache_key=f"wp93-{uuid.uuid4().hex[:12]}", prompt_version=ENGINE_VERSION,
        image_model="m", image_quality="reference",
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(yesterday)
    db_session.flush()
    yesterday.panels.append(
        GraphicNovelPanel(
            panel_index=0, title="1", beat="b", image_prompt="p",
            overlay_payload={"narration_fr": "Il pleut.", "dialogue": [
                {"character_id": "lila_bonnet", "text_fr": "Ma clé !"}]},
        )
    )
    db_session.flush()
    journey = DailyJourney(
        id=uuid.uuid4(), user_id=user.id, local_date=date(2026, 9, 29), timezone="UTC",
        status="active", budget_seconds=1200,
    )
    service = DailyJourneyService(db_session, adapters=None)  # type: ignore[arg-type]
    [offer] = service._reading_for_today(user, journey, engine_brief())
    assert offer["variant"] == "relecture" and offer["scene_id"] == str(yesterday.id)
    assert offer["texts_fr"] == ["Il pleut.", "Ma clé !"] and offer["panel_count"] == 1
    journey.budget_seconds = 600
    assert service._reading_for_today(user, journey, engine_brief()) == []
    # Intensif reads two pages: yesterday's and the one before.
    before = GraphicNovelScene(
        user_id=user.id, title="Le parapluie", brief="x", status="completed",
        source_snapshot={"journey_id": str(uuid.uuid4())}, script_payload={},
        cache_key=f"wp93-{uuid.uuid4().hex[:12]}", prompt_version=ENGINE_VERSION,
        image_model="m", image_quality="reference",
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.add(before)
    db_session.flush()
    before.panels.append(
        GraphicNovelPanel(panel_index=0, title="1", beat="b", image_prompt="p",
                          overlay_payload={"narration_fr": "Il fait beau.", "dialogue": []})
    )
    db_session.flush()
    journey.budget_seconds = 1800
    offers = service._reading_for_today(user, journey, engine_brief())
    assert [offer["scene_id"] for offer in offers] == [str(yesterday.id), str(before.id)]
    db_session.rollback()


# ---------------------------------------------------------------------------
# 8. The word biography: «revu dans l'épisode du …»
# ---------------------------------------------------------------------------


def test_the_word_biography_lists_the_pages_that_brought_it_back(
    assembled_client, db_session, journey_enabled, clock
) -> None:
    email = f"wp93-bio-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    user_id = learner_id(db_session, email)
    word = VocabularyWord(
        language="fr", word="le parapluie", normalized_word="le parapluie",
        english_translation="the umbrella",
    )
    db_session.add(word)
    journey_id = uuid.uuid4()
    db_session.add(
        DailyJourney(
            id=journey_id, user_id=user_id, local_date=date(2026, 9, 12), timezone="Europe/Paris",
            status="completed", budget_seconds=600,
        )
    )
    for title, lemmas, key in (
        ("La clé oubliée", {"recycled_lemmas": ["parapluie", "pluie"]}, str(journey_id)),
        ("Sans parapluie", {"placed_lemmas": ["verre"]}, None),
    ):
        db_session.add(
            GraphicNovelScene(
                user_id=user_id, title=title, brief="x", status="completed",
                source_snapshot={"journey_id": key} if key else {}, script_payload=lemmas,
                cache_key=f"wp93-bio-{uuid.uuid4().hex[:12]}", prompt_version=ENGINE_VERSION,
                image_model="m", image_quality="reference",
            )
        )
    db_session.commit()
    response = assembled_client.get(f"/api/v1/vocabulary/{word.id}/biography", headers=headers)
    assert response.status_code == 200, response.text
    revisits = response.json()["revisited_in"]
    assert revisits == [
        {"date": "2026-09-12", "scene_title_fr": "La clé oubliée", "scene_id": revisits[0]["scene_id"]}
    ]


def test_the_line_audio_door_speaks_the_rule_cards_scene_line_only() -> None:
    from types import SimpleNamespace

    from app.services.line_audio import match_line, step_lines

    rule = SimpleNamespace(
        kind="rule",
        public_prompt={
            "scene_example_fr": "Hier, [tu as laissé] ton parapluie ici.",
            "scene_example_speaker": "margaux_barman",
        },
        private_task={},
    )
    lines = step_lines(None, SimpleNamespace(steps=[]), rule)  # type: ignore[arg-type]
    hit = match_line(lines, "Hier, tu as laissé ton parapluie ici.")
    assert hit is not None and hit.character_id == "margaux_barman"
    assert match_line(lines, "Un autre texte.") is None
    other = SimpleNamespace(kind="forge", public_prompt={"title_fr": "Le passé composé"}, private_task={})
    assert step_lines(None, SimpleNamespace(steps=[]), other) == []  # type: ignore[arg-type]


@pytest.mark.parametrize("audio", [False, True])
def test_intensif_reads_two_pages_and_hears_more(audio: bool) -> None:
    offers = [
        {"variant": "coulisses", "title_fr": "Coulisses"},
        _relecture(),
        _relecture(title_fr="Avant-hier"),
    ]
    # As production folds it on Intensif (WP-S4): its real minutes count.
    forge = {"concept_id": None, "reserve_seconds": 240, "max_seconds": 600}
    plan = _plan(1800, reading=offers, audio_available=audio, forge=forge)
    plan.validate()
    assert any(step.kind is StepKind.FORGE for step in plan.steps)
    reads = [step for step in plan.steps if step.kind is StepKind.READ]
    assert [step.public_prompt["variant"] for step in reads] == ["coulisses", "relecture"]
    assert [step.kind for step in plan.steps[-2:]] == [StepKind.READ, StepKind.READ]
    heard = sum(1 for step in plan.steps if is_heard_step(step))
    drills = planner.recall_count(plan) - heard
    assert drills <= rhythm_caps(1800).max_recall
    if audio:
        # Heard items may pass the ceiling: listening is input.
        assert heard > planner.LISTEN_TAP_ITEMS_BY_BUDGET[1800]
        assert plan.estimated_active_seconds >= 0.9 * 1800, plan.rationale
    one = _plan(1200, reading=offers, audio_available=audio)
    assert [s.public_prompt["variant"] for s in one.steps if s.kind is StepKind.READ] == ["coulisses"]


def test_the_preview_states_the_planned_minutes() -> None:
    assert planner.expected_day_seconds(1800) < 1800
    assert planner.expected_day_seconds(1800, [1500, 1700, 1600]) == 1600
    assert planner.expected_day_seconds(300) <= 300


def test_an_unavailable_coulisses_gives_its_place_to_yesterdays_page(db_session, monkeypatch) -> None:
    from app.db.models.daily_journey import DailyJourneyStep
    from app.services.daily_journey import DailyJourneyService

    monkeypatch.setattr(settings, "ATELIER_COULISSES_ENABLED", False)
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@wp93.test", hashed_password="x",
        native_language="en", target_language="fr",
    )
    db_session.add(user)
    db_session.flush()
    yesterday = GraphicNovelScene(
        user_id=user.id, title="La clé oubliée", brief="x", status="completed",
        source_snapshot={}, script_payload={}, cache_key=f"wp93-{uuid.uuid4().hex[:12]}",
        prompt_version=ENGINE_VERSION, image_model="m", image_quality="reference",
    )
    db_session.add(yesterday)
    db_session.flush()
    journey = DailyJourney(
        id=uuid.uuid4(), user_id=user.id, local_date=date(2026, 9, 29), timezone="UTC",
        status="active", budget_seconds=1800,
    )
    relecture = {"scene_id": str(yesterday.id), "title_fr": "La clé oubliée"}

    def read_step(ordinal: int, variant: str) -> DailyJourneyStep:
        return DailyJourneyStep(
            id=uuid.uuid4(), ordinal=ordinal, kind="read", status="pending",
            estimated_seconds=150, optional=True,
            public_prompt={"variant": variant, "title_fr": "t", "scene_id": None,
                           "status": "writing", "audio_available": False},
            private_task={"variant": variant, "relectures": [relecture],
                          **({"relecture": relecture} if variant == "relecture" else {})},
            assistance_used=[],
        )

    first, second = read_step(8, "coulisses"), read_step(9, "relecture")
    journey.steps = [first, second]
    views = DailyJourneyService(db_session, adapters=None)._read_views(journey)  # type: ignore[arg-type]
    # Relecture first; the second page has nothing left to show.
    assert ReadPrompt.model_validate(views[first.id]).model_dump() == {
        "variant": "relecture", "title_fr": "La clé oubliée", "scene_id": str(yesterday.id),
        "status": "ready", "audio_available": False, "character_id": None, "character_name": None,
    }
    assert views[second.id]["status"] == "unavailable" and views[second.id]["scene_id"] is None
    db_session.rollback()


def test_nothing_sits_between_the_reply_and_the_ending() -> None:
    """WP-109 «Une seule maison»: the episode is never interrupted — practice wraps it,
    before the scene and after the ending."""

    plan = _plan(600)
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    respond_at = kinds.index(StepKind.RESPOND)
    assert kinds[respond_at + 1] is StepKind.RESOLUTION
    after = kinds.index(StepKind.RECALL, respond_at)
    steps = list(plan.steps)
    item = steps.pop(after)
    steps.insert(respond_at + 1, item)
    steps = [replace(step, ordinal=index) for index, step in enumerate(steps)]
    with pytest.raises(ValueError, match="between the reply and the ending"):
        replace(plan, steps=steps).validate()
