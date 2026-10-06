"""WP-138 — «Tenue» (retained grammar) is granted by evidence, never by elapsed time.

Status plan 2026-10-06, "make progress understandable", item 4. Fourteen days
since the introduction only opens the window for the spaced item; the success
itself must be an unaided recall after the unit was left alone for at least
``HELD_SPACED_GAP_HOURS``. Time passing on its own grants nothing.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.core.srs.memory import Evidence, EvidenceFormat
from app.services import concept_life
from app.services.grammar import apply_grammar_evidence

DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
PRODUCE = Evidence(EvidenceFormat.PRODUCE, correct=True)
SPACED = Evidence(EvidenceFormat.TRANSFORM, correct=True)


def _life(**fields) -> SimpleNamespace:
    base = {
        "created_at": DAY0,
        "reps": 1,
        "introduced_at": DAY0,
        "free_use_first_at": None,
        "free_use_last_at": None,
        "spaced_success_at": None,
        "held_at": None,
        "last_review": None,
    }
    base.update(fields)
    return SimpleNamespace(**base)


def _with_free_use_pair() -> SimpleNamespace:
    life = _life()
    concept_life.note_concept_evidence(life, PRODUCE, now=DAY0 + timedelta(days=1))
    concept_life.note_concept_evidence(life, PRODUCE, now=DAY0 + timedelta(days=9))
    assert concept_life.held_conditions(life) == (True, False)
    return life


def test_elapsed_time_alone_grants_nothing():
    life = _with_free_use_pair()
    far = DAY0 + timedelta(days=120)
    assert concept_life.held_conditions(life) == (True, False)
    assert not concept_life.is_held(life)
    assert concept_life.concept_stage(life) != concept_life.STAGE_HELD
    # Nothing but a mention arrives: still not held.
    concept_life.note_concept_evidence(life, Evidence.mention(), now=far)
    assert life.held_at is None


def test_a_spaced_item_right_after_contact_is_not_retention():
    life = _with_free_use_pair()
    now = DAY0 + timedelta(days=20)
    concept_life.note_concept_evidence(life, SPACED, now=now, previous_contact_at=now - timedelta(hours=3))
    assert life.spaced_success_at is None
    assert life.held_at is None


def test_an_assisted_spaced_item_is_not_retention():
    life = _with_free_use_pair()
    now = DAY0 + timedelta(days=20)
    concept_life.note_concept_evidence(
        life,
        Evidence(EvidenceFormat.TRANSFORM, correct=True, assisted=True),
        now=now,
        previous_contact_at=now - timedelta(days=5),
    )
    assert life.spaced_success_at is None
    assert life.held_at is None


def test_a_delayed_unaided_recall_completes_held():
    life = _with_free_use_pair()
    now = DAY0 + timedelta(days=20)
    concept_life.note_concept_evidence(life, SPACED, now=now, previous_contact_at=now - timedelta(days=5))
    assert life.spaced_success_at == now
    assert life.held_at == now


def test_the_row_last_review_is_the_previous_contact_by_default():
    life = _with_free_use_pair()
    now = DAY0 + timedelta(days=20)
    life.last_review = now - timedelta(hours=1)
    concept_life.note_concept_evidence(life, SPACED, now=now)
    assert life.spaced_success_at is None
    assert not concept_life.spaced_item_owed(life, now=now)
    later = life.last_review + timedelta(hours=concept_life.HELD_SPACED_GAP_HOURS)
    assert concept_life.spaced_item_owed(life, now=later)


def test_apply_grammar_evidence_measures_the_gap_before_stamping_last_review():
    """The schedule writes ``last_review = now`` before the life sees the
    observation; the gap is still measured from the earlier contact."""

    now = DAY0 + timedelta(days=20)
    progress = SimpleNamespace(
        stability=10.0, difficulty=5.0, lapses=0, reps=4, last_review=now - timedelta(days=6),
        next_review=now, score=7.0, state="learning", updated_at=None,
        created_at=DAY0, introduced_at=DAY0,
        free_use_first_at=DAY0 + timedelta(days=1), free_use_last_at=DAY0 + timedelta(days=9),
        spaced_success_at=None, held_at=None,
    )
    apply_grammar_evidence(progress, SPACED, now=now)
    assert progress.last_review == now
    assert progress.spaced_success_at == now
    assert progress.held_at == now

    fresh = SimpleNamespace(**{**vars(progress), "last_review": now - timedelta(hours=2),
                               "spaced_success_at": None, "held_at": None})
    apply_grammar_evidence(fresh, SPACED, now=now)
    assert fresh.spaced_success_at is None
    assert fresh.held_at is None
