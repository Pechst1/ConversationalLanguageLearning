"""#133, #250, owner decision D2: the corrected line holds every verified fix, and nothing else.

A model returns a sentence and a list as two pieces of text. The sentence was printed as it
came, so it could change what the learner asked, and change more than the list said. The
learner copies that line. No model call is made in this file.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from app.core.verdict import apply_edits, locate_edits
from app.services import correction_contract as cc
from app.services import missions as missions_module
from app.services.atelier import repair_line_from_parts
from app.services.forge_grading import reconcile_with_sentence, refine_production_correction
from app.services.journal import JournalService
from app.services.missions import MissionConversationService
from tests.test_correction_corpus import rule_card_mistakes
from tests.test_failed_check_counts_for_nothing import _a_grade, _begin, _Client

#: The live walk of 14 Oct 2026, word for word (#133).
LETTER = (
    "Salut Margaux ! Je ne vends pas le appartement. Camille a une clé aussi, c est bizarre. "
    "Qu est-ce que c est, jeudi a dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent"
)
REWRITE = (
    "Salut Margaux ! Je ne vends pas l'appartement. Camille a une clé aussi, c'est bizarre. "
    "C'est jeudi à dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent"
)
LISTED = [
    {
        "learner_text": "le appartement",
        "corrected_target": "l'appartement",
        "why_wrong": "«le» becomes «l'» before a vowel.",
        "task_error_type": "grammar",
    },
    {
        "learner_text": "c est bizarre",
        "corrected_target": "c'est bizarre",
        "why_wrong": "«c'est» takes an apostrophe.",
        "task_error_type": "grammar",
    },
]
QUESTION = "Qu est-ce que c est, jeudi a dix-huit heures ?"


def _pairs(errata) -> list[tuple[str, str]]:
    return [(item["learner_text"], item["corrected_target"]) for item in errata]


def _with_each_fix_made(text: str, errata) -> str:
    """The line a reader gets by making each listed change, and nothing else."""

    rows = [{"span": item["learner_text"], "replacement": item["corrected_target"]} for item in errata]
    return apply_edits(text, locate_edits(text, rows))


# --- the line ---------------------------------------------------------------------------------


def test_the_learners_question_stays_and_each_change_in_the_line_is_listed():
    checked = cc.verify_correction(LETTER, REWRITE, LISTED, language="en")

    assert "C'est jeudi" not in checked.corrected
    assert "jeudi à dix-huit heures ?" in checked.corrected, "the real fix the model did not list"
    assert ("jeudi a", "jeudi à") in _pairs(checked.errata), "and it is listed, by the «a» it means"
    assert "Camille a une clé" in checked.corrected, "the right «a» earlier in the line stays"
    assert checked.corrected == _with_each_fix_made(LETTER, checked.errata)
    assert [row["reason"] for row in checked.refused] == ["the_question"]


def test_a_listed_fix_goes_on_the_word_the_model_meant():
    line = "Camille a une clé, jeudi a dix-huit heures."
    listed = [{"learner_text": "a", "corrected_target": "à", "why_wrong": "«à» takes an accent.", "task_error_type": "grammar"}]

    checked = cc.verify_correction(line, "Camille a une clé, jeudi à dix-huit heures.", listed)

    assert checked.corrected == "Camille a une clé, jeudi à dix-huit heures."
    assert _with_each_fix_made(line, checked.errata) == checked.corrected


def test_two_fixes_with_the_same_words_are_both_made():
    line = "C est bon et c est bien."
    listed = [
        {"learner_text": "c est", "corrected_target": "c'est", "why_wrong": "apostrophe", "task_error_type": "grammar"},
        {"learner_text": "c est", "corrected_target": "c'est", "why_wrong": "apostrophe", "task_error_type": "grammar"},
    ]

    checked = cc.verify_correction(line, None, listed)

    assert checked.corrected.casefold() == "c'est bon et c'est bien."


def test_a_listed_rewrite_of_the_question_is_refused_too():
    checked = cc.verify_correction(
        QUESTION,
        None,
        [{"learner_text": "Qu est-ce que c est,", "corrected_target": "C'est", "why_wrong": "Plus naturel."}],
    )
    assert [row["corrected_target"] for row in checked.refused] == ["C'est"]
    assert all(item["corrected_target"] != "C'est" for item in checked.errata)
    assert "Qu'est-ce que c'est" in checked.corrected


@pytest.mark.parametrize(
    ("line", "sentence", "reason"),
    [
        pytest.param("J'ai un stylo.", "J'ai une voiture.", "words", id="another-thing"),
        pytest.param("Je visite avec Lila.", "Je visite le bel appartement avec Lila.", "words", id="words-added"),
        pytest.param("Je suis vraiment très content.", "Je suis content.", "words", id="words-taken-out"),
        pytest.param("Je vais à Lyon jeudi.", "Je vais à Lyon vendredi.", "words", id="another-day"),
        pytest.param("Mercredi je visite avec Lila.", "Je visite avec Lila mercredi.", "words", id="moved-far"),
        pytest.param("Où tu vas demain ?", "Pourquoi tu vas demain ?", "the_question", id="another-question"),
    ],
)
def test_a_change_nobody_listed_is_dropped_when_it_changes_what_was_said(line, sentence, reason):
    checked = cc.verify_correction(line, sentence, [])

    assert checked.corrected == line
    assert checked.errata == []
    assert {row["reason"] for row in checked.refused} == {reason}


@pytest.mark.parametrize(
    ("line", "sentence", "fix"),
    [
        pytest.param("Je suis tres content.", "Je suis très content.", "très", id="accent"),
        pytest.param("Elle est parti hier.", "Elle est partie hier.", "partie", id="agreement"),
        pytest.param("Je mange un pomme.", "Je mange une pomme.", "une", id="gender"),
        pytest.param("Je vais la gare.", "Je vais à la gare.", "à", id="missing-word"),
        pytest.param("Je ne pas parle allemand.", "Je ne parle pas allemand.", "parle pas", id="moved-word"),
        pytest.param("Est-ce que vous avez-vous du pain ?", "Est-ce que vous avez du pain ?", "avez", id="doubled"),
    ],
)
def test_a_real_fix_only_the_sentence_holds_is_kept_and_listed(line, sentence, fix):
    checked = cc.verify_correction(line, sentence, [])

    assert checked.corrected.rstrip(" .?") == sentence.rstrip(" .?")
    assert any(fix in item["corrected_target"] for item in checked.errata), checked.errata
    assert not checked.refused


def test_a_sentence_moved_around_is_a_rewrite_and_a_local_move_is_a_fix():
    assert cc.changes_what_was_said("Mercredi je visite avec Lila", "Je visite Lila mercredi") == "order"
    assert cc.changes_what_was_said("une rouge voiture", "une voiture rouge") is None


def test_a_word_of_another_language_may_become_the_french_word():
    assert cc.changes_what_was_said("le flat", "l'appartement") is None
    assert cc.changes_what_was_said("store", "magasin") is None


def test_a_listed_word_choice_stands_where_an_unlisted_one_does_not():
    assert cc.changes_what_was_said("librairie", "bibliothèque") == "words"
    assert cc.changes_what_was_said("librairie", "bibliothèque", listed=True) is None


def test_a_fix_found_by_the_rules_is_in_the_line_and_on_the_list():
    checked = cc.verify_correction("Je suis tres content.", None, cc.deterministic_errata("Je suis tres content."))
    assert checked.corrected == "Je suis très content."
    assert ("tres", "très") in _pairs(checked.errata)


def test_a_sentence_that_undoes_a_listed_fix_does_not_win():
    checked = cc.verify_correction(
        "Je suis tres content.",
        "Je suis tres content.",
        [{"learner_text": "tres", "corrected_target": "très", "why_wrong": "accent"}],
    )
    assert checked.corrected == "Je suis très content."


def test_notes_about_the_task_stay_listed_and_change_nothing_in_the_line():
    note = {"learner_text": LETTER, "corrected_target": "", "why_wrong": "Answer her question.", "task_error_type": "task_compliance"}
    word = {"learner_text": "visite", "corrected_target": "visiter", "why_wrong": "", "task_error_type": "vocabulary_target"}

    checked = cc.verify_correction("Mercredi je visite.", None, [note, word])

    assert checked.corrected == "Mercredi je visite."
    assert len(checked.errata) == 2


#: A fix only the sentence holds, on the rule cards' own mistakes. These are rephrasings the
#: model has to list to get through, like «Je sais Marie» -> «Je connais Marie».
CARD_FIXES_FLOOR = 0.75


def test_the_gate_lets_most_of_the_rule_cards_real_fixes_through():
    passed = refused = 0
    for wrong, right in rule_card_mistakes():
        wrong, right = re.sub(r"[{}]", "", wrong), re.sub(r"[{}]", "", right)
        for gap in cc.sentence_gaps(wrong, right) or []:
            if cc.changes_what_was_said(gap.wrong, gap.fix, question=cc.in_a_question(wrong, gap.wrong)):
                refused += 1
            else:
                passed += 1
    assert passed / (passed + refused) >= CARD_FIXES_FLOOR, (passed, refused)


# --- La Forge ---------------------------------------------------------------------------------


def _forge_result(errata, sentence):
    return {"verdict": "partial", "score_0_4": 2, "errata": errata, "lexical_gaps": [], "corrected_answer": sentence}


def test_forge_refuses_the_rewrite_as_a_gap():
    refined = reconcile_with_sentence(_forge_result([], "C'est jeudi à dix-huit heures ?"), QUESTION, "en")

    assert "C'est" not in str(refined["corrected_answer"])
    assert "Qu est-ce que" in refined["corrected_answer"]
    assert all(item["corrected_target"] != "C'est" for item in refined["errata"])
    assert ("a", "à") in _pairs(refined["errata"])
    assert repair_line_from_parts(QUESTION, refined["errata"]) == refined["corrected_answer"]


def test_forge_refuses_the_rewrite_as_the_line_to_retype():
    # A listed fix the line can't hold: the whole line is retyped, so its target is what matters.
    unplaceable = {"learner_text": "aller", "corrected_target": "vais", "why_wrong": "", "task_error_type": "grammar"}
    refined = reconcile_with_sentence(_forge_result([unplaceable], "C'est jeudi à dix-huit heures ?"), QUESTION, "en")

    assert "C'est jeudi" not in refined["corrected_answer"]
    assert refined["corrected_answer"] == "Qu est-ce que c est, jeudi à dix-huit heures ?"


def test_forge_refuses_a_listed_rewrite_through_the_whole_refinement():
    listed = {
        "learner_text": QUESTION,
        "corrected_target": "C'est jeudi à dix-huit heures ?",
        "why_wrong": "Plus naturel.",
        "task_error_type": "grammar",
    }
    refined = refine_production_correction(
        _forge_result([listed], "C'est jeudi à dix-huit heures ?"), learner_text=QUESTION, accepted=[], language="en"
    )

    assert "C'est jeudi" not in refined["corrected_answer"]
    assert all("C'est jeudi" not in str(item.get("corrected_target")) for item in refined["errata"])


def test_forge_keeps_another_thing_out_of_the_line():
    refined = reconcile_with_sentence(_forge_result([], "J'ai une voiture."), "J'ai un stylo.", "en")
    assert refined["corrected_answer"] == "J'ai un stylo."
    assert not refined["errata"]


# --- the other surfaces -----------------------------------------------------------------------


def test_courrier_prints_the_learners_line_and_lists_each_change(client, db_session, monkeypatch):
    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    grade = json.loads(_a_grade(LETTER, verdict="partial", errata=LISTED))
    grade["corrected_answer"] = REWRITE
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=json.dumps(grade)))

    body = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": LETTER, "mode": "chat"}, headers=headers).json()
    correction, check = body["user_turn"]["correction"], body["check"]

    assert "C'est jeudi" not in correction["corrected_answer"]
    assert "jeudi à dix-huit heures ?" in correction["corrected_answer"]
    assert check["corrected"] == correction["corrected_answer"]
    listed = {(edit["span"], edit["replacement"]) for edit in check["edits"]}
    assert {("le appartement", "l'appartement"), ("c est bizarre", "c'est bizarre")} <= listed


def test_an_old_courrier_row_shows_its_listed_fixes_and_not_the_stored_sentence():
    from app.services import verdicts

    stored = {"verdict": "partial", "corrected_answer": REWRITE, "errata": LISTED, "correction_debug": {"model": "m"}}
    check = verdicts.from_courrier(stored, text=LETTER)

    assert "C'est jeudi" not in check.corrected
    assert "Qu est-ce que c est" in check.corrected


def test_journal_builds_the_line_from_its_fixes(db_session):
    user = SimpleNamespace(id=None, native_language="en")
    shaped = JournalService(db_session)._shape_correction(
        user,
        {"assessment_status": "checked", "verdict": "needs_revision", "errata": LISTED, "corrected_answer": REWRITE},
        LETTER,
        truncated=False,
    )

    assert "C'est jeudi" not in shaped["corrected_answer"]
    assert "jeudi à dix-huit heures ?" in shaped["corrected_answer"]
    assert ("a dix-huit", "à dix-huit") in {(item["span_fr"], item["corrected_fr"]) for item in shaped["errata"]}


def test_the_scenes_one_chip_is_no_rewrite():
    span, fixed, _note = cc.first_valid_edit(QUESTION, "Qu est-ce que c est,", "C'est", "Plus naturel.", language="en")
    assert fixed != "C'est"
    assert span != "Qu est-ce que c est,"
