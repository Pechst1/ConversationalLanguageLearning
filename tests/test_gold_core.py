"""Package O-1 — the mint table (``app/core/gold.py``), rule by rule.

``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §4 is the specification; each test names
the rule it pins. Pure: no database, no clock.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from app.core import gold
from app.core.gold import Category, DayState, GoldObservation, mint

T = gold.target_key("grammar", 12)


def obs(category: Category, **kwargs) -> GoldObservation:
    return GoldObservation(category=category, **kwargs)


def paid(observation: GoldObservation, day: DayState | None = None) -> int | None:
    minted = mint(observation, day or DayState())
    return None if minted is None else minted.amount


# -- §4.1 the table --------------------------------------------------------------


def test_the_base_values_are_the_spec_table() -> None:
    assert gold.BASE_VALUE == {
        Category.RECOGNISED: 1,
        Category.TYPED: 2,
        Category.GUIDED: 3,
        Category.FREE: 5,
        Category.LETTER: 8,
        Category.REPAIR: 1,
    }
    for category, value in gold.BASE_VALUE.items():
        assert paid(obs(category)) == value


@pytest.mark.parametrize(
    "fmt",
    ["choice", "who_said", "listen_tap", "match_pairs", "classify", "tiles", "unscramble", "word_bank"],
)
def test_the_journeys_picks_and_orders_are_recognition(fmt: str) -> None:
    assert gold.category_for_format(fmt) is Category.RECOGNISED


@pytest.mark.parametrize("fmt", ["short_answer", "transform", "dictation"])
def test_typed_formats_are_typed_recall(fmt: str) -> None:
    assert gold.category_for_format(fmt) is Category.TYPED


def test_production_formats_and_unknown_formats() -> None:
    assert gold.category_for_format("sentence") is Category.GUIDED
    assert gold.category_for_format("conversation") is Category.FREE
    assert gold.category_for_format("reply") is Category.FREE
    # An unknown format never pays more than the lowest rank.
    assert gold.category_for_format("something_new") is Category.RECOGNISED
    assert gold.category_for_format(None) is Category.RECOGNISED


def test_the_forge_staircase() -> None:
    assert [gold.category_for_rung(rung) for rung in range(6)] == [
        Category.RECOGNISED,  # recognise
        Category.RECOGNISED,  # discriminate
        Category.RECOGNISED,  # build
        Category.TYPED,  # transform
        Category.GUIDED,  # produce: a model and a frame are given
        Category.FREE,  # free_use
    ]
    assert gold.category_for_rung(9) is Category.FREE
    assert gold.category_for_rung(-1) is Category.RECOGNISED


# -- R1 le meilleur du jour -----------------------------------------------------


def test_r1_a_better_evidence_pays_the_difference() -> None:
    """The spec's own example: recognise (1), rewrite (2, +1), use freely (5, +3)."""

    day = DayState()
    amounts = []
    for category in (Category.RECOGNISED, Category.TYPED, Category.FREE):
        observation = obs(category, target=T)
        minted = mint(observation, day)
        assert minted is not None
        amounts.append(minted.amount)
        day = gold.advance(day, observation, minted)
    assert amounts == [1, 1, 3]
    assert day.best[T] == 5 and day.earned == 5


def test_r1_the_same_format_again_pays_nothing() -> None:
    first = obs(Category.TYPED, target=T)
    day = gold.advance(DayState(), first, mint(first, DayState()))
    assert mint(obs(Category.TYPED, target=T), day) is None
    assert mint(obs(Category.RECOGNISED, target=T), day) is None
    # Another target is its own day.
    assert paid(obs(Category.TYPED, target=gold.target_key("vocabulary", 7)), day) == 2


def test_r1_a_unit_pays_as_itself_and_lifts_what_it_shows() -> None:
    """A reply turn pays once and lifts its targets: no double pay for one sentence."""

    day = gold.advance(DayState(), obs(Category.TYPED, target=T), mint(obs(Category.TYPED, target=T), DayState()))
    turn = obs(Category.FREE, lifts=(T,))
    minted = mint(turn, day)
    assert minted is not None and minted.amount == 5, "the turn pays its own 5, not a top-up"
    day = gold.advance(day, turn, minted)
    assert day.best[T] == 5
    assert mint(obs(Category.FREE, target=T), day) is None, "the sentence already paid for the rule"
    # A second turn is a second unit.
    assert paid(obs(Category.FREE, lifts=(T,)), day) == 5


