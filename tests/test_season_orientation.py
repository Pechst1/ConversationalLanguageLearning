"""STORY-ORIENTATION / STORY-FIRST (2026-10-12): the owner's first run on a phone.

«A new learner does not know where they are or what they are in», and «many tasks
make no sense». A learner who begins on the authored season skipped the café first
day and with it the only cast intro; the season's premise was never shown; and the
first screens were warm-up drills of words from a scene not yet read. Pinned here:

1. the learner's first season day carries the premise, how to play and the faces of
   the first night, in the learner's language — and only that day does;
2. on an authored season page nothing is drilled before the scene is read;
3. GRAMMAR-DAY-ONE (#81): grammar starts on day one. The rule is one the page itself
   uses (Gus's «C'est qui, vous ?» → «je suis / tu es»), taught and practised straight
   after the ending, not shown before the learner knows where they are.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import settings
from app.db.models.user import User
from app.services import concept_life
from app.services import journey_planner as planner
from app.services.atelier import AtelierScheduler
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.journey_contracts import DayShape, StepKind
from app.services.season.intro import is_first_season_day, season_intro
from tests import test_journey_end_to_end as support
from tests.test_journey_planner import _brief
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture
from tests.test_wp78_practice_day import _dice
from tests.test_wp86_scene_floor import CAST, DRAFT, _lexicon_candidates

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def test_the_season_intro_reads_in_the_learners_language():
    intro = season_intro("s1", "de")
    assert intro and "Odile" in intro["premise_native"] and "Mistral" in intro["premise_native"]
    assert "Wohnung" in intro["premise_native"]
    assert intro["how_native"]
    ids = [row["character_id"] for row in intro["cast_intro"]]
    assert ids == ["margaux_barman", "augustin_de_roncourt", "marin_leveque", "lila_bonnet", "camille_marchand"]
    assert all(row["role_native"] and row["line_fr"] and row["line_native"] for row in intro["cast_intro"])
    assert season_intro("nope", "de") is None
    assert "·" not in season_intro("s1", "fr")["premise_native"]


def test_only_the_first_season_page_is_a_first_day():
    def ctx(day, **extra):
        return {"season": {"kind": "tentpole", "position": {"season_day": day}, **extra}}

    assert is_first_season_day(ctx(1))
    assert not is_first_season_day(ctx(2))
    assert not is_first_season_day(ctx(1, reprise={"token": "x"}))
    assert not is_first_season_day({"season": {"kind": "gap", "position": {"season_day": 1}}})
    assert not is_first_season_day(None)


def _steps_before_first_scene(journey: dict) -> list[dict]:
    steps = journey.get("steps") or []
    first_scene = next(index for index, step in enumerate(steps) if step.get("kind") == "scene")
    return steps[:first_scene]


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_day_one_says_where_you_are_and_reads_the_scene_first(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client, support.register(assembled_client, f"s1-orient-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session
    )
    d.create()
    day_one = d.journey
    assert day_one["story_premise_native"] and "Odile" in day_one["story_premise_native"]
    assert day_one["story_how_native"]
    assert [row["character_id"] for row in day_one["cast_intro"]][:1] == ["margaux_barman"]
    assert not [step for step in _steps_before_first_scene(day_one) if step.get("kind") == "recall"], (
        "nothing is drilled before the first page is read"
    )
    d.play(answer="Odile, c'est ma grand-mère.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    day_two = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    assert day_two["story_premise_native"] is None and day_two["cast_intro"] is None
    # Walk #77: from day 2 on, the scene's «Bisher» box carries the premise; on day 1
    # the intro already said it, so the scene does not say it twice.
    scene = lambda journey: next(step for step in journey["steps"] if step["kind"] == "scene")  # noqa: E731
    assert scene(day_one)["prompt"]["premise_native"] is None
    assert scene(day_two)["prompt"]["premise_native"]
    # The part of the season each page belongs to, so the client can hand over its object.
    assert scene(day_one)["prompt"]["season_part"] == {
        "season_id": "s1", "segment": "t1", "kind": "tentpole", "day_in_segment": 1,
    }
    assert scene(day_two)["prompt"]["season_part"]["segment"] == "t1"
    assert scene(day_two)["prompt"]["season_part"]["day_in_segment"] == 2


def _plan(season: dict | None):
    context = {"draft": DRAFT, "source": {"world": {"cast": CAST}}}
    if season is not None:
        context["season"] = season
    plan = planner.plan_journey(
        scenario=_brief(story_context=context, control_language="de", level_band="A2"),
        candidates=_lexicon_candidates(),
        practice=True,
        dice=_dice(),
        day_shape=DayShape.STANDARD,
    )
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    return plan, kinds[: kinds.index(StepKind.SCENE)]


def test_an_authored_page_is_read_before_anything_is_drilled():
    _plan_, before = _plan(None)
    assert StepKind.RECALL in before, "a generated day still opens on its warm-ups"
    plan, before = _plan({"kind": "tentpole", "position": {"season_day": 1}})
    assert StepKind.RECALL not in before, plan.rationale
    assert any(step.kind is StepKind.RECALL for step in plan.steps), "the drills come after the scene"


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_the_first_day_is_the_story_then_la_forge_then_the_words(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    """GENTLE-ONBOARDING (owner, 2026-10-12): «la forge and vocab should also start
    day one, but as second and third after the story». Even on Soutenu, whose days
    fold La Forge into the story, the first day folds nothing in: the forge is the
    after-day entry, and from day 2 the rhythm folds it as before."""

    from app.db.models.user import User

    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    email = f"s1-gentle-{uuid.uuid4()}@example.com"
    headers = support.register(assembled_client, email, cefr="A2.1")
    user = db_session.get(User, support.learner_id(db_session, email))
    user.daily_goal_minutes = 20  # Soutenu: La Forge is folded into an ordinary day
    user.daily_pace = None  # a rhythm learner: no round-3 pace picked
    db_session.commit()
    d = support.Driver(assembled_client, headers, db=db_session)
    d.create()
    day_one = d.journey
    assert day_one["cast_intro"], "the first day meets the cast"
    kinds = [step["kind"] for step in day_one["steps"]]
    assert not {"forge", "read", "desk"} & set(kinds), kinds
    today = d.today()
    assert today["forge"] and today["forge"]["folded"] is False, "La Forge follows the story on day 1"
    assert today["forge"]["href"]
    d.play(answer="Odile, c'est ma grand-mère.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    day_two_today = d.today()
    assert day_two_today["forge"]["folded"] is True, "from day 2 the rhythm folds La Forge again"


@pytest.fixture
def catalogue_v2(monkeypatch, db_session):
    """The production catalogue (v2, FR2_* units), seeded; v1 is restored afterwards."""

    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    db_session.commit()
    yield
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_grammar_starts_on_day_one_with_a_rule_from_the_page(
    assembled_client, db_session, journey_enabled, clock, season_on, catalogue_v2, monkeypatch  # noqa: F811
):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client, support.register(assembled_client, f"s1-gram-{uuid.uuid4()}@example.com", cefr="A1.1"), db=db_session
    )
    d.create()
    steps = d.journey["steps"]
    kinds = [step["kind"] for step in steps]
    assert kinds[:3] == ["scene", "respond", "resolution"], kinds
    rules = [step for step in steps if step["kind"] == "rule"]
    assert len(rules) == 1, kinds
    rule = rules[0]["prompt"]
    assert not rule.get("review")
    assert "être" in rule["title_fr"]
    page_lines = [line for line in (rule["rule_card"].get("example") or {}).values() if isinstance(line, str)]
    assert any("C'est" in line for line in page_lines), "the rule's example is a line of the page"
    guided = [step for step in steps[kinds.index("rule") + 1 :] if step["kind"] == "recall"]
    assert len(guided) >= 2 and all(
        (step["prompt"].get("target") or {}).get("kind") == "grammar" for step in guided[:2]
    ), "the rule is practised, not just shown"
    reply_targets = steps[kinds.index("respond")]["prompt"]["targets"]
    assert not [t for t in reply_targets if t.get("kind") == "grammar"], "the reply does not ask for a rule not yet taught"
    d.play(answer="Odile, c'est ma grand-mère.")
    assert d.finish("complete").status_code == 200


def test_a_page_introduces_only_a_unit_it_uses(db_session, catalogue_v2):
    user = User(
        id=uuid.uuid4(), email=f"s1-units-{uuid.uuid4().hex}@example.com", hashed_password="x",
        native_language="en", target_language="fr", proficiency_level="A1", cefr_estimate="A1.1",
        daily_goal_minutes=10,
    )
    db_session.add(user)
    db_session.commit()
    upcoming = AtelierScheduler(db_session).next_new_concepts(user, limit=4, language="fr")
    assert len(upcoming) >= 2
    second = str(upcoming[1].external_id)
    brief = concept_life.introduction_for_today(db_session, user, units=[second, "FR2_NOT_A_UNIT"])
    assert brief is not None and brief["concept_id"] == upcoming[1].id
    assert concept_life.introduction_for_today(db_session, user, units=[]) is None
    assert concept_life.introduction_for_today(db_session, user, units=["FR2_NOT_A_UNIT"]) is None


def test_season_part_reads_the_scene_payload_and_nothing_else():
    from app.services.story_archive import season_part_of

    payload = {"season": {"id": "s1", "season_id": "s1", "segment": "g2", "kind": "gap", "day_in_segment": 3, "key": "g2.3"}}
    assert season_part_of(payload) == {"season_id": "s1", "segment": "g2", "kind": "gap", "day_in_segment": 3}
    assert season_part_of({"season": {"id": "s1", "segment": "t1", "kind": "odd"}})["kind"] is None
    assert season_part_of({}) is None
    assert season_part_of({"season": {"segment": None}}) is None
    assert season_part_of(None) is None
