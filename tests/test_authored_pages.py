"""Authored scenes are graphic-novel pages too (2026-09-25).

The first day and the story engine's stand-in are authored and instant. They
used to be one plate and one line; each variant now carries a 4-panel page in
which the cast talk to each other before the addressed character turns to the
learner. The page travels on the scene step's prompt.
"""

from __future__ import annotations

from app.schemas.daily_journey import ScenePrompt
from app.services import journey_content as jc
from app.services.journey_contracts import ScenarioBrief
from app.services.journey_planner import plan_journey
from tests.test_journey_content import _user


def _briefs(db_session):
    for scenario_key in jc.SCENARIO_PRIORITY:
        for band in ("A1", "A2"):
            user = _user(db_session, cefr=f"{band}.1")
            brief = jc.resolve_scenario_brief(db_session, user=user, scenario_key=scenario_key)
            assert isinstance(brief, ScenarioBrief), brief
            yield scenario_key, band, brief


def test_every_authored_variant_is_a_page_where_the_cast_talk(db_session):
    for scenario_key, band, brief in _briefs(db_session):
        label = f"{scenario_key} {band}"
        assert jc.MIN_AUTHORED_PANELS <= len(brief.panels) <= jc.MAX_AUTHORED_PANELS, label
        speakers = {line["character_id"] for p in brief.panels for line in p["dialogue"]}
        assert len(speakers - {brief.character_id}) >= 1, f"{label}: nobody else speaks"
        last = brief.panels[-1]["dialogue"][-1]
        assert last["character_id"] == brief.character_id, label
        assert last["text_fr"] == brief.opening_line_fr, f"{label}: the page ends on the opening line"
        assert all(line["character_name"] for p in brief.panels for line in p["dialogue"]), label
        assert all(p["image_url"] for p in brief.panels), label


def test_the_page_rides_on_the_scene_step(db_session):
    _, _, brief = next(_briefs(db_session))
    plan = plan_journey(scenario=brief, candidates=[])
    scene = next(step for step in plan.steps if str(step.kind) == "scene")
    prompt = ScenePrompt.model_validate(scene.public_prompt)
    assert prompt.panels and len(prompt.panels) == len(brief.panels)
    assert prompt.panels[0].image_status in {"panel_art", "setting_reference"}


def test_a_panel_without_its_drawing_shows_the_plate():
    variant = {"panels": [{"narration_fr": "x", "dialogue": [], "image_asset": "assets/nope/missing.webp"}]}
    [panel] = jc.authored_panels(variant, fallback_image_url="/assets/serial/locations/le_mistral-counter.webp")
    assert panel["image_url"] == "/assets/serial/locations/le_mistral-counter.webp"
    assert panel["image_status"] == "setting_reference"
