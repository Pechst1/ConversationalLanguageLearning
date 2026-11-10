# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""#443 — «Forge today's rule» opens on the day's rule, and a séance that is not over is not finished.

The 1 Nov live walk: Home and the pre-scene drills named «Avoir» as the day's
rule; La Forge opened on «Un, une, des» at Level 6, and after one repaired line
its only button was «Finish», which ended the séance at 1 of 17.

Two derivations let it happen:

* The day's rule was derived twice. The journey plans it (the scene's own rule,
  ``plan_selection["introduction"]``); the forge entry Home links to asked the
  forge picker again, without the plan, and the picker answers with the
  quota's first rule or a due erratum's. The entry now reads the plan.
* ``ForgeState.finished`` was a stored copy of "no slot ahead". A free line that
  the local check read as using the rule tops its rule out *provisionally*
  (``record``); the model's reading then withdrew the top-out (``settle``) but
  left the copy, so the séance stayed over and the page offered «Finish».
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Verdict
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.error import UserError
from app.services.atelier import AtelierScheduler
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    enabled,
    make_user,
)
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture


def test_entry_names_planned_rule(db_session: Session, v2, enabled) -> None:
    user = make_user(db_session, f"forge-443-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201

    # The day's plan introduces the scene's own rule: not the quota's first one.
    upcoming = AtelierScheduler(db_session).next_new_concepts(user, limit=4, language="fr")
    assert len(upcoming) >= 2
    days_rule = upcoming[1]
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    row.plan_selection = {
        **dict(row.plan_selection or {}),
        "introduction": {"concept_id": days_rule.id, "title_native": days_rule.name},
    }
    flag_modified(row, "plan_selection")
    db_session.commit()

    today = service.get_today(user)
    assert today.forge is not None
    assert today.forge.concept_id == days_rule.id, "the forge entry names the day's rule, not another"
    assert f"concept={days_rule.id}" in today.forge.href
    assert f"concept={days_rule.id}" in today.practice_href


def test_entry_names_the_rule_of_a_review_only_card(db_session: Session, v2, enabled) -> None:
    """8 Nov walk: day 2's rule card was a known rule (``review``: it introduces nothing,
    so ``plan_selection`` has no introduction) and a day-1 slip on another rule was
    due. The Forge entry fell back to the picker, which puts the erratum first: the
    slip rule took «Regel des Tages» and the card's own rule came back as a review.
    The entry names the rule the card shows, introduced or reviewed."""

    user = make_user(db_session, f"forge-443-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201

    upcoming = AtelierScheduler(db_session).next_new_concepts(user, limit=4, language="fr")
    assert len(upcoming) >= 2
    slip_rule, card_rule = upcoming[0], upcoming[1]
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=slip_rule.id,
            error_category="grammar",
            error_pattern="article",
            original_text="la appartement",
            correction="l'appartement",
            next_review_date=datetime.now(UTC) - timedelta(hours=1),
            occurrences=1,
        )
    )
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    selection = dict(row.plan_selection or {})
    selection["introduction"] = None  # a review-only card introduces nothing
    row.plan_selection = selection
    flag_modified(row, "plan_selection")
    db_session.add(
        DailyJourneyStep(
            journey_id=row.id,
            ordinal=len(row.steps),
            kind="rule",
            status="pending",
            estimated_seconds=40,
            public_prompt={
                "concept_id": card_rule.id,
                "title_native": card_rule.name,
                "review": True,
                "rule_card": {"example": {"fr": "Je suis [content]."}, "rule": {"en": "A known rule."}},
            },
            private_task={"review_concept_id": card_rule.id},
        )
    )
    db_session.commit()

    today = service.get_today(user)
    assert today.forge is not None
    assert today.forge.concept_id == card_rule.id, "the day's Forge works on the rule the card shows, not on a slip rule"
    assert f"concept={card_rule.id}" in today.forge.href
    assert f"concept={card_rule.id}" in today.practice_href

    # The folded forge step was planned with the picker's rule: its link follows the card.
    folded = DailyJourneyStep(
        journey_id=row.id,
        ordinal=len(row.steps) + 1,
        kind="forge",
        status="pending",
        estimated_seconds=300,
        public_prompt={"concept_id": slip_rule.id, "budget_seconds": 300},
    )
    db_session.add(folded)
    db_session.commit()
    db_session.refresh(row)
    view = service._forge_prompt_view(row, folded)
    assert view["concept_id"] == card_rule.id
    assert f"concept={card_rule.id}" in view["href"]


