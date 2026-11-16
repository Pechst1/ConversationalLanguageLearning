"""#147: what a learner reads about the cast is limited to the people they have met.

Live walk 8 Nov 2026, a drill on day 1: «Say it in French: “Romy and I send a letter.”». The coach
gate already kept Romy's face away; the item's text did not, and the rule card's speaker still
said Romy on 50 cards. Romy is first on a page at T4 A.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from app.services import cast_registry, forge, forge_coaches, item_bank, journey_learning
from app.services.cast_registry import met_ids, season_reach, unmet_named
from app.services.forge_coaches import card_for_learner, names_unmet, only_met, recast_scene
from app.services.rule_cards import _cards, rule_card_for
from app.services.season.clock import SEASON_KEY

ROMY = "romy_tremblay"
FIRST_PAGE = {"margaux_barman", "augustin_de_roncourt", "marin_leveque", "lila_bonnet"}
A_ROMY_UNIT = "FR2_A11_QUESTIONS"


def _state(*played: tuple[str, int]) -> dict:
    rows = [{"segment": segment, "day_in_segment": day} for segment, day in played]
    return {"relationships": {}, "living_story": {SEASON_KEY: {"id": "s1", "played": rows, "flags": {}}}}


DAY_ONE = _state(("t1", 1))
BEFORE_ANY_SCENE = _state()
AFTER_T4 = _state(("t4", 1))


# --------------------------------------------------------------------------- #
# Who has been met
# --------------------------------------------------------------------------- #


def test_a_season_with_no_settled_day_stands_on_its_first_page():
    """Day 1, before the day settles, La Forge was told «nothing can tell» and let all through."""

    assert season_reach(BEFORE_ANY_SCENE) == (1, "a")
    assert met_ids(BEFORE_ANY_SCENE) == FIRST_PAGE
    assert season_reach({"relationships": {}}) is None
    assert met_ids({"living_story": {"day_index": 4}}) is None


def test_unmet_named_reads_a_text():
    assert unmet_named(DAY_ONE, "Romy et moi envoyons une lettre.") == [ROMY]
    assert unmet_named(DAY_ONE, "Lila et moi envoyons une lettre.") == []
    assert unmet_named(AFTER_T4, "Romy et moi envoyons une lettre.") == []
    # An older story has no canon of who comes when.
    assert unmet_named({"living_story": {}}, "Romy et moi envoyons une lettre.") == []


# --------------------------------------------------------------------------- #
# Item text
# --------------------------------------------------------------------------- #


def test_names_unmet_reads_every_part_of_an_item():
    assert names_unmet({"prompt": "Say it in French: “Romy and I send a letter.”"}, DAY_ONE) == [ROMY]
    assert names_unmet({"options": ["Lila dort.", "Romy dort."]}, DAY_ONE) == [ROMY]
    assert names_unmet({"prompt_l10n": {"de": "Romy schläft."}}, DAY_ONE) == [ROMY]
    assert names_unmet({"scene": {"lines": [{"fr": "Tu viens ?", "name": "Romy"}]}}, DAY_ONE) == [ROMY]
    assert names_unmet({"prompt": "Lila dort.", "id": "romy_tremblay-1"}, DAY_ONE) == []
    assert names_unmet({"prompt": "Romy dort."}, None) == []


def _provider(monkeypatch, payload: dict, *, state: dict | None) -> forge.BankItemProvider:
    monkeypatch.setattr(forge, "story_state_of", lambda db, user: state)
    return forge.BankItemProvider(
        None,
        user=SimpleNamespace(id="u"),
        session=SimpleNamespace(id="s"),
        sets={1: SimpleNamespace(payload=payload)},
        concepts={1: SimpleNamespace(id=1, external_id=A_ROMY_UNIT)},
    )


@pytest.mark.parametrize(
    "state, romy_too",
    [(DAY_ONE, False), (BEFORE_ANY_SCENE, False), (AFTER_T4, True), (None, True)],
)
def test_a_shared_set_never_poses_a_sentence_about_someone_unmet(monkeypatch, state, romy_too):
    provider = _provider(monkeypatch, {}, state=state)
    assert provider._fits_story(1, {"prompt": "Romy et moi envoyons une lettre."}) is romy_too
    assert provider._fits_story(1, {"prompt": "Lila et moi envoyons une lettre."}) is True


def test_the_gate_is_on_the_payload_provider_itself(monkeypatch):
    """Every way an item leaves the set goes through ``candidates``: a drill, a burst, a rung."""

    provider = _provider(monkeypatch, {}, state=DAY_ONE)
    assert provider.payloads.keep is not None
    assert provider.payloads.keep(1, {"prompt": "Romy dort."}) is False
    assert provider.payloads.keep(1, {"prompt": "Lila dort."}) is True


def test_a_scene_the_coach_takes_over_is_not_refused_for_its_old_speaker(monkeypatch):
    provider = _provider(monkeypatch, {}, state=DAY_ONE)
    item = {
        "prompt": "Romy : Tu viens ce soir ?",
        "character": {"id": ROMY, "name": "Romy", "register": "tu"},
        "coach": {"id": ROMY, "name": "Romy"},
        "scene": {"lines": [{"speaker": ROMY, "name": "Romy", "fr": "Tu viens ce soir ?"}]},
    }
    coach = forge_coaches.coach_for_concept(A_ROMY_UNIT, state=DAY_ONE)
    assert coach["id"] != ROMY
    assert "Romy" not in str(recast_scene(item, coach))
    assert provider._fits_story(1, item) is True


def _a_unit_that_names_romy() -> tuple[str, str]:
    """(external id, its first bank unit) of an A1 rule whose bank sentences name Romy."""

    bank = item_bank.default_bank()
    for external_id in sorted(_cards()):
        for unit in item_bank.units_for_external_id(external_id)[:1]:
            if not bank.frames(unit):
                continue
            detector = item_bank.unit_detector(unit)
            sentences = bank.generate(unit, 40, seed="probe", detector=detector)
            if sum("Romy" in item.sentence for item in sentences) >= 3:
                return external_id, unit
    raise AssertionError("no rule names Romy any more: this test has nothing to hold")


def test_a_bank_stream_never_names_someone_unmet():
    bank = item_bank.default_bank()
    _external_id, unit = _a_unit_that_names_romy()
    stream = bank.sample(unit, random.Random("day-one"), detector=only_met(item_bank.unit_detector(unit), DAY_ONE))
    served = [item for _index, item in zip(range(30), stream, strict=False)]
    assert served
    assert not [item.sentence for item in served if "Romy" in f"{item.sentence} {item.en}"]


def test_only_met_changes_nothing_when_nothing_can_tell():
    def detector(_sentence: str) -> bool:
        return True

    assert only_met(detector, None) is detector
    assert only_met(None, None) is None
    assert only_met(None, DAY_ONE)("Lila dort.") is True
    assert only_met(None, DAY_ONE)("Romy dort.") is False


def test_the_coach_scene_drill_of_day_one_never_names_romy():
    """The walk's drill: ``coach_scene_review_task``, over many days of one unit. Without the
    learner's state the same days do name her, so this is not holding by luck."""

    external_id, _unit = _a_unit_that_names_romy()
    brief = {
        "external_id": external_id,
        "concept_id": 1,
        "title_native": "x",
        "title_fr": "x",
        "rule_card": {},
        "unit_id": external_id,
        "catalog_version": "v2",
    }

    def said(state: dict | None) -> list[str]:
        tasks = (
            journey_learning.coach_scene_review_task(
                brief, language="en", day_key=f"2026-11-{day:02d}", state=state
            )
            for day in range(1, 31)
        )
        return [str(task) for task in tasks if task is not None]

    assert any("Romy" in text for text in said(None))
    served = said(DAY_ONE)
    assert served
    assert not [text for text in served if "Romy" in text]


