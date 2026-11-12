"""#662: a correction card and its note name the same form.

Live walk 10 Nov, Courrier letter 4 of 4. The learner wrote «Non, je n’ai pas des
serviette. Pourquoi tu veut partager la commande avec ta voisine ?». The card printed
«pas de serviettes» and the note under it said «singular nouns take no plural -s». The
model's sentence and the rules each changed the noun after the note about it was
written, and nothing held the finished card to its notes. These tests drive the card
builder (``verify_correction``) and the rules with the walk's line. No model is called.
"""

from __future__ import annotations

import re
import unicodedata

import pytest

from app.services import correction_contract as cc

LINE = "Non, je n’ai pas des serviette. Pourquoi tu veut partager la commande avec ta voisine ?"
MODEL_SENTENCE = "Non, je n’ai pas de serviettes. Pourquoi tu veux partager la commande avec ta voisine ?"
SINGULAR_NOTE = "After negation, des becomes de; singular nouns take no plural -s."
TU = {
    "learner_text": "tu veut",
    "corrected_target": "tu veux",
    "why_wrong": "With tu, vouloir ends in -x.",
    "task_error_type": "grammar",
}
_QUOTE = re.compile(r"«\s*([^«»]+?)\s*»")


def _fold(text: object) -> str:
    out = unicodedata.normalize("NFC", str(text or "")).replace("’", "'").casefold()
    return " ".join(out.split())


def _holds(text: str, fragment: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(_fold(fragment))}(?!\w)", _fold(text)) is not None


def _card_problems(line: str, checked: cc.CheckedCorrection) -> list[str]:
    """What a learner would see contradict itself: a fix the line doesn't print, or a note
    quoting a form about the fix that neither the learner's line nor the card holds."""

    problems = []
    for item in checked.errata:
        if not cc.is_about_the_line(item):
            continue
        fix, span = str(item.get("corrected_target") or ""), str(item.get("learner_text") or "")
        if fix and not _holds(checked.corrected, fix):
            problems.append(f"fix «{fix}» is not in the card «{checked.corrected}»")
        words = set(re.findall(r"\w+", _fold(fix + " " + span)))
        for key in ("why_wrong", "repair_hint"):
            for quoted in _QUOTE.findall(str(item.get(key) or "")):
                if len(quoted.strip()) <= 1 or not (set(re.findall(r"\w+", _fold(quoted))) & words):
                    continue
                if not (_holds(line, quoted) or _holds(checked.corrected, quoted)):
                    problems.append(f"{key} quotes «{quoted}», in neither «{line}» nor «{checked.corrected}»")
    return problems


def test_singular_note_keeps_noun():
    # The model lists «des» -> «de» with a note that says the noun stays singular, and its
    # sentence adds the -s anyway. The card printed «de serviettes» under that note.
    erratum = {"learner_text": "des", "corrected_target": "de", "why_wrong": SINGULAR_NOTE, "task_error_type": "grammar"}
    checked = cc.verify_correction(LINE, MODEL_SENTENCE, [erratum, TU], language="en")

    assert "serviettes" not in checked.corrected, (
        f"the card prints «{checked.corrected}» under the note «{SINGULAR_NOTE}»"
    )
    assert checked.corrected == "Non, je n’ai pas de serviette. Pourquoi tu veux partager la commande avec ta voisine ?"
    assert not [item for item in checked.errata if "serviettes" in str(item.get("corrected_target"))]
    assert _card_problems(LINE, checked) == []


def test_walk_card_prints_note_form():
    # «Done when» of #662: the model's sentence says «de serviettes», its note «pas de serviette».
    erratum = {
        "learner_text": "pas des serviette",
        "corrected_target": "pas de serviette",
        "why_wrong": SINGULAR_NOTE,
        "task_error_type": "grammar",
    }
    checked = cc.verify_correction(LINE, MODEL_SENTENCE, [erratum, TU], language="en")

    assert "pas de serviette." in checked.corrected
    assert "tu veux" in checked.corrected
    assert _card_problems(LINE, checked) == []


