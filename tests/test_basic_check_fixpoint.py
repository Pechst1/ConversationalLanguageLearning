"""#857: the basic check never prints a «corrected» line it would still correct.

With no model, the learner's corrected line comes from the rules of
``app.services.correction_contract``. Each rule used to decide from a hand-kept list of
contexts whether it may fire, and kept silent anywhere else; the line was printed as the
right one all the same. Three walk findings show the mechanism:

- #856 «Peut-etre c est a Gus» -> «Peut-être c est à Gus»: «c est» was glued only after a
  listed word, and «peut-être» was not on the list.
- #825 «je ne pas oublie plus» -> «je n'oublie pas plus»: the negation reorder moved «pas»
  behind the verb without reading the «plus» that already closed the negation there.
- #810 «ce n est pas a moi» -> «ce n'est pas a moi»: «a» -> «à» fired only right after the
  verb, so a negation in between stopped it.

The guards below run the check on real learner lines from the walks and assert two things
for each: the corrected line is a fixed point (a second pass makes no edit), and it keeps
none of the slips the check fixes elsewhere (a dropped apostrophe, «pas» + a second
negation word, «pas a» before a noun). The three children's lines are asserted word for
word. A last guard runs the floor's own sentence corpora through the check the same way.
No model call is made anywhere in this file.
"""

from __future__ import annotations

import re

import pytest

from app.core.verdict import span_pattern
from app.services import correction_contract as cc

# ---------------------------------------------------------------------------
# The walk lines and what the basic check must print for them
# ---------------------------------------------------------------------------

#: #856 (walk 17 Nov, a2-en, Courrier day 1).
COURRIER_856 = (
    "Salut Margaux ! Non, ce n est pas mon echarpe, j ai pas de echarpe rouge. Peut-etre c est a Gus ? "
    "Je ne passe pas demain, je suis ailleurs, chez le notaire."
)
#: #825 (walk 16 Nov, a1-de-fresh, Courrier day 1).
COURRIER_825 = "Merci Margaux ! Oui, je passe demain. Je suis tres fatigue, je ne pas oublie plus."
#: #810 (walk 15 Nov, a2-en, Courrier days 1 and 2).
COURRIER_810_DAY1 = "Salut Margaux ! Mais je n ai pas d echarpe, ce n est pas a moi. Peut-être c est a Gus ?"
COURRIER_810_DAY2 = "Mais je suis pas a la maison, je dors a l hotel !"

EXPECTED = [
    pytest.param(
        COURRIER_856,
        "Salut Margaux ! Non, ce n'est pas mon écharpe, j'ai pas d'écharpe rouge. Peut-être c'est à Gus ? "
        "Je ne passe pas demain, je suis ailleurs, chez le notaire.",
        id="856",
    ),
    pytest.param("Peut-etre c est a Gus ?", "Peut-être c'est à Gus ?", id="856s"),
    pytest.param(
        COURRIER_825,
        "Merci Margaux ! Oui, je passe demain. Je suis très fatigue, je n'oublie plus.",
        id="825",
    ),
    pytest.param("je ne pas oublie plus", "je n'oublie plus", id="825s"),
    pytest.param(
        COURRIER_810_DAY1,
        "Salut Margaux ! Mais je n'ai pas d'écharpe, ce n'est pas à moi. Peut-être c'est à Gus ?",
        id="810a",
    ),
    pytest.param(COURRIER_810_DAY2, "Mais je suis pas à la maison, je dors à l'hôtel !", id="810b"),
]


@pytest.mark.parametrize(("line", "right"), EXPECTED)
def test_walk_line(line, right):
    """The children of #857, word for word."""
    assert cc.repair_text(line) == right


def test_courrier_856():
    """#856 done-when, through the Courrier's own model-free pass."""
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    _errata, corrected = service._deterministic_errata(COURRIER_856, language="en")
    assert "Peut-être c'est à Gus ?" in corrected, corrected
    again, corrected_again = service._deterministic_errata(corrected, language="en")
    assert again == [] and corrected_again == corrected, again