# -- R2 aide --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "assistance", "expected"),
    [
        (Category.RECOGNISED, "hint", None),  # ½ rounds down to nothing
        (Category.TYPED, "hint", 1),
        (Category.TYPED, "translation", 1),
        (Category.FREE, "hint", 2),
        (Category.GUIDED, "hint", 1),
        (Category.FREE, "suggested_response", None),
        (Category.FREE, "solution", None),
        (Category.TYPED, "unheard_of_help", None),
    ],
)
def test_r2_assistance(category: Category, assistance: str, expected: int | None) -> None:
    assert paid(obs(category, assistance=assistance)) == expected


# -- R3 partiel ------------------------------------------------------------------


def test_r3_partly_met_or_an_accent_slip_pays_half() -> None:
    assert paid(obs(Category.TYPED, outcome=gold.OUTCOME_PARTIAL)) == 1
    assert paid(obs(Category.TYPED, accent_slip=True)) == 1
    assert paid(obs(Category.RECOGNISED, outcome=gold.OUTCOME_PARTIAL)) is None
    assert paid(obs(Category.FREE, outcome=gold.OUTCOME_PARTIAL)) == 2
    assert paid(obs(Category.LETTER, outcome=gold.OUTCOME_PARTIAL)) == 4


def test_r3_production_that_pays_pays_at_least_one() -> None:
    # 3 × ½ (hint) × ½ (partial) = 0.75 → 1, because it is production.
    assert paid(obs(Category.GUIDED, assistance="hint", outcome=gold.OUTCOME_PARTIAL)) == 1
    assert paid(obs(Category.FREE, assistance="hint", outcome=gold.OUTCOME_PARTIAL)) == 1
    # A zero factor stays zero: a shown solution is not production.
    assert paid(obs(Category.GUIDED, assistance="solution", outcome=gold.OUTCOME_PARTIAL)) is None
    # A repair is not production: ½ of 1 is nothing.
    assert paid(obs(Category.REPAIR, assistance="hint")) is None


# -- R4 rappel différé ------------------------------------------------------------


def test_r4_doubles_a_correct_unaided_spaced_item() -> None:
    assert paid(obs(Category.RECOGNISED, delayed_recall=True)) == 2
    assert paid(obs(Category.TYPED, delayed_recall=True)) == 4


@pytest.mark.parametrize(
    "observation",
    [
        obs(Category.FREE, delayed_recall=True),  # a reply is not a spaced item
        obs(Category.GUIDED, delayed_recall=True),
        obs(Category.TYPED, delayed_recall=True, assistance="hint"),
        obs(Category.TYPED, delayed_recall=True, outcome=gold.OUTCOME_PARTIAL),
        obs(Category.TYPED, delayed_recall=True, accent_slip=True),
        obs(Category.REPAIR, delayed_recall=True),
    ],
)
def test_r4_never_doubles_anything_else(observation: GoldObservation) -> None:
    minted = mint(observation, DayState())
    assert minted is None or all(factor["rule"] != "R4" for factor in minted.breakdown["factors"])


# -- R5 posé en dessous -----------------------------------------------------------


def test_r5_below_the_level_pays_half_and_the_order_of_factors_never_matters() -> None:
    assert paid(obs(Category.TYPED, below_level=True)) == 1
    assert paid(obs(Category.RECOGNISED, below_level=True)) is None
    # 1 × 2 × ½ = 1 (rounded once), never 0 (rounded at each step).
    assert paid(obs(Category.RECOGNISED, below_level=True, delayed_recall=True)) == 1


# -- R6 vérifié seulement, R7 premier essai, copies -----------------------------


def test_r6_unchecked_is_pending_and_unscored_pays_nothing() -> None:
    minted = mint(obs(Category.FREE, checked=False), DayState())
    assert minted is not None and minted.state == gold.STATE_PENDING and minted.amount == 5
    assert mint(obs(Category.FREE), DayState()).state == gold.STATE_SETTLED
    assert mint(obs(Category.FREE, outcome=gold.OUTCOME_UNSCORED), DayState()) is None
    assert mint(obs(Category.FREE, outcome=gold.OUTCOME_NOT_YET), DayState()) is None


def test_r7_first_submission_only_except_the_repair() -> None:
    assert mint(obs(Category.TYPED, first_attempt=False), DayState()) is None
    assert paid(obs(Category.REPAIR, first_attempt=False)) == 1


def test_a_copied_sentence_pays_nothing() -> None:
    assert mint(obs(Category.GUIDED, copy=True), DayState()) is None


# -- R8 le plafond ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("earned", "pays"),
    [(0, 0), (1, 1), (90, 90), (91, 90), (92, 91), (120, 105), (150, 120), (151, 120), (10_000, 120)],
)
def test_r8_the_plafond_curve(earned: int, pays: int) -> None:
    assert gold.plafond(earned) == pays
    assert gold.DAY_CAP == 120


