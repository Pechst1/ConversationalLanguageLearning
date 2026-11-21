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
# #925: a slip written twice is fixed twice in the printed line
# ---------------------------------------------------------------------------

#: #925 (walk 19 Nov, a2-en, Courrier day 1): «n'ai» listed twice, printed once.
COURRIER_925 = (
    "Salut Marin ! Je n ai pas vendu l appartement. J ai garde la cle dans ma poche toute la nuit. "
    "Je n ai rien mange, tu connais un bon restaurant ? Peut-etre je reste a Paris, c est fou !"
)
#: #925, seen again 21 Nov (a2-en, Courrier day 1 to Margaux): the second «j ai» left.
COURRIER_925_AGAIN = (
    "Salut Margaux ! Je n ai pas d echarpe, je suis anglais, j ai toujours froid mais j ai oublie "
    "mon echarpe a Manchester."
)


def _stored_basic_check(line: str) -> list[dict]:
    """The errata the Courrier stores for ``line`` with no model: its rules, then the line
    rebuilt from them (``MissionCorrectionService.correct_submission``'s basic path)."""
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    errata, sentence = service._deterministic_errata(line, language="en")
    return cc.verify_correction(line, sentence, errata, language="en").errata


def _printed_lines(line: str, errata: list[dict]) -> dict[str, str]:
    """What Courrier, La Forge and the Journal print for ``line`` and its errata, read
    as the model's check and as the rules' (no model)."""
    from app.services import verdicts

    journal_rows = [
        {"span_fr": item.get("learner_text"), "corrected_fr": item.get("corrected_target"), "note_native": "x"}
        for item in errata
    ]
    verdict_list = {
        "courrier/model": verdicts.from_courrier(
            {"errata": errata, "verdict": "needs_revision", "correction_debug": {"model": "m"}}, text=line
        ),
        "courrier/rules": verdicts.from_courrier(
            {"errata": errata, "verdict": "needs_revision", "correction_debug": {"fallback_used": True}}, text=line
        ),
        "forge/model": verdicts.from_forge(
            {"errata": errata, "verdict": "wrong", "assessment_status": "checked", "correction_debug": {"model": "m"}},
            text=line,
        ),
        "forge/rules": verdicts.from_forge(
            {"errata": errata, "verdict": "wrong", "assessment_status": "unavailable"}, text=line
        ),
        "journal/model": verdicts.from_journal({"checker": "model", "errata": journal_rows}, text=line),
        "journal/rules": verdicts.from_journal({"checker": "rules", "errata": journal_rows}, text=line),
    }
    return {name: verdict.corrected or line for name, verdict in verdict_list.items()}


@pytest.mark.parametrize("line", [COURRIER_925, COURRIER_925_AGAIN], ids=["925", "925b"])
def test_slip_written_twice_is_fixed_twice(line):
    """#925 done-when: the walk's line, through each surface with its basic-check errata,
    prints every listed fix."""
    errata = _stored_basic_check(line)
    listed = [item["learner_text"] for item in errata]
    assert len(listed) > len(set(listed)), listed  # the slip is listed twice, as on the walk
    for surface, printed in _printed_lines(line, errata).items():
        assert printed == cc.repair_text(line), (surface, printed)
    printed = _printed_lines(COURRIER_925, _stored_basic_check(COURRIER_925))["courrier/model"]
    assert "Je n'ai pas" in printed and "Je n'ai rien" in printed, printed


def _change_of(span: str, replacement: str) -> tuple[str, str]:
    """The characters a fix changes, without the words it quotes around them."""
    lead = 0
    while lead < min(len(span), len(replacement)) and span[lead] == replacement[lead]:
        lead += 1
    trail = 0
    while trail < min(len(span), len(replacement)) - lead and span[-1 - trail] == replacement[-1 - trail]:
        trail += 1
    return span[lead : len(span) - trail], replacement[lead : len(replacement) - trail]


def _slip_written_twice(line: str) -> bool:
    changes = [_change_of(edit.span, edit.replacement) for edit in cc.deterministic_edits(line)]
    return len(changes) != len(set(changes))


_TWICE = [line for line in [*CORPUS, COURRIER_925, COURRIER_925_AGAIN] if _slip_written_twice(line)]


@pytest.mark.parametrize("line", _TWICE, ids=[f"t{number}" for number in range(1, len(_TWICE) + 1)])
def test_every_listed_fix_is_printed(line):
    """#925 property: a corpus line with a slip written twice prints exactly the basic
    check's edits applied to it, on every surface."""
    assert len(_TWICE) >= 5, _TWICE
    right = cc.apply_edits(line, cc.deterministic_edits(line))
    errata = _stored_basic_check(line)
    for surface, printed in _printed_lines(line, errata).items():
        assert printed == right, (surface, printed)


def test_a_note_given_twice_changes_no_right_word():
    """#931's failed review (#93): the same fix listed twice takes a second place only
    when that place is a slip too. «il a faim» keeps its «a»."""
    line = "Je vais a Paris et il a faim."
    note = {"learner_text": "a", "corrected_target": "à", "why_wrong": "Preposition à.", "task_error_type": "orthography"}
    for surface, printed in _printed_lines(line, [note, dict(note)]).items():
        assert printed == "Je vais à Paris et il a faim.", (surface, printed)
    assert len(cc.grounded_errata(line, [note, dict(note)], language="en")) == 1