#: Learner lines the walks of 11-17 Nov wrote in the Courrier, La Forge and the Journal,
#: word for word. A line here may still hold a slip no rule knows (a participle); what it
#: may not hold is a slip the check fixes elsewhere.
CORPUS = [
    COURRIER_856,
    COURRIER_825,
    COURRIER_810_DAY1,
    COURRIER_810_DAY2,
    "Je m appelle Sam, je suis le petit fils de Odile. Mais je ne suis pas ici pour vendre… Et vous, vous etes qui ?",
    "Je suis Jonas, le petit-fils de Odile. Je suis ici pour la appartement.",
    "Non, je ne vend pas. C est pas simple pour moi, la appartement est de Odile.",
    "Non, je vend pas… Je veux ouvrir une librairie au premier etage… Plus simple pour qui ? Pour Solvel ?",
    "Non, pas ce soir, je dors a l hotel. Margaux, pourquoi elle ne donnait jamais cette clé ? Tu etais son amie ?",
    "Oui, je monte. Je suis fatigue. Je veux voir le appartement.",
    "oui je monte. Odile c est qui pour toi?",
    "Salut Margaux ! Je ne vends pas le appartement. Camille a une clé aussi, c est bizarre. "
    "Qu est-ce que c est, jeudi a dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent",
    "Samedi dernier, il a telephone a la banque.",
    "La semaine derniere, ils ont expliquer la methode de Gus. Mais c est quoi, cette methode ?",
    "Avant-hier, tu as appele la banque.",
    "Hier soir, je suis arrive au Mistral avec la cle de ma grand-mère. Gus m a demande qui j etais, "
    "et Margaux m a donne la cle.",
]
_CORPUS_IDS = [f"w{number}" for number in range(1, len(CORPUS) + 1)]

#: The slips the check fixes, as they would show in a printed line: a lone letter that
#: elides, a space, a word that takes the elision; «pas» doubled by a second negation
#: word; «pas a» in front of an article or a stressed pronoun.
_DROPPED_APOSTROPHE = re.compile(r"(?<![\w'’-])[cjnmtsl] (?=(?:est|ai|a|as|y|en|étais|etais|il|ils)\b)", re.IGNORECASE)
_DOUBLED_NEGATION = re.compile(r"\bpas (?:plus|jamais|rien|personne|aucun|aucune|guère)\b", re.IGNORECASE)
_PAS_A = re.compile(r"\b(?:pas|plus|jamais) a (?=(?:la|le|l'|les|moi|toi|lui|elle|eux|nous|vous)\b)", re.IGNORECASE)


def _residual_slips(line: str) -> list[str]:
    return [m.group(0) for pattern in (_DROPPED_APOSTROPHE, _DOUBLED_NEGATION, _PAS_A) for m in pattern.finditer(line)]


@pytest.mark.parametrize("line", CORPUS, ids=_CORPUS_IDS)
def test_fixpoint(line):
    """A second pass over the corrected walk line makes no edit."""
    fixed = cc.repair_text(line)
    again = [(e.rule_id, e.span, e.replacement) for e in cc.deterministic_edits(fixed)]
    assert again == [], f"{line!r} -> {fixed!r}, second pass: {again}"


@pytest.mark.parametrize("line", CORPUS, ids=_CORPUS_IDS)
def test_no_slip_left(line):
    """The corrected walk line keeps no slip the check fixes elsewhere."""
    fixed = cc.repair_text(line)
    assert _residual_slips(fixed) == [], f"{line!r} -> {fixed!r}"


# ---------------------------------------------------------------------------
# #825: one negation word after the verb, and a comparative «plus» keeps «pas»
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        # the second negation word closes it: «pas» goes
        ("je pas oublie plus.", "je n'oublie plus."),
        ("Il ne pas mange jamais.", "Il ne mange jamais."),
        ("Je ne pas vois personne.", "Je ne vois personne."),
        ("Tu ne pas manges rien.", "Tu ne manges rien."),
        ("Je ne plus oublie pas.", "Je n'oublie plus."),
        # a comparative «plus» is no negation: «pas» stays, as main printed it
        ("Je ne pas suis plus grand que toi.", "Je ne suis pas plus grand que toi."),
        ("Il ne pas parle plus fort.", "Il ne parle pas plus fort."),
        ("Je ne pas mange plus que toi.", "Je ne mange pas plus que toi."),
        ("Je pas parle plus fort.", "Je ne parle pas plus fort."),
        # the plain reorders are kept
        ("Je ne pas parle.", "Je ne parle pas."),
        ("Je pas ai beaucoup de bagages.", "Je n'ai pas beaucoup de bagages."),
        ("Je ne jamais vois rien.", "Je ne vois jamais rien."),
    ],
    ids=[f"n{number}" for number in range(1, 13)],
)
def test_negation(sentence, right):
    """Both negation reorders read the word after the verb."""
    assert cc.repair_text(sentence) == right


