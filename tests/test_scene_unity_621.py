"""#621 (root cause #145): one page is one scene.

Live walk of 9 Nov: under the header «Le quai de Valmy · Lila brings pizza and asks if
you'll share it», the four read panels were «Le soir. Au téléphone : l'assurance. Margaux
essuie un verre déjà sec.», «Dehors, sur le quai.» (Lila), «Le lendemain matin. Le même
banc.» (Lila) and Gus's «Bonjour. Bonne journée à vous.».

The writer is told one place, one moment and the scene's cast. What is checked afterwards
is only what the page's own state says, compared exactly, and softly: one retry with the
reason, then the draft is served. The golden pages and the fake's drafts must not fire.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services import scene_unity, story_split
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import project, resolve_day
from app.services.season.runtime import _engine_panel
from tests.prompt_regression import harness

SCENE_PLACE = "quai_de_valmy"
LILA = "lila_bonnet"
GUS = "augustin_de_roncourt"

#: The walk's four panels, word for word, as the page would declare them.
WALK_PANELS = [
    {
        "narration_fr": "Le soir. Au téléphone : l'assurance. Margaux essuie un verre déjà sec.",
        "location_id": "le_mistral",
        "dialogue": [],
    },
    {
        "narration_fr": "Dehors, sur le quai.",
        "location_id": SCENE_PLACE,
        "dialogue": [
            {"character_id": LILA, "text_fr": "Oui, la photo au mur, c'est mon idée… un secret, c'est pire que l'assurance."}
        ],
    },
    {
        "narration_fr": "Le lendemain matin. Le même banc.",
        "location_id": SCENE_PLACE,
        "time_jump": True,
        "dialogue": [{"character_id": LILA, "text_fr": "Les chiffres du notaire. Camille regarde tout."}],
    },
    {
        "narration_fr": "",
        "location_id": SCENE_PLACE,
        "dialogue": [{"character_id": GUS, "text_fr": "Bonjour. Bonne journée à vous."}],
    },
]


def _draft(panels=WALK_PANELS, *, cast=(LILA,), location=SCENE_PLACE, lead=LILA) -> engine.SceneDraft:
    return engine.SceneDraft.model_validate(
        {
            "title_fr": "Lila revient avec une pizza",
            "premise_fr": "Lila revient sur le quai avec une pizza.",
            "setup_native": "Lila comes back with a pizza.",
            "objective_native": "Lila brings pizza and asks if you'll share it.",
            "objective_semantics": "Any honest reply.",
            "character_id": lead,
            "location_id": location,
            "causal_reason": "They have fought. → They are still here.",
            "novelty_key": "lila-pizza-banc",
            "chapter": {
                "title_fr": "La dispute",
                "dramatic_question": "Encore amis ?",
                "possible_developments": ["Oui.", "Non."],
            },
            "scene_cast": list(cast),
            "panels": [{"visual_direction": "A panel.", **panel} for panel in panels],
            "opening_line_fr": "On partage ?",
            "suggested_response_fr": "Oui, on partage.",
            "hint_native": "Say if you share.",
            "translation_native": "Shall we share?",
        }
    )


# ---------------------------------------------------------------------------
# The done-when: the scene's place, or an explicit time-jump caption; the scene's cast
# ---------------------------------------------------------------------------


def test_every_panel_shares_the_place_or_an_explicit_jump_and_every_speaker_is_cast():
    """The issue's done-when, on the walk's own text."""

    draft = _draft()
    assert scene_unity.panels_elsewhere(draft) == [(1, "le_mistral")]
    assert scene_unity.speakers_outside_cast(draft) == {GUS: [4]}
    hint = scene_unity.gap(draft)
    assert "panel 1 at le_mistral" in hint and GUS in hint and "panel 4" in hint

    told_as_one_scene = deepcopy(WALK_PANELS)
    told_as_one_scene[0]["location_id"] = SCENE_PLACE
    told_as_one_scene[3]["dialogue"] = [{"character_id": LILA, "text_fr": "Bonjour. Bonne journée à vous."}]
    assert scene_unity.gap(_draft(told_as_one_scene)) is None


def test_the_walk_page_declaring_two_jumps_is_named_too():
    """The same page whose writer declares each hop honestly: the caption for each is
    there, and it is still the page that jumps on every panel."""

    panels = deepcopy(WALK_PANELS)
    panels[0]["time_jump"] = True
    draft = _draft(panels, cast=(LILA, GUS))
    assert scene_unity.panels_elsewhere(draft) == []
    assert scene_unity.time_jumps(draft) == [1, 3]
    assert "2 times (panels 1, 3)" in scene_unity.gap(draft)


def test_a_deliberate_jump_with_its_caption_passes():
    """«Le lendemain matin. Le même banc.» is the writer's to use, once."""

    panels = [
        {"narration_fr": "Le soir. Un banc, le canal.", "location_id": SCENE_PLACE, "dialogue": [{"character_id": LILA, "text_fr": "Oui, la photo au mur, c'est mon idée."}]},
        {"narration_fr": "Lila part.", "location_id": SCENE_PLACE, "dialogue": []},
        {"narration_fr": "Le lendemain matin. Le même banc.", "location_id": SCENE_PLACE, "time_jump": True, "dialogue": []},
        {"narration_fr": "", "location_id": SCENE_PLACE, "dialogue": [{"character_id": LILA, "text_fr": "Une pizza. Pour toi."}]},
    ]
    assert scene_unity.gap(_draft(panels)) is None


