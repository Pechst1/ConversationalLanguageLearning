"""Nightly explore walk, 13 Oct 2026: the three story findings (#105, #107, #108).

1. #105 — after the last question of an authored season page, the closing nudge
   («Et on se quitte comme ça ?») bought one more exchange. The page had already
   played its close; the learner was sent back to the last question, the counter
   grew from «1 of 2» to «3 of 3», and the next answer replayed the close.
2. #107 — Camille's look was only sent once the learner chose it in T1 B, a choice
   no screen poses: Camille stayed a blank «C» while the story already said «il» or
   «elle» from the seeded flag. The headline now sends that same seeded look.
3. #108 — at A1, Lila's stairwell line read as a refusal of her own offer («Pas comme
   ça, non.»), and the ending said «Tu pars mercredi» as if the learner had said so.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services.season.clock import SEASON_KEY
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.story_headline import cast_variants
from tests import learner_walk as walk
from tests.test_learner_walk import (  # noqa: F401
    assembled_client,
    clock,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


# ---------------------------------------------------------------------------
# 1. #105 · the close plays once
# ---------------------------------------------------------------------------


class _Scripted(walk.Answerer):
    def __init__(self, texts: list[str]):
        super().__init__("good")
        self.texts = list(texts)

    def reply(self, step, examples, native):
        return self.texts.pop(0) if self.texts else (examples[0] if examples else "Je ne sais pas.")


def test_an_off_script_last_answer_closes_the_page_once(
    monkeypatch, assembled_client, db_session, journey_enabled, clock, production_day  # noqa: F811
):
    """The walk's a2-en day 1 on the walk's own fake provider (scripts/dev_story_engine_server.py)."""

    import dev_story_engine_server as dev

    from app.services import living_story as engine

    fake = dev.FakeStoryProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    persona = walk.Persona("a2-en", "en", "A2.1", "off-script answers")
    headers, _email = walk.register(assembled_client, persona)
    transcript = walk.play_day(
        assembled_client,
        db_session,
        headers,
        persona=persona,
        quality="good",
        day=1,
        answerer=_Scripted(
            [
                "Je suis la petite-fille d'Odile. Je viens pour l'appartement.",
                "Non, ce soir je reste ici. Je veux parler avec vous. Qui est Solvel ?",
                "Oui, je vais monter ce soir. Je veux voir l'appartement.",
            ]
        ),
    )
    answered = [event for event in transcript["events"] if event["step"]["kind"] == "respond" and event.get("result")]
    replies = [str(event["result"].get("character_reply_fr") or "") for event in answered]
    assert sum("Camille Marchand" in reply for reply in replies) == 1, replies
    last = answered[-1]["result"]
    assert "Camille Marchand" in str(last.get("character_reply_fr")), "the off-script answer is the last one"
    assert last.get("next_turn") is None, "a closed page asks nothing more"
    assert "Et on se quitte comme ça ?" not in str(last.get("character_reply_fr"))
    planned = {event["step"]["prompt"].get("max_turns") for event in answered}
    # Le Quartier phase 1: T1 A plans four exchanges (Gus, the café crème, Margaux's
    # stairs, the key); a learner the café passes over closes on the third.
    assert planned == {4}, f"the exchange count does not grow: {planned}"


# ---------------------------------------------------------------------------
# 2. #107 · Camille has a face from the night she walks in
# ---------------------------------------------------------------------------


def test_the_headline_sends_the_look_the_story_already_plays(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    seed = "learner-1"
    seeded = effective_flags(load_season("s1"), {}, seed=seed)["s1.camille_gender"]
    assert cast_variants({}, seed=seed) == {"camille_marchand": seeded}
    assert cast_variants({SEASON_KEY: {"id": "s1", "flags": {}}}, seed=seed) == {"camille_marchand": seeded}
    # The learner's own choice, once stored, wins.
    other = "m" if seeded == "f" else "f"
    stored = {SEASON_KEY: {"id": "s1", "flags": {"s1.camille_gender": other}}}
    assert cast_variants(stored, seed=seed) == {"camille_marchand": other}
    # Without a seed (La Revue's «chosen» test) nothing is guessed.
    assert cast_variants({SEASON_KEY: {"id": "s1", "flags": {}}}) == {}
    # Another season has no Camille.
    assert cast_variants({SEASON_KEY: {"id": "s2", "flags": {}}}, seed=seed) == {}


# ---------------------------------------------------------------------------
# 3. #108 · Lila does not turn down her own offer
# ---------------------------------------------------------------------------


def _said(page, panel_id):
    for movement in page["movements"]:
        if movement.get("id") == panel_id:
            return [line["text_fr"] for line in movement.get("lines") or []]
        panel = movement.get("panel") or {}
        if panel.get("id") == panel_id:
            return [line["text_fr"] for line in panel.get("lines") or []]
    raise AssertionError(panel_id)


@pytest.mark.parametrize("letter", ["lila", "nobody"])
def test_at_a1_the_stairwell_line_reads_as_the_closed_door_not_a_refusal(letter):
    season = load_season("s1")
    flags = {**effective_flags(season, {}, seed="x"), "s1.letter_trusted_to": letter}
    page = resolve_day(season, "t1", "b", flags=flags, band="A1", language="de")
    lila = _said(page, "b.r4")
    assert lila[0] == "Tu n'entres pas ? Je comprends."
    assert not any(line.endswith(", non.") for line in lila)
    ending = " ".join(_said(page, "b.last"))
    assert "billet de retour" in ending and "Tu pars" not in ending
