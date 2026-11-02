"""Phase 2 «Folge in Akten», PR 5: the limits rise with the switch, for its cohort alone,
and a day of acts still opens and plays with the cost of its night.

The night writes the page and the acts after it, and they are billed on the day they are
played (``story_acts``). So a learner the night writes acts for has caps of their own
(``ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD``, ``ATELIER_STORY_ACTS_WEEKLY_COST_GUARDRAIL_USD``),
read by every reader of the cap, and the night writes no act the learner's day or week
could no longer pay. The caps render.yaml declares are checked against the writer it
names for the night, at what the gold day surface measured that writer to cost
(``tests/gold_transcripts/runner.NIGHT_WRITER_USD``): a writer nobody measured fails here
before it writes a night.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest
import yaml
from fastapi import HTTPException

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.services import journey_latency, line_audio, panel_art, spend_guard, story_acts
from app.services import living_story as engine
from tests import test_story_acts_night as night_support
from tests.gold_transcripts import runner as R
from tests.test_journey_latency import make_brief
from tests.test_story_acts_night import _learner, _page

night = night_support.night

#: The most acts a night writes after the page: B1 on Intensif, «Le soir» and «À côté».
LATER_ACTS = 2
#: The bounds a learner's night and day are held to, as render.yaml declares them.
BOUNDS = (
    "USER_DAILY_SPEND_CAP_USD",
    "ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD",
    "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD",
    "ATELIER_STORY_ACTS_WEEKLY_COST_GUARDRAIL_USD",
    "SERVICE_DAILY_SPEND_CAP_USD",
)


def _services() -> dict[str, dict[str, dict]]:
    data = yaml.safe_load((R.S.REPO / "render.yaml").read_text(encoding="utf-8"))
    return {
        str(svc["name"]): {str(env["key"]): env for env in svc.get("envVars") or [] if "key" in env}
        for svc in data["services"]
        if svc.get("name") in ("atelier-api", "atelier-worker")
    }


def _bounds() -> dict[str, float]:
    api = R.render_values("atelier-api")
    return {key: float(api[key]) for key in BOUNDS}


def _writer() -> str:
    """The writer the night runs: the worker writes the page and the acts ahead of time."""

    return str(_services()["atelier-worker"]["STORY_WRITER_MODEL"]["value"])


def _measured() -> dict[str, float]:
    return R.NIGHT_WRITER_USD[_writer()]


def _costing(brief, usd: float):
    """``brief`` written for ``usd``: what the ledger bills it at when it is played."""

    return replace(brief, story_context={**brief.story_context, "generation_usage": [{"stage": "SceneDraft", "cost_usd": usd}]})


def _billed(db_session, user, usd: float, event_type: str = "journey_story_scene_cost") -> None:
    db_session.add(
        PilotEvent(
            user_id=user.id,
            event_type=event_type,
            entity_type="graphic_novel_scene",
            entity_id=str(uuid.uuid4()),
            payload={"stage": "test"},
            cost_usd=usd,
            occurred_at=datetime.now(UTC),
        )
    )
    db_session.commit()


@pytest.fixture
def production_bounds(monkeypatch):
    """The spend bounds as production runs them (render.yaml), panel art on its allowance."""

    for key, value in _bounds().items():
        monkeypatch.setattr(settings, key, value)
    api = R.render_values("atelier-api")
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD", float(api["ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD"]))
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_COST_USD_PER_PANEL", 0.04)
    monkeypatch.setattr(spend_guard, "service_budget_reached", lambda db, **kwargs: False)


# ---------------------------------------------------------------------------
# render.yaml: the bounds fit the writer they name
# ---------------------------------------------------------------------------


def test_the_night_s_writer_was_measured_and_the_worker_reads_the_api_s_bounds():
    services = _services()
    for name, env in services.items():
        writer = str(env["STORY_WRITER_MODEL"]["value"])
        assert writer in R.NIGHT_WRITER_USD, f"{name} writes with {writer}: measure it on the gold day surface first"
    for key in BOUNDS:
        assert "value" in services["atelier-api"][key], key
        assert services["atelier-worker"][key].get("fromService", {}).get("envVarKey") == key, (
            f"the night reads the day's {key}"
        )
    bounds = _bounds()
    assert bounds["ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD"] > bounds["USER_DAILY_SPEND_CAP_USD"]
    assert bounds["ATELIER_STORY_ACTS_WEEKLY_COST_GUARDRAIL_USD"] > bounds["PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD"]


def test_the_dearest_night_measured_leaves_its_day_the_cap_its_voices_and_its_panels():
    cost, bounds = _measured(), _bounds()
    cap = bounds["ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD"]
    dearest = cost["page"] + LATER_ACTS * cost["act_dearest"]
    pressure = float(R.render_values("atelier-api").get("ATELIER_PANEL_ART_TEXT_PRESSURE", settings.ATELIER_PANEL_ART_TEXT_PRESSURE))
    # The night writes it (``story_acts.day_holds_an_act``) …
    assert dearest + story_acts.DAY_PLAY_USD <= cap
    # … and its day still plays: the characters keep their voices to the end
    # (``line_audio.CAP_NEAR_SHARE``), the last act still gets its panels
    # (``ATELIER_PANEL_ART_TEXT_PRESSURE``).
    assert dearest + story_acts.DAY_PLAY_USD <= line_audio.CAP_NEAR_SHARE * cap
    assert dearest < pressure * cap


def test_a_week_of_nights_with_acts_still_writes_the_next_night_s_page_and_acts():
    cost, bounds = _measured(), _bounds()
    guardrail = bounds["ATELIER_STORY_ACTS_WEEKLY_COST_GUARDRAIL_USD"]
    one_night = cost["page"] + LATER_ACTS * cost["act"]
    week = 7 * (one_night + story_acts.DAY_PLAY_USD)
    # The eighth night: its page (``prefetch_scene_for``) …
    assert week < guardrail
    # … and its last act, which keeps the ninth night's page its room (``write_act``).
    assert week + cost["page"] + (LATER_ACTS - 1) * cost["act"] + 2 * cost["page"] < guardrail


# ---------------------------------------------------------------------------
# The caps rise with the switch, for its cohort alone
# ---------------------------------------------------------------------------


def test_the_caps_rise_with_the_switch_and_only_for_its_cohort(db_session, night, monkeypatch):
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 1.0)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD", 2.5)
    monkeypatch.setattr(settings, "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD", 4.0)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_WEEKLY_COST_GUARDRAIL_USD", 12.0)
    learner, other = _learner(db_session), _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", learner.email)

    assert (spend_guard.daily_cap_usd(learner), spend_guard.open_day_ceiling_usd(learner)) == (2.5, 5.0)
    assert journey_latency.weekly_guardrail_usd(learner) == 12.0
    assert spend_guard.daily_cap_usd(other) == spend_guard.daily_cap_usd() == 1.0
    assert journey_latency.weekly_guardrail_usd(other) == journey_latency.weekly_guardrail_usd() == 4.0

    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    assert spend_guard.daily_cap_usd(learner) == 1.0 and journey_latency.weekly_guardrail_usd(learner) == 4.0, (
        "the switch off, the plain caps"
    )
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", True)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 3.0)
    assert spend_guard.daily_cap_usd(learner) == 3.0, "the acts cap never lowers a cap"
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.0)
    monkeypatch.setattr(settings, "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD", 0.0)
    assert spend_guard.daily_cap_usd(learner) == 0.0 and journey_latency.weekly_guardrail_usd(learner) == 0.0, (
        "a bound that is off stays off"
    )


# ---------------------------------------------------------------------------
# A night at its dearest, and the day it was written for
# ---------------------------------------------------------------------------


def test_a_dear_night_is_written_and_its_day_still_opens_and_plays(db_session, night, production_bounds, monkeypatch):
    cost = _measured()
    monkeypatch.setattr(engine, "generate_scene", lambda db, *, user, input_mode: _costing(make_brief(), cost["page"]))
    night["act_result"] = _costing(make_brief("story_act"), cost["act_dearest"])
    user = _learner(db_session)  # B1 on Intensif: «Le soir», then «À côté»

    page = _page(db_session, user)
    roles = story_acts.roles_to_write(db_session, user)
    assert len(roles) == LATER_ACTS
    for role in roles:
        assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role=role) == "prefetched", role
    night_usd = cost["page"] + LATER_ACTS * cost["act_dearest"]
    assert story_acts._unbilled_usd(db_session, user) == pytest.approx(night_usd)

    # The morning opens the day: the creation route is held to the cap.
    spend_guard.enforce_daily_budget(db_session, user)
    # The page and the acts are billed as the day serves them, then the day is played.
    for usd in (cost["page"], *[cost["act_dearest"]] * LATER_ACTS):
        _billed(db_session, user, usd)
    assert not line_audio._cap_near(db_session, user), "the last act's panels and voices come after the bill"
    assert panel_art.affordable_panels(db_session, user, 4) > 0
    _billed(db_session, user, story_acts.DAY_PLAY_USD, "journey_story_turn_cost")
    spend_guard.enforce_daily_budget(db_session, user, open_day=True)
    spend_guard.enforce_daily_budget(db_session, user)  # a paid route outside the day (the Courrier)
    assert not line_audio._cap_near(db_session, user)

    # The same night held to the plain cap would have cost the learner the rest of the day.
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    with pytest.raises(HTTPException) as refused:
        spend_guard.enforce_daily_budget(db_session, user)
    assert refused.value.status_code == 429


def test_the_night_writes_no_act_its_day_could_not_pay(db_session, night, monkeypatch):
    # The page and every act cost 0.004 (``make_brief``). Under 0.16 a day holds the page,
    # «Le soir» and the day's play (0.158), not «À côté» as well (0.162).
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", story_acts.DAY_PLAY_USD + 0.01)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD", 0.0)
    user = _learner(db_session)
    page = _page(db_session, user)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="cote") == "skipped_budget"
    assert night["acts"] == ["soir"]

    # What the learner's day has already cost counts too, and the acts cap makes room.
    someone = _learner(db_session)
    other_page = _page(db_session, someone)
    _billed(db_session, someone, 0.01, "journey_story_generation_failed")
    assert story_acts.write_act(db_session, someone, prefetch_id=str(other_page.id), role="soir") == "skipped_budget"
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_DAILY_SPEND_CAP_USD", 1.0)
    assert story_acts.write_act(db_session, someone, prefetch_id=str(other_page.id), role="soir") == "prefetched"
