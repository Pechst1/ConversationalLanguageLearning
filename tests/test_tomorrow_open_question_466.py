"""Live walk 2 Nov 2026 (#466): the Done screen and Home ended on «Dis, j'y repense…».

The day's hook was «Dis, j'y repense… C'est peut-être un signe. Je repense à ce détail.
Marin pose une petite bouillotte rouge près du radiateur.»: a voice opener, a frame and
a planted detail told as a statement. Nothing in it was a question the learner could
carry into tomorrow, and the «Tomorrow» line was cut from its first words, which are the
character's voice, not the open fact.

Root cause: ``compose_teaser`` glued the voice, the frame and the row into one string
and kept no record of which words are the open fact; every surface then guessed the
heart of the line from the prose. The teaser now ends on a question about the open row,
and names the row's words (``open_fr``) so no surface cuts the prose to find them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services.achievement_recap import recap_teaser

BOUILLOTTE = "Marin pose une petite bouillotte rouge près du radiateur."


def _live(plant: str = BOUILLOTTE) -> dict:
    return {"planted": [{"id": "e1:plant", "text_fr": plant, "status": "open", "character_id": "marin_leveque"}]}


def _teaser(live: dict, world: dict | None = None, *, register: str = "tu") -> dict:
    teaser = engine.next_teaser(
        live, world or {}, character_id="marin_leveque", register=register, date="2026-11-02", seed="t", name="Marin"
    )
    assert teaser is not None
    return teaser


def test_the_walks_hook_ends_on_a_question_about_the_open_fact():
    """The 2 Nov hook: an open planted detail, Marin speaking, tu."""

    teaser = _teaser(_live())
    text = teaser["text_fr"]
    assert text.startswith("Dis, j'y repense…")
    assert BOUILLOTTE in text, "the hook names the open fact"
    assert text.rstrip().endswith("?"), f"the hook ends on a statement, not a question: «{text}»"
    assert text.index(BOUILLOTTE) < text.rindex("?"), "the question comes after the fact it asks about"


@pytest.mark.parametrize("register", ["tu", "vous"])
@pytest.mark.parametrize("variant", [0, 1])
def test_every_kind_of_open_row_closes_on_a_question(register, variant):
    live = {
        "commitments": [
            {"id": "c1", "status": "open", "witnesses": ["marin_leveque"], "source_quote": "Je viens samedi."}
        ],
        "planted": [{"id": "p1", "text_fr": BOUILLOTTE, "status": "open", "character_id": "marin_leveque"}],
    }
    rows = engine.teaser_candidates(live, {})
    rows.append({"ref": "s1:0", "kind": "thread", "text_fr": "Qui était Odile", "characters": []})
    assert {row["kind"] for row in rows} == {"commitment", "plant", "thread"}
    for row in rows:
        text = engine.compose_teaser(row, character_id="marin_leveque", register=register, variant=variant)
        assert text.rstrip().endswith("?"), f"{row['kind']}/{register}/{variant}: «{text}»"


def test_the_teaser_names_the_open_fact_apart_from_the_voice():
    teaser = _teaser(_live())
    assert teaser.get("open_fr") == BOUILLOTTE
    assert not teaser["text_fr"].startswith(BOUILLOTTE)


def test_the_recap_carries_the_open_fact_and_the_whole_closing_question():
    # A long detail is clipped for the hook; the question after it must survive the recap's own clip.
    long_detail = "Marin pose une petite bouillotte rouge près du radiateur du studio de Lila, avec un mot plié dessous."
    teaser = _teaser(_live(long_detail))
    journey = SimpleNamespace(
        scenario_snapshot={"character_id": "marin_leveque", "character_name": "Marin"}, id="j1", steps=[]
    )
    shown = recap_teaser(SimpleNamespace(cefr_estimate="A1.1"), journey, {"next_teaser": teaser})
    assert shown.get("open_fr") == teaser.get("open_fr")
    assert shown["text_fr"] == teaser["text_fr"], "the recap's clip cut the closing question"
    assert shown["text_fr"].endswith("?")
