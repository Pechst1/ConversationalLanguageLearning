"""#282: a repair gap holds the words that differ, as its instruction says.

Live walk 22 Oct: «Replace «à le» with «au» here.» over a field holding
«à le marché aux puces»; typing «au», as told, was refused («the words in red still
need fixing»). The erratum's stretch was wider than the slip, and the gap took all
of it. ``repair_parts`` mirrors ``web-frontend/lib/repair-parts.ts``.
"""
from app.services.atelier import repair_line_from_parts, repair_parts

LINE = "Il est à le marché aux puces avec Romy"
WIDE = [{"learner_text": "à le marché aux puces", "corrected_target": "au marché aux puces", "task_error_type": "preposition"}]


def test_a_gap_holds_only_the_words_that_differ() -> None:
    parts = repair_parts(LINE, WIDE)
    assert parts == [
        {"text": "Il est "},
        {"wrong": "à le", "fix": "au", "erratum": 0},
        {"text": " marché aux puces avec Romy"},
    ]
    # The line a learner assembles from the one-word fix is the line the server accepts.
    assert repair_line_from_parts(LINE, WIDE) == "Il est au marché aux puces avec Romy"


def test_an_insertion_keeps_a_word_to_hold_its_gap() -> None:
    parts = repair_parts("Je vois la maison", [{"learner_text": "la maison", "corrected_target": "la grande maison"}])
    assert parts[1] == {"wrong": "maison", "fix": "grande maison", "erratum": 0}
