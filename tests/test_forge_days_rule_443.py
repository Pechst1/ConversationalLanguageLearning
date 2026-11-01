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

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Verdict
from app.db.models.daily_journey import DailyJourney
from app.services.atelier import AtelierScheduler
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import create_request, enabled, make_user  # noqa: F401 - fixture
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture


def test_the_forge_entry_opens_on_the_rule_the_day_planned(db_session: Session, v2, enabled) -> None:
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


def test_a_top_out_the_model_withdrew_does_not_leave_the_seance_finished() -> None:
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