def test_a_flashback_to_another_place_passes_and_comes_back_without_a_caption():
    panels = [
        {"narration_fr": "", "location_id": SCENE_PLACE, "dialogue": [{"character_id": LILA, "text_fr": "Tu sais, le toit ?"}]},
        {"narration_fr": "L'été dernier. Le toit.", "location_id": "toit", "time_jump": True, "dialogue": []},
        {"narration_fr": "", "location_id": "toit", "dialogue": [{"character_id": LILA, "text_fr": "Regarde. Tout Paris."}]},
        {"narration_fr": "", "location_id": SCENE_PLACE, "dialogue": []},
    ]
    assert scene_unity.gap(_draft(panels)) is None


def test_a_jump_says_when():
    panels = deepcopy(WALK_PANELS)
    panels[0]["location_id"] = SCENE_PLACE
    panels[2]["narration_fr"] = ""
    panels[3]["dialogue"] = []
    draft = _draft(panels)
    assert scene_unity.jumps_without_caption(draft) == [3]
    assert "Panel 3 jumps in time with no caption" in scene_unity.gap(draft)


# ---------------------------------------------------------------------------
# What the check does not do
# ---------------------------------------------------------------------------


def test_the_words_of_a_caption_are_never_read():
    """The walk's captions with no state behind them make no claim, and pass: no clause
    pattern over French decides a story (the reviews of #600 and #631). What stops this
    page is the writer's own rule, not this check."""

    panels = deepcopy(WALK_PANELS)
    for panel in panels:
        panel.pop("location_id")
        panel.pop("time_jump", None)
    panels[3]["dialogue"] = []
    assert scene_unity.gap(_draft(panels)) is None


def test_a_gus_the_plan_itself_cast_passes():
    """The check compares the page with its plan. A plan that casts Gus is the planner's
    to fix (rule 10), and is not a page that left its scene."""

    panels = deepcopy(WALK_PANELS)
    panels[0]["location_id"] = SCENE_PLACE
    assert scene_unity.gap(_draft(panels, cast=(LILA, GUS))) is None


def test_no_declared_state_is_no_claim():
    draft = _draft(cast=())
    assert scene_unity.speakers_outside_cast(draft) == {}
    undeclared = [{key: value for key, value in panel.items() if key not in ("location_id", "time_jump")} for panel in WALK_PANELS]
    assert scene_unity.gap(_draft(undeclared, cast=())) is None


