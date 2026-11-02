"""#472 — a scene word quotes a real line of the scene, never the page's title.

Walk, 2 November (a1-de-fresh, day 2): «la lettre» came first in the deck and its
example was « La lettre », the episode's title. A page without a caption or a
spoken first line is published with its title standing in for ``premise_fr`` and
``opening_line_fr``, and ``scene_texts`` read those fields as lines of the scene,
so ``scene_lines`` quoted the title (and a lexicon word could enter the scene
only because the title printed it).
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.scene_deck import scene_lines
from app.services.scene_items import scene_texts
from app.services.season import runtime
from app.services.season.format import load_season
from app.services.season.page import resolve_day

LINE = "Leur prix est dans votre lettre."
LINE_TEXT = LINE + " Avant le 8 janvier."


def _draft() -> dict:
    return {
        "title_fr": "La lettre",
        "premise_fr": "La lettre",  # no caption: the title stands in
        "opening_line_fr": "La lettre",  # no spoken first line: the title again
        "panels": [{"narration_fr": "", "dialogue": [{"character_id": "camille", "text_fr": LINE_TEXT}]}],
        "lexicon": [{"lemma": "lettre", "surface_fr": "lettre", "line_ref": "premise"}],
    }


def _lines(draft: dict, *heads: str) -> dict[str, str | None]:
    words = {index: SimpleNamespace(word=head) for index, head in enumerate(heads)}
    out = scene_lines(draft=draft, journey_id="j", words=words, progress={}, candidates=set(words))
    return {heads[index]: line["sentence_fr"] for index, line in out.items()}


def test_472_the_title_is_not_a_line_of_the_scene() -> None:
    draft = _draft()
    assert "La lettre" not in scene_texts(draft).values()
    assert list(scene_texts(draft).values()) == [LINE_TEXT]


def test_472_a_lexicon_word_quotes_the_scene_line_not_the_title() -> None:
    # Before: {'lettre': 'La lettre'}
    assert _lines(_draft(), "lettre") == {"lettre": LINE}


def test_472_a_reserved_word_found_in_the_text_skips_the_title_too() -> None:
    draft = _draft()
    draft["lexicon"] = []  # the candidate branch: found in the scene's texts
    assert _lines(draft, "lettre") == {"lettre": LINE}


def test_472_a_word_only_the_title_prints_has_no_line() -> None:
    draft = _draft()
    draft["panels"] = [{"narration_fr": "", "dialogue": [{"character_id": "camille", "text_fr": "Bonjour."}]}]
    assert _lines(draft, "lettre") == {}


def _authored(day: str) -> dict:
    season = load_season("s1")
    page = resolve_day(season, "t1", day, flags={}, band="A1.1", language="de")
    today = SimpleNamespace(
        season=season,
        language="de",
        band="A1.1",
        pos=SimpleNamespace(key=f"t1:{day}", tentpole_day=day, is_tentpole=True),
    )
    return runtime.authored_draft(today, page, page.get("turns") or [])


def test_472_the_real_first_days_quote_real_lines() -> None:
    """Season 1's tentpole pages as the engine publishes them (day 1 «Le mauvais
    accueil», day 2 «La lettre», which has no caption of its own)."""

    day_two = _authored("b")
    assert _lines(day_two, "lettre")["lettre"] == LINE_TEXT  # the whole line, with its translation
    day_one = _authored("a")
    quoted = _lines(day_one, "clé", "appartement", "vendre")
    assert quoted["clé"] == "Tu as une valise, une lettre, une clé."
    texts = " ".join(scene_texts(day_one).values())
    for draft in (day_one, day_two):
        titles = {draft["title_fr"], draft["chapter"]["title_fr"]}
        for line in _lines(draft, "lettre", "clé", "appartement", "vendre").values():
            assert line not in titles
    assert all(line in texts for line in quoted.values())