# --------------------------------------------------------------------------- #
# The rule card
# --------------------------------------------------------------------------- #


def test_a_card_is_not_spoken_by_someone_unmet():
    card = rule_card_for(A_ROMY_UNIT)
    assert card["speaker"] == ROMY
    shown = card_for_learner(card, external_id=A_ROMY_UNIT, state=DAY_ONE)
    assert shown["speaker"] != ROMY
    assert shown["speaker"] in FIRST_PAGE
    assert shown["example"] == card["example"], "the card keeps its example"
    assert card["speaker"] == ROMY, "the shared card is not changed"


def test_a_card_whose_example_the_stand_in_cannot_say_names_nobody():
    card = {"speaker": ROMY, "example": {"fr": "Tu viens ?"}}
    stand_in = {"id": "augustin_de_roncourt", "register": "vous"}
    original = forge_coaches.coach_for_concept
    forge_coaches.coach_for_concept = lambda *a, **k: stand_in
    try:
        assert card_for_learner(card, external_id="x", state=DAY_ONE)["speaker"] is None
    finally:
        forge_coaches.coach_for_concept = original


def test_a_card_stays_as_written_once_met_or_when_nothing_can_tell():
    card = rule_card_for(A_ROMY_UNIT)
    assert card_for_learner(card, external_id=A_ROMY_UNIT, state=AFTER_T4)["speaker"] == ROMY
    assert card_for_learner(card, external_id=A_ROMY_UNIT, state=None)["speaker"] == ROMY
    assert card_for_learner(None, external_id=A_ROMY_UNIT, state=DAY_ONE) is None


def test_no_rule_card_text_names_anyone_past_the_first_page():
    """The gate moves the speaker; the card's text cannot move, so it may only name people of
    the season's first page. A card that names Romy in its text fails here."""

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, inner in value.items():
                if key != "speaker":
                    yield from strings(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from strings(inner)

    found = {
        external_id: named
        for external_id, card in _cards().items()
        if (named := set(cast_registry.people_named(" ".join(strings(card)))) - FIRST_PAGE)
    }
    assert not found, found


def test_every_surface_that_serves_a_card_goes_through_the_gate():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app/services"
    for path, needle in (
        ("atelier.py", "card_for_learner("),
        ("grammar_map.py", "card_for_learner("),
        ("journey_learning.py", "card_for_learner("),
        ("daily_journey.py", "card_for_learner("),
    ):
        assert needle in (root / path).read_text(encoding="utf-8"), path
