"""«Papier · l'écho» on the page: the record the night writer reads and the guard behind it.

Real-model run of 22 Nov 2026 (Sonnet 5.5 writer, 7 scenes): the echo never reached the night
writer (``story_split``'s payloads are whitelists), and nothing but the prompt held a written
echo to «once, by someone who was there, nothing beyond the record».
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.services import living_story as engine
from tests.test_living_story import _scene_context, draft

ECHO = {
    "instruction": "…",
    "when_fr": "hier",
    "headline_fr": "Le Goncourt retire le roman de Thélyson Orélien de sa sélection",
    "rubric": "culture",
    "desk_fr": "Le comptoir",
    "learner_did": {"stance": "contre", "sentence_fr": "Je suis contre, parce que l'écrivain dit non."},
    "present": [{"id": "romy_tremblay", "name": "Romy"}, {"id": "margaux_petit", "name": "Margaux"}],
    "kept_words": ["la sélection"],
}


def _context(**extra) -> dict:
    context = _scene_context(**extra)
    context["world"]["cast"] = [
        {"id": "romy_tremblay", "name": "Romy Tremblay"},
        {"id": "lila_bonnet", "name": "Lila Bonnet"},
        {"id": "margaux_petit", "name": "Margaux Petit"},
    ]
    return context


def _page(*lines: tuple[str, str]) -> engine.SceneDraft:
    """The fixture page with these (speaker, line) said in its second panel."""

    value = draft(_context(), 0)
    value = deepcopy(value)
    value["panels"][1]["dialogue"] = [
        {"character_id": who, "text_fr": text, "text_native": f"[en] {text}"} for who, text in lines
    ]
    return engine.SceneDraft.model_validate(value)


def test_a_page_without_an_echo_passes_and_one_true_echo_by_someone_who_was_there_passes():
    context = _context(papier_echo=ECHO)
    engine._validate_scene(_page(("romy_tremblay", "Vous avez une idée ?")), context)
    engine._validate_scene(_page(("romy_tremblay", "Notre papier sur le Goncourt est sorti, hier !")), _context(papier_echo=ECHO))
    # A sheet of paper is not the newspaper.
    engine._validate_scene(_page(("lila_bonnet", "Le stylo gratte le papier.")), _context(papier_echo=ECHO))


def test_an_echo_said_twice_is_refused():
    page = _page(
        ("romy_tremblay", "Notre papier sur le Goncourt est sorti !"),
        ("margaux_petit", "Le Goncourt retire le roman, je n'en reviens pas."),
    )
    with pytest.raises(engine.StoryUnavailable, match="papier_echo_repeated") as raised:
        engine._validate_scene(page, _context(papier_echo=ECHO))
    assert "once" in (raised.value.hint or "")


def test_an_echo_in_the_mouth_of_someone_who_was_not_there_is_refused():
    page = _page(("lila_bonnet", "J'ai lu ton article sur le Goncourt !"))
    with pytest.raises(engine.StoryUnavailable, match="papier_echo_absent_speaker") as raised:
        engine._validate_scene(page, _context(papier_echo=ECHO))
    assert "lila_bonnet" in (raised.value.hint or "")


@pytest.mark.parametrize(
    "line, invented",
    [
        ("Notre papier sur le Goncourt : 8 romans restent, c'est fou.", "8"),
        ("Le Goncourt retire le roman, et Gallimard ne dit rien.", "Gallimard"),
    ],
)
def test_an_echo_that_states_a_number_or_name_beyond_the_record_is_refused(line, invented):
    with pytest.raises(engine.StoryUnavailable, match="papier_echo_beyond_record") as raised:
        engine._validate_scene(_page(("romy_tremblay", line)), _context(papier_echo=ECHO))
    assert invented in (raised.value.hint or "")


def test_without_an_echo_in_the_context_the_guard_reads_nothing():
    page = _page(
        ("lila_bonnet", "J'ai lu ton article sur le Goncourt : 8 romans !"),
        ("lila_bonnet", "Le Goncourt retire le roman, et Gallimard ne dit rien."),
    )
    engine._validate_scene(page, _context())
