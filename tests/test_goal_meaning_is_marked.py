"""R5 (CI walk «en + B1», 19 Nov): «The neighbours have run out of milk? Construis la phrase :
« I'll bring them some this afternoon. » Un mot est en trop.» — the meaning a French goal
quotes is the learner's own language and is now named for the screen to mark with ``lang``.
"""

from __future__ import annotations

from app.services import item_bank as ib
from tests.test_native_meaning_goals import _word_bank


def _marks(item: dict) -> list[dict]:
    return item.get("goal_native_marks") or []


def test_a_french_goal_names_the_meaning_it_quotes_and_its_language() -> None:
    for native, meaning in (("de", "Sie können am Kanal entlang spazieren, Gus."), ("en", "They can walk along the canal, Gus.")):
        item = ib.with_goal(_word_bank(), "fr", native)
        assert _marks(item) == [{"text": meaning, "lang": native}]
        assert meaning in item["goal_native"]
    # Another language reads the English floor, marked as English.
    assert _marks(ib.with_goal(_word_bank(), "fr", "es")) == [{"text": "They can walk along the canal, Gus.", "lang": "en"}]


def test_the_line_said_before_a_build_is_marked_too() -> None:
    item = {**_word_bank(), "context_l10n": {"en": "The neighbours have run out of milk?", "de": "Den Nachbarn ist die Milch ausgegangen?"}}
    out = ib.with_goal(item, "fr", "en")
    assert out["goal_native"].startswith("The neighbours have run out of milk? Construis la phrase : «")
    assert _marks(out)[0] == {"text": "The neighbours have run out of milk?", "lang": "en"}


def test_no_marks_where_the_goal_quotes_nothing_foreign() -> None:
    assert _marks(ib.with_goal(_word_bank(), "fr", "fr")) == []
    assert _marks(ib.with_goal(_word_bank(), "de", "de")) == []
    # A stored set's old marks never outlive the goal they belonged to.
    stale = {**_word_bank(), "goal_native_marks": [{"text": "x", "lang": "en"}]}
    assert _marks(ib.with_goal(stale, "fr", "fr")) == []


# R5 (CI walk «en + B1», day 3): «Corrige la phrase · It should say: "I'm going to the town
# hall to renew my passport."» — the follow-up's goal took the explanation language's
# template. The goal is interface: French from B1, quoting the meaning, marked.
def _judged() -> dict:
    from app.services.forge_grading import TO_CORRECT_LABEL

    return {
        "id": "j1",
        "correct_label": TO_CORRECT_LABEL,
        "prompt": "Je vais à la mairie pour renouvelle mon passeport.",
        "follow_up_key": {
            "corrected_fr": "Je vais à la mairie pour renouveler mon passeport.",
            "meaning": "I'm going to the town hall to renew my passport.",
            "meaning_l10n": {"de": "Ich gehe zum Rathaus, um meinen Pass zu verlängern."},
        },
    }


def test_a_b1_follow_up_goal_is_french_and_quotes_the_marked_meaning() -> None:
    from app.services.forge_grading import TO_CORRECT_LABEL, classify_follow_up

    for native, meaning in (
        ("en", "I'm going to the town hall to renew my passport."),
        ("de", "Ich gehe zum Rathaus, um meinen Pass zu verlängern."),
    ):
        out = classify_follow_up(_judged(), TO_CORRECT_LABEL, band="B1", language=native, chrome="fr")["follow_up"]
        assert out["goal_native"] == f"La phrase veut dire : « {meaning} »"
        assert out["goal_native_marks"] == [{"text": meaning, "lang": native}]


def test_below_b1_the_follow_up_goal_is_unchanged() -> None:
    from app.services.forge_grading import TO_CORRECT_LABEL, classify_follow_up

    out = classify_follow_up(_judged(), TO_CORRECT_LABEL, band="A1", language="en", chrome="en")["follow_up"]
    assert out["goal_native"] == 'It should say: "I\'m going to the town hall to renew my passport."'
    assert "goal_native_marks" not in out