def test_the_lead_is_always_in_the_scene():
    panels = [{"narration_fr": "", "dialogue": [{"character_id": LILA, "text_fr": "Salut."}]}] * 2
    assert scene_unity.gap(_draft(panels, cast=("margaux_barman",))) is None


@pytest.mark.parametrize(
    ("value", "place"),
    [(None, None), ("", None), ("  ", None), ("null", None), (7, None), (["le_mistral"], None), ("x" * 81, None), (" toit ", "toit")],
)
def test_a_scratch_place_is_no_claim_never_a_lost_page(value, place):
    panel = {"visual_direction": "A panel.", "location_id": value}
    assert engine.Panel.model_validate(panel).location_id == place
    assert story_split.WrittenPanel.model_validate(panel).location_id == place


@pytest.mark.parametrize(
    ("value", "jump"),
    [(True, True), ("true", True), ("yes", True), (False, False), (None, False), ("maybe", False), (1, False)],
)
def test_anything_but_a_plain_yes_is_no_jump(value, jump):
    panel = {"visual_direction": "A panel.", "time_jump": value}
    assert engine.Panel.model_validate(panel).time_jump is jump
    assert story_split.WrittenPanel.model_validate(panel).time_jump is jump


@pytest.mark.parametrize(
    ("value", "cast"),
    [(None, []), ("lila_bonnet", []), ([LILA, LILA, " ", 3], [LILA]), ([LILA, GUS], [LILA, GUS])],
)
def test_a_scratch_cast_is_no_claim_never_a_lost_page(value, cast):
    payload = _draft().model_dump()
    payload["scene_cast"] = value
    assert engine.SceneDraft.model_validate(payload).scene_cast == cast


# ---------------------------------------------------------------------------
# Soft: one retry with the reason, then the draft is served
# ---------------------------------------------------------------------------


def _approved(draws, validate):
    """``living_story._approved`` with a scripted draw and no database: the retry loop."""

    seen: list[list[str]] = []

    def draw(request, record, *, deadline, budget=None):
        seen.append(list(request["previous_rejections"]))
        if not draws:
            # Every attempt after the scripted ones fails (there may be a bonus attempt).
            raise engine.StoryUnavailable("provider_down")
        return draws.pop(0)

    served, _usage = engine._approved(
        "system",
        {},
        engine.SceneDraft,
        validate,
        db=SimpleNamespace(),
        user=SimpleNamespace(id=None),
        draw=draw,
    )
    return served, seen


def _unity_only(proposal):
    """The soft rider alone: the guards before it are other tests' business."""

    hint = scene_unity.gap(proposal)
    if hint:
        raise engine.SoftRejection("panels_leave_the_scene", hint=hint, proposal=proposal)


def test_the_retry_is_told_the_reason_and_a_second_wandering_page_is_served(monkeypatch):
    monkeypatch.setattr(engine, "_record_cost", lambda *args, **kwargs: None)
    first, second = _draft(), _draft()
    served, seen = _approved([first, second], _unity_only)
    assert served is second
    assert seen[0] == []
    assert GUS in seen[1][0] and "panel 1 at le_mistral" in seen[1][0]


def test_a_retry_that_fails_serves_the_first_draft_the_day_is_not_lost(monkeypatch):
    monkeypatch.setattr(engine, "_record_cost", lambda *args, **kwargs: None)
    first = _draft()
    served, _seen = _approved([first], _unity_only)
    assert served is first


def test_a_page_at_its_place_is_never_refused(monkeypatch):
    panels = deepcopy(WALK_PANELS)
    panels[0]["location_id"] = SCENE_PLACE
    panels[3]["dialogue"] = []
    draft = _draft(panels)
    served, seen = _approved([draft], _unity_only)
    assert served is draft and len(seen) == 1


