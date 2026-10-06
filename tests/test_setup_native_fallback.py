"""A caption-less authored page's native setup is in the learner's language (owner option B, 2026-10-06).

T8 day B («La lumière est fausse», «Laisser partir») has no caption before its first
turn, so the engine's ``setup_native`` fell back to the French title for German and
English learners (found by the forced-outage life walk). It now uses the page's own
can-do, already localized; a French-chrome learner keeps the title.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.season import runtime
from app.services.season.clock import Position
from app.services.season.format import load_season
from app.services.season.page import resolve_day

FLAGS = {"s1.ending": "laisser_partir"}


def _draft(language: str) -> dict:
    season = load_season("s1")
    page = resolve_day(season, "t8", "b", flags=FLAGS, band="A2.1", language=language)
    index, segment = next((i, seg) for i, seg in enumerate(season.segments) if seg.id == "t8")
    pos = Position(season.id, segment, index, 2, 59)
    today = SimpleNamespace(
        language=language, season=season, pos=pos, local_date=date(2026, 10, 6), band="A2.1", flags=FLAGS, state={}
    )
    return runtime.authored_draft(today, page, page.get("turns") or []), page


@pytest.mark.parametrize("language", ["de", "en"])
def test_a_caption_less_page_sets_the_scene_in_the_learners_language(language):
    draft, page = _draft(language)
    assert draft["setup_native"] != page["title_fr"], draft["setup_native"]
    assert draft["setup_native"] == str(page.get("can_do_native"))[:600]


def test_a_french_chrome_learner_keeps_the_title():
    draft, page = _draft("fr")
    assert draft["setup_native"] in (page["title_fr"], str(page.get("can_do_native") or ""))