def test_entry_keeps_the_rule_card_over_a_due_erratum(db_session: Session, v2, enabled) -> None:
    """Walks 6 and 7 Nov: day 2's rule card taught one rule, a slip from day 1 was due on
    another, and «Forge today's rule» opened on the slip's rule. The séance seated from the
    entry's href must start on the rule card's rule."""

    from app.services import forge_picker

    user = make_user(db_session, f"forge-443-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    upcoming = AtelierScheduler(db_session).next_new_concepts(user, limit=4, language="fr")
    assert len(upcoming) >= 2
    card_rule, slipped_rule = upcoming[1], upcoming[0]
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=slipped_rule.id,
            error_category="grammar",
            error_pattern="article",
            original_text="la appartement",
            correction="l'appartement",
            next_review_date=datetime.now(UTC) - timedelta(hours=1),
            occurrences=2,
        )
    )
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    row.plan_selection = {
        **dict(row.plan_selection or {}),
        "introduction": {"concept_id": card_rule.id, "title_native": card_rule.name},
    }
    flag_modified(row, "plan_selection")
    db_session.commit()

    today = service.get_today(user)
    assert today.forge is not None and today.forge.concept_id == card_rule.id
    # What the page does with the href: ask for a day-step séance on that concept.
    plan = forge_picker.forge_plan(
        db_session, user, preferred_concept_id=today.forge.concept_id, origin="after_day"
    )
    assert plan.units[0].concept_id == card_rule.id
    assert plan.units[0].role == "today"


def test_withdrawn_top_out_reopens() -> None:
    state = ForgeState.seance([ForgeUnit(7, "today", rung=int(core.TOP_RUNG))], length=17, review_share=0.25)
    slot = state.next_slot()
    assert slot is not None and slot.rung == int(core.TOP_RUNG)

    # A free line the local check reads as using the rule: provisionally clean at the top.
    state.record(
        concept_id=7,
        rung=slot.rung,
        verdict=Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_CORRECT),
    )
    # The model reads it: two errors. The top-out is withdrawn with the provisional step.
    state.settle(state.history[-1], Verdict.wrong())

    assert not state.tracks[0].topped
    assert not state.finished, "1 of 17 answered and the rule still has items: the séance goes on"
    assert state.next_slot() is not None


# ---------------------------------------------------------------------------
# 10 Nov walk: a séance on a rule already at Level 6 ended after one item.
#
# Day 2 forged être, which day 1 had taken to the top (Level 6). The counter
# read «1/23»; one right free line topped the rule out, and on the day's step
# a topped-out today's rule ends the séance: «Beenden» was the only button and
# the end sheet said «Früher beendet». Two numbers for one séance: the length
# the counter promised and the slots the mix would still deal.
# ---------------------------------------------------------------------------


def _answer(state: ForgeState, verdict: Verdict) -> core.Slot:
    slot = state.next_slot()
    assert slot is not None, f"no item {state.position + 1} of {state.length}: the séance ended before its minimum"
    state.record(concept_id=slot.concept_id, rung=slot.rung, verdict=verdict, fingerprint=f"item-{slot.position}")
    return slot


def test_a_days_rule_at_the_top_still_serves_the_seances_minimum() -> None:
    from app.services.forge_picker import DAY_REVIEW_SHARE

    state = ForgeState.seance([ForgeUnit(1, "today", rung=int(core.TOP_RUNG))], length=23, review_share=DAY_REVIEW_SHARE)
    _answer(state, Verdict.right())
    assert not state.finished, "one right line at Level 6 ended a séance of 23 at item 1"

    while not state.finished:
        _answer(state, Verdict.right())
    assert state.position >= core.MIN_SEANCE_ITEMS
    assert {entry["concept_id"] for entry in state.history} == {1}, "the day's step stays on today's rule"


def test_a_capped_review_does_not_end_the_day_step_early() -> None:
    """Today's rule clean at the top, a review rule still able but capped (#169): the
    séance goes on with today's rule; the review keeps to its quarter."""

    from app.services.forge_picker import DAY_REVIEW_SHARE

    state = ForgeState.seance(
        [ForgeUnit(1, "today", rung=int(core.TOP_RUNG)), ForgeUnit(2, "due", rung=1)],
        length=16,
        review_share=DAY_REVIEW_SHARE,
    )
    _answer(state, Verdict.right())
    assert not state.finished, "today's rule topped out at item 1 and the review is capped: the séance ended at 1 of 16"
    while not state.finished:
        _answer(state, Verdict.right())
    assert state.position >= core.MIN_SEANCE_ITEMS
    review = sum(1 for entry in state.history if entry["role"] != "today")
    assert review <= DAY_REVIEW_SHARE * state.position + 1e-9


