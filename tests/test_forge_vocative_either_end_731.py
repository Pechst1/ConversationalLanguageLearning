"""#731, walk of 12 Nov 2026: «Margaux, sie sind glücklich.» answered «Margaux, ils sont
heureux.» stayed «nicht geprüft».

The item (``fr2-a11-etre-conversation-1b3fa9675c``, frame ``etre-adj~voc``) stores the name
last: «Ils sont heureux, Margaux.» / «Elles sont heureuses, Margaux.». The German goal puts
it first (#384, so «Sie» reads as «they»). A name set off by a comma may stand at either end
of the sentence; the key's one accept-list (:func:`answer_acceptance.widened_answers`, #174)
knew a moved place phrase but not a moved vocative.
"""
from __future__ import annotations

PROMPT = {
    "items": [
        {
            "id": "fr2-a11-etre-conversation-1b3fa9675c",
            "prompt_en": "They are happy, Margaux.",
            "prompt_l10n": {"en": "They are happy, Margaux.", "de": "Margaux, sie sind glücklich."},
            "accepted_answers": ["Elles sont heureuses, Margaux.", "Ils sont heureux, Margaux."],
            "example_answer": "Ils sont heureux, Margaux.",
        }
    ]
}


def _local(text: str) -> str:
    from app.services.atelier import _accepted_answers
    from app.services.forge_grading import production_local_check

    item = PROMPT["items"][0]
    return production_local_check(None, text, item["example_answer"], _accepted_answers(PROMPT))["local_status"]


def test_the_name_said_first_is_the_same_sentence() -> None:
    assert _local("Margaux, ils sont heureux.") == "right", "the key reads a vocative at either end"
    assert _local("Margaux, elles sont heureuses.") == "right"
    assert _local("Ils sont heureux, Margaux.") == "right"


def test_a_right_answer_by_the_key_needs_no_model(db_session) -> None:
    """«right» locally is the key's verdict: it counts with no model call (#401)."""

    from app.services import verdicts

    status = _local("Margaux, ils sont heureux.")
    check = verdicts.from_forge(
        {"assessment_status": "checked", "local_status": status, "verdict": "correct"}, text="Margaux, ils sont heureux."
    ).to_dict()
    assert (check["outcome"], check["checked_by"], check["call"], check["counts"]) == ("right", "key", "not_called", True)


def test_moving_the_name_loosens_nothing_else() -> None:
    assert _local("Margaux, ils est heureux.") == "checking", "a wrong verb form is still not right"
    assert _local("Margaux, ils sont heureuses.") == "checking"
    assert _local("Ils Margaux sont heureux.") == "checking", "only the ends of the sentence take the name"
    assert _local("Margaux, sont heureux.") == "checking"


def test_the_widened_key_moves_a_name_both_ways_and_only_a_name() -> None:
    from app.services.answer_acceptance import fold_typography, widened_answers

    folded = {fold_typography(item) for item in widened_answers(["Lila, tu es prête ?"])}
    assert fold_typography("Tu es prête, Lila ?") in folded
    # A capital that starts the sentence is not a name: «Alors, il est là.» keeps its order.
    assert {fold_typography(item) for item in widened_answers(["Alors, il est là."])} == {"alors il est là"}
    # Two sentences: the name belongs to the one it closes.
    assert len(widened_answers(["Bonjour. Il est là, Gus."])) == 1