# ---------------------------------------------------------------------------
# #810: «a» -> «à» after a negated verb; the lookalikes stay
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "Il n'a pas à manger.",
        "Elle ne l'a pas aimé.",
        "Ce qu'il ne savait pas a été dit.",
        "Elle ne sait pas, Gus a la clé.",
    ],
    ids=["a1", "a2", "a3", "a4"],
)
def test_a_stays(sentence):
    """An «a» after a negation that is avoir, or in another clause, stays."""
    assert cc.repair_text(sentence) == sentence


# ---------------------------------------------------------------------------
# The floor's own sentence corpora: no printed line triggers its own rule again
# ---------------------------------------------------------------------------


def _sentences_of(module) -> list[str]:
    """Every French sentence a test module holds: its module-level lists of strings and
    the first string of each parametrised case."""

    found: list[str] = []
    for value in vars(module).values():
        if isinstance(value, (list, tuple)) and value and all(isinstance(item, str) for item in value):
            found.extend(value)
        for mark in getattr(value, "pytestmark", []) if callable(value) else []:
            if mark.name != "parametrize" or len(mark.args) < 2:
                continue
            for case in mark.args[1]:
                values = getattr(case, "values", case)
                values = values if isinstance(values, (list, tuple)) else (values,)
                first = next((item for item in values if isinstance(item, str)), None)
                if first and " " in first:
                    found.append(first)
    return found


def _floor_sentences() -> list[str]:
    from tests import (
        test_correction_contract,
        test_correction_negative_corpus,
        test_correction_walk_rules,
    )

    seen: dict[str, None] = {}
    for module in (test_correction_contract, test_correction_negative_corpus, test_correction_walk_rules):
        for sentence in _sentences_of(module):
            seen.setdefault(sentence, None)
    for param in EXPECTED:
        seen.setdefault(param.values[0], None)
    for line in CORPUS:
        seen.setdefault(line, None)
    return list(seen)


def test_floor_corpora_settle():
    """#825's guard, widened: every basic-check edit is applied to its sentence, and the
    printed line triggers no further edit of a kind that already fired, nor holds a doubled
    negation the learner did not write."""

    sentences = _floor_sentences()
    assert len(sentences) > 150, len(sentences)
    wrong: list[str] = []
    for sentence in sentences:
        first = cc.deterministic_edits(sentence)
        if not first:
            continue
        fixed = cc.apply_edits(sentence, first)
        fired = {edit.rule_id for edit in first}
        again = [(e.rule_id, e.span) for e in cc.deterministic_edits(fixed) if e.rule_id in fired]
        doubled = len(_DOUBLED_NEGATION.findall(fixed)) > len(_DOUBLED_NEGATION.findall(sentence))
        if again or doubled:
            wrong.append(f"{sentence!r} -> {fixed!r} {again}")
    assert not wrong, f"{len(wrong)} printed lines the check would still correct: {wrong}"


# ---------------------------------------------------------------------------
# #925: a slip written twice is listed twice, and fixed twice in the printed line
# ---------------------------------------------------------------------------

#: #925 (walk 19 Nov, a2-en, Courrier day 1): «n ai» twice.
COURRIER_925 = (
    "Salut Marin ! Je n ai pas vendu l appartement. J ai garde la cle dans ma poche toute la nuit. "
    "Je n ai rien mange, tu connais un bon restaurant ? Peut-etre je reste a Paris, c est fou !"
)
#: More lines with one slip written twice, as learners write them.
TWICE = [
    COURRIER_925,
    "J ai faim et j ai soif.",
    "Je n ai pas la clé, je n ai rien.",
    "C est bizarre, c est fou, c est Paris.",
    "Il m a dit que je suis le petit fils, et il m a donne la cle.",
]


