"""#350: Gus says «tu» in the scene and «vous» in the Courrier on the same day.

ROOT CAUSE: the cast has one registry (#147) but ids reached the register resolver in
whatever spelling the surface had (a witness «gus», a portrait directory, the season's
«odile» for the registry's «odile_ferrand»), and ``address.character_register`` compared
the raw string with the keys of the relationship map and the season's cast. A spelling the
resolver did not know fell through to its last default, «vous», while the scene (which
reads the season row by its own id) said «tu». The Courrier's own fallback reply then
guessed the register again from the words of the opening instead of reading the one the
letter was written in.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.address import character_register

GUS_SPELLINGS = ("augustin_de_roncourt", "gus", "augustin", "Gus", " gus ")


def expect(actual, expected, what: str) -> None:
    """One-line failure message, so the red/green harness reads the reason of each failure."""

    if actual != expected:
        raise AssertionError(f"{what}: expected {expected!r}, got {actual!r}")


def _season_state(**flags: str) -> dict:
    """A life on season 1 after T3 A: Gus's «register.augustin_de_roncourt» flag is «tu»."""

    return {"living_story": {"season_script": {"id": "s1", "played": [], "flags": dict(flags), "signals": []}}}


@pytest.fixture()
def season_one(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")


@pytest.mark.parametrize("spelling", GUS_SPELLINGS, ids=[f"spelled-{i}" for i in range(len(GUS_SPELLINGS))])
def test_gus_is_tu_whatever_id_the_surface_calls_him_by(season_one, spelling) -> None:
    state = _season_state(**{"register.augustin_de_roncourt": "tu"})
    expect(character_register(state, "augustin_de_roncourt"), "tu", "the scene's reading")
    expect(character_register(state, spelling), "tu", f"Gus spelled {spelling!r} in the Courrier")


@pytest.mark.parametrize("spelling", GUS_SPELLINGS, ids=[f"spelled-{i}" for i in range(len(GUS_SPELLINGS))])
def test_a_register_recorded_under_the_registry_id_answers_to_every_spelling(spelling) -> None:
    state = {"relationships": {"augustin_de_roncourt": {"register": "tu"}}}
    expect(character_register(state, spelling), "tu", f"Gus spelled {spelling!r}")


def test_the_season_opening_is_read_through_aliases_too(season_one) -> None:
    expect(character_register({}, "margaux"), "tu", "margaux")
    expect(character_register({}, "romy"), "tu", "romy")
    # The season writes Odile «odile», the registry «odile_ferrand».
    expect(character_register({}, "odile_ferrand"), "tu", "odile_ferrand")
    expect(character_register({}, "odile"), "tu", "odile")
    expect(character_register({}, "gus"), "vous", "gus before T3")


def test_the_landlord_stays_vous_under_his_aliases() -> None:
    state = {"relationships": {"landlord_marchand": {"register": "tu"}}}
    expect(character_register(state, "marchand"), "vous", "marchand")
    expect(character_register(state, "landlord"), "vous", "landlord")


def test_a_story_letter_from_gus_is_tu_all_the_way_to_the_reply(season_one) -> None:
    """The EXACT stock letter of the issue («Bonjour, c'est Gus. … Et vous, qu'en pensez-vous ?»)
    and its «Merci pour votre message» must not reach a learner Gus tutoie."""

    from app.services import story_correspondence as courrier
    from app.services.missions import MissionGenerator, _unassessed_acknowledgement

    thread = SimpleNamespace(state=_season_state(**{"register.augustin_de_roncourt": "tu"}), world_bible={})
    register = courrier.learner_register(thread, "gus")
    facts = courrier.story_letter_context(
        {"character_id": "gus", "character_name": "Gus", "register": register, "summary_fr": "La fête."}
    )
    generator = MissionGenerator.__new__(MissionGenerator)
    context = generator._custom_context({**facts, "summary_fr": "La fête."})
    _title, _brief, messenger, _objectives = generator._story_born_mission(
        title="", brief="", messenger={}, custom_context=context, learner_band="A2"
    )
    opening = messenger["opening_message"]
    expect(register, "tu", "the register the Courrier resolves for «gus»")
    expect("vous" in opening.lower().split(), False, f"the opening addresses Gus's friend as vous: {opening!r}")
    expect(opening.startswith("Salut, c'est Gus"), True, f"the opening {opening!r}")
    expect(messenger["target_register"].startswith("tu"), True, "target_register")

    reply = _unassessed_acknowledgement(SimpleNamespace(prompt_payload={"messenger": messenger}))
    expect("votre" in reply or "vous" in reply.lower().split(), False, f"the fallback reply {reply!r}")


def test_the_fallback_reply_reads_the_register_the_letter_was_written_in() -> None:
    """A tu letter whose opening happens to start «Bonjour» still gets a tu reply."""

    from app.services.missions import _unassessed_acknowledgement

    tu_letter = SimpleNamespace(
        prompt_payload={
            "messenger": {"target_register": "tu / registre familier", "opening_message": "Bonjour, c'est Gus."}
        }
    )
    expect(
        _unassessed_acknowledgement(tu_letter),
        "Merci pour ton message, je l'ai bien lu. Je te réponds vite.",
        "a tu letter's fallback reply",
    )
    vous_letter = SimpleNamespace(
        prompt_payload={
            "messenger": {"target_register": "vous / registre poli", "opening_message": "Salut, c'est Gus."}
        }
    )
    expect(
        _unassessed_acknowledgement(vous_letter).startswith("Merci pour votre message"), True, "a vous letter's reply"
    )
