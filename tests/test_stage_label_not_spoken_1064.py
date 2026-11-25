"""#1064: a page's title is never a line someone says.

Live walk of 25 Nov 2026 (A1.1, day 43, T6 day B «Dix heures»): the chat showed the
bubble «Margaux — Dix heures», and the rule card and the finished card quoted
«Margaux — Dix heures» as a line of today's scene. «Dix heures» is the page's title
(the panel header «Dix heures · 2/6»), not something Margaux says.

The page's question is asked in silence (Toi's balloon, no line in the turn's
panel), and the authored projection filled the scene contract's opening line, the
addressee's own words, with the page title. Every reader then took it for Margaux's
speech: the respond prompt's ``character_line_fr``, ``scene_lines`` (the rule card's
and the deck's quotes), the grader's ``character_line_fr``.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.living_story import AuthoredSceneDraft
from app.services.scene_items import fold, scene_lines
from app.services.season import runtime
from app.services.season.clock import Position
from app.services.season.format import load_season
from app.services.season.page import resolve_day

#: Pages whose first question's panel holds no line (Toi's balloon): T6 day B «Dix
#: heures» (the walk's page) and T7 day B «Huit heures».
SILENT_QUESTION_PAGES = [("t6", "b"), ("t7", "b")]


def _draft(tentpole: str, letter: str, band: str = "A2.1", language: str = "en") -> tuple[dict, dict]:
    season = load_season("s1")
    page = resolve_day(season, tentpole, letter, flags={}, band=band, language=language)
    assert page is not None
    index, segment = next((i, seg) for i, seg in enumerate(season.segments) if seg.id == tentpole)
    pos = Position(season.id, segment, index, 1 if letter == "a" else 2, 43)
    today = SimpleNamespace(
        language=language, season=season, pos=pos, local_date=date(2026, 11, 25), band=band, flags={}, state={}
    )
    return runtime.authored_draft(today, page, runtime.projected_turns(page)), page


@pytest.mark.parametrize(("tentpole", "letter"), SILENT_QUESTION_PAGES)
@pytest.mark.parametrize("band", ["A1.1", "A2.1", "B1.1"])
def test_a_silent_question_has_no_opening_line_in_the_title(tentpole, letter, band):
    draft, page = _draft(tentpole, letter, band)
    title = page["title_fr"]

    assert fold(draft["opening_line_fr"]) != fold(title), (
        f"{draft['character_id']} says the page title «{draft['opening_line_fr']}»"
    )
    assert fold(draft["translation_native"]) != fold(title)
    spoken = [
        (line.character_id, line.text_fr)
        for line in scene_lines(SimpleNamespace(story_context={"draft": draft}, character_id=draft["character_id"]))
    ]
    assert all(fold(text) != fold(title) for _who, text in spoken), spoken
    # the scene contract still takes the page (tentpole_brief validates it)
    AuthoredSceneDraft.model_validate({key: value for key, value in draft.items() if key != "_ending"})


def test_the_walks_page_produces_no_margaux_line_dix_heures():
    """The issue's guard: T6 day B produces no ``speaker: Margaux, text: Dix heures`` line."""

    draft, page = _draft("t6", "b", band="A1.1")
    assert page["title_fr"] == "Dix heures"
    validated = AuthoredSceneDraft.model_validate({k: v for k, v in draft.items() if k != "_ending"})
    lines = scene_lines(SimpleNamespace(story_context={"draft": validated.model_dump(mode="json")}))
    assert ("margaux_barman", "Dix heures") not in [(line.character_id, line.text_fr) for line in lines]
    assert validated.opening_line_fr != "Dix heures"


def test_a_question_with_its_own_words_keeps_them():
    """A page whose question is said (T6 day A: Margaux's own line) keeps that line."""

    draft, page = _draft("t6", "a")
    assert draft["opening_line_fr"]
    assert fold(draft["opening_line_fr"]) != fold(page["title_fr"])


def test_the_chat_does_not_open_on_a_margaux_bubble_dix_heures():
    """The bubble the walk saw: the respond step's ``character_line_fr`` (the chat's
    line from the addressee) and the brief's opening are never the page title."""

    from app.services.journey_contracts import StepKind
    from tests.test_tentpole_pricing import _plan, _step, tentpole

    brief = tentpole("t6", 2, band="A1", language="en")
    assert brief.title_fr.startswith("Dix heures")
    assert fold(brief.opening_line_fr or "") != "dix heures"
    assert fold(brief.response_task.opening_line_fr or "") != "dix heures"
    assert fold(brief.response_task.translation_native or "") != "dix heures"
    respond = _step(_plan(brief), StepKind.RESPOND)
    bubble = (respond.public_prompt or {}).get("character_line_fr")
    assert fold(bubble or "") != "dix heures", f"chat bubble «{bubble}» is the page title"