def _erratum(span: str, fix: str) -> dict:
    return {"learner_text": span, "corrected_target": fix, "why_wrong": "", "task_error_type": "orthography"}


#: The Courrier row the walk read: its list says «n'ai · l'appartement · J'ai · c'est · n'ai».
COURRIER_925_ERRATA = [
    _erratum("n ai", "n'ai"),
    _erratum("l appartement", "l'appartement"),
    _erratum("J ai", "J'ai"),
    _erratum("c est", "c'est"),
    _erratum("n ai", "n'ai"),
]


def _journal_row(errata: list[dict]) -> dict:
    return {
        "checker": "model",
        "verdict": "needs_revision",
        "errata": [{"span_fr": e["learner_text"], "corrected_fr": e["corrected_target"]} for e in errata],
    }


#: Each surface's stored row, read by the model or by the rules alone.
_ROWS = {
    "courrier-model": lambda errata: (
        "courrier",
        {"errata": errata, "verdict": "needs_revision", "correction_debug": {"model": "m"}},
    ),
    "courrier-rules": lambda errata: (
        "courrier",
        {"errata": errata, "verdict": "unassessed", "correction_debug": {"fallback_used": True, "failure": "no_model"}},
    ),
    "forge-model": lambda errata: ("forge", {"errata": errata, "verdict": "partial", "correction_debug": {"model": "m"}}),
    "forge-rules": lambda errata: ("forge", {"errata": errata, "assessment_status": "unavailable"}),
    "journal-model": lambda errata: ("journal", _journal_row(errata)),
}


def _printed(row: str, errata: list[dict], line: str) -> str | None:
    from app.services import verdicts

    surface, payload = _ROWS[row](errata)
    return getattr(verdicts, f"from_{surface}")(payload, text=line).corrected


@pytest.mark.parametrize("row", list(_ROWS))
def test_courrier_925(row):
    """#925 done-when: the walk's line, with the errata the walk's row held and with its
    deterministic errata, prints «n'ai» in both places the list names it."""
    for errata in (COURRIER_925_ERRATA, cc.deterministic_errata(COURRIER_925, language="en")):
        printed = _printed(row, errata, COURRIER_925) or ""
        assert "Je n'ai pas vendu" in printed and "Je n'ai rien mange" in printed, printed


def _as_listed(line: str, edits) -> list[dict]:
    """The edits as a model lists them: the slip's own words, without the words the check
    puts in front so that a span is found only there. A span is cut back only when every
    place its words stand in the line is a slip of the same fix (a slip written twice)."""

    bare = []
    for edit in edits:
        wrong, right = edit.span.split(" "), edit.replacement.split(" ")
        while len(wrong) > 1 and len(right) > 1 and wrong[0] == right[0]:
            wrong, right = wrong[1:], right[1:]
        bare.append((" ".join(wrong), " ".join(right)))
    rows = []
    for edit, (wrong, right) in zip(edits, bare, strict=True):
        written = len(list(span_pattern(wrong).finditer(line)))
        listed = sum(1 for pair in bare if pair == (wrong, right))
        rows.append(_erratum(wrong, right) if written == listed else _erratum(edit.span, edit.replacement))
    return rows


def _twice_lines() -> list[str]:
    """The lines, among #925's and the walks', where one fix is listed twice."""
    lines: list[str] = []
    for line in [*TWICE, *CORPUS, *(param.values[0] for param in EXPECTED)]:
        pairs = [(row["learner_text"], row["corrected_target"]) for row in _as_listed(line, cc.deterministic_edits(line))]
        if len(set(pairs)) < len(pairs) and line not in lines:
            lines.append(line)
    return lines


def test_twice_corpus_is_not_empty():
    assert len(_twice_lines()) >= 5, _twice_lines()


@pytest.mark.parametrize("row", list(_ROWS))
def test_every_listed_fix_is_printed(row):
    """#925's guard: for every line with a slip written twice, the printed line is the
    check's own edits applied to it, whichever surface reads the row and whoever wrote it."""
    wrong = []
    for line in _twice_lines():
        edits = cc.deterministic_edits(line)
        printed = _printed(row, _as_listed(line, edits), line)
        if printed != cc.apply_edits(line, edits):
            wrong.append(f"{line!r} -> {printed!r}")
    assert not wrong, wrong