def test_it_rides_the_one_retry_of_the_reading_aids():
    """Through the real rider: the same soft channel as the translations and the alt text,
    the hint merged, and the draft carried so it can be served."""

    draft = _draft()
    context = {"level": "B1", "control_language": "en"}
    for panel in draft.panels:
        panel.alt_native = "A panel."
    with pytest.raises(engine.SoftRejection) as refused:
        engine._check_reading_aids(draft, context)
    assert str(refused.value) == "panels_leave_the_scene"
    assert refused.value.proposal is draft
    assert GUS in refused.value.hint

    for panel in draft.panels:
        panel.alt_native = None
    with pytest.raises(engine.SoftRejection) as both:
        engine._check_reading_aids(draft, context)
    assert str(both.value) == "missing_reading_aids"
    assert GUS in both.value.hint and "alt_native" in both.value.hint


def test_an_epreuve_where_everyone_comes_is_left_alone(monkeypatch):
    monkeypatch.setattr(engine, "epreuve_gap", lambda draft, context: None)
    draft = _draft()
    for panel in draft.panels:
        panel.alt_native = "A panel."
    engine._check_reading_aids(draft, {"level": "B1", "control_language": "en", engine.EPREUVE_KEY: {"cast": []}})


# ---------------------------------------------------------------------------
# The writer: what it is told, and what it hands on
# ---------------------------------------------------------------------------


def test_the_writer_is_told_one_place_one_moment_the_cast_and_where_it_ends():
    assert "A day is one scene." in story_split.PLANNER
    assert "nobody comes in for one line" in story_split.PLANNER
    assert "The hook is tomorrow" in story_split.PLANNER
    author = story_split.AUTHOR
    assert "one place (plan.location)" in author
    assert "plan.cast speak" in author
    assert "The page ends where plan.question points" in author
    assert "no panel stages it" in author
    assert "A page is one scene" in engine.DIRECTOR


def test_the_caption_examples_the_walk_copied_are_gone():
    """«Margaux essuie un verre déjà sec.» reached the page word for word, and «Le
    lendemain matin.» has the form of the example next to it: the prompt taught a caption
    that names a person and jumps a day."""

    rule = story_split.AUTHOR.split("- Captions are comic captions", 1)[1].split("- People talk", 1)[0]
    assert "Margaux" not in rule
    assert "lendemain" not in rule


def _plan(**over) -> story_split.PagePlan:
    return story_split.PagePlan.model_validate(
        {
            "location_id": SCENE_PLACE,
            "cast": ["margaux_barman"],
            "lead_id": LILA,
            "beats": ["a", "b"],
            "change": {"before": "b", "after": "a"},
            "question": "Share?",
            "task": "Lila asks if you share.",
            **over,
        }
    )


def test_assemble_keeps_the_plans_cast_and_the_panels_state():
    text = story_split.PageText.model_validate(
        {
            "title_fr": "Lila revient avec une pizza",
            "premise_fr": "Lila revient.",
            "opening_line_fr": "On partage ?",
            "suggested_response_fr": "Oui.",
            "panels": [
                {"visual_direction": "A.", "location_id": SCENE_PLACE, "narration_fr": "Dehors, sur le quai."},
                {
                    "visual_direction": "B.",
                    "location_id": SCENE_PLACE,
                    "time_jump": True,
                    "narration_fr": "Le lendemain matin. Le même banc.",
                },
            ],
        }
    )
    assembled = story_split.assemble({"chapter": {"title_fr": "T", "dramatic_question": "Q", "possible_developments": ["a", "b"]}}, _plan(), text, None)
    assert assembled["scene_cast"] == [LILA, "margaux_barman"], "the lead first, once"
    assert [panel["location_id"] for panel in assembled["panels"]] == [SCENE_PLACE, SCENE_PLACE]
    assert [panel["time_jump"] for panel in assembled["panels"]] == [False, True]