def test_note_rewritten_from_fix():
    # The model's fix says «serviettes», its note quotes «pas de serviette»: the card would
    # print one form and explain another. The note is written from the fix the card prints.
    erratum = {
        "learner_text": "pas des serviette",
        "corrected_target": "pas de serviettes",
        "why_wrong": "After negation, des becomes de: « pas de serviette ».",
        "task_error_type": "grammar",
    }
    checked = cc.verify_correction(LINE, MODEL_SENTENCE, [erratum, TU], language="en")

    assert _card_problems(LINE, checked) == []
    shown = next(item for item in checked.errata if item["learner_text"] == "pas des serviette")
    assert "pas de serviettes" in shown["why_wrong"]


def test_rule_note_quotes_card():
    # The rules alone (no model): «des serviette» settles to «de serviettes» after the
    # negation, and the plural note quoted «des de serviettes», a form nobody wrote.
    errata = cc.deterministic_errata(LINE, language="en")
    checked = cc.verify_correction(LINE, None, errata, language="en")

    assert "de serviettes" in checked.corrected
    for item in errata:
        assert "des de" not in item["why_wrong"], item["why_wrong"]
    assert _card_problems(LINE, checked) == []


@pytest.mark.parametrize("language", ["en", "fr", "de"])
def test_widened_fix_two_reasons(language):
    # «des serviette» -> «de serviettes» changes two words for two reasons: the note names both.
    plural = next(item for item in cc.deterministic_errata(LINE, language=language) if "serviette" in item["learner_text"])
    assert (plural["learner_text"], plural["corrected_target"]) == ("des serviette", "de serviettes")
    quoted = _QUOTE.findall(plural["why_wrong"])
    assert "de serviettes" in quoted, plural["why_wrong"]
    assert "de" in quoted, plural["why_wrong"]  # the negation's own rule, «des» becomes «de»


def test_quoted_note_keeps_noun():
    # The same contradiction with the note quoting its own fix: «pas de serviette» under a card
    # that would print «serviettes». The card keeps the form the note quotes.
    erratum = {
        "learner_text": "des",
        "corrected_target": "de",
        "why_wrong": "After negation, des becomes de: « pas de serviette ».",
        "task_error_type": "grammar",
    }
    checked = cc.verify_correction(LINE, MODEL_SENTENCE, [erratum, TU], language="en")

    assert "pas de serviette." in checked.corrected, checked.corrected
    assert _card_problems(LINE, checked) == []


# Review of #706: a change only the sentence makes next to a listed fix is a real correction
# when the fix's note says nothing against it. The card keeps it, listed as its own fix.
NEIGHBOURS = [
    ("Les enfant mange du pain.", "Les enfants mangent du pain.", "enfant", "enfants", "Plural after les.", "mange", "mangent"),
    ("Il a deux chat noir.", "Il a deux chats noirs.", "chat", "chats", "Plural after deux.", "noir", "noirs"),
    (
        "Les enfant mange du pain.",
        "Les enfants mangent du pain.",
        "enfant",
        "enfants",
        "In « Les enfant mange », the noun takes the plural of les.",
        "mange",
        "mangent",
    ),
]


@pytest.mark.parametrize(("line", "sentence", "span", "fix", "note", "near", "near_fix"), NEIGHBOURS)
def test_neighbour_fix_kept(line, sentence, span, fix, note, near, near_fix):
    erratum = {"learner_text": span, "corrected_target": fix, "why_wrong": note, "task_error_type": "grammar"}
    checked = cc.verify_correction(line, sentence, [erratum], language="en")

    assert checked.corrected == sentence, f"the card prints «{checked.corrected}»; refused: {checked.refused}"
    derived = [(item["learner_text"], item["corrected_target"]) for item in checked.errata if item.get("derived_from_sentence")]
    assert derived == [(near, near_fix)]
    assert _card_problems(line, checked) == []