#: One slip written twice, and the model's list naming it twice or once.
TWICE_LINE = "Je n ai pas la clé, je n ai rien."
_N_AI = {"learner_text": "n ai", "corrected_target": "n'ai", "why_wrong": "Apostrophe.", "task_error_type": "orthography", "severity": 1}


def _placed(line: str, errata: list[dict]) -> str:
    """The line with the listed fixes made, each in its own place, as a screen prints it."""
    from app.core.verdict import apply_edits, locate_edits

    rows = [{"span": e.get("learner_text"), "replacement": e.get("corrected_target")} for e in errata]
    return apply_edits(line, locate_edits(line, rows))


def test_a_note_per_place_is_kept():
    """#925, where a list is cleaned: the same words noted twice are two notes when the
    line holds them twice, and one note when it holds them once (#93)."""
    assert len(cc.grounded_errata(TWICE_LINE, [_N_AI, dict(_N_AI)])) == 2
    assert len(cc.grounded_errata("Je n ai pas la clé.", [_N_AI, dict(_N_AI)])) == 1


def test_courrier_clean_keeps_a_note_per_place():
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    service._normalize_erratum = lambda raw, mission, submission_text=None: dict(raw)
    kept = service._clean_errata([_N_AI, dict(_N_AI)], mission=None, submission_text=TWICE_LINE, language="en")
    assert _placed(TWICE_LINE, kept) == "Je n'ai pas la clé, je n'ai rien.", kept
    once = service._clean_errata([_N_AI, dict(_N_AI)], mission=None, submission_text="Je n ai rien.", language="en")
    assert len(once) == 1, once


def test_merges_add_the_rules_second_place():
    """#925, where the rules' fixes join the model's: the model named «n ai» once, the
    rules name both places, and the list ends with both."""
    import inspect

    from app.services import atelier
    from app.services.missions import MissionCorrectionService

    merged = cc.merge_deterministic_errata(TWICE_LINE, [_N_AI], language="en")
    assert _placed(TWICE_LINE, merged) == "Je n'ai pas la clé, je n'ai rien.", merged

    forge = atelier._with_rule_fixes({"errata": [dict(_N_AI)]}, TWICE_LINE, language="en")["errata"]
    assert _placed(TWICE_LINE, forge) == "Je n'ai pas la clé, je n'ai rien.", forge

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    rules, _corrected = service._deterministic_errata(TWICE_LINE, language="en")
    merge = service._merge_deterministic_errata
    where = {"text": TWICE_LINE} if "text" in inspect.signature(merge).parameters else {}
    courrier = merge(
        correction={"errata": [dict(_N_AI)], "verdict": "needs_revision"},
        deterministic_errata=rules,
        corrected_answer="",
        **where,
    )["errata"]
    assert _placed(TWICE_LINE, courrier) == "Je n'ai pas la clé, je n'ai rien.", courrier


def test_merges_keep_one_card_per_fragment():
    """#250 still holds by place: a longer quote of the model's around a rule's fragment
    keeps the fragment off a second card."""
    import inspect

    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    line = "Mon carte est jolie."
    model = {"learner_text": "Mon carte", "corrected_target": "Ma carte", "why_wrong": "carte is feminine.", "task_error_type": "gender_agreement"}
    rule = {"learner_text": "Mon", "corrected_target": "Ma", "why_wrong": "", "task_error_type": "gender_agreement"}
    merge = service._merge_deterministic_errata
    where = {"text": line} if "text" in inspect.signature(merge).parameters else {}
    merged = merge(
        correction={"errata": [model], "verdict": "needs_revision"}, deterministic_errata=[rule], corrected_answer="", **where
    )["errata"]
    assert [item["learner_text"] for item in merged] == ["Mon carte"]


def test_journal_foreground_is_one_of_its_fixes():
    """The Journal's foreground is the first of its listed fixes, not one more: it does not
    land on a right «a» further on."""
    from app.services import verdicts

    line = "Je vais a Paris et il a faim."
    payload = {
        "checker": "model",
        "verdict": "needs_revision",
        "foreground": {"span_fr": "a", "corrected_fr": "à"},
        "errata": [{"span_fr": "a", "corrected_fr": "à"}],
    }
    assert verdicts.from_journal(payload, text=line).corrected == "Je vais à Paris et il a faim."