def test_the_aids_never_read_the_panels_state():
    """They translate what is printed; a place id in their payload is a model's bait."""

    text = story_split.PageText.model_validate(
        {
            "title_fr": "Titre",
            "premise_fr": "Prémisse.",
            "opening_line_fr": "Ça va ?",
            "suggested_response_fr": "Oui.",
            "panels": [
                {"visual_direction": "A.", "location_id": SCENE_PLACE, "time_jump": True},
                {"visual_direction": "B.", "location_id": SCENE_PLACE},
            ],
        }
    )
    page = story_split.aids_payload({"control_language": "en", "level": "A1"}, text)["page"]
    assert all("location_id" not in panel and "time_jump" not in panel for panel in page["panels"])


# ---------------------------------------------------------------------------
# Real content: it must not over-fire
# ---------------------------------------------------------------------------

GOLDEN_PAGES = [case for case in harness.load_cases() if case.lane == "page" and case.answers.get("PageText")]


@pytest.mark.parametrize("case", GOLDEN_PAGES, ids=[case.id for case in GOLDEN_PAGES])
def test_every_golden_page_passes_except_the_walks(case):
    result = harness.run_case(case)
    observed, draft = result.observed, result.served
    assert draft is not None and draft.scene_cast, "the plan's cast reached the draft"
    if case.id == "page-a1-walk-four-moments":
        assert observed["scene_guard"] == "soft:panels_leave_the_scene"
        assert GUS in observed["scene_hint"]
        return
    assert scene_unity.gap(draft) is None, case.id
    assert observed["scene_guard"] != "soft:panels_leave_the_scene"


def _fake():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import dev_story_engine_server as dev

    return dev.FakeStoryProvider


def _fake_context() -> dict:
    """A captured brief, as the free walks' fake reads it."""

    context = json.loads((harness.CONTEXTS / "s1-g4.3-a1.json").read_text(encoding="utf-8"))
    context.pop("_season", None)
    return context


def test_the_walks_fake_season_pages_declare_one_scene_and_pass():
    """The free walks' fake writes the state, so a walk runs the comparison on every page."""

    fake, context = _fake(), _fake_context()
    for number in range(14):
        draft = engine.SceneDraft.model_validate(fake._season_draft(context, number))
        assert draft.scene_cast == [draft.character_id]
        assert {panel.location_id for panel in draft.panels} == {draft.location_id}
        assert scene_unity.gap(draft) is None, number


def test_the_walks_fake_scenes_without_a_season_make_no_claim():
    fake, context = _fake(), _fake_context()
    for number in range(7):
        draft = engine.SceneDraft.model_validate(fake._draft(context, number))
        assert scene_unity.gap(draft) is None, number


def test_an_authored_tentpole_page_carries_no_state_and_is_never_compared():
    """A tentpole's panels (``AuthoredPanel``) keep their own place in the season files,
    and move: the owner's pages walk from the stairs into the flat with no caption. None of
    that reaches this check: the projection onto the scene contract writes no state, and
    ``tentpole_brief`` serves the page without ``_validate_scene``."""

    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    pages = moved = 0
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            for band in ("A1", "A2", "B1", "B2", "C1"):
                page = resolve_day(season, tentpole.id, day.day, flags=flags, band=band, language="en")
                if page is None:
                    continue
                scene = project(page)["scene_panels"]
                pages += 1
                moved += any(panel.get("location_id") not in (None, page["location_id"]) for panel in scene)
                panels = [engine.AuthoredPanel.model_validate(_engine_panel(panel, language="en")) for panel in scene]
                assert all(panel.location_id is None and panel.time_jump is False for panel in panels)
                draft = SimpleNamespace(panels=panels, location_id=page["location_id"], character_id="", scene_cast=[])
                assert scene_unity.gap(draft) is None, (tentpole.id, day.day, band)
    assert pages and moved, "the season files do move between places: the rule is not theirs"


# ---------------------------------------------------------------------------
# What is served: the page held to its scene, whatever the retry did. A soft rejection's
# page goes out without the hard guards running again, so the held page keeps the
# engine's panel floor and its lexicon is checked again (#740's review).
# ---------------------------------------------------------------------------


