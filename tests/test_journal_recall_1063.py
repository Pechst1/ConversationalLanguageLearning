"""#1063: the Journal's recall check credits a kept line only with words that carry it.

Live walk 25 Nov 2026 (A1.1, day 43). Retelling «L'autre côté» at La gérance Marchand
(day 42: one typed «non», then Marchand's «Je comprends. Votre grand-mère ne vous a rien
dit. Alors on est deux.» and the scene ended), the learner wrote «Hier, Marchand a dit :
non, ce nest pas possible. Margaux a peur de lui. Je veux garder le cahier de ma
grand-mere.» Marchand never said that, and the screen said «You recalled everything the
scene kept (1/1)».

The one kept line was Marchand's. Its cues hit were «grand» and «mere», the two halves of
one written word, and «dit», from «Marchand a dit», a word that only says who spoke:
three «hits» for a retell that recalls nothing of the line. :func:`invented_clauses`
already ruled that framing words prove no memory; the score did not ask.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.journal import scene_facts_for, scene_lines, score_content_recall

RETELL = (
    "Hier, Marchand a dit : non, ce nest pas possible. Margaux a peur de lui. "
    "Je veux garder le cahier de ma grand-mere."
)
MARCHAND = "Je comprends. Votre grand-mère ne vous a rien dit. Alors on est deux."
TURNS = [
    {
        "learner": "Non. Ma grand-mere est parti. Elle ne a rien dit a moi.",
        "character": MARCHAND,
        "correction": {"corrected_fr": "Non. Ma grand-mere est partie. Elle ne a rien dit a moi."},
    }
]
LEDGER = {"established": [{"key": "refus", "fact_fr": "L'apprenant refuse.", "quote": "Non", "at": 0}]}


def _gerance():
    """Day 42 as the 24 Nov walk describes it: Camille opens, one reply, Marchand answers."""
    scene = SimpleNamespace(
        ordinal=0,
        kind="scene",
        public_prompt={
            "setup_fr": "À la gérance, M. Marchand attend avec un dossier ouvert.",
            "character_line_fr": "Grand-père veut parler avec vous. Sans les autres.",
        },
        private_task={},
    )
    respond = SimpleNamespace(
        ordinal=1, kind="respond", public_prompt={}, private_task={"turns": TURNS, "ledger": LEDGER}
    )
    return SimpleNamespace(
        scenario_snapshot={
            "character_name": "M. Marchand",
            "location_name": "La gérance Marchand",
            "title_fr": "L'autre côté",
        },
        recap_snapshot={"story_outcome": {"callback_fr": "Pourquoi elle part ? Vous savez, vous ?"}},
        serial_episode_id="ep-42",
        steps=[scene, respond],
    )


def _score(text: str) -> dict:
    journey = _gerance()
    facts = [fact.as_dict() for fact in scene_facts_for(journey, story_context={})]
    return score_content_recall(text, facts, scene=scene_lines(journey), given={"marchand", "gerance"})


def test_the_scene_kept_marchands_line():
    held = [fact.text_fr for fact in scene_facts_for(_gerance(), story_context={})]
    assert held == [MARCHAND], held


def test_the_walks_invented_retell_is_not_everything_the_scene_kept():
    """#1063 done-when: «You recalled everything the scene kept (1/1)» for the walk's retell."""
    recall = _score(RETELL)
    found, total = len(recall["matched"]), recall["facts_total"]
    assert found < total, (
        f"«{RETELL}» was scored {found}/{total} («You recalled everything the scene kept») "
        f"on {recall['matched']}"
    )


def test_one_compound_word_is_one_piece_of_evidence():
    """«grand-mère» is one word: it cannot be the two cues a long line needs."""
    recall = _score("Ma grand-mère.")
    assert recall["matched"] == [], recall["matched"]


def test_who_spoke_is_not_what_was_said():
    """«a dit» frames a memory; the kept line's «rien dit» is not recalled by it."""
    recall = _score("Marchand a dit quelque chose sur ma grand-mère.")
    assert recall["matched"] == [], recall["matched"]


def test_a_true_retell_of_marchands_line_is_still_recalled():
    recall = _score("Marchand comprend : ma grand-mère ne lui a rien dit non plus. Ils sont deux.")
    assert len(recall["matched"]) == 1, recall


def test_a_line_made_only_of_frame_words_can_still_be_recalled():
    """A kept line with nothing but framing words keeps them, or it could never be found."""
    facts = [{"key": "k", "kind": "scene", "text_fr": "Il a dit pourquoi.", "cues": ["dit", "pourquoi"]}]
    recall = score_content_recall("Il a dit pourquoi.", facts)
    assert len(recall["matched"]) == 1, recall
