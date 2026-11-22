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
#: #996 (walk 22 Nov, a1-de-fresh, Courrier day 1, reply to Gus).
COURRIER_996 = (
    "Bonjour Gus. Je pense que le Mistral est tres bien. Demain je vais a le notaire. "
    "Je suis pas sur pour le appartement. Jonas"
)

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
    # #996: «le» sets the gender of a two-gender noun, and an «a» -> «à» fix that makes
    # «à le» is read again with the other fixes in the line.
    pytest.param("Demain je vais a le notaire.", "Demain je vais au notaire.", id="996a"),
    pytest.param("Je vais à le médecin.", "Je vais au médecin.", id="996b"),
    pytest.param("Je parle de le professeur.", "Je parle du professeur.", id="996c"),
    pytest.param("Je vais a le cafe.", "Je vais au café.", id="996d"),
    pytest.param(
        COURRIER_996,
        "Bonjour Gus. Je pense que le Mistral est très bien. Demain je vais au notaire. "
        "Je suis pas sur pour l'appartement. Jonas",
        id="996",
    ),
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


def test_courrier_996():
    """#996 done-when, through the Courrier's own model-free pass: «au notaire» is printed,
    the fix list names it, and a second pass makes no edit."""
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    errata, corrected = service._deterministic_errata(COURRIER_996, language="de")
    assert "Demain je vais au notaire." in corrected, corrected
    assert "à le" not in corrected, corrected
    assert any(str(item.get("corrected_target") or "").strip().endswith("au") for item in errata), errata
    again, corrected_again = service._deterministic_errata(corrected, language="de")
    assert again == [] and corrected_again == corrected, again


@pytest.mark.parametrize(
    "sentence",
    ["Il essaie de le vendre.", "Je vais de le hôtel à la gare.", "Je dors à le hôtel."],
    ids=["de-le-vendre", "de-le-hotel", "a-le-hotel"],
)
def test_996_no_contraction(sentence):
    """«de le vendre» (a pronoun) and «à le hôtel» (an elision) are never contracted."""
    assert not [e for e in cc.deterministic_edits(sentence) if e.rule_id == "FR_CONTRACTION"]


#: Learner lines the walks of 11-17 Nov wrote in the Courrier, La Forge and the Journal,
#: word for word. A line here may still hold a slip no rule knows (a participle); what it
#: may not hold is a slip the check fixes elsewhere.
CORPUS = [
    COURRIER_856,
    COURRIER_825,
    COURRIER_810_DAY1,
    COURRIER_810_DAY2,
    COURRIER_996,
    "Demain je vais a le notaire.",
    "Je vais à le médecin.",
    "Je parle de le professeur.",
    "Je vais a le cafe.",
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


def test_996_fix_list_names_the_contraction():
    """«a» -> «à» and «cafe» -> «café» each settle alone; the line with both holds «à le
    café». The fix list the learner reads names «a le» -> «au», not «a» -> «à»."""
    edits = [(e.span, e.replacement) for e in cc.deterministic_edits("Je vais a le cafe.")]
    assert edits == [("a le", "au"), ("cafe", "café")], edits
