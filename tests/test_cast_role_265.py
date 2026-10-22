"""ROOT CAUSE #265 (child of #147): a person's role is one string in the cast registry.

Lila was «institutrice et peintre» in the Courrier header, an English paragraph
about a CE1 class in the generated Courrier, and Margaux was «serveuse» in one
letter and «Tient Le Mistral» in the cast intro: every surface typed its own copy.
The guard: every surface that prints a person's role prints the same text.
"""
from __future__ import annotations

import pytest

from app.services import missions
from app.services.cast_voices import speech_instructions
from app.services.journey_content import first_day_cast_intro
from app.services.living_story import _cast_with_pronouns
from app.services.season.intro import season_intro
from app.services.serial import SerialThreadService
from app.services.serial_notifications import CHARACTER_NAMES  # noqa: F401  (the teaser's names)

LANGUAGES = ("fr", "en", "de")


def _role_of(text: str) -> str:
    """The role is the first sentence of an intro line («Role. Trait.»)."""

    return text.split(". ")[0].strip().rstrip(".").casefold()


def _intro_roles(language: str) -> dict[str, str]:
    rows = season_intro("s1", language)["cast_intro"]
    return {row["character_id"]: _role_of(row["role_native"]) for row in rows}


def _first_day_roles(language: str) -> dict[str, str]:
    return {row["character_id"]: _role_of(row["role_native"]) for row in first_day_cast_intro(language)}


class _Thread:
    """What the generated Courrier reads: the world bible's own cast rows."""

    def __init__(self) -> None:
        import json

        from app.services.cast_registry import WORLD_PATH

        self.world_bible = json.loads(WORLD_PATH.read_text(encoding="utf-8"))


def _generated_courrier_role(character_id: str) -> str:
    service = SerialThreadService.__new__(SerialThreadService)
    return service._character_role(_Thread(), character_id).casefold()


@pytest.mark.parametrize("character_id", sorted(missions.CAST_ROLES_FR))
def test_the_courrier_prints_the_same_role_whether_authored_or_generated(character_id):
    authored = missions.CAST_ROLES_FR[character_id].casefold()
    assert _generated_courrier_role(character_id) == authored, (
        f"{character_id}: the generated Courrier header says one thing, the authored one another"
    )


@pytest.mark.parametrize("character_id", sorted(missions.CAST_ROLES_FR))
def test_the_cast_intro_and_the_courrier_agree_on_a_role(character_id):
    courrier = missions.CAST_ROLES_FR[character_id].casefold()
    intro = _intro_roles("fr").get(character_id)
    if intro is not None:
        assert intro == courrier, f"{character_id}: cast intro says «{intro}», the Courrier «{courrier}»"
    first_day = _first_day_roles("fr").get(character_id)
    if first_day is not None:
        assert first_day == courrier, f"{character_id}: first-day intro says «{first_day}», the Courrier «{courrier}»"


@pytest.mark.parametrize("language", LANGUAGES)
def test_both_cast_intros_print_the_same_role_in_every_language(language):
    season, first_day = _intro_roles(language), _first_day_roles(language)
    for character_id in sorted(set(season) & set(first_day)):
        assert season[character_id] == first_day[character_id], (
            f"{character_id} ({language}): «{season[character_id]}» vs «{first_day[character_id]}»"
        )


def test_the_first_letters_print_the_registry_role():
    for band, letter in missions.FIRST_LETTERS.items():
        cast_id = letter["character_id"]
        assert letter["contact_role"] == missions.CAST_ROLES_FR[cast_id], (band, cast_id)


def test_the_scene_prompt_hands_the_director_each_persons_role():
    cast = [{"id": cid, "name": cid, "role": "free text from the bible"} for cid in missions.CAST_ROLES_FR]
    rows = {row["id"]: row for row in _cast_with_pronouns(cast, flags={})}
    for cast_id, role in missions.CAST_ROLES_FR.items():
        assert rows[cast_id].get("role_fr") == role, f"{cast_id}: the scene prompt has no registry role"


def test_a_voice_persona_uses_the_same_role_as_the_courrier():
    persona = speech_instructions("lila_bonnet", "a2")
    assert missions.CAST_ROLES_FR["lila_bonnet"] in persona


def test_the_cast_intro_files_do_not_keep_a_second_copy_of_a_registry_role():
    import json

    from app.services.journey_content import FIRST_DAY_DATA_PATH
    from app.services.season.format import SEASON_ROOT

    for path in (SEASON_ROOT / "s1" / "intro.json", FIRST_DAY_DATA_PATH):
        for row in json.loads(path.read_text(encoding="utf-8"))["cast_intro" if path == FIRST_DAY_DATA_PATH else "cast"]:
            if row["character_id"] in missions.CAST_ROLES_FR:
                assert "role_native" not in row, f"{path.name}: {row['character_id']} types its own role"
