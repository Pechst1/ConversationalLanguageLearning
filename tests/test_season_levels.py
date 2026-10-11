"""T-2 (content program 2026-10-03): the season reads at the learner's level.

The bible's A2 line (and B1 where it wrote one) stays canonical; a1 / b2 / c1
variants are optional, and a band never reads a line written above it.
"""

from __future__ import annotations

import pytest

from app.services.season.director import level_shape
from app.services.season.format import Reply, Say, Wording, examples_at, written_levels


@pytest.mark.parametrize(
    ("band", "expected"),
    [
        ("A1.1", "un"),
        ("A2.2", "deux"),
        ("B1.1", "trois"),
        ("B2.2", "quatre"),
        ("C1.1", "cinq"),
        ("C2", "cinq"),
    ],
)
def test_each_band_reads_its_own_level(band, expected):
    say = Say(a1="un", a2="deux", b1="trois", b2="quatre", c1="cinq")

    assert say.text(band) == expected


def test_a_missing_variant_falls_back_downward_never_up():
    say = Say(a2="deux", b1="trois")

    assert say.text("A1") == "deux"  # no a1: the canonical A2 line (with its translation)
    assert say.text("B2") == "trois"  # no b2: the B1 line, never above
    assert say.text("C1") == "trois"
    assert Say(a2="deux", c1="cinq").text("B2") == "deux"  # a C1 line is never read at B2


def test_the_neutral_wording_has_levels_too():
    say = Say(a2="Joyeux Noël !", neutral=Wording(a2="Bonne soirée !", a1="Bonsoir !"))

    assert say.text("A1", neutral=True) == "Bonsoir !"
    assert say.text("B1", neutral=True) == "Bonne soirée !"


def test_a_bands_own_examples_come_first_and_the_bibles_still_route():
    reply = Reply(id="r", label="oui", means="agrees", examples=["Oui, d'accord."],
                  examples_by_level={"a1": ["Oui."], "c1": ["Volontiers, ça me va tout à fait."]})

    assert examples_at(reply.examples, reply.examples_by_level, "A1.2") == ["Oui.", "Oui, d'accord."]
    assert examples_at(reply.examples, reply.examples_by_level, "B1") == ["Oui, d'accord."]
    assert examples_at(reply.examples, reply.examples_by_level, "C1")[0].startswith("Volontiers")


def test_written_levels_and_page_shape_cover_a1_to_c1():
    assert written_levels("C1.2")[0] == "c1"
    assert written_levels(None) == ("a1", "a2")
    assert level_shape("A1.1")["panels"] == "3-4"
    assert level_shape("C2")["band"] == "C1"
    assert level_shape("zz")["band"] == "A2"


def test_after_the_last_tentpole_the_next_chapter_is_the_interlude():
    """D8: a finished scripted season goes to the interlude, not 40 unbriefed chapters."""

    from app.services.living_story import season_stage_after_chapter
    from app.services.season.clock import SEASON_KEY
    from app.services.season.format import load_season
    from app.services.season.runtime import season_script_finished

    season = load_season("s1")
    played = [
        {"segment": segment.id, "event_id": f"{segment.id}:{n}"}
        for segment in season.segments
        for n in range(segment.days)
    ]
    finished = {SEASON_KEY: {"id": "s1", "played": played, "flags": {}, "signals": []}}
    midway = {SEASON_KEY: {"id": "s1", "played": played[:20], "flags": {}, "signals": []}}

    assert season_script_finished(finished) is True
    assert season_script_finished(midway) is False
    assert season_script_finished({}) is False
    args = {"chapter": {"id": "c"}, "world_arcs": [], "arc_progress": {}}
    assert season_stage_after_chapter(finished, **args) == "interlude"
    assert season_stage_after_chapter(midway, **args) == "running"
