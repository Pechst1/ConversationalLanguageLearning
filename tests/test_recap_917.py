"""#917 (root cause #145) — a stored «Précédemment» or summary line never says «learner».

The live walk of 19 Nov opened «Romy et la tuque» on a «Previously» card that read
«La carte du learner trouve sa place parmi les souvenirs d’Odile.»: the English role
word the page's own voice is told to use («the learner», ``story_memory.NAME_SCOPE``)
was written into a French recap line, stored, and printed. Nothing between the model
and the card read the line.

The guard (``story_memory.role_placeholder`` / ``story_memory.address_placeholder``)
runs where a recap line is built (``living_story.previously_lines``,
``closing_filler.scene_fact``, ``day_contract.previously``) and where a stored one is
read back (``story_archive.previously_of``): the line speaks to the learner as «tu», or
it is not printed.
"""

from __future__ import annotations

import pytest

from app.services import closing_filler, living_story, story_archive

#: The exact line of the issue.
LEAK = "La carte du learner trouve sa place parmi les souvenirs d’Odile."
FIXED = "Ta carte trouve sa place parmi les souvenirs d’Odile."


def _role_words(lines: list[str]) -> list[str]:
    return [line for line in lines if any(word in line.casefold() for word in ("learner", "player"))]


def test_stored_card():
    """The card of the walk: a page stored before the fix is repaired when it is read."""

    lines = story_archive.previously_of({"previously_fr": ["Romy cherche sa tuque.", LEAK]})
    assert not _role_words(lines), f"the «Précédemment» card prints the placeholder: {lines}"
    assert lines == ["Romy cherche sa tuque.", FIXED]


def test_built_box():
    """A new page's box, built from the chapter's stored event summary."""

    live = {"events": [{"chapter_id": "c1", "summary_fr": LEAK}]}
    lines = living_story.previously_lines(live, chapter_id="c1")
    assert lines == [FIXED], f"the box is built from a summary that says «learner»: {lines}"


def test_unrepairable():
    """A placeholder the guard cannot turn into «tu» costs the line, never the card."""

    stored = ["Le learner trouve la carte d’Odile.", "Romy cherche sa tuque.", "The player keeps the key."]
    assert story_archive.previously_of({"previously_fr": stored}) == ["Romy cherche sa tuque."]
    live = {
        "events": [{"chapter_id": "c1", "summary_fr": "Odile donne la carte au player."}],
        "chronicle": [{"title_fr": "La tuque", "resolved_fr": "Romy retrouve sa tuque."}],
    }
    assert living_story.previously_lines(live, chapter_id="c1") == ["La tuque : Romy retrouve sa tuque."]


def test_contract(monkeypatch):
    """The day after a contract day, the box ends on what that day changed."""

    from app.config import settings
    from app.services.season import day_contract

    monkeypatch.setattr(settings, "STORY_DAY_CONTRACT", True, raising=False)
    after = [{"text_fr": LEAK, "day_index": 4}]
    live = {"day_index": 4, "season_script": {day_contract.LEDGER_KEY: {"after": after}}}
    assert day_contract.previously(live, ["Romy cherche sa tuque."]) == ["Romy cherche sa tuque.", FIXED]
    after[0]["text_fr"] = "Le learner garde la carte."
    assert day_contract.previously(live, ["Romy cherche sa tuque."]) == ["Romy cherche sa tuque."]


def test_scene_fact():
    """The event summary a later box reads is filed through ``scene_fact``."""

    assert closing_filler.scene_fact(LEAK, fallback="Romy et la tuque") == FIXED
    # A callback that cannot be said with «tu» falls to the next candidate.
    assert closing_filler.scene_fact("Le learner garde la carte.", "Romy garde la tuque.") == "Romy garde la tuque."


CAUGHT = [
    (LEAK, "learner"),
    ("Odile parle avec the learner.", "the learner"),
    ("Le player garde la clé.", "player"),
    ("Romy sourit au Learner.", "Learner"),
    ("The learner's card stays.", "The learner's"),
]


@pytest.mark.parametrize("text, word", CAUGHT, ids=[f"c{i}" for i in range(len(CAUGHT))])
def test_catches(text, word):
    """The guard fails on the standalone word, «the learner» and «player»."""

    from app.services.story_memory import role_placeholder

    assert role_placeholder(text) == word


FRENCH = ["L'apprenant garde la carte.", "Romy trouve sa tuque.", "Les learnerships n'existent pas ici.", "Le playerX"]


@pytest.mark.parametrize("text", FRENCH, ids=[f"f{i}" for i in range(len(FRENCH))])
def test_french(text):
    """A line without the role word is printed as it was stored."""

    assert story_archive.previously_of({"previously_fr": [text]}) == [text]


REPAIRS = [
    (LEAK, FIXED),
    ("Odile range les souvenirs du learner.", "Odile range tes souvenirs."),
    ("L’histoire du learner plaît à Romy.", "Ton histoire plaît à Romy."),
    ("Le carnet de la learner reste chez Odile.", "Ton carnet reste chez Odile."),
    ("Romy parle du learner à Odile.", "Romy parle de toi à Odile."),
    ("Odile reste près du player.", "Odile reste près de toi."),
    ("Le learner garde la carte.", None),
    ("Odile donne la carte au learner.", None),
    ("Odile parle avec the learner.", None),
    ("The learner's card stays.", None),
]


@pytest.mark.parametrize("text, fixed", REPAIRS, ids=[f"r{i}" for i in range(len(REPAIRS))])
def test_repair(text, fixed):
    """The stored line reads «tu», or is not printed."""

    assert story_archive.previously_of({"previously_fr": [text]}) == ([fixed] if fixed else [])
