# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-78 — «Une vraie journée de pratique».

The median day holds at least six graded interactions — quick recall items
around the one open reply — and still fits the minutes it states. The three new
formats (matching pairs, listen-and-tap read-and-tap, unscramble) render on the
wire, grade on the server, and carry a key the device can grade them with. A
word tapped in the story can be kept: a learner-scoped Lexique entry with its
sentence and its gloss, which the next day's plan brings back.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas.daily_journey import RecallPrompt
from app.services import journey_learning
from app.services import journey_planner as planner
from app.services.journey_answer_key import answer_key_for, answer_matches_key
from app.services.journey_contracts import (
    MAX_WARMUP_RECALL_STEPS,
    AssistanceLevel,
    AttemptAnswer,
    DayShape,
    InputMode,
    PlannedJourney,
    StepKind,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_day_shapes import DayShapeInputs
from app.services.kept_words import KEPT_INTERACTION_TYPE, kept_words_for
from tests.test_journey_end_to_end import (
    Clock,  # noqa: F401 - fixture type
    Driver,
    assembled_client,  # noqa: F401 - fixture
    clock,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    leaked_keys,
    learner_id,
    register,
    seed_due_vocabulary,
)
from tests.test_journey_planner import ANSWER_KEY_MARKERS, _brief, _candidate

#: What a real queue holds a few weeks in: nouns with their article, phrases
#: that tutoient or vouvoient, multi-word phrases, bare words.
QUEUE = (
    ("un café", "a coffee"),
    ("la clé", "the key"),
    ("tu viens demain", "you are coming tomorrow"),
    ("vous partez déjà", "you are leaving already"),
    ("à tout à l'heure", "see you shortly"),
    ("brouillard", "fog"),
    ("le zinc", "the counter"),
)


def _queue() -> list:
    return [
        _candidate(identifier=f"w{index}", label_fr=fr, label_native=native, priority=10 - index)
        for index, (fr, native) in enumerate(QUEUE)
    ]


def _dice(user: str = "learner-a") -> DayShapeInputs:
    return DayShapeInputs(user_id=user, local_date=datetime(2026, 9, 21).date())


def _graded(plan: PlannedJourney) -> int:
    return planner.graded_interactions(plan)


# ---------------------------------------------------------------------------
# 1. The planner: ≥ 6 graded interactions, inside the stated minutes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_a_practice_day_has_six_graded_interactions_inside_its_minutes(band, language) -> None:
    plan = planner.plan_journey(
        scenario=_brief(level_band=band, control_language=language),
        candidates=_queue(),
        practice=True,
        dice=_dice(),
        day_shape=DayShape.STANDARD,
    )
    plan.validate()
    assert plan.practice is True
    assert _graded(plan) >= 6, plan.rationale
    # The stated minutes are the estimate, and the estimate is the whole day.
    assert plan.estimated_active_seconds == sum(step.estimated_seconds for step in plan.steps)
    assert plan.estimated_active_seconds <= plan.budget_seconds == 300

    kinds = [step.kind for step in plan.steps]
    scene_at = kinds.index(StepKind.SCENE)
    respond_at = kinds.index(StepKind.RESPOND)
    assert 2 <= scene_at <= MAX_WARMUP_RECALL_STEPS, "two or three warm-ups before the scene"
    assert 1 <= respond_at - scene_at - 1 <= 2, "one or two items between scene and reply"
    assert kinds[respond_at + 1] is StepKind.RECALL, "one word from today after the reply"
    assert kinds[-1] is StepKind.RESOLUTION
    for step in plan.steps:
        serialized = json.dumps(step.public_prompt, ensure_ascii=False, default=str)
        for marker in ANSWER_KEY_MARKERS:
            assert marker not in serialized, f"{step.kind} leaks {marker}"
        if step.kind is StepKind.RECALL:
            RecallPrompt.model_validate(step.public_prompt)
    quick = [step.public_prompt["task_type"] for step in plan.steps if step.kind is StepKind.RECALL]
    assert len(set(quick)) >= 4, f"a mix, not one format five times: {quick}"


def test_the_median_of_a_month_of_practice_days_holds_six() -> None:
    counts = []
    for day in range(28):
        dice = DayShapeInputs(
            user_id="learner-b", local_date=(datetime(2026, 9, 1) + timedelta(days=day)).date()
        )
        plan = planner.plan_journey(
            scenario=_brief(), candidates=_queue(), practice=True, dice=dice,
            day_shape=DayShape.STANDARD,
        )
        assert plan.estimated_active_seconds <= plan.budget_seconds
        counts.append(_graded(plan))
    counts.sort()
    assert counts[len(counts) // 2] >= 6, counts


def test_quick_items_are_priced_at_ten_seconds_or_so_not_a_constant() -> None:
    plan = planner.plan_journey(
        scenario=_brief(), candidates=_queue(), practice=True, dice=_dice()
    )
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    for step in recalls:
        assert step.estimated_seconds <= 18, (step.public_prompt["task_type"], step.estimated_seconds)
    # A slower measured pace costs more seconds, never a made-up minute count.
    slow = planner.plan_journey(
        scenario=_brief(),
        candidates=_queue(),
        practice=True,
        dice=_dice(),
        pace=planner.PacingProfile(0.70, 1.35, 40),
    )
    assert slow.estimated_active_seconds <= slow.budget_seconds
    assert _graded(slow) >= 3


def test_practice_off_is_the_classic_day_byte_for_byte() -> None:
    classic = planner.plan_journey(scenario=_brief(), candidates=_queue())
    again = planner.plan_journey(scenario=_brief(), candidates=_queue(), practice=False)
    assert classic == again
    assert classic.practice is False
    assert classic.steps[0].kind is StepKind.SCENE


def test_a_short_day_stays_short_and_the_first_day_is_untouched() -> None:
    short = planner.plan_journey(
        scenario=_brief(), candidates=_queue(), practice=True, day_shape=DayShape.SHORT
    )
    assert [step.kind for step in short.steps] == [
        StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION
    ]
    first = planner.plan_journey(
        scenario=_brief(), candidates=_queue()[:2], practice=True, first_day=True
    )
    assert first.practice is False and first.steps[0].kind is StepKind.SCENE


def test_a_listening_day_poses_nothing_before_the_scene_and_only_dictation() -> None:
    from app.services.journey_contracts import DICTATION_RECALL_FORMATS

    plan = planner.plan_journey(
        scenario=_brief(), candidates=_queue(), practice=True,
        day_shape=DayShape.LISTENING, audio_available=True, dice=_dice(),
    )
    if plan.day_shape is DayShape.LISTENING:
        assert plan.steps[0].kind is StepKind.SCENE
        for step in plan.steps:
            if step.kind is StepKind.RECALL:
                assert step.public_prompt["task_type"] in DICTATION_RECALL_FORMATS


def test_an_unscramble_never_comes_before_the_scene_nor_spells_the_reply() -> None:
    plan = planner.plan_journey(
        scenario=_brief(), candidates=_queue(), practice=True, dice=_dice()
    )
    scene_at = [step.kind for step in plan.steps].index(StepKind.SCENE)
    respond_at = [step.kind for step in plan.steps].index(StepKind.RESPOND)
    suggested = plan.scenario.response_task.suggested_response_fr
    from app.services.journey_content import line_spoils_reply

    for index, step in enumerate(plan.steps):
        if step.kind is StepKind.RECALL and step.private_task.task_type == "unscramble":
            assert index > scene_at
            if index < respond_at:
                assert not line_spoils_reply(step.private_task.solution_fr, suggested)
    # And the contract refuses the other order outright.
    warm = next(step for step in plan.steps if step.kind is StepKind.RECALL)
    task = planner.build_unscramble_task(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="z", label_fr="le zinc"),
        sentences=planner.scene_sentences(plan.scenario.setup_fr),
        optional=False,
        control_language="en",
    )
    assert task is not None
    bad = replace(plan, steps=[replace(plan.steps[0], private_task=task), *plan.steps[1:]])
    assert warm.ordinal == 0
    with pytest.raises(ValueError, match="unscramble"):
        bad.validate()


# ---------------------------------------------------------------------------
# 2. The three formats grade on the server and on the device
# ---------------------------------------------------------------------------

POOL = [
    TargetRef(kind=TargetKind.VOCABULARY, id=f"p{index}", label_fr=fr, label_native=native)
    for index, (fr, native) in enumerate(QUEUE)
]


def _evaluate(task, **answer):
    return journey_learning.evaluate_recall(
        None,  # type: ignore[arg-type]
        user=None,  # type: ignore[arg-type]
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", **answer),
        assistance=AssistanceLevel.NONE,
    )


def test_matching_pairs_grades_the_target_on_its_first_pairing() -> None:
    task = planner.build_match_pairs_task(
        target=POOL[0], pool=POOL, optional=False, control_language="en"
    )
    assert task is not None and len(task.options) == 8
    assert {option["side"] for option in task.options} == {"fr", "native"}
    order = task.correct_tile_order
    fr, native = order[0], order[1]
    assert _evaluate(task, tile_ids=list(order)).outcome is TaskOutcome.MET
    # Found by elimination after other mistakes: the target's own pairing was right.
    assert _evaluate(task, tile_ids=[order[2], order[5], *order]).outcome is TaskOutcome.MET
    # Tried against the wrong meaning first: not known.
    assert _evaluate(task, tile_ids=[fr, order[3], fr, native]).outcome is TaskOutcome.NOT_YET

    key = answer_key_for("step-1", {"task_type": "match_pairs", "correct_tile_order": order})
    assert key is not None and len(key["digests"]) == 4
    assert answer_matches_key(key, "match_pairs", tile_ids=[fr, native]) is True
    assert answer_matches_key(key, "match_pairs", tile_ids=[fr, order[3]]) is False
    # The digests do not say which pair is the target.
    assert key["digests"] == sorted(key["digests"])


def test_listen_tap_is_read_and_tap_without_audio_and_grades_by_id() -> None:
    task = planner.build_listen_tap_task(
        target=POOL[5], pool=POOL, optional=False, control_language="de"
    )
    assert task is not None
    assert task.prompt_fr == "brouillard"
    assert task.instruction_native == "Was bedeutet das?"
    assert all(option["side"] == "native" for option in task.options)
    assert "fog" in {option["text_fr"] for option in task.options}
    wrong = next(o["id"] for o in task.options if o["id"] != task.correct_option_id)
    assert _evaluate(task, option_id=task.correct_option_id).outcome is TaskOutcome.MET
    assert _evaluate(task, option_id=wrong).outcome is TaskOutcome.NOT_YET
    key = answer_key_for("s", {"task_type": "listen_tap", "correct_option_id": task.correct_option_id})
    assert answer_matches_key(key, "listen_tap", option_id=task.correct_option_id) is True
    assert answer_matches_key(key, "listen_tap", option_id=wrong) is False


def test_unscramble_rebuilds_the_scene_sentence_and_grades_by_order() -> None:
    sentences = planner.scene_sentences("Il pleut. « Margaux essuie le zinc. » Fin")
    assert "Margaux essuie le zinc." in sentences
    task = planner.build_unscramble_task(
        target=POOL[6], sentences=sentences, optional=False, control_language="en"
    )
    assert task is not None and task.solution_fr == "Margaux essuie le zinc."
    assert [tile["id"] for tile in task.options] != task.correct_tile_order
    assert _evaluate(task, tile_ids=list(task.correct_tile_order)).outcome is TaskOutcome.MET
    assert _evaluate(task, tile_ids=list(reversed(task.correct_tile_order))).outcome is TaskOutcome.NOT_YET
    key = answer_key_for("s", {"task_type": "unscramble", "correct_tile_order": task.correct_tile_order})
    assert answer_matches_key(key, "unscramble", tile_ids=task.correct_tile_order) is True


def test_a_quick_format_that_cannot_be_posed_honestly_is_not_posed() -> None:
    lonely = POOL[:2]
    assert planner.build_match_pairs_task(
        target=POOL[0], pool=lonely, optional=False, control_language="en"
    ) is None, "four pairs need four words"
    erratum = TargetRef(kind=TargetKind.ERROR, id="e1", label_fr="je suis allé", label_native="aux")
    assert planner.build_listen_tap_task(
        target=erratum, pool=POOL, optional=False, control_language="en"
    ) is None, "an erratum's explanation is not a gloss"
    assert planner.build_unscramble_task(
        target=POOL[5], sentences=["Il pleut."], optional=False, control_language="en"
    ) is None


# ---------------------------------------------------------------------------
# 3. Tap-to-keep
# ---------------------------------------------------------------------------


def _word(db: Session, word: str, english: str | None, **extra) -> VocabularyWord:
    row = VocabularyWord(
        language="fr", word=word, normalized_word=word.lower(),
        english_translation=english, difficulty_level=1, **extra,
    )
    db.add(row)
    db.commit()
    return row


def test_keep_writes_a_learner_scoped_entry_and_never_the_shared_row(
    assembled_client: TestClient, db_session: Session
) -> None:
    email = f"wp78-keep-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    other = register(assembled_client, f"wp78-other-{uuid.uuid4().hex[:8]}@example.com")
    # A word no other test creates: the suite shares one database, and with a
    # second «parapluie» row left by another suite (reversed file order) the
    # keep endpoint matched that row and this test found no progress on its own.
    word = _word(db_session, "ombrelle", "parasol")
    before = (word.example_sentence, word.english_translation, word.definition)

    sentence = "Romy secoue son ombrelle sur le seuil."
    response = assembled_client.post(
        "/api/v1/vocabulary/keep",
        headers=headers,
        json={"term": "ombrelle", "sentence": sentence, "surface": "ombrelle"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gloss"] == "parasol" and body["example_fr"] == sentence
    assert body["already_kept"] is False

    user_id = learner_id(db_session, email)
    rows = db_session.query(WordInteraction).filter(
        WordInteraction.user_id == user_id,
        WordInteraction.interaction_type == KEPT_INTERACTION_TYPE,
    ).all()
    assert len(rows) == 1 and rows[0].context_sentence == sentence
    progress = db_session.query(UserVocabularyProgress).filter_by(
        user_id=user_id, word_id=word.id
    ).one()
    assert progress.provenance == "kept_from_story" and progress.state == "new"
    db_session.refresh(word)
    assert (word.example_sentence, word.english_translation, word.definition) == before

    # Idempotent, and nobody else's Lexique.
    again = assembled_client.post(
        "/api/v1/vocabulary/keep", headers=headers,
        json={"term": "ombrelle", "sentence": sentence},
    )
    assert again.json()["already_kept"] is True
    other_id = db_session.query(User).filter(User.id != user_id).first().id
    assert kept_words_for(db_session, user_id=other_id) == [] or all(
        row.example_fr != sentence for row in kept_words_for(db_session, user_id=other_id)
    )
    assert other  # a second learner exists and kept nothing

    # The word biography shows the kept sentence with its meaning.
    bio = assembled_client.get(f"/api/v1/vocabulary/{word.id}/biography", headers=headers)
    assert bio.status_code == 200, bio.text
    examples = bio.json().get("examples") or []
    assert any(ex["sentence"] == sentence and ex["source"] == "story" for ex in examples)


def test_keep_refuses_a_word_it_cannot_gloss_in_the_learners_language(
    assembled_client: TestClient, db_session: Session
) -> None:
    headers = register(assembled_client, f"wp78-refuse-{uuid.uuid4().hex[:8]}@example.com")
    _word(db_session, "gouttière", None, german_translation="Dachrinne")
    missing = assembled_client.post(
        "/api/v1/vocabulary/keep", headers=headers,
        json={"term": "introuvablemot", "sentence": "Un introuvablemot."},
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "not_in_lexicon"
    foreign = assembled_client.post(
        "/api/v1/vocabulary/keep", headers=headers,
        json={"term": "gouttière", "sentence": "La gouttière déborde."},
    )
    assert foreign.status_code == 422
    assert foreign.json()["detail"]["code"] == "no_gloss_in_learner_language"
    assert db_session.query(VocabularyWord).filter_by(word="introuvablemot").count() == 0


def test_a_kept_word_comes_back_the_next_day_in_its_own_sentence(
    assembled_client: TestClient, db_session: Session
) -> None:
    email = f"wp78-next-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    user_id = learner_id(db_session, email)
    seed_due_vocabulary(db_session, user_id, QUEUE[:5])
    _word(db_session, "parapluie", "umbrella")
    sentence = "Romy secoue son parapluie sur le seuil."
    assert assembled_client.post(
        "/api/v1/vocabulary/keep", headers=headers,
        json={"term": "parapluie", "sentence": sentence},
    ).status_code == 200

    user = db_session.get(User, user_id)
    scenario = _brief()
    candidates = journey_learning.select_learning_candidates(
        db_session, user=user, scenario=scenario, limit=8
    )
    kept = [c for c in candidates if (c.metadata or {}).get("kept")]
    assert kept and kept[0].target.label_fr == "parapluie"
    assert kept[0].metadata["example_fr"] == sentence
    # The reply's obligations did not grow: a kept word the scene does not use
    # is practised, never required.
    plan = planner.plan_journey(
        scenario=scenario, candidates=candidates, practice=True, dice=_dice()
    )
    kept_steps = [
        step for step in plan.steps
        if step.kind is StepKind.RECALL and step.target and step.target.label_fr == "parapluie"
    ]
    assert kept_steps, plan.rationale
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert all(t["label_fr"] != "parapluie" for t in respond.public_prompt["targets"])
    posed = {step.private_task.task_type for step in kept_steps}
    assert posed & {"unscramble", "match_pairs", "listen_tap", "short_answer", "tiles"}
    unscrambles = [s for s in kept_steps if s.private_task.task_type == "unscramble"]
    for step in unscrambles:
        assert step.private_task.solution_fr == sentence


# ---------------------------------------------------------------------------
# 4. Through the real API: a practice day played end to end
# ---------------------------------------------------------------------------


def test_a_practice_day_is_played_end_to_end_without_leaking_a_key(
    assembled_client: TestClient, journey_enabled: None, clock, db_session: Session
) -> None:
    email = f"wp78-e2e-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    seed_due_vocabulary(db_session, learner_id(db_session, email), QUEUE)
    driver = Driver(assembled_client, headers, db=db_session)
    journey = driver.create(expect=(201,))
    assert journey["status"] == "active"
    kinds = [step["kind"] for step in journey["steps"]]
    graded = kinds.count("recall") + kinds.count("respond")
    assert graded >= 6, kinds
    # WP-L6: a new learner is on Régulier; the day fits its ten minutes.
    assert journey["estimated_active_seconds"] <= journey["budget_seconds"] == 600
    assert kinds[0] == "recall" and kinds[-1] == "resolution"
    for step in journey["steps"]:
        if step["kind"] == "recall" and step["prompt"]["task_type"] in {
            "match_pairs", "listen_tap", "unscramble"
        }:
            assert step["prompt"].get("answer_key"), "the device can grade it"
    results = driver.play(answer="Bonjour, je voudrais un café en terrasse, s'il vous plaît.")
    assert driver.journey["current_step_id"] is None
    verdicts = [r for r in results if r.get("task_outcome") and not r.get("pending")]
    assert len(verdicts) >= 6
    recall_met = [
        r for r in results[:-1] if r["task_outcome"] == "met"
    ]
    assert recall_met, "correct quick answers are graded met on the server"
    assert driver.finish("complete").status_code == 200
    assert not driver.private_leaks, driver.private_leaks
    assert not leaked_keys(driver.journey)


def test_a_thin_queue_borrows_context_cards_and_fragile_words_never_obligations(
    assembled_client: TestClient, db_session: Session
) -> None:
    """One due word still gets a matching grid: the other three cards are words
    the learner owns (no evidence, no schedule); a word about to come due is a
    fragile target (CONTRACTS §9) and fills the day."""

    email = f"wp78-thin-{uuid.uuid4().hex[:8]}@example.com"
    register(assembled_client, email)
    user_id = learner_id(db_session, email)
    seed_due_vocabulary(db_session, user_id, QUEUE[:1])
    studied = seed_due_vocabulary(db_session, user_id, QUEUE[1:5], overdue_days=-10)
    fragile = seed_due_vocabulary(db_session, user_id, QUEUE[5:6], overdue_days=-1)
    user = db_session.get(User, user_id)
    candidates = journey_learning.select_learning_candidates(
        db_session, user=user, scenario=_brief(), limit=8
    )
    partners = [c for c in candidates if (c.metadata or {}).get("partner_only")]
    assert {c.target.id for c in partners} >= {str(word.id) for word in studied}
    assert any((c.metadata or {}).get("fragile") and c.target.id == str(fragile[0].id) for c in candidates)

    plan = planner.plan_journey(
        scenario=_brief(), candidates=candidates, practice=True, dice=_dice()
    )
    partner_ids = {c.target.id for c in partners if not (c.metadata or {}).get("fragile")}
    for step in plan.steps:
        if step.target is not None:
            assert step.target.id not in partner_ids, "a context card is never a target"
    assert all(pid.split(":")[1] not in partner_ids for pid in plan.selected_target_ids)
    formats = [s.private_task.task_type for s in plan.steps if s.kind is StepKind.RECALL]
    assert len(formats) >= 4, formats
    due = next(c for c in candidates if c.target.label_fr == "un café")
    assert planner.build_match_pairs_task(
        target=due.target, pool=[c.target for c in partners], optional=False, control_language="en"
    ) is not None, "the owned words make a matching grid possible for one due word"
    # The classic day never sees the practice pool.
    classic = journey_learning.select_learning_candidates(
        db_session, user=user, scenario=_brief(), limit=3
    )
    assert not any((c.metadata or {}).get("partner_only") for c in classic)


def test_a_shape_that_could_not_be_built_is_not_dealt_straight_back() -> None:
    """The WP-68 finding: a listening day served as standard used to exclude
    only *standard* the next morning, so the dice dealt listening again."""

    from app.services.journey_day_shapes import choose_day_shape

    for offset in range(40):
        inputs = DayShapeInputs(
            user_id="learner-c",
            local_date=(datetime(2026, 1, 5) + timedelta(days=offset)).date(),
            previous_shape=DayShape.STANDARD,
            previous_dealt_shape=DayShape.LISTENING,
            audio_available=True,
            errata_count=1,
        )
        assert choose_day_shape(inputs).shape is DayShape.REPRISE
    # With nothing else left, yesterday's served standard day comes again
    # rather than the shape that just failed.
    lonely = DayShapeInputs(
        user_id="learner-c",
        local_date=datetime(2026, 1, 5).date(),
        previous_shape=DayShape.STANDARD,
        previous_dealt_shape=DayShape.LISTENING,
        audio_available=True,
    )
    assert choose_day_shape(lonely).shape is DayShape.STANDARD
