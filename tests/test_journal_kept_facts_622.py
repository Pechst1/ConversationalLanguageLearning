"""#622 (child of #145): the Journal holds a retell to what the scene said, not to its hook.

Live walk 9 Nov. Yesterday's scene was at the notary's with Camille. «What you remember:
None of what the scene kept appears (0/1). L'appartement est un souvenir de ta
grand-mère.» That line is ``callback_fr``, the hook that opens tomorrow, and it had also
appeared in another scene's panels that day. The same mistake as #539 with another line,
so the fix cannot be one more entry in the list of known fillers.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.closing_filler import is_closing_filler
from app.services.journal import scene_facts_for, score_content_recall

FILLER = "L'appartement est un souvenir de ta grand-mère."
NOTARY = "Maître Vasseur garde les papiers de la dette."
DEBT = "L'appartement paie d'abord mon grand-père."
QUESTION = "Vous êtes d'accord, non ?"


def _journey(turns, *, ledger=None, callback=FILLER, rubric="NEVER PUBLIC"):
    respond = SimpleNamespace(
        ordinal=1,
        kind="respond",
        public_prompt={},
        private_task={
            "rubric": rubric,
            "accepted": ["ACCEPTED ANSWER"],
            "response_task": {"suggested_response_fr": "HIDDEN SUGGESTION"},
            "turns": turns,
            "ledger": ledger or {},
        },
    )
    scene = SimpleNamespace(
        ordinal=0,
        kind="scene",
        public_prompt={"setup_fr": "Camille vous attend chez le notaire avec un dossier."},
        private_task={"rubric": rubric},
    )
    return SimpleNamespace(
        scenario_snapshot={"character_name": "Camille", "location_name": "Chez Maître Vasseur"},
        recap_snapshot={"story_outcome": {"callback_fr": callback}},
        serial_episode_id="ep-27",
        steps=[scene, respond],
    )


WALK_TURNS = [
    {"learner": "Bonjour, je ne comprend pas.", "character": f"{NOTARY} {QUESTION}",
     "correction": {"corrected_fr": "Bonjour, je ne comprends pas."}},
    {"learner": "Non, je ne paie pas la dette de ton frère.", "character": DEBT, "correction": None},
]
WALK_LEDGER = {
    "established": [
        {"key": "refuse_dette", "fact_fr": "L'apprenant refuse de payer la dette.",
         "quote": "je ne paie pas la dette de ton frère", "at": 1},
    ]
}


def test_the_hook_is_not_what_the_scene_kept():
    facts = scene_facts_for(_journey(WALK_TURNS, ledger=WALK_LEDGER), story_context={})
    assert FILLER not in [fact.text_fr for fact in facts]
    assert all(not is_closing_filler(fact.text_fr) for fact in facts)


def test_what_the_scene_kept_comes_from_its_replies():
    facts = scene_facts_for(_journey(WALK_TURNS, ledger=WALK_LEDGER), story_context={})
    assert [fact.kind for fact in facts] == ["said", "scene", "scene"]
    assert facts[0].text_fr == "je ne paie pas la dette de ton frère"
    assert NOTARY in [fact.text_fr for fact in facts]
    assert DEBT in [fact.text_fr for fact in facts]


def test_the_walks_retell_is_scored_against_the_scene():
    """They wrote about the notary, the papers and Camille tired: that now counts."""

    facts = scene_facts_for(_journey(WALK_TURNS, ledger=WALK_LEDGER), story_context={})
    recall = score_content_recall(
        "Hier, je suis allé chez le notaire. Maître Vasseur a les papiers. Camille est fatiguée.",
        [fact.as_dict() for fact in facts],
    )
    assert [row["text_fr"] for row in recall["matched"]] == [NOTARY]


def test_a_question_a_character_asked_is_not_a_fact():
    facts = scene_facts_for(_journey(WALK_TURNS), story_context={})
    assert all("?" not in fact.text_fr for fact in facts)


def test_a_fact_is_shown_in_the_learners_words_never_as_a_note_for_the_writers():
    ledger = {"established": [{"key": "a", "fact_fr": "L'apprenant a faim.", "quote": "j'ai faim", "at": 0}]}
    turns = [{"learner": "J'ai faim.", "character": "Moi aussi.", "correction": None}]
    facts = scene_facts_for(_journey(turns, ledger=ledger), story_context={})
    assert "L'apprenant" not in " ".join(fact.text_fr for fact in facts)


def test_a_corrected_reply_is_kept_as_it_was_corrected():
    ledger = {"established": [{"key": "a", "fact_fr": "L'apprenant a faim.", "quote": "je a faim beaucoup", "at": 0}]}
    turns = [{"learner": "Je a faim beaucoup.", "character": "Moi aussi.",
              "correction": {"corrected_fr": "J'ai très faim."}}]
    facts = scene_facts_for(_journey(turns, ledger=ledger), story_context={})
    assert facts[0].text_fr == "J'ai très faim."


def test_the_rubric_is_never_read():
    facts = scene_facts_for(_journey(WALK_TURNS, ledger=WALK_LEDGER), story_context={})
    held = " ".join(fact.text_fr for fact in facts)
    for hidden in ("NEVER PUBLIC", "ACCEPTED ANSWER", "HIDDEN SUGGESTION"):
        assert hidden not in held


def test_a_day_with_a_stock_exit_is_not_scored_on_it():
    """#518's line said nothing of the scene, and it is on stored rows for good."""

    turns = [{"learner": "Un dinosaure mange la lettre !", "character": "Attends, on m’appelle — je reviens vers toi très vite, promis."}]
    facts = scene_facts_for(_journey(turns, callback="Margaux a dû partir avant de répondre."), story_context={})
    assert [fact.kind for fact in facts] == ["setup"]


def test_a_day_from_before_the_record_still_has_its_outcome():
    facts = scene_facts_for(_journey([], callback="Romy a laissé la clé du premier étage."), story_context={})
    assert [fact.kind for fact in facts] == ["outcome"]


def test_a_long_scene_is_not_scored_out_of_ten():
    turns = [
        {"learner": f"Réponse {index}.", "character": f"Le voisin numéro {word} arrive avec un carton."}
        for index, word in enumerate(["un", "deux", "trois", "quatre", "cinq", "six"])
    ]
    facts = scene_facts_for(_journey(turns), story_context={})
    assert len(facts) == 2
    assert "six" in facts[-1].text_fr