def _scene_context(**over) -> dict:
    """Just enough of a world for ``_validate_scene``: the walk's people and places."""

    return {
        "world": {"cast": [{"id": LILA}, {"id": GUS}], "locations": [{"id": SCENE_PLACE}, {"id": "le_mistral"}]},
        "events": [],
        "chapter": None,
        "recent_situations": [],
        "level": "B1",
        "control_language": "en",
        **over,
    }


def _aids_written(draft):
    for panel in draft.panels:
        panel.alt_native = "A panel."
    return draft


def _spoken(draft) -> list[str]:
    return [line.text_fr for panel in draft.panels for line in panel.dialogue]


def _served_by_the_scene_guards(draft, context=None):
    """The page a soft rejection of ``_validate_scene`` carries to be served."""

    with pytest.raises(engine.SoftRejection) as refused:
        engine._validate_scene(draft, context or _scene_context())
    return refused.value.proposal


def test_wanders_twice_held(monkeypatch):
    """The walk's page twice: the retry was told and wandered again. Gus's «Bonjour.
    Bonne journée à vous.» is not served, and the page keeps the panels a page has."""

    monkeypatch.setattr(engine, "_record_cost", lambda *args, **kwargs: None)
    context = _scene_context()
    served, seen = _approved(
        [_aids_written(_draft()), _aids_written(_draft())], lambda proposal: engine._validate_scene(proposal, context)
    )
    assert GUS in seen[1][0], "the retry was told"
    assert scene_unity.speakers_outside_cast(served) == {}, f"served as it wandered: {_spoken(served)}"
    assert "Bonjour. Bonne journée à vous." not in _spoken(served)
    assert len(served.panels) >= engine.MIN_SCENE_PANELS
    assert scene_unity.jumps_without_caption(served) == []


def test_retry_fails_held(monkeypatch):
    """The provider is down on the retry: the day is not lost, and the walk's page is not
    what it gets either. On a page of four, the floor keeps the bar's panel (it still says
    where it is); Gus's line goes and his panel stays, silent."""

    monkeypatch.setattr(engine, "_record_cost", lambda *args, **kwargs: None)
    context = _scene_context()
    served, _seen = _approved([_aids_written(_draft())], lambda proposal: engine._validate_scene(proposal, context))
    assert scene_unity.speakers_outside_cast(served) == {}, f"served as it wandered: {_spoken(served)}"
    assert len(served.panels) == engine.MIN_SCENE_PANELS
    assert [panel.narration_fr for panel in served.panels] == [panel["narration_fr"] for panel in WALK_PANELS]
    assert _spoken(served) == [
        "Oui, la photo au mur, c'est mon idée… un secret, c'est pire que l'assurance.",
        "Les chiffres du notaire. Camille regarde tout.",
    ]


def test_held_lexicon():
    """#740's review: the lexicon was validated on the page as written and served with the
    held one. On a page of six, Gus's panel and the bar's go: «journée» (Gus) and «verre»
    (the bar) are no longer printed, and «photo» and «notaire» moved up a panel."""

    from app.services.scene_items import contains_surface, scene_texts

    panels = [
        *deepcopy(WALK_PANELS),
        {
            "narration_fr": "Lila ouvre la boîte.",
            "location_id": SCENE_PLACE,
            "dialogue": [{"character_id": LILA, "text_fr": "Une pizza. Pour toi."}],
        },
        {"narration_fr": "", "location_id": SCENE_PLACE, "dialogue": [{"character_id": LILA, "text_fr": "On partage ?"}]},
    ]
    draft = _aids_written(_draft(panels))
    draft.lexicon = [
        engine.LexiconEntry.model_validate({"part_of_speech": "noun", "lemma": surface, **entry, "surface_fr": surface})
        for surface, entry in (
            ("verre", {"gloss_native": "glass", "gender": "m", "line_ref": "panel:0:narration"}),
            ("journée", {"gloss_native": "day", "gender": "f", "line_ref": "panel:3:line:0"}),
            ("photo", {"gloss_native": "picture", "gender": "f", "line_ref": "panel:1:line:0"}),
            ("notaire", {"gloss_native": "notary", "gender": "m", "line_ref": "panel:2:line:0"}),
        )
    ]
    served = _served_by_the_scene_guards(draft)
    assert scene_unity.speakers_outside_cast(served) == {}, f"served as it wandered: {_spoken(served)}"
    assert scene_unity.panels_elsewhere(served) == []
    assert len(served.panels) == engine.MIN_SCENE_PANELS
    texts = scene_texts(served.model_dump(mode="json"))
    taught = {entry.surface_fr: entry.line_ref for entry in served.lexicon}
    assert taught == {"photo": "panel:0:line:0", "notaire": "panel:1:line:0"}
    for surface, ref in taught.items():
        assert contains_surface(texts.get(ref, ""), surface), (surface, ref)
    assert len(draft.panels) == 6 and len(draft.lexicon) == 4, "the page as written is left as written"