def test_r8_an_entry_past_90_pays_at_half_rate_and_is_still_written() -> None:
    minted = mint(obs(Category.FREE), DayState(earned=89))
    assert minted is not None and minted.earned == 5 and minted.amount == 3  # 90 + 2 − 89
    assert minted.breakdown["plafond_factor"] == "3/5"
    spent = mint(obs(Category.FREE), DayState(earned=150))
    assert spent is not None and spent.amount == 0, "past 150 the entry records the evidence and pays 0"
    assert "plafond du jour" in spent.breakdown["reason_fr"]


def test_r8_no_day_ever_pays_more_than_120() -> None:
    rnd = random.Random(45)
    categories = list(Category)
    for _ in range(200):
        day = DayState()
        total = 0
        for _ in range(rnd.randint(1, 120)):
            observation = obs(
                rnd.choice(categories),
                outcome=rnd.choice([gold.OUTCOME_MET, gold.OUTCOME_MET, gold.OUTCOME_PARTIAL]),
                assistance=rnd.choice(["none", "none", "none", "hint"]),
                delayed_recall=rnd.random() < 0.3,
                target=rnd.choice([None, *(gold.target_key("vocabulary", n) for n in range(30))]),
            )
            minted = mint(observation, day)
            if minted is not None:
                total += minted.amount
                day = gold.advance(day, observation, minted)
        assert total == gold.plafond(day.earned) <= gold.DAY_CAP


# -- a relecture that lands later -------------------------------------------------


def test_resettle_prices_the_final_verdict_against_the_day_it_was_minted() -> None:
    pending = mint(obs(Category.FREE, checked=False, target=T), DayState(earned=40, best={T: 2}))
    assert pending is not None and pending.amount == 3 and pending.state == gold.STATE_PENDING
    confirmed = gold.resettle(pending.breakdown, obs(Category.FREE, target=T))
    assert confirmed is not None and confirmed.amount == 3 and confirmed.state == gold.STATE_SETTLED
    partial = gold.resettle(pending.breakdown, obs(Category.FREE, outcome=gold.OUTCOME_PARTIAL, target=T))
    assert partial is None, "half of 5 is 2, no better than the 2 the rule already had today"
    alone = mint(obs(Category.FREE, checked=False, target=T), DayState())
    assert gold.resettle(alone.breakdown, obs(Category.FREE, outcome=gold.OUTCOME_PARTIAL, target=T)).amount == 2


# -- milestones, marks and time ---------------------------------------------------


def test_milestones_and_marks_are_the_spec() -> None:
    assert gold.MILESTONE_VALUE == {
        gold.Milestone.RULE_HELD: 25,
        gold.Milestone.CAPABILITY_CONFIRMED: 10,
        gold.Milestone.EPREUVE_PASSED: 30,
        gold.Milestone.PERFECT_DAY: 10,
    }
    assert gold.JOLI_BONUS == 2
    assert gold.JOURNEE_PLEINE_MARK == {"leger": 10, "regulier": 20, "soutenu": 35, "intensif": 45}
    assert set(gold.CALIBRATION_TARGETS) == set(gold.JOURNEE_PLEINE_MARK)


def test_the_week_is_the_iso_week_in_paris() -> None:
    # Sunday 1 Nov 2026, 23:30 Paris (22:30 UTC) is still week 44; half past
    # midnight in Paris (23:30 UTC) is Monday, week 45.
    assert gold.week_id(datetime(2026, 11, 1, 22, 30, tzinfo=UTC)) == "2026-W44"
    assert gold.week_id(datetime(2026, 11, 1, 23, 30, tzinfo=UTC)) == "2026-W45"
    assert gold.week_id(datetime(2026, 11, 1, 23, 30)) == "2026-W45", "a naive instant is UTC"


def test_the_local_day_is_the_learners_zone() -> None:
    instant = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)
    assert gold.local_date(instant, "Europe/Paris").isoformat() == "2026-11-02"
    assert gold.local_date(instant, "America/New_York").isoformat() == "2026-11-01"


def test_the_breakdown_explains_the_amount_in_french() -> None:
    minted = mint(obs(Category.TYPED, delayed_recall=True, target=T), DayState())
    assert minted.breakdown["reason_fr"] == "Rappel écrit · rappel différé ×2"
    assert minted.breakdown["base"] == 2 and minted.breakdown["value"] == 4
    assert minted.breakdown["factors"] == [{"rule": "R4", "name": "rappel_differe", "factor": "2"}]
    helped = mint(obs(Category.FREE, assistance="hint"), DayState())
    assert helped.breakdown["reason_fr"] == "Production libre · avec aide ×1/2"
