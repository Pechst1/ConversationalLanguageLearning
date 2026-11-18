"""P12 round 2 · Le Quartier as the walk of 17 Nov met it (integration branch, real model).

1. Home never offered «Im Quartier spielen»: before Start the offer is the story engine's
   invitation (``describe_next``: ``location_id=""``), so Home could not tell where the day
   plays. The headline now carries the planned page's stage (key, opening place, places).
2. «Un indice» before any attempt printed «Zum Beispiel: «Oui, ce soir.»» — the whole accepted
   answer: the hint is now a start of at most three words, never the whole example.
3. The end card said «Tu as dit que tu viens pour vendre» of a reply that said no such thing:
   a classifier reading that is not clear is not «heard as meant» (task outcome partially met).
4. «Ton carnet» listed only the day played in 3D: a page's «Le choix» cards are now in the
   archive (``choices``).
"""

from __future__ import annotations

import uuid

from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.runtime import hint_for
from app.services.season.turns import ReplyChoice
from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def test_home_knows_where_the_day_plays_before_start(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    provider = season_on
    d = support.Driver(assembled_client, support.register(assembled_client, f"r2q-{uuid.uuid4()}@example.com", cefr="A1.1"), db=db_session)
    today = d.today()
    # what the walk's Home had: the engine's invitation, with no place
    assert today["available"]["scenario_key"] == "story_next"
    assert today["available"]["location_id"] == ""
    stage = today["headline"]["stage"]
    assert stage["key"] == "t1.a", stage
    assert stage["location_id"] in ("quai_de_valmy", "le_mistral"), stage
    assert "le_mistral" in stage["locations"]
    _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    day_b = d.today()["headline"]["stage"]
    assert day_b["key"] == "t1.b"
    assert "stairwell" in day_b["locations"], "day b goes up the stairs (an unfinished place)"
    _play(d, provider, clock, "Oui, je reste une semaine.")
    assert d.today()["headline"]["stage"] is None, "a gap day's place is not known before it is written"


def test_the_hint_is_a_start_of_at_most_three_words_never_the_answer():
    from app.services.season import runtime

    margaux = {"replies": [{"id": "tonight", "examples": ["Oui. Ce soir."]}, {"id": "dont_know", "examples": ["Je ne sais pas."]}]}
    hint = hint_for(margaux, "de")
    # observed: «Zum Beispiel: «Oui, ce soir.»» — the whole accepted answer, on the first tap
    assert "Ce soir" not in hint, hint
    assert hint == "Zum Beispiel: «Oui. …»", hint
    for example in ["Odile, c'est ma grand-mère.", "Je vends et je pars. Une semaine.", "Moi… pas Marchand. Odile… grand-mère. La clé, c'est à elle.", "Les photos."]:
        start = runtime.hint_start(example)
        words = start.removesuffix(" …").split()
        assert 1 <= len(words) <= 3 and len(words) < len(example.split()), (example, start)
    assert runtime.hint_start("Merci.") is None, "a one-word answer has no start that is not the answer"
    assert hint_for({"replies": [{"id": "a", "examples": ["Merci."]}]}, "en") is None


def test_an_unclear_reading_is_not_heard_as_meant():
    from app.services.season.runtime import heard_as_meant

    # the classifier's fallback for a reply that says none of the routes keeps its default confidence
    assert heard_as_meant(ReplyChoice(reply_id="dont_know", clear=False)) is False
    assert heard_as_meant(ReplyChoice(reply_id="dont_know", clear=True, confidence=0.9)) is True
    assert heard_as_meant(ReplyChoice(reply_id="dont_know", clear=True, confidence=0.1)) is False


def test_a_page_played_as_pages_files_its_cards_for_the_carnet():
    from app.services.story_archive import choices_of

    page = resolve_day(load_season("s1"), "t1", "b", flags={}, band="A1", language="de")
    payload = {
        "season_page": page,
        "season_routing": [
            {"turn_id": "b.turn1", "reply_id": "b", "learner": "Je ne sais pas."},
            {"turn_id": "b.letter", "reply_id": "nobody", "learner": "Personne"},
        ],
    }
    # a free reply's route may be the fallback: only the card is a choice
    assert choices_of(payload) == [{"turn_id": "b.letter", "reply_id": "nobody", "label_fr": "Personne"}]
    assert choices_of({}) == [] and choices_of({"season_page": page}) == []