def test_title_retry_held():
    """#194's title check refuses first: the page it carries is the one served if the
    retry fails, and it is held to its scene as well."""

    draft = _aids_written(_draft())
    served = _served_by_the_scene_guards(draft, _scene_context(recent_situations=[{"title_fr": draft.title_fr}]))
    assert served.title_fr != draft.title_fr
    assert scene_unity.speakers_outside_cast(served) == {}, f"served as it wandered: {_spoken(served)}"


def test_floor_kept_recorded(monkeypatch):
    """What holding could not take out (the walk's bar, on a page of four) is on the brief
    for the critic and the next night; a page in one scene records nothing."""

    monkeypatch.setattr(engine, "_brief", lambda draft, context, *, usage: SimpleNamespace(story_context={}))
    context = _scene_context()
    served = _served_by_the_scene_guards(_aids_written(_draft()), context)
    left = engine._scene_brief(served, context, usage=[]).story_context.get("scene_unity")
    assert left and "panel 1 at le_mistral" in left[0] and GUS not in " ".join(left)

    at_its_place = deepcopy(WALK_PANELS)
    at_its_place[0]["location_id"] = SCENE_PLACE
    at_its_place[3]["dialogue"] = []
    assert "scene_unity" not in engine._scene_brief(_draft(at_its_place), context, usage=[]).story_context


def test_holding_keeps_floor():
    """Only the page's state decides, and never below the floor it is given: a page at its
    place is the same page, a jump that does not say when is no jump, an emptied panel
    goes before a panel at another place, and the draft is left as written."""

    from app.services.scene_unity import held_to_scene

    at_its_place = deepcopy(WALK_PANELS)
    at_its_place[0]["location_id"] = SCENE_PLACE
    at_its_place[3]["dialogue"] = []
    draft = _draft(at_its_place)
    assert held_to_scene(draft, floor=4) is draft, "nothing to hold: the page itself, uncopied"

    silent_jump = deepcopy(WALK_PANELS)
    silent_jump[2]["narration_fr"] = ""
    assert not any(panel.time_jump for panel in held_to_scene(_draft(silent_jump), floor=4).panels)

    walk = _draft()
    held = held_to_scene(walk, floor=4)
    assert len(held.panels) == 4 and scene_unity.speakers_outside_cast(held) == {}
    assert walk.panels[3].dialogue, "the draft itself is left as written"
    bar = "Le soir. Au téléphone : l'assurance. Margaux essuie un verre déjà sec."
    assert [panel.narration_fr for panel in held_to_scene(walk, floor=3).panels] == [
        bar,
        "Dehors, sur le quai.",
        "Le lendemain matin. Le même banc.",
    ]
    assert [panel.narration_fr for panel in held_to_scene(walk, floor=2).panels] == [
        "Dehors, sur le quai.",
        "Le lendemain matin. Le même banc.",
    ]
