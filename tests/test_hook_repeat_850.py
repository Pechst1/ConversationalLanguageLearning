"""The same story question is not tomorrow's hook two days running, in other words (#850).

Live walk of 17 Nov 2026 (A1.1, day 36): 16 Nov's Done ended on «Margaux lira-t-elle la
lettre avec toi ?»; the learner answered «non» in the scene and «Non, je ne veux pas lire
la lettre maintenant» in the Courrier; 17 Nov's last panel and Done ended on «Margaux
va-t-elle lire la lettre ?». The teaser ledger compared yesterday's hook with today's
string for string, so the same question in another tense was a new hook.
"""

from __future__ import annotations

from app.services import living_story as engine
from app.services import story_teaser

#: The walk's two hooks, word for word.
NOV_16 = "Margaux lira-t-elle la lettre avec toi ?"
NOV_17 = "Margaux va-t-elle lire la lettre ?"
#: What else the story had open on 17 Nov: a detail Marin's scene planted.
PLANT = {
    "id": "e36:plant",
    "text_fr": "Une photo montre ta grand-mère avec un perroquet.",
    "status": "open",
    "character_id": "marin_leveque",
}
SCENE = (
    "Marin et le train. Marin ouvre le dossier bleu. Une photo montre ta grand-mère avec un "
    "perroquet. Margaux garde la lettre d'Odile. Lila veut partir. Margaux va-t-elle lire la lettre ?"
)


def _live_after_16_nov() -> dict:
    """The living story as 16 Nov's scene left it: its hook filed in the teaser ledger."""

    first = engine.next_teaser(
        {}, {}, character_id="margaux_barman", register="tu", date="2026-11-16", seed="walk-850",
        question=NOV_16,
    )
    assert first is not None and first["open_fr"] == NOV_16
    return {"planted": [PLANT], "teasers": engine.teasers_after({}, first)}


def test_the_walks_second_day_question_is_not_the_hook():
    """Done when: «Margaux lira-t-elle la lettre avec toi ?» (16 Nov) then «Margaux va-t-elle
    lire la lettre ?» (17 Nov) fails as the same question two days in a row."""

    hook = engine.next_teaser(
        _live_after_16_nov(), {}, character_id="marin_leveque", register="tu", date="2026-11-17",
        seed="walk-850", question=NOV_17,
    )
    assert hook is not None
    assert hook["open_fr"] != NOV_17, f"16 Nov's question asked again on 17 Nov: {hook}"
    assert "lettre" not in hook["text_fr"], hook
    # The story moves on to what else is open.
    assert hook["kind"] == "plant", hook


def test_the_scenes_own_open_question_is_held_to_the_same_rule():
    """With no writer, the question a character left open is the hook: not when an earlier
    day's hook asked it already (here: Margaux's «Tu peux lire cette lettre avec moi ?», the
    Courrier's opening on 17 Nov, left open in a scene)."""

    hook = engine.next_teaser(
        _live_after_16_nov(), {}, character_id="margaux_barman", register="tu", date="2026-11-18",
        seed="walk-850", question="Tu peux lire cette lettre avec moi ?",
    )
    assert hook is None or "lettre" not in hook["open_fr"], hook


def test_the_writers_question_is_dropped_before_any_surface_prints_it():
    """The writer's question is checked against the hooks already shown, so a tentpole's
    «Tomorrow» (``season_teaser(question=…)``), which never passes through ``next_teaser``,
    does not print it either."""

    asked = story_teaser.hooks_asked(_live_after_16_nov(), date="2026-11-17")
    assert asked == [NOV_16]
    assert story_teaser.question_problem(NOV_17, known=SCENE, asked=asked) == "tomorrow_asked_before"


def test_the_same_question_is_held_for_the_window_only():
    """Fourteen days on, the question may come back: the ledger's window, as for any hook."""

    hook = engine.next_teaser(
        _live_after_16_nov(), {}, character_id="marin_leveque", register="tu", date="2026-11-30",
        seed="walk-850", question=NOV_17,
    )
    assert hook is not None and hook["open_fr"] == NOV_17


def test_a_new_question_about_the_letter_is_a_new_hook():
    """A question that asks something more than yesterday's is the story moving on."""

    assert story_teaser.same_question("Qui a vraiment écrit cette lettre ?", NOV_16) is False
    assert story_teaser.same_question("Margaux va-t-elle ouvrir le tiroir ?", NOV_16) is False
    assert story_teaser.same_question("Lila va-t-elle partir demain ?", "Lila partira-t-elle demain ?") is True
    assert story_teaser.same_question(NOV_17, NOV_16) is True
    # Nothing to compare but the words themselves.
    assert story_teaser.same_question("Et toi ?", "Et Lila ?") is False
    assert story_teaser.same_question("Et toi ?", "Et toi ?") is True


def test_a_good_question_still_holds():
    assert story_teaser.question_problem("Qui a vraiment écrit cette lettre ?", known=SCENE, asked=[NOV_16]) is None
