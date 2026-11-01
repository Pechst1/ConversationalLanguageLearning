"""Owner decision 2026-11-01: the daily vocabulary review deals no cloze card.

«The example-sentence cards where the word is missing mostly don't work, it's too hard to
get to the word. Instead: you translate the word, and you get the example sentence along
with it.» The top rung of the recall ladder is production (meaning → French, the card
carries its example). The drill picked its own card type with its own thresholds when the
server sent none; it now falls back to the server's table, mirrored in
``web-frontend/components/lexique/recall-ladder.ts`` — this test holds the two together.
"""

from __future__ import annotations

import re
from itertools import product
from pathlib import Path
from types import SimpleNamespace

from app.services.recall_ladder import (
    LADDER_RUNGS,
    LEECH_LAPSES,
    RUNGS,
    THRESHOLDS,
    card_ladder,
    rung,
)

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "web-frontend" / "components" / "lexique" / "recall-ladder.ts"

STABILITIES = [None, 0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 14.0, 21.0, 30.0, 45.0, 90.0, 365.0, 4000.0]
LEVELS = [None, "", "A1", "A2", "B1", "B1.1", "B2", "C1", "C2", "zz"]


def test_the_rung_is_never_cloze_at_any_stability_or_band():
    for stability, level, reps, lapses in product(STABILITIES, LEVELS, (0, 1, 3, 12), (0, 2, LEECH_LAPSES)):
        got = rung(stability=stability, reps=reps, lapses=lapses, level=level)
        assert got != "cloze", (stability, level, reps)
        assert got in LADDER_RUNGS
    assert "cloze" not in LADDER_RUNGS


def test_a_well_held_word_is_translated_at_the_top():
    for level, (_production, _audio, top) in THRESHOLDS.items():
        assert rung(stability=top, reps=4, lapses=0, level=level) == "production"
        assert rung(stability=top * 10, reps=4, lapses=0, level=level) == "production"


def _word(example: str) -> SimpleNamespace:
    return SimpleNamespace(word="la serrure", example_sentence=example)


def test_card_ladder_never_deals_a_cloze():
    contexts = [None, {"sentence_fr": "Tu as vu la serrure ?", "speaker_id": "margaux_barman"}]
    examples = ["Il change la serrure de la porte.", "", "Les serrures du quartier."]
    for stability, level, reps, lapses, context, example in product(
        STABILITIES, LEVELS, (0, 1, 2, 3, 9), (0, LEECH_LAPSES, 8), contexts, examples
    ):
        progress = SimpleNamespace(reps=reps, lapses=lapses, stability=stability, context=context)
        card = card_ladder(progress, _word(example), level=level)
        assert card["ladder"] in LADDER_RUNGS | {"scene", "rescue"}, card
        if card["ladder"] == "rescue":
            cue = card["rescue_cue"]
            assert cue["first_letter"] and cue["length"], "a rescue keeps its letter-and-length cue"


def test_the_drill_falls_back_to_the_servers_own_table():
    source = CLIENT.read_text(encoding="utf-8")
    block = re.search(r"LADDER_THRESHOLDS[^=]*=\s*\{(.*?)\};", source, re.S)
    assert block, "the drill's fallback table is gone"
    client = {
        band: tuple(float(n) for n in numbers.split(","))
        for band, numbers in re.findall(r"(A1|A2|B1|B2|C1):\s*\[([^\]]+)\]", block.group(1))
    }
    assert client == THRESHOLDS
    steps = re.search(r"LADDER_RUNGS[^=]*=\s*\[([^\]]+)\]", source)
    assert steps and tuple(re.findall(r"'(\w+)'", steps.group(1))) == RUNGS
    assert "'cloze'" not in re.search(r"export type CardMode = ([^;]+);", source).group(1)
