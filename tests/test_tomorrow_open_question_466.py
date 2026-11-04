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


def test_the_push_fallback_keeps_the_closing_question(monkeypatch):
    """The recap snapshot's hook is up to ENGINE_TEASER_CHARS long; the push must not clip it again.

    One limit for one line: with no ``next_teaser`` in the story state the push reads the
    snapshot's ``teaser_fr``, and a shorter clip there cut the question off («…»).
    """

    from app.services import serial_notifications

    hook = (
        "J'ai rien entendu. Mais quand même… Je repense à ce détail. "
        "Marin pose une petite bouillotte rouge près du radiateur du studio, avec un mot plié dessous. "
        "Pourquoi, à ton avis ?"
    )
    assert 160 < len(hook) <= 260
    journey = SimpleNamespace(
        recap_snapshot={"teaser_fr": hook},
        scenario_snapshot={"character_id": "margaux_barman", "character_name": "Margaux"},
        local_date=None,
    )
    monkeypatch.setattr(serial_notifications, "_latest_journey", lambda db, user: journey)
    db = SimpleNamespace(scalar=lambda *_args, **_kwargs: None)  # no active thread, no next_teaser
    pushed = serial_notifications.engine_teaser(db, SimpleNamespace(id=1))
    assert pushed is not None
    assert pushed["text_fr"] == hook, f"the push cut the hook: «{pushed['text_fr']}»"
    assert pushed["text_fr"].endswith("?")


def test_margauxs_hook_of_4_nov_is_a_sentence_with_a_question_not_her_opener():
    """Live walk 4 Nov: Home's «Tomorrow» read «J'ai rien entendu», Margaux's voice opener."""

    teaser = engine.next_teaser(
        _live("Margaux range une lettre sans nom dans le tiroir du comptoir."),
        {},
        character_id="margaux_barman",
        register="tu",
        date="2026-11-04",
        seed="t",
        name="Margaux",
    )
    assert teaser is not None
    text = teaser["text_fr"]
    assert text.startswith("J'ai rien entendu."), "the opener is the voice, not the hook"
    assert text.rstrip().endswith("?"), f"not a question: «{text}»"
    assert len(text.split()) > 3
    assert teaser["open_fr"] == "Margaux range une lettre sans nom dans le tiroir du comptoir."
    assert not text.startswith(teaser["open_fr"])