def test_a_mixed_seance_goes_on_with_the_rule_still_climbing() -> None:
    """Outside the day's step the same flaw ended a séance of 12 at item 2: rule 1
    topped out, and rule 2, the only rule left, could not follow itself."""

    state = ForgeState.seance([ForgeUnit(1, "today", 5), ForgeUnit(2, "due", 0)], length=12)
    _answer(state, Verdict.right())
    _answer(state, Verdict.right())
    assert not state.finished, "rule 2 still climbs: the séance does not end at 2 of 12"
    while not state.finished:
        _answer(state, Verdict.right())
    assert [entry["concept_id"] for entry in state.history].count(1) == 1, "a rule clean at the top stays retired"
    assert state.position >= core.MIN_SEANCE_ITEMS


class _OneItemProvider:
    """A pool that can deal one item of the rule, then nothing."""

    supports_drills = False

    def __init__(self) -> None:
        self.dealt = 0

    def item_for(self, *, concept_id: int, rung: int, exclude: set[str], drill=None, accept=None):
        from app.services.forge import ForgeItem

        if self.dealt >= 1:
            return None
        self.dealt += 1
        return ForgeItem(
            concept_id=concept_id,
            rung=rung,
            round="sentence",
            mode="sentence",
            item_id="only",
            item_index=0,
            fingerprint=f"{concept_id}:sentence:sentence:only",
            payload={"id": "only", "prompt": "Écrivez une phrase."},
            drill="produce",
        )


def test_the_counter_shows_what_the_pool_could_deal(db_session: Session) -> None:
    """When the pool runs dry before the planned length, the séance ends by itself:
    its length is what it served, so the counter's last item is the one with
    «Finish», and the end sheet does not read «Finished early»."""

    from app.db.models.atelier import AtelierSession
    from app.services.forge import ForgeService, _store_state, forge_state_of
    from tests.test_atelier import _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[1], status="in_progress", quote_payload={})
    _store_state(session, ForgeState.seance([ForgeUnit(1, "today", rung=2)], length=23, review_share=0.25))
    db_session.add(session)
    db_session.commit()
    service = ForgeService(db_session, item_provider=_OneItemProvider())
    service.coach_for = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

    view = service.view(user=user, session=session)
    assert view["next"] is not None and view["length"] == 23

    state = forge_state_of(session)
    slot = state.next_slot()
    state.record(concept_id=1, rung=slot.rung, verdict=Verdict.right(), fingerprint=view["next"]["fingerprint"])
    _store_state(session, state)
    db_session.commit()

    view = service.view(user=user, session=session)
    assert view["finished"] and view["next"] is None
    assert view["length"] == view["answered"] == 1, (
        f"the séance served {view['answered']} item(s) but its counter reads «of {view['length']}»: "
        "«Finish» on item 1 of 23 is a stop button"
    )


def test_the_days_forge_on_a_level_6_rule_deals_its_minimum_from_the_bank(db_session: Session) -> None:
    """The 10 Nov walk end to end, with the real item provider: the day's séance on a
    rule at Level 6, every line right. «Finish» (``finished``) comes only on the
    counter's last item, and that item is at least the séance's minimum."""

    from app.services.forge import ForgeService, _store_state, forge_state_of
    from app.services.forge_picker import DAY_REVIEW_SHARE
    from tests.test_forge_integration import _forge_session

    user, concept, session, _shared = _forge_session(db_session, "FR_A2_NEG_001")
    state = ForgeState.seance([ForgeUnit(concept.id, "today", rung=int(core.TOP_RUNG))], length=23, review_share=DAY_REVIEW_SHARE)
    _store_state(session, state)
    db_session.add(session)
    db_session.commit()
    service = ForgeService(db_session)

    counters: list[tuple[int, int, bool]] = []
    for _ in range(30):
        view = service.view(user=user, session=session)
        if view["finished"]:
            break
        item = view["next"]
        assert item is not None
        state = forge_state_of(session)
        state.record(concept_id=concept.id, rung=int(item["rung"]), verdict=Verdict.right(), fingerprint=item["fingerprint"])
        _store_state(session, state)
        db_session.commit()
        after = service.view(user=user, session=session)
        counters.append((after["answered"], after["length"], after["finished"]))

    answered, length, finished = counters[-1]
    assert finished and answered == length, f"«Finish» at {answered} of {length}"
    assert answered >= core.MIN_SEANCE_ITEMS, f"the day's séance on a Level 6 rule ended at item {answered}"
    assert all(not done for _n, _total, done in counters[:-1])
