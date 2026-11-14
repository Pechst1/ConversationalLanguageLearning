"""#250: every correction a learner sees is about the words they wrote.

Two holes the walks kept finding, closed at the one checker every surface shares
(``correction_contract.verify_edit`` / ``reconcile_notes``):

- the span: a near-quote («un grand réunion» for the learner's «une grand réunion»,
  #772) was shown as «You wrote …» although the learner never wrote it. The span is
  now always the learner's own stretch, or the edit is dropped;
- the note: a note quoting French that is neither in the learner's sentence nor in
  the fix («With « tu » …» when nobody is «tu», #193), or claiming «no plural -s» over
  a fix that adds one (#662), is rewritten from the fix itself.
"""
from __future__ import annotations

import pytest

from app.services import correction_contract as cc
from app.services import forge_grading

REUNION = "Aujourd'hui, j'ai une grand réunion très fatigant."


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").casefold().split())


def _quotes(note: str) -> list[str]:
    import re

    return [m.group(1).strip() for m in re.finditer(r"«\s*([^»]+?)\s*»", note or "")]


def test_the_forge_never_quotes_words_the_learner_did_not_write():
    erratum = {
        "learner_text": "un grand réunion",
        "corrected_target": "une grande réunion",
        "why_wrong": "You wrote « un grand réunion »; « réunion » is feminine, so use « une grande réunion ».",
        "repair_hint": "Change the article and add -e to « grand ».",
        "task_error_type": "grammar_target",
    }
    shown, _dropped = forge_grading.held_to_sentence([erratum], REUNION, "en")
    assert shown, "the real slip (grand -> grande) is still shown"
    item = shown[0]
    assert _norm(item["learner_text"]) in _norm(REUNION), item
    fixed = _norm(REUNION.replace(item["learner_text"], item["corrected_target"]))
    for key in ("why_wrong", "repair_hint"):
        for quote in _quotes(item.get(key) or ""):
            assert _norm(quote) in _norm(REUNION) or _norm(quote) in fixed, (key, quote)
    assert "article" not in (item.get("repair_hint") or "").lower(), "the article was right"


def test_a_quote_that_matches_nothing_the_learner_wrote_is_dropped():
    assert cc.verify_edit("Je vois le chien.", "la maison", "la maison bleue", strict_span=False).ok is False


@pytest.mark.parametrize(
    ("text", "span", "replacement", "note"),
    [
        # #193: «tu» is nowhere in the sentence
        ("Odile est parti parce que la restaurant est fermé.", "est", "es", "With « tu », « est » must be « es »."),
    ],
)
def test_a_note_quoting_french_from_another_sentence_is_rewritten(text, span, replacement, note):
    assert cc.note_quotes_hold(note, span, replacement, text) is False
    rewritten = cc.note_for_form(span, replacement, note, language="en", context=text)
    assert "tu" not in _quotes(rewritten)


@pytest.mark.parametrize(
    ("text", "span", "replacement", "note"),
    [
        ("Pourquoi tu veut partager ?", "tu veut", "tu veux", "With « tu », « vouloir » ends in -x."),
        ("Je ai oublié.", "Je ai", "J'ai", "Before a vowel, « je » elides to « j' »: « J'ai »."),
        ("Il a deux chat.", "chat", "chats", "After « deux », « chat » takes « -s »."),
        ("Elle est allé.", "allé", "allée", "« être » + participle agrees: « allée »."),
    ],
)
def test_a_note_that_points_at_the_learner_or_the_fix_is_kept(text, span, replacement, note):
    assert cc.note_quotes_hold(note, span, replacement, text) is True
    assert cc.note_for_form(span, replacement, note, language="en", context=text) == note


def test_a_note_saying_no_plural_over_a_fix_that_adds_one_is_rewritten():
    """#662: «pas de serviettes» under «singular nouns take no plural -s»."""
    text = "Non, je n'ai pas des serviette. Pourquoi tu veut partager ?"
    erratum = {
        "learner_text": "pas des serviette",
        "corrected_target": "pas de serviettes",
        "why_wrong": "After negation, des becomes de; singular nouns take no plural -s.",
        "task_error_type": "grammar_target",
    }
    [shown] = cc.grounded_errata(text, [erratum], language="en")
    assert "singular" not in shown["why_wrong"].lower()
    assert "de serviettes" in shown["why_wrong"]


def test_a_note_telling_the_learner_to_add_the_plural_is_kept():
    note = "After « deux », the noun is plural: add -s."
    assert cc.note_for_form("chat", "chats", note, language="en", context="Il a deux chat.") == note
