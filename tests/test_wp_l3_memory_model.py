"""WP-L3 · One memory model for everything.

1. grammar gets the vocabulary's FSRS-style memory (migration + seed formula);
2. one evidence → rating mapping, and every grammar credit path goes through
   one function;
3. errata are scheduled by the same model and still retire after three
   correct repairs on separate days;
4. one interleaved review queue for the day planner;
5. held items keep coming back, at least every 60 days;
6. a seeded 120-day learner simulation (the numbers are in the WP doc).
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from app.core.srs import memory
from app.core.srs.memory import (
    MAX_INTERVAL_DAYS,
    Evidence,
    EvidenceFormat,
    MemoryState,
    Rating,
    grade_evidence,
    seed_from_legacy,
)
from app.core.srs.simulation import simulate_learner
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import atelier_session_evidence
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_REPAIRING,
    ErrorMemoryService,
)
from app.services.grammar import GrammarService, apply_grammar_evidence
from app.services.journey_contracts import EvidenceKind, TargetKind, TargetRef
from app.services.journey_learning import JOURNEY_EVIDENCE, _apply_grammar_credit
from app.services.unified_srs import (
    RAPPEL_ITEM_SECONDS,
    DueLearningItem,
    ItemType,
    UnifiedSRSService,
    interleave_review_items,
    review_concept_key,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "d1f3a5c7e9b2_wpl3_grammar_memory.py"
NOW = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"wp-l3-{uuid4().hex}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language="en",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _concept(db_session, *, name: str = "Concept", source_refs: dict | None = None) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_WPL3_{uuid4().hex[:10]}",
        language="fr",
        name=f"{name} {uuid4().hex[:6]}",
        level="A1",
        category="Test",
        active=True,
        source_refs=source_refs or {},
    )
    db_session.add(concept)
    db_session.flush()
    return concept


def _progress(db_session, user, concept, **fields) -> UserGrammarProgress:
    row = UserGrammarProgress(user_id=user.id, concept_id=concept.id, **fields)
    db_session.add(row)
    db_session.flush()
    return row


def _state(decision) -> MemoryState:
    return MemoryState(decision.stability, decision.difficulty, decision.reps, decision.lapses)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


# ---------------------------------------------------------------------------
# 1. Migration: additive columns, seeded from the SM-2-era fields
# ---------------------------------------------------------------------------


def _load_migration():
    spec = importlib.util.spec_from_file_location("wpl3_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_follows_the_head_it_was_written_against() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "d1f3a5c7e9b2"' in source
    assert 'down_revision = "c4d6e8f0a2b3"' in source


def test_migration_upgrade_seeds_and_downgrade_drops() -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _load_migration()
    engine = sa.create_engine("sqlite://")
    last = datetime(2026, 9, 1, 8, 0)
    rows = [
        # id, score, reps, last_review, next_review
        (1, 0.0, 0, None, None),  # never reviewed
        (2, 8.0, 3, last, last + timedelta(days=20)),  # interval readback
        (3, 9.5, 5, None, None),  # no pair: seed by score
        (4, 3.5, 1, last, last + timedelta(days=1)),  # failed last review
    ]
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE user_grammar_progress (id INTEGER PRIMARY KEY, score FLOAT, "
                "reps INTEGER, state VARCHAR(50), last_review DATETIME, next_review DATETIME)"
            )
        )
        for row_id, score, reps, lr, nr in rows:
            connection.execute(
                sa.text(
                    "INSERT INTO user_grammar_progress VALUES (:id, :score, :reps, 'x', :lr, :nr)"
                ),
                {"id": row_id, "score": score, "reps": reps, "lr": lr, "nr": nr},
            )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        seeded = {
            row[0]: (row[1], row[2], row[3])
            for row in connection.execute(
                sa.text("SELECT id, stability, difficulty, lapses FROM user_grammar_progress")
            )
        }
        assert seeded[1] == (0.0, 5.0, 0)
        assert seeded[2] == (20.0, pytest.approx(3.2), 0)
        assert seeded[3] == (30.0, pytest.approx(2.3), 0)
        assert seeded[4] == (1.0, pytest.approx(5.9), 1)
        # The app's reader uses the same formula.
        for row_id, score, reps, lr, nr in rows:
            expected = seed_from_legacy(
                score=score,
                reps=reps,
                last_review=lr.replace(tzinfo=UTC) if lr else None,
                next_review=nr.replace(tzinfo=UTC) if nr else None,
            )
            assert seeded[row_id][0] == pytest.approx(expected.stability)
            assert seeded[row_id][1] == pytest.approx(expected.difficulty)
            assert seeded[row_id][2] == expected.lapses
        # Nothing is re-dated.
        untouched = connection.execute(
            sa.text("SELECT next_review FROM user_grammar_progress WHERE id = 2")
        ).scalar()
        assert str(untouched).startswith("2026-09-21")

        module.upgrade()  # idempotent
        module.downgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("user_grammar_progress")}
        assert not {"stability", "difficulty", "lapses"} & columns
        assert {"score", "reps", "state", "last_review", "next_review"} <= columns


def test_a_row_without_stability_continues_from_its_last_interval(db_session) -> None:
    """A row written before the migration reads the seed formula, not zero."""

    user = _user(db_session)
    concept = _concept(db_session)
    progress = _progress(
        db_session, user, concept, score=7.0, reps=4, state="gefestigt",
        last_review=NOW - timedelta(days=12), next_review=NOW, stability=0.0,
    )
    decision = apply_grammar_evidence(
        progress, Evidence(EvidenceFormat.GUIDED), now=NOW, score=7.0
    )
    assert decision is not None
    # Good on S=12: 12·1.3 + 1 = 16.6
    assert progress.stability == pytest.approx(16.6)
    assert (_naive(progress.next_review) - _naive(NOW)).days == 17


# ---------------------------------------------------------------------------
# 2. Evidence weights, and the one door
# ---------------------------------------------------------------------------


def _intervals(evidence: Evidence, reviews: int = 6) -> list[int]:
    state, out = None, []
    for _ in range(reviews):
        decision = memory.review(state, evidence, now=NOW)
        state = _state(decision)
        out.append(decision.interval_days)
    return out


def test_the_evidence_ladder_orders_formats() -> None:
    ladder = [
        Evidence(EvidenceFormat.RECOGNISE, assisted=True),
        Evidence(EvidenceFormat.RECOGNISE),
        Evidence(EvidenceFormat.GUIDED),
        Evidence(EvidenceFormat.TRANSFORM),
        Evidence(EvidenceFormat.PRODUCE),
    ]
    sums = [sum(_intervals(evidence)) for evidence in ladder]
    assert sums == sorted(sums)
    assert len(set(sums)) == len(sums), sums
    # stability after the same history, strictly increasing along the ladder
    base = MemoryState(stability=10.0, difficulty=5.0, reps=3, lapses=0)
    stabilities = [memory.review(base, evidence, now=NOW).stability for evidence in ladder]
    assert stabilities == sorted(stabilities) and len(set(stabilities)) == 5


def test_assisted_is_one_step_lower() -> None:
    pairs = [
        (EvidenceFormat.GUIDED, EvidenceFormat.RECOGNISE),
        (EvidenceFormat.TRANSFORM, EvidenceFormat.GUIDED),
        (EvidenceFormat.PRODUCE, EvidenceFormat.TRANSFORM),
    ]
    for assisted_format, lower in pairs:
        assisted = grade_evidence(Evidence(assisted_format, assisted=True))
        plain = grade_evidence(Evidence(lower))
        assert (assisted.rating, assisted.weight, assisted.step) == (
            plain.rating, plain.weight, plain.step,
        )


def test_a_lapse_is_an_error_in_production() -> None:
    held = MemoryState(stability=20.0, difficulty=4.0, reps=5, lapses=0)
    lapse = memory.review(held, Evidence(EvidenceFormat.PRODUCE, correct=False), now=NOW)
    assert lapse.grade.rating is Rating.AGAIN
    assert lapse.lapses == 1
    assert lapse.interval_days == 1
    assert lapse.stability == pytest.approx(4.0)  # S·0.2
    for fmt in (EvidenceFormat.RECOGNISE, EvidenceFormat.GUIDED, EvidenceFormat.TRANSFORM):
        slip = memory.review(held, Evidence(fmt, correct=False), now=NOW)
        assert slip.grade.rating is Rating.HARD
        assert slip.lapses == 0
        assert 1 < slip.interval_days < 20
    assumed = memory.review(
        held, Evidence(EvidenceFormat.PRODUCE, correct=False, assisted=True), now=NOW
    )
    assert assumed.is_lapse


def test_a_mention_never_schedules() -> None:
    assert grade_evidence(Evidence.mention()) is None
    assert memory.review(MemoryState(5.0, 5.0, 2, 0), Evidence.mention(), now=NOW) is None


def test_the_journey_maps_evidence_kinds_onto_the_ladder() -> None:
    assert JOURNEY_EVIDENCE[EvidenceKind.RECOGNIZED].format is EvidenceFormat.RECOGNISE
    assert JOURNEY_EVIDENCE[EvidenceKind.PRODUCED_SUPPORTED] == Evidence(
        EvidenceFormat.PRODUCE, correct=True, assisted=True
    )
    assert JOURNEY_EVIDENCE[EvidenceKind.PRODUCED_INDEPENDENT] == Evidence(EvidenceFormat.PRODUCE)
    assert grade_evidence(JOURNEY_EVIDENCE[EvidenceKind.NOT_YET]).is_lapse


def test_journey_credit_goes_through_the_one_door(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session)
    _progress(
        db_session, user, concept, score=8.5, reps=3, state="gefestigt",
        last_review=NOW - timedelta(days=10), next_review=NOW,
        stability=10.0, difficulty=4.0, lapses=0,
    )
    target = TargetRef(kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr="x")

    ok = _apply_grammar_credit(
        db_session, user=user, target=target,
        evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT, now=NOW,
    )
    progress = db_session.query(UserGrammarProgress).filter_by(user_id=user.id, concept_id=concept.id).one()
    assert ok.applied
    assert progress.stability == pytest.approx(10 * 1.6 + 1.5)
    assert progress.reps == 4

    later = NOW + timedelta(days=18)
    _apply_grammar_credit(
        db_session, user=user, target=target, evidence_kind=EvidenceKind.NOT_YET, now=later,
    )
    assert progress.lapses == 1
    assert (_naive(progress.next_review) - _naive(later)) == timedelta(days=1)


def test_the_atelier_credits_the_strongest_format_it_saw() -> None:
    passed = atelier_session_evidence(
        [("recognize", "fill", 4.0), ("transform", "transform", 4.0), ("produce", "produce", 4.0)],
        passed=True,
    )
    assert passed == Evidence(EvidenceFormat.PRODUCE)
    word_bank_only = atelier_session_evidence([("recognize", "word_bank", 4.0)], passed=True)
    assert word_bank_only.format is EvidenceFormat.GUIDED
    partial = atelier_session_evidence([("sentence", "guided", 2.0)], passed=True)
    assert partial == Evidence(EvidenceFormat.PRODUCE, assisted=True)
    failed_production = atelier_session_evidence(
        [("recognize", "fill", 4.0), ("produce", "produce", 1.0)], passed=False
    )
    assert grade_evidence(failed_production).is_lapse
    failed_recognition = atelier_session_evidence([("recognize", "classify", 1.0)], passed=False)
    assert grade_evidence(failed_recognition).rating is Rating.HARD


def test_record_review_uses_the_evidence_it_is_given(db_session) -> None:
    user = _user(db_session)
    weak, strong = _concept(db_session), _concept(db_session)
    service = GrammarService(db_session)
    a = service.record_review(
        user=user, concept_id=weak.id, score=8.0,
        evidence=Evidence(EvidenceFormat.RECOGNISE),
    )
    b = service.record_review(
        user=user, concept_id=strong.id, score=8.0,
        evidence=Evidence(EvidenceFormat.PRODUCE),
    )
    assert a.score == b.score == 8.0  # display unchanged
    assert a.stability < b.stability
    assert a.next_review < b.next_review


def test_a_mention_leaves_the_schedule_alone(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session)
    progress = _progress(
        db_session, user, concept, score=7.0, reps=3, state="gefestigt",
        last_review=NOW - timedelta(days=5), next_review=NOW + timedelta(days=5),
        stability=10.0, difficulty=5.0,
    )
    GrammarService(db_session).mark_concepts_practiced_in_context(user=user, concept_ids=[concept.id])
    db_session.refresh(progress)
    assert progress.stability == 10.0
    assert progress.reps == 3
    assert _naive(progress.next_review) == _naive(NOW + timedelta(days=5))
    assert progress.score == 7.5


def test_nothing_but_the_one_door_writes_a_grammar_schedule() -> None:
    """Every `<progress>.next_review = …` in app/ lives in apply_grammar_evidence."""

    writers: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute) and target.attr == "next_review":
                                writers.append(f"{path.relative_to(ROOT)}:{node.name}")
    assert writers == ["app/services/grammar.py:apply_grammar_evidence"], writers


# ---------------------------------------------------------------------------
# 3. Errata on the same model; three spaced repairs still retire them
# ---------------------------------------------------------------------------


def _erratum(db_session, user, **fields) -> UserError:
    error = UserError(
        user_id=user.id,
        error_category="grammar",
        error_pattern="wp_l3",
        display_label=f"Erratum {uuid4().hex[:6]}",
        memory_key=f"wp_l3:{uuid4().hex}",
        original_text="au le café",
        correction="au café",
        state="open",
        next_review_date=NOW - timedelta(hours=1),
        **fields,
    )
    db_session.add(error)
    db_session.flush()
    return error


def test_errata_are_scheduled_by_stability(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    service = ErrorMemoryService(db_session)
    intervals = []
    for day in range(3):
        reviewed = service.review_error(
            user=user, error_id=error.id, rating=4, repaired=True, now=NOW + timedelta(days=day * 5)
        )
        intervals.append(reviewed.scheduled_days)
        assert reviewed.stability > 0
    assert intervals == sorted(intervals) and intervals[-1] > intervals[0]

    failed = service.review_error(
        user=user, error_id=error.id, rating=1, repaired=False, now=NOW + timedelta(days=30)
    )
    assert failed.scheduled_days == 1
    assert failed.lapses == 1
    assert failed.mastery_streak == 0


def test_errata_still_retire_after_three_repairs_on_separate_days(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    service = ErrorMemoryService(db_session)
    # Two repairs the same day count once.
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW)
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW + timedelta(hours=2))
    assert error.mastery_streak == 1
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW + timedelta(days=2))
    assert error.state == ERROR_STATE_REPAIRING
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW + timedelta(days=7))
    assert error.state == ERROR_STATE_MASTERED


def test_the_unified_error_card_uses_the_same_lifecycle(db_session) -> None:
    """The daily-practice card used to run its own interval table and never retired."""

    user = _user(db_session)
    error = _erratum(db_session, user)
    db_session.commit()
    service = UnifiedSRSService(db_session)
    for _ in range(3):
        # Each «Bien» lands on a later day than the previous accepted repair.
        error.last_correct_date = datetime.now(UTC) - timedelta(days=2)
        db_session.commit()
        service.complete_item(user_id=user.id, item_type=ItemType.ERROR, item_id=str(error.id), rating=3)
    db_session.refresh(error)
    assert error.state == ERROR_STATE_MASTERED
    assert error.stability > 0
    assert error.reps == 3


def test_a_recurrence_collapses_the_erratums_stability(db_session) -> None:
    user = _user(db_session)
    service = ErrorMemoryService(db_session)
    erratum = {
        "display_label": "Reprise : au le café",
        "learner_text": "au le café",
        "corrected_target": "au café",
        "why_wrong": "à + le = au",
        "repair_hint": "au café",
        "severity": 2,
        "recurring": True,
        "task_error_type": "wp_l3_recurrence",
        "external_id": None,
    }
    created = service.record_erratum(user=user, erratum=erratum, source_type="daily_journey")
    error = db_session.get(UserError, UUID(str(created["error_id"])))
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW)
    service.review_error(user=user, error_id=error.id, rating=4, repaired=True, now=NOW + timedelta(days=5))
    strong = error.stability
    service.record_erratum(user=user, erratum=erratum, source_type="daily_journey")
    assert error.stability == pytest.approx(max(0.2, strong * 0.2))
    assert error.state == ERROR_STATE_REPAIRING


# ---------------------------------------------------------------------------
# 4. One queue, interleaved
# ---------------------------------------------------------------------------


def _item(kind: ItemType, key: int, priority: float, **metadata) -> DueLearningItem:
    base = {
        ItemType.GRAMMAR: {"concept_id": key},
        ItemType.ERROR: {"concept_id": metadata.pop("concept_id", None)},
        ItemType.VOCAB: {"word_id": key},
        ItemType.CONJUGATION: {"normalized_lemma": f"verb{key}"},
    }[kind]
    return DueLearningItem(
        id=f"{kind}_{key}_{uuid4().hex[:4]}",
        item_type=kind,
        priority_score=priority,
        display_title=str(key),
        display_subtitle="",
        level="A1",
        due_since_days=0,
        estimated_seconds=RAPPEL_ITEM_SECONDS[kind],
        original_id=key,
        metadata={**base, **metadata},
    )


def test_every_block_draws_from_three_sources_when_it_can() -> None:
    items = (
        [_item(ItemType.GRAMMAR, i, 90 - i) for i in range(8)]
        + [_item(ItemType.ERROR, 100 + i, 60 - i) for i in range(4)]
        + [_item(ItemType.VOCAB, 200 + i, 20 - i) for i in range(12)]
    )
    ordered = interleave_review_items(items)
    assert len(ordered) == len(items)
    blocks = [ordered[i : i + 6] for i in range(0, len(ordered), 6)]
    for block in blocks[:2]:  # all three sources still have items
        assert len({item.item_type for item in block}) >= 3


def test_no_concept_twice_in_a_row() -> None:
    # An erratum linked to concept 1 is concept 1.
    items = [
        _item(ItemType.GRAMMAR, 1, 99),
        _item(ItemType.ERROR, 50, 98, concept_id=1),
        _item(ItemType.GRAMMAR, 2, 10),
        _item(ItemType.VOCAB, 7, 5),
    ]
    ordered = interleave_review_items(items)
    keys = [review_concept_key(item) for item in ordered]
    assert all(a != b for a, b in zip(keys, keys[1:], strict=False)), keys


def test_the_budget_is_respected() -> None:
    items = [_item(ItemType.GRAMMAR, i, 50) for i in range(10)] + [
        _item(ItemType.VOCAB, 100 + i, 40) for i in range(10)
    ]
    ordered = interleave_review_items(items, budget_seconds=120)
    assert sum(item.estimated_seconds for item in ordered) <= 120
    assert ordered  # something fits
    assert interleave_review_items(items, budget_seconds=5) == []


def _due_word(db_session, user, word: str) -> None:
    vocab = VocabularyWord(
        language="fr", word=f"{word}{uuid4().hex[:4]}", normalized_word=f"{word}{uuid4().hex[:4]}",
        english_translation=word, difficulty_level=1,
    )
    db_session.add(vocab)
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id, word_id=vocab.id, state="reviewing", reps=2, stability=3.0,
            due_at=NOW - timedelta(hours=2),
        )
    )


def test_plan_review_items_is_the_day_planner_api(db_session) -> None:
    user = _user(db_session)
    for index in range(3):
        concept = _concept(db_session)
        _progress(
            db_session, user, concept, score=6.0, reps=2, state="in_arbeit",
            last_review=NOW - timedelta(days=4), next_review=NOW - timedelta(hours=index + 1),
            stability=4.0,
        )
        _erratum(db_session, user, concept_id=concept.id)
        _due_word(db_session, user, f"mot{index}")
    db_session.commit()

    plan = UnifiedSRSService(db_session).plan_review_items(user.id, budget_seconds=600, now=NOW)

    assert {item.item_type for item in plan[:6]} >= {ItemType.GRAMMAR, ItemType.ERROR, ItemType.VOCAB}
    assert sum(item.estimated_seconds for item in plan) <= 600
    keys = [review_concept_key(item) for item in plan]
    assert all(a != b for a, b in zip(keys, keys[1:], strict=False)), keys
    grammar = next(item for item in plan if item.item_type is ItemType.GRAMMAR)
    assert grammar.metadata["stability"] == 4.0
    # Read-only.
    assert db_session.query(UserGrammarProgress).filter_by(user_id=user.id).filter(
        UserGrammarProgress.next_review > NOW
    ).count() == 0


def test_a_contrast_partner_comes_back_once_a_week(db_session) -> None:
    user = _user(db_session)
    partner = _concept(db_session, name="passé composé")
    anchor = _concept(db_session, name="imparfait", source_refs={"contrast_partners": [partner.external_id]})
    _progress(
        db_session, user, anchor, score=6.0, reps=3, state="in_arbeit",
        last_review=NOW - timedelta(days=3), next_review=NOW - timedelta(hours=1), stability=3.0,
    )
    partner_progress = _progress(
        db_session, user, partner, score=8.0, reps=4, state="gefestigt",
        last_review=NOW - timedelta(days=9), next_review=NOW + timedelta(days=20), stability=29.0,
    )
    db_session.commit()
    service = UnifiedSRSService(db_session)

    plan = service.plan_review_items(user.id, budget_seconds=600, now=NOW)
    contrast = [item for item in plan if item.metadata.get("contrast_for") == anchor.id]
    assert [item.original_id for item in contrast] == [partner.id]

    # Seen within the week: not pulled in again.
    partner_progress.last_review = NOW - timedelta(days=2)
    db_session.commit()
    plan = service.plan_review_items(user.id, budget_seconds=600, now=NOW)
    assert not [item for item in plan if item.metadata.get("contrast_for")]


def test_contrast_is_a_no_op_without_partner_data(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session)
    other = _concept(db_session)
    _progress(
        db_session, user, concept, score=6.0, reps=3, last_review=NOW - timedelta(days=3),
        next_review=NOW - timedelta(hours=1), stability=3.0,
    )
    _progress(
        db_session, user, other, score=6.0, reps=3, last_review=NOW - timedelta(days=30),
        next_review=NOW + timedelta(days=9), stability=30.0,
    )
    db_session.commit()
    plan = UnifiedSRSService(db_session).plan_review_items(user.id, budget_seconds=600, now=NOW)
    assert [item.original_id for item in plan if item.item_type is ItemType.GRAMMAR] == [concept.id]


# ---------------------------------------------------------------------------
# 5. Held items keep returning, at least every 60 days
# ---------------------------------------------------------------------------


def test_a_held_concept_returns_within_sixty_days(db_session) -> None:
    decision = memory.review(
        MemoryState(stability=300.0, difficulty=2.0, reps=12, lapses=0),
        Evidence(EvidenceFormat.PRODUCE),
        now=NOW,
    )
    assert decision.stability > 300
    assert decision.interval_days == MAX_INTERVAL_DAYS == 60

    user = _user(db_session)
    concept = _concept(db_session)
    progress = _progress(
        db_session, user, concept, score=9.5, reps=8, state="gemeistert",
        last_review=NOW - timedelta(days=60), next_review=NOW - timedelta(minutes=5), stability=200.0,
    )
    db_session.commit()
    plan = UnifiedSRSService(db_session).plan_review_items(user.id, budget_seconds=300, now=NOW)
    assert concept.id in [item.original_id for item in plan if item.item_type is ItemType.GRAMMAR]
    apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE), now=NOW, score=9.5)
    assert progress.state == "gemeistert"
    assert (_naive(progress.next_review) - _naive(NOW)).days <= 60


# ---------------------------------------------------------------------------
# 6. The scheduler simulation (numbers in WORK-PACKAGES-2026-09-23-learning.md)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("accuracy", [0.70, 0.85, 0.95])
def test_intervals_grow_with_success_and_collapse_on_a_lapse(accuracy: float) -> None:
    result = simulate_learner(accuracy, days=120)
    successes = collapses = 0
    for item in result.items:
        steps = zip(item.intervals, item.intervals[1:], item.outcomes[1:], item.lapses_at[1:], strict=False)
        for previous, current, correct, lapse in steps:
            if correct:
                assert current >= previous  # success never shortens the interval
                successes += current > previous
            if lapse:
                assert current == 1
                collapses += previous > 1
    assert successes > 0
    assert collapses > 0
    assert result.total_lapses > 0


def test_held_concepts_return_at_least_every_sixty_days() -> None:
    result = simulate_learner(0.95, days=365)
    assert result.max_gap_days == 60


def test_steady_state_review_load_per_new_item() -> None:
    """The numbers written into the WP doc for WP-L6's throttle."""

    loads = {
        accuracy: round(simulate_learner(accuracy, days=120).load_per_new_item, 1)
        for accuracy in (0.70, 0.85, 0.95)
    }
    assert loads[0.70] > loads[0.85] > loads[0.95]
    assert loads == {0.70: 13.5, 0.85: 8.1, 0.95: 5.9}


def test_contrast_partners_are_read_from_the_v2_syllabus_block():
    """v2 stores contrast partners under source_refs["syllabus"]; the forge seats them."""

    from types import SimpleNamespace

    from app.services.unified_srs import contrast_partner_refs

    v2 = SimpleNamespace(source_refs={"syllabus": {"contrast_partners": ["FR2_A11_DEF_ARTICLES", " "]}})
    flat = SimpleNamespace(source_refs={"contrast_partners": [7]})
    assert contrast_partner_refs(v2) == ["FR2_A11_DEF_ARTICLES"]
    assert contrast_partner_refs(flat) == [7]
    assert contrast_partner_refs(SimpleNamespace(source_refs=None)) == []
