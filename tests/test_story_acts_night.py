"""Phase 2 «Folge in Akten», PR 2: the night writes the acts after the day's first.

The night's page is the day's first act («Le fil»). With ``ATELIER_STORY_ACTS`` on for a
learner, the night then writes «Le soir» and, on Intensif, «À côté» — as many as the
learner's rhythm and pace can play — each written against the first act alone, read by
the story critic as an act, and dropped when it is refused
(``living_story.generate_act``, ``story_split.act_context``). Each act is stored like the
page, under the day's key, and billed when it is served or when it expires
(``story_acts.write_act``, ``journey_latency.sweep_expired_prefetches``).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import journey_latency, story_acts, story_split
from app.services import living_story as engine
from app.services.journey_contracts import ContentUnavailable, InputMode
from app.services.journey_latency import (
    PREFETCH_DISCARDED_EVENT,
    PREFETCH_EVENT,
    prefetch_scene_for,
    sweep_expired_prefetches,
    take_prefetched_scene,
)
from app.services.season.director import STORY_CRITIC, StoryReview, critic_payload, review_verdict
from app.services.story_acts import ACT_PREFETCH_EVENT
from app.tasks import journey_prefetch
from tests import test_journey_end_to_end as support
from tests.test_journey_latency import make_brief, make_user
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import SplitProvider, _learner_on_gap_day

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


# ---------------------------------------------------------------------------
# The writer: a later act through the planner, the author, the aids and the critic
# ---------------------------------------------------------------------------


class ActProvider(SplitProvider):
    """The split fake, planning and writing a later act when the planner is told one."""

    def __init__(self) -> None:
        super().__init__()
        self.act_repeats_lead_once = False

    def _plan(self, source: dict) -> dict:
        act = source.get("act")
        if not act:
            return super()._plan(source)
        first = act["first_act"]
        lead = "marin_leveque" if first["lead_id"] != "marin_leveque" else "lila_bonnet"
        if self.act_repeats_lead_once or act.get("shape") == "two_hander":
            # A two-hander's act goes on with its one voice (``story_split.ACT_SHAPE_RULES``).
            self.act_repeats_lead_once = False
            lead = first["lead_id"]
        place = "le_mistral" if first["location_id"] != "le_mistral" else "quai_de_valmy"
        if act.get("shape") == "bottle":
            place = act["room"]
        n = len(self.plans)
        plan = {
            "premise_id": None,
            "location_id": place,
            "cast": [lead],
            "lead_id": lead,
            "beats": ["Marin tunes the old radio.", "A song from Odile's youth plays.", "Marin turns it down."],
            "change": {"before": "The radio is silent.", "after": "The radio plays Odile's song."},
            "question": "Which song should Marin play tonight?",
            "task": "Marin asks which song to play tonight.",
            "replies": [{"gist": "a song", "intent": "other", "then": "Marin plays it"}],
            "hook": "Odile hears the song through the wall." if act["role"] == "soir" else "",
            "chapter": None,
            "threads": ["Odile's songs"],
            "small_moment_id": None,
            "complication": None,
            "callback_id": None,
            "learner_agency": None,
            "novelty_key": f"la-radio-{n}",
            "problem_key": "evening_radio",
        }
        self.plans.append(plan)
        return plan

    def _text(self, source: dict) -> dict:
        if not source.get("act"):
            return super()._text(source)
        lead = source["plan"]["lead_id"]
        return {
            "title_fr": "La radio du soir",
            "premise_fr": "Le soir, une vieille radio joue une chanson d'Odile.",
            "panels": [
                {"visual_direction": "An old radio on the zinc.", "narration_fr": "Le soir tombe sur le café.", "dialogue": []},
                {"visual_direction": "Marin turns the dial.", "narration_fr": "", "dialogue": [{"character_id": lead, "text_fr": "Elle marche encore !", "mood": "happy"}]},
                {"visual_direction": "A song fills the room.", "narration_fr": "Une vieille chanson.", "dialogue": []},
                {"visual_direction": "Marin turns to Toi.", "narration_fr": "", "dialogue": [{"character_id": lead, "text_fr": "On écoute laquelle ?", "mood": "neutral"}]},
            ],
            "opening_line_fr": "Tu veux écouter quelle chanson ?",
            "suggested_response_fr": "Une chanson triste.",
            "hook_fr": "Odile entend la chanson à travers le mur." if source["act"]["role"] == "soir" else "",
            "chapter_title_fr": None,
            "chapter_question_fr": None,
        }


@pytest.fixture
def acts_writer(season_on, monkeypatch):  # noqa: F811 - the fixture above
    fake = ActProvider()
    fake.critic_refusals_left = 0
    monkeypatch.setattr(engine, "_client", lambda: fake)
    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)
    # Every chapter dealt standard: a bottle and a two-hander keep a room or a voice
    # (tested below).
    monkeypatch.setattr(engine, "SHAPE_DECK", ("standard",))
    return fake


def _first_act(db_session, user):
    with engine.written_ahead_of_time():
        first = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(first, ContentUnavailable), first
    return first


def _act(db_session, user, first, role: str = "soir"):
    with engine.written_ahead_of_time():
        return engine.generate_act(db_session, user=user, first=first, role=role)


def _payloads(provider, schema: str) -> list[dict]:
    return [payload for name, payload in provider.calls if name == schema]


def test_le_soir_is_written_against_the_day_s_first_act_and_moves_no_season(
    assembled_client, db_session, journey_enabled, clock, acts_writer
):
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()

    act = _act(db_session, user, first)

    assert not isinstance(act, ContentUnavailable), act
    assert act.story_context["act"] == {"role": "soir", "first_scenario_key": first.scenario_key}
    assert "season" not in act.story_context, "only the day's first act takes the season's step"
    assert act.character_id != first.character_id and act.location_id != first.location_id
    assert act.title_fr != first.title_fr

    [planner] = _payloads(acts_writer, "PagePlan")
    assert planner["act"]["role"] == "soir"
    assert planner["act"]["first_act"]["lead_id"] == first.character_id
    today = planner["brief"]["today"]
    assert today["required_premise"] is None and today["premises"] == [] and today["beat"] is None
    assert planner["brief"]["chapter"]["open_new"] is False, "the act goes on in the first act's chapter"
    [author] = _payloads(acts_writer, "PageText")
    assert set(author["act"]["first_act"]) == {"title_fr", "premise_fr", "lead_id", "location_id", "question_fr"}
    [critic] = _payloads(acts_writer, "StoryReview")
    assert critic["act"]["role"] == "soir"
    assert critic["recent_days"][-1]["character_id"] == first.character_id, "the first act reads as the day before"


def test_an_act_planned_with_the_first_act_s_lead_costs_only_a_new_plan(
    assembled_client, db_session, journey_enabled, clock, acts_writer
):
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()
    acts_writer.act_repeats_lead_once = True

    act = _act(db_session, user, first)

    assert not isinstance(act, ContentUnavailable), act
    schemas = [name for name, _ in acts_writer.calls if name != "StoryReview"]
    assert schemas == ["PagePlan", "PagePlan", "PageText", "PageAids"], "no French was paid for the plan"
    second = _payloads(acts_writer, "PagePlan")[1]
    assert any("leads the first act today" in hint for hint in second["previous_rejections"])


def test_an_act_the_critic_refuses_is_dropped_never_served(
    assembled_client, db_session, journey_enabled, clock, acts_writer
):
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()
    acts_writer.critic_refusals_left = 99

    act = _act(db_session, user, first)

    assert isinstance(act, ContentUnavailable)
    assert act.reason == "story_critic_refused"
    reviews = _payloads(acts_writer, "StoryReview")
    assert len(reviews) >= 2, "a refusal buys a new plan, as on the page"
    assert len(_payloads(acts_writer, "PagePlan")) == len(reviews)
    db_session.commit()  # as ``story_acts.write_act`` does with a dropped act
    failed = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == user.id, PilotEvent.event_type == "journey_story_generation_failed"
        )
    ).all()
    assert failed, "the spend on a dropped act is recorded where the week's guardrail sees it"


def test_a_page_written_live_has_no_act_after_it(assembled_client, db_session, journey_enabled, clock, acts_writer):
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()

    act = engine.generate_act(db_session, user=user, first=first, role="soir")

    assert isinstance(act, ContentUnavailable) and act.reason == "act_not_on_a_planned_day"
    assert acts_writer.calls == [], "nothing is paid for"


def test_a_tentpole_day_plays_one_act(assembled_client, db_session, journey_enabled, clock, acts_writer):
    user = _learner_on_gap_day(assembled_client, db_session, day=1)  # T1 A
    first = SimpleNamespace(scenario_key="story_t1", story_context={"draft": {"panels": [{"narration_fr": "Le café."}]}})

    act = _act(db_session, user, first)

    assert isinstance(act, ContentUnavailable) and act.reason == "act_not_on_a_gap_day"
    assert acts_writer.calls == []


def test_a_bottle_chapter_s_act_stays_in_its_room_with_someone_else(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    monkeypatch.setattr(engine, "SHAPE_DECK", ("bottle",))
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()

    act = _act(db_session, user, first)

    assert not isinstance(act, ContentUnavailable), act
    assert act.location_id == first.location_id, "a bottle keeps its room"
    assert act.character_id != first.character_id, "someone else comes into it"
    [planner] = _payloads(acts_writer, "PagePlan")
    assert planner["act"]["shape"] == "bottle" and planner["act"]["room"] == first.location_id
    [critic] = _payloads(acts_writer, "StoryReview")
    assert critic["act"]["shape"] == "bottle"


def test_a_two_hander_s_evening_goes_on_with_its_one_voice_somewhere_else(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    monkeypatch.setattr(engine, "SHAPE_DECK", ("two_hander",))
    user = _learner_on_gap_day(assembled_client, db_session)
    first = _first_act(db_session, user)
    acts_writer.calls.clear()

    act = _act(db_session, user, first)

    assert not isinstance(act, ContentUnavailable), act
    assert act.character_id == first.character_id, "a two-hander keeps its one voice"
    assert act.location_id != first.location_id
    [planner] = _payloads(acts_writer, "PagePlan")
    assert planner["act"]["shape"] == "two_hander"


def test_a_two_hander_has_no_side_thread(assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch):
    monkeypatch.setattr(engine, "SHAPE_DECK", ("two_hander",))
    user = _learner_on_gap_day(assembled_client, db_session)
    first = SimpleNamespace(scenario_key="story_g", story_context={"draft": {"panels": [{"narration_fr": "Le café."}]}})

    act = _act(db_session, user, first, role="cote")

    assert isinstance(act, ContentUnavailable) and act.reason == "act_not_in_a_two_hander"
    assert acts_writer.calls == [], "nothing is paid for"


def test_an_act_needs_a_written_first_act():
    first = SimpleNamespace(scenario_key="story_authored", story_context={})
    act = engine.generate_act(None, user=SimpleNamespace(id=uuid.uuid4()), first=first, role="soir")
    assert isinstance(act, ContentUnavailable) and act.reason == "act_without_a_written_page"


def test_a_page_and_its_act_are_written_ahead_end_to_end(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "*")
    user = _learner_on_gap_day(assembled_client, db_session)
    user.daily_goal_minutes = 30  # Intensif: an A2 learner's day plays «Le soir»
    db_session.commit()

    assert prefetch_scene_for(db_session, user, input_mode=InputMode.TEXT) == "prefetched"
    page = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == PREFETCH_EVENT)
    ).one()
    assert story_acts.roles_to_write(db_session, user) == ["soir"]

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"

    [row] = story_acts.act_rows(db_session, user, prefetch_id=str(page.id))
    assert row.entity_id == page.entity_id, "the act is stored under the day's key"
    act = journey_latency._brief_codec()[1](dict(row.payload["brief"]))
    assert act.story_context["act"]["role"] == "soir"
    assert act.character_id != journey_latency._brief_codec()[1](dict(page.payload["brief"])).character_id


# ---------------------------------------------------------------------------
# The night's bookkeeping: the switch, the page, the rhythm, the week
# ---------------------------------------------------------------------------


@pytest.fixture()
def night(monkeypatch: pytest.MonkeyPatch):
    """The prefetch and the acts switched on for everyone, a settable story revision, and
    a page and an act written by fakes that count their calls."""

    for name, value in (
        ("ATELIER_JOURNEY_PREFETCH_ENABLED", True),
        ("ATELIER_STORY_ENGINE_ENABLED", True),
        ("ATELIER_DAILY_JOURNEY_ENABLED", True),
        ("ATELIER_DAILY_JOURNEY_COHORT", ""),
        ("APP_ENV", "test"),
        ("ATELIER_STORY_ACTS", True),
        ("ATELIER_STORY_ACTS_COHORT", "*"),
        ("PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD", 0.0),
    ):
        monkeypatch.setattr(settings, name, value, raising=False)
    state = {"revision": "rev-1", "acts": [], "act_result": None}
    monkeypatch.setattr(engine, "story_revision", lambda db, user: state["revision"])
    monkeypatch.setattr(engine, "generate_scene", lambda db, *, user, input_mode: make_brief())

    def fake_generate_act(db, *, user, first, role, now=None):
        state["acts"].append(role)
        if state["act_result"] is not None:
            return state["act_result"]
        brief = make_brief(f"story_act_{role}")
        return replace(
            brief,
            story_context={**brief.story_context, "act": {"role": role, "first_scenario_key": first.scenario_key}},
        )

    monkeypatch.setattr(engine, "generate_act", fake_generate_act)
    return state


def _learner(db_session, *, minutes: int = 30, cefr: str = "B1.1") -> User:
    user = make_user(db_session, f"acts-{uuid.uuid4().hex[:8]}@example.com")
    user.daily_goal_minutes = minutes
    user.cefr_estimate = cefr
    db_session.commit()
    return user


def _page(db_session, user) -> PilotEvent:
    assert prefetch_scene_for(db_session, user) == "prefetched"
    return db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == PREFETCH_EVENT)
    ).one()


def _act_rows(db_session, user) -> list[PilotEvent]:
    return list(
        db_session.scalars(
            select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == ACT_PREFETCH_EVENT)
        ).all()
    )


@pytest.mark.parametrize(
    ("minutes", "cefr", "roles"),
    [
        (10, "B1.1", []),  # Régulier plays «Le fil» alone
        (20, "B1.1", ["soir"]),
        (20, "A2.1", []),  # a band that composes slowly gets fewer acts
        (30, "A2.1", ["soir"]),
        (30, "B1.1", ["soir", "cote"]),  # «Le soir» first: «À côté» never plays without it
    ],
)
def test_the_night_writes_the_acts_the_learner_s_rhythm_plays(db_session, night, minutes, cefr, roles):
    assert story_acts.roles_to_write(db_session, _learner(db_session, minutes=minutes, cefr=cefr)) == roles


def test_acts_need_the_switch_and_its_cohort(db_session, night, monkeypatch):
    user = _learner(db_session)
    assert story_acts.acts_enabled_for(user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "someone-else@example.com")
    assert not story_acts.acts_enabled_for(user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", f"someone-else@example.com, {user.email.upper()}")
    assert story_acts.acts_enabled_for(user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "")
    assert story_acts.acts_enabled_for(user), "an empty cohort is everyone in development"
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert not story_acts.acts_enabled_for(user), "and nobody in production"
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "*")
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    assert not story_acts.acts_enabled_for(user)
    page = _page(db_session, user)
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "skipped_disabled"
    assert night["acts"] == []


def test_le_soir_is_stored_under_the_day_s_key_and_written_once(db_session, night):
    user = _learner(db_session)
    page = _page(db_session, user)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "cached"

    assert night["acts"] == ["soir"], "the same act twice never pays twice"
    [row] = _act_rows(db_session, user)
    assert row.entity_id == page.entity_id
    assert row.payload["prefetch_id"] == str(page.id) and row.payload["role"] == "soir"
    assert row.cost_usd == 0.0, "billed when served or when it expires, as the page"
    assert [item["role"] for item in story_acts.act_payloads([row])] == ["soir"]


def test_no_act_is_written_after_a_page_that_was_served_or_moved(db_session, night):
    served = _learner(db_session)
    page = _page(db_session, served)
    assert take_prefetched_scene(db_session, served) is not None
    db_session.commit()
    assert story_acts.write_act(db_session, served, prefetch_id=str(page.id), role="soir") == "skipped_stale"

    moved = _learner(db_session)
    page = _page(db_session, moved)
    night["revision"] = "rev-2"
    assert story_acts.write_act(db_session, moved, prefetch_id=str(page.id), role="soir") == "skipped_stale"

    other = _learner(db_session)
    assert story_acts.write_act(db_session, other, prefetch_id=str(page.id), role="soir") == "skipped_stale"
    assert story_acts.write_act(db_session, other, prefetch_id="not-a-row", role="soir") == "skipped_stale"
    assert night["acts"] == []


def test_an_act_the_rhythm_no_longer_plays_is_not_written(db_session, night):
    user = _learner(db_session, minutes=30)
    page = _page(db_session, user)
    user.daily_goal_minutes = 10
    db_session.commit()

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "skipped_rhythm"
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="fil") == "skipped_rhythm"
    assert night["acts"] == []


def test_the_week_s_guardrail_counts_what_the_night_wrote_and_nobody_billed(db_session, night, monkeypatch):
    # The page and every act cost 0.004 (``make_brief``). With the page written, «Le soir»
    # fits under 0.01; with «Le soir» written too, «À côté» would not.
    monkeypatch.setattr(settings, "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD", 0.01)
    user = _learner(db_session)
    page = _page(db_session, user)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="cote") == "skipped_budget"
    assert night["acts"] == ["soir"]


def test_the_service_s_day_stops_the_acts(db_session, night, monkeypatch):
    from app.services import spend_guard

    user = _learner(db_session)
    page = _page(db_session, user)
    monkeypatch.setattr(spend_guard, "service_budget_reached", lambda db, **kwargs: True)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "skipped_budget"
    assert night["acts"] == []


def test_the_service_s_day_counts_what_the_night_wrote_and_nobody_billed(db_session, night, monkeypatch):
    # Nothing is on a ledger yet: every page and act waits, unbilled, at 0.004 each
    # (``make_brief``). Two learners' pages and «Le soir» make 0.012; one more act would
    # take the service's day past 0.015.
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", 0.015)
    user, someone = _learner(db_session), _learner(db_session)
    page = _page(db_session, user)
    _page(db_session, someone)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="cote") == "skipped_budget"
    assert night["acts"] == ["soir"]


def test_no_act_is_written_after_a_page_that_expired_and_was_written_again(db_session, night):
    user = _learner(db_session)
    expired = _page(db_session, user)
    expired.occurred_at = datetime.now(UTC) - timedelta(
        seconds=settings.ATELIER_JOURNEY_PREFETCH_TTL_SECONDS + 3600
    )
    db_session.commit()
    # The same key, a new page: the act belongs to the page it was queued for.
    assert prefetch_scene_for(db_session, user) == "prefetched"

    assert story_acts.write_act(db_session, user, prefetch_id=str(expired.id), role="soir") == "skipped_stale"
    assert night["acts"] == []


@pytest.mark.parametrize(
    ("reason", "status"),
    [("story_critic_refused", "unavailable"), ("act_not_on_a_gap_day", "skipped_day"), ("act_not_in_a_two_hander", "skipped_day")],
)
def test_an_act_that_is_not_written_stores_nothing(db_session, night, reason, status):
    night["act_result"] = ContentUnavailable(reason=reason)
    user = _learner(db_session)
    page = _page(db_session, user)

    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == status
    assert _act_rows(db_session, user) == []


def test_an_expired_act_is_swept_and_billed_past_rows_already_closed(db_session, night):
    user, someone = _learner(db_session), _learner(db_session)
    old = datetime.now(UTC) - timedelta(days=3)
    # More closed rows than one read takes, all older than the act: the sweep pages on.
    for index in range(4):
        closed = PilotEvent(
            user_id=someone.id,
            event_type=PREFETCH_EVENT,
            entity_type="journey_scene_prefetch",
            entity_id=f"old-key-{index}",
            payload={"cache_key": f"old-key-{index}"},
            cost_usd=0.0,
            occurred_at=old - timedelta(hours=index + 1),
        )
        db_session.add(closed)
        db_session.flush()
        journey_latency._mark(db_session, closed, journey_latency.PREFETCH_CONSUMED_EVENT, reason="served")
    page = _page(db_session, user)
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    [act] = _act_rows(db_session, user)
    for row in (page, act):
        row.occurred_at = old
    db_session.commit()

    assert sweep_expired_prefetches(db_session, limit=3) == 2
    assert sweep_expired_prefetches(db_session, limit=3) == 0
    billed = {
        row.entity_id: row
        for row in db_session.scalars(
            select(PilotEvent).where(
                PilotEvent.user_id == user.id,
                PilotEvent.event_type == PREFETCH_DISCARDED_EVENT,
                PilotEvent.entity_id.in_([str(page.id), str(act.id)]),
            )
        ).all()
    }
    assert set(billed) == {str(page.id), str(act.id)}
    assert billed[str(act.id)].payload["reason"] == "expired"
    assert billed[str(act.id)].cost_usd == pytest.approx(0.004)


def test_a_row_past_the_sweep_window_is_left_alone(db_session, night):
    user = _learner(db_session)
    db_session.add(
        PilotEvent(
            user_id=user.id,
            event_type=ACT_PREFETCH_EVENT,
            entity_type=story_acts.ACT_ENTITY_TYPE,
            entity_id="ancient-key",
            payload={"cache_key": "ancient-key"},
            cost_usd=0.0,
            occurred_at=datetime.now(UTC) - journey_latency.SWEEP_WINDOW - timedelta(days=3),
        )
    )
    db_session.commit()
    assert sweep_expired_prefetches(db_session) == 0


# ---------------------------------------------------------------------------
# The queue: one task per act, «Le soir» first, the chain ends at an act not written
# ---------------------------------------------------------------------------


@pytest.fixture()
def broker(monkeypatch):
    queued: list[list] = []
    monkeypatch.setitem(journey_prefetch.celery_app.conf, "task_always_eager", False)
    monkeypatch.setattr(
        journey_prefetch.write_story_acts, "apply_async", lambda args, **kw: queued.append(list(args))
    )
    return queued


def test_the_night_queues_le_soir_first_after_the_page(db_session, night, broker):
    user = _learner(db_session)
    page = _page(db_session, user)

    assert journey_prefetch.queue_story_acts(db_session, user)

    assert broker == [[str(user.id), str(page.id), ["soir", "cote"]]]


def test_nothing_is_queued_without_the_switch_a_worker_or_an_act_to_write(db_session, night, broker, monkeypatch):
    regulier = _learner(db_session, minutes=10)
    _page(db_session, regulier)
    assert not journey_prefetch.queue_story_acts(db_session, regulier), "Régulier plays one act"

    user = _learner(db_session)
    assert not journey_prefetch.queue_story_acts(db_session, user), "no page waiting"
    _page(db_session, user)
    monkeypatch.setitem(journey_prefetch.celery_app.conf, "task_always_eager", True)
    assert not journey_prefetch.queue_story_acts(db_session, user), "eager dev has no worker"
    monkeypatch.setitem(journey_prefetch.celery_app.conf, "task_always_eager", False)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    assert not journey_prefetch.queue_story_acts(db_session, user)
    assert broker == []


@pytest.mark.parametrize(
    ("status", "next_queued"),
    [("prefetched", True), ("cached", True), ("unavailable", False), ("skipped_budget", False)],
)
def test_the_next_act_is_only_queued_once_the_one_before_it_stands(monkeypatch, broker, status, next_queued):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    written: list[str] = []

    class Db:
        def get(self, model, user_id):
            return SimpleNamespace(id=user_id)

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(journey_prefetch, "SessionLocal", Db)
    monkeypatch.setattr(
        story_acts, "write_act", lambda db, user, *, prefetch_id, role: written.append(role) or status
    )
    user_id = str(uuid.uuid4())

    result = journey_prefetch.write_story_acts(user_id, "page-id", ["soir", "cote"])

    assert result == {"status": status, "role": "soir"}
    assert written == ["soir"], "one act per task"
    assert broker == ([[user_id, "page-id", ["cote"]]] if next_queued else [])


def test_the_batch_queues_the_acts_after_each_page_it_writes(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS", 25)

    class Db:
        def get(self, model, user_id):
            return user_id

        def rollback(self):
            pass

        def close(self):
            pass

    statuses = {"a": "prefetched", "b": "cached", "c": "prefetched"}
    queued: list[str] = []
    monkeypatch.setattr(journey_prefetch, "SessionLocal", Db)
    monkeypatch.setattr(journey_prefetch, "sweep_expired_prefetches", lambda db: 0)
    monkeypatch.setattr(journey_prefetch, "_active_learner_ids", lambda db, **kw: list(statuses))
    monkeypatch.setattr(journey_prefetch, "prefetch_enabled_for", lambda user: True)
    monkeypatch.setattr(journey_prefetch, "prefetch_scene_for", lambda db, user, **kw: statuses[user])
    monkeypatch.setattr(journey_prefetch, "queue_story_acts", lambda db, user: queued.append(user) or True)

    result = journey_prefetch.prefetch_next_journey_scenes()

    assert queued == ["a", "c"], "acts follow a page the night just wrote"
    assert result["acts_queued"] == 2


# ---------------------------------------------------------------------------
# The act's rules, without a model
# ---------------------------------------------------------------------------


def _draft(**changes) -> dict:
    draft = {
        "title_fr": "La boîte",
        "premise_fr": "Une boîte de photos sous le lit d'Odile.",
        "objective_native": "Lila wants to know who the caption is about.",
        "objective_semantics": "A name, or a guess.",
        "character_id": "lila_bonnet",
        "location_id": "user_apartment",
        "causal_reason": "Follows the gap's thread.",
        "novelty_key": "la-boite",
        "problem_key": "polaroid_box",
        "opening_line_fr": "C'est qui, à ton avis ?",
        "chapter": {"title_fr": "La boîte", "dramatic_question": "Qu'y a-t-il dedans ?", "possible_developments": ["Des photos."]},
        "season_checklist": {
            "premise_id": "p_box",
            "threads": ["The Polaroid box"],
            "change_before": "The box is closed.",
            "change_after": "The box is open.",
            "hook_fr": "Marin veut te demander quelque chose.",
            "small_moment_id": "sm_radio",
        },
        "panels": [{"narration_fr": "Sous le lit, une boîte."}],
    }
    draft.update(changes)
    return draft


def _context() -> dict:
    return {
        "level": "A2",
        "season_script": {
            "id": "s1",
            "brief": {
                "today": {
                    "required_premise": {"id": "p_box", "title_fr": "La boîte"},
                    "beat": {"before": "closed", "after": "open", "hook": "Someone knocks at Odile's door."},
                    "premises": [{"id": "p_box"}],
                    "small_moments": [{"id": "sm_radio"}, {"id": "sm_cat"}],
                    "gate": "romance",
                    "may_set": ["user.usual_order"],
                    "open_obstacle": {"id": "ob1"},
                    "picked": "p_box",
                    "callback": {"id": "cb1"},
                    "learner_agency_rules": "rules",
                    "agreements": ["You promised Lila to keep the key."],
                },
                "gap": {"id": "g2", "threads": ["The Polaroid box", "Romy's notes"]},
                "page_rules": {"chapter": {"open_new": True}},
            },
        },
        "chapter": {"title_fr": "Avant", "dramatic_question": "?", "resolved": True},
        "recent_situations": [{"title_fr": "Hier", "character_id": "romy_tremblay"}],
        "absence": {"days": 3},
        "callback": {"id": "cb1"},
        engine.GRAMMAR_PLAN_KEY: {"unit": "passe_compose"},
        engine.EPREUVE_KEY: {"band": "A2.1"},
        "variety": {"must_change": {}},
    }


def test_a_later_act_s_context_leaves_the_season_s_day_to_the_first_act():
    context = _context()
    act = story_split.act_context(context, _draft(), "soir")

    today = act["season_script"]["brief"]["today"]
    assert today["required_premise"] is None and today["beat"] is None and today["premises"] == []
    assert today["gate"] is None and today["may_set"] == [] and today["open_obstacle"] is None
    assert not {"picked", "callback", "learner_agency_rules"} & set(today)
    assert today["agreements"] == ["You promised Lila to keep the key."], "what the learner decided stays true"
    assert today["small_moments"] == [{"id": "sm_cat"}], "the first act's small moment is taken"
    assert act["season_script"]["brief"]["page_rules"]["chapter"]["open_new"] is False
    assert act["chapter"]["title_fr"] == "La boîte", "the chapter the first act opened goes on"
    assert not {"absence", "callback", engine.GRAMMAR_PLAN_KEY, engine.EPREUVE_KEY} & set(act)
    assert act["recent_situations"][-1]["character_id"] == "lila_bonnet", "the first act reads as the day before"
    assert act["act"]["role"] == "soir" and act["act"]["day_hook"] == "Someone knocks at Odile's door."
    assert act["act"]["shape"] == "standard" and "room" not in act["act"]
    first = act["act"]["first_act"]
    assert (first["lead_id"], first["location_id"], first["question_fr"]) == ("lila_bonnet", "user_apartment", "C'est qui, à ton avis ?")
    assert first["change"] == {"before": "The box is closed.", "after": "The box is open."}
    # The day's own context is untouched: the first act's page and brief are not rewritten.
    assert context["season_script"]["brief"]["today"]["required_premise"] == {"id": "p_box", "title_fr": "La boîte"}
    assert context["season_script"]["brief"]["page_rules"]["chapter"]["open_new"] is True
    assert len(context["recent_situations"]) == 1


def test_an_open_chapter_is_kept_for_the_act():
    context = _context()
    context["chapter"] = {"title_fr": "Le carnet", "dramatic_question": "À qui ?", "possible_developments": ["Un nom."]}
    assert story_split.act_context(context, _draft(), "cote")["chapter"] == context["chapter"]


def _plan(**changes) -> story_split.PagePlan:
    plan = {
        "premise_id": None,
        "location_id": "le_mistral",
        "cast": ["marin_leveque"],
        "lead_id": "marin_leveque",
        "beats": ["One.", "Two."],
        "change": {"before": "Silent.", "after": "Playing."},
        "question": "Which song?",
        "task": "Marin asks which song to play.",
        "hook": "Odile hears it.",
    }
    plan.update(changes)
    return story_split.PagePlan.model_validate(plan)


@pytest.mark.parametrize(
    ("changes", "role", "words"),
    [
        ({"lead_id": "lila_bonnet", "cast": ["lila_bonnet"]}, "soir", "leads the first act"),
        ({"location_id": "user_apartment"}, "cote", "somewhere else"),
        ({"premise_id": "p_box"}, "cote", "premise_id is null"),
        ({"hook": ""}, "soir", "write hook"),
    ],
)
def test_a_later_act_s_plan_that_repeats_the_first_act_is_refused(changes, role, words):
    context = story_split.act_context(_context(), _draft(), role)
    assert words in (story_split.act_plan_issue(_plan(**changes), context) or "")


def test_a_later_act_s_plan_that_keeps_the_rules_passes():
    assert story_split.act_plan_issue(_plan(hook=""), story_split.act_context(_context(), _draft(), "cote")) is None
    assert story_split.act_plan_issue(_plan(), story_split.act_context(_context(), _draft(), "soir")) is None
    assert story_split.act_plan_issue(_plan(lead_id="lila_bonnet", cast=["lila_bonnet"]), _context()) is None, "a page is no act"


def _shaped(shape: str, room: str | None = None) -> dict:
    context = _context()
    context["chapter"] = {"title_fr": "Le zinc", "dramatic_question": "Qui viendra ?", "shape": shape}
    if room:
        context["chapter"]["location_id"] = room
    return context


def test_a_bottle_chapter_s_act_keeps_the_room_and_changes_the_lead():
    context = story_split.act_context(_shaped("bottle", room="le_mistral"), _draft(location_id="le_mistral"), "soir")
    assert context["act"]["shape"] == "bottle" and context["act"]["room"] == "le_mistral"

    assert story_split.act_plan_issue(_plan(), context) is None, "Marin comes into Lila's room"
    assert "bottle" in story_split.act_plan_issue(_plan(location_id="quai_de_valmy"), context)
    assert "leads the first act" in story_split.act_plan_issue(_plan(lead_id="lila_bonnet", cast=["lila_bonnet"]), context)


def test_a_bottle_the_first_act_opened_keeps_the_first_act_s_room():
    context = _context()  # yesterday's chapter is resolved: the first act opened today's
    context["chapter_shape"] = {"shape": "bottle"}
    act = story_split.act_context(context, _draft(), "cote")

    assert act["chapter"]["shape"] == "bottle" and act["chapter"]["location_id"] == "user_apartment"
    assert act["act"]["room"] == "user_apartment"
    assert story_split.act_plan_issue(_plan(location_id="user_apartment", hook=""), act) is None


def test_a_two_hander_s_act_keeps_the_lead_and_changes_the_place():
    context = story_split.act_context(_shaped("two_hander"), _draft(), "soir")
    assert context["act"]["shape"] == "two_hander" and "room" not in context["act"]
    lila = {"lead_id": "lila_bonnet", "cast": ["lila_bonnet"]}

    assert story_split.act_plan_issue(_plan(**lila), context) is None, "Lila again, at le_mistral"
    assert "two-hander" in story_split.act_plan_issue(_plan(), context)
    assert "somewhere else" in story_split.act_plan_issue(_plan(**lila, location_id="user_apartment"), context)


def test_an_act_that_breaks_its_chapter_s_shape_is_refused():
    checklist = SimpleNamespace(premise_id=None, hook_fr="Demain, Odile frappe.")
    first = {"lead_id": "lila_bonnet", "location_id": "le_mistral"}
    marin_outside = SimpleNamespace(character_id="marin_leveque", location_id="quai_de_valmy", season_checklist=checklist)
    lila_inside = SimpleNamespace(character_id="lila_bonnet", location_id="le_mistral", season_checklist=checklist)

    bottle = {"act": {"role": "soir", "first_act": first, "shape": "bottle", "room": "le_mistral"}}
    with pytest.raises(engine.StoryUnavailable, match="act_breaks_chapter_shape"):
        engine._validate_act(marin_outside, bottle)
    two_hander = {"act": {"role": "soir", "first_act": first, "shape": "two_hander"}}
    with pytest.raises(engine.StoryUnavailable, match="act_breaks_chapter_shape"):
        engine._validate_act(marin_outside, two_hander)
    with pytest.raises(engine.StoryUnavailable, match="act_repeats_first_act"):
        engine._validate_act(lila_inside, two_hander)


def test_the_planner_reads_the_act_s_rules_only_on_a_later_act():
    assert story_split.planner_system({}) == story_split.PLANNER
    assert story_split.planner_system({"act": {"role": "fil"}}) == story_split.PLANNER
    soir = story_split.planner_system({"act": {"role": "soir"}})
    assert soir.startswith(story_split.PLANNER) and "TODAY HAS MORE THAN ONE ACT" in soir and "«Le soir»" in soir
    assert "«À côté»" in story_split.planner_system({"act": {"role": "cote"}})
    assert "act.shape is" not in soir
    assert "act.shape is bottle" in story_split.planner_system({"act": {"role": "cote", "shape": "bottle"}})
    assert "act.shape is two_hander" in story_split.planner_system({"act": {"role": "soir", "shape": "two_hander"}})
    assert story_split.author_system({"level": "A2"}).count("TODAY HAS MORE THAN ONE ACT") == 0
    assert "TODAY HAS MORE THAN ONE ACT" in story_split.author_system({"level": "A2", "act": {"role": "soir"}})


def test_the_author_reads_the_first_act_as_printed_never_the_planner_s_notes():
    context = story_split.act_context(_context(), _draft(), "soir")
    author = story_split._author_act(context["act"])
    assert author == {
        "role": "soir",
        "first_act": {
            "title_fr": "La boîte",
            "premise_fr": "Une boîte de photos sous le lit d'Odile.",
            "lead_id": "lila_bonnet",
            "location_id": "user_apartment",
            "question_fr": "C'est qui, à ton avis ?",
        },
    }


def test_the_critic_reads_a_later_act_as_one_and_refuses_it_when_it_does_not_move_on():
    review = StoryReview.model_validate(
        {
            "hook": True, "stakes": True, "value_turn": True, "meaningful_change": True,
            "advances_thread": True, "in_character": True, "spoils_next_tentpole": False,
            "change_summary": "avant → après", "issues": ["It stages the first act again."],
            "accepted": True, "moves_on": False,
        }
    )
    assert review_verdict(review) is True, "the day's page is never refused for moves_on"
    assert review_verdict(review, act=True) is False
    brief = _context()["season_script"]["brief"]
    assert "act" not in critic_payload(brief, _draft())
    assert critic_payload(brief, _draft(), act={"role": "soir"})["act"] == {"role": "soir"}
    assert "When act is present" in STORY_CRITIC and "act.shape" in STORY_CRITIC


def test_an_act_with_the_first_act_s_lead_or_without_tomorrow_s_hook_is_refused():
    context = {"act": {"role": "soir", "first_act": {"lead_id": "lila_bonnet", "location_id": "user_apartment"}}}
    checklist = SimpleNamespace(premise_id="p_box", hook_fr="")

    with pytest.raises(engine.StoryUnavailable, match="act_repeats_first_act"):
        engine._validate_act(SimpleNamespace(character_id="lila_bonnet", location_id="le_mistral", season_checklist=checklist), context)
    with pytest.raises(engine.StoryUnavailable, match="act_without_hook"):
        engine._validate_act(SimpleNamespace(character_id="marin_leveque", location_id="le_mistral", season_checklist=checklist), context)
    assert checklist.premise_id is None, "only the day's first act takes the season's step"
