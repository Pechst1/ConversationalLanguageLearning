"""Walk of 9 Nov, T1 A. «Non merci.» to the coffee: Margaux slides the cup away in silence, and
the thread showed nothing, so her next line read as her answer. The owner chose a caption, 9 Nov."""

from __future__ import annotations

from app.services.season.turns import reaction_lines, reaction_text
from tests.test_quartier_phase1 import FAMILY, _page, offline, story_qa  # noqa: F401

CAPTION = "Margaux pousse la tasse jusqu'au tabouret d'Odile."


def _declined(language: str = "en"):
    scenario = story_qa._scenario(_page(language=language))
    history: list[dict] = []
    story_qa._record(history, FAMILY, story_qa._say(scenario, FAMILY, history, 0))
    return story_qa._say(scenario, "Non merci.", history, 1)


def test_the_thread_says_what_margaux_did_and_she_still_says_nothing(offline):  # noqa: F811
    evaluation = _declined()
    first = evaluation.reply_lines[0]
    assert (first["speaker_id"], first["text_fr"]) == ("caption", CAPTION)
    assert CAPTION not in evaluation.character_reply_fr
    [beat] = evaluation.stage["beats"]
    assert beat["silence"] is True
    assert [line["kind"] for line in beat["lines"]] == ["caption"]


def test_the_caption_has_its_translations(offline):  # noqa: F811
    assert _declined("en").stage["beats"][0]["lines"][0]["text_native"] == "Margaux pushes the cup over to Odile's stool."
    assert _declined("de").stage["beats"][0]["lines"][0]["text_native"] == "Margaux schiebt die Tasse zu Odiles Hocker hinüber."


def test_any_other_caption_stays_on_the_page():
    panel = {"lines": [{"who": "caption", "kind": "caption", "text_fr": "Deux clés. À suivre…"}]}
    assert reaction_lines([panel], addressee="margaux_barman") == []
    assert reaction_text([panel], addressee="margaux_barman") == ""
