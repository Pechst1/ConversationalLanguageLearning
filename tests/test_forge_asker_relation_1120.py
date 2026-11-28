"""#1120: La Forge put «Ton frère te demande :» under Lila's badge.

Live walk of 28 Nov 2026 (production, A1.1, day 46, La Forge on «On = we», item 2/6): the
prompt read «Ton frère te demande : « On mange où ce soir ? »», under it the speaker chip
«Lila» and her register token «tu». Lila is the learner's accomplice, not their brother.

ROOT CAUSE #147: the item names its asker by what they are to the learner («ton frère»),
and ``_with_serial_conversation`` read the item's cast only by names: a relation word was
nobody to it, so the beat's character went on a line the item had given to someone else.
The registry now reads the asker a relation word names (``relation_speaking``) and who of
the cast holds that relation (``relation_holders``): the badge is that person when the
learner has met them, and no badge (no chip, no register token) when nobody of the cast
is what the prompt says.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.test_one_cast_147 import _context, _day_19, _payload, _served

WALK_PROMPT = "Ton frère te demande : « On mange où ce soir ? » Réponds avec « on »."


def _serve(prompt: str, answer: str = "On mange chez Margaux.") -> dict:
    from app.api.v1.endpoints.atelier import _with_serial_conversation

    return _served(
        _with_serial_conversation(
            _payload(prompt, answer),
            context=_context(_day_19()),
            concept=SimpleNamespace(id=1, name="on"),
        )
    )


def test_the_walk_item_does_not_go_out_under_lila():
    """The EXACT live-walk item: «Ton frère te demande :» never stands under «Lila»."""

    item = _serve(WALK_PROMPT)
    character = item.get("character") or {}
    assert character.get("name") != "Lila", f"«Ton frère te demande :» under {character}"
    # Nobody of the cast is the learner's brother: no chip, so no stray «tu» token.
    assert "character" not in item, item.get("character")
    assert "serial_context" not in item


@pytest.mark.parametrize(
    ("prompt", "name"),
    [
        # The relation the cast gives Marin is «ton ami»: his badge, with his register.
        ("Ton ami te demande : « On mange où ce soir ? »", "Marin"),
        # Lila is «ta complice».
        ("Ta complice te demande : « On mange où ce soir ? »", "Lila"),
        # The prompt names the speaker: the badge is that person's (#147, 14 Nov).
        ("Lila te demande : « On mange où ce soir ? »", "Lila"),
    ],
)
def test_the_badge_is_the_person_the_relation_names(prompt, name):
    item = _serve(prompt)
    assert (item.get("character") or {}).get("name") == name, item.get("character")


@pytest.mark.parametrize(
    "prompt",
    [
        "Ta sœur te demande : « On va au cinéma ? »",
        "Un collègue te demande : « On déjeune ensemble ? »",
        "Ta voisine : « On se voit demain ? »",
    ],
)
def test_an_asker_nobody_of_the_cast_is_goes_out_plain(prompt):
    assert "character" not in _serve(prompt)


def test_the_registry_reads_the_relation_that_speaks():
    from app.services.cast_registry import relation_holders, relation_speaking

    assert relation_speaking(WALK_PROMPT) == "ton frère"
    assert relation_speaking("Ta voisine : « On se voit demain ? »") == "ta voisine"
    assert relation_speaking("« On mange où ? », demande ton ami.") == "ton ami"
    assert relation_speaking("Ton frère est au café.") is None
    assert relation_holders("ton frère") == []
    assert relation_holders("ton ami") == ["marin_leveque"]
    assert relation_holders("la patronne") == ["margaux_barman"]
